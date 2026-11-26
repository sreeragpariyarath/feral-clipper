"""Find the streamer's face in a clip and return a webcam crop box around it.

Ported from Feral Streams Clipper (https://github.com/NaufalRizqullah/opensource-clipping),
clipping/studio/face_detection.py, MIT License, Copyright (c) 2026 Muhammad Naufal Rizqullah.
The detector is MediaPipe BlazeFace (short range). Only the face-finding idea is taken; the
rest of our renderer stays as it is.

Config: "facecam": "face" uses this; the box is found per clip. If no face is found the
caller falls back to a layout that needs no webcam.
"""
import os
import subprocess
import tempfile

import cv2
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          "models", "blaze_face_short_range.tflite")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/"
             "float16/1/blaze_face_short_range.tflite")

FACE_MARGIN = 4.0        # the crop is this many face-widths wide, to include head and shoulders
CAM_ASPECT = 1080 / 640  # the punch webcam panel is 1080 x 640
MIN_HIT_RATE = 0.2       # the face must be found in at least this share of the samples
MAX_FACE_W = 0.3         # faces wider than this share of the frame are not a webcam
SAME_SPOT = 0.06         # two detections closer than this (fraction of the frame) are the same person

_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
        if not os.path.exists(MODEL_PATH):
            os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
            import urllib.request
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        opts = mp_vision.FaceDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=mp_vision.RunningMode.IMAGE,
            min_detection_confidence=0.5,
        )
        _detector = mp_vision.FaceDetector.create_from_options(opts)
    return _detector


def _grab(media, t, out_path):
    """One frame at time t (seconds) written as a JPEG. Returns True when it worked."""
    res = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}",
                          "-i", str(media), "-frames:v", "1", "-vf", "scale=640:-2", str(out_path)],
                         capture_output=True)
    return res.returncode == 0 and os.path.exists(out_path)


def _detect(detector, bgr, mp, edge_margin=None):
    """Faces in one BGR image as (cx, cy, width) fractions of that image.
    With `edge_margin` (pixels), faces whose box touches the image edge are dropped: in a tile they are
    cut in half and their box lands on the neck."""
    h, w = bgr.shape[:2]
    img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(np.ascontiguousarray(bgr), cv2.COLOR_BGR2RGB))
    out = []
    for d in detector.detect(img).detections:
        bb = d.bounding_box
        if edge_margin is not None and (bb.origin_x < edge_margin or bb.origin_y < edge_margin
                                        or bb.origin_x + bb.width > w - edge_margin
                                        or bb.origin_y + bb.height > h - edge_margin):
            continue
        out.append(((bb.origin_x + bb.width / 2) / w, (bb.origin_y + bb.height / 2) / h, bb.width / w))
    return out


# BlazeFace shrinks every input to 128 px, so a face must fill about 1/6 of the image to be found.
# A webcam face is ~6 % of the frame wide: tiles of 30 % make it ~20 % of the tile. Upscaling a tile
# does not help (tested: 50 % tiles miss the face at 1-4x; 35 % and 25 % tiles find it at 0.94-0.97).
TILE = 0.3
TILE_STEPS = (0.0, 0.15, 0.3, 0.45, 0.55, 0.7)     # half-overlapping grid, 6 x 6 tiles, last tile ends at 100 %


def _faces_in(detector, bgr, mp):
    """Faces in the whole frame; if none, in overlapping tiles (small webcam faces are missed otherwise).
    Duplicates from overlapping tiles are merged. Coordinates are fractions of the frame."""
    found = _detect(detector, bgr, mp)
    if found:
        return found
    h, w = bgr.shape[:2]
    tw, th = int(w * TILE), int(h * TILE)
    for fy in TILE_STEPS:
        for fx in TILE_STEPS:
            x0, y0 = int(w * fx), int(h * fy)
            tile = bgr[y0:y0 + th, x0:x0 + tw]
            for cx, cy, fw in _detect(detector, tile, mp, edge_margin=2):
                found.append(((x0 + cx * tw) / w, (y0 + cy * th) / h, fw * tw / w))
    merged: list[list[float]] = []
    for f in found:                                    # one face seen by several tiles -> one entry
        for m in merged:
            if abs(m[0] - f[0]) <= SAME_SPOT and abs(m[1] - f[1]) <= SAME_SPOT:
                m[3] += 1
                for k in range(3):
                    m[k] += (f[k] - m[k]) / m[3]
                break
        else:
            merged.append([*f, 1])
    return [(m[0], m[1], m[2]) for m in merged]


