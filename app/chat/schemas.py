from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    user_id: str | None = None
    role: str | None = None
    allowed_scopes: list[str] | None = None


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
