"""Window scoring: prefix-sum version must match the plain per-window computation."""
import numpy as np

from clipper.detect import energy as en


def _reference(db, mot, win, step):
    thr_db = float(np.percentile(db, 50)) + 6.0
    thr_mot = float(np.percentile(mot, 60))
    rows = [en.score_window(db, mot, a, win, thr_db, thr_mot) for a in range(0, len(db) - win + 1, step)]
    rows = [r for r in rows if r and r["passes"]]
    return sorted(rows, key=lambda r: r["total"], reverse=True)


def test_find_windows_matches_reference():
    rng = np.random.default_rng(7)
    db = rng.normal(-30, 8, 3000)
    mot = np.abs(rng.normal(0, 1, 3000))
    db[1000:1060] += 25                                  # one loud, busy stretch
    mot[1000:1060] += 3
    got = en.find_windows(db, mot, win=30, step=5)
    want = _reference(db, mot, 30, 5)
    assert [r["a"] for r in got] == [r["a"] for r in want]
    assert any(990 <= r["a"] <= 1060 for r in got)


def test_find_windows_short_input():
    assert en.find_windows(np.zeros(10), np.zeros(10), win=30) == []


def test_pick_non_overlapping_keeps_gap():
    rows = [{"peak": p, "total": t} for p, t in [(100, 0.9), (120, 0.8), (200, 0.7), (150, 0.6), (40, 0.5)]]
    kept = en.pick_non_overlapping(rows, top=10, gap=45)
    assert [r["peak"] for r in kept] == [100, 200, 150, 40]      # 120 is 20 s from 100, so dropped


def test_pick_non_overlapping_respects_top():
    rows = [{"peak": i * 100, "total": 1.0} for i in range(10)]
    assert len(en.pick_non_overlapping(rows, top=3, gap=45)) == 3
