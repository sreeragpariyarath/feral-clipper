"""The 12 pipeline steps.

Every step reads its inputs from the stream folder, writes its output there (most under <stream>/auto/),
reports progress through ctx.report(), and returns a short summary. When its output already exists,
the step reports 100% and returns at once, so a job resumes where it stopped.
"""
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

from clipper.common import duration_of, fmt_ts, read_json, write_json

from .context import Ctx

FFMPEG_QUIET = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]


def _skip(ctx: Ctx, what: str) -> dict:
    ctx.report(100, f"{what} already done, skipped", force=True)
    return {"skipped": True}


def _window_words(words, start, end):
    return [{"w": w["w"], "s": round(w["s"] - start, 2), "e": round(w["e"] - start, 2)}
            for w in words if w["e"] > start and w["s"] < end]


# 1 ---------------------------------------------------------------- ingest
def ingest(ctx: Ctx) -> dict:
    """Download the VOD from its URL, or register a video file that is already on disk."""
    try:
        v = ctx.video_path()
        if v.exists() and v.stat().st_size > 0:
            return {**_skip(ctx, f"video {v.name}"), "video": str(v)}
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


# 2 ---------------------------------------------------------------- audio
def audio(ctx: Ctx) -> dict:
    """Get the audio track: download it for a URL, or extract it from a local file."""
    for name in ("audio.mp4", "audio.m4a", "audio.wav"):
        p = ctx.folder / name
        if p.exists() and p.stat().st_size > 0:
            return {**_skip(ctx, f"audio {name}"), "audio": str(p)}

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


# 3 ---------------------------------------------------------------- transcribe
def transcribe(ctx: Ctx) -> dict:
    """Transcribe the whole stream once (Whisper on the GPU). Every clip reuses this transcript."""
    if ctx.path("transcript.json").exists():
        return _skip(ctx, "transcript")
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


# 4 ---------------------------------------------------------------- signals
def signals(ctx: Ctx) -> dict:
    """Per-second loudness and picture change for the whole stream."""
    if ctx.path("signals.npz").exists():
        return _skip(ctx, "signals")
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


# 5 ---------------------------------------------------------------- candidates
def candidates(ctx: Ctx) -> dict:
    """Score sliding windows with the sound and picture filters; keep the best, spaced apart."""
    if ctx.path("candidates.json").exists():
        return _skip(ctx, "candidates")
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


# 6 ---------------------------------------------------------------- hooks
def hooks(ctx: Ctx) -> dict:
    """Hook lines from the transcript and reaction sounds (laughter, screaming) for each candidate."""
    if ctx.path("hooks.json").exists():
        return _skip(ctx, "hooks")
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
        out[c["no"]] = hk.analyze(_window_words(words, c["start"], c["end"]), c["end"] - c["start"], tags)
        ctx.report(100 * (i + 1) / max(1, len(cands)), f"hooks {i + 1} of {len(cands)}")
    ctx.write("hooks.json", out)
    return {"candidates": len(out), "with_hook": sum(1 for h in out.values() if h["hook_score"] > 0.3)}


