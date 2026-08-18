from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import encode_token
from app.dev.schemas import DevTokenRequest, DevTokenResponse

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/token", response_model=DevTokenResponse)
@limiter.limit(lambda: get_settings().dev_token_rate_limit)
async def mint_token(request: Request, body: DevTokenRequest) -> DevTokenResponse:
    settings = get_settings()
    token = encode_token(body.user_id, body.role, body.allowed_scopes)
    return DevTokenResponse(access_token=token, expires_in=settings.jwt_expires_minutes * 60)
