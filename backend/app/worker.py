"""Worker process: claim and advance pipeline jobs."""

from __future__ import annotations

import logging
import time

from app.config import settings
from app.db import SessionLocal
from app.services.pipeline import claim_next_job, process_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("worker")


def main() -> None:
    settings.ensure_dirs()
    log.info("worker started, poll=%ss", settings.worker_poll_seconds)
    while True:
        db = SessionLocal()
        try:
            job = claim_next_job(db)
            if job:
                log.info("processing job=%s stage=%s attempt=%s", job.id, job.stage, job.attempt)
                process_job(db, job)
            else:
                time.sleep(settings.worker_poll_seconds)
        except Exception:
            log.exception("worker loop error")
            time.sleep(settings.worker_poll_seconds)
        finally:
            db.close()


if __name__ == "__main__":
    main()
