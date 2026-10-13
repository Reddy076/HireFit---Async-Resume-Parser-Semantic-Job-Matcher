import json
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from sqlalchemy import or_
from sqlalchemy.orm import Session
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "common"))
from consul import register_with_consul
from .auth import current_user, require_recruiter
from .db import Base, engine, get_db
from .events import publish
from .models import Job
from .schemas import JobCreate, JobOut, JobUpdate

PORT = int(os.getenv("PORT", "8004"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "job-service")
REQUESTS = Counter("http_requests_total", "total requests", ["service", "path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    register_with_consul(SERVICE_NAME, PORT)
    yield


app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)


def to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        description=job.description,
        skills=json.loads(job.skills_json),
        created_by=job.created_by,
    )


@app.get("/health")
def health():
    return {"service": SERVICE_NAME, "status": "ok"}


@app.get("/api/v1/jobs/health")
def jobs_health():
    REQUESTS.labels(SERVICE_NAME, "/api/v1/jobs/health").inc()
    return {"service": SERVICE_NAME, "status": "ok", "queue": "kafka:job.created"}


@app.post("/api/v1/jobs", response_model=JobOut, status_code=201)
def create_job(body: JobCreate, db: Session = Depends(get_db), user: dict = Depends(require_recruiter)):
    job = Job(
        title=body.title.strip(),
        description=body.description.strip(),
        skills_json=json.dumps([s.strip() for s in body.skills if s.strip()]),
        created_by=user["id"],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    publish("job.created", {"job_id": job.id})
    REQUESTS.labels(SERVICE_NAME, "/api/v1/jobs").inc()
    return to_out(job)


@app.get("/api/v1/jobs", response_model=list[JobOut])
def list_jobs(
    q: str = "", limit: int = 20, offset: int = 0,
    db: Session = Depends(get_db), user: dict = Depends(current_user),
):
    query = db.query(Job).order_by(Job.created_at.desc())
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Job.title.ilike(like), Job.description.ilike(like)))
    return [to_out(j) for j in query.offset(offset).limit(min(limit, 100)).all()]


@app.get("/api/v1/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="not found")
    return to_out(job)


@app.patch("/api/v1/jobs/{job_id}", response_model=JobOut)
def update_job(job_id: str, body: JobUpdate, db: Session = Depends(get_db), user: dict = Depends(require_recruiter)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="not found")
    if job.created_by != user["id"]:
        raise HTTPException(status_code=403, detail="not your job")
    if body.title is not None:
        job.title = body.title.strip()
    if body.description is not None:
        job.description = body.description.strip()
    if body.skills is not None:
        job.skills_json = json.dumps([s.strip() for s in body.skills if s.strip()])
    db.commit()
    db.refresh(job)
    return to_out(job)


@app.delete("/api/v1/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, db: Session = Depends(get_db), user: dict = Depends(require_recruiter)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="not found")
    if job.created_by != user["id"]:
        raise HTTPException(status_code=403, detail="not your job")
    db.delete(job)
    db.commit()
    return Response(status_code=204)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
