import asyncio
import logging

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.logging import configure_logging
from app.feedback import models as feedback_models  # noqa: F401
from app.jobs.handlers import JOB_HANDLERS
from app.jobs.repository import JobRepository

configure_logging()
logger = logging.getLogger(__name__)


async def run_once() -> bool:
    # Worker mengambil satu job, menjalankan handler, lalu mencatat hasilnya.
    async with SessionFactory() as session:
        repo = JobRepository(session)
        job = await repo.claim_next()
        if job is None:
            return False
        handler = JOB_HANDLERS.get(job.job_type)
        try:
            if handler is None:
                raise ValueError(f"No handler registered for job_type={job.job_type!r}")
            await handler(job.payload, session)
        except Exception as exc:
            logger.exception("Job %s failed", job.id)
            await repo.mark_failed(job.id, str(exc))
        else:
            await repo.mark_done(job.id)
    return True


async def main() -> None:
    settings = get_settings()
    logger.info("Worker starting, poll_interval=%s", settings.worker_poll_interval_seconds)
    while True:
        did_work = await run_once()
        if not did_work:
            await asyncio.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(main())
