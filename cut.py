"""Make clips from a session after the fact, or re-render one clip.

    python cut.py <session_dir> --all                 clip every detected moment
    python cut.py <session_dir> --id 7 [--force]      clip one moment (--force ignores the AI's reject)
    python cut.py --rerender <clip_dir>               re-render with an edited/pasted judge.json
"""
import argparse
import json
from pathlib import Path

from common import load_config, log, read_json


def load_candidates(session):
    session = Path(session)
    if (session / "candidates.json").exists():
        return read_json(session / "candidates.json")
    out = []
    p = session / "candidates.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--id", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--rerender")
    ap.add_argument("--judge", help="judge JSON file (default: <clip_dir>/judge.json)")
    args = ap.parse_args()
    cfg = load_config()

    if args.rerender:
        from pipeline import rerender
        rerender(args.rerender, cfg, args.judge)
        return

    if not args.session:
        ap.error("session dir required")
    cands = load_candidates(args.session)
    if args.id is not None:
        cands = [c for c in cands if c["id"] == args.id]
    elif not args.all:
        for c in cands:
            print(f"#{c['id']:03d}  H={c['h_score']}  chat={c['chat_top']}")
        print("Use --all or --id N")
        return

    from pipeline import process_candidate
    for c in cands:
        try:
            process_candidate(args.session, c, cfg, force=args.force)
        except Exception as e:
            log(f"#{c['id']:03d} failed: {e}")


if __name__ == "__main__":
    main()
