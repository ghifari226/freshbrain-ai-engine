from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.schemas import (
    ConversationsListResponse,
    DeleteConversationResponse,
    RenameConversationRequest,
    RenameConversationResponse,
)
from app.conversations.service import ConversationService
from app.core.database import get_session
from app.core.security import TokenClaims, get_current_claims

router = APIRouter(prefix="/conversations", tags=["conversations"])
Session = Annotated[AsyncSession, Depends(get_session)]
Claims = Annotated[TokenClaims, Depends(get_current_claims)]


@router.get("", response_model=ConversationsListResponse)
async def list_conversations(
    session: Session,
    claims: Claims,
) -> ConversationsListResponse:
    return await ConversationService(session).list(claims.user_id)


@router.patch("/{conversation_id}", response_model=RenameConversationResponse)
async def rename_conversation(
    conversation_id: str,
    request: RenameConversationRequest,
    session: Session,
    claims: Claims,
) -> RenameConversationResponse:
    # Token claims are authoritative — see chat/router.py's chat() for why.
    await ConversationService(session).rename(conversation_id, claims.user_id, request.title)
    return RenameConversationResponse(
        conversation_id=conversation_id,
        title=request.title,
    )


@router.delete("/{conversation_id}", response_model=DeleteConversationResponse)
async def delete_conversation(
    conversation_id: str,
    session: Session,
    claims: Claims,
) -> DeleteConversationResponse:
    await ConversationService(session).delete(conversation_id, claims.user_id)
    return DeleteConversationResponse(conversation_id=conversation_id)
