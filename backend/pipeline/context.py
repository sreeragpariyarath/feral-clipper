"""What a step needs: the job's settings, the stream folder, the pipeline config and a progress reporter.

Progress goes to stdout as one line per update:  @@P {"percent": 42.0, "message": "...", "eta": "..."}
The worker reads these lines from the step process and stores them for the UI.
"""
import json
import time
from pathlib import Path

from clipper.common import load_config

from ..config import VOD_DIR

AUTO_DIR = "auto"      # pipeline outputs live in <stream>/auto/


def _fmt_eta(seconds):
    seconds = int(max(0, seconds))
    if seconds >= 3600:
        return f"about {seconds // 3600}h {seconds % 3600 // 60}m left"
    if seconds >= 60:
        return f"about {seconds // 60}m {seconds % 60}s left"
    return f"about {seconds}s left"


class Ctx:
    def __init__(self, job_id, stream_id, params, source_url=""):
        self.job_id = job_id
        self.stream_id = stream_id
        self.params = params or {}
        self.source_url = source_url
        self.source_path = self.params.get("source_path", "")
        self.top = int(self.params.get("top", 10))
        self.folder = VOD_DIR / stream_id
        self.folder.mkdir(parents=True, exist_ok=True)
        self.auto = self.folder / AUTO_DIR
        self.auto.mkdir(exist_ok=True)
        self.cfg = load_config()
        # campaign settings only when the job names a campaign (phase 5); never another streamer's text
        campaign = self.params.get("campaign") or {}
        self.cfg["campaign_overlay"] = campaign.get("overlay") or None
        self.cfg["campaign_caption"] = campaign.get("caption") or None
        self.cfg["campaign_brief"] = campaign.get("brief") or None
        if self.params.get("render_min") is not None:          # per-job minimum score to render
            self.cfg["decide"] = dict(self.cfg["decide"], render_min=float(self.params["render_min"]))
        self._t0 = time.time()
        self._last = 0.0

    # ------------------------------------------------------------ progress
    def report(self, percent=None, message="", eta=None, force=False):
        now = time.time()
        if not force and now - self._last < 0.5:
            return
        self._last = now
        if eta is None and percent and percent > 0.5:
            elapsed = now - self._t0
            eta = _fmt_eta(elapsed * (100 - percent) / percent)
        print("@@P " + json.dumps({"percent": None if percent is None else round(float(percent), 1),
                                   "message": message[:200], "eta": eta or ""}, ensure_ascii=False), flush=True)

    def log(self, message):
        print(message, flush=True)

    # ------------------------------------------------------------ files
    def path(self, name) -> Path:
        return self.auto / name

    def read(self, name, default=None):
        try:
            return json.loads(self.path(name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def write(self, name, data):
        tmp = self.path(name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path(name))          # never leave a half-written file behind

    def session_meta(self):
        try:
            return json.loads((self.folder / "session.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def video_path(self) -> Path:
        f = self.session_meta().get("file") or ""
        if not f:
            raise RuntimeError("no video registered for this stream yet (run the ingest step)")
        p = Path(f)
        return p if p.is_absolute() else self.folder / p

    def audio_path(self) -> Path:
        for name in ("audio.mp4", "audio.m4a", "audio.wav"):
            if (self.folder / name).exists():
                return self.folder / name
        raise RuntimeError("no audio track yet (run the audio step)")
