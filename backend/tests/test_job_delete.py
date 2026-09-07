from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_admin
from app.db import get_db
from app.main import app

from app.config import settings
from app.models import IgnoredSource
from app.services.jobs import (
    cleanup_local_paths,
    delete_job,
    forget_ignored_source,
    is_source_ignored,
    local_paths_for_job,
    remember_ignored_source,
)


class _Query:
    def __init__(self, count=0, existing=None):
        self._count = count
        self._existing = existing

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def count(self):
        return self._count

    def one_or_none(self):
        return self._existing

    def first(self):
        return None


class FakeDB:
    def __init__(self, sibling_count=0, ignored=None):
        self.sibling_count = sibling_count
        self.deleted = []
        self.added = []
        self.committed = False
        self.ignored = dict(ignored or {})

    def query(self, model):
        return _Query(count=self.sibling_count)

    def delete(self, obj):
        self.deleted.append(obj)
        if isinstance(obj, IgnoredSource):
            self.ignored.pop(obj.source_key, None)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, IgnoredSource):
            self.ignored[obj.source_key] = obj

    def get(self, model, key):
        if model is IgnoredSource:
            return self.ignored.get(key)
        return None

    def commit(self):
        self.committed = True


def _job(*, status="pending", include_files=True, tmp: Path | None = None):
    job_id = uuid4()
    asset = SimpleNamespace(
        id=uuid4(),
        source_key="drive:abc123",
        local_path=str((tmp / "assets" / "clip.mp4") if tmp else "/data/assets/clip.mp4"),
    )
    job = SimpleNamespace(
        id=job_id,
        asset_id=asset.id,
        asset=asset,
        status=status,
        render_path=str((tmp / "renders" / f"{job_id}.mp4") if tmp else None),
        srt_path=str((tmp / "renders" / f"{job_id}.srt") if tmp else None),
        youtube_video_id=f"mock_{job_id.hex[:12]}",
    )
    if include_files and tmp is not None:
        Path(job.render_path).write_bytes(b"mp4")
        Path(job.srt_path).write_bytes(b"srt")
        Path(asset.local_path).write_bytes(b"src")
        (tmp / "work" / str(job_id)).mkdir(parents=True)
        (tmp / "work" / str(job_id) / "tmp.txt").write_text("x")
        (tmp / "youtube_mock" / f"{job.youtube_video_id}.json").write_text("{}")
    return job


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    for name in ("assets", "renders", "work", "youtube_mock"):
        (tmp_path / name).mkdir()
    return tmp_path


def test_local_paths_include_render_work_and_asset(data_dir):
    job = _job(tmp=data_dir)
    paths = local_paths_for_job(job, include_asset=True)
    assert Path(job.render_path) in paths
    assert Path(job.srt_path) in paths
    assert settings.work_dir / str(job.id) in paths
    assert Path(job.asset.local_path) in paths
    assert settings.youtube_mock_dir / f"{job.youtube_video_id}.json" in paths


def test_cleanup_removes_files_and_work_dir(data_dir):
    job = _job(tmp=data_dir)
    paths = local_paths_for_job(job, include_asset=True)
    removed = cleanup_local_paths(paths)
    assert not Path(job.render_path).exists()
    assert not Path(job.srt_path).exists()
    assert not Path(job.asset.local_path).exists()
    assert not (data_dir / "work" / str(job.id)).exists()
    assert not (data_dir / "youtube_mock" / f"{job.youtube_video_id}.json").exists()
    assert len(removed) >= 4


def test_delete_running_job_rejected(data_dir):
    job = _job(status="running", tmp=data_dir)
    db = FakeDB()
    with pytest.raises(RuntimeError, match="处理中"):
        delete_job(db, job)
    assert not db.committed
    assert Path(job.render_path).exists()


def test_delete_exclusive_job_removes_asset_and_ignores_source(data_dir):
    job = _job(tmp=data_dir)
    db = FakeDB(sibling_count=0)
    result = delete_job(db, job)
    assert result["asset_removed"] is True
    assert db.committed
    assert job in db.deleted
    assert job.asset in db.deleted
    assert any(isinstance(x, IgnoredSource) and x.source_key == "drive:abc123" for x in db.added)
    assert not Path(job.render_path).exists()
    assert not Path(job.asset.local_path).exists()


def test_delete_shared_asset_keeps_asset_file(data_dir):
    job = _job(tmp=data_dir)
    db = FakeDB(sibling_count=1)
    result = delete_job(db, job)
    assert result["asset_removed"] is False
    assert job in db.deleted
    assert job.asset not in db.deleted
    assert Path(job.asset.local_path).exists()
    assert not Path(job.render_path).exists()
    assert not any(isinstance(x, IgnoredSource) for x in db.added)


def test_ingest_skips_ignored_source(tmp_path):
    from app.services.ingest import ingest_file

    src = tmp_path / "clip.mp4"
    src.write_bytes(b"not-a-real-video")
    db = FakeDB(ignored={"drive:abc123": IgnoredSource(source_key="drive:abc123")})
    asset, job, created = ingest_file(
        db, src, source="drive", source_key="drive:abc123", filename="clip.mp4"
    )
    assert asset is None
    assert job is None
    assert created is False


def test_ignore_helpers_roundtrip():
    db = FakeDB()
    assert is_source_ignored(db, "mock:sample-cat.mp4") is False
    remember_ignored_source(db, "mock:sample-cat.mp4")
    assert is_source_ignored(db, "mock:sample-cat.mp4") is True
    forget_ignored_source(db, "mock:sample-cat.mp4")
    assert is_source_ignored(db, "mock:sample-cat.mp4") is False


def test_delete_endpoint_requires_auth():
    client = TestClient(app)
    res = client.delete(f"/api/jobs/{uuid4()}")
    assert res.status_code == 401
    assert res.json()["detail"] == "未登录"


def test_delete_endpoint_204(monkeypatch, data_dir):
    from app.routers import jobs as jobs_router
    from app.services import pipeline

    job = _job(tmp=data_dir)
    monkeypatch.setattr(pipeline, "get_job", lambda db, job_id: job)
    monkeypatch.setattr(jobs_router, "delete_job", lambda db, j: {"ok": True, "asset_removed": True, "removed_files": []})
    app.dependency_overrides[get_current_admin] = lambda: "admin"
    app.dependency_overrides[get_db] = lambda: FakeDB()
    try:
        client = TestClient(app)
        res = client.delete(f"/api/jobs/{job.id}")
        assert res.status_code == 204
    finally:
        app.dependency_overrides.clear()


def test_delete_endpoint_404(monkeypatch):
    from app.services import pipeline

    monkeypatch.setattr(pipeline, "get_job", lambda db, job_id: None)
    app.dependency_overrides[get_current_admin] = lambda: "admin"
    app.dependency_overrides[get_db] = lambda: FakeDB()
    try:
        client = TestClient(app)
        res = client.delete(f"/api/jobs/{uuid4()}")
        assert res.status_code == 404
        assert res.json()["detail"] == "任务不存在"
    finally:
        app.dependency_overrides.clear()
