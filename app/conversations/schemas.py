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
    # Only populated when the request used `limit`/`before` cursor
    # pagination — omitted (None) for the existing unpaginated call shape,
    # so current callers that ignore unknown fields see no behavior change.
    next_cursor: str | None = None


class MessagesPageResponse(BaseModel):
    messages: list[ConversationMessageOut]
    next_cursor: str | None = None


# user_id/role used to live on Rename/Delete requests too — removed since
# the verified JWT (see app/core/security.py) is the only source for
# identity now, and neither op ever used `role` for anything. The frontend
# still sends them in the body; FastAPI/Pydantic just ignores unrecognized
# fields, so that's harmless. Delete has no fields left at all — the router
# no longer declares a request body for it.
class RenameConversationRequest(BaseModel):
    title: str


class RenameConversationResponse(BaseModel):
    conversation_id: str
    title: str


class DeleteConversationResponse(BaseModel):
    conversation_id: str
