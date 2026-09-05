"""YouTube upload/publish: mock (local JSON) and live OAuth."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID

from app.config import settings

log = logging.getLogger(__name__)


def upload_private_draft(
    job_id: UUID,
    video_path: Path,
    title: str,
    description: str,
) -> tuple[str, str]:
    """Upload as PRIVATE draft. Returns (video_id, mode). Idempotent caller must skip if id exists."""
    mode = settings.youtube_mode.lower()
    if mode == "live":
        video_id = _live_upload(video_path, title, description, privacy="private")
        return video_id, "live"
    return _mock_upload(job_id, video_path, title, description, privacy="private"), "mock"


def publish_public(video_id: str, mode: str | None) -> str:
    """Set visibility to public for this draft only."""
    effective = (mode or settings.youtube_mode).lower()
    if effective == "live" and not video_id.startswith("mock_"):
        _live_set_privacy(video_id, "public")
        return "public"
    record = settings.youtube_mock_dir / f"{video_id}.json"
    if record.exists():
        data = json.loads(record.read_text(encoding="utf-8"))
        data["privacy"] = "public"
        record.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return "public"


def _mock_upload(job_id: UUID, video_path: Path, title: str, description: str, privacy: str) -> str:
    settings.youtube_mock_dir.mkdir(parents=True, exist_ok=True)
    video_id = f"mock_{job_id.hex[:12]}"
    record = {
        "id": video_id,
        "title": title,
        "description": description,
        "privacy": privacy,
        "path": str(video_path),
        "size": video_path.stat().st_size if video_path.exists() else 0,
    }
    (settings.youtube_mock_dir / f"{video_id}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    log.info("YouTube mock draft stored: %s", video_id)
    return video_id


def _creds():
    from google.oauth2.credentials import Credentials

    if not settings.youtube_token_file.exists():
        raise RuntimeError(
            f"YouTube token missing at {settings.youtube_token_file}. "
            "Run: python -m app.tools.oauth_youtube"
        )
    return Credentials.from_authorized_user_file(
        str(settings.youtube_token_file),
        scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"],
    )


def _live_upload(video_path: Path, title: str, description: str, privacy: str) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    youtube = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "categoryId": settings.youtube_category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    resp = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    return resp["id"]


def _live_set_privacy(video_id: str, privacy: str) -> None:
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    youtube.videos().update(
        part="status",
        body={"id": video_id, "status": {"privacyStatus": privacy}},
    ).execute()
