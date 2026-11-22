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

SAMPLES = 12             # frames per clip; a 30-40 s clip gets one every 3 s
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


def _detect(detector, bgr, mp):
    """Faces in one BGR image as (cx, cy, width) fractions of that image."""
    h, w = bgr.shape[:2]
    img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    out = []
    for d in detector.detect(img).detections:
        bb = d.bounding_box
        out.append(((bb.origin_x + bb.width / 2) / w, (bb.origin_y + bb.height / 2) / h, bb.width / w))
    return out


def _faces_in(detector, bgr, mp):
    """Faces in the whole frame; if none, in four overlapping tiles (small webcams are missed otherwise).
    Returned coordinates are fractions of the whole frame."""
    found = _detect(detector, bgr, mp)
    if found:
        return found
    h, w = bgr.shape[:2]
    tw, th = int(w * 0.6), int(h * 0.6)
    for x0, y0 in ((0, 0), (w - tw, 0), (0, h - th), (w - tw, h - th)):
        tile = bgr[y0:y0 + th, x0:x0 + tw]
        for cx, cy, fw in _detect(detector, tile, mp):
            # map tile fractions back to whole-frame fractions
            found.append(((x0 + cx * tw) / w, (y0 + cy * th) / h, fw * tw / w))
    return found


def find_webcam_box(media, offset, duration, samples=SAMPLES):
    """Return {"x","y","w","h"} as fractions of the frame, or None when no face is found.

    `offset` and `duration` are seconds inside `media` (same convention as extract_window).
    """
    import mediapipe as mp

    detector = _get_detector()
    per_frame = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(samples):
            t = offset + (i + 0.5) * duration / samples
            jpg = os.path.join(tmp, f"f{i}.jpg")
            if not _grab(media, t, jpg):
                continue
            bgr = cv2.imread(jpg)
            if bgr is None:
                continue
            found = [f for f in _faces_in(detector, bgr, mp) if f[2] <= MAX_FACE_W]
            if found:
                per_frame.append(found)

    # The webcam stays in one place, so take the spot where a face shows up in most frames.
    # A big face in a crowd appears once, so it loses to the webcam even when it is larger.
    best, best_hits = None, []
    for frame_faces in per_frame:
        for cand in frame_faces:
            hits = [f for pf in per_frame for f in pf
                    if abs(f[0] - cand[0]) <= SAME_SPOT and abs(f[1] - cand[1]) <= SAME_SPOT]
            if len(hits) > len(best_hits):
                best, best_hits = cand, hits
    if best is None or len(best_hits) / samples < MIN_HIT_RATE:
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
    return {"x": round(float(x), 4), "y": round(float(y), 4), "w": round(float(bw), 4), "h": round(float(bh), 4)}
