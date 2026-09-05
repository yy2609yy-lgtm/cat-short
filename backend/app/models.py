import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Pipeline stages. Failures stay on the attempted stage; retry does not reset to NEW.
STAGES = (
    "NEW",
    "CROP_CONFIRMED",
    "RENDERING",
    "RENDERED",
    "CHECKING",
    "CHECKED",
    "UPLOADING",
    "DRAFT",
    "PUBLISHING",
    "PUBLIC",
)

AUTO_STAGES = {
    "CROP_CONFIRMED",
    "RENDERING",
    "RENDERED",
    "CHECKING",
    "CHECKED",
    "UPLOADING",
    "PUBLISHING",
}


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("source_key", name="uq_assets_source_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # drive | local | sample
    source_key: Mapped[str] = mapped_column(String(512), nullable=False)  # drive file id or local checksum path
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(String(128), default="video/mp4")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[list["Job"]] = relationship(back_populates="asset")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending|running|failed|done
    crop: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    crop_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    render_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    srt_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    youtube_video_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    youtube_privacy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    youtube_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    asset: Mapped[Asset] = relationship(back_populates="jobs")


class SyncState(Base):
    __tablename__ = "sync_state"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # "drive"
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
