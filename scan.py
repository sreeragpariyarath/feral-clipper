"""Frame scan: find the moments in a downloaded VOD where something is happening ON SCREEN.

Why: voice/chat detection picks talking moments. This looks at the picture instead.

  1. ffmpeg grabs one small frame every N seconds (keyframes only, so it is fast)
  2. frames are tiled into contact sheets (12 per image) and Claude scores each cell
     using the GTA 6 knowledge list (chase, crash, animal, helicopter, new thing...)
  3. best moments (spaced apart, safe-to-post only) are cut, transcribed, judged and rendered
     by the normal pipeline.

Local mode (after `python setup_models.py`): CLIP + PANNs on your GPU score every frame for free,
then Claude only double-checks the best 36 (3 calls). Without the models it falls back to Claude-only.

Usage (from C:\\clipper\\gta-clipper, venv active, ANTHROPIC_API_KEY set):
  python scan.py data\\vod\\twitchvod-v2933231152 --dry          # just count calls, spend nothing
  python scan.py data\\vod\\twitchvod-v2933231152 --list         # scan + show moments, no render
  python scan.py data\\vod\\twitchvod-v2933231152                # scan + render the top 6
  python scan.py <session> --from 3:30:00 --to 4:30:00 --top 4   # only part of the stream
Re-running is safe: finished sheets are cached in <session>\\scan\\results.json.
"""
import argparse
import base64
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import fmt_ts, load_config, log, need, read_json, run, write_json

CELL_W, CELL_H, COLS = 384, 216, 4
BLOCK = {"cutscene", "menu_or_loading", "suggestive", "gore"}

SCAN_SYSTEM = """You are scouting GTA 6 gameplay for short viral clips. You get ONE contact sheet: a grid of \
numbered screenshots taken a few seconds apart from a streamer's live stream (game footage, sometimes with a \
facecam or chat overlay). Score every numbered cell for how clippable the PICTURE is.

Score 0-10:
 9-10 spectacular or rare: police chase with helicopters, big crash/explosion, a wild animal or creature, plane \
crash, a brand-new or unusual thing, boat/hovercraft chaos, something clearly on the 'known GTA 6 things' list.
 6-8 exciting action: driving fast, shootout, getting chased, fighting, stunt, funny physics, interesting new vehicle.
 3-5 mildly interesting scenery or activity.
 0-2 boring: walking, menus, maps, inventory, loading, phone, shop screens, plain dialogue, talking to the camera.

Set flags (true/false lists) for anything that must not be posted: "cutscene" (scripted story scene or \
letterboxed cinematic), "menu_or_loading", "suggestive" (nudity, underwear, strip clubs, sexual content), "gore".

Reply with ONLY JSON, no prose:
{"cells":[{"cell":1,"score":7,"kind":"chase|crash|animal|vehicle|shootout|stunt|scenery|new_unlisted|other|none",\
"what":"max 12 words, what is visible","flags":[]}]}
Include only cells with score >= 3 OR any flag. Omit boring cells."""


# ---------------------------------------------------------------- frames
def video_of(session):
    for ext in (".mp4", ".mkv", ".ts", ".webm"):
        v = session / f"vod{ext}"
        if v.exists():
            return v
    raise SystemExit(f"No vod.mp4 in {session}. Run vod.py on the VOD first (it downloads the full video).")


def duration_of(video):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(video)]).stdout.strip()
    return float(out)


