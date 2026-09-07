"""Job deletion: Postgres rows + local copies. Drive originals are never touched."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Asset, IgnoredSource, Job

log = logging.getLogger(__name__)


def local_paths_for_job(job: Job, *, include_asset: bool) -> list[Path]:
    """Known local artifacts for a job. Missing paths are fine; cleanup skips them."""
    paths: list[Path] = []
    if job.render_path:
        paths.append(Path(job.render_path))
    if job.srt_path:
        paths.append(Path(job.srt_path))
    paths.append(settings.renders_dir / f"{job.id}.mp4")
    paths.append(settings.renders_dir / f"{job.id}.srt")
    paths.append(settings.work_dir / str(job.id))
    if job.youtube_video_id:
        paths.append(settings.youtube_mock_dir / f"{job.youtube_video_id}.json")
    if include_asset and job.asset is not None and job.asset.local_path:
        paths.append(Path(job.asset.local_path))
    return paths


def cleanup_local_paths(paths: list[Path]) -> list[str]:
    removed: list[str] = []
    seen: set[Path] = set()
    for path in paths:
        try:
            resolved = path if not path.exists() else path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            if path.is_file():
                path.unlink()
                removed.append(str(path))
            elif path.is_dir():
                shutil.rmtree(path)
                removed.append(str(path))
        except OSError as exc:
            log.warning("Failed to remove %s: %s", path, exc)
    return removed


def remember_ignored_source(db: Session, source_key: str) -> None:
    if not source_key:
        return
    if db.get(IgnoredSource, source_key) is None:
        db.add(IgnoredSource(source_key=source_key))


def forget_ignored_source(db: Session, source_key: str) -> None:
    row = db.get(IgnoredSource, source_key)
    if row is not None:
        db.delete(row)


def is_source_ignored(db: Session, source_key: str) -> bool:
    return db.get(IgnoredSource, source_key) is not None


def delete_job(db: Session, job: Job) -> dict:
    """Remove the job. If its asset has no other jobs, remove that asset too.

    Records the asset source_key so Drive/inbox sync will not immediately
    recreate the same item. Does not delete anything from Google Drive.
    """
    if job.status == "running":
        raise RuntimeError("任务处理中，请稍后再删")

    siblings = (
        db.query(Job)
        .filter(Job.asset_id == job.asset_id, Job.id != job.id)
        .count()
    )
    exclusive = siblings == 0
    paths = local_paths_for_job(job, include_asset=exclusive)
    asset: Asset | None = job.asset if exclusive else None
    source_key = asset.source_key if asset is not None else None

    db.delete(job)
    if exclusive and asset is not None:
        remember_ignored_source(db, asset.source_key)
        db.delete(asset)
    db.commit()
    removed = cleanup_local_paths(paths)
    log.info(
        "Deleted job; asset_removed=%s source_key=%s files=%s",
        exclusive,
        source_key,
        removed,
    )
    return {"ok": True, "asset_removed": exclusive, "removed_files": removed}
