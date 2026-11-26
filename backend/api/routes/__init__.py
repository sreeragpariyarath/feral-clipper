"""Thin HTTP routes for /api/v1: parse the request, call a service, return a schema. No logic here."""
from fastapi import APIRouter

from . import campaigns, clips, jobs, posts, streams, system

router = APIRouter(prefix="/api/v1")
for _module in (system, streams, clips, jobs, campaigns, posts):
    router.include_router(_module.router)
