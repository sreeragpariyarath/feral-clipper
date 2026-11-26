"""Step: Combine sound/picture, hook, on-screen action, reaction and payoff into one score; keep the top N."""
import numpy as np

from clipper.detect import quality as q

from ..context import Ctx
from ._common import skip

VERSION = 4          # 4 = stream-relative action score; loudness payoff is info only


def scores(ctx: Ctx) -> dict:
    """Combine every signal into one score per candidate (see clipper.detect.quality); keep the top N."""
    old = ctx.read("scores.json")
    vis = ctx.read("visual.json", {})
    if (old and old.get("version") == VERSION and old.get("top") == ctx.top
            and old.get("visual_version") == vis.get("_version")):
        return skip(ctx, "score sheet")
    cands = ctx.read("candidates.json", [])
    hooks_ = ctx.read("hooks.json", {})
    sig = np.load(ctx.path("signals.npz"))
    db, mot = sig["db"], sig["mot"]
    mot_ref = float(np.percentile(mot, 90)) if len(mot) else 0.0

    visuals = [vis.get(c["no"], {}) for c in cands]
    actions = q.action_scores([v.get("margin") for v in visuals], [v.get("change") for v in visuals])

    rows = []
    for c, v, action in zip(cands, visuals, actions):
        h = hooks_.get(c["no"], {})
        payoff = q.payoff_score(db, mot, c["start"], c["end"], mot_ref)
        talk_only = h.get("talk_density", 0) >= 2.2 and c["raw"]["motion_frac"] < 0.35 and h.get("reaction", 0) < 0.3
        final, notes = q.combine(c["monitor"], h.get("hook_score", 0), action, h.get("reaction", 0), payoff,
                                 talk_only, (v.get("unsafe") or 0) > 0.5)
        rows.append({**c, "hook": h, "visual": {**v, "action_score": action}, "payoff": payoff,
                     "final": final, "notes": notes})
    rows.sort(key=lambda r: r["final"], reverse=True)
    picked = [r["no"] for r in rows[:ctx.top]]
    ctx.write("scores.json", {"version": VERSION, "visual_version": vis.get("_version"), "top": ctx.top, "picked": picked, "all": rows})
    no_payoff = sum("quiet ending" in r["notes"] for r in rows)
    ctx.report(100, f"picked {len(picked)} of {len(rows)}; {no_payoff} end quietly", force=True)
    return {"picked": len(picked), "candidates": len(rows), "quiet_endings": no_payoff}
