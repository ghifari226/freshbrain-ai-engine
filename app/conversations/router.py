from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.schemas import (
    ConversationsListResponse,
    DeleteConversationRequest,
    DeleteConversationResponse,
    RenameConversationRequest,
    RenameConversationResponse,
)
from app.conversations.service import ConversationService
from app.core.database import get_session
from app.core.security import authenticated_user_id

router = APIRouter(prefix="/conversations", tags=["conversations"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=ConversationsListResponse)
async def list_conversations(
    session: Session,
    user_id: str,
    role: str,
    authorization: str | None = Header(default=None),
) -> ConversationsListResponse:
    authenticated_user_id(user_id, authorization)
    return await ConversationService(session).list(user_id)


@router.patch("/{conversation_id}", response_model=RenameConversationResponse)
async def rename_conversation(
    conversation_id: str,
    request: RenameConversationRequest,
    session: Session,
    authorization: str | None = Header(default=None),
) -> RenameConversationResponse:
    authenticated_user_id(request.user_id, authorization)
    await ConversationService(session).rename(conversation_id, request.user_id, request.title)
    return RenameConversationResponse(
        conversation_id=conversation_id,
        title=request.title,
    )


@router.delete("/{conversation_id}", response_model=DeleteConversationResponse)
async def delete_conversation(
    conversation_id: str,
    session: Session,
    request: Annotated[DeleteConversationRequest, Body()],
    authorization: str | None = Header(default=None),
) -> DeleteConversationResponse:
    authenticated_user_id(request.user_id, authorization)
    await ConversationService(session).delete(conversation_id, request.user_id)
    return DeleteConversationResponse(conversation_id=conversation_id)
