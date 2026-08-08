from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    # user_id/role used to live here too — removed since the verified JWT
    # (see app/core/security.py) is the only source for identity now
    # (role is still persisted on the Feedback row, just sourced from the
    # token instead of the body — see feedback/service.py's add()). The
    # frontend still sends both in the body; FastAPI/Pydantic just ignores
    # unrecognized fields, so that's harmless.
    message_id: str
    conversation_id: str
    rating: str
    reason: str | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: str
