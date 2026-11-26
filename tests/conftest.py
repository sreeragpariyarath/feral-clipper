"""Every test runs against a throw-away data folder; the real data/feral.db is never touched."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="feral-test-"))
os.environ["FERAL_DATA_DIR"] = str(_TMP)          # must be set before backend.config is imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from backend.config import VOD_DIR  # noqa: E402
from backend.db import engine, init_db  # noqa: E402


@pytest.fixture()
def session():
    SQLModel.metadata.drop_all(engine)
    init_db()
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(session):
    from backend.app import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def vod_dir() -> Path:
    VOD_DIR.mkdir(parents=True, exist_ok=True)
    return VOD_DIR
