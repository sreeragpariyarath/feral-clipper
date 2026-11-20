"""Re-render every approved clip of a session with the current layout/settings.

    python tools/rerender_ready.py data\\vod\\twitchvod-v2933231152
    python tools/rerender_ready.py data\\kaicenat\\20261119-220525 --all-ready

Only clips whose status.json says "ready" are re-rendered (skipped clips - cutscenes, menus -
stay skipped). Uses each clip's saved judge.json, so no API calls are made.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so `clipper` is found when run from tools\

import argparse
from pathlib import Path

from clipper.common import load_config, log, read_json
from clipper.pipeline import rerender


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session", help="session folder (contains a clips folder)")
    args = ap.parse_args()
    cfg = load_config()
    clips = Path(args.session) / "clips"
    if not clips.exists():
        raise SystemExit(f"No clips folder in {args.session}")
    done = 0
    for d in sorted(p for p in clips.iterdir() if p.is_dir()):
        st = d / "status.json"
        if not st.exists() or read_json(st).get("status") != "ready":
            continue
        try:
            rerender(d, cfg)
            done += 1
        except Exception as e:
            log(f"{d.name}: re-render failed: {e}")
    log(f"Re-rendered {done} clip(s) with the current layout.")


if __name__ == "__main__":
    main()
