import logging
from contextlib import asynccontextmanager
from uuid import UUID

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import verify_mock_token, verify_mock_token_unscoped
from db import repository
from db.connection import close_pool, init_pool
from orchestration.loop import extract_final_text, generate_title, run_chat_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="FreshBrain AI Engine", lifespan=lifespan)

# Local-dev only: chat-interface runs on a Vite dev server whose port can
# shift (5173, 5174, ...). Tighten this to explicit origins before deploying
# anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    # Per auth-contract.md's "every subsequent request" shape. role is
    # stored as a timestamped snapshot on feedback/tool_call_logs rows (not
    # implemented yet) but never treated as current truth; allowed_scopes is
    # what actually gates which tools this request can see — see
    # orchestration/loop.py's TOOL_SCOPES/scope_grants().
    user_id: str | None = None
    role: str | None = None
    allowed_scopes: list[str] | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    message_id: str
    # Only ever populated on a message after the first one — the first
    # message's title comes from the separate POST /chat/title call
    # instead (see generate_title/TitleRequest below), so the visible
    # answer never waits on title generation. Present when ai-engine
    # detects a mid-conversation rename request as a side effect of
    # answering (orchestration/loop.py's rename_conversation tool).
    title: str | None = None


class FeedbackRequest(BaseModel):
    message_id: str
    conversation_id: str
    user_id: str
    role: str
    rating: str
    reason: str | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: str


class TitleRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class TitleResponse(BaseModel):
    title: str


class ConversationMessageOut(BaseModel):
    id: str
    role: str
    text: str
    createdAt: str


class ConversationOut(BaseModel):
    id: str
    title: str
    timestamp: str
    messages: list[ConversationMessageOut]


class ConversationsListResponse(BaseModel):
    conversations: list[ConversationOut]


class RenameConversationRequest(BaseModel):
    title: str
    user_id: str
    role: str


class RenameConversationResponse(BaseModel):
    conversation_id: str
    title: str


class DeleteConversationRequest(BaseModel):
    user_id: str
    role: str


class DeleteConversationResponse(BaseModel):
    conversation_id: str


def _conversation_message_to_out(row: dict) -> ConversationMessageOut | None:
    """Maps a stored `messages` row (Claude-native content — a plain string
    for real user turns, a list of text/tool_use blocks for assistant turns,
    or a list of tool_result blocks for synthetic tool-round-trip turns) to
    the flat display text chat-interface expects. Returns None for rows
    that shouldn't render at all: synthetic tool_result turns, and
    assistant turns that were pure tool_use with no accompanying text."""
    content = row["content"]
    if row["role"] == "user":
        if not isinstance(content, str):
            return None
        text = content
    else:
        text = extract_final_text(content) if isinstance(content, list) else str(content)
        if not text:
            return None
    return ConversationMessageOut(
        id=str(row["id"]),
        role=row["role"],
        text=text,
        createdAt=row["created_at"].isoformat(),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, authorization: str | None = Header(default=None)) -> ChatResponse:
    # verify_mock_token is a temporary stand-in for chat-gateway's real
    # signature verification (see auth.py) — delete once chat-gateway exists
    # and signs real tokens.
    verify_mock_token(authorization, req.user_id)

    is_new_conversation = not req.conversation_id
    if req.conversation_id:
        try:
            conversation_id = UUID(req.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id")
        if not await repository.conversation_exists(conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        history = await repository.get_messages(conversation_id)
    else:
        try:
            user_id = UUID(req.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id")
        conversation_id = await repository.create_conversation(user_id)
        history = []

    await repository.add_message(conversation_id, "user", req.message)
    messages = history + [{"role": "user", "content": req.message}]

    # Fail closed: an omitted allowed_scopes means no tools are visible,
    # not unrestricted access. Real callers (chat-interface) always send a
    # real (possibly empty) list once logged in. allow_rename is only
    # offered mid-conversation — a brand-new conversation's title comes
    # from POST /chat/title instead (see auth-contract.md).
    new_messages, renamed_title = await run_chat_loop(
        messages,
        allowed_scopes=req.allowed_scopes or [],
        allow_rename=not is_new_conversation,
    )

    final_message_id = None
    for msg in new_messages:
        final_message_id = await repository.add_message(conversation_id, msg["role"], msg["content"])

    await repository.touch_conversation(conversation_id)
    if renamed_title:
        await repository.update_conversation_title(conversation_id, renamed_title)

    final_text = extract_final_text(new_messages[-1]["content"])

    return ChatResponse(
        answer=final_text,
        conversation_id=str(conversation_id),
        message_id=str(final_message_id),
        title=renamed_title,
    )


@app.post("/feedback", response_model=FeedbackResponse)
async def feedback(
    req: FeedbackRequest, authorization: str | None = Header(default=None)
) -> FeedbackResponse:
    verify_mock_token(authorization, req.user_id)

    if req.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="Invalid rating")
    if req.rating == "down" and not req.reason:
        raise HTTPException(status_code=400, detail="reason is required for a down rating")

    feedback_id = await repository.add_feedback(
        UUID(req.message_id),
        UUID(req.conversation_id),
        UUID(req.user_id),
        req.role,
        req.rating,
        req.reason,
        req.comment,
    )
    return FeedbackResponse(id=str(feedback_id))


@app.post("/chat/title", response_model=TitleResponse)
async def chat_title(
    req: TitleRequest, authorization: str | None = Header(default=None)
) -> TitleResponse:
    # No user_id on this contract (titling isn't RBAC/scope-gated) — see
    # verify_mock_token_unscoped's docstring.
    verify_mock_token_unscoped(authorization)
    title = await generate_title(req.message)
    return TitleResponse(title=title)


@app.get("/conversations", response_model=ConversationsListResponse)
async def get_conversations(
    user_id: str, role: str, authorization: str | None = Header(default=None)
) -> ConversationsListResponse:
    verify_mock_token(authorization, user_id)
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    rows = await repository.list_conversations(user_uuid)
    conversations = [
        ConversationOut(
            id=str(row["id"]),
            title=row["title"] or "",
            timestamp=row["last_active_at"].isoformat(),
            messages=[
                out
                for out in (_conversation_message_to_out(m) for m in row["messages"])
                if out is not None
            ],
        )
        for row in rows
    ]
    return ConversationsListResponse(conversations=conversations)


@app.patch("/conversations/{conversation_id}", response_model=RenameConversationResponse)
async def rename_conversation(
    conversation_id: str,
    req: RenameConversationRequest,
    authorization: str | None = Header(default=None),
) -> RenameConversationResponse:
    verify_mock_token(authorization, req.user_id)
    try:
        conv_uuid = UUID(conversation_id)
        user_uuid = UUID(req.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")

    renamed = await repository.rename_conversation(conv_uuid, user_uuid, req.title)
    if not renamed:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return RenameConversationResponse(conversation_id=conversation_id, title=req.title)


@app.delete("/conversations/{conversation_id}", response_model=DeleteConversationResponse)
async def delete_conversation(
    conversation_id: str,
    req: DeleteConversationRequest,
    authorization: str | None = Header(default=None),
) -> DeleteConversationResponse:
    verify_mock_token(authorization, req.user_id)
    try:
        conv_uuid = UUID(conversation_id)
        user_uuid = UUID(req.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")

    deleted = await repository.delete_conversation(conv_uuid, user_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return DeleteConversationResponse(conversation_id=conversation_id)
