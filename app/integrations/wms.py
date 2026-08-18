import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _envelope(date: str, status: str, count: int, source: str) -> dict:
    if count == 0:
        return {"status": "NO_DATA", "data": None}
    return {
        "status": "SUCCESS",
        "data": {"date": date, "status": status, "count": count, "source": source},
    }


# Integration client menerjemahkan kontrak aplikasi ke kontrak sistem eksternal.
class WmsClient:
    async def get_inbound_count(self, date: str, status: str) -> dict:
        settings = get_settings()
        if not settings.wms_base_url or not settings.wms_api_key:
            logger.warning("WMS is not configured; returning stub inbound data")
            return _envelope(date, status, 42, "STUB — not real WMS data")

        logger.warning("WMS endpoint contract is not configured; returning UPSTREAM_ERROR")
        return {"status": "UPSTREAM_ERROR", "data": None}
