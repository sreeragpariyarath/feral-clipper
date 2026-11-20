"""Candidate -> transcript -> Claude judge -> rendered 9:16 clip."""
from pathlib import Path

from clipper.common import fmt_ts, log, read_json, write_json
from clipper.detect.discovery import analyze as discover
from clipper.ai.judge import judge, validate
from clipper.render.media import detect_black, extract_audio, extract_window, render_clip
from clipper.ai.transcribe import plain_text, transcribe


def clip_words(words, start_s, end_s):
    out = []
    for w in words:
        if w["e"] <= start_s or w["s"] >= end_s:
            continue
        out.append({"w": w["w"], "s": round(w["s"] - start_s, 2), "e": round(w["e"] - start_s, 2)})
    return out


def process_candidate(session_dir, cand, cfg, force=False):
    session_dir = Path(session_dir)
    meta = read_json(session_dir / "session.json")
    clip_dir = session_dir / "clips" / f"{cand['id']:03d}"
    clip_dir.mkdir(parents=True, exist_ok=True)
    write_json(clip_dir / "candidate.json", cand)

    media, offset = extract_window(session_dir, cand["win_start"], cand["win_end"], clip_dir)
    window_len = cand["win_end"] - cand["win_start"]

    wav = clip_dir / "window.wav"
    extract_audio(media, offset, window_len, wav)
    tr = transcribe(wav, cfg)
    write_json(clip_dir / "transcript.json", tr)
    wav.unlink(missing_ok=True)

    disc = None
    try:
        disc = discover(media, offset, window_len, tr["words"], cand, cfg, clip_dir,
                        meta.get("channel", ""))
    except Exception as e:  # discovery is a bonus, never block a clip on it
        log(f"   discovery check failed: {e}")
    if disc:
        write_json(clip_dir / "discovery.json", disc)
        v = disc.get("vision") or {}
        cand = dict(cand, discovery={"text": disc["text"], "seen": v.get("what"), "kind": v.get("kind"),
                                     "strength": disc["strength"], "blocked": disc["blocked"]})

    j = judge(cand, tr["words"], window_len, cfg, meta.get("channel", ""), clip_dir,
              brief=cfg.get("campaign_brief"))
    apply_discovery(j, disc, cfg)
    final = round(min(1.0, 0.4 * cand["h_score"] + 0.6 * j["score"] / 10 + j.get("disc_bonus", 0)), 3)
    j["final_score"] = final
    write_json(clip_dir / "judge.json", j)

    rejected = (not j.get("standalone", True)) or bool(j.get("violations")) \
        or final < cfg["decide"]["render_min"]
    label = f"#{cand['id']:03d} @ {fmt_ts(cand['peak_t'] - meta.get('t0', 0))}"
    if rejected and not force:
        log(f"{label} skipped (final {final}, score {j['score']}): {j.get('reasons', '')}")
        write_json(clip_dir / "status.json", {"status": "skipped", "final": final})
        return clip_dir

    return render_from_judge(clip_dir, media, offset, tr["words"], j, cfg, label)


def apply_discovery(j, disc, cfg):
    """Fold discovery into the judge result: bonus score, blocked content, 'I found X' hook."""
    if not disc:
        return j
    j["disc_bonus"] = round(cfg.get("discovery", {}).get("bonus", 0.12) * disc["strength"], 3)
    for b in disc.get("blocked", []):
        if b not in j.setdefault("violations", []):
            j["violations"].append(b)
    v = disc.get("vision") or {}
    if v.get("discovery") and v.get("hook") and disc["strength"] >= 0.6:
        j["hook_text"] = v["hook"][:60]
        j.setdefault("title", v["hook"])
    return j


def trim_black(media, offset, start, end):
    """Cut black screens off the start/end. Returns (start, end) or None if mostly black."""
    dur = end - start
    black = detect_black(media, offset + start, dur)
    if sum(b - a for a, b in black) > 0.4 * dur:
        return None
    new_start, new_end = start, end
    for a, b in black:               # a, b are relative to the original start
        if a <= 0.5:
            new_start = max(new_start, start + b)
        elif b >= dur - 0.5:
            new_end = min(new_end, start + a)
    if new_end - new_start < 8:
        return None
    return round(new_start, 2), round(new_end, 2)


def render_from_judge(clip_dir, media, offset, words, j, cfg, label=""):
    start, end = j["start_s"], j["end_s"]
    trimmed = trim_black(media, offset, start, end)
    if trimmed is None:
        log(f"{label} skipped: mostly black screen (streamer on a break/scene switch)")
        write_json(Path(clip_dir) / "status.json", {"status": "skipped", "reason": "black"})
        return clip_dir
    if trimmed != (start, end):
        log(f"{label} trimmed black screen: {start:.1f}-{end:.1f}s -> {trimmed[0]:.1f}-{trimmed[1]:.1f}s")
    start, end = trimmed
    cw = clip_words(words, start, end)
    render_clip(media, offset + start, end - start, clip_dir, cfg, cw,
                hook=j.get("hook_text") or None, emphasize=j.get("emphasize", []))
    cap = cfg.get("campaign_caption")      # required caption + hashtags some campaigns demand
    if cap:
        (Path(clip_dir) / "post.txt").write_text(
            f"TITLE (YouTube Shorts):\n{(j.get('title') or '').strip()}\n\nCAPTION (all platforms):\n{cap}\n",
            encoding="utf-8")
    strong = j.get("final_score", 0) >= cfg["decide"]["strong_min"]
    write_json(clip_dir / "status.json", {"status": "ready", "strong": strong,
                                          "final": j.get("final_score")})
    tag = "STRONG" if strong else "review"
    log(f"{label} clip ready [{tag}] {end - start:.0f}s  score {j['score']}/10  "
        f"title: {j.get('title') or '-'}  -> {clip_dir / 'clip.mp4'}")
    if j.get("source") == "heuristic":
        log(f"   (no API key: paste {clip_dir / 'prompt.txt'} into Claude, save reply as judge.json, "
            f"then: python cut.py --rerender \"{clip_dir}\")")
    return clip_dir


def rerender(clip_dir, cfg, judge_file=None):
    clip_dir = Path(clip_dir)
    session_dir = clip_dir.parent.parent
    cand = read_json(clip_dir / "candidate.json")
    tr = read_json(clip_dir / "transcript.json")
    jf = Path(judge_file) if judge_file else clip_dir / "judge.json"
    raw = jf.read_text(encoding="utf-8")
    from clipper.ai.judge import parse_json
    meta = read_json(session_dir / "session.json")
    media, offset = extract_window(session_dir, cand["win_start"], cand["win_end"], clip_dir)
    window_len = cand["win_end"] - cand["win_start"]
    j = validate(parse_json(raw), window_len)
    dj = clip_dir / "discovery.json"
    apply_discovery(j, read_json(dj) if dj.exists() else None, cfg)
    j["final_score"] = round(min(1.0, 0.4 * cand["h_score"] + 0.6 * j["score"] / 10
                                 + j.get("disc_bonus", 0)), 3)
    j.setdefault("source", "manual")
    write_json(clip_dir / "judge.json", j)
    return render_from_judge(clip_dir, media, offset, tr["words"], j, cfg,
                             f"#{cand['id']:03d}")
