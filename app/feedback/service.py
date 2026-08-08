from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.service import parse_uuid
from app.feedback.models import Feedback
from app.feedback.repository import FeedbackRepository
from app.feedback.schemas import FeedbackRequest, FeedbackResponse


class FeedbackService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = FeedbackRepository(session)

    async def add(self, request: FeedbackRequest, user_id: str, role: str) -> FeedbackResponse:
        # user_id/role come from the verified JWT (see feedback/router.py),
        # not the request body — see FeedbackRequest's comment.
        if request.rating not in {"up", "down"}:
            raise HTTPException(status_code=400, detail="Invalid rating")
        if request.rating == "down" and not request.reason:
            raise HTTPException(
                status_code=400,
                detail="reason is required for a down rating",
            )
        feedback = await self.repository.add(
            Feedback(
                message_id=parse_uuid(request.message_id),
                conversation_id=parse_uuid(request.conversation_id),
                user_id=parse_uuid(user_id),
                role=role,
                rating=request.rating,
                reason=request.reason,
                comment=request.comment,
            )
        )
        await self.session.commit()
        return FeedbackResponse(id=str(feedback.id))
