"""Start the API:  python -m backend.run_api   (from the repo root)"""
import uvicorn

from .config import API_HOST, API_PORT

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host=API_HOST, port=API_PORT, log_level="info")
