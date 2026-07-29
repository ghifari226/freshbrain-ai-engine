from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.orchestration import generate_title
from app.chat.schemas import ChatRequest, ChatResponse, TitleRequest, TitleResponse
from app.chat.service import ChatService
from app.core.database import get_session
from app.core.security import authenticated_user_id, verify_unscoped_token

router = APIRouter(tags=["chat"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: Session,
    authorization: str | None = Header(default=None),
) -> ChatResponse:
    authenticated_user_id(request.user_id or "", authorization)
    return await ChatService(session).chat(request)


@router.post("/chat/title", response_model=TitleResponse)
async def title(
    request: TitleRequest,
    authorization: str | None = Header(default=None),
) -> TitleResponse:
    verify_unscoped_token(authorization)
    return TitleResponse(title=await generate_title(request.message))
