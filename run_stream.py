"""One command for many finished streams: run every step, resume after failures, write a review list.

    python run_stream.py <vod_url> [<vod_url> ...] [--top 10] [--scan]
    python run_stream.py --queue queue.txt [--top 10] [--scan]      # one URL per line, # = comment
    python run_stream.py --queue queue.txt --force                  # redo streams already marked done

Per stream it runs the existing scripts in order (no logic is duplicated here):
  default:  vod.py <url> --top N                         chat/audio moments -> clips
  --scan:   vod.py <url> --download-only                 full VOD + chat/audio candidates
            scan.py <session> --list --top 15 --gap 45 --min 5
            merge.py <session> --top N                   picture + chat/audio moments -> clips
Then it writes REVIEW.md in the session folder: every clip, best first, with title, score and reason.

A stream that fails is logged and the queue moves on. A stream marked done is skipped next time,
so re-running after a crash only redoes the stream that broke.
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from clipper.common import load_config, log, read_json, write_json
from clipper.sources import vod_source as vs

HERE = Path(__file__).resolve().parent


def run_script(name, *args):
    cmd = [sys.executable, str(HERE / name), *args]
    log("$ " + " ".join(f'"{a}"' if " " in a else a for a in cmd[1:]))
    return subprocess.run(cmd).returncode == 0


def _has_twitch_cli(cfg):
    import shutil
    cli = cfg["twitch_downloader_cli"]
    return shutil.which(cli) is not None or Path(cli).exists() or (HERE / f"{cli}.exe").exists()


def write_review(session):
    """REVIEW.md: all clips in the session, ready ones first, best score first."""
    rows = []
    for d in sorted((session / "clips").glob("*")):
        st_path = d / "status.json"
        if not st_path.exists():
            continue
        st = read_json(st_path)
        j = read_json(d / "judge.json") if (d / "judge.json").exists() else {}
        rows.append({
            "dir": d.name,
            "status": st.get("status", "?"),
            "final": st.get("final") or j.get("final_score") or 0,
            "strong": bool(st.get("strong")),
            "title": (j.get("title") or "").strip(),
            "hook": (j.get("hook_text") or "").strip(),
            "reason": (j.get("reasons") or st.get("reason") or "").strip(),
            "clip": d / "clip.mp4",
            "post": d / "post.txt",
        })
    rows.sort(key=lambda r: (r["status"] != "ready", not r["strong"], -float(r["final"])))
    ready = sum(1 for r in rows if r["status"] == "ready")
    lines = [f"# Review: {session.name}", "",
             f"{ready} clips ready, {len(rows) - ready} skipped. Keep the ones you like; "
             "skipped folders can be forced with `python cut.py <session> --id N --force`.", ""]
    lines += ["| Clip | Status | Final | Title | Why | File |", "|---|---|---|---|---|---|"]
    for r in rows:
        tag = "STRONG" if r["strong"] else r["status"]
        title = (r["title"] or "-").replace("|", "/")
        why = (r["reason"] or "-").replace("|", "/").replace("\n", " ")[:160]
        file = f"clips/{r['dir']}/clip.mp4" if r["clip"].exists() else "-"
        lines.append(f"| {r['dir']} | {tag} | {r['final']} | {title} | {why} | `{file}` |")
    lines += ["", "Captions and titles for posting are in each folder's `post.txt` (when the campaign needs them)."]
    (session / "REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ready


def process_url(url, args, cfg, log_path):
    state_path = None
    info = session = None
    last_err = None
    for attempt in range(1, 11):                 # Twitch drops connections often: retry like vod.py does
        try:
            info, session = vs.vod_session(url, cfg)
            break
        except Exception as e:
            last_err = e
            log(f"could not read video info (try {attempt}/10): {str(e).splitlines()[0][:120]}; retrying in 10 s")
            time.sleep(10)
    if info is None:
        return f"FAILED ({url}): could not read the video info after 10 tries: {last_err}"
    state_path = session / "run_state.json"
    state = read_json(state_path) if state_path.exists() else {}
    if state.get("done") and not args.force:
        return f"skipped (already done): {session.name}"

    log(f"=== {session.name}: {info.get('title', '')}")
    # Twitch chat replay needs TwitchDownloaderCLI. Without it, use loud-audio detection instead.
    chat_ok = "twitch" not in info.get("extractor_key", "").lower() or _has_twitch_cli(cfg)
    audio_flags = [] if chat_ok else ["--audio"]
    if not chat_ok:
        log("TwitchDownloaderCLI not found -> using loud-audio detection (no chat replay)")
    mode = "scan" if args.scan else ("chat" if chat_ok else "audio")
    is_slice = read_json(session / "session.json").get("slice_start") is not None if (session / "session.json").exists() else False
    if is_slice:
        # A --from/--to download: the file is a slice, so cut with merge.py (it shifts the times for us).
        log("This session is a downloaded slice -> rendering with merge.py")
        steps = []
        if not (session / "candidates.json").exists():
            steps.append(("vod.py candidates", ["vod.py", url, "--download-only"] + audio_flags))
        if args.scan:
            steps.append(("scan", ["scan.py", str(session), "--list", "--top", "15", "--gap", "45", "--min", "5"]))
        steps.append(("merge + render", ["merge.py", str(session), "--top", str(args.top)]))
    elif args.scan:
        steps = [
            ("vod.py download", ["vod.py", url, "--download-only"] + audio_flags),
            ("scan", ["scan.py", str(session), "--list", "--top", "15", "--gap", "45", "--min", "5"]),
            ("merge + render", ["merge.py", str(session), "--top", str(args.top)]),
        ]
    else:
        steps = [("vod.py render", ["vod.py", url, "--top", str(args.top)] + audio_flags)]

    for label, cmd in steps:
        if not run_script(*cmd):
            write_json(state_path, {"done": False, "failed_at": label, "mode": mode,
                                    "when": datetime.now().isoformat(timespec="seconds")})
            return f"FAILED at '{label}': {session.name}"

    ready = write_review(session)
    write_json(state_path, {"done": True, "mode": mode, "ready": ready,
                            "when": datetime.now().isoformat(timespec="seconds")})
    return f"done: {session.name} -> {ready} clips ready, see {session / 'REVIEW.md'}"


def read_queue(path):
    urls = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="VOD / YouTube video URLs")
    ap.add_argument("--queue", help="text file with one URL per line")
    ap.add_argument("--top", type=int, default=10, help="clips to render per stream (default 10)")
    ap.add_argument("--scan", action="store_true", help="also use the picture scan (slower, finds silent moments)")
    ap.add_argument("--force", action="store_true", help="redo streams already marked done")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.queue:
        urls += read_queue(args.queue)
    if not urls:
        ap.error("give at least one URL or --queue file")

    cfg = load_config()
    log_path = Path(cfg["data_dir"]) / "run_log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for url in urls:
        result = process_url(url, args, cfg, log_path)
        results.append(result)
        log(result)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')}  {url}  {result}\n")

    log("=== Summary")
    for r in results:
        log("  " + r)


if __name__ == "__main__":
    main()
