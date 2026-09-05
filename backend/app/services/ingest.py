"""Idempotent asset ingest + job creation."""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Asset, Job
from app.services.media import MediaError, video_meta

log = logging.getLogger(__name__)


def checksum_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_file(
    db: Session,
    src: Path,
    *,
    source: str,
    source_key: str,
    filename: str,
    mime: str = "video/mp4",
) -> tuple[Asset, Job, bool]:
    """Create asset+job if source_key is new. Returns (asset, job, created)."""
    existing = db.query(Asset).filter(Asset.source_key == source_key).one_or_none()
    if existing:
        job = db.query(Job).filter(Job.asset_id == existing.id).order_by(Job.created_at.asc()).first()
        if job is None:
            job = Job(asset_id=existing.id, stage="NEW", status="pending")
            db.add(job)
            db.commit()
            db.refresh(job)
        return existing, job, False

    dest = settings.assets_dir / f"{uuid4().hex}_{filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)

    try:
        meta = video_meta(dest)
    except MediaError:
        meta = {"duration": None, "width": None, "height": None, "size_bytes": dest.stat().st_size}

    asset = Asset(
        source=source,
        source_key=source_key,
        filename=filename,
        local_path=str(dest),
        mime=mime,
        size_bytes=int(meta.get("size_bytes") or dest.stat().st_size),
        duration_sec=meta.get("duration"),
        width=meta.get("width"),
        height=meta.get("height"),
        checksum=checksum_file(dest),
    )
    db.add(asset)
    db.flush()
    job = Job(asset_id=asset.id, stage="NEW", status="pending")
    db.add(job)
    db.commit()
    db.refresh(asset)
    db.refresh(job)
    log.info("Ingested %s as asset %s job %s", filename, asset.id, job.id)
    return asset, job, True
