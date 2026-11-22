"""Stream monitor: measure a downloaded stream, filter 30 s windows, write a score sheet, optionally render.

    python monitor.py <session> [--from 0:00:00] [--to 1:00:00] [--top 10] [--window 30] [--step 5]
    python monitor.py <session> --top 5 --render        # also cut the top picks with the usual judge + layout

Needs the session folder from run_stream.py / vod.py: it reads the video from session.json and the
audio track from audio.mp4 (the audio-only download made by vod.py). No Claude calls unless --render.

Output in the session folder:
  monitor.json      every picked window with its sub-scores, flags and raw numbers
  monitor_sheet.csv the same picks as a table you can open in Excel
Clip ids for rendered picks are 901+ (manual 801+, merged 701+, scan 501+, chat 001+).
"""
import argparse
import csv
import json
from pathlib import Path

from clipper.common import duration_of, fmt_ts, load_config, log, read_json, to_sec, write_json
from clipper.detect import energy as en


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", help=r"e.g. data\vod\twitchvod-v2933758895")
    ap.add_argument("--from", dest="t_from", default="0:00:00", help="start of the part to measure")
    ap.add_argument("--to", dest="t_to", help="end of the part to measure (default: end of the stream)")
    ap.add_argument("--top", type=int, default=10, help="how many picks to keep (default 10)")
    ap.add_argument("--window", type=int, default=30, help="window length in seconds (default 30)")
    ap.add_argument("--step", type=int, default=5, help="seconds between window starts (default 5)")
    ap.add_argument("--gap", type=int, default=45, help="min seconds between two picks (default 45)")
    ap.add_argument("--render", action="store_true", help="cut the picks with the judge and layout")
    return ap.parse_args()


def main():
    args = parse_args()
    session = Path(args.session)
    sj = session / "session.json"
    if not sj.exists():
        raise SystemExit(f"No session.json in {session}. Run run_stream.py or vod.py on this stream first.")
    meta = read_json(sj)
    if meta.get("slice_start") is not None:
        raise SystemExit("This session is a --from/--to slice. Measure the full stream session instead.")
    video = session / meta.get("file", "")
    audio = session / "audio.mp4"
    if not video.exists():
        raise SystemExit(f"Video file not found: {video}")
    if not audio.exists():
        raise SystemExit(f"Audio track not found: {audio}. Run vod.py with --audio or download it first.")

    total = duration_of(video)
    a0 = to_sec(args.t_from)
    a1 = min(total, to_sec(args.t_to)) if args.t_to else total
    if a1 - a0 < args.window:
        raise SystemExit("The part to measure is shorter than one window.")
    length = int(a1 - a0)
    log(f"Measuring {fmt_ts(a0)} - {fmt_ts(a0 + length)} ({fmt_ts(length)}) of {video.name}")

    db = en.audio_db_per_second(audio, start=a0, duration=length)
    mot = en.picture_change_long(video, a0, length)
    n = min(len(db), len(mot))
    if n < args.window:
        raise SystemExit("Not enough signal data to score windows (is the video readable?)")
    log(f"Signals: {n} seconds of audio and picture data")

    rows = en.find_windows(db[:n], mot[:n], win=args.window, step=args.step)
    picks = en.pick_non_overlapping(rows, args.top, gap=args.gap)
    log(f"Windows that passed the filters: {len(rows)}; picks kept: {len(picks)}")

    out = []
    for i, p in enumerate(picks, 1):
        abs_start = a0 + p["a"]
        row = {"id": 900 + i, "start": round(abs_start, 1), "end": round(abs_start + p["win"], 1),
               "peak": round(a0 + p["peak"], 1), "total": p["total"], "sub": p["sub"],
               "flags": p["flags"], "raw": p["raw"]}
        out.append(row)
        log(f"  #{row['id']}  {fmt_ts(row['start'])}-{fmt_ts(row['end'])}  score {row['total']:.2f}  "
            f"energy {p['sub']['energy']:.2f}  picture {p['sub']['picture']:.2f}  sound {p['sub']['sound']:.2f}  "
            f"hook {p['sub']['hook']:.2f}  payoff {p['sub']['payoff']:.2f}")

    write_json(session / "monitor.json", {"from": a0, "to": a0 + length, "window": args.window,
                                          "step": args.step, "picks": out})
    with open(session / "monitor_sheet.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "start", "end", "peak", "total", "energy", "picture", "sound", "hook", "payoff",
                    "silent_action", "reaction", "start_ok", "payoff_ok", "energy_frac", "motion_frac"])
        for r in out:
            w.writerow([r["id"], fmt_ts(r["start"]), fmt_ts(r["end"]), fmt_ts(r["peak"]), r["total"],
                        r["sub"]["energy"], r["sub"]["picture"], r["sub"]["sound"], r["sub"]["hook"],
                        r["sub"]["payoff"], r["flags"]["silent_action"], r["flags"]["reaction"],
                        r["flags"]["start_ok"], r["flags"]["payoff_ok"], r["raw"]["energy_frac"],
                        r["raw"]["motion_frac"]])
    log(f"Score sheet: {session / 'monitor_sheet.csv'}")

    if not args.render:
        log("Not rendered. Add --render to cut these picks.")
        return
    from clipper.pipeline import process_candidate
    cfg = load_config()
    for r in out:
        cand = {"id": r["id"], "peak_t": r["peak"], "win_start": r["start"], "win_end": r["end"],
                "h_score": r["total"], "signals": {"monitor": True}, "chat_top": {}, "chat_samples": []}
        try:
            process_candidate(session, cand, cfg)
        except Exception as e:
            log(f"#{r['id']} failed: {e}")


if __name__ == "__main__":
    main()
