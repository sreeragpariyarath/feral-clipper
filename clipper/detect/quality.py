"""Clip quality scores that are compared within one stream (Phase 4).

Raw model numbers (CLIP similarity, loudness in dB) mean different things on different streams, so the
action score is a rank among this stream's candidates, and the payoff score is measured against the
window's own loudness and the stream's own picture-change level. Everything here is pure numpy: no
models, no files, easy to test.
"""
from __future__ import annotations

import numpy as np

# Loudness payoff has no weight: on a talk-driven stream it pointed the wrong way (the judge's three
# accepted comedy clips had the lowest loudness payoff). It is kept as information; the judge decides
# the payoff from the words and must name it (clipper.ai.judge.has_payoff).
WEIGHTS = {"monitor": 0.40, "hook": 0.25, "action": 0.20, "reaction": 0.15}
TALK_ONLY_PENALTY = 0.6
UNSAFE_PENALTY = 0.3


def ranks(values: list[float | None]) -> list[float | None]:
    """Percentile rank of each value among the others, 0..1 (ties share the average rank)."""
    known = [(v, i) for i, v in enumerate(values) if v is not None]
    out: list[float | None] = [None] * len(values)
    if len(known) == 1:
        out[known[0][1]] = 0.5
    if len(known) < 2:
        return out
    order = sorted(known)
    n = len(order) - 1
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and order[j + 1][0] == order[i][0]:
            j += 1
        r = ((i + j) / 2) / n
        for k in range(i, j + 1):
            out[order[k][1]] = r
        i = j + 1
    return out


def action_scores(margins: list[float | None], changes: list[float | None]) -> list[float | None]:
    """On-screen action, 0..1: how much more the frames look like action than like menus / standing
    around (CLIP margin), and how much the scene changes between frames (not just a camera pan)."""
    rm, rc = ranks(margins), ranks(changes)
    out: list[float | None] = []
    for m, c in zip(rm, rc):
        if m is None and c is None:
            out.append(None)
        else:
            out.append(round(0.6 * (m if m is not None else 0.5) + 0.4 * (c if c is not None else 0.5), 3))
    return out


def payoff_score(db: np.ndarray, mot: np.ndarray, start: float, end: float, mot_ref: float) -> float:
    """Does the window END with something? 0..1 from the last third of the window:
    its loudest second against the window's own loud level (75th percentile; 8 dB above = full marks),
    or a picture spike above the stream's busy level `mot_ref` (its 90th percentile).

    Compared with the median instead, ordinary talking already counts as a payoff (tested on a 5 h
    stream: 30 of 30 windows passed; with the 75th percentile about a third end flat)."""
    a, b = int(start), int(min(end, len(db), len(mot)))
    if b - a < 6:
        return 0.0
    tail = a + 2 * (b - a) // 3
    loud = float(db[tail:b].max() - np.percentile(db[a:b], 75)) / 8.0
    busy = float(mot[tail:b].max() / mot_ref) - 1.0 if mot_ref > 0 else 0.0
    return round(float(np.clip(max(loud, busy), 0.0, 1.0)), 3)


def combine(monitor: float, hook: float, action: float | None, reaction: float, payoff: float,
            talk_only: bool, unsafe: bool) -> tuple[float, list[str]]:
    """Final score 0..1 and notes. Talk-only and unsafe windows are penalised; a quiet ending is only noted."""
    parts = {"monitor": monitor, "hook": hook, "action": 0.5 if action is None else action, "reaction": reaction}
    final = sum(WEIGHTS[k] * parts[k] for k in WEIGHTS)
    notes: list[str] = []
    if payoff < 0.2:
        notes.append("quiet ending")            # information only, no penalty
    if talk_only:
        notes.append("talk only")
        final *= TALK_ONLY_PENALTY
    if unsafe:
        notes.append("possibly unsafe")
        final *= UNSAFE_PENALTY
    return round(final, 3), notes
