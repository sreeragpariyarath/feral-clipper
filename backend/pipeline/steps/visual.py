"""Step: Six frames per candidate; the local CLIP model rates them and measures scene change."""
import subprocess
from collections import Counter

import numpy as np

from ..context import Ctx
from ._common import FFMPEG_QUIET, skip

VERSION = 3          # 3 = adds what each frame shows (for the judge); older visual.json files are redone


def visual(ctx: Ctx) -> dict:
    """Six frames per candidate; CLIP gives an action-vs-boring margin and a scene-change number."""
    old = ctx.read("visual.json")
    if old and old.get("_version") == VERSION:
        return skip(ctx, "visual check")
    cands = ctx.read("candidates.json", [])
    video = ctx.video_path()
    model = None
    try:
        from clipper.ai.local_models import Clip, scene_change
        model = Clip()
    except (ImportError, OSError, RuntimeError) as exc:        # no GPU / model files: frames only
        ctx.log(f"CLIP unavailable, frames are kept without scores: {exc}")
    out: dict = {"_version": VERSION}
    for i, c in enumerate(cands):
        d = ctx.auto / "frames" / c["no"]
        d.mkdir(parents=True, exist_ok=True)
        paths, times = [], []
        for k in range(6):
            t = c["start"] + (k + 0.5) * (c["end"] - c["start"]) / 6
            p = d / f"f{k}.jpg"
            if not p.exists():
                subprocess.run(FFMPEG_QUIET + ["-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                                               "-vf", "scale=384:-2", str(p)], capture_output=True)
            if p.exists():
                paths.append(p)
                times.append(round(t - c["start"], 1))
        res = {"frames": [str(p.relative_to(ctx.folder)) for p in paths],
               "action": None, "boring": None, "unsafe": None, "margin": None, "change": None, "best": ""}
        if paths and not (d / "strip.jpg").exists():
            subprocess.run(FFMPEG_QUIET + ["-i", str(d / "f%d.jpg"), "-vf", f"tile={len(paths)}x1",
                                           "-frames:v", "1", str(d / "strip.jpg")], capture_output=True)
        if (d / "strip.jpg").exists():
            res["strip"] = str((d / "strip.jpg").relative_to(ctx.folder))
        if model and paths:
            emb = model.embed([str(p) for p in paths])
            sc = model.score(emb)
            res["action"] = round(float(np.mean([s["action"] for s in sc])), 3)
            res["boring"] = round(float(np.mean([s["boring"] for s in sc])), 3)
            res["unsafe"] = round(float(max(s["unsafe"] for s in sc)), 3)
            res["margin"] = round(float(np.mean([s["margin"] for s in sc])), 4)
            res["change"] = round(scene_change(emb), 4)
            res["best"] = Counter(s["best"] for s in sc).most_common(1)[0][0]
            # what each frame looks like, seconds into the window: the judge reads this as `visual_scan`
            res["seen"] = [{"at_s": at, "kind": s["best_kind"], "what": s["best"]} for at, s in zip(times, sc)]
        out[c["no"]] = res
        ctx.report(100 * (i + 1) / max(1, len(cands)), f"frames checked {i + 1} of {len(cands)}")
    ctx.write("visual.json", out)
    return {"candidates": len(out) - 1, "scored": model is not None}
