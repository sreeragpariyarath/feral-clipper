"""Step: Download the VOD from its URL, or register a video file that is already on disk."""
from pathlib import Path

from clipper.common import write_json

from ..context import Ctx
from ._common import skip


def ingest(ctx: Ctx) -> dict:
    """Download the VOD from its URL, or register a video file that is already on disk."""
    try:
        v = ctx.video_path()
        if v.exists() and v.stat().st_size > 0:
            return {**skip(ctx, f"video {v.name}"), "video": str(v)}
    except RuntimeError:
        pass

    if ctx.source_path:
        src = Path(ctx.source_path)
        if not src.is_file():
            raise RuntimeError(f"file not found: {src}")
        write_json(ctx.folder / "session.json", {
            "type": "vod", "file": str(src.resolve()), "channel": ctx.params.get("channel", ""),
            "t0": 0, "url": "", "title": ctx.params.get("title") or src.stem, "source": "local"})
        ctx.report(100, f"using local file {src.name}", force=True)
        return {"video": str(src)}

    from clipper.sources import vod_source as vs
    info, session, duration, channel = vs.open_vod(ctx.source_url, ctx.cfg)
    if session.resolve() != ctx.folder.resolve():
        raise RuntimeError(f"stream folder mismatch: {session.name} vs {ctx.stream_id}")
    ctx.report(0, "downloading video", force=True)
    video = vs.download_vod(ctx.source_url, session, ctx.cfg, int(ctx.params.get("height", 1080)))
    vs.write_session(session, ctx.source_url, info, channel, file=video.name)
    return {"video": str(video), "duration": duration}
