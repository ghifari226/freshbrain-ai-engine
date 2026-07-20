import os
from datetime import date
from decimal import Decimal

import httpx

WAREHOUSE_API_BASE_URL = os.getenv("WAREHOUSE_API_BASE_URL", "http://localhost:8002")


async def get_partner_revenue(partner_ids: tuple[int, ...], date_from: date, date_to: date) -> Decimal:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{WAREHOUSE_API_BASE_URL}/revenue/partner-summary",
            params={
                "partner_ids": ",".join(str(p) for p in partner_ids),
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return Decimal(response.json()["total"])
