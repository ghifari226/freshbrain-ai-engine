from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import get_settings

_bearer_scheme = HTTPBearer()


# Claims adalah identitas yang sudah diverifikasi, bukan data yang dipercaya dari body request.
class TokenClaims(BaseModel):
    user_id: str
    role: str
    allowed_scopes: list[str]


def encode_token(
    user_id: str,
    role: str,
    allowed_scopes: list[str],
    expires_minutes: int | None = None,
) -> str:
    # JWT ditandatangani agar isi token tidak dapat diubah tanpa diketahui server.
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
    # FastAPI menjalankan dependency autentikasi ini sebelum handler endpoint.
    return decode_token(credentials.credentials)