def to_sec(v):
    p = [float(x) for x in v.split(":")]
    while len(p) < 3:
        p.insert(0, 0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def grab_frames(video, out_dir, t_from, t_to, every):
    """One small frame every `every` seconds. Keyframes only = decodes ~1/100 of the video.
    Returns (frame_paths, frame_times) with the REAL time of each frame (read from ffmpeg)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = out_dir / "times.json"
    want = int((t_to - t_from) // every) + 1
    have = sorted(out_dir.glob("f_*.jpg"))
    if meta.exists():
        m = read_json(meta)
        if m.get("key") == [t_from, t_to, every] and len(m["times"]) == len(have) > 0:
            log(f"Frames already extracted ({len(have)})")
            return have, m["times"]
    for f in have:
        f.unlink()
    log(f"Extracting ~{want} frames (keyframes only, one every {every:.0f}s)... a few minutes for a long VOD")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "info", "-skip_frame", "nokey",
           "-ss", f"{t_from:.2f}", "-i", str(video), "-t", f"{t_to - t_from:.2f}",
           "-vf", f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{every - 0.5})',showinfo,"
                  f"scale={CELL_W}:{CELL_H}:force_original_aspect_ratio=decrease,"
                  f"pad={CELL_W}:{CELL_H}:(ow-iw)/2:(oh-ih)/2",
           "-fps_mode", "vfr", "-q:v", "5", str(out_dir / "f_%05d.jpg")]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError("ffmpeg frame extraction failed:\n" + "\n".join(res.stderr.splitlines()[-10:]))
    pts = [float(x) for x in re.findall(r"pts_time:\s*([0-9.]+)", res.stderr)]
    have = sorted(out_dir.glob("f_*.jpg"))
    if len(pts) >= len(have):
        pts = pts[:len(have)]
    else:
        log(f"   warning: {len(have)} frames but {len(pts)} timestamps; using estimated times")
        pts = [i * every for i in range(len(have))]
    times = [round(t_from + p, 2) for p in pts]
    write_json(meta, {"key": [t_from, t_to, every], "times": times})
    return have, times


# ---------------------------------------------------------------- sheets
def make_sheet(frames, times, path):
    rows = math.ceil(len(frames) / COLS)
    sheet = Image.new("RGB", (COLS * CELL_W, rows * CELL_H), (0, 0, 0))
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
        except Exception:
            font = ImageFont.load_default()
    d = ImageDraw.Draw(sheet)
    for i, fp in enumerate(frames):
        im = Image.open(fp).convert("RGB")
        x, y = (i % COLS) * CELL_W, (i // COLS) * CELL_H
        sheet.paste(im, (x, y))
        d.rectangle((x, y, x + 54, y + 40), fill=(0, 0, 0))
        d.text((x + 6, y + 2), str(i + 1), fill=(255, 255, 0), font=font)
        d.rectangle((x, y, x + CELL_W - 1, y + CELL_H - 1), outline=(60, 60, 60))
    sheet.save(path, "JPEG", quality=78)
    return path


# ---------------------------------------------------------------- Claude
def parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in reply")
    return json.loads(m.group(0))


def score_sheet(client, model, sheet_path, n_cells, know_text, call=None):
    data = base64.b64encode(Path(sheet_path).read_bytes()).decode()
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
        {"type": "text", "text": f"This sheet has cells 1 to {n_cells}. Return the JSON."},
    ]
    last = None
    for _ in range(3):
        try:
            if call:
                text = call(content)
            else:
                resp = client.messages.create(
                    model=model, max_tokens=1500,
                    system=[{"type": "text", "text": SCAN_SYSTEM + "\n\n" + know_text,
                             "cache_control": {"type": "ephemeral"}}],
                    messages=[{"role": "user", "content": content}])
                text = "".join(b.text for b in resp.content if b.type == "text")
            return parse_json(text).get("cells", [])
        except Exception as e:
            last = e
    log(f"   sheet failed after 3 tries: {last}")
    return None


# ---------------------------------------------------------------- pick moments
def pick(rows, min_score, top, min_gap):
    """rows: [{t, score, kind, what, flags}]. Neighbouring high cells = sustained action -> small boost."""
    rows = sorted(rows, key=lambda r: r["t"])
    ts = [r["t"] for r in rows]
    diffs = [b - a for a, b in zip(ts, ts[1:]) if b - a > 1]
    step = min(diffs) if diffs else None

    def ok(r):
        return r["score"] >= min_score and not (set(r.get("flags") or []) & BLOCK)

    good = []
    for i, r in enumerate(rows):
        if not ok(r):
            continue
        boost = 0
        if step:
            for j in (i - 1, i + 1):
                if 0 <= j < len(rows) and abs(rows[j]["t"] - r["t"]) <= step * 1.5 and ok(rows[j]):
                    boost += 1
        good.append(dict(r, rank=r["score"] + 0.5 * boost))
    good.sort(key=lambda r: r["rank"], reverse=True)
    chosen = []
    for r in good:
        if all(abs(r["t"] - c["t"]) >= min_gap for c in chosen):
            chosen.append(r)
        if len(chosen) >= top:
            break
    chosen.sort(key=lambda r: r["t"])
    return chosen


# ---------------------------------------------------------------- main
def local_stage(session, scan_dir, video, frames, ftimes, t_from, t_to, rescan):
    """Open-source models on your GPU: CLIP action/novelty + PANNs sounds. Free. Returns per-frame rows."""
    import numpy as np
    import local_models as lm
    cache = scan_dir / "local.json"
    key = [len(frames), ftimes[0] if ftimes else 0, ftimes[-1] if ftimes else 0, lm.PANNS_CKPT.exists()]
    if cache.exists() and not rescan:
        c = read_json(cache)
        if c.get("key") == key:
            log("Local model scores already computed (cached)")
            return c["rows"], c.get("audio", [])

    log(f"CLIP: looking at {len(frames)} frames on your GPU...")
    clip = lm.Clip()
    emb = clip.embed([str(f) for f in frames])
    vis = clip.score(emb)
    nov = lm.novelty(emb, ftimes, memory=lm.load_memory())
    log(f"   CLIP done on {clip.dev}")

    audio = []
    try:
        src = session / "audio.mp4" if (session / "audio.mp4").exists() else video
        log(f"PANNs: listening to {fmt_ts(t_to - t_from)} of audio ({src.name}) for sirens, gunfire, crashes...")
        tagger = lm.AudioTagger()
        audio = tagger.tag_file(src, t_from, t_to, progress=lambda s: print(
            f"\r   heard {fmt_ts(s)} / {fmt_ts(t_to - t_from)}", end="", flush=True))
        print()
        log(f"   PANNs done on {tagger.dev}")
    except Exception as e:
        log(f"   audio model skipped ({type(e).__name__}); using CLIP only. Put Cnn14_mAP=0.431.pth in models\\ to add sound.")

    def pct(xs):                         # rank -> 0..1, robust to each model's own scale
        xs = np.asarray(xs, dtype=float)
        return (xs.argsort().argsort() / max(1, len(xs) - 1)) if len(xs) else xs

    act = pct([v["action"] - v["boring"] for v in vis])
    novp = pct(nov)
    rows = []
    for i, (f, t, v) in enumerate(zip(frames, ftimes, vis)):
        a = lm.audio_at(audio, t) if audio else {"score": 0.0, "top": {}}
        s = 0.5 * act[i] + 0.25 * novp[i] + 0.25 * min(1.0, a["score"] * 1.5)
        if v["best_kind"] == "unsafe" or v["unsafe"] > 0.35:
            s *= 0.2
        if v["best_kind"] == "boring" and v["boring"] > 0.6:
            s *= 0.5
        rows.append({"i": i, "t": t, "local": round(float(s), 3), "clip": v["best"], "clip_kind": v["best_kind"],
                     "novelty": round(float(nov[i]), 3), "sound": list(a["top"].keys())[:3],
                     "sound_score": a["score"], "unsafe": round(v["unsafe"], 3)})
    write_json(cache, {"key": key, "rows": rows, "audio": audio})
    lm.save_memory(emb)
    return rows, audio


def shortlist(rows, n, gap=30):
    out = []
    for r in sorted(rows, key=lambda r: -r["local"]):
        if all(abs(r["t"] - o["t"]) >= gap for o in out):
            out.append(r)
        if len(out) >= n:
            break
    return sorted(out, key=lambda r: r["t"])


def models_ready():
    try:
        import open_clip  # noqa: F401
        import panns_inference.models  # noqa: F401
        from local_models import MODELS
        return any(MODELS.glob("clip/**/open_clip_model.safetensors"))
    except Exception:
        return False


def main():
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
    args = ap.parse_args()

    need("ffmpeg"); need("ffprobe")
    cfg = load_config()
    session = Path(args.session)
    video = video_of(session)
    dur = duration_of(video)
    t_from = to_sec(args.t_from) if args.t_from else 0.0
    t_to = min(dur, to_sec(args.t_to)) if args.t_to else dur

    if args.at:                                  # manual: you found the moment, just cut + judge + render it
        from pipeline import process_candidate
        clips = session / "clips"
        nid = max([int(d.name) for d in clips.glob("8[0-9][0-9]")] + [850]) + 1
        for a in args.at:
            t = to_sec(a)
            c = {"id": nid, "peak_t": t, "win_start": max(0, t - args.len * 0.6),
                 "win_end": min(dur, t + args.len * 0.4), "h_score": 0.9, "manual": True,
                 "signals": {"manual": True}, "chat_top": {}, "chat_samples": []}
            nid += 1
            log(f"#{c['id']}: clipping around {fmt_ts(t)} ({fmt_ts(c['win_start'])} - {fmt_ts(c['win_end'])})")
            try:
                process_candidate(session, c, cfg, force=True)
            except Exception as e:
                log(f"#{c['id']} failed: {e}")
        log(f"Done. Clips are in {clips}")
        return

    local = not args.claude_only and models_ready()
    if not args.claude_only and not local:
        log("Open-source models not installed yet (run: python setup_models.py). Using Claude for every frame.")
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
    frames, ftimes = grab_frames(video, scan_dir / f"frames_{int(every)}s", t_from, t_to, every)

    # ---- which frames go to Claude
    if local:
        lrows, _ = local_stage(session, scan_dir, video, frames, ftimes, t_from, t_to, args.rescan)
        best = shortlist(lrows, args.shortlist)
        log("Top frames by the local models:")
        for r in sorted(best, key=lambda r: -r["local"])[:10]:
            snd = (" + " + ", ".join(r["sound"])) if r["sound"] else ""
            log(f"  {fmt_ts(r['t'])}  {r['local']:.2f}  {r['clip']}{snd}")
        sel = [r["i"] for r in best]
    else:
        lrows, sel = [], list(range(len(frames)))

    if local and args.no_claude:
        rows = []
        for r in best:
            sc = round(4 + 6 * r["local"], 1)
            if r["clip_kind"] == "boring":
                sc = min(sc, 5.0)            # CLIP thinks it's a menu/talking -> below the default --min
            rows.append({"t": r["t"], "score": sc, "kind": r["clip_kind"],
                         "what": r["clip"] + ((" + " + ", ".join(r["sound"])) if r["sound"] else ""),
                         "flags": ["suggestive"] if r["clip_kind"] == "unsafe" else []})
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY is not set in this terminal. Set it, or use --no-claude.")
        import anthropic
        from discovery import knowledge_text
        client = anthropic.Anthropic()
        know = knowledge_text()
        model = cfg.get("discovery", {}).get("model") or cfg["anthropic_model"]
        results_path = scan_dir / "results.json"
        cache = read_json(results_path) if results_path.exists() and not args.rescan else {}
        (scan_dir / "sheets").mkdir(parents=True, exist_ok=True)
        rows = []
        n_sheets = math.ceil(len(sel) / args.sheet)
        tag = "L" if local else "A"
        for si in range(n_sheets):
            idx = sel[si * args.sheet:(si + 1) * args.sheet]
            times = [ftimes[i] for i in idx]
            key = f"{tag}:{every}:" + ",".join(str(i) for i in idx)
            if key in cache:
                cells = cache[key]
            else:
                sp = make_sheet([frames[i] for i in idx], times, scan_dir / "sheets" / f"{tag}_{si + 1:04d}.jpg")
                cells = score_sheet(client, model, sp, len(idx), know)
                if cells is None:
                    continue
                cache[key] = cells
                write_json(results_path, cache)
            for c in cells:
                try:
                    k = int(c["cell"]) - 1
                    if 0 <= k < len(times):
                        rows.append({"t": times[k], "score": float(c.get("score", 0)), "kind": c.get("kind", "other"),
                                     "what": c.get("what", ""), "flags": c.get("flags") or []})
                except Exception:
                    continue
            print(f"\r  Claude sheet {si + 1}/{n_sheets}   ", end="", flush=True)
        print()

    chosen = pick(rows, args.min, args.top, args.gap)
    blocked = sum(1 for r in rows if set(r["flags"]) & BLOCK)
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

    from pipeline import process_candidate
    clips = session / "clips"
    done = {}                                    # peak time -> existing scan clip folder
    for d in clips.glob("5[0-9][0-9]"):
        try:
            done[round(read_json(d / "candidate.json")["peak_t"])] = d
        except Exception:
            pass
    next_id = max([int(d.name) for d in done.values()] + [500]) + 1
    for r in chosen:
        prev = next((d for t, d in done.items() if abs(t - r["t"]) <= 6 and (d / "status.json").exists()), None)
        if prev:
            log(f"{fmt_ts(r['t'])} already done in clips\\{prev.name}, skipping")
            continue
        c = {"id": next_id, "peak_t": r["t"], "win_start": max(0, r["t"] - 40), "win_end": min(dur, r["t"] + 30),
             "h_score": round(min(0.95, 0.5 + r["score"] / 20), 2), "signals": {"scan": r["kind"]},
             "chat_top": {}, "chat_samples": []}
        next_id += 1
        try:
            process_candidate(session, c, cfg)
        except Exception as e:
            log(f"#{c['id']} failed: {e}")
    log(f"Done. Clips are in {session / 'clips'}  (folders 501, 502, ...)")


if __name__ == "__main__":
    main()
