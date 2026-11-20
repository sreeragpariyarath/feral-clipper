"""VOD mode: finished Twitch or YouTube stream -> top moments -> clips.

    python vod.py <vod_url> [--top 10] [--detect-only] [--min-m30 8] [--from 0:50:00] [--to 3:00:00]

Twitch chat replay needs TwitchDownloaderCLI (free). YouTube chat replay comes from yt-dlp.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from common import fmt_ts, load_config, log, need, read_json, run, write_json
from detector import Detector


def load_chat(path):
    """Return sorted [(t_seconds, user, msg)] from TwitchDownloader JSON or yt-dlp live_chat.json."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    events = []
    if text.lstrip().startswith("{") and '"comments"' in text[:5000]:
        for c in json.loads(text)["comments"]:
            msg = (c.get("message") or {}).get("body", "")
            user = ((c.get("commenter") or {}).get("name")
                    or (c.get("commenter") or {}).get("display_name") or "?")
            events.append((float(c["content_offset_seconds"]), user.lower(), msg))
    else:  # yt-dlp YouTube live_chat (one JSON object per line)
        for line in text.splitlines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            replay = obj.get("replayChatItemAction", {})
            t = int(replay.get("videoOffsetTimeMsec", -1)) / 1000
            for act in replay.get("actions", []):
                item = act.get("addChatItemAction", {}).get("item", {})
                r = item.get("liveChatTextMessageRenderer")
                if not r or t < 0:
                    continue
                parts = []
                for run_ in r.get("message", {}).get("runs", []):
                    if "text" in run_:
                        parts.append(run_["text"])
                    elif "emoji" in run_:
                        sc = run_["emoji"].get("shortcuts") or [""]
                        parts.append(sc[0].strip(":") or run_["emoji"].get("emojiId", ""))
                user = r.get("authorName", {}).get("simpleText", "?")
                events.append((t, user.lower(), " ".join(parts)))
    events.sort(key=lambda e: e[0])
    return events


def get_chat(info, session, cfg, chat_arg):
    if chat_arg:
        return Path(chat_arg)
    extractor = info.get("extractor_key", "").lower()
    if "twitch" in extractor:
        out = session / "chat_raw.json"
        if out.exists():
            return out
        cli = cfg["twitch_downloader_cli"]
        if shutil.which(cli) is None and not Path(cli).exists():
            raise SystemExit(
                "Twitch chat replay needs TwitchDownloaderCLI.\n"
                "Download it from github.com/lay295/TwitchDownloader/releases (CLI zip),\n"
                "put TwitchDownloaderCLI.exe in this folder or on PATH, or set "
                "'twitch_downloader_cli' in config.json.")
        log("Downloading Twitch chat replay...")
        run([cli, "chatdownload", "--id", str(info["id"]).lstrip("v"), "-o", str(out)])
        return out
    if "youtube" in extractor:
        log("Downloading YouTube chat replay...")
        run(["yt-dlp", "--skip-download", "--write-subs", "--sub-langs", "live_chat",
             "-o", str(session / "chat_raw"), info["webpage_url"]])
        found = list(session.glob("chat_raw*.json"))
        if not found:
            log("No YouTube chat replay on this video -> switching to audio-spike detection")
            return None
        return found[0]
    raise SystemExit(f"Unsupported site: {extractor}. Pass a chat file with --chat.")


def vod_download_cmd(url, out_template, rate, height=1080, section=None):
    """yt-dlp command for the VOD. section=(start_s, end_s) downloads only that part."""
    cmd = ["yt-dlp", "-f", f"bv*[height<={height}]+ba/b[height<={height}]/b",
           "--retries", "15", "--fragment-retries", "30", "--extractor-retries", "8",
           "--socket-timeout", "30", "--retry-sleep", "3",
           "--limit-rate", str(rate),
           "--merge-output-format", "mp4", "-N", "4"]
    if section:
        cmd += ["--download-sections", f"*{int(section[0])}-{int(section[1])}"]
    return cmd + ["-o", str(out_template), url]