def _frames_every_second(media, offset, duration, folder):
    """One small frame per second of [offset, offset+duration), decoded in a single ffmpeg pass
    (much faster than one seek per sample). Returns [(t, path)]."""
    pattern = os.path.join(folder, "s%04d.jpg")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{offset:.2f}", "-t", f"{duration:.2f}",
                    "-i", str(media), "-vf", "fps=1,scale=640:-2", "-q:v", "4", pattern], capture_output=True)
    out = []
    for i, name in enumerate(sorted(f for f in os.listdir(folder) if f.startswith("s"))):
        out.append((offset + i + 0.5, os.path.join(folder, name)))
    return out


def track_faces(media, offset, duration, keep_gray=None):
    """Faces found every second: [(t, [(cx, cy, w), ...])], webcam-sized faces only.
    If `keep_gray` is a list, each frame's grayscale image is appended to it (for overlay_edges)."""
    import mediapipe as mp

    detector = _get_detector()
    track = []
    with tempfile.TemporaryDirectory() as tmp:
        for t, jpg in _frames_every_second(media, offset, duration, tmp):
            bgr = cv2.imread(jpg)
            if bgr is not None:
                track.append((t, [f for f in _faces_in(detector, bgr, mp) if f[2] <= MAX_FACE_W]))
                if keep_gray is not None:
                    keep_gray.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32))
    return track


EDGE_PEAK = 2.5          # an overlay border must be this many times stronger than the typical edge nearby


def overlay_edges(grays):
    """Edges that stay in the same place across frames: the border of a webcam overlay.
    Moving gameplay edges average out; the overlay's straight border does not. Returns (gx, gy)."""
    stack = np.stack(grays)
    gx = np.abs(np.diff(stack, axis=2)).mean(axis=0)          # vertical borders
    gy = np.abs(np.diff(stack, axis=1)).mean(axis=0)          # horizontal borders
    return gx, gy


def _peak(profile, reverse=False):
    """Index of the first strong peak scanning away from the face, or None."""
    if profile.size < 3:
        return None
    floor = float(np.median(profile)) + 1e-6
    idx = range(profile.size - 1, -1, -1) if reverse else range(profile.size)
    best = max(idx, key=lambda i: profile[i])
    return best if profile[best] >= EDGE_PEAK * floor else None


SNAP_NEAR, SNAP_FAR = 1.5, 6.0   # search for the overlay border 1.5-6 face widths from the face centre


def snap_to_overlay(box, face, gx, gy):
    """Fit the crop to the webcam overlay around `face` when its border is visible.

    On each side, looks for the strongest steady edge between SNAP_NEAR and SNAP_FAR face widths from
    the face (closer edges are hair, headphones, the room). A side with no clear border falls back to
    the margin box. Then takes the largest panel-shaped crop inside that rectangle, centred on the face,
    so no gameplay or overlay text spills into the webcam panel."""
    h, w = gy.shape[0] + 1, gx.shape[1] + 1
    cx, cy, fw = face[0] * w, face[1] * h, face[2] * w
    near, far = SNAP_NEAR * fw, SNAP_FAR * fw
    r0, r1 = int(max(0, cy - fw)), int(min(h - 1, cy + fw))            # rows through the face
    c0, c1 = int(max(0, cx - fw)), int(min(w - 2, cx + fw))            # columns through the face

    def side(profile_of, lo, hi, reverse):
        lo, hi = int(max(0, lo)), int(hi)
        if hi - lo < 3:
            return None
        i = _peak(profile_of(lo, hi), reverse=reverse)
        return None if i is None else lo + i

    right = side(lambda a, b: gx[r0:r1, a:b].mean(axis=0), cx + near, min(w - 1, cx + far), False)
    left = side(lambda a, b: gx[r0:r1, a:b].mean(axis=0), cx - far, cx - near, True)
    down = side(lambda a, b: gy[a:b, c0:c1].mean(axis=1), cy + near, min(h - 1, cy + far), False)
    up = side(lambda a, b: gy[a:b, c0:c1].mean(axis=1), cy - far, cy - near, True)
    if (right, left, down, up) == (None, None, None, None):
        return box

    L = left + 1 if left is not None else (0 if cx - far <= 0 else box["x"] * w)
    R = right if right is not None else (w if cx + far >= w else (box["x"] + box["w"]) * w)
    T = up + 1 if up is not None else (0 if cy - far <= 0 else box["y"] * h)
    B = down if down is not None else (h if cy + far >= h else (box["y"] + box["h"]) * h)

    aspect = CAM_ASPECT                                                # panel width / height in pixels
    bw = min(R - L, (B - T) * aspect)
    bh = bw / aspect
    if bw < 2.5 * fw:                                                  # border too close: not a webcam frame
        return box
    x = min(max(cx - bw / 2, L), R - bw)
    y = min(max(cy - bh * 0.45, T), B - bh)
    out = dict(box)
    out.update({"x": round(x / w, 4), "y": round(y / h, 4), "w": round(bw / w, 4), "h": round(bh / h, 4),
                "snapped": True, "overlay": [round(v, 4) for v in (L / w, T / h, R / w, B / h)]})
    return out


