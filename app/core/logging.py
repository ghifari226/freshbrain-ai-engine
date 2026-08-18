import logging
from typing import Any

import structlog

_SECRET_KEY_MARKERS = (
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "credential",
)
_REDACTED = "***REDACTED***"


def _redact_secret_fields(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    for key in event_dict:
        if any(marker in key.lower() for marker in _SECRET_KEY_MARKERS):
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging() -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_secret_fields,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)
