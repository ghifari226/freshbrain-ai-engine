from uuid import UUID

from sqlalchemy import case, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.worker.models import BackgroundJob


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _reclaim_stale_jobs(self) -> None:
        # A worker that dies mid-job leaves its row stuck in "processing"
        # with no lease to expire it. Anything past the lease gets
        # requeued as "pending" — unless it's already burned through its
        # attempts, in which case it's finalized as "failed" here instead
        # of being reclaimed forever.
        settings = get_settings()
        lease_cutoff = text("now() - make_interval(secs => :lease_seconds)").bindparams(
            lease_seconds=settings.worker_lease_seconds
        )
        await self.session.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.status == "processing",
                BackgroundJob.updated_at < lease_cutoff,
            )
            .values(
                status=case(
                    (BackgroundJob.attempts >= settings.worker_max_attempts, "failed"),
                    else_="pending",
                ),
                error=case(
                    (
                        BackgroundJob.attempts >= settings.worker_max_attempts,
                        "Exceeded max attempts after lease timeout",
                    ),
                    else_=BackgroundJob.error,
                ),
            )
        )

    async def enqueue(self, job_type: str, payload: dict) -> None:
        # idx_background_jobs_pending_dedup is a partial UNIQUE INDEX, not a
        # named constraint — ON CONFLICT ON CONSTRAINT only targets real
        # constraints in Postgres, so this must use index inference instead.
        stmt = (
            insert(BackgroundJob)
            .values(job_type=job_type, payload=payload)
            .on_conflict_do_nothing(
                index_elements=["job_type", text("(payload->>'conversation_id')")],
                index_where=text("status = 'pending'"),
            )
        )
        await self.session.execute(stmt)

    async def claim_next(self) -> BackgroundJob | None:
        # Claim-then-commit here, work happens outside this method, a
        # separate commit marks done/failed — never hold a transaction open
        # across the (potentially slow, externally-dependent) job work.
        await self._reclaim_stale_jobs()
        job = await self.session.scalar(
            select(BackgroundJob)
            .where(BackgroundJob.status == "pending")
            .order_by(BackgroundJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        job.status = "processing"
        job.attempts += 1
        await self.session.commit()
        return job

    async def mark_done(self, job_id: UUID) -> None:
        await self.session.execute(
            update(BackgroundJob).where(BackgroundJob.id == job_id).values(status="done")
        )
        await self.session.commit()

    async def mark_failed(self, job_id: UUID, error: str) -> None:
        # Retry while attempts remain (claim_next already incremented
        # attempts for this run); once exhausted, fail permanently instead
        # of looping forever.
        settings = get_settings()
        await self.session.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == job_id)
            .values(
                status=case(
                    (BackgroundJob.attempts >= settings.worker_max_attempts, "failed"),
                    else_="pending",
                ),
                error=error,
            )
        )
        await self.session.commit()
