import pytest
from fastapi import HTTPException

from app.core.security import authenticated_user_id


def test_mock_token_must_match_user() -> None:
    assert authenticated_user_id("user-1", "Bearer mock:user-1") == "user-1"

    with pytest.raises(HTTPException) as error:
        authenticated_user_id("user-1", "Bearer mock:user-2")

    assert error.value.status_code == 401
