"""Backward-compatible ASGI entrypoint.

Prefer ``uvicorn app.main:app`` for new deployments.
"""

from app.main import app

__all__ = ["app"]
