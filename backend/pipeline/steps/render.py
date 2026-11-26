"""Step: Render each accepted clip: punch layout, webcam crop from the face step, captions."""

from clipper.common import read_json

from ..context import Ctx
from ._common import accepted


def render(ctx: Ctx) -> dict:
    """Render each accepted clip: punch layout, webcam crop from the face step, captions."""
    from clipper.pipeline import render_from_judge
    from clipper.render.media import extract_window
    clips = list(accepted(ctx))
    rendered = 0
    for i, (no, d) in enumerate(clips):
        if (d / "clip.mp4").exists() and (d / "status.json").exists():
            rendered += 1
            continue
        cand, j = read_json(d / "candidate.json"), read_json(d / "judge.json")
        box = (read_json(d / "face.json") if (d / "face.json").exists() else {}).get("box")
        cfg = dict(ctx.cfg, facecam=box, layout=ctx.params.get("layout") or "punch")
        media, offset = extract_window(ctx.folder, cand["win_start"], cand["win_end"], d)
        words = read_json(d / "transcript.json")["words"]
        ctx.report(100 * i / max(1, len(clips)), f"rendering clip {i + 1} of {len(clips)}", force=True)
        render_from_judge(d, media, offset, words, j, cfg, f"#{no}")
        rendered += 1
    ctx.report(100, f"rendered {rendered} clips", force=True)
    return {"rendered": rendered}
