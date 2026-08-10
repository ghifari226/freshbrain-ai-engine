from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.conversations.models import Conversation, Message
from app.conversations.repository import ConversationRepository
from app.conversations.service import ConversationService, conversation_to_output, message_to_output


def test_conversation_projection_defaults_null_title_to_empty_string() -> None:
    conversation = Conversation(
        id=uuid4(),
        user_id=uuid4(),
        title=None,
        last_active_at=datetime.now(UTC),
    )

    output = conversation_to_output(conversation)

    assert output.title == ""


def test_message_to_output_hides_synthetic_tool_messages() -> None:
    messages = [
        Message(
            id=uuid4(),
            role="user",
            content="hello",
            created_at=datetime.now(UTC),
        ),
        Message(
            id=uuid4(),
            role="assistant",
            content=[{"type": "tool_use", "name": "lookup"}],
            created_at=datetime.now(UTC),
        ),
        Message(
            id=uuid4(),
            role="user",
            content=[{"type": "tool_result", "content": "{}"}],
            created_at=datetime.now(UTC),
        ),
        Message(
            id=uuid4(),
            role="assistant",
            content=[{"type": "text", "text": "hi"}],
            created_at=datetime.now(UTC),
        ),
    ]

    outputs = [message_to_output(message) for message in messages]

    assert [output.text for output in outputs if output is not None] == ["hello", "hi"]


async def test_delete_is_soft_and_hides_from_reads(db_session) -> None:
    repo = ConversationRepository(db_session)
    user_id = uuid4()
    conversation = await repo.create(user_id)
    await db_session.commit()

    deleted = await repo.delete(conversation.id, user_id)
    await db_session.commit()
    assert deleted is True

    assert await repo.get_owned(conversation.id, user_id) is None
    assert await repo.get_by_id(conversation.id) is None
    assert conversation.id not in {c.id for c in await repo.list_for_user(user_id)}

    # Row still exists in the DB, just flagged. Queried via select() rather
    # than session.get() — repo.delete()'s bulk UPDATE expires the
    # deleted_at column on the identity-mapped instance, and get() only
    # refreshes fully-expired objects, so a naive get() would return an
    # object whose attribute access lazily (and unsafely) triggers IO
    # outside the awaited call.
    raw = (
        await db_session.execute(select(Conversation).where(Conversation.id == conversation.id))
    ).scalar_one()
    assert raw.deleted_at is not None


async def test_delete_is_idempotent_once_already_deleted(db_session) -> None:
    repo = ConversationRepository(db_session)
    user_id = uuid4()
    conversation = await repo.create(user_id)
    await db_session.commit()

    assert await repo.delete(conversation.id, user_id) is True
    await db_session.commit()
    assert await repo.delete(conversation.id, user_id) is False


async def test_list_for_user_page_walks_backward_without_gaps_or_dupes(db_session) -> None:
    repo = ConversationRepository(db_session)
    user_id = uuid4()
    base = datetime.now(UTC)
    created = []
    for i in range(5):
        conversation = await repo.create(user_id)
        conversation.last_active_at = base + timedelta(seconds=i)
        created.append(conversation)
    await db_session.commit()

    # Most-recent-first — index 4 (latest last_active_at) comes back first.
    expected_order = [c.id for c in reversed(created)]

    page1, cursor1 = await repo.list_for_user_page(user_id, 2, None)
    assert [c.id for c in page1] == expected_order[:2]
    assert cursor1 == page1[-1].id

    cursor1_pos = await repo.get_conversation_cursor(cursor1, user_id)
    page2, cursor2 = await repo.list_for_user_page(user_id, 2, cursor1_pos)
    assert [c.id for c in page2] == expected_order[2:4]

    cursor2_pos = await repo.get_conversation_cursor(cursor2, user_id)
    page3, cursor3 = await repo.list_for_user_page(user_id, 2, cursor2_pos)
    assert [c.id for c in page3] == expected_order[4:5]
    assert cursor3 is None


async def test_get_conversation_cursor_is_owner_scoped(db_session) -> None:
    repo = ConversationRepository(db_session)
    owner = uuid4()
    other = uuid4()
    conversation = await repo.create(owner)
    await db_session.commit()

    assert await repo.get_conversation_cursor(conversation.id, owner) is not None
    assert await repo.get_conversation_cursor(conversation.id, other) is None


async def test_service_list_without_limit_matches_existing_shape(db_session) -> None:
    service = ConversationService(db_session)
    user_id = uuid4()
    await service.repository.create(user_id)
    await db_session.commit()

    response = await service.list(str(user_id))
    assert response.next_cursor is None
    assert len(response.conversations) == 1


async def test_service_list_rejects_invalid_cursor(db_session) -> None:
    service = ConversationService(db_session)
    user_id = uuid4()

    with pytest.raises(HTTPException) as error:
        await service.list(str(user_id), limit=10, before=str(uuid4()))
    assert error.value.status_code == 400


async def test_service_list_messages_walks_cursor(db_session) -> None:
    repo = ConversationRepository(db_session)
    service = ConversationService(db_session)
    user_id = uuid4()
    conversation = await repo.create(user_id)
    base = datetime.now(UTC)
    messages = []
    for i in range(3):
        message = Message(
            conversation_id=conversation.id,
            role="user",
            content=f"turn {i}",
            created_at=base + timedelta(seconds=i),
        )
        db_session.add(message)
        messages.append(message)
    await db_session.commit()

    expected_order = [str(m.id) for m in reversed(messages)]

    page1 = await service.list_messages(str(conversation.id), str(user_id), 2, None)
    assert [m.id for m in page1.messages] == expected_order[:2]
    assert page1.next_cursor == expected_order[1]

    page2 = await service.list_messages(str(conversation.id), str(user_id), 2, page1.next_cursor)
    assert [m.id for m in page2.messages] == expected_order[2:3]
    assert page2.next_cursor is None


async def test_service_list_messages_requires_ownership(db_session) -> None:
    repo = ConversationRepository(db_session)
    service = ConversationService(db_session)
    owner = uuid4()
    conversation = await repo.create(owner)
    await db_session.commit()

    with pytest.raises(HTTPException) as error:
        await service.list_messages(str(conversation.id), str(uuid4()), 10, None)
    assert error.value.status_code == 404
