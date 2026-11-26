"""Step: Six frames per candidate; the local CLIP model rates them action / boring / unsafe."""
from collections import Counter
import subprocess

import numpy as np


from ..context import Ctx
from ._common import FFMPEG_QUIET, skip


def visual(ctx: Ctx) -> dict:
    """Six frames per candidate; the local CLIP model rates them action / boring / unsafe."""
    if ctx.path("visual.json").exists():
        return skip(ctx, "visual check")
    cands = ctx.read("candidates.json", [])
    video = ctx.video_path()
    model = None
    try:
        from clipper.ai.local_models import Clip
        model = Clip()
    except Exception as exc:
        ctx.log(f"CLIP unavailable, frames are kept without scores: {exc}")
    out = {}
    for i, c in enumerate(cands):
        d = ctx.auto / "frames" / c["no"]
        d.mkdir(parents=True, exist_ok=True)
        paths = []
        for k in range(6):
            t = c["start"] + (k + 0.5) * (c["end"] - c["start"]) / 6
            p = d / f"f{k}.jpg"
            if not p.exists():
                subprocess.run(FFMPEG_QUIET + ["-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                                               "-vf", "scale=384:-2", str(p)], capture_output=True)
            if p.exists():
                paths.append(p)
        res = {"frames": [str(p.relative_to(ctx.folder)) for p in paths],
               "action": None, "boring": None, "unsafe": None, "best": ""}
        if paths:
            subprocess.run(FFMPEG_QUIET + ["-i", str(d / "f%d.jpg"), "-vf", f"tile={len(paths)}x1",
                                           "-frames:v", "1", str(d / "strip.jpg")], capture_output=True)
            res["strip"] = str((d / "strip.jpg").relative_to(ctx.folder))
        if model and paths:
            sc = model.score(model.embed([str(p) for p in paths]))
            res["action"] = round(float(np.mean([s["action"] for s in sc])), 3)
            res["boring"] = round(float(np.mean([s["boring"] for s in sc])), 3)
            res["unsafe"] = round(float(max(s["unsafe"] for s in sc)), 3)
            res["best"] = Counter(s["best"] for s in sc).most_common(1)[0][0]
        out[c["no"]] = res
        ctx.report(100 * (i + 1) / max(1, len(cands)), f"frames checked {i + 1} of {len(cands)}")
    ctx.write("visual.json", out)
    return {"candidates": len(out), "scored": model is not None}
