"""Discovery detection: find 'I found X' moments (new creatures, places, mechanics, secrets).

Two cheap layers, both only run on candidate windows (never the whole stream):
  1. text_discovery(words)   - discovery phrases + creature/place nouns in the transcript
  2. vision_check(...)       - 4 frames from the window sent to Claude: what is on screen,
                               is it a real discovery, is it safe to post (cutscene / suggestive)

Without ANTHROPIC_API_KEY the vision step is skipped; frames + vision_prompt.txt are saved
so you can paste them into claude.ai by hand.
"""
import base64
import json
import os
import re
from pathlib import Path

from clipper.common import ROOT, log, run

# ---- layer 1: transcript -------------------------------------------------------------

# phrases streamers use when they run into something unexpected
PHRASES = [
    r"what is (that|this)", r"what the (hell|heck|fuck)", r"wait,? what", r"no way",
    r"i('ve| have)? never seen", r"didn'?t know (you|that|this)", r"you can (actually|even)",
    r"is (that|this) (new|real)", r"there'?s a\b", r"look at (that|this)", r"oh my (god|gosh)",
    r"hidden", r"secret", r"easter egg", r"found (a|an|the|something)", r"did you (see|know)",
    r"how (is|did) (that|this)", r"they (added|put|put in)", r"first time",
]
# things that make good 'I found X' hooks (creatures, places, mechanics)
NOUNS = [
    "crocodile", "croc", "alligator", "gator", "snake", "shark", "dolphin", "turtle", "bird",
    "flamingo", "dog", "cat", "raccoon", "bear", "deer", "boar", "gator", "manatee", "stingray",
    "cave", "tunnel", "island", "swamp", "bunker", "boat", "plane", "helicopter", "airplane",
    "shop", "store", "mall", "mansion", "beach", "tree", "tower", "bridge", "airport",
    "phone", "mission", "heist", "cop", "police", "wanted", "glitch", "secret", "easter egg",
]

# ---- what is actually in GTA 6 (gta6_knowledge.json, researched + updated over time) ----
def load_knowledge():
    p = ROOT / "gta6_knowledge.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"discoveries": [], "never_post": {"items": []}}


KNOW = load_knowledge()
NOUNS = NOUNS + [w for x in KNOW["discoveries"] for w in x["words"]]
TIER_BONUS = {"hot": 0.15, "rare": 0.25, "common": 0.0}


def knowledge_text():
    lines = [f"- {x['name']} ({x['where']}; {x['tier']}): looks like {x['look']}" for x in KNOW["discoveries"]]
    bad = "; ".join(KNOW.get("never_post", {}).get("items", []))
    return ("KNOWN GTA 6 THINGS PLAYERS ARE SHARING RIGHT NOW (tier: hot = going viral, rare = few clips exist, "
            "common = seen a lot):\n" + "\n".join(lines) +
            "\nAnything notable that is NOT on this list may be brand new - flag it with kind='new_unlisted'.\n"
            "NEVER POST: " + bad)


_PH = re.compile("|".join(PHRASES), re.I)
_NOUN = re.compile(r"\b(" + "|".join(sorted(set(NOUNS), key=len, reverse=True)) + r")s?\b", re.I)


def text_discovery(words):
    """words: [{'w','s','e'}] relative to window start.
    Returns {'score': 0-1, 'phrases': [...], 'nouns': [...], 'first_t': sec or None}."""
    if not words:
        return {"score": 0.0, "phrases": [], "nouns": [], "first_t": None}
    text = " ".join(w["w"] for w in words)
    # map char offset -> time so we can say WHEN the discovery was spoken
    offs, pos = [], 0
    for w in words:
        offs.append((pos, w["s"]))
        pos += len(w["w"]) + 1

    def when(ch):
        t = offs[0][1]
        for p, s in offs:
            if p <= ch:
                t = s
            else:
                break
        return t

    ph = [(m.group(0).lower(), when(m.start())) for m in _PH.finditer(text)]
    no = [(m.group(1).lower(), when(m.start())) for m in _NOUN.finditer(text)]
    nouns = sorted({n for n, _ in no})
    phrases = sorted({p for p, _ in ph})
    # phrase + noun close together (within 8 s) is the real signal
    close = any(abs(pt - nt) <= 8 for _, pt in ph for _, nt in no)
    score = min(1.0, 0.25 * min(len(ph), 3) + 0.15 * min(len(nouns), 2) + (0.35 if close else 0))
    first = min([t for _, t in ph + no], default=None)
    return {"score": round(score, 2), "phrases": phrases[:6], "nouns": nouns[:6],
            "first_t": None if first is None else round(first, 1)}


# ---- layer 2: vision -----------------------------------------------------------------

