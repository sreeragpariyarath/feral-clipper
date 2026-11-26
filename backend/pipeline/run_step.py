"""Run one pipeline step for a job:  python -m backend.pipeline.run_step <job_id> <step>

The worker starts this as a separate process, so a step can be cancelled by stopping the process.
Exit code 0 = step done; anything else = failed (the traceback is in the job log).
"""
import sys
import traceback

from sqlmodel import Session

from ..db import engine, init_db
from ..models import Job
from .context import Ctx
from .registry import ORDER, load


def main(job_id: int, step: str) -> None:
    if step not in ORDER:
        raise SystemExit(f"unknown step {step}")
    init_db()
    with Session(engine) as s:
        job = s.get(Job, job_id)
        if job is None:
            raise SystemExit(f"job {job_id} not found")
        ctx = Ctx(job.id, job.stream_id, job.params, job.source_url)

    result = load(step)(ctx) or {}

    with Session(engine) as s:                       # keep each step's summary (and token use) on the job
        job = s.get(Job, job_id)
        params = dict(job.params or {})
        results = dict(params.get("results") or {})
        results[step] = result
        params["results"] = results
        for key in ("tokens_in", "tokens_out"):
            if result.get(key):
                params[key] = int(params.get(key, 0)) + int(result[key])
        job.params = params
        s.add(job)
        s.commit()
    ctx.report(100, "done", force=True)


if __name__ == "__main__":
    try:
        main(int(sys.argv[1]), sys.argv[2])
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
