import logging
from contextlib import asynccontextmanager
from uuid import UUID

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
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

    new_messages = await run_chat_loop(messages)

    for msg in new_messages:
        await repository.add_message(conversation_id, msg["role"], msg["content"])

    await repository.touch_conversation(conversation_id)

    final_text = extract_final_text(new_messages[-1]["content"])

    return ChatResponse(answer=final_text, conversation_id=str(conversation_id))
