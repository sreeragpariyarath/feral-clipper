"""Shared helpers: config, paths, logging, subprocess."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # project folder (config.json, data/, models/ live here)

# Windows consoles default to a legacy codepage; don't crash on emoji in titles/chat.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_CONFIG = {
    "data_dir": "data",
    "quality": "720p60,720p,best",
    "segment_seconds": 10,
    "keep_hours": 6,
    "facecam": None,
    "gameplay": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
    "caption_language": None,
    "whisper_model": "large-v3-turbo",
    "whisper_device": "cuda",
    "whisper_compute": "float16",
    "encoder": "h264_nvenc",
    "anthropic_model": "claude-haiku-5-5",
    "twitch_downloader_cli": "TwitchDownloaderCLI",
    "detect": {
        "threshold": 0.45,
        "min_m30": 15,
        "min_ratio": 1.6,
        "audio_threshold": 0.35,
        "pre_s": 45,
        "post_s": 20,
        "merge_s": 45,
        "cooldown_s": 30,
        "warmup_s": 180,
        "baseline_s": 600,
    },
    "decide": {"render_min": 0.55, "strong_min": 0.75},
    "discovery": {"enabled": True, "vision": True, "frames": 4, "bonus": 0.12,
                  "vision_min_text": 0.25, "vision_min_h": 0.6, "model": None},
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    path = ROOT / "config.json"
    if path.exists():
        user = json.loads(path.read_text(encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    cfg["data_dir"] = str((ROOT / cfg["data_dir"]).resolve())
    return cfg


def log(*args):
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}]", *args, flush=True)


def need(binary):
    if shutil.which(binary) is None:
        sys.exit(f"Missing '{binary}'. Install it and make sure it is on PATH.")


def run(cmd, cwd=None, quiet=True):
    """Run a command, raise with stderr tail on failure."""
    res = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL,   # ffmpeg must never wait on the console
    )
    if res.returncode != 0:
        tail = "\n".join(res.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"Command failed: {' '.join(map(str, cmd[:6]))} ...\n{tail}")
    if not quiet:
        print(res.stdout)
    return res


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fmt_ts(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def to_sec(v):
    """'1:02:03' / '2:03' / '45' -> seconds."""
    parts = [float(p) for p in str(v).split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def video_of(session):
    """The downloaded VOD file inside a session folder."""
    for ext in (".mp4", ".mkv", ".ts", ".webm"):
        v = Path(session) / f"vod{ext}"
        if v.exists():
            return v
    raise SystemExit(f"No vod.mp4 in {session}. Run vod.py on the VOD first (it downloads the full video).")


def duration_of(video):
    """Length of a media file in seconds (ffprobe)."""
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(video)]).stdout.strip()
    return float(out)
