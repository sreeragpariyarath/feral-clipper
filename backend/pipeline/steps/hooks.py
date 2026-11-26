"""Step: Hook lines from the transcript and reaction sounds (laughter, screaming) for each candidate."""


from ..context import Ctx
from ._common import skip, window_words


def hooks(ctx: Ctx) -> dict:
    """Hook lines from the transcript and reaction sounds (laughter, screaming) for each candidate."""
    if ctx.path("hooks.json").exists():
        return skip(ctx, "hooks")
    from clipper.detect import hooks as hk
    cands = ctx.read("candidates.json", [])
    words = (ctx.read("transcript.json") or {}).get("words", [])
    tagger = None
    try:
        from clipper.ai.local_models import AudioTagger
        tagger = AudioTagger()
    except Exception as exc:                        # sound tags are a bonus, not required
        ctx.log(f"sound tags unavailable: {exc}")
    src = ctx.audio_path()
    out = {}
    for i, c in enumerate(cands):
        tags = tagger.tag_file(src, c["start"], c["end"]) if tagger else []
        out[c["no"]] = hk.analyze(window_words(words, c["start"], c["end"]), c["end"] - c["start"], tags)
        ctx.report(100 * (i + 1) / max(1, len(cands)), f"hooks {i + 1} of {len(cands)}")
    ctx.write("hooks.json", out)
    return {"candidates": len(out), "with_hook": sum(1 for h in out.values() if h["hook_score"] > 0.3)}
