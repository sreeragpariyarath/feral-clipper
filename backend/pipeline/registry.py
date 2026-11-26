"""Step registry: name -> (label, function), in run order. The only place the step order is defined."""
from collections.abc import Callable
from importlib import import_module

from .context import Ctx

StepFn = Callable[[Ctx], dict]

_LABELS: dict[str, str] = {
    "ingest": "Download or open the video",
    "audio": "Get the audio",
    "transcribe": "Transcribe the stream",
    "signals": "Measure loudness and picture",
    "candidates": "Find candidate moments",
    "hooks": "Find hooks and reactions",
    "visual": "Check what is on screen",
    "scores": "Build the score sheet",
    "judge": "Judge with Claude",
    "face": "Find the streamer's face",
    "render": "Render the clips",
    "ready": "Ready for review",
}
ORDER: list[str] = list(_LABELS)


def label_of(name: str) -> str:
    return _LABELS[name]


def load(name: str) -> StepFn:
    """Import only the step being run, so a light step never loads the heavy models."""
    if name not in _LABELS:
        raise KeyError(f"unknown step {name!r}")
    return getattr(import_module(f".steps.{name}", __package__), name)
