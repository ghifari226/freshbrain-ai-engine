"""Stand-in for chat-gateway's real signature verification (auth-contract.md).
Delete this once chat-gateway exists and signs real tokens — ai-engine should
only ever verify a signature here, never issue or validate credentials itself."""
from fastapi import HTTPException


def verify_mock_token(authorization: str | None, user_id: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    if not user_id or token != f"mock:{user_id}":
        raise HTTPException(status_code=401, detail="Token does not match user_id")


def verify_mock_token_unscoped(authorization: str | None) -> None:
    """Same stand-in as verify_mock_token, for the one endpoint (POST
    /chat/title) whose contract has no user_id field to match against —
    titling isn't RBAC/scope-gated, so this only checks token shape, not
    which user it belongs to."""
    if not authorization or not authorization.startswith("Bearer mock:"):
        raise HTTPException(status_code=401, detail="Missing bearer token")