# 7 ---------------------------------------------------------------- visual
def visual(ctx: Ctx) -> dict:
    """Six frames per candidate; the local CLIP model rates them action / boring / unsafe."""
    if ctx.path("visual.json").exists():
        return _skip(ctx, "visual check")
    cands = ctx.read("candidates.json", [])
    video = ctx.video_path()
    model = None
    try:
        from clipper.ai.local_models import Clip
        model = Clip()
    except Exception as exc:
        ctx.log(f"CLIP unavailable, frames are kept without scores: {exc}")
    out = {}
    for i, c in enumerate(cands):
        d = ctx.auto / "frames" / c["no"]
        d.mkdir(parents=True, exist_ok=True)
        paths = []
        for k in range(6):
            t = c["start"] + (k + 0.5) * (c["end"] - c["start"]) / 6
            p = d / f"f{k}.jpg"
            if not p.exists():
                subprocess.run(FFMPEG_QUIET + ["-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                                               "-vf", "scale=384:-2", str(p)], capture_output=True)
            if p.exists():
                paths.append(p)
        res = {"frames": [str(p.relative_to(ctx.folder)) for p in paths],
               "action": None, "boring": None, "unsafe": None, "best": ""}
        if paths:
            subprocess.run(FFMPEG_QUIET + ["-i", str(d / "f%d.jpg"), "-vf", f"tile={len(paths)}x1",
                                           "-frames:v", "1", str(d / "strip.jpg")], capture_output=True)
            res["strip"] = str((d / "strip.jpg").relative_to(ctx.folder))
        if model and paths:
            sc = model.score(model.embed([str(p) for p in paths]))
            res["action"] = round(float(np.mean([s["action"] for s in sc])), 3)
            res["boring"] = round(float(np.mean([s["boring"] for s in sc])), 3)
            res["unsafe"] = round(float(max(s["unsafe"] for s in sc)), 3)
            res["best"] = Counter(s["best"] for s in sc).most_common(1)[0][0]
        out[c["no"]] = res
        ctx.report(100 * (i + 1) / max(1, len(cands)), f"frames checked {i + 1} of {len(cands)}")
    ctx.write("visual.json", out)
    return {"candidates": len(out), "scored": model is not None}


# 8 ---------------------------------------------------------------- scores
def scores(ctx: Ctx) -> dict:
    """Combine sound/picture, hook, visual and reaction into one score; keep the top N."""
    if ctx.path("scores.json").exists():
        return _skip(ctx, "score sheet")
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


# 9 ---------------------------------------------------------------- judge
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
        win_words = _window_words(words, r["start"], r["end"])
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


def _accepted(ctx: Ctx):
    """Clip folders that were judged and not rejected, in the order of the score sheet."""
    sheet = ctx.read("scores.json") or {}
    for no in sheet.get("picked", []):
        d = ctx.folder / "clips" / no
        status = read_json(d / "status.json") if (d / "status.json").exists() else {}
        if (d / "judge.json").exists() and status.get("status") != "skipped":
            yield no, d


# 10 --------------------------------------------------------------- face
def face(ctx: Ctx) -> dict:
    """Find the streamer's webcam in each accepted clip (MediaPipe)."""
    from clipper.render.face_track import find_webcam_box
    from clipper.render.media import extract_window
    clips = list(_accepted(ctx))
    found = 0
    for i, (no, d) in enumerate(clips):
        if not (d / "face.json").exists():
            cand, j = read_json(d / "candidate.json"), read_json(d / "judge.json")
            media, offset = extract_window(ctx.folder, cand["win_start"], cand["win_end"], d)
            box = find_webcam_box(media, offset + j["start_s"], max(1.0, j["end_s"] - j["start_s"]))
            write_json(d / "face.json", {"box": box})
        found += 1 if (read_json(d / "face.json") or {}).get("box") else 0
        ctx.report(100 * (i + 1) / max(1, len(clips)), f"face check {i + 1} of {len(clips)}")
    return {"clips": len(clips), "with_face": found}


# 11 --------------------------------------------------------------- render
def render(ctx: Ctx) -> dict:
    """Render each accepted clip: punch layout, webcam crop from the face step, captions."""
    from clipper.pipeline import render_from_judge
    from clipper.render.media import extract_window
    clips = list(_accepted(ctx))
    rendered = 0
    for i, (no, d) in enumerate(clips):
        if (d / "clip.mp4").exists() and (d / "status.json").exists():
            rendered += 1
            continue
        cand, j = read_json(d / "candidate.json"), read_json(d / "judge.json")
        box = (read_json(d / "face.json") if (d / "face.json").exists() else {}).get("box")
        cfg = dict(ctx.cfg, facecam=box, layout=ctx.params.get("layout") or "punch")
        media, offset = extract_window(ctx.folder, cand["win_start"], cand["win_end"], d)
        words = read_json(d / "transcript.json")["words"]
        ctx.report(100 * i / max(1, len(clips)), f"rendering clip {i + 1} of {len(clips)}", force=True)
        render_from_judge(d, media, offset, words, j, cfg, f"#{no}")
        rendered += 1
    ctx.report(100, f"rendered {rendered} clips", force=True)
    return {"rendered": rendered}


# 12 --------------------------------------------------------------- ready
def ready(ctx: Ctx) -> dict:
    """Summarise the run; the worker loads the clips into the library."""
    base = ctx.folder / "clips"
    statuses = Counter()
    for d in base.glob("9*") if base.exists() else []:
        s = read_json(d / "status.json") if (d / "status.json").exists() else {}
        statuses[s.get("status", "unfinished")] += 1
    summary = {"ready": statuses.get("ready", 0), "skipped": statuses.get("skipped", 0)}
    ctx.write("summary.json", summary)
    ctx.report(100, f"{summary['ready']} clips ready, {summary['skipped']} skipped", force=True)
    return summary


STEPS = {
    "ingest": ("Download or open the video", ingest),
    "audio": ("Get the audio", audio),
    "transcribe": ("Transcribe the stream", transcribe),
    "signals": ("Measure loudness and picture", signals),
    "candidates": ("Find candidate moments", candidates),
    "hooks": ("Find hooks and reactions", hooks),
    "visual": ("Check what is on screen", visual),
    "scores": ("Build the score sheet", scores),
    "judge": ("Judge with Claude", judge),
    "face": ("Find the streamer's face", face),
    "render": ("Render the clips", render),
    "ready": ("Ready for review", ready),
}
ORDER = list(STEPS)
