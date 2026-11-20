"""Live mode: record a Twitch stream in 10 s segments, read chat, detect spikes, make clips.

    python live.py <twitch_channel> [--auto] [--min-m30 8]

--auto   transcribe + judge + render each moment as soon as it is ready
         (without it, moments are only listed in candidates.jsonl; cut later with cut.py)
Stop with Ctrl+C.
"""
import argparse
import json
import queue
import subprocess
import threading
import time
from pathlib import Path

from clipper.sources import chat_twitch
from clipper.common import fmt_ts, load_config, log, need, write_json
from clipper.detect.detector import Detector
from clipper.render.media import list_segments, segments_ready


def recorder(channel, seg_dir, cfg, stop):
    """streamlink | ffmpeg segmenter, restarted with backoff until stop."""
    backoff = 5
    pattern = str(seg_dir / "%Y%m%d-%H%M%S.ts")
    while not stop.is_set():
        sl = subprocess.Popen(
            ["streamlink", "--twitch-disable-ads", "--retry-streams", "30", "--retry-open", "3",
             "--stdout", f"https://twitch.tv/{channel}", cfg["quality"]],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        ff = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-c", "copy",
             "-f", "segment", "-segment_time", str(cfg["segment_seconds"]),
             "-strftime", "1", pattern],
            stdin=sl.stdout, stderr=subprocess.DEVNULL)
        sl.stdout.close()
        log(f"Recorder started for {channel} ({cfg['quality']})")
        started = time.time()
        while not stop.is_set() and ff.poll() is None:
            time.sleep(1)
        for p in (ff, sl):
            if p.poll() is None:
                p.terminate()
        if stop.is_set():
            break
        backoff = 5 if time.time() - started > 120 else min(backoff * 2, 60)
        log(f"Recorder stopped (stream offline or connection drop); retrying in {backoff}s")
        time.sleep(backoff)


def segment_loudness(path, rate=8000):
    """dB per second of one recorded segment."""
    import numpy as np
    res = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                          "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
                         capture_output=True)
    a = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32)
    n = len(a) // rate
    if n == 0:
        return []
    a = a[: n * rate].reshape(n, rate)
    rms = np.sqrt(np.mean(a * a, axis=1)) + 1e-6
    return list(20 * np.log10(rms / 32768))


def audio_watcher(seg_dir, det, lock, stop):
    """Measure the streamer's loudness from each finished segment and feed it to the detector."""
    done = set()
    while not stop.is_set():
        segs = list_segments(seg_dir)
        for st, f in segs[:-1]:                      # the last one is still being written
            if f in done:
                continue
            done.add(f)
            try:
                dbs = segment_loudness(f)
            except Exception:
                continue
            with lock:
                for i, db in enumerate(dbs):
                    det.feed_audio(st + i, db)
        time.sleep(2)


