"""Find hook lines in a window's transcript and rate how much the streamer reacts.

Input: the window's words (times relative to the window start) and, optionally, sound tags
from PANNs for the same window. No AI call: a word list, punctuation and sound tags.
"""
import re

# phrases streamers use when something is happening; weight = how strong a hook it is
STRONG = {
    "oh my god": 1.0, "no way": 1.0, "what the": 1.0, "holy": 0.9, "let's go": 0.9, "lets go": 0.9,
    "bro": 0.5, "dude": 0.5, "wait": 0.6, "what": 0.5, "why": 0.4, "how": 0.3, "run": 0.6,
    "help": 0.7, "dead": 0.8, "died": 0.8, "dying": 0.7, "crash": 0.8, "cops": 0.7, "police": 0.7,
    "chase": 0.8, "insane": 0.9, "crazy": 0.8, "yo": 0.5, "nah": 0.5, "shut up": 0.7, "scream": 0.7,
    "explode": 0.9, "explosion": 0.9, "boom": 0.7, "fire": 0.6, "shoot": 0.7, "gun": 0.5,
}
REACTION_TAGS = {"Laughter", "Screaming", "Shout", "Yell", "Gasp", "Explosion", "Gunshot, gunfire", "Siren"}
SENTENCE_END = re.compile(r"[.!?]$")


def _sentences(words):
    """Group words into sentences using the punctuation Whisper writes."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if SENTENCE_END.search(w["w"]) or len(cur) >= 18:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _line_score(text):
    t = text.lower()
    score = sum(weight for phrase, weight in STRONG.items() if phrase in t)
    score += 0.4 * text.count("!") + 0.25 * text.count("?")
    return min(1.0, score / 2.0)


def analyze(words, window_len, tags=None):
    """Returns hook line, where it starts, hook score (0..1), talk density and reaction (0..1)."""
    sentences = _sentences(words)
    best = {"text": "", "t": None, "score": 0.0}
    for sent in sentences:
        text = " ".join(w["w"] for w in sent).strip()
        score = _line_score(text)
        start = sent[0]["s"]
        # a hook near the start of the clip is worth more: viewers decide in the first seconds
        weighted = score * (1.0 if start <= 8 else 0.7)
        if weighted > best["score"]:
            best = {"text": text, "t": round(start, 2), "score": round(weighted, 3)}

    talk_density = round(len(words) / max(1.0, window_len), 2)        # words per second
    reaction, reaction_labels = 0.0, []
    for x in tags or []:
        hits = {k: v for k, v in (x.get("top") or {}).items() if k in REACTION_TAGS}
        if hits:
            reaction = max(reaction, max(hits.values()))
            reaction_labels += list(hits)
    return {
        "hook_line": best["text"][:200],
        "hook_t": best["t"],
        "hook_score": best["score"],
        "talk_density": talk_density,
        "reaction": round(min(1.0, reaction * 2), 3),
        "reaction_labels": sorted(set(reaction_labels)),
        "sentences": len(sentences),
    }
