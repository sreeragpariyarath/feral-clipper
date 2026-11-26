"""Step: Score sliding windows with the sound and picture filters; keep the best, spaced apart."""
import numpy as np


from ..context import Ctx
from ._common import skip


def candidates(ctx: Ctx) -> dict:
    """Score sliding windows with the sound and picture filters; keep the best, spaced apart."""
    if ctx.path("candidates.json").exists():
        return skip(ctx, "candidates")
    from clipper.detect import energy as en
    data = np.load(ctx.path("signals.npz"))
    rows = en.find_windows(data["db"], data["mot"], win=int(ctx.params.get("window", 30)), step=5)
    keep = en.pick_non_overlapping(rows, min(40, max(ctx.top * 3, ctx.top)), gap=45)
    cands = [{"no": f"{900 + i}", "start": float(r["a"]), "end": float(r["a"] + r["win"]), "peak": float(r["peak"]),
              "monitor": r["total"], "sub": r["sub"], "flags": r["flags"], "raw": r["raw"]}
             for i, r in enumerate(keep, 1)]
    ctx.write("candidates.json", cands)
    ctx.report(100, f"{len(rows)} windows passed, kept {len(cands)} candidates", force=True)
    return {"windows": len(rows), "candidates": len(cands)}
