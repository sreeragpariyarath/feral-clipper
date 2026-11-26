"""Step: Summarise the run; the worker loads the clips into the library."""
from collections import Counter

from clipper.common import read_json

from ..context import Ctx


def ready(ctx: Ctx) -> dict:
    """Summarise the run; the worker loads the clips into the library."""
    base = ctx.folder / "clips"
    statuses = Counter()
    for d in base.glob("9*") if base.exists() else []:
        s = read_json(d / "status.json") if (d / "status.json").exists() else {}
        statuses[s.get("status", "unfinished")] += 1
    summary = {"ready": statuses.get("ready", 0), "skipped": statuses.get("skipped", 0)}
    ctx.write("summary.json", summary)
    ctx.report(100, f"{summary['ready']} clips ready, {summary['skipped']} skipped", force=True)
    return summary
