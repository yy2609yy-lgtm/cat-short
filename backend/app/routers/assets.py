from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.config import settings
from app.db import get_db
from app.models import Asset
from app.schemas import AssetOut, JobOut
from app.services.ingest import ingest_file
from app.services.pipeline import get_job

router = APIRouter(prefix="/api/assets", tags=["assets"], dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[AssetOut])
def list_assets(db: Session = Depends(get_db)) -> list[AssetOut]:
    return db.query(Asset).order_by(Asset.created_at.desc()).all()


@router.post("/upload", response_model=JobOut)
async def upload_local(file: UploadFile = File(...), db: Session = Depends(get_db)) -> JobOut:
    suffix = Path(file.filename or "clip.mp4").suffix.lower() or ".mp4"
    if suffix not in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}:
        raise HTTPException(400, "仅支持视频文件")
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "空文件")
    tmp = settings.work_dir / f"upload_{uuid4().hex}{suffix}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw)
    filename = Path(file.filename or tmp.name).name
    source_key = f"local:{filename}:{len(raw)}"
    _, job, _ = ingest_file(
        db,
        tmp,
        source="local",
        source_key=source_key,
        filename=filename,
        mime=file.content_type or "video/mp4",
    )
    loaded = get_job(db, job.id)
    from app.routers.jobs import _out

    return _out(loaded)
