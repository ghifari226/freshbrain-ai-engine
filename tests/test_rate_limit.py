import httpx
from limits.storage import MemoryStorage

from app.core.rate_limit import limiter as rate_limiter
from app.main import app


async def test_dev_token_rate_limited() -> None:
    # @limiter.limit(...) on the route binds directly to this specific
    # Limiter instance at decoration time — NOT to request.app.state.limiter
    # dynamically (that's only read by SlowAPIMiddleware/the exception
    # handler for header injection). So the only way to redirect enforcement
    # for a test is to swap this instance's storage/strategy in place,
    # rather than replacing app.state.limiter (which does nothing here).
    # Avoids polluting the module-level limiter's shared in-memory counter
    # across test runs. Restored afterward.
    original_storage = rate_limiter._storage
    original_strategy = rate_limiter._limiter
    memory_storage = MemoryStorage()
    rate_limiter._storage = memory_storage
    rate_limiter._limiter = type(original_strategy)(memory_storage)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {"user_id": "u", "role": "Superuser", "allowed_scopes": []}
            responses = [await client.post("/dev/token", json=payload) for _ in range(5)]
            limited = await client.post("/dev/token", json=payload)
    finally:
        rate_limiter._storage = original_storage
        rate_limiter._limiter = original_strategy

    assert all(r.status_code == 200 for r in responses)
    assert limited.status_code == 429
    assert "Rate limit exceeded" in limited.json()["error"]
