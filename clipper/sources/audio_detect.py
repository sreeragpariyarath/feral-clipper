"""Moment detection without chat: loud audio spikes + YouTube "Most replayed" heatmap.

Used by vod.py when a VOD has no chat replay.
"""
import subprocess
from pathlib import Path

import numpy as np

from clipper.common import log, run

RATE = 8000  # loudness only, 8 kHz mono is plenty


def download_audio(url, session):
    found = [p for p in session.glob("audio.*") if p.suffix not in (".part", ".ytdl")]
    if found:
        return found[0]
    log("Downloading audio only (small, fast)...")
    import time
    flags = ["--retries", "15", "--fragment-retries", "30", "--extractor-retries", "8",
             "--socket-timeout", "30", "--retry-sleep", "3"]
    for attempt in range(1, 4):
        try:
            # no capture: yt-dlp prints its progress, so the review UI can show a percentage
            import subprocess
            res = subprocess.run(["yt-dlp", *flags, "-f", "ba", "-o", str(session / "audio.%(ext)s"), url])
            if res.returncode != 0:
                raise RuntimeError("audio download failed (yt-dlp exit %d)" % res.returncode)
            break
        except RuntimeError as e:
            if attempt == 3:
                raise
            log(f"Download failed ({str(e).splitlines()[-1][:120]}), retrying {attempt}/2 in 10 s...")
            time.sleep(10)
    return [p for p in session.glob("audio.*") if p.suffix not in (".part", ".ytdl")][0]


def loudness_per_second(audio_path):
    """Return array of dB (RMS) per second."""
    proc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(audio_path),
         "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
        stdout=subprocess.PIPE)
    out = []
    chunk = RATE * 2 * 60  # one minute of int16 samples
    rest = b""
    while True:
        data = proc.stdout.read(chunk)
        if not data:
            break
        data = rest + data
        usable = len(data) - len(data) % (RATE * 2)
        rest = data[usable:]
        a = np.frombuffer(data[:usable], dtype=np.int16).astype(np.float32).reshape(-1, RATE)
        rms = np.sqrt(np.mean(a * a, axis=1)) + 1e-6
        out.append(20 * np.log10(rms / 32768))
    proc.wait()
    return np.concatenate(out) if out else np.zeros(0)


def rolling_median(x, window=600, step=10):
    n = len(x)
    med = np.zeros(n)
    centers = list(range(0, n, step))
    vals = [np.median(x[max(0, c - window // 2):min(n, c + window // 2) + 1]) for c in centers]
    med[:] = np.interp(np.arange(n), centers, vals)
    return med


def heat_per_second(info, n):
    hm = info.get("heatmap") or []
    heat = np.zeros(n)
    for seg in hm:
        a, b = int(seg["start_time"]), int(seg["end_time"])
        heat[a:min(b + 1, n)] = seg.get("value", 0)
    if heat.max() > 0:
        base = np.median(heat[heat > 0])
        heat = np.clip((heat - base) / max(heat.max() - base, 1e-6), 0, 1)
    return heat, bool(hm)


def detect(url, info, session, cfg, max_moments=40):
    d = cfg["detect"]
    audio = download_audio(url, session)
    log("Measuring loudness...")
    db = loudness_per_second(audio)
    n = len(db)
    if n < 300:
        return []
    excess = db - rolling_median(db)
    # smooth: a moment is a few loud seconds, not one click
    smooth = np.convolve(excess, np.ones(3) / 3, mode="same")
    s_audio = np.clip((smooth - 6) / 24, 0, 1)  # wide range so big spikes still rank
    heat, has_heat = heat_per_second(info, n)
    if has_heat:
        log("Using YouTube 'Most replayed' data too")
        h = 0.65 * s_audio + 0.35 * heat
    else:
        h = s_audio

    thr = d.get("audio_threshold", 0.35)
    order = np.argsort(-h)
    picked = []
    for sec in order:
        if h[sec] < thr or len(picked) >= max_moments:
            break
        if sec < d["warmup_s"]:
            continue
        if any(abs(sec - p) < d["merge_s"] + 15 for p in picked):
            continue
        picked.append(int(sec))
    picked.sort()
    out = []
    for i, t1 in enumerate(picked, 1):
        out.append({
            "id": i, "peak_t": t1,
            "win_start": max(0, t1 - d["pre_s"] + 15),   # audio peaks are at the moment, no chat lag
            "win_end": min(n, t1 + d["post_s"] + 10),
            "h_score": round(float(h[t1]), 3),
            "signals": {"loud_excess_db": round(float(smooth[t1]), 1),
                        "heat": round(float(heat[t1]), 2)},
            "chat_top": {}, "chat_samples": [],
        })
    return out
