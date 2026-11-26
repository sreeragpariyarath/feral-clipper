"""Phase 6: readable step errors, disk rules, deleting a source video, database backup, step resume."""
import json
from types import SimpleNamespace

import pytest

from backend.models import Job, JobStep, Stream
from backend.services import streams, system
from backend.services.errors import Conflict, InvalidInput, NotFound
from backend.worker import errors, runner

TRACEBACK = """=== Get the audio
Traceback (most recent call last):
  File "C:\\clipper\\backend\\pipeline\\run_step.py", line 50, in <module>
    main(int(sys.argv[1]), sys.argv[2])
  File "C:\\clipper\\backend\\pipeline\\steps\\audio.py", line 40, in audio
    raise RuntimeError("ffmpeg could not extract the audio: moov atom not found")
RuntimeError: ffmpeg could not extract the audio: moov atom not found""".splitlines()


def test_explain_picks_the_exception_and_a_hint():
    reason, hint = errors.explain(TRACEBACK, 1)
    assert reason == "RuntimeError: ffmpeg could not extract the audio: moov atom not found"
    assert "damaged" in hint


@pytest.mark.parametrize("line,word", [
    ("torch.cuda.OutOfMemoryError: CUDA out of memory. Tried to allocate 2 GiB", "GPU"),
    ("anthropic.AuthenticationError: Error code: 401 - invalid x-api-key", "key"),
    ("OSError: [Errno 28] No space left on device", "disk"),
    ("ERROR: [twitch:vod] 2934513082: HTTP Error 404: Not Found", "Twitch"),
    ("urllib.error.URLError: <urlopen error [Errno 11001] getaddrinfo failed>", "internet"),
])
def test_explain_hints(line, word):
    reason, hint = errors.explain(["something", line], 1)
    assert word.lower() in hint.lower() and reason


def test_explain_without_traceback():
    assert errors.explain([], 3)[0] == "the step stopped with exit code 3"
    assert errors.explain(["working...", "giving up after 3 tries"], 1)[0] == "giving up after 3 tries"


def test_step_refused_when_disk_is_nearly_full(session, monkeypatch, tmp_path):
    job = Job(kind="monitor", stream_id="s", log_file=str(tmp_path / "j.log"), status="running")
    session.add(job)
    session.commit()
    step = JobStep(job_id=job.id, idx=0, name="ingest", label="Download")
    session.add(step)
    session.commit()
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda p: SimpleNamespace(free=2e9, total=1e12, used=0))
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: pytest.fail("step must not start"))
    assert runner._run_step(session, job, step) == "failed"
    assert "GB free" in step.message and "Streams page" in job.error_hint


def test_health_flags_low_disk(session, monkeypatch):
    monkeypatch.setattr(system.shutil, "disk_usage", lambda p: SimpleNamespace(free=10e9, total=1e12, used=0))
    assert system.health(session).low_disk is True
    monkeypatch.setattr(system.shutil, "disk_usage", lambda p: SimpleNamespace(free=500e9, total=1e12, used=0))
    assert system.health(session).low_disk is False


def _stream(session, vod_dir, sid, file_name="vod.mp4", meta_file=None):
    folder = vod_dir / sid
    (folder / "clips" / "901").mkdir(parents=True, exist_ok=True)
    (folder / "clips" / "901" / "clip.mp4").write_bytes(b"clip")
    if file_name:
        (folder / file_name).write_bytes(b"0" * 1000)
    (folder / "session.json").write_text(json.dumps({"file": meta_file or file_name}))
    s = Stream(id=sid, video_file=file_name or "")
    session.add(s)
    session.commit()
    return s


def test_delete_video_keeps_clips(session, vod_dir):
    s = _stream(session, vod_dir, "del-ok")
    out = streams.delete_video(session, s)
    assert out.freed_gb == 0.0 and not (vod_dir / "del-ok" / "vod.mp4").exists()
    assert (vod_dir / "del-ok" / "clips" / "901" / "clip.mp4").exists()
    with pytest.raises(NotFound):
        streams.delete_video(session, s)


def test_delete_video_never_touches_a_users_own_file(session, vod_dir, tmp_path):
    own = tmp_path / "my_stream.mp4"
    own.write_bytes(b"mine")
    s = _stream(session, vod_dir, "del-local", file_name=None, meta_file=str(own))
    with pytest.raises(InvalidInput):
        streams.delete_video(session, s)
    assert own.exists()


def test_delete_video_refused_while_a_job_runs(session, vod_dir):
    s = _stream(session, vod_dir, "del-busy")
    session.add(Job(kind="render", stream_id="del-busy", status="running"))
    session.commit()
    with pytest.raises(Conflict):
        streams.delete_video(session, s)
    assert (vod_dir / "del-busy" / "vod.mp4").exists()


def test_backup_copies_the_database(session, monkeypatch, tmp_path):
    monkeypatch.setattr(system, "BACKUP_DIR", tmp_path / "backups")
    b = system.backup()
    assert (tmp_path / "backups" / b.name).stat().st_size > 0
    import sqlite3
    tables = {r[0] for r in sqlite3.connect(tmp_path / "backups" / b.name).execute("select name from sqlite_master")}
    assert {"job", "clip", "campaign", "post"} <= tables
    assert system.backups()[0].name == b.name


def test_retry_resumes_from_the_failed_step(client, session):
    r = client.post("/api/v1/jobs", json={"kind": "download", "url": "https://www.twitch.tv/videos/2934513082"})
    jid = r.json()["id"]
    job = session.get(Job, jid)
    from sqlmodel import select
    first, second = session.exec(select(JobStep).where(JobStep.job_id == jid).order_by(JobStep.idx)).all()
    first.status, second.status, second.message = "done", "failed", "RuntimeError: boom"
    job.status, job.error, job.error_hint = "failed", "RuntimeError: boom", "press Retry"
    session.add_all([first, second, job])
    session.commit()
    got = client.get(f"/api/v1/jobs/{jid}").json()
    assert got["error"] == "RuntimeError: boom" and got["error_hint"] == "press Retry"
    got = client.post(f"/api/v1/jobs/{jid}/retry").json()
    assert [s["status"] for s in got["steps"]] == ["done", "pending"] and got["error_hint"] == ""


def test_explain_uses_the_detail_under_a_multiline_error():
    lines = ["Traceback (most recent call last):", '  File "x.py", line 1, in <module>',
             "RuntimeError: Command failed: ffprobe -v error -show_entries format=duration -of ...",
             r"C:\data\broken.mp4: Invalid data found when processing input"]
    reason, hint = errors.explain(lines, 1)
    assert reason == r"RuntimeError: C:\data\broken.mp4: Invalid data found when processing input"
    assert "damaged" in hint


def test_streams_with_a_deleted_folder_are_forgotten(session, vod_dir):
    from sqlmodel import select
    from backend.importer import forget_missing
    from backend.models import Clip, Post
    session.add_all([Stream(id="gone"), Clip(stream_id="gone", clip_no="901"),
                     Stream(id="gone-posted"), Clip(stream_id="gone-posted", clip_no="902")])
    session.commit()
    posted = session.exec(select(Clip).where(Clip.stream_id == "gone-posted")).one()
    session.add(Post(clip_id=posted.id, platform="youtube"))
    session.commit()
    assert forget_missing(session) == 1
    assert session.get(Stream, "gone") is None and session.get(Stream, "gone-posted") is not None
