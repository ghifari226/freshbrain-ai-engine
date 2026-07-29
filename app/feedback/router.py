from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import authenticated_user_id
from app.feedback.schemas import FeedbackRequest, FeedbackResponse
from app.feedback.service import FeedbackService

router = APIRouter(tags=["feedback"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(
    request: FeedbackRequest,
    session: Session,
    authorization: str | None = Header(default=None),
) -> FeedbackResponse:
    authenticated_user_id(request.user_id, authorization)
    return await FeedbackService(session).add(request)
