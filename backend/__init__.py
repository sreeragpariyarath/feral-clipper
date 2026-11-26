"""Feral Clipper backend: FastAPI app, SQLite database and a worker process that runs the clip pipeline.

Start from the repo root:
    python -m backend.run_api       # API on http://127.0.0.1:8766
    python -m backend.run_worker    # runs queued jobs
"""
