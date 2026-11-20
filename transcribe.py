"""faster-whisper wrapper with word timestamps. Loads the model once."""
import os
import site
import sys
from pathlib import Path

from common import log

_model = None


def _add_cuda_dlls():
    """On Windows, pip's nvidia-cublas/cudnn wheels put DLLs in site-packages/nvidia/*/bin."""
    if sys.platform != "win32":
        return
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        nv = Path(base) / "nvidia"
        if nv.exists():
            for bin_dir in nv.glob("*/bin"):
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]


def get_model(cfg):
    global _model
    if _model is not None:
        return _model
    from faster_whisper import WhisperModel
    _add_cuda_dlls()
    try:
        _model = WhisperModel(cfg["whisper_model"], device=cfg["whisper_device"],
                              compute_type=cfg["whisper_compute"])
        log(f"Whisper loaded: {cfg['whisper_model']} on {cfg['whisper_device']}")
    except Exception as e:  # CUDA libs missing etc.
        log(f"GPU Whisper failed ({e}); falling back to CPU 'small' int8 (slower, less accurate)")
        _model = WhisperModel("small", device="cpu", compute_type="int8")
    return _model


def transcribe(wav_path, cfg):
    model = get_model(cfg)
    segments, info = model.transcribe(
        str(wav_path), word_timestamps=True, vad_filter=True,
        language=cfg.get("caption_language"), beam_size=5)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)})
    return {"language": info.language, "words": words}


def plain_text(words):
    return " ".join(w["w"] for w in words)
