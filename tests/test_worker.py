from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import engine
from app.worker.models import BackgroundJob
from app.worker.repository import JobRepository


async def test_enqueue_dedupes_pending_jobs(db_session) -> None:
    repo = JobRepository(db_session)
    await repo.enqueue("summarize_conversation", {"conversation_id": "dedup-test-convo"})
    await repo.enqueue("summarize_conversation", {"conversation_id": "dedup-test-convo"})
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(BackgroundJob).where(BackgroundJob.job_type == "summarize_conversation")
            )
        )
        .scalars()
        .all()
    )
    matching = [r for r in rows if r.payload.get("conversation_id") == "dedup-test-convo"]
    assert len(matching) == 1


async def test_enqueue_allows_new_pending_once_processing(db_session) -> None:
    repo = JobRepository(db_session)
    await repo.enqueue("summarize_conversation", {"conversation_id": "reenqueue-test-convo"})
    await db_session.commit()

    claimed = await repo.claim_next()
    assert claimed is not None
    assert claimed.status == "processing"

    # A job for the same conversation is now allowed again since the
    # dedup index only applies to status='pending'.
    await repo.enqueue("summarize_conversation", {"conversation_id": "reenqueue-test-convo"})
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(BackgroundJob).where(BackgroundJob.job_type == "summarize_conversation")
            )
        )
        .scalars()
        .all()
    )
    matching = [r for r in rows if r.payload.get("conversation_id") == "reenqueue-test-convo"]
    assert len(matching) == 2
    assert {r.status for r in matching} == {"processing", "pending"}


async def test_skip_locked_prevents_concurrent_double_claim() -> None:
    # This needs two genuinely independent transactions to prove SKIP LOCKED
    # actually skips a row still locked by another, uncommitted transaction —
    # the shared savepoint-wrapped db_session fixture is single-connection
    # by design and can't demonstrate that. Two pending jobs are inserted so
    # a real assertion is possible: conn_b must skip the row conn_a is
    # holding (without blocking) and claim the *other* one instead — if
    # SKIP LOCKED weren't working, conn_b would either block indefinitely
    # or double-claim conn_a's row.
    async with engine.connect() as setup_conn:
        await setup_conn.execute(
            BackgroundJob.__table__.insert().values(
                job_type="skip_locked_test", payload={"marker": "first"}
            )
        )
        await setup_conn.execute(
            BackgroundJob.__table__.insert().values(
                job_type="skip_locked_test", payload={"marker": "second"}
            )
        )
        await setup_conn.commit()

    try:
        async with engine.connect() as conn_a, engine.connect() as conn_b:
            await conn_a.begin()
            await conn_b.begin()
            session_a: AsyncSession = async_sessionmaker(
                bind=conn_a, join_transaction_mode="create_savepoint", expire_on_commit=False
            )()
            session_b: AsyncSession = async_sessionmaker(
                bind=conn_b, join_transaction_mode="create_savepoint", expire_on_commit=False
            )()
            repo_a = JobRepository(session_a)
            repo_b = JobRepository(session_b)

            job_a = await repo_a.claim_next()
            assert job_a is not None
            assert job_a.job_type == "skip_locked_test"

            # conn_a's real transaction is still open (claim_next only
            # released a SAVEPOINT) — its row lock is still held, so conn_b
            # must skip it (not block, not double-claim) and get the other row.
            job_b = await repo_b.claim_next()
            assert job_b is not None
            assert job_b.id != job_a.id

            await conn_a.commit()
            await conn_b.commit()
    finally:
        async with engine.connect() as cleanup_conn:
            await cleanup_conn.execute(
                delete(BackgroundJob).where(BackgroundJob.job_type == "skip_locked_test")
            )
            await cleanup_conn.commit()
