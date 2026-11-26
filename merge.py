"""Merge the finders: chat/audio moments (vod.py) + frame-scan moments (scan.py) -> one ranked list -> clips.

Why: vod.py finds moments from chat and loud audio, scan.py finds them from the picture. Until now they
never met, so a silent crash and a loud chat spike were two separate runs. This joins them.

Steps (all on one downloaded VOD session, e.g. data\\vod\\twitchvod-v2933231152):

  1. python vod.py <vod_url> --download-only        # chat replay + candidates.json + full VOD, no clips
  2. python scan.py <session> --list --top 15 --gap 45 --min 5     # writes scan\\moments.json, spends nothing extra if cached
  3. python merge.py <session> --list               # see the merged ranking
  4. python merge.py <session> --top 8              # render the best 8

Merge rules:
  * A scan moment joins a chat/audio candidate when the frame time falls from 45 s before to 10 s after the
    candidate's peak (chat reacts 5-20 s AFTER the moment, so the picture comes first).
  * When both finders agree, the score gets a small boost (+0.10), not an automatic win. Loud things are often
    visual things, so the two signals are related.
  * Scan-only moments (silent action) keep the scan's own score.
  * Close moments are de-duplicated: the better one is kept (default gap 45 s).
Re-running is safe: moments already rendered (same peak within 6 s) are skipped.
"""
import argparse
from pathlib import Path

from clipper.common import duration_of, fmt_ts, load_config, log, read_json, write_json

AGREE_BOOST = 0.10
MATCH_BEFORE = 45        # scan frame may be this many seconds before the chat peak
MATCH_AFTER = 10         # ... or this many after
SCAN_PRE, SCAN_POST = 40, 30
ID_BASE = 700            # merged clips live in clips\701, 702, ... (chat 001+, scan 501+, manual 801+)


def scan_h(r):
    """Same mapping scan.py uses when it renders its own moments."""
    return round(min(0.95, 0.5 + r["score"] / 20), 2)


def merge(chat, scan, dur=None, gap=45):
    """chat: candidates.json list. scan: scan/moments.json list. Returns list sorted by score, best first."""
    used = set()
    out = []
    for c in chat:
        lo, hi = c["peak_t"] - MATCH_BEFORE, c["peak_t"] + MATCH_AFTER
        hits = [i for i, r in enumerate(scan) if lo <= r["t"] <= hi]
        used.update(hits)
        m = dict(c, sources=["chat"])
        if hits:
            best = max((scan[i] for i in hits), key=lambda r: r["score"])
            m["sources"] = ["chat", "scan"]
            m["h_score"] = round(min(0.98, max(c["h_score"], scan_h(best)) + AGREE_BOOST), 3)
            m["scan"] = {"kind": best["kind"], "what": best["what"], "score": best["score"],
                         "at_s": round(best["t"] - c["win_start"], 1)}
        out.append(m)
    for i, r in enumerate(scan):
        if i in used:
            continue
        start = max(0, r["t"] - SCAN_PRE)
        end = r["t"] + SCAN_POST
        out.append({
            "peak_t": r["t"], "win_start": start,
            "win_end": min(dur, end) if dur else end,
            "h_score": scan_h(r), "signals": {"scan": r["kind"]}, "chat_top": {}, "chat_samples": [],
            "sources": ["scan"],
            "scan": {"kind": r["kind"], "what": r["what"], "score": r["score"],
                     "at_s": round(r["t"] - start, 1)},
        })
    out.sort(key=lambda m: m["h_score"], reverse=True)
    kept = []
    for m in out:                               # greedy de-dupe: best first, drop anything too close
        if all(abs(m["peak_t"] - k["peak_t"]) >= gap for k in kept):
            kept.append(m)
    return kept


def shift_chat(chat, s0, dur=None):
    """Move chat/audio candidates from VOD time into slice time; drop the ones outside the slice."""
    out = []
    for c in chat:
        peak = c["peak_t"] - s0
        if peak < 0 or (dur and peak > dur):
            continue
        out.append(dict(c, peak_t=peak, win_start=max(0.0, c["win_start"] - s0),
                        win_end=min(dur, c["win_end"] - s0) if dur else c["win_end"] - s0))
    return out


