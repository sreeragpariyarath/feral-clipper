"""Stream monitor, stages A and B: cheap per-second signals, then sliding-window filters and a score.

No Claude calls in here. Everything is numbers, so a whole stream can be measured on this PC.

Signals (one value per second):
  * audio loudness in dBFS, from the audio track
  * picture change (0..1), measured between keyframes (about every 2 s on Twitch)

Windows (default 30 s, stepped every 5 s) are kept or dropped by the filters in FILTERS,
and get a score sheet of sub-scores. Nothing here decides the final clip; the judge and you do.
"""
import subprocess

import numpy as np

SR = 16000                      # audio sample rate used for loudness
FRAME_W, FRAME_H = 160, 90      # tiny frames are enough to measure change
CHUNK_S = 3600                  # picture change is decoded one hour at a time to keep memory low

# Each filter can be switched on (True) or off (False). A filter that is on is a gate:
# a window that fails it is dropped. "soft" filters only add to the score sheet.
FILTERS = {
    "sustained": True,        # loud for most of the window (gate: energy OR silent action)
    "picture": True,          # the screen changes enough to not be a static shot (gate)
    "silent_action": True,    # quiet audio + strong picture = keep (part of the gate above)
    "start": False,           # the first 3 s have a jump in sound or picture (gate when True)
    "payoff": False,          # the last 5 s have a result (gate when True)
    "talk_only": False,       # needs the transcript; not in stage A yet
    "gameplay": False,        # needs a screen-layout check; not in stage A yet
}

WEIGHTS = {"energy": 0.25, "picture": 0.25, "sound": 0.15, "hook": 0.15, "payoff": 0.20}


