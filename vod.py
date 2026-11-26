"""VOD mode: finished Twitch or YouTube stream -> top moments -> clips.

    python vod.py <vod_url> [--top 10] [--detect-only] [--min-m30 8] [--from 0:50:00] [--to 3:00:00]

Twitch chat replay needs TwitchDownloaderCLI (free). YouTube chat replay comes from yt-dlp.
The real work lives in clipper/sources/vod_source.py; this file only reads the options and calls it in order.
"""
import argparse

from clipper.common import load_config, log, need, read_json
from clipper.pipeline import process_candidate
from clipper.sources import vod_source as vs


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--top", type=int, default=10, help="how many moments to clip")
    ap.add_argument("--detect-only", action="store_true")
    ap.add_argument("--height", type=int, default=1080, help="max video height to download (default 1080)")
    ap.add_argument("--download-only", action="store_true",
                    help="download the VOD + write candidates.json, render nothing (then scan.py and merge.py). "
                         "With --from/--to it downloads ONLY that part, e.g. --from 0:00:00 --to 2:00:00")
    ap.add_argument("--at", action="append",
                    help="clip this time of the video, e.g. --at 28:45:10 (repeat for more); skips detection")
    ap.add_argument("--len", type=int, default=90, help="seconds to grab around --at (default 90)")
    ap.add_argument("--fast", action="store_true",
                    help="download only the minute around each moment, not the whole stream")
    ap.add_argument("--chat", help="chat replay file if you already have one")
    ap.add_argument("--min-m30", type=int)
    ap.add_argument("--audio", action="store_true", help="detect from loud audio instead of chat")
    ap.add_argument("--from", dest="t_from", help="only clip moments after this time, e.g. 0:50:00")
    ap.add_argument("--to", dest="t_to", help="only clip moments before this time, e.g. 3:10:00")
    return ap.parse_args()


def main():
    args = parse_args()
    need("ffmpeg")
    need("yt-dlp")
    cfg = load_config()
    if args.min_m30:
        cfg["detect"]["min_m30"] = args.min_m30

    info, session, duration, channel = vs.open_vod(args.url, cfg)

    if args.at:                                   # exact times, no detection
        vs.clip_manual_times(args.url, info, session, cfg, channel, args.at, args.len)
        return

    sj = session / "session.json"
    if (not args.download_only and not args.fast and sj.exists()
            and read_json(sj).get("slice_start") is not None):
        # The file on disk is only a slice; the moments below would use VOD time and cut the wrong part.
        raise SystemExit("This session holds only a --from/--to slice. Finish it with merge.py "
                         "(see run_stream.py), or delete the session folder and start again.")

    found = vs.find_moments(args.url, info, session, cfg, duration, chat=args.chat, audio=args.audio)
    top = vs.pick_top(found, args.top, args.t_from, args.t_to)
    if args.detect_only:
        return

    if args.fast:                                 # download only the minute around each moment
        vs.clip_fast(args.url, info, session, cfg, channel, top)
        return

    section = None
    if args.download_only and (args.t_from or args.t_to):
        section = vs.slice_range(args.t_from, args.t_to, duration)
    video = vs.download_vod(args.url, session, cfg, args.height, section)
    extra = {} if section is None else {"slice_start": section[0], "slice_end": section[1]}
    vs.write_session(session, args.url, info, channel, file=video.name, **extra)

    if args.download_only:
        log(f"Downloaded. Next: python scan.py \"{session}\" --list --top 15 --gap 45 --min 5   then   "
            f"python merge.py \"{session}\" --list")
        return

    for c in top:
        try:
            process_candidate(session, c, cfg)
        except Exception as e:
            log(f"#{c['id']:03d} failed: {e}")
    log(f"Done. Clips are in {session / 'clips'}")


if __name__ == "__main__":
    main()
