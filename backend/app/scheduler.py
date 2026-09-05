"""Scheduler process: periodic Drive sync."""

from __future__ import annotations

import logging
import time

from app.config import settings
from app.db import SessionLocal
from app.services.sync import run_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("scheduler")


def main() -> None:
    settings.ensure_dirs()
    log.info(
        "scheduler started, tick=%ss drive_interval=%ss mode=%s",
        settings.scheduler_tick_seconds,
        settings.drive_sync_interval_seconds,
        settings.drive_mode,
    )
    next_sync = time.time() + 3
    while True:
        now = time.time()
        if now >= next_sync:
            db = SessionLocal()
            try:
                result = run_sync(db)
                log.info("sync result: %s", result)
            except Exception:
                log.exception("scheduled sync failed")
            finally:
                db.close()
            next_sync = now + settings.drive_sync_interval_seconds
        time.sleep(settings.scheduler_tick_seconds)


if __name__ == "__main__":
    main()
