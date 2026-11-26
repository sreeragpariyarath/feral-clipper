from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...config import key_status
from ...db import get_session
from ...schemas import JobCreate, JobOut
from ...services import jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=202, response_model=JobOut)
def create_job(body: JobCreate, session: Session = Depends(get_session)) -> JobOut:
    return jobs.to_out(session, jobs.create(session, body, key_status()["anthropic"]))


@router.get("", response_model=list[JobOut])
def list_jobs(limit: int = 30, session: Session = Depends(get_session)) -> list[JobOut]:
    return [jobs.to_out(session, j) for j in jobs.recent(session, limit)]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, session: Session = Depends(get_session)) -> JobOut:
    return jobs.to_out(session, jobs.get(session, job_id), with_log=True)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: int, session: Session = Depends(get_session)) -> JobOut:
    return jobs.to_out(session, jobs.cancel(session, jobs.get(session, job_id)))


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_job(job_id: int, session: Session = Depends(get_session)) -> JobOut:
    return jobs.to_out(session, jobs.retry(session, jobs.get(session, job_id)))
