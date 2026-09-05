"""Google Drive sync: mock (local inbox) and live OAuth."""

from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)

VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


@dataclass
class RemoteFile:
    key: str
    name: str
    mime: str
    size: int
    fetch: callable  # (dest: Path) -> Path


def _copy_local(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == src.stat().st_size:
        return dest
    dest.write_bytes(src.read_bytes())
    return dest


def list_mock_inbox() -> list[RemoteFile]:
    inbox = settings.drive_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    files: list[RemoteFile] = []
    for path in sorted(inbox.iterdir()):
        if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        mime = mimetypes.guess_type(path.name)[0] or "video/mp4"
        files.append(
            RemoteFile(
                key=f"mock:{path.name}",
                name=path.name,
                mime=mime,
                size=path.stat().st_size,
                fetch=lambda dest, src=path: _copy_local(src, dest),
            )
        )
    return files


def list_live_drive() -> list[RemoteFile]:
    if not settings.drive_folder_id:
        raise RuntimeError("DRIVE_FOLDER_ID is empty; set it for live Drive sync")
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    if not settings.google_token_file.exists():
        raise RuntimeError(
            f"Google token missing at {settings.google_token_file}. "
            "Run: python -m app.tools.oauth_drive"
        )
    creds = Credentials.from_authorized_user_file(
        str(settings.google_token_file),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    q = f"'{settings.drive_folder_id}' in parents and trashed=false"
    files: list[RemoteFile] = []
    page_token = None
    while True:
        resp = (
            service.files()
            .list(
                q=q,
                pageSize=100,
                pageToken=page_token,
                fields="nextPageToken, files(id, name, mimeType, size)",
            )
            .execute()
        )
        for item in resp.get("files", []):
            mime = item.get("mimeType") or ""
            name = item.get("name") or "video.mp4"
            if not (mime.startswith("video/") or Path(name).suffix.lower() in VIDEO_SUFFIXES):
                continue

            def _fetch(dest: Path, file_id: str = item["id"]) -> Path:
                dest.parent.mkdir(parents=True, exist_ok=True)
                request = service.files().get_media(fileId=file_id)
                with dest.open("wb") as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        _, done = downloader.next_chunk()
                return dest

            files.append(
                RemoteFile(
                    key=f"drive:{item['id']}",
                    name=name,
                    mime=mime or "video/mp4",
                    size=int(item.get("size") or 0),
                    fetch=_fetch,
                )
            )
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def list_remote() -> list[RemoteFile]:
    mode = settings.drive_mode.lower()
    if mode == "live":
        return list_live_drive()
    return list_mock_inbox()
