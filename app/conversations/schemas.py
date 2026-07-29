from pydantic import BaseModel


class ConversationMessageOut(BaseModel):
    id: str
    role: str
    text: str
    createdAt: str


class ConversationOut(BaseModel):
    id: str
    title: str
    timestamp: str
    messages: list[ConversationMessageOut]


class ConversationsListResponse(BaseModel):
    conversations: list[ConversationOut]


class RenameConversationRequest(BaseModel):
    title: str
    user_id: str
    role: str


class RenameConversationResponse(BaseModel):
    conversation_id: str
    title: str


class DeleteConversationRequest(BaseModel):
    user_id: str
    role: str


class DeleteConversationResponse(BaseModel):
    conversation_id: str
