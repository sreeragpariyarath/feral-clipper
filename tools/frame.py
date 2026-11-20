"""Save a frame with a 10% grid so you can read the facecam box for config.json.

    python tools/frame.py <session_dir>            (latest live segment, or 10 min into a VOD)
    python tools/frame.py <session_dir> --at 1800  (seconds into a VOD)

Each grid cell is 0.1 of width/height. Example: facecam in the top-right
cell block from 74%..98% wide and 2%..29% tall ->
  "facecam": {"x": 0.74, "y": 0.02, "w": 0.24, "h": 0.27}
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so `clipper` is found when run from tools\

import argparse
from pathlib import Path

from clipper.common import load_config, log, read_json
from clipper.render.media import grab_frame, list_segments


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--at", type=float, default=600)
    args = ap.parse_args()
    load_config()
    session = Path(args.session)
    meta = read_json(session / "session.json")
    if meta["type"] == "vod":
        media, at = session / meta["file"], args.at
    else:
        segs = list_segments(session / "segments")
        if len(segs) < 2:
            raise SystemExit("No finished segments yet")
        media, at = segs[-2][1], 1
    out = session / "frame.jpg"
    grab_frame(media, at, out)
    log(f"Saved {out}. Open it, read the facecam box on the grid, put it in config.json.")


if __name__ == "__main__":
    main()
