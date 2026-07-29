import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class WmsClient:
    async def get_inbound_count(self, date: str, status: str) -> dict:
        settings = get_settings()
        if not settings.wms_base_url or not settings.wms_api_key:
            logger.warning("WMS is not configured; returning stub inbound data")
            return {
                "date": date,
                "status": status,
                "count": 42,
                "source": "STUB — not real WMS data",
            }

        # The real endpoint contract has not been supplied yet. Keeping this
        # explicit prevents accidentally presenting guessed integration data.
        raise NotImplementedError("WMS endpoint contract is not configured")