# ---------------------------------------------------------------- signals
def audio_db_per_second(audio_path, start=0.0, duration=None):
    """dBFS for every second of the audio. Streams the file, so a 12 h track never sits in memory."""
    if not audio_path.exists():
        raise FileNotFoundError(f"no audio track at {audio_path}")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if start:
        cmd += ["-ss", f"{start:.2f}"]
    cmd += ["-i", str(audio_path)]
    if duration:
        cmd += ["-t", f"{duration:.2f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    need = SR * 2                              # bytes per second of 16-bit mono audio
    out = []
    try:
        while True:
            raw = proc.stdout.read(need)
            if len(raw) < 2:
                break
            samples = np.frombuffer(raw[: len(raw) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0
            out.append(20.0 * np.log10(rms + 1e-6))
            if len(raw) < need:
                break
    finally:
        proc.stdout.close()
        code = proc.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg could not read the audio ({audio_path.name})")
    return np.array(out, dtype=np.float32)


def _keyframe_times(video, start, duration):
    cmd = ["ffprobe", "-v", "error", "-skip_frame", "nokey", "-select_streams", "v:0"]
    cmd += ["-read_intervals", f"{start:.2f}%+{duration:.2f}"]
    cmd += ["-show_entries", "frame=pts_time", "-of", "csv=p=0", str(video)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    times = []
    for line in res.stdout.splitlines():
        line = line.strip().rstrip(",")
        if line and line != "N/A":
            try:
                times.append(float(line))
            except ValueError:
                continue
    return times


def picture_change_per_second(video, start, duration):
    """Picture change (0..1) for every second of [start, start+duration), measured between keyframes.

    Returns a float array of length ceil(duration). Each keyframe's change is spread over the
    seconds until the next keyframe.
    """
    n_sec = int(np.ceil(duration))
    times = _keyframe_times(video, start, duration)
    if len(times) < 2:
        return np.zeros(n_sec, dtype=np.float32)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-skip_frame", "nokey",
           "-ss", f"{start:.2f}", "-t", f"{duration:.2f}", "-i", str(video), "-an",
           "-fps_mode", "passthrough",   # one output frame per keyframe; otherwise ffmpeg repeats frames
           "-vf", f"scale={FRAME_W}:{FRAME_H},format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        tail = res.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
        raise RuntimeError(f"ffmpeg could not decode the picture ({video.name}): {' | '.join(tail)}")
    raw = res.stdout
    frame_bytes = FRAME_W * FRAME_H
    n = min(len(times), len(raw) // frame_bytes)
    if n < 2:
        return np.zeros(n_sec, dtype=np.float32)
    frames = np.frombuffer(raw[: n * frame_bytes], dtype=np.uint8).reshape(n, frame_bytes).astype(np.int16)
    change = np.zeros(n, dtype=np.float32)
    change[1:] = np.abs(np.diff(frames, axis=0)).mean(axis=1) / 255.0
    rel = np.array(times[:n]) - times[0]
    idx = np.searchsorted(rel, np.arange(n_sec), side="right") - 1
    idx = np.clip(idx, 0, n - 1)
    return change[idx]


def picture_change_long(video, start, duration):
    """picture_change_per_second for any length, one hour at a time."""
    parts = []
    t = 0.0
    while t < duration:
        d = min(CHUNK_S, duration - t)
        parts.append(picture_change_per_second(video, start + t, d))
        t += d
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


# ---------------------------------------------------------------- windows and filters
def _safe_mean(x):
    return float(np.mean(x)) if len(x) else 0.0


def score_window(db, mot, a, win, thr_db, thr_mot):
    """Features and filter results for one window [a, a+win) of the per-second arrays."""
    db_w = db[a:a + win]
    mot_w = mot[a:a + win]
    if len(db_w) < win // 2:
        return None
    energy_frac = _safe_mean(db_w > thr_db)
    motion_frac = _safe_mean(mot_w > thr_mot)
    motion_mean = _safe_mean(mot_w)
    before = db[max(0, a - 5):a]
    before_db = float(before.mean()) if len(before) else float(db_w[:3].mean())
    start_jump = float(db_w[:3].max() - before_db)
    start_ok = bool(mot_w[:3].max() >= thr_mot or start_jump >= 6.0)
    payoff_ok = bool(mot_w[-5:].max() >= thr_mot or db_w[-5:].max() >= thr_db)
    rise = float(db_w.max() - np.median(db_w))
    reaction = rise >= 10.0
    silent_action = bool(energy_frac < 0.35 and motion_frac >= 0.5)

    # gates
    passes = True
    if FILTERS["sustained"] or FILTERS["silent_action"]:
        ok_sound = energy_frac >= 0.6
        passes &= ok_sound or (FILTERS["silent_action"] and silent_action)
    if FILTERS["picture"]:
        passes &= motion_frac >= 0.3 or (FILTERS["silent_action"] and silent_action)
    if FILTERS["start"]:
        passes &= start_ok
    if FILTERS["payoff"]:
        passes &= payoff_ok

    # score sheet (0..1 each)
    sub = {
        "energy": min(1.0, energy_frac),
        "picture": min(1.0, motion_frac),
        "sound": 1.0 if reaction else min(1.0, max(0.0, rise / 20.0)),
        "hook": 1.0 if start_ok else 0.3,
        "payoff": 1.0 if payoff_ok else 0.0,
    }
    total = round(sum(WEIGHTS[k] * sub[k] for k in WEIGHTS), 3)
    # peak = the second with the most combined loudness and change, for the cut and the review sheet
    combined = (db_w - thr_db) / 20.0 + mot_w / max(thr_mot, 1e-6)
    peak = a + int(np.argmax(combined))
    return {
        "a": a, "win": win, "peak": peak, "passes": bool(passes), "total": total, "sub": sub,
        "flags": {"silent_action": silent_action, "reaction": reaction,
                  "start_ok": start_ok, "payoff_ok": payoff_ok},
        "raw": {"energy_frac": round(energy_frac, 3), "motion_frac": round(motion_frac, 3),
                "motion_mean": round(motion_mean, 3), "rise_db": round(rise, 1)},
    }


def find_windows(db, mot, win=30, step=5):
    """Score every window; returns dicts for windows that pass the gates."""
    if len(db) < win or len(mot) < win:
        return []
    thr_db = float(np.percentile(db, 50)) + 6.0           # "loud for this stream"
    thr_mot = float(np.percentile(mot, 60))               # "busy for this stream"
    rows = []
    for a in range(0, len(db) - win + 1, step):
        r = score_window(db, mot, a, win, thr_db, thr_mot)
        if r and r["passes"]:
            rows.append(r)
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


def pick_non_overlapping(rows, top, gap=45):
    """Greedy: best first, skip any window whose peak is within `gap` seconds of a kept one."""
    kept = []
    for r in rows:
        if all(abs(r["peak"] - k["peak"]) >= gap for k in kept):
            kept.append(r)
        if len(kept) >= top:
            break
    return kept
