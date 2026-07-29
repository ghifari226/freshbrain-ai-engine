from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.feedback.schemas import FeedbackRequest
from app.feedback.service import FeedbackService


async def test_down_rating_requires_reason() -> None:
    service = FeedbackService(AsyncMock())
    request = FeedbackRequest(
        message_id=str(uuid4()),
        conversation_id=str(uuid4()),
        user_id=str(uuid4()),
        role="user",
        rating="down",
    )

    with pytest.raises(HTTPException) as error:
        await service.add(request)

    assert error.value.status_code == 400
