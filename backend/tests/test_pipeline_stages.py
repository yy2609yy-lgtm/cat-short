from app.models import AUTO_STAGES
from app.schemas import CropParams
from app.services.media import crop_fingerprint
from app.services.pipeline import request_publish, request_retry


class FakeJob:
    def __init__(self, **kw):
        self.stage = kw.get("stage", "NEW")
        self.status = kw.get("status", "failed")
        self.error_message = "boom"
        self.youtube_privacy = kw.get("youtube_privacy")
        self.youtube_video_id = kw.get("youtube_video_id")


def test_retry_does_not_reset_to_new():
    job = FakeJob(stage="UPLOADING")
    request_retry(job)
    assert job.stage == "UPLOADING"
    assert job.status == "pending"
    assert job.error_message is None


def test_retry_from_new_rejected():
    job = FakeJob(stage="NEW")
    try:
        request_retry(job)
        assert False, "should reject"
    except RuntimeError:
        assert job.stage == "NEW"


def test_publish_only_from_draft():
    job = FakeJob(stage="DRAFT", youtube_video_id="mock_x")
    request_publish(job)
    assert job.stage == "PUBLISHING"
    assert job.status == "pending"


def test_crop_fingerprint_stable():
    a = CropParams(start=1, end=8, focus_x=0.5, focus_y=0.4, zoom=1.2)
    b = CropParams(start=1, end=8, focus_x=0.5, focus_y=0.4, zoom=1.2)
    c = CropParams(start=1, end=9, focus_x=0.5, focus_y=0.4, zoom=1.2)
    assert crop_fingerprint(a) == crop_fingerprint(b)
    assert crop_fingerprint(a) != crop_fingerprint(c)


def test_auto_stages_exclude_new_and_public():
    assert "NEW" not in AUTO_STAGES
    assert "PUBLIC" not in AUTO_STAGES
    assert "DRAFT" not in AUTO_STAGES
    assert "CROP_CONFIRMED" in AUTO_STAGES
    assert "PUBLISHING" in AUTO_STAGES
