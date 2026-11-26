"""Service layer: jobs, clips and their errors, without HTTP."""
import pytest
from pydantic import ValidationError

from backend.models import Clip
from backend.pipeline.registry import ORDER, label_of, load
from backend.schemas import ClipPatch, JobCreate
from backend.services import clips, jobs
from backend.services.errors import Conflict, InvalidInput, NotFound

VOD = "https://www.twitch.tv/videos/2934513082"


def test_registry_loads_every_step():
    assert len(ORDER) == 12 and ORDER[0] == "ingest" and ORDER[-1] == "ready"
    for name in ORDER:
        assert callable(load(name)) and label_of(name)


def test_stream_id_for_url():
    assert jobs.stream_id_for_url(VOD) == "twitchvod-v2934513082"
    with pytest.raises(InvalidInput):
        jobs.stream_id_for_url("https://youtube.com/watch?v=x")


def test_job_needs_exactly_one_source():
    with pytest.raises(ValidationError):
        JobCreate(kind="monitor")
    with pytest.raises(ValidationError):
        JobCreate(kind="monitor", url=VOD, path="C:/x.mp4")


@pytest.mark.parametrize("kind,steps", [("download", 2), ("monitor", 8), ("render", 12)])
def test_create_job_writes_steps_in_one_go(session, kind, steps):
    job = jobs.create(session, JobCreate(kind=kind, url=VOD), has_key=True)
    assert job.status == "queued"
    assert [s.name for s in jobs.steps_of(session, job.id)] == ORDER[:steps]


def test_render_needs_key(session):
    with pytest.raises(InvalidInput):
        jobs.create(session, JobCreate(kind="render", url=VOD), has_key=False)


def test_local_file_must_be_video(session, tmp_path):
    txt = tmp_path / "notes.txt"
    txt.write_text("x")
    with pytest.raises(InvalidInput):
        jobs.create(session, JobCreate(kind="monitor", path=str(txt)), has_key=False)
    with pytest.raises(InvalidInput):
        jobs.create(session, JobCreate(kind="monitor", path=str(tmp_path / "missing.mp4")), has_key=False)
    mp4 = tmp_path / "My Clip.mp4"
    mp4.write_bytes(b"0")
    job = jobs.create(session, JobCreate(kind="monitor", path=str(mp4)), has_key=False)
    assert job.stream_id.startswith("local-my-clip-") and job.params["source_path"]


def test_cancel_queued_and_retry(session):
    job = jobs.create(session, JobCreate(kind="monitor", url=VOD), has_key=False)
    with pytest.raises(Conflict):
        jobs.retry(session, job)
    job = jobs.cancel(session, job)
    assert job.status == "cancelled"
    assert {s.status for s in jobs.steps_of(session, job.id)} == {"cancelled"}
    job = jobs.retry(session, job)
    assert job.status == "queued"
    assert {s.status for s in jobs.steps_of(session, job.id)} == {"pending"}


def test_get_missing_raises(session):
    with pytest.raises(NotFound):
        jobs.get(session, 999)
    with pytest.raises(NotFound):
        clips.get(session, 999)


def _clip(session, vod_dir, no="901"):
    folder = vod_dir / "s1" / "clips" / no
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "clip.mp4").write_bytes(b"0")
    c = Clip(stream_id="s1", clip_no=no, status="ready", final_score=0.7, has_video=True)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def test_review_writes_review_json(session, vod_dir):
    c = clips.review(session, _clip(session, vod_dir), ClipPatch(decision="approved", title="Hi"))
    assert c.decision == "approved"
    assert (vod_dir / "s1" / "clips" / "901" / "review.json").exists()


def test_trash_and_restore_move_the_folder(session, vod_dir):
    c = _clip(session, vod_dir, "902")
    c = clips.trash(session, c)
    assert c.deleted and (vod_dir / "s1" / "clips_trash" / "902").is_dir()
    assert clips.to_out(c).video_url is None
    c = clips.restore(session, c)
    assert not c.deleted and (vod_dir / "s1" / "clips" / "902" / "clip.mp4").exists()
