"""Drive sync orchestration (idempotent on source_key)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import SyncState
from app.services.drive import list_remote
from app.services.ingest import ingest_file
from app.services.media import MediaError

log = logging.getLogger(__name__)


def run_sync(db: Session) -> dict:
    ingested = 0
    skipped = 0
    errors: list[str] = []
    mode = settings.drive_mode.lower()
    try:
        remotes = list_remote()
    except Exception as exc:  # noqa: BLE001
        _save_state(db, error=str(exc), result={"ingested": 0, "skipped": 0})
        raise

    for remote in remotes:
        dest = settings.work_dir / "sync" / remote.name
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            remote.fetch(dest)
            _, _, created = ingest_file(
                db,
                dest,
                source="drive" if mode == "live" else "local",
                source_key=remote.key,
                filename=remote.name,
                mime=remote.mime,
            )
            if created:
                ingested += 1
            else:
                skipped += 1
        except MediaError as exc:
            errors.append(f"{remote.name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            log.exception("sync failed for %s", remote.name)
            errors.append(f"{remote.name}: {exc}")

    result = {"ingested": ingested, "skipped": skipped, "errors": errors, "seen": len(remotes)}
    _save_state(db, error="; ".join(errors) if errors else None, result=result)
    return {"mode": mode, **result}


def _save_state(db: Session, error: str | None, result: dict) -> None:
    state = db.get(SyncState, "drive")
    if state is None:
        state = SyncState(id="drive")
        db.add(state)
    state.last_sync_at = datetime.now(timezone.utc)
    state.last_error = error
    state.last_result = result
    db.commit()
