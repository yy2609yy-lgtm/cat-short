from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class CropParams(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    focus_x: float = Field(default=0.5, ge=0, le=1)
    focus_y: float = Field(default=0.5, ge=0, le=1)
    zoom: float = Field(default=1.0, ge=1.0, le=3.0)


class AssetOut(BaseModel):
    id: UUID
    source: str
    source_key: str
    filename: str
    mime: str
    size_bytes: int
    duration_sec: float | None
    width: int | None
    height: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: UUID
    asset_id: UUID
    stage: str
    status: str
    crop: dict[str, Any] | None
    crop_fingerprint: str | None
    has_render: bool = False
    youtube_video_id: str | None
    youtube_privacy: str | None
    youtube_mode: str | None
    error_message: str | None
    attempt: int
    check_report: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    asset: AssetOut | None = None

    model_config = {"from_attributes": True}


class SettingsOut(BaseModel):
    drive_mode: str
    youtube_mode: str
    render_max_seconds: float
    render_width: int
    render_height: int
    render_fps: int
    admin_username: str


class SyncStatusOut(BaseModel):
    drive_mode: str
    last_sync_at: datetime | None
    last_error: str | None
    last_result: dict[str, Any] | None


class SyncResultOut(BaseModel):
    mode: str
    ingested: int
    skipped: int
    errors: list[str] = []
