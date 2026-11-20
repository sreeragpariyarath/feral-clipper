"""Frame scan: find the moments in a downloaded VOD where something is happening ON SCREEN.

Why: voice/chat detection picks talking moments. This looks at the picture instead.

  1. ffmpeg grabs one small frame every N seconds (keyframes only, so it is fast)
  2. frames are tiled into contact sheets (12 per image) and Claude scores each cell
     using the GTA 6 knowledge list (chase, crash, animal, helicopter, new thing...)
  3. best moments (spaced apart, safe-to-post only) are cut, transcribed, judged and rendered
     by the normal pipeline.

Local mode (after `python tools/setup_models.py`): CLIP + PANNs on your GPU score every frame for free,
then Claude only double-checks the best 36 (3 calls). Without the models it falls back to Claude-only.

Usage (from C:\\clipper\\gta-clipper, venv active, ANTHROPIC_API_KEY set):
  python scan.py data\\vod\\twitchvod-v2933231152 --dry          # just count calls, spend nothing
  python scan.py data\\vod\\twitchvod-v2933231152 --list         # scan + show moments, no render
  python scan.py data\\vod\\twitchvod-v2933231152                # scan + render the top 6
  python scan.py <session> --from 3:30:00 --to 4:30:00 --top 4   # only part of the stream
Re-running is safe: finished sheets are cached in <session>\\scan\\results.json.
"""
import argparse
import math
from pathlib import Path

from clipper.common import duration_of, fmt_ts, load_config, log, need, to_sec, video_of, write_json
from clipper.detect import frame_scan as fs


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", help=r"e.g. data\vod\twitchvod-v2933231152")
    ap.add_argument("--every", type=float, default=None,
                    help="seconds between frames (default 10 with local models, 20 Claude-only)")
    ap.add_argument("--sheet", type=int, default=12, help="frames per contact sheet (default 12)")
    ap.add_argument("--from", dest="t_from", help="start, e.g. 1:00:00")
    ap.add_argument("--to", dest="t_to", help="end, e.g. 3:30:00")
    ap.add_argument("--min", type=float, default=6, help="minimum Claude score to keep (default 6)")
    ap.add_argument("--top", type=int, default=6, help="how many moments to render (default 6)")
    ap.add_argument("--gap", type=float, default=90, help="min seconds between moments (default 90)")
    ap.add_argument("--shortlist", type=int, default=36,
                    help="local mode: how many best frames Claude double-checks (default 36 = 3 calls)")
    ap.add_argument("--no-claude", action="store_true", help="local models only, zero API calls for scanning")
    ap.add_argument("--claude-only", action="store_true", help="old mode: Claude looks at every frame")
    ap.add_argument("--dry", action="store_true", help="only count frames/calls, spend nothing")
    ap.add_argument("--list", action="store_true", help="show the moments, do not render")
    ap.add_argument("--rescan", action="store_true", help="ignore cached scores")
    ap.add_argument("--at", action="append", help="clip this exact time from the local VOD (repeatable), e.g. --at 0:54:46")
    ap.add_argument("--len", type=float, default=100, help="seconds of window around --at (default 100)")
    return ap.parse_args()


def main():
    args = parse_args()
    need("ffmpeg"); need("ffprobe")
    cfg = load_config()
    session = Path(args.session)
    video = video_of(session)
    dur = duration_of(video)
    t_from = to_sec(args.t_from) if args.t_from else 0.0
    t_to = min(dur, to_sec(args.t_to)) if args.t_to else dur

    if args.at:
        fs.clip_manual_times(session, cfg, args.at, args.len, dur)
        return

    local = not args.claude_only and fs.models_ready()
    if not args.claude_only and not local:
        log("Open-source models not installed yet (run: python tools/setup_models.py). Using Claude for every frame.")
    every = args.every or (10 if local else 20)
    n_frames = int((t_to - t_from) // every) + 1
    if local:
        calls = 0 if args.no_claude else math.ceil(min(args.shortlist, n_frames) / args.sheet)
        log(f"{video.name}: {fmt_ts(dur)} long; scanning {fmt_ts(t_from)} - {fmt_ts(t_to)}: {n_frames} frames. "
            f"CLIP + PANNs on your GPU (free) -> Claude double-checks the best {min(args.shortlist, n_frames)} "
            f"({calls} calls)")
    else:
        calls = math.ceil(n_frames / args.sheet)
        log(f"{video.name}: {fmt_ts(dur)} long; scanning {fmt_ts(t_from)} - {fmt_ts(t_to)}: "
            f"{n_frames} frames -> {calls} Claude calls")
    if args.dry:
        log("Dry run: nothing extracted, nothing sent.")
        return

    scan_dir = session / "scan"
    frames, ftimes = fs.grab_frames(video, scan_dir / f"frames_{int(every)}s", t_from, t_to, every)

    # ---- which frames go to Claude
    if local:
        lrows, _ = fs.local_stage(session, scan_dir, video, frames, ftimes, t_from, t_to, args.rescan)
        best = fs.shortlist(lrows, args.shortlist)
        log("Top frames by the local models:")
        for r in sorted(best, key=lambda r: -r["local"])[:10]:
            snd = (" + " + ", ".join(r["sound"])) if r["sound"] else ""
            log(f"  {fmt_ts(r['t'])}  {r['local']:.2f}  {r['clip']}{snd}")
        sel = [r["i"] for r in best]
    else:
        sel = list(range(len(frames)))

    if local and args.no_claude:
        rows = fs.rows_from_local(best)
    else:
        rows = fs.rows_from_claude(cfg, scan_dir, frames, ftimes, sel, every, args.sheet, local, args.rescan)

    chosen = fs.pick(rows, args.min, args.top, args.gap)
    blocked = sum(1 for r in rows if set(r["flags"]) & fs.BLOCK)
    log(f"{len(rows)} scored frames; {blocked} blocked (cutscene/menu/suggestive/gore); {len(chosen)} moments chosen:")
    for r in chosen:
        log(f"  {fmt_ts(r['t'])}  {r['score']:.0f}/10  {r['kind']:<12} {r['what']}")
    write_json(scan_dir / "moments.json", chosen)
    if not chosen:
        log("Nothing strong enough. Try --min 5, a bigger --shortlist, or another part with --from/--to.")
        return
    if args.list:
        log("List only. To render these: run the same command without --list (scores are cached).")
        return
    fs.render_moments(session, cfg, chosen, dur)


if __name__ == "__main__":
    main()
