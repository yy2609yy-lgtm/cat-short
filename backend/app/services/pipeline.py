"""Stage-based render/upload/publish. Retry resumes the failed stage."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import AUTO_STAGES, Job
from app.schemas import CropParams
from app.services import captions, media, youtube

log = logging.getLogger(__name__)


def claim_next_job(db: Session) -> Job | None:
    stmt = (
        select(Job.id)
        .where(Job.status == "pending", Job.stage.in_(tuple(AUTO_STAGES)))
        .order_by(Job.updated_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job_id = db.execute(stmt).scalar_one_or_none()
    if not job_id:
        return None
    job = db.get(Job, job_id)
    if not job:
        return None
    job.status = "running"
    job.attempt = (job.attempt or 0) + 1
    job.error_message = None
    db.commit()
    return (
        db.query(Job)
        .options(joinedload(Job.asset))
        .filter(Job.id == job_id)
        .one()
    )


def process_job(db: Session, job: Job) -> None:
    try:
        _advance(db, job)
        if job.stage == "DRAFT":
            job.status = "done"
        elif job.stage == "PUBLIC":
            job.status = "done"
        elif job.stage in AUTO_STAGES:
            job.status = "pending"
        else:
            job.status = "done"
        job.error_message = None
        db.commit()
    except Exception as exc:  # noqa: BLE001 — persist stage, do not reset
        log.exception("Job %s failed at %s", job.id, job.stage)
        job.status = "failed"
        job.error_message = str(exc)[:2000]
        db.commit()


def _advance(db: Session, job: Job) -> None:
    """Run the current stage once, then advance. Idempotent inside each step."""
    if job.stage in {"CROP_CONFIRMED", "RENDERING"}:
        job.stage = "RENDERING"
        db.commit()
        _render(job)
        job.stage = "RENDERED"
        db.commit()

    if job.stage in {"RENDERED", "CHECKING"}:
        job.stage = "CHECKING"
        db.commit()
        _check(job)
        job.stage = "CHECKED"
        db.commit()

    if job.stage in {"CHECKED", "UPLOADING"}:
        job.stage = "UPLOADING"
        db.commit()
        _upload(job)
        job.stage = "DRAFT"
        db.commit()

    if job.stage == "PUBLISHING":
        _publish(job)
        job.stage = "PUBLIC"
        db.commit()


def _crop(job: Job) -> CropParams:
    if not job.crop:
        raise RuntimeError("crop params missing")
    return CropParams.model_validate(job.crop)


def _render(job: Job) -> None:
    crop = _crop(job)
    fingerprint = media.crop_fingerprint(crop)
    dest = settings.renders_dir / f"{job.id}.mp4"
    srt_path = settings.renders_dir / f"{job.id}.srt"
    work = settings.work_dir / str(job.id)

    if (
        job.render_path
        and job.crop_fingerprint == fingerprint
        and Path(job.render_path).exists()
        and Path(job.render_path).stat().st_size > 0
    ):
        log.info("Skip render (idempotent) job=%s", job.id)
        return

    duration = min(max(0.2, crop.end - crop.start), settings.render_max_seconds)
    captions.write_srt(srt_path, duration)
    media.render_vertical(
        src=Path(job.asset.local_path),
        dest=dest,
        crop=crop,
        srt_path=srt_path,
        music_path=settings.music_bed_path,
        work_dir=work,
    )
    job.render_path = str(dest)
    job.srt_path = str(srt_path)
    job.crop_fingerprint = fingerprint


def _check(job: Job) -> None:
    if not job.render_path:
        raise RuntimeError("render_path missing before technical check")
    report = media.technical_check(Path(job.render_path))
    job.check_report = report
    if not report.get("ok"):
        raise RuntimeError(f"technical check failed: {report.get('errors')}")


def _upload(job: Job) -> None:
    if job.youtube_video_id:
        log.info("Skip upload (idempotent) job=%s video=%s", job.id, job.youtube_video_id)
        return
    if not job.check_report or not job.check_report.get("ok"):
        raise RuntimeError("refusing upload: technical check is not ok")
    title = f"{settings.youtube_default_title_prefix} · {job.asset.filename}"
    description = (
        "Rendered by Cat Shorts Workbench.\n"
        "Music: original CC0 bed (cozy_afternoon).\n"
        "Captions: English fallback lines (see caption contract)."
    )
    video_id, mode = youtube.upload_private_draft(
        job.id, Path(job.render_path), title, description
    )
    job.youtube_video_id = video_id
    job.youtube_privacy = "private"
    job.youtube_mode = mode


def _publish(job: Job) -> None:
    if job.youtube_privacy == "public":
        log.info("Skip publish (idempotent) job=%s", job.id)
        return
    if not job.youtube_video_id:
        raise RuntimeError("no YouTube video id to publish")
    job.youtube_privacy = youtube.publish_public(job.youtube_video_id, job.youtube_mode)


def request_retry(job: Job) -> None:
    """Resume from the current (failed) stage. Never reset to NEW."""
    if job.stage == "NEW":
        raise RuntimeError("nothing to retry before crop confirm")
    if job.stage == "PUBLIC":
        raise RuntimeError("already public")
    job.status = "pending"
    job.error_message = None
    # If we failed mid-auto-stage, stay there. If we are sitting on DRAFT, retry is a no-op.
    if job.stage == "DRAFT":
        return


def request_publish(job: Job) -> None:
    if job.stage == "PUBLIC" and job.youtube_privacy == "public":
        return
    if job.stage != "DRAFT" and not (job.stage == "PUBLISHING" and job.status == "failed"):
        raise RuntimeError(f"publish only from DRAFT, current stage={job.stage}")
    job.stage = "PUBLISHING"
    job.status = "pending"
    job.error_message = None


def get_job(db: Session, job_id: UUID) -> Job | None:
    return (
        db.query(Job)
        .options(joinedload(Job.asset))
        .filter(Job.id == job_id)
        .one_or_none()
    )
