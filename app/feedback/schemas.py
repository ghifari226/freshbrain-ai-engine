from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    message_id: str
    conversation_id: str
    user_id: str
    role: str
    rating: str
    reason: str | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: str
