"""Render clips at exact times chosen by Claude (or you).

    python picks.py <vod_url> picks.json

picks.json:
[
  {"start": "1:35:12", "end": "1:35:48", "hook": "Speed got ambushed", "title": "...", "emphasize": ["NO"]},
  {"start": "2:29:25", "end": "2:30:01", "hook": "...", "layout": "fit"},   <- per-pick layout override
  ...
]
"""
import argparse
import json
import subprocess
from pathlib import Path

from clipper.common import load_config, log, write_json
from clipper.render.media import extract_audio, extract_window
from clipper.pipeline import render_from_judge
from clipper.ai.transcribe import transcribe
from clipper.common import to_sec
from clipper.sources.vod_source import vod_session


def ensure_video(url, session, info):
    vids = [v for v in session.glob("vod.*") if v.suffix in (".mp4", ".mkv", ".webm", ".ts")]
    if not vids:
        log("Downloading video (720p)... one time only, can take a while")
        subprocess.run(["yt-dlp", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
                        "--merge-output-format", "mp4", "-N", "8",
                        "-o", str(session / "vod.%(ext)s"), url], check=True)
        vids = [v for v in session.glob("vod.*") if v.suffix in (".mp4", ".mkv", ".webm", ".ts")]
    write_json(session / "session.json",
               {"type": "vod", "file": vids[0].name, "channel": info.get("uploader", ""), "t0": 0,
                "url": url, "title": info.get("title")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("picks")
    ap.add_argument("--only", help="re-render only these picks, e.g. 3,4,5")
    args = ap.parse_args()
    cfg = load_config()
    raw = Path(args.picks).read_text(encoding="utf-8")
    picks = json.loads(raw[raw.index("["):raw.rindex("]") + 1])

    info, session = vod_session(args.url, cfg)
    ensure_video(args.url, session, info)

    only = {int(x) for x in args.only.split(",")} if args.only else None
    for i, p in enumerate(picks, 1):
        if only and i not in only:
            continue
        pcfg = dict(cfg)
        for key in ("layout", "facecam", "gameplay"):
            if key in p:
                pcfg[key] = p[key]
        start, end = to_sec(p["start"]), to_sec(p["end"])
        pad = 2.0
        cand = {"id": 100 + i, "peak_t": start, "win_start": max(0, start - pad), "win_end": end + pad,
                "h_score": 1.0, "signals": {"source": "picks"}, "chat_top": {}, "chat_samples": []}
        clip_dir = session / "clips" / f"pick{i:02d}"
        clip_dir.mkdir(parents=True, exist_ok=True)
        write_json(clip_dir / "candidate.json", cand)
        try:
            media, offset = extract_window(session, cand["win_start"], cand["win_end"], clip_dir)
            win_len = cand["win_end"] - cand["win_start"]
            wav = clip_dir / "window.wav"
            extract_audio(media, offset, win_len, wav)
            tr = transcribe(wav, cfg)
            wav.unlink(missing_ok=True)
            write_json(clip_dir / "transcript.json", tr)
            j = {"standalone": True, "score": int(p.get("score", 8)), "start_s": pad,
                 "end_s": pad + (end - start), "hook_text": p.get("hook", ""),
                 "title": p.get("title", ""), "emphasize": p.get("emphasize", []),
                 "reasons": p.get("why", ""), "violations": [], "source": "picks"}
            j["final_score"] = round(0.4 + 0.6 * j["score"] / 10, 3)
            write_json(clip_dir / "judge.json", j)
            render_from_judge(clip_dir, media, offset, tr["words"], j, pcfg, f"pick{i:02d}")
        except Exception as e:
            log(f"pick{i:02d} failed: {e}")
    log(f"Done. Clips in {session / 'clips'} (folders pick01, pick02, ...)")


if __name__ == "__main__":
    main()
