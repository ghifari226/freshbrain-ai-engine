from app.core.logging import _redact_secret_fields


def test_redacts_secret_like_keys() -> None:
    event_dict = {
        "event": "login_attempt",
        "password": "hunter2",
        "api_key": "sk-live-abc123",
        "Authorization": "Bearer xyz",
        "user_token": "abc",
        "user_id": "42",
    }

    result = _redact_secret_fields(None, "info", event_dict)

    assert result["password"] == "***REDACTED***"
    assert result["api_key"] == "***REDACTED***"
    assert result["Authorization"] == "***REDACTED***"
    assert result["user_token"] == "***REDACTED***"
    assert result["user_id"] == "42"
    assert result["event"] == "login_attempt"
