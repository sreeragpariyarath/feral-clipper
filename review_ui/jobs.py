"""Background jobs for the review UI: download a Twitch VOD, run the monitor, and optionally render.

Each job runs the existing scripts in order, one job at a time, and writes its log to
data\\jobs\\<id>.log. The Anthropic key is read from .env (or the environment) and is never sent
to the browser or written into logs.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "data" / "jobs"
MODES = ("download", "monitor", "render")
TWITCH_VOD = re.compile(r"^https?://(?:www\.)?twitch\.tv/videos/(\d{6,})")

_lock = threading.Lock()
_current = {"id": None}


def load_env():
    """Read .env into os.environ for keys that are not already set. Values are never printed."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def has_key():
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_status(job_id, data):
    (JOBS_DIR / f"{job_id}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _run_step(log, label, args):
    log.write(f"\n=== {label}\n$ python {' '.join(args)}\n")
    log.flush()
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                          stdin=subprocess.DEVNULL)
    return proc.returncode


def _worker(job_id, url, mode, top, session_id):
    log_path = JOBS_DIR / f"{job_id}.log"
    status = _read(JOBS_DIR / f"{job_id}.json", {})
    try:
        with open(log_path, "a", encoding="utf-8", errors="replace") as log:
            steps = [("Download video and audio", ["vod.py", url, "--download-only", "--audio"])]
            if mode in ("monitor", "render"):
                steps.append(("Find moments (monitor)", ["monitor.py", str(ROOT / "data" / "vod" / session_id),
                                                         "--top", str(top)]))
            if mode == "render":
                steps[-1][1].append("--render")
            for label, args in steps:
                status["step"] = label
                _write_status(job_id, status)
                code = _run_step(log, label, args)
                if code != 0:
                    status.update(state="failed", step=label, finished=datetime.now().isoformat(timespec="seconds"))
                    _write_status(job_id, status)
                    log.write(f"\nFAILED at {label} (exit {code})\n")
                    return
            status.update(state="done", step="finished", finished=datetime.now().isoformat(timespec="seconds"))
            _write_status(job_id, status)
            log.write("\nDONE\n")
    except Exception as exc:  # keep the server alive whatever happens in a job
        status.update(state="failed", error=str(exc), finished=datetime.now().isoformat(timespec="seconds"))
        _write_status(job_id, status)
    finally:
        _lock.release()
        _current["id"] = None


def start_job(body):
    """Validate the request, then start the job in a background thread. Returns (http_status, payload)."""
    url = str(body.get("url", "")).strip()
    mode = str(body.get("mode", "monitor")).strip()
    try:
        top = int(body.get("top", 10))
    except (TypeError, ValueError):
        return 400, {"error": "top must be a number"}
    if mode not in MODES:
        return 400, {"error": "mode must be download, monitor or render"}
    m = TWITCH_VOD.match(url)
    if not m:
        return 400, {"error": "paste a Twitch VOD link like https://www.twitch.tv/videos/1234567890"}
    if not 1 <= top <= 30:
        return 400, {"error": "top must be between 1 and 30"}
    if mode == "render" and not has_key():
        return 400, {"error": "render needs ANTHROPIC_API_KEY in .env (see the note in review_ui)"}
    if not _lock.acquire(blocking=False):
        return 409, {"error": "another job is running; wait for it to finish", "running": _current["id"]}

    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    session_id = f"twitchvod-v{m.group(1)}"
    job_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + m.group(1)
    status = {"id": job_id, "url": url, "mode": mode, "top": top, "session": session_id,
              "state": "running", "step": "starting", "started": datetime.now().isoformat(timespec="seconds")}
    _write_status(job_id, status)
    _current["id"] = job_id
    threading.Thread(target=_worker, args=(job_id, url, mode, top, session_id), daemon=True).start()
    return 202, status


def list_jobs():
    if not JOBS_DIR.exists():
        return []
    items = [_read(p, {}) for p in sorted(JOBS_DIR.glob("*.json"), reverse=True)]
    return [i for i in items if i][:20]


def get_job(job_id):
    if not re.match(r"^[0-9A-Za-z_\-]{1,80}$", job_id or ""):
        return 400, {"error": "bad job id"}
    status = _read(JOBS_DIR / f"{job_id}.json")
    if not status:
        return 404, {"error": "job not found"}
    log_path = JOBS_DIR / f"{job_id}.log"
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:] if log_path.exists() else []
    return 200, {**status, "log": lines, "progress": _progress(status, lines)}


def _eta(status, pct):
    """Rough time left from the time spent so far and the percentage done."""
    try:
        started = datetime.fromisoformat(status["started"])
    except (KeyError, ValueError):
        return None
    elapsed = (datetime.now() - started).total_seconds()
    if pct <= 0 or elapsed <= 0:
        return None
    left = int(elapsed * (100 - pct) / pct)
    return f"about {left // 3600}h {(left % 3600) // 60}m left" if left >= 3600 else f"about {left // 60}m {left % 60}s left"


def _progress(status, lines):
    """Percent for the current step. The video download prints '[download] 12.3% ...' to the log;
    the audio download does not, so for that step we report the file size so far instead."""
    if status.get("state") != "running":
        return {"percent": 100.0 if status.get("state") == "done" else None, "text": status.get("state", "")}
    for line in reversed(lines):
        m = re.search(r"\[download\]\s+([\d.]+)%", line)
        if m:
            pct = float(m.group(1))
            return {"percent": pct, "text": line.strip()[-160:], "eta": _eta(status, pct)}
    session_dir = ROOT / "data" / "vod" / status.get("session", "")
    for name in ("vod.mp4.part", "vod.mp4", "audio.mp4.part", "audio.mp4"):
        f = session_dir / name
        if f.exists():
            return {"percent": None, "text": f"{name}: {f.stat().st_size / 1048576:.0f} MB so far"}
    return {"percent": None, "text": status.get("step", "starting")}
