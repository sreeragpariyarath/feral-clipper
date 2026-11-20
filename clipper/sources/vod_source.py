"""Getting a VOD and finding moments in it: info, chat, detection, download.

Everything here is a plain function; vod.py (the command) just calls them in order.
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

from clipper.common import fmt_ts, log, read_json, run, to_sec, write_json
from clipper.detect.detector import Detector
from clipper.pipeline import process_candidate


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


def open_vod(url, cfg):
    """Ask yt-dlp about the VOD and make its session folder. -> (info, session, duration, channel)"""
    log("Reading VOD info...")
    info = None
    for attempt in range(1, 11):
        try:
            info = json.loads(run(["yt-dlp", "-J", "--no-warnings", "--extractor-retries", "5",
                                   "--socket-timeout", "30", url]).stdout)
            break
        except RuntimeError:
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
    return info, session, duration, channel


def write_session(session, url, info, channel, file="", fast=False, **extra):
    meta = {"type": "vod", "file": file, "channel": channel, "t0": 0, "url": url, "title": info.get("title")}
    if fast:
        meta["fast"] = True
    meta.update(extra)
    write_json(session / "session.json", meta)


def find_moments(url, info, session, cfg, duration, chat=None, audio=False):
    """Detect moments from chat (or loud audio) and save them to candidates.json."""
    chat_path = None if audio else get_chat(info, session, cfg, chat)
    if chat_path is None:
        from clipper.sources import audio_detect
        found = audio_detect.detect(url, info, session, cfg)
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
    return found


def pick_top(found, top, t_from=None, t_to=None):
    """Keep moments inside --from/--to, then the best `top` by score, in time order."""
    if t_from:
        found = [c for c in found if c["win_start"] >= to_sec(t_from)]
    if t_to:
        found = [c for c in found if c["win_end"] <= to_sec(t_to)]
    best = sorted(found, key=lambda c: c["h_score"], reverse=True)[:top]
    best.sort(key=lambda c: c["peak_t"])
    log(f"Moments found: {len(found)}; clipping top {len(best)}:")
    for c in best:
        log(f"  #{c['id']:03d} at {fmt_ts(c['peak_t'])}  H={c['h_score']}  chat={c['chat_top']}")
    return best


def clip_manual_times(url, info, session, cfg, channel, times, length):
    """--at: clip exact times without any detection (downloads just that minute or two)."""
    write_session(session, url, info, channel, fast=True)
    for i, at in enumerate(times, 1):
        t = to_sec(at)
        c = {"id": 800 + i, "peak_t": t, "win_start": max(0, t - length * 2 // 3),
             "win_end": t + length // 3, "h_score": 0.9, "manual": True,
             "signals": {"manual": True}, "chat_top": {}, "chat_samples": []}
        if download_section(url, c, session / "clips" / f"{c['id']:03d}", cfg):
            try:
                process_candidate(session, c, cfg, force=True)
            except Exception as e:
                log(f"#{c['id']} failed: {e}")
        else:
            log(f"#{c['id']} download failed")
    log(f"Done. Clips are in {session / 'clips'}")


def clip_fast(url, info, session, cfg, channel, top):
    """--fast: download only the minute around each moment, not the whole stream."""
    write_session(session, url, info, channel, fast=True)
    for c in top:
        clip_dir = session / "clips" / f"{c['id']:03d}"
        if not download_section(url, c, clip_dir, cfg):
            log(f"#{c['id']:03d} section download failed, skipping")
            continue
        try:
            process_candidate(session, c, cfg)
        except Exception as e:
            log(f"#{c['id']:03d} failed: {e}")
    log(f"Done. Clips are in {session / 'clips'}")


def slice_range(t_from, t_to, duration):
    """--download-only with --from/--to downloads ONLY that part of the VOD (a 2 h slice instead of 11-20 h).
    Chat moments keep VOD time; merge.py shifts them by slice_start so everything lines up with the file."""
    start = to_sec(t_from) if t_from else 0.0
    end = to_sec(t_to) if t_to else start + 7200
    if duration:
        end = min(end, duration)
    if end - start < 60:
        raise SystemExit("The --from/--to slice is shorter than a minute.")
    return start, end


def download_vod(url, session, cfg, height=1080, section=None):
    """Download the VOD (or only section=(start_s, end_s)) into the session. Returns the video path."""
    exts = (".mp4", ".mkv", ".ts", ".webm")
    vids = [v for v in session.glob("vod.*") if v.suffix in exts]
    sj = session / "session.json"
    if vids and section is not None:
        old = read_json(sj).get("slice_start") if sj.exists() else None
        if old != section[0]:
            raise SystemExit(f"{vids[0].name} already exists here and is not the {fmt_ts(section[0])} slice. "
                             f"Delete it (and session.json), then run this again.")
    if not vids:
        if section is not None:
            log(f"Downloading only {fmt_ts(section[0])} - {fmt_ts(section[1])} "
                f"({fmt_ts(section[1] - section[0])}) at up to {height}p...")
        else:
            log(f"Downloading video (up to {height}p)... this can take a while for long streams")
        cmd = vod_download_cmd(url, session / "vod.%(ext)s", cfg.get("vod_limit_rate", "1.5M"), height, section)
        for attempt in range(1, 9):
            if subprocess.run(cmd).returncode == 0:
                break
            if attempt == 8:
                raise SystemExit("Video download kept failing (network drops Twitch). "
                                 "Try a VPN / Cloudflare WARP, then run the same command again.")
            log(f"Download interrupted (attempt {attempt}/8), retrying in 15 s... (progress is kept)")
            time.sleep(15)
        vids = [v for v in session.glob("vod.*") if v.suffix in exts]
    return vids[0]


def vod_session(url, cfg):
    """Session folder for a VOD URL without printing anything. -> (info, session)"""
    info = json.loads(run(["yt-dlp", "-J", "--no-warnings", url]).stdout)
    site = info.get("extractor_key", "site").lower()
    session = Path(cfg["data_dir"]) / "vod" / f"{site}-{info['id']}"
    session.mkdir(parents=True, exist_ok=True)
    return info, session
