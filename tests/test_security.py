from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.security import decode_token, encode_token


def test_encode_decode_roundtrip() -> None:
    token = encode_token("user-1", "Superuser", ["wms.inbound"])
    claims = decode_token(token)

    assert claims.user_id == "user-1"
    assert claims.role == "Superuser"
    assert claims.allowed_scopes == ["wms.inbound"]


def test_decode_rejects_bad_signature() -> None:
    token = encode_token("user-1", "Superuser", [])
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    with pytest.raises(HTTPException) as error:
        decode_token(tampered)

    assert error.value.status_code == 401


def test_decode_rejects_expired_token() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "role": "Superuser",
        "allowed_scopes": [],
        "iat": now - timedelta(minutes=30),
        "exp": now - timedelta(minutes=1),
    }
    expired = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(HTTPException) as error:
        decode_token(expired)

    assert error.value.status_code == 401


def test_decode_rejects_missing_claims() -> None:
    settings = get_settings()
    incomplete = jwt.encode(
        {"sub": "user-1"}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )

    with pytest.raises(HTTPException) as error:
        decode_token(incomplete)

    assert error.value.status_code == 401
