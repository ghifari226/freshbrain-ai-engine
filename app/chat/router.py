from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.orchestration import generate_title
from app.chat.schemas import ChatRequest, ChatResponse, TitleRequest, TitleResponse
from app.chat.service import ChatService
from app.core.database import get_session
from app.core.security import TokenClaims, get_current_claims

router = APIRouter(tags=["chat"])
Session = Annotated[AsyncSession, Depends(get_session)]
Claims = Annotated[TokenClaims, Depends(get_current_claims)]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: Session,
    claims: Claims,
) -> ChatResponse:
    # Token claims are authoritative — user_id/allowed_scopes never come
    # from the body (see ChatRequest's comment).
    return await ChatService(session).chat(request, claims.user_id, claims.allowed_scopes)


@router.post("/chat/title", response_model=TitleResponse)
async def title(
    request: TitleRequest,
    claims: Claims,
) -> TitleResponse:
    return TitleResponse(title=await generate_title(request.message))
