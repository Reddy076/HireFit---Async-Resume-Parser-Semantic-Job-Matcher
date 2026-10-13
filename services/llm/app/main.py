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
from .auth import current_user
from .db import Base, engine, get_db
from .models import GenerationLog
from .prompts import PROMPTS, pack_context
from .providers import generate
import httpx

PORT = int(os.getenv("PORT", "8007"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "llm-service")
RESUME_API = os.getenv("RESUME_API", "http://resume-service:8002")
JOB_API = os.getenv("JOB_API", "http://job-service:8004")
MATCH_API = os.getenv("MATCH_API", "http://matching-service:8006")
REQUESTS = Counter("http_requests_total", "total requests", ["service", "path"])
KINDS = ("explain", "gaps", "rewrite")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    register_with_consul(SERVICE_NAME, PORT)
    yield


app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)


class ExplainIn(BaseModel):
    resume_id: str
    job_id: str
    kind: str = "explain"


def _get(url: str, not_found: str) -> dict:
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url)
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail=not_found)
        r.raise_for_status()
        return r.json()


def fetch_resume(resume_id: str) -> dict:
    return _get(f"{RESUME_API}/api/v1/resumes/{resume_id}", "resume not found")


def fetch_job(job_id: str) -> dict:
    return _get(f"{JOB_API}/internal/jobs/{job_id}", "job not found")


def fetch_match(resume_id: str, job_id: str) -> dict:
    return _get(f"{MATCH_API}/internal/matches/resume/{resume_id}/job/{job_id}", "match not found, run match first")


@app.get("/health")
def health():
    return {"service": SERVICE_NAME, "status": "ok", "backend": os.getenv("LLM_BACKEND", "heuristic")}


@app.get("/api/v1/explain/health")
def explain_health():
    REQUESTS.labels(SERVICE_NAME, "/api/v1/explain/health").inc()
    return {"service": SERVICE_NAME, "status": "ok"}


@app.post("/api/v1/explain", status_code=201)
def explain(body: ExplainIn, db: Session = Depends(get_db), user: dict = Depends(current_user)):
    if body.kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {KINDS}")
    try:
        resume = fetch_resume(body.resume_id)
        job = fetch_job(body.job_id)
        match = fetch_match(body.resume_id, body.job_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=502, detail="downstream unavailable")
    if not resume.get("parsed"):
        raise HTTPException(status_code=409, detail="resume not parsed yet")
    context, sections = pack_context(resume["parsed"])
    prompt = PROMPTS[body.kind](job, match, context)
    output, model = generate(body.kind, prompt, job, match, sections)
    row = GenerationLog(
        resume_id=body.resume_id,
        job_id=body.job_id,
        kind=body.kind,
        model=model,
        context_ids=json.dumps(sections),
        prompt=prompt,
        output=output,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    REQUESTS.labels(SERVICE_NAME, "/api/v1/explain").inc()
    return {"log_id": row.id, "kind": body.kind, "model": model, "citations": sections, "output": output}


@app.get("/api/v1/explain/logs")
def list_logs(resume_id: str = "", job_id: str = "", limit: int = 20, db: Session = Depends(get_db), user: dict = Depends(current_user)):
    q = db.query(GenerationLog).order_by(GenerationLog.created_at.desc())
    if resume_id:
        q = q.filter(GenerationLog.resume_id == resume_id)
    if job_id:
        q = q.filter(GenerationLog.job_id == job_id)
    return [
        {"log_id": r.id, "kind": r.kind, "model": r.model, "citations": json.loads(r.context_ids), "output": r.output}
        for r in q.limit(min(limit, 100)).all()
    ]


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
