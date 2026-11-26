"""FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .api import compat
from .api.routes import router as v1_router
from .db import engine, init_db
from .events import emit
from .importer import sync_all
from .services.errors import ServiceError


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



@app.exception_handler(ServiceError)
async def service_error(_request: Request, exc: ServiceError) -> JSONResponse:
    """Services raise typed errors; this maps them to HTTP status codes in one place."""
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


app.include_router(v1_router)
app.include_router(compat.router)
