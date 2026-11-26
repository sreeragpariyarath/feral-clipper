"""Step: Find the streamer's webcam in each accepted clip (MediaPipe, one frame per second)."""
from clipper.common import read_json, write_json

from ..context import Ctx
from ._common import accepted

VERSION = 3          # 3 = per-second tracking, 30 % tiles, overlay-border snap, stream-wide fallback


def face(ctx: Ctx) -> dict:
    """Per clip: track faces every second and take the webcam spot. Clips where no face was found
    (streamer looked away, cam hidden) get the stream's usual webcam spot, if the other clips agree on one."""
    from clipper.render.face_track import find_webcam_box, stream_box
    from clipper.render.media import extract_window
    clips = list(accepted(ctx))
    own: dict[str, dict | None] = {}
    for i, (no, d) in enumerate(clips):
        saved = read_json(d / "face.json") if (d / "face.json").exists() else {}
        if saved.get("version") == VERSION:
            own[no] = saved.get("own")
        else:
            cand, j = read_json(d / "candidate.json"), read_json(d / "judge.json")
            media, offset = extract_window(ctx.folder, cand["win_start"], cand["win_end"], d)
            own[no] = find_webcam_box(media, offset + j["start_s"], max(1.0, j["end_s"] - j["start_s"]))
        ctx.report(90 * (i + 1) / max(1, len(clips)), f"face check {i + 1} of {len(clips)}")

    # the stream-wide spot also uses earlier runs, so one good clip can help the next run
    known = ctx.read("webcam.json") or {}
    usual = stream_box([b for b in own.values() if b] + ([known] if known.get("x") is not None else []))
    if usual:
        ctx.write("webcam.json", usual)

    found = fallback = moving = 0
    for no, d in clips:
        box, source = own[no], "clip"
        if box is None and usual:
            box, source = usual, "stream"
        found += box is not None and source == "clip"
        fallback += source == "stream"
        moving += bool(box and box.get("moving"))
        write_json(d / "face.json", {"version": VERSION, "box": box, "source": source if box else "none",
                                     "own": own[no]})
    ctx.report(100, f"{found} found, {fallback} used the usual webcam spot", force=True)
    return {"clips": len(clips), "with_face": found, "stream_fallback": fallback, "moving_cam": moving}
