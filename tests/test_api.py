import httpx

from app.core.security import encode_token
from app.main import app


async def test_title_endpoint_preserves_contract() -> None:
    token = encode_token("user-id", "Superuser", [])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/chat/title",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "show inbound warehouse shipments"},
        )

    assert response.status_code == 200
    assert response.json() == {"title": "Show inbound warehouse shipments"}


async def test_title_endpoint_requires_token() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/chat/title", json={"message": "hello"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
