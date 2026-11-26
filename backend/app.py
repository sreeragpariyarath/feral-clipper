"""FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .api import compat, v1
from .db import engine, init_db
from .events import emit
from .importer import sync_all


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with Session(engine) as session:
        n = sync_all(session)            # pick up streams and clips already on disk
        emit(session, "info", f"API started; {n} streams loaded")
    yield


app = FastAPI(title="Feral Clipper API", version="0.1.0", lifespan=lifespan)

# Only the local frontend may call the API from a browser.
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:3107", "http://localhost:3107"],
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(v1.router)
app.include_router(compat.router)
