from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import get_settings

_bearer_scheme = HTTPBearer()


class TokenClaims(BaseModel):
    """Decoded, verified identity for the current request — the
    authoritative source for user_id/role/allowed_scopes from here on.
    Request bodies still carry same-named fields (frontend isn't changing),
    but those are no longer trusted; routers overwrite them with this."""

    user_id: str
    role: str
    allowed_scopes: list[str]


def encode_token(
    user_id: str,
    role: str,
    allowed_scopes: list[str],
    expires_minutes: int | None = None,
) -> str:
    """Self-issued for now — see app/dev/router.py's POST /dev/token. Signs
    exactly the claim shape chat-gateway is expected to sign once it's in
    the live path (v0.5.0 Beta, see freshbrain-agreement/VERSIONING.md)."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "allowed_scopes": allowed_scopes,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes or settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(status_code=401, detail="Token has expired") from error
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="Invalid token") from error

    try:
        return TokenClaims(
            user_id=payload["sub"],
            role=payload["role"],
            allowed_scopes=payload["allowed_scopes"],
        )
    except KeyError as error:
        raise HTTPException(status_code=401, detail="Token missing required claims") from error


async def get_current_claims(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> TokenClaims:
    """FastAPI dependency — HTTPBearer (not a raw Header) so /docs renders a
    real Authorize padlock instead of a per-endpoint text box."""
    return decode_token(credentials.credentials)
