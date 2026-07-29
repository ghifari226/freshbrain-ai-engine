from datetime import date
from decimal import Decimal

import httpx

from app.core.config import get_settings


class WarehouseClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or get_settings().warehouse_api_base_url

    async def get_partner_revenue(
        self,
        partner_ids: tuple[int, ...],
        date_from: date,
        date_to: date,
    ) -> Decimal:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.get(
                "/revenue/partner-summary",
                params={
                    "partner_ids": ",".join(map(str, partner_ids)),
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                },
                timeout=10.0,
            )
            response.raise_for_status()
            return Decimal(response.json()["total"])
