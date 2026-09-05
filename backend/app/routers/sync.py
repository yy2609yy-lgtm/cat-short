from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.config import settings
from app.db import get_db
from app.models import SyncState
from app.schemas import SettingsOut, SyncResultOut, SyncStatusOut
from app.services.sync import run_sync

router = APIRouter(prefix="/api", tags=["sync"], dependencies=[Depends(get_current_admin)])


@router.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return SettingsOut(
        drive_mode=settings.drive_mode,
        youtube_mode=settings.youtube_mode,
        render_max_seconds=settings.render_max_seconds,
        render_width=settings.render_width,
        render_height=settings.render_height,
        render_fps=settings.render_fps,
        admin_username=settings.admin_username,
    )


@router.get("/sync/status", response_model=SyncStatusOut)
def sync_status(db: Session = Depends(get_db)) -> SyncStatusOut:
    state = db.get(SyncState, "drive")
    return SyncStatusOut(
        drive_mode=settings.drive_mode,
        last_sync_at=state.last_sync_at if state else None,
        last_error=state.last_error if state else None,
        last_result=state.last_result if state else None,
    )


@router.post("/sync/drive", response_model=SyncResultOut)
def sync_now(db: Session = Depends(get_db)) -> SyncResultOut:
    result = run_sync(db)
    return SyncResultOut(**result)
