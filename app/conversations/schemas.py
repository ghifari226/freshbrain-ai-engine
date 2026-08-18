from pydantic import BaseModel


# Schema Pydantic menjaga kontrak data di batas masuk dan keluar API.
class ConversationMessageOut(BaseModel):
    id: str
    role: str
    text: str
    createdAt: str


class ConversationOut(BaseModel):
    id: str
    title: str
    timestamp: str


class ConversationsListResponse(BaseModel):
    conversations: list[ConversationOut]
    next_cursor: str | None = None


class MessagesPageResponse(BaseModel):
    messages: list[ConversationMessageOut]
    next_cursor: str | None = None


class RenameConversationRequest(BaseModel):
    title: str


class RenameConversationResponse(BaseModel):
    conversation_id: str
    title: str


class DeleteConversationResponse(BaseModel):
    conversation_id: str
