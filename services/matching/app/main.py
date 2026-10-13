import json
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel
from sqlalchemy.orm import Session
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "common"))
from consul import register_with_consul
from .auth import current_user, require_recruiter
from .db import Base, engine, get_db
from .models import Match
from .pipeline import _to_dict, rank_candidates, score_pair, store_match
import httpx

PORT = int(os.getenv("PORT", "8006"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "matching-service")
RESUME_API = os.getenv("RESUME_API", "http://resume-service:8002")
JOB_API = os.getenv("JOB_API", "http://job-service:8004")
EMBED_API = os.getenv("EMBED_API", "http://embedding-service:8005")
REQUESTS = Counter("http_requests_total", "total requests", ["service", "path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    register_with_consul(SERVICE_NAME, PORT)
    yield


app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)


class SingleIn(BaseModel):
    resume_id: str
    job_id: str


class BulkIn(BaseModel):
    top_k: int = 50
    limit: int = 20


def fetch_resume(resume_id: str) -> dict:
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{RESUME_API}/api/v1/resumes/{resume_id}")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="resume not found")
        r.raise_for_status()
        return r.json()


def fetch_job(job_id: str) -> dict:
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{JOB_API}/internal/jobs/{job_id}")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="job not found")
        r.raise_for_status()
        return r.json()


def fetch_parsed(resume_id: str) -> dict | None:
    try:
        return fetch_resume(resume_id).get("parsed")
    except HTTPException:
        return None


def search_chunks(text: str, top_k: int) -> list[dict]:
    with httpx.Client(timeout=15.0) as client:
        r = client.post(f"{EMBED_API}/api/v1/embeddings/search", json={"text": text, "top_k": top_k})
        r.raise_for_status()
        return r.json()["hits"]


@app.get("/health")
def health():
    return {"service": SERVICE_NAME, "status": "ok"}


@app.get("/api/v1/match/health")
def match_health():
    REQUESTS.labels(SERVICE_NAME, "/api/v1/match/health").inc()
    return {"service": SERVICE_NAME, "status": "ok"}


@app.post("/api/v1/match/single", status_code=201)
def match_single(body: SingleIn, db: Session = Depends(get_db), user: dict = Depends(current_user)):
    try:
        resume = fetch_resume(body.resume_id)
        job = fetch_job(body.job_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=502, detail="downstream unavailable")
    if not resume.get("parsed"):
        raise HTTPException(status_code=409, detail="resume not parsed yet")
    scores = score_pair(job, resume["parsed"])
    row = store_match(db, body.resume_id, body.job_id, scores)
    return _to_dict(row)


@app.post("/api/v1/match/job/{job_id}")
def match_bulk(job_id: str, body: BulkIn, db: Session = Depends(get_db), user: dict = Depends(require_recruiter)):
    try:
        job = fetch_job(job_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=502, detail="downstream unavailable")
    try:
        from .pipeline import job_text

        hits = search_chunks(job_text(job), min(body.top_k, 100))
    except Exception:
        raise HTTPException(status_code=502, detail="embedding-service unavailable")
    ranked = rank_candidates(db, job, hits, fetch_parsed, limit=min(body.limit, 50))
    REQUESTS.labels(SERVICE_NAME, "/api/v1/match/job").inc()
    return {"job_id": job_id, "matches": ranked}


@app.get("/api/v1/match/resume/{resume_id}/job/{job_id}")
def get_match(resume_id: str, job_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)):
    row = db.query(Match).filter(Match.resume_id == resume_id, Match.job_id == job_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return _to_dict(row)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
