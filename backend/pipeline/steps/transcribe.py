"""Step: Transcribe the whole stream once (Whisper on the GPU). Every clip reuses this transcript."""

from clipper.common import duration_of, fmt_ts

from ..context import Ctx
from ._common import skip


def transcribe(ctx: Ctx) -> dict:
    """Transcribe the whole stream once (Whisper on the GPU). Every clip reuses this transcript."""
    if ctx.path("transcript.json").exists():
        return skip(ctx, "transcript")
    from clipper.ai.transcribe import get_model
    model = get_model(ctx.cfg)
    src = ctx.audio_path()
    total = max(1.0, duration_of(src))
    ctx.report(0, "loading audio for Whisper", force=True)
    segments, info = model.transcribe(str(src), word_timestamps=True, vad_filter=True,
                                      language=ctx.cfg.get("caption_language"), beam_size=1)
    words, segs = [], []
    for seg in segments:
        segs.append({"s": round(seg.start, 2), "e": round(seg.end, 2), "text": seg.text.strip()})
        for w in seg.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)})
        ctx.report(min(99.0, 100 * seg.end / total), f"{fmt_ts(seg.end)} of {fmt_ts(total)} transcribed")
    ctx.write("transcript.json", {"language": info.language, "duration": total, "words": words, "segments": segs})
    return {"language": info.language, "words": len(words), "segments": len(segs)}