def cleanup(seg_dir, keep_hours, busy_from):
    cutoff = time.time() - keep_hours * 3600
    for st, f in list_segments(seg_dir):
        if st < cutoff and st < busy_from - 120:
            f.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel")
    ap.add_argument("--auto", action="store_true", help="make clips automatically")
    ap.add_argument("--min-m30", type=int, help="min chat msgs in 30s (lower for small channels)")
    args = ap.parse_args()

    need("ffmpeg")
    need("streamlink")
    cfg = load_config()
    if args.min_m30:
        cfg["detect"]["min_m30"] = args.min_m30

    channel = args.channel.lower()
    session = Path(cfg["data_dir"]) / channel / time.strftime("%Y%m%d-%H%M%S")
    seg_dir = session / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    write_json(session / "session.json",
               {"type": "live", "channel": channel, "t0": time.time()})
    log(f"Session: {session}")

    stop = threading.Event()
    det = Detector(cfg)
    lock = threading.Lock()
    chat_file = open(session / "chat.jsonl", "a", encoding="utf-8")

    def on_message(t, user, msg):
        with lock:
            det.feed(t, user, msg)
        chat_file.write(json.dumps({"t": round(t, 2), "u": user, "m": msg}, ensure_ascii=False) + "\n")

    threading.Thread(target=recorder, args=(channel, seg_dir, cfg, stop), daemon=True).start()
    threading.Thread(target=chat_twitch.listen, args=(channel, on_message, stop), daemon=True).start()
    use_audio = cfg["detect"].get("live_audio", True)
    lag = cfg["detect"].get("audio_lag_s", 25) if use_audio else 0
    if use_audio:
        threading.Thread(target=audio_watcher, args=(seg_dir, det, lock, stop), daemon=True).start()

    work = queue.Queue()
    busy_from = [time.time()]

    def worker():
        from clipper.pipeline import process_candidate
        while not stop.is_set():
            try:
                cand = work.get(timeout=1)
            except queue.Empty:
                continue
            busy_from[0] = cand["win_start"]
            for _ in range(60):  # wait for segments to cover the window
                if segments_ready(session, cand["win_end"]):
                    break
                time.sleep(2)
            try:
                process_candidate(session, cand, cfg, force=bool(cand.get("manual")))
            except Exception as e:
                log(f"#{cand['id']:03d} failed: {e}")
            busy_from[0] = time.time()

    if args.auto:
        threading.Thread(target=worker, daemon=True).start()

    manual_n = [900]

    def keyboard():
        """Press Enter in this window to clip the last ~75 s right now."""
        while not stop.is_set():
            try:
                line = input()
            except (EOFError, OSError):
                return
            now = time.time()
            back = cfg["detect"].get("manual_back_s", 75)
            manual_n[0] += 1
            cand = {"id": manual_n[0], "peak_t": now - 15, "win_start": now - back, "win_end": now + 10,
                    "h_score": 0.9, "manual": True, "note": line.strip(),
                    "signals": {"manual": True}, "chat_top": {}, "chat_samples": []}
            with lock:
                for s in range(int(now - 25), int(now)):
                    cand["chat_samples"].extend(det.samples.get(s, []))
            cand["chat_samples"] = cand["chat_samples"][-12:]
            with open(session / "candidates.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(cand, ensure_ascii=False) + "\n")
            log(f"MANUAL CLIP #{cand['id']} marked (last {back} s) - it will be made in ~30 s")
            work.put(cand)

    threading.Thread(target=keyboard, daemon=True).start()

    log("Watching chat. Warm-up 3 min before moments are detected. Ctrl+C to stop.")
    log(">>> See something good on stream? Press ENTER in this window to clip the last 75 s. <<<")
    last_cleanup = time.time()
    last_status = time.time()
    try:
        while True:
            time.sleep(1)
            with lock:
                ready = det.tick(time.time() - lag)
            for cand in ready:
                with open(session / "candidates.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(cand, ensure_ascii=False) + "\n")
                sg = cand.get("signals", {})
                log(f"MOMENT #{cand['id']:03d} at {time.strftime('%H:%M:%S', time.localtime(cand['peak_t']))} "
                    f"H={cand['h_score']} chat={sg.get('h_chat')} voice={sg.get('s_audio')} "
                    f"(+{sg.get('loud_excess_db')} dB) words={cand['chat_top']}")
                if args.auto:
                    work.put(cand)
            if time.time() - last_status > 60:
                segs = len(list(seg_dir.glob("*.ts")))
                with lock:
                    h = det.timeline.get(det.last_scored or 0, 0)
                    sp = sum(det.spam.get(x, 0) for x in range(int(time.time()) - 60, int(time.time())))
                log(f"status: {segs} segments, score now {h:.2f}, moments {det.count}, "
                    f"queue {work.qsize()}, spam filtered/min {sp}")
                last_status = time.time()
            if time.time() - last_cleanup > 600:
                cleanup(seg_dir, cfg["keep_hours"], busy_from[0])
                last_cleanup = time.time()
    except KeyboardInterrupt:
        log("Stopping...")
        stop.set()
        chat_file.close()
        with lock:
            rest = det.flush()
        for cand in rest:
            with open(session / "candidates.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(cand, ensure_ascii=False) + "\n")
        log(f"Done. Moments found: {det.count}. Session: {session}")
        log(f"Cut any moment later: python cut.py \"{session}\" --all")


if __name__ == "__main__":
    main()