VISION_SYSTEM = """You help a clipping channel find DISCOVERY moments in GTA 6 livestream footage
(a player finds a creature, place, mechanic, vehicle, secret or surprise).
You get a few frames from one stream window plus the streamer's words. Judge ONLY what you can see/read.
The stream is of GTA 6 (Grand Theft Auto VI). If the footage is clearly a different game, set discovery=false and kind='none'.
Rules:
- Do not guess about GTA 6 facts you are not sure of. Describe what is visible ("an alligator in a canal").
- 'discovery' is true only if something notable is actually on screen, not just the streamer talking.
- Flag cutscenes (letterboxed/story scene), sexual or suggestive content, nudity, gore, and menus/loading screens.
- Flag if the stream overlay or chat covers the action so the gameplay is unreadable.
- Output ONLY one JSON object:
{"discovery": bool, "kind": "creature|place|mechanic|vehicle|secret|funny_event|chase|new_unlisted|none",
 "what": "short plain description of what is on screen", "payoff_visible": bool,
 "cutscene": bool, "suggestive": bool, "gore": bool, "menu_or_loading": bool,
 "best_frame": 1-based index of the clearest frame,
 "hook": "max 8 words, first person like 'I found a gator in GTA 6', or '' if no discovery",
 "known_match": "name from the known list, or 'new' if it is notable and not on the list, or ''",
 "confidence": 0-1}"""


def sample_frames(media, offset, window_len, out_dir, n=4, around=None, width=768):
    """Grab n frames. If `around` (seconds into the window) is given, cluster them around it;
    otherwise spread over the window."""
    out_dir = Path(out_dir)
    if around is not None:
        lo, hi = max(1.0, around - 6), min(window_len - 1, around + 10)
    else:
        lo, hi = 2.0, max(3.0, window_len - 2)
    step = (hi - lo) / max(1, n - 1)
    paths = []
    for i in range(n):
        t = lo + step * i
        p = out_dir / f"disc_{i + 1}.jpg"
        try:
            run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{offset + t:.2f}",
                 "-i", str(media), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(p)])
            paths.append(p)
        except Exception as e:
            log(f"   frame grab failed at {t:.0f}s: {e}")
    return paths


def _parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in vision reply")
    return json.loads(m.group(0))


def vision_check(frames, words_text, cfg, clip_dir, channel=""):
    """Returns the parsed dict, or None if no API key / failure."""
    clip_dir = Path(clip_dir)
    user_text = json.dumps({"channel": channel, "frames": len(frames),
                            "streamer_words": words_text[:1200]}, ensure_ascii=False)
    (clip_dir / "vision_prompt.txt").write_text(
        VISION_SYSTEM + "\n\n" + knowledge_text() + "\n\nINPUT:\n" + user_text +
        "\n\n(attach disc_1.jpg ... disc_%d.jpg from this folder)" % len(frames), encoding="utf-8")
    if not frames or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    client = anthropic.Anthropic()
    content = []
    for i, p in enumerate(frames, 1):
        content.append({"type": "text", "text": f"Frame {i}:"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg",
            "data": base64.b64encode(Path(p).read_bytes()).decode()}})
    content.append({"type": "text", "text": user_text})
    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=cfg.get("discovery", {}).get("model") or cfg["anthropic_model"],
                max_tokens=1500,
                system=[{"type": "text", "text": VISION_SYSTEM + "\n\n" + knowledge_text(),
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": content}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text")
            if "{" not in text:
                kinds = [b.type for b in resp.content]
                (clip_dir / "vision_raw.txt").write_text(
                    f"stop_reason={resp.stop_reason} blocks={kinds}\n---\n{text}", encoding="utf-8")
                raise ValueError(f"no JSON (stop_reason={resp.stop_reason}, blocks={kinds}, "
                                 f"text={text[:160]!r})")
            return _parse(text)
        except Exception as e:
            last = e
    log(f"   vision check failed: {last}")
    return None


# ---- combine -------------------------------------------------------------------------

def analyze(media, offset, window_len, words, cand, cfg, clip_dir, channel=""):
    """Run both layers. Returns a dict that goes into the judge input and clip folder."""
    dc = cfg.get("discovery", {})
    if not dc.get("enabled", True):
        return None
    spike_rel = cand["peak_t"] - cand["win_start"]
    td = text_discovery(words)
    out = {"text": td, "vision": None, "strength": td["score"], "blocked": []}

    # only pay for the vision call when there is a reason to
    want_vision = dc.get("vision", True) and (
        td["score"] >= dc.get("vision_min_text", 0.25) or cand.get("h_score", 0) >= dc.get("vision_min_h", 0.6))
    if want_vision:
        around = td["first_t"] if td["first_t"] is not None else spike_rel
        frames = sample_frames(media, offset, window_len, clip_dir, dc.get("frames", 4), around=around)
        v = vision_check(frames, " ".join(w["w"] for w in words), cfg, clip_dir, channel)
        out["vision"] = v
        if v:
            conf = float(v.get("confidence", 0.5))
            if v.get("discovery") and v.get("payoff_visible", True):
                out["strength"] = round(min(1.0, max(td["score"], conf) * 0.6 + td["score"] * 0.4 + 0.2), 2)
                km = (v.get("known_match") or "").lower()
                tier = "rare" if km == "new" or v.get("kind") == "new_unlisted" else next(
                    (x["tier"] for x in KNOW["discoveries"] if x["name"].lower() == km), "common")
                out["tier"] = tier
                out["strength"] = round(min(1.0, out["strength"] + TIER_BONUS.get(tier, 0)), 2)
            for flag, why in (("cutscene", "cutscene"), ("suggestive", "suggestive content"),
                              ("gore", "gore"), ("menu_or_loading", "menu/loading screen")):
                if v.get(flag):
                    out["blocked"].append(why)
            best = int(v.get("best_frame", 1))
            if 1 <= best <= len(frames):
                out["best_frame_file"] = Path(frames[best - 1]).name
    return out
