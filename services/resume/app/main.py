import os
import uuid
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from sqlalchemy.orm import Session
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "common"))
from consul import register_with_consul
from .db import Base, engine, get_db
from .models import Resume
from .s3 import put_bytes
from .events import publish

PORT = int(os.getenv("PORT", "8002"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "resume-service")
REQUESTS = Counter("http_requests_total", "total requests", ["service", "path"])
MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    register_with_consul(SERVICE_NAME, PORT)
    yield


app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)


@app.get("/health")
def health():
    return {"service": SERVICE_NAME, "status": "ok"}


@app.get("/api/v1/resumes/health")
def resume_health():
    REQUESTS.labels(SERVICE_NAME, "/api/v1/resumes/health").inc()
    return {"service": SERVICE_NAME, "status": "ok", "queue": "kafka:resume.uploaded"}


@app.post("/api/v1/resumes/upload", status_code=202)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="only PDF supported in cycle 1")
    data = await file.read()
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="empty or >10MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="not a valid PDF")
    resume_id = str(uuid.uuid4())
    key = f"{resume_id}/{file.filename or 'resume.pdf'}"
    put_bytes(key, data, content_type="application/pdf")
    row = Resume(id=resume_id, s3_key=key, filename=file.filename or "resume.pdf", size_bytes=len(data))
    db.add(row)
    db.commit()
    publish("resume.uploaded", {"resume_id": resume_id, "s3_key": key})
    REQUESTS.labels(SERVICE_NAME, "/api/v1/resumes/upload").inc()
    return {"resume_id": resume_id, "status": "queued"}


@app.get("/api/v1/resumes/{resume_id}")
def get_resume(resume_id: str, db: Session = Depends(get_db)):
    row = db.get(Resume, resume_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "resume_id": row.id,
        "filename": row.filename,
        "size_bytes": row.size_bytes,
        "status": row.status,
        "s3_key": row.s3_key,
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
