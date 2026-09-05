"""initial tables

Revision ID: 001_initial
Revises:
Create Date: 2026-09-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_key", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=False),
        sa.Column("mime", sa.String(128), nullable=False, server_default="video/mp4"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_assets_source_key", "assets", ["source_key"])

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False, server_default="NEW"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("crop", postgresql.JSONB(), nullable=True),
        sa.Column("crop_fingerprint", sa.String(64), nullable=True),
        sa.Column("render_path", sa.Text(), nullable=True),
        sa.Column("srt_path", sa.Text(), nullable=True),
        sa.Column("check_report", postgresql.JSONB(), nullable=True),
        sa.Column("youtube_video_id", sa.String(128), nullable=True),
        sa.Column("youtube_privacy", sa.String(32), nullable=True),
        sa.Column("youtube_mode", sa.String(16), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_stage_status", "jobs", ["stage", "status"])

    op.create_table(
        "sync_state",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cursor", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_result", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sync_state")
    op.drop_index("ix_jobs_stage_status", table_name="jobs")
    op.drop_table("jobs")
    op.drop_constraint("uq_assets_source_key", "assets", type_="unique")
    op.drop_table("assets")
