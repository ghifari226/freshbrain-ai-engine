from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat.orchestration import generate_title
from app.ai.chat.schemas import ChatRequest, ChatResponse, TitleRequest, TitleResponse
from app.ai.chat.service import ChatService
from app.core.config import get_settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.core.security import TokenClaims, get_current_claims

# Router chat menangani transport HTTP; alur AI tetap berada di service dan orchestration.
router = APIRouter(tags=["chat"])
Session = Annotated[AsyncSession, Depends(get_session)]
Claims = Annotated[TokenClaims, Depends(get_current_claims)]


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat(
    request: Request,
    body: ChatRequest,
    session: Session,
    claims: Claims,
) -> ChatResponse:
    return await ChatService(session).chat(body, claims.user_id, claims.allowed_scopes)


@router.post("/chat/stream")
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat_stream(
    request: Request,
    body: ChatRequest,
    session: Session,
    claims: Claims,
) -> StreamingResponse:
    events = await ChatService(session).chat_stream(body, claims.user_id, claims.allowed_scopes)
    return StreamingResponse(events, media_type="text/event-stream")


@router.post("/chat/title", response_model=TitleResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def title(
    request: Request,
    body: TitleRequest,
    claims: Claims,
) -> TitleResponse:
    return TitleResponse(title=await generate_title(body.message))
