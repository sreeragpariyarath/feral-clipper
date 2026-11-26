"""Face tracking logic that needs no model: picking the webcam spot, the stream fallback, border snapping."""
import numpy as np

from clipper.render import face_track as ft


def test_recurring_face_beats_one_big_face():
    cam = (0.11, 0.48, 0.05)
    crowd = (0.6, 0.5, 0.2)
    track = [(t, [cam]) for t in range(8)] + [(8, [crowd, cam]), (9, [])]
    box = ft.box_from_track(track)
    assert box and abs(box["face"][0] - 0.11) < 1e-6 and box["hit_rate"] == 0.9 and not box["moving"]


def test_no_box_when_face_is_rare():
    assert ft.box_from_track([(0, [(0.1, 0.5, 0.05)])] + [(t, []) for t in range(1, 10)]) is None


def test_stream_box_uses_agreeing_clips():
    a = {"x": 0.0, "y": 0.35, "w": 0.27, "h": 0.28}
    b = {"x": 0.01, "y": 0.36, "w": 0.26, "h": 0.27}
    stray = {"x": 0.7, "y": 0.1, "w": 0.2, "h": 0.2}
    out = ft.stream_box([a, None, b, stray])
    assert out["agree"] == 2 and out["x"] < 0.05


def test_snap_finds_overlay_border():
    h, w = 360, 640
    grays = []
    rng = np.random.default_rng(1)
    for _ in range(6):                              # moving noise everywhere, a fixed bright webcam box
        g = rng.uniform(0, 255, (h, w)).astype(np.float32) * 0.3
        g[120:240, 0:170] = 200.0
        grays.append(g)
    face = (70 / w, 175 / h, 30 / w)
    box = {"x": 0.0, "y": 0.3, "w": 0.4, "h": 0.4}
    out = ft.snap_to_overlay(box, face, *ft.overlay_edges(grays))
    assert out.get("snapped")
    assert abs(out["overlay"][2] - 170 / w) < 0.01        # right border found
