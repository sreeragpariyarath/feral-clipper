"""Re-render every approved clip of a session with the current layout/settings.

    python rerender_ready.py data\\vod\\twitchvod-v2933231152
    python rerender_ready.py data\\kaicenat\\20261119-220525 --all-ready

Only clips whose status.json says "ready" are re-rendered (skipped clips - cutscenes, menus -
stay skipped). Uses each clip's saved judge.json, so no API calls are made.
"""
import argparse
from pathlib import Path

from common import load_config, log, read_json
from pipeline import rerender


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
