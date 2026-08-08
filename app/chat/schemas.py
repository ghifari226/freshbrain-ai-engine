from pydantic import BaseModel


class ChatRequest(BaseModel):
    # user_id/role/allowed_scopes used to live here too — removed since the
    # verified JWT (see app/core/security.py) is the only source for those
    # now. The frontend still sends them in the body; FastAPI/Pydantic just
    # ignores unrecognized fields, so that's harmless.
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    message_id: str
    title: str | None = None


class TitleRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class TitleResponse(BaseModel):
    title: str
