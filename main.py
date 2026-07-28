import logging
from contextlib import asynccontextmanager
from uuid import UUID

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import verify_mock_token
from db import repository
from db.connection import close_pool, init_pool
from orchestration.loop import extract_final_text, run_chat_loop

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


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, authorization: str | None = Header(default=None)) -> ChatResponse:
    # verify_mock_token is a temporary stand-in for chat-gateway's real
    # signature verification (see auth.py) — delete once chat-gateway exists
    # and signs real tokens.
    verify_mock_token(authorization, req.user_id)

    if req.conversation_id:
        try:
            conversation_id = UUID(req.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id")
        if not await repository.conversation_exists(conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        history = await repository.get_messages(conversation_id)
    else:
        conversation_id = await repository.create_conversation()
        history = []

    await repository.add_message(conversation_id, "user", req.message)
    messages = history + [{"role": "user", "content": req.message}]

    # Fail closed: an omitted allowed_scopes means no tools are visible,
    # not unrestricted access. Real callers (chat-interface) always send a
    # real (possibly empty) list once logged in.
    new_messages = await run_chat_loop(messages, allowed_scopes=req.allowed_scopes or [])

    final_message_id = None
    for msg in new_messages:
        final_message_id = await repository.add_message(conversation_id, msg["role"], msg["content"])

    await repository.touch_conversation(conversation_id)

    final_text = extract_final_text(new_messages[-1]["content"])

    return ChatResponse(
        answer=final_text,
        conversation_id=str(conversation_id),
        message_id=str(final_message_id),
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
