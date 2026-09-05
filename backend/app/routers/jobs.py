from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_admin
from app.db import get_db
from app.models import Job
from app.schemas import CropParams, JobOut
from app.services import pipeline

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(get_current_admin)])


def _out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        asset_id=job.asset_id,
        stage=job.stage,
        status=job.status,
        crop=job.crop,
        crop_fingerprint=job.crop_fingerprint,
        has_render=bool(job.render_path and Path(job.render_path).exists()),
        youtube_video_id=job.youtube_video_id,
        youtube_privacy=job.youtube_privacy,
        youtube_mode=job.youtube_mode,
        error_message=job.error_message,
        attempt=job.attempt,
        check_report=job.check_report,
        created_at=job.created_at,
        updated_at=job.updated_at,
        asset=job.asset,
    )


@router.get("", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db)) -> list[JobOut]:
    jobs = db.query(Job).options(joinedload(Job.asset)).order_by(Job.created_at.desc()).all()
    return [_out(j) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: UUID, db: Session = Depends(get_db)) -> JobOut:
    job = pipeline.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return _out(job)


@router.post("/{job_id}/confirm", response_model=JobOut)
def confirm_crop(job_id: UUID, crop: CropParams, db: Session = Depends(get_db)) -> JobOut:
    job = pipeline.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    if job.status == "running":
        raise HTTPException(409, "任务处理中，请稍后再改裁剪")
    if job.stage not in {"NEW", "CROP_CONFIRMED"}:
        raise HTTPException(409, f"当前阶段 {job.stage} 不能重新确认裁剪")
    duration = job.asset.duration_sec or crop.end
    if crop.end <= crop.start:
        raise HTTPException(400, "结束时间必须大于开始时间")
    if crop.end - crop.start > 60:
        raise HTTPException(400, "成片时长需 ≤ 60 秒")
    if crop.start >= duration:
        raise HTTPException(400, "开始时间超出素材时长")
    crop.end = min(crop.end, duration, crop.start + 59.0)
    job.crop = crop.model_dump()
    job.stage = "CROP_CONFIRMED"
    job.status = "pending"
    job.error_message = None
    # New crop invalidates previous render fingerprint; keep youtube id if already uploaded
    db.commit()
    db.refresh(job)
    return _out(job)


@router.post("/{job_id}/retry", response_model=JobOut)
def retry(job_id: UUID, db: Session = Depends(get_db)) -> JobOut:
    job = pipeline.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    try:
        pipeline.request_retry(job)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    db.refresh(job)
    return _out(job)


@router.post("/{job_id}/publish", response_model=JobOut)
def publish(job_id: UUID, db: Session = Depends(get_db)) -> JobOut:
    job = pipeline.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    try:
        pipeline.request_publish(job)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    db.refresh(job)
    return _out(job)


@router.get("/{job_id}/media/source")
def source_media(job_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    job = pipeline.get_job(db, job_id)
    if not job or not Path(job.asset.local_path).exists():
        raise HTTPException(404, "素材不存在")
    return FileResponse(job.asset.local_path, media_type="video/mp4", filename=job.asset.filename)


@router.get("/{job_id}/media/render")
def render_media(job_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    job = pipeline.get_job(db, job_id)
    if not job or not job.render_path or not Path(job.render_path).exists():
        raise HTTPException(404, "成片不存在")
    return FileResponse(job.render_path, media_type="video/mp4", filename=f"{job.id}.mp4")
