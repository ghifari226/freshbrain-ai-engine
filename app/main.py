from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.chat.router import router as chat_router
from app.conversations.router import router as conversations_router
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.core.request_logging import RequestLoggingMiddleware
from app.dev.router import router as dev_router
from app.feedback.router import router as feedback_router
from app.tool_requests.router import router as tool_requests_router
from app.tools.router import router as tools_router

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # Middleware order matters: Starlette applies last-added = outermost, so
    # CORS is registered last to stay outermost (wraps rate limiting/logging).
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)
    app.include_router(feedback_router)
    app.include_router(conversations_router)
    app.include_router(dev_router)
    app.include_router(tools_router)
    app.include_router(tool_requests_router)
    return app


app = create_app()
