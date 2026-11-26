"""Helpers shared by the pipeline steps."""
from collections.abc import Iterator
from pathlib import Path

from clipper.common import read_json

from ..context import Ctx

FFMPEG_QUIET = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]


def skip(ctx: Ctx, what: str) -> dict:
    """Report a step whose output already exists as done."""
    ctx.report(100, f"{what} already done, skipped", force=True)
    return {"skipped": True}


def window_words(words: list[dict], start: float, end: float) -> list[dict]:
    """Words inside [start, end], with times relative to start."""
    return [{"w": w["w"], "s": round(w["s"] - start, 2), "e": round(w["e"] - start, 2)}
            for w in words if w["e"] > start and w["s"] < end]


def accepted(ctx: Ctx) -> Iterator[tuple[str, Path]]:
    """Clip folders that were judged and not rejected, in the order of the score sheet."""
    sheet = ctx.read("scores.json") or {}
    for no in sheet.get("picked", []):
        d = ctx.folder / "clips" / no
        status = read_json(d / "status.json") if (d / "status.json").exists() else {}
        if (d / "judge.json").exists() and status.get("status") != "skipped":
            yield no, d
