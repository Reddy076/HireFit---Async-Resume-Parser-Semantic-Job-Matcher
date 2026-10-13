"""Index + search pipeline shared by the HTTP API and the kafka worker."""

import json
import os

import httpx
import numpy as np
from sqlalchemy.orm import Session

from .backends import cosine_search, get_backend
from .chunk import chunk_sections
from .models import JobEmbedding, ResumeChunk

RESUME_API = os.getenv("RESUME_API", "http://resume-service:8002")
JOB_API = os.getenv("JOB_API", "http://job-service:8004")


def fetch_parsed_resume(resume_id: str) -> dict:
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{RESUME_API}/api/v1/resumes/{resume_id}")
        r.raise_for_status()
        return r.json()


def fetch_job(job_id: str) -> dict:
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{JOB_API}/internal/jobs/{job_id}")
        r.raise_for_status()
        return r.json()


def job_text(job: dict) -> str:
    return "\n".join([job.get("title", ""), job.get("description", ""), " ".join(job.get("skills", []))])


def index_resume(db: Session, resume_id: str, parsed: dict) -> int:
    backend = get_backend()
    pairs = chunk_sections(parsed)
    if not pairs:
        return 0
    vecs = backend.encode([text for _, text in pairs])
    db.query(ResumeChunk).filter(ResumeChunk.resume_id == resume_id).delete()
    for (section, text), vec in zip(pairs, vecs):
        db.add(ResumeChunk(resume_id=resume_id, section=section, text=text, embedding_json=json.dumps(vec.tolist())))
    db.commit()
    return len(pairs)


def index_job(db: Session, job: dict) -> str:
    backend = get_backend()
    text = job_text(job)
    vec = backend.encode([text])[0]
    row = db.get(JobEmbedding, job["id"])
    if row is None:
        db.add(JobEmbedding(job_id=job["id"], text=text, embedding_json=json.dumps(vec.tolist())))
    else:
        row.text = text
        row.embedding_json = json.dumps(vec.tolist())
    db.commit()
    return str(job["id"])


def search_resumes(db: Session, query: str, top_k: int = 50) -> list[dict]:
    backend = get_backend()
    rows = db.query(ResumeChunk).all()
    if not rows:
        return []
    q = backend.encode([query])[0]
    mat = np.asarray([json.loads(r.embedding_json) for r in rows], dtype=np.float64)
    idx, scores = cosine_search(q, mat, top_k)
    return [
        {"resume_id": rows[i].resume_id, "section": rows[i].section, "score": scores[n], "snippet": rows[i].text[:280]}
        for n, i in enumerate(idx)
    ]
