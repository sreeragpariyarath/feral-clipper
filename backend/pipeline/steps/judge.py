"""Step: Claude rates each picked candidate and writes the title and hook. Skipped clips are marked."""

from clipper.common import read_json, write_json

from ..context import Ctx
from ._common import window_words


def judge(ctx: Ctx) -> dict:
    """Claude rates each picked candidate and writes the title and hook. Skipped clips are marked."""
    from clipper.ai.judge import judge as run_judge
    sheet = ctx.read("scores.json") or {}
    words = (ctx.read("transcript.json") or {}).get("words", [])
    picked = [r for r in sheet.get("all", []) if r["no"] in sheet.get("picked", [])]
    channel = ctx.session_meta().get("channel", "")
    tokens_in = tokens_out = judged = rejected = 0
    source = ""
    for i, r in enumerate(picked):
        clip_dir = ctx.folder / "clips" / r["no"]
        clip_dir.mkdir(parents=True, exist_ok=True)
        win_words = window_words(words, r["start"], r["end"])
        cand = {"id": int(r["no"]), "peak_t": r["peak"], "win_start": r["start"], "win_end": r["end"],
                "h_score": r["final"], "signals": {"monitor": True, "hook": r["hook"].get("hook_line", "")},
                "chat_top": {}, "chat_samples": []}
        write_json(clip_dir / "candidate.json", cand)
        write_json(clip_dir / "transcript.json", {"words": win_words})
        if (clip_dir / "judge.json").exists():
            continue                                # judged on an earlier run
        j = run_judge(cand, win_words, r["end"] - r["start"], ctx.cfg, channel, clip_dir,
                      brief=ctx.cfg.get("campaign_brief"))
        j["final_score"] = round(min(1.0, 0.4 * cand["h_score"] + 0.6 * j["score"] / 10), 3)
        write_json(clip_dir / "judge.json", j)
        usage = j.get("usage") or {}
        tokens_in += usage.get("in", 0)
        tokens_out += usage.get("out", 0)
        source = j.get("source", source)
        judged += 1
        if (not j.get("standalone", True)) or j.get("violations") or j["final_score"] < ctx.cfg["decide"]["render_min"]:
            write_json(clip_dir / "status.json", {"status": "skipped", "final": j["final_score"]})
            rejected += 1
        ctx.report(100 * (i + 1) / max(1, len(picked)), f"judged {i + 1} of {len(picked)}: {j.get('title') or '-'}")
    return {"judged": judged, "rejected": rejected, "tokens_in": tokens_in, "tokens_out": tokens_out, "source": source}
