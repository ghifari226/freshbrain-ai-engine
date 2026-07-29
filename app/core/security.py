from fastapi import Header, HTTPException


def authenticated_user_id(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> str:
    """Temporary mock-token validation until the gateway signs real tokens."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if authorization.removeprefix("Bearer ") != f"mock:{user_id}":
        raise HTTPException(status_code=401, detail="Token does not match user_id")
    return user_id


def verify_unscoped_token(
    authorization: str | None = Header(default=None),
) -> None:
    if not authorization or not authorization.startswith("Bearer mock:"):
        raise HTTPException(status_code=401, detail="Missing bearer token")
