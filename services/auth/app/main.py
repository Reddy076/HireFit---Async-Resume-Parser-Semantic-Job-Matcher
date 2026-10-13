import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "common"))
from consul import register_with_consul

PORT = int(os.getenv("PORT", "8001"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "auth-service")
REQUESTS = Counter("http_requests_total", "total requests", ["service", "path"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    register_with_consul(SERVICE_NAME, PORT)
    yield

app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)

@app.get("/health")
def health():
    REQUESTS.labels(SERVICE_NAME, "/health").inc()
    return {"service": SERVICE_NAME, "status": "ok"}

@app.get("/api/v1/auth/health")
def auth_health():
    REQUESTS.labels(SERVICE_NAME, "/api/v1/auth/health").inc()
    return {"service": SERVICE_NAME, "status": "ok"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
