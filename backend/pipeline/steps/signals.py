"""Step: Per-second loudness and picture change for the whole stream."""
import numpy as np

from clipper.common import duration_of, fmt_ts

from ..context import Ctx
from ._common import skip


def signals(ctx: Ctx) -> dict:
    """Per-second loudness and picture change for the whole stream."""
    if ctx.path("signals.npz").exists():
        return skip(ctx, "signals")
    from clipper.detect import energy as en
    video = ctx.video_path()
    total = int(duration_of(video))
    db = en.audio_db_per_second(ctx.audio_path(), 0.0, total,
                                progress=lambda s: ctx.report(40 * s / total, f"loudness {fmt_ts(s)} of {fmt_ts(total)}"))
    mot = en.picture_change_long(video, 0.0, total, chunk_s=600,
                                 progress=lambda s: ctx.report(40 + 60 * s / total, f"picture {fmt_ts(s)} of {fmt_ts(total)}"))
    n = min(len(db), len(mot))
    tmp = ctx.path("signals.tmp.npz")
    np.savez(tmp, db=db[:n], mot=mot[:n])
    tmp.replace(ctx.path("signals.npz"))
    return {"seconds": n}
