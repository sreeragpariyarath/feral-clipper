"""Step: Get the audio track: download it for a URL, or extract it from a local file."""
import subprocess

from clipper.common import duration_of, fmt_ts

from ..context import Ctx
from ._common import FFMPEG_QUIET, skip


def audio(ctx: Ctx) -> dict:
    """Get the audio track: download it for a URL, or extract it from a local file."""
    for name in ("audio.mp4", "audio.m4a", "audio.wav"):
        p = ctx.folder / name
        if p.exists() and p.stat().st_size > 0:
            return {**skip(ctx, f"audio {name}"), "audio": str(p)}

    if ctx.source_url and not ctx.source_path:
        from clipper.sources.audio_detect import download_audio
        return {"audio": str(download_audio(ctx.source_url, ctx.folder))}

    video = ctx.video_path()
    total = max(1.0, duration_of(video))
    tmp, out = ctx.folder / "audio.tmp.m4a", ctx.folder / "audio.m4a"
    proc = subprocess.Popen(FFMPEG_QUIET + ["-i", str(video), "-vn", "-ac", "1", "-c:a", "aac", "-b:a", "128k",
                                            "-progress", "pipe:1", "-nostats", str(tmp)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in proc.stdout:
        if line.startswith("out_time_us="):
            try:
                done = int(line.split("=", 1)[1]) / 1e6
            except ValueError:
                continue
            ctx.report(min(99.0, 100 * done / total), f"audio {fmt_ts(done)} of {fmt_ts(total)}")
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg could not extract the audio: " + (proc.stderr.read() or "")[-300:])
    tmp.replace(out)
    return {"audio": str(out)}
