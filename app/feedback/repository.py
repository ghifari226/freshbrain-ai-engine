from sqlalchemy.ext.asyncio import AsyncSession

from app.feedback.models import Feedback


class FeedbackRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, feedback: Feedback) -> Feedback:
        self.session.add(feedback)
        await self.session.flush()
        return feedback
