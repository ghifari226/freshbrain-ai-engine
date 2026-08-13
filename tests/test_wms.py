import pytest

from app.core.config import get_settings
from app.integrations.wms import WmsClient, _envelope


def test_envelope_positive_count_is_success() -> None:
    result = _envelope("2026-08-13", "pending", 5, "real WMS")
    assert result == {
        "status": "SUCCESS",
        "data": {"date": "2026-08-13", "status": "pending", "count": 5, "source": "real WMS"},
    }


def test_envelope_zero_count_is_no_data() -> None:
    result = _envelope("2026-08-13", "pending", 0, "real WMS")
    assert result == {"status": "NO_DATA", "data": None}


async def test_unconfigured_wms_returns_stub_wrapped_in_success() -> None:
    result = await WmsClient().get_inbound_count("2026-08-13", "pending")
    assert result["status"] == "SUCCESS"
    assert result["data"]["count"] == 42
    assert result["data"]["source"] == "STUB — not real WMS data"


async def test_configured_but_unimplemented_wms_returns_upstream_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "wms_base_url", "http://wms.example.test")
    monkeypatch.setattr(settings, "wms_api_key", "test-key")

    result = await WmsClient().get_inbound_count("2026-08-13", "pending")

    assert result == {"status": "UPSTREAM_ERROR", "data": None}
