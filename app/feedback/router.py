from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import TokenClaims, get_current_claims
from app.feedback.schemas import FeedbackRequest, FeedbackResponse
from app.feedback.service import FeedbackService

router = APIRouter(tags=["feedback"])
Session = Annotated[AsyncSession, Depends(get_session)]
Claims = Annotated[TokenClaims, Depends(get_current_claims)]


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(
    request: FeedbackRequest,
    session: Session,
    claims: Claims,
) -> FeedbackResponse:
    return await FeedbackService(session).add(request, claims.user_id, claims.role)
