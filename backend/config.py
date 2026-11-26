"""Paths and settings. API keys come from .env (git-ignored) and are never sent to the browser."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("FERAL_DATA_DIR", ROOT / "data"))   # tests point this at a temp folder
VOD_DIR = DATA_DIR / "vod"
JOB_LOG_DIR = DATA_DIR / "jobs"
DB_PATH = DATA_DIR / "feral.db"

API_HOST = os.environ.get("FERAL_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("FERAL_API_PORT", "8766"))   # the frontend proxies to this port

WORKER_IDLE_SECONDS = 2.0        # how often the worker looks for new jobs
PROGRESS_WRITE_SECONDS = 1.0     # how often a running step writes progress to the database
MIN_FREE_GB = float(os.environ.get("FERAL_MIN_FREE_GB", 5))   # a step will not start with less free space
LOW_DISK_GB = float(os.environ.get("FERAL_LOW_DISK_GB", 30))  # the app shows a warning below this


def load_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=VALUE lines from .env into os.environ for keys not already set. Values are never printed."""
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


def key_status() -> dict:
    """Which provider keys are set. Only true/false, never the key itself."""
    return {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "gemini": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
    }


load_env()


def judge_ready() -> bool:
    """True when the judge provider chosen in config.json can run (its key is set, or it is local)."""
    from clipper.ai.providers import available
    from clipper.common import load_config
    return available(load_config())
