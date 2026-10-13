import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel
from sqlalchemy.orm import Session
import sys, pathlib
_COMMON_CANDIDATES = (
    pathlib.Path(__file__).resolve().parents[2] / "common",
    pathlib.Path("/code/common"),
)
for _candidate in _COMMON_CANDIDATES:
    if (_candidate / "consul.py").exists():
        sys.path.insert(0, str(_candidate))
        break
from consul import register_with_consul
from .backends import get_backend
from .db import Base, SessionLocal, engine, get_db
from .pipeline import fetch_job, fetch_parsed_resume, index_job, index_resume, search_resumes
from .worker import start_background

PORT = int(os.getenv("PORT", "8005"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "embedding-service")
REQUESTS = Counter("http_requests_total", "total requests", ["service", "path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    register_with_consul(SERVICE_NAME, PORT)
    if os.getenv("WORKER_ENABLED", "1") == "1":
        start_background()
    yield


app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)


class SearchIn(BaseModel):
    text: str
    top_k: int = 50


@app.get("/health")
def health():
    backend = get_backend()
    return {"service": SERVICE_NAME, "status": "ok", "backend": backend.name, "dim": backend.dim}


@app.get("/api/v1/embeddings/health")
def embeddings_health():
    REQUESTS.labels(SERVICE_NAME, "/api/v1/embeddings/health").inc()
    backend = get_backend()
    return {"service": SERVICE_NAME, "status": "ok", "backend": backend.name}


@app.post("/api/v1/embeddings/resumes/{resume_id}")
def embed_resume(resume_id: str, db: Session = Depends(get_db)):
    try:
        resume = fetch_parsed_resume(resume_id)
    except Exception:
        raise HTTPException(status_code=502, detail="resume-service unavailable")
    if not resume.get("parsed"):
        raise HTTPException(status_code=409, detail="resume not parsed yet")
    n = index_resume(db, resume_id, resume["parsed"])
    return {"resume_id": resume_id, "chunks": n}


@app.post("/api/v1/embeddings/jobs/{job_id}")
def embed_job(job_id: str, db: Session = Depends(get_db)):
    try:
        job = fetch_job(job_id)
    except Exception:
        raise HTTPException(status_code=502, detail="job-service unavailable")
    return {"job_id": index_job(db, job)}


@app.post("/api/v1/embeddings/search")
def search(body: SearchIn, db: Session = Depends(get_db)):
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="empty query")
    return {"hits": search_resumes(db, body.text, min(body.top_k, 100))}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
