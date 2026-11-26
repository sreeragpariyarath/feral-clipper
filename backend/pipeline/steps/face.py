"""Step: Find the streamer's webcam in each accepted clip (MediaPipe)."""

from clipper.common import read_json, write_json

from ..context import Ctx
from ._common import accepted


def face(ctx: Ctx) -> dict:
    """Find the streamer's webcam in each accepted clip (MediaPipe)."""
    from clipper.render.face_track import find_webcam_box
    from clipper.render.media import extract_window
    clips = list(accepted(ctx))
    found = 0
    for i, (no, d) in enumerate(clips):
        if not (d / "face.json").exists():
            cand, j = read_json(d / "candidate.json"), read_json(d / "judge.json")
            media, offset = extract_window(ctx.folder, cand["win_start"], cand["win_end"], d)
            box = find_webcam_box(media, offset + j["start_s"], max(1.0, j["end_s"] - j["start_s"]))
            write_json(d / "face.json", {"box": box})
        found += 1 if (read_json(d / "face.json") or {}).get("box") else 0
        ctx.report(100 * (i + 1) / max(1, len(clips)), f"face check {i + 1} of {len(clips)}")
    return {"clips": len(clips), "with_face": found}
