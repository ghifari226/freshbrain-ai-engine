"""
get_inbound_count — WMS-backed tool function.

##############################################################################
# STUB — THIS RETURNS FAKE DATA, NOT REAL WMS DATA.
#
# We don't have real WMS endpoint/auth details yet. This stub lets the
# Claude tool-use loop be tested end-to-end. Swap in the real HTTP call
# (sketched below) once WMS_BASE_URL / WMS_API_KEY are available, then
# delete this comment block.
##############################################################################
"""

import logging
import os

logger = logging.getLogger(__name__)

WMS_BASE_URL = os.getenv("WMS_BASE_URL")
WMS_API_KEY = os.getenv("WMS_API_KEY")


async def get_inbound_count(date: str, status: str) -> dict:
    """Get the count of inbound shipments for a date and status.

    STUB: returns fake data — see module docstring.
    """
    logger.warning(
        "STUB get_inbound_count(date=%s, status=%s) called — returning FAKE data, "
        "not real WMS data. Swap in the real WMS call in tools/functions/inbound.py.",
        date,
        status,
    )
    return {
        "date": date,
        "status": status,
        "count": 42,
        "source": "STUB — not real WMS data",
    }

    # --- Real implementation, once WMS endpoint/auth details are known ---
    # import httpx
    #
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(
    #         f"{WMS_BASE_URL}/inbound/count",
    #         params={"date": date, "status": status},
    #         headers={"Authorization": f"Bearer {WMS_API_KEY}"},
    #         timeout=10.0,
    #     )
    #     response.raise_for_status()
    #     return response.json()
