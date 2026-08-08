from pydantic import BaseModel


class DevTokenRequest(BaseModel):
    user_id: str
    role: str
    allowed_scopes: list[str] = []


class DevTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
