"""Step: Combine sound/picture, hook, visual and reaction into one score; keep the top N."""


from ..context import Ctx
from ._common import skip


def scores(ctx: Ctx) -> dict:
    """Combine sound/picture, hook, visual and reaction into one score; keep the top N."""
    if ctx.path("scores.json").exists():
        return skip(ctx, "score sheet")
    cands = ctx.read("candidates.json", [])
    hooks_ = ctx.read("hooks.json", {})
    vis = ctx.read("visual.json", {})
    rows = []
    for c in cands:
        h, v = hooks_.get(c["no"], {}), vis.get(c["no"], {})
        action = 0.5 if v.get("action") is None else v["action"]
        final = 0.40 * c["monitor"] + 0.25 * h.get("hook_score", 0) + 0.20 * action + 0.15 * h.get("reaction", 0)
        notes = []
        talk_only = h.get("talk_density", 0) >= 2.2 and c["raw"]["motion_frac"] < 0.35 and h.get("reaction", 0) < 0.3
        if talk_only:
            notes.append("talk only")
            final *= 0.6
        if (v.get("unsafe") or 0) > 0.5:
            notes.append("possibly unsafe")
            final *= 0.3
        rows.append({**c, "hook": h, "visual": v, "final": round(final, 3), "notes": notes})
    rows.sort(key=lambda r: r["final"], reverse=True)
    picked = [r["no"] for r in rows[:ctx.top]]
    ctx.write("scores.json", {"top": ctx.top, "picked": picked, "all": rows})
    ctx.report(100, f"picked {len(picked)} of {len(rows)} candidates", force=True)
    return {"picked": len(picked), "candidates": len(rows)}
