"""Make a timestamped transcript of a VOD so Claude (in chat) can pick the best moments.

    python tools/transcript.py <vod_url> [--from 0:50:00] [--to 2:53:00]

Writes data/vod/<id>/transcript.txt. Each line:
    [01:35:28] LOUD+18 bro he's behind me BRO NO NO NO
Upload that file to Claude and ask for picks; save the reply as picks.json, then run picks.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so `clipper` is found when run from tools\

import argparse
from pathlib import Path

import numpy as np

from clipper.sources import audio_detect
from clipper.common import fmt_ts, load_config, log, run, to_sec
from clipper.sources.vod_source import vod_session
from clipper.ai.transcribe import get_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--from", dest="t_from", default="0")
    ap.add_argument("--to", dest="t_to")
    args = ap.parse_args()
    cfg = load_config()

    info, session = vod_session(args.url, cfg)
    audio = audio_detect.download_audio(args.url, session)
    start = to_sec(args.t_from)
    end = to_sec(args.t_to) if args.t_to else float(info.get("duration") or 0)

    log("Measuring loudness...")
    db = audio_detect.loudness_per_second(audio)
    excess = db - audio_detect.rolling_median(db)

    wav = session / "range.wav"
    log(f"Extracting audio {fmt_ts(start)} -> {fmt_ts(end)}")
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-i", str(audio),
         "-t", str(end - start), "-ac", "1", "-ar", "16000", str(wav)])

    log("Transcribing on GPU (a few minutes for a 2-hour stream)...")
    model = get_model(cfg)
    segments, _ = model.transcribe(str(wav), vad_filter=True, beam_size=1,
                                   language=cfg.get("caption_language"),
                                   condition_on_previous_text=False)
    lines = []
    for seg in segments:
        t = start + seg.start
        a, b = int(t), int(start + seg.end) + 1
        loud = float(np.max(excess[a:b])) if b <= len(excess) and b > a else 0.0
        tag = f"LOUD+{loud:.0f} " if loud >= 10 else ""
        text = seg.text.strip()
        if text:
            lines.append(f"[{fmt_ts(t)}] {tag}{text}")
        if len(lines) % 200 == 0 and lines:
            log(f"  ...{fmt_ts(t)}")
    wav.unlink(missing_ok=True)

    header = (f"# {info.get('uploader', '')}: {info.get('title', '')}\n"
              f"# URL: {args.url}\n# Range: {fmt_ts(start)} - {fmt_ts(end)}\n"
              f"# LOUD+N = N dB louder than usual (screaming, gunfire, music)\n\n")
    out = session / "transcript.txt"
    out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    log(f"Done: {len(lines)} lines -> {out}")
    log("Upload transcript.txt to Claude and ask for the best clip picks as picks.json.")


if __name__ == "__main__":
    main()
