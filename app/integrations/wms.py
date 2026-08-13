import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _envelope(date: str, status: str, count: int, source: str) -> dict:
    # A genuine zero (valid, authorized query that found nothing) is
    # meaningfully different from a real positive count — callers need to
    # tell "checked, found none" apart from "here's the data" without
    # inspecting the count themselves.
    if count == 0:
        return {"status": "NO_DATA", "data": None}
    return {
        "status": "SUCCESS",
        "data": {"date": date, "status": status, "count": count, "source": source},
    }


class WmsClient:
    async def get_inbound_count(self, date: str, status: str) -> dict:
        settings = get_settings()
        if not settings.wms_base_url or not settings.wms_api_key:
            logger.warning("WMS is not configured; returning stub inbound data")
            return _envelope(date, status, 42, "STUB — not real WMS data")

        # The real endpoint contract has not been supplied yet. Returning
        # UPSTREAM_ERROR (rather than raising) keeps this from crashing the
        # chat loop and lets Claude tell the user the data isn't available
        # right now, instead of presenting a guess as a real answer.
        logger.warning("WMS endpoint contract is not configured; returning UPSTREAM_ERROR")
        return {"status": "UPSTREAM_ERROR", "data": None}