def box_from_track(track, min_hit_rate=MIN_HIT_RATE):
    """The webcam box from a per-second face track, or None.

    The webcam stays in one place, so the spot where a face shows up in the most seconds wins; a big face
    in a crowd appears for a moment and loses even when it is larger. Positions are smoothed with the
    median over every second that matched, so a single bad detection cannot move the crop. `moving` is
    True when the matched face drifts more than one SAME_SPOT step (a cam that moves during the clip).
    """
    per_frame = [faces for _, faces in track if faces]
    if not track:
        return None
    best, best_hits = None, []
    for frame_faces in per_frame:
        for cand in frame_faces:
            hits = [f for pf in per_frame for f in pf
                    if abs(f[0] - cand[0]) <= SAME_SPOT and abs(f[1] - cand[1]) <= SAME_SPOT]
            if len(hits) > len(best_hits):
                best, best_hits = cand, hits
    if best is None or len(best_hits) / len(track) < min_hit_rate:
        return None

    cx = float(np.median([f[0] for f in best_hits]))
    cy = float(np.median([f[1] for f in best_hits]))
    fw = float(np.median([f[2] for f in best_hits]))
    bw = min(1.0, fw * FACE_MARGIN)
    # height from the panel's aspect ratio: the crop must match the panel once scaled
    frame_aspect = 16 / 9
    bh = min(1.0, bw * frame_aspect / CAM_ASPECT)
    x = min(max(cx - bw / 2, 0.0), 1.0 - bw)
    y = min(max(cy - bh * 0.42, 0.0), 1.0 - bh)     # a little more room above the head than below
    spread = float(max(np.ptp([f[0] for f in best_hits]), np.ptp([f[1] for f in best_hits])))
    return {"x": round(float(x), 4), "y": round(float(y), 4), "w": round(float(bw), 4), "h": round(float(bh), 4),
            "hit_rate": round(len(best_hits) / len(track), 3), "moving": spread > SAME_SPOT,
            "face": [round(cx, 4), round(cy, 4), round(fw, 4)]}


def find_webcam_box(media, offset, duration, samples=None):
    """Return {"x","y","w","h",...} as fractions of the frame, or None when no face is found.

    Samples one frame per second (`samples` is kept for old callers and ignored).
    `offset` and `duration` are seconds inside `media` (same convention as extract_window).
    """
    grays: list = []
    box = box_from_track(track_faces(media, offset, duration, keep_gray=grays))
    if box and len(grays) >= 3:
        box = snap_to_overlay(box, box["face"], *overlay_edges(grays))
    return box


def stream_box(boxes):
    """The streamer's usual webcam spot across clips: median of boxes that agree with each other.
    Used for clips where the face was turned away or hidden the whole time."""
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    best = max(boxes, key=lambda b: sum(abs(o["x"] - b["x"]) <= SAME_SPOT and abs(o["y"] - b["y"]) <= SAME_SPOT
                                        for o in boxes))
    agree = [o for o in boxes if abs(o["x"] - best["x"]) <= SAME_SPOT and abs(o["y"] - best["y"]) <= SAME_SPOT]
    return {k: round(float(np.median([o[k] for o in agree])), 4) for k in ("x", "y", "w", "h")} | {"agree": len(agree)}