def describe(m):
    src = "+".join(m["sources"])
    bits = []
    if m.get("chat_top"):
        bits.append("chat " + ",".join(f"{k}:{v}" for k, v in m["chat_top"].items()))
    if m.get("scan"):
        bits.append(f"saw {m['scan']['kind']}: {m['scan']['what']}")
    return f"{fmt_ts(m['peak_t'])}  H={m['h_score']:.2f}  [{src:<9}] " + " | ".join(bits)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", help=r"e.g. data\vod\twitchvod-v2933231152")
    ap.add_argument("--top", type=int, default=8, help="how many merged moments to render (default 8)")
    ap.add_argument("--gap", type=float, default=45, help="min seconds between moments (default 45)")
    ap.add_argument("--list", action="store_true", help="show the merged ranking, do not render")
    args = ap.parse_args()

    session = Path(args.session)
    cpath, spath = session / "candidates.json", session / "scan" / "moments.json"
    chat = read_json(cpath) if cpath.exists() else []
    scan = read_json(spath) if spath.exists() else []
    if not cpath.exists():
        log("No candidates.json (chat/audio finder). Run: python vod.py <url> --download-only")
    if not spath.exists():
        log("No scan\\moments.json (frame scan). Run: python scan.py <session> --list --top 15 --gap 45 --min 5")
    if not chat and not scan:
        raise SystemExit("Nothing to merge.")

    dur = None
    sj = session / "session.json"
    meta = read_json(sj) if sj.exists() else None
    if meta and meta.get("file"):
        try:
            dur = duration_of(session / meta["file"])
        except Exception:
            dur = None
    s0 = float((meta or {}).get("slice_start") or 0)
    if meta and meta.get("slice_start") is not None:
        # the file is only a slice of the VOD; chat moments are in VOD time, scan moments in file time.
        # Filter even when the slice starts at 0, or moments past the end of the file get cut.
        chat = shift_chat(chat, s0, dur)
        log(f"Downloaded slice starts at {fmt_ts(s0)} of the VOD; times below are in the slice "
            f"(VOD time = shown time + {fmt_ts(s0)})")
    merged = merge(chat, scan, dur, args.gap)
    both = sum(1 for m in merged if len(m["sources"]) > 1)
    log(f"chat/audio: {len(chat)}   scan: {len(scan)}   merged: {len(merged)} ({both} found by both)")
    top = merged[:args.top]
    for m in top:
        log("  " + describe(m))
    write_json(session / "merged.json", merged)
    if args.list:
        log("List only. Render with: python merge.py <session> --top 8")
        return

    if not meta or not meta.get("file"):
        raise SystemExit("No downloaded VOD in this session. Run: python vod.py <url> --download-only")
    cfg = load_config()
    from clipper.render.media import campaign_overlay
    try:
        campaign_overlay(cfg)                    # fail now, not after Whisper and Claude have run
    except RuntimeError as e:
        raise SystemExit(str(e))
    from clipper.pipeline import process_candidate
    clips = session / "clips"
    done = {}
    for d in clips.glob("7[0-9][0-9]"):
        try:
            done[round(read_json(d / "candidate.json")["peak_t"])] = d
        except Exception:
            pass
    next_id = max([int(d.name) for d in done.values()] + [ID_BASE]) + 1
    for m in sorted(top, key=lambda m: m["peak_t"]):
        prev = next((d for t, d in done.items() if abs(t - m["peak_t"]) <= 6 and (d / "status.json").exists()), None)
        if prev:
            log(f"{fmt_ts(m['peak_t'])} already done in clips\\{prev.name}, skipping")
            continue
        c = dict(m, id=next_id)
        next_id += 1
        try:
            process_candidate(session, c, cfg)
        except Exception as e:
            log(f"#{c['id']} failed: {e}")
    log(f"Done. Clips are in {clips}  (folders 701, 702, ...)")


if __name__ == "__main__":
    main()