def download_section(url, cand, clip_dir, cfg, tries=5):
    """Download only [win_start-5, win_end+5] of a VOD into clip_dir/source.mp4."""
    import time
    clip_dir.mkdir(parents=True, exist_ok=True)
    src = clip_dir / "source.mp4"
    if src.exists() and src.stat().st_size > 100_000:
        return True
    a = max(0, int(cand["win_start"]) - 5)
    b = int(cand["win_end"]) + 5
    log(f"#{cand['id']:03d} downloading {fmt_ts(a)}-{fmt_ts(b)} only...")
    cmd = ["yt-dlp", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--download-sections", f"*{a}-{b}",
           "--retries", "10", "--extractor-retries", "8", "--socket-timeout", "30",
           "--merge-output-format", "mp4", "--force-overwrites", "-o", str(src), url]
    for attempt in range(1, tries + 1):
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0 and src.exists() and src.stat().st_size > 100_000:
            write_json(clip_dir / "source.json", {"start": a, "end": b})
            return True
        tail = (res.stderr or "").strip().splitlines()[-1:] or [""]
        log(f"   try {attempt}/{tries} failed ({tail[0][:100]}), retrying in 8 s")
        time.sleep(8)
    return False


def main():
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
    args = ap.parse_args()

    need("ffmpeg")
    need("yt-dlp")
    cfg = load_config()
    if args.min_m30:
        cfg["detect"]["min_m30"] = args.min_m30

    log("Reading VOD info...")
    import time
    info = None
    for attempt in range(1, 11):
        try:
            info = json.loads(run(["yt-dlp", "-J", "--no-warnings", "--extractor-retries", "5",
                                   "--socket-timeout", "30", args.url]).stdout)
            break
        except RuntimeError as e:
            if attempt == 10:
                raise SystemExit("Could not reach Twitch after 10 tries (your network drops it). "
                                 "Turn on Cloudflare WARP / a VPN and run the command again.")
            log(f"Twitch connection dropped (try {attempt}/10), retrying in 8 s...")
            time.sleep(8)
    site = info.get("extractor_key", "site").lower()
    session = Path(cfg["data_dir"]) / "vod" / f"{site}-{info['id']}"
    session.mkdir(parents=True, exist_ok=True)
    duration = float(info.get("duration") or 0)
    channel = info.get("uploader") or info.get("channel") or ""
    log(f"{channel}: '{info.get('title', '')}' ({fmt_ts(duration)}) -> {session}")

    if args.at:
        def _sec(x):
            p = [float(q) for q in x.split(":")]
            while len(p) < 3:
                p.insert(0, 0)
            return p[0] * 3600 + p[1] * 60 + p[2]
        write_json(session / "session.json",
                   {"type": "vod", "file": "", "fast": True, "channel": channel, "t0": 0,
                    "url": args.url, "title": info.get("title")})
        from pipeline import process_candidate
        for i, at in enumerate(args.at, 1):
            t = _sec(at)
            c = {"id": 800 + i, "peak_t": t, "win_start": max(0, t - args.len * 2 // 3),
                 "win_end": t + args.len // 3, "h_score": 0.9, "manual": True,
                 "signals": {"manual": True}, "chat_top": {}, "chat_samples": []}
            if download_section(args.url, c, session / "clips" / f"{c['id']:03d}", cfg):
                try:
                    process_candidate(session, c, cfg, force=True)
                except Exception as e:
                    log(f"#{c['id']} failed: {e}")
            else:
                log(f"#{c['id']} download failed")
        log(f"Done. Clips are in {session / 'clips'}")
        return

    chat_path = None if args.audio else get_chat(info, session, cfg, args.chat)
    if chat_path is None:
        import audio_detect
        found = audio_detect.detect(args.url, info, session, cfg)
    else:
        events = load_chat(chat_path)
        log(f"Chat messages: {len(events)}")
        if len(events) < 200:
            log("Warning: very little chat. Detection works best on streams with active chat.")
        det = Detector(cfg)
        found = []
        for t, u, m in events:
            found += det.tick(t)
            det.feed(t, u, m)
        found += det.tick((duration or events[-1][0]) + 120)
        found += det.flush()
    for c in found:
        c["win_start"] = max(0, c["win_start"])
        if duration:
            c["win_end"] = min(duration, c["win_end"])
    write_json(session / "candidates.json", found)

    def to_sec(v):
        parts = [float(p) for p in v.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        return parts[0] * 3600 + parts[1] * 60 + parts[2]

    if args.t_from:
        found = [c for c in found if c["win_start"] >= to_sec(args.t_from)]
    if args.t_to:
        found = [c for c in found if c["win_end"] <= to_sec(args.t_to)]

    top = sorted(found, key=lambda c: c["h_score"], reverse=True)[:args.top]
    top.sort(key=lambda c: c["peak_t"])
    log(f"Moments found: {len(found)}; clipping top {len(top)}:")
    for c in top:
        log(f"  #{c['id']:03d} at {fmt_ts(c['peak_t'])}  H={c['h_score']}  chat={c['chat_top']}")
    if args.detect_only:
        return

    if args.fast:
        write_json(session / "session.json",
                   {"type": "vod", "file": "", "fast": True, "channel": channel, "t0": 0,
                    "url": args.url, "title": info.get("title")})
        from pipeline import process_candidate
        for c in top:
            clip_dir = session / "clips" / f"{c['id']:03d}"
            if not download_section(args.url, c, clip_dir, cfg):
                log(f"#{c['id']:03d} section download failed, skipping")
                continue
            try:
                process_candidate(session, c, cfg)
            except Exception as e:
                log(f"#{c['id']:03d} failed: {e}")
        log(f"Done. Clips are in {session / 'clips'}")
        return

    # --download-only with --from/--to downloads ONLY that part of the VOD (a 2 h slice instead of 11-20 h).
    # Chat moments keep VOD time; merge.py shifts them by slice_start so everything lines up with the file.
    slice_start = slice_end = None
    if args.download_only and (args.t_from or args.t_to):
        slice_start = to_sec(args.t_from) if args.t_from else 0.0
        slice_end = to_sec(args.t_to) if args.t_to else slice_start + 7200
        if duration:
            slice_end = min(slice_end, duration)
        if slice_end - slice_start < 60:
            raise SystemExit("The --from/--to slice is shorter than a minute.")
    vids = list(session.glob("vod.*"))
    vids = [v for v in vids if v.suffix in (".mp4", ".mkv", ".ts", ".webm")]
    sj = session / "session.json"
    if vids and slice_start is not None:
        old = read_json(sj).get("slice_start") if sj.exists() else None
        if old != slice_start:
            raise SystemExit(f"{vids[0].name} already exists here and is not the {fmt_ts(slice_start)} slice. "
                             f"Delete it (and session.json), then run this again.")
    if not vids:
        if slice_start is not None:
            log(f"Downloading only {fmt_ts(slice_start)} - {fmt_ts(slice_end)} "
                f"({fmt_ts(slice_end - slice_start)}) at up to {args.height}p...")
        else:
            log(f"Downloading video (up to {args.height}p)... this can take a while for long streams")
        import time
        cmd = vod_download_cmd(args.url, session / "vod.%(ext)s", cfg.get("vod_limit_rate", "1.5M"),
                               args.height, None if slice_start is None else (slice_start, slice_end))
        for attempt in range(1, 9):
            rc = subprocess.run(cmd).returncode
            if rc == 0:
                break
            if attempt == 8:
                raise SystemExit("Video download kept failing (network drops Twitch). "
                                 "Try a VPN / Cloudflare WARP, then run the same command again.")
            log(f"Download interrupted (attempt {attempt}/8), retrying in 15 s... (progress is kept)")
            time.sleep(15)
        vids = [v for v in session.glob("vod.*") if v.suffix in (".mp4", ".mkv", ".ts", ".webm")]
    meta = {"type": "vod", "file": vids[0].name, "channel": channel, "t0": 0,
            "url": args.url, "title": info.get("title")}
    if slice_start is not None:
        meta.update(slice_start=slice_start, slice_end=slice_end)
    write_json(session / "session.json", meta)

    if args.download_only:
        log(f"Downloaded. Next: python scan.py \"{session}\" --list --top 15 --gap 45 --min 5   then   "
            f"python merge.py \"{session}\" --list")
        return

    from pipeline import process_candidate
    for c in top:
        try:
            process_candidate(session, c, cfg)
        except Exception as e:
            log(f"#{c['id']:03d} failed: {e}")
    log(f"Done. Clips are in {session / 'clips'}")


if __name__ == "__main__":
    main()
