from fastapi import APIRouter

from app.core.config import get_settings
from app.core.security import encode_token
from app.dev.schemas import DevTokenRequest, DevTokenResponse

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/token", response_model=DevTokenResponse)
async def mint_token(request: DevTokenRequest) -> DevTokenResponse:
    """Stands in for chat-gateway signing a real token — deliberately
    unauthenticated (there's nothing to authenticate against yet). Delete
    this endpoint once chat-gateway is in the live path (v0.5.0 Beta, see
    freshbrain-agreement/VERSIONING.md) and mints tokens instead."""
    settings = get_settings()
    token = encode_token(request.user_id, request.role, request.allowed_scopes)
    return DevTokenResponse(access_token=token, expires_in=settings.jwt_expires_minutes * 60)
