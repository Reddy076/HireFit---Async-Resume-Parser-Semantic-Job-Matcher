import os

os.environ["DATABASE_URL"] = "sqlite:///./test_job.db"
os.environ["JWT_SECRET"] = "test-secret"

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.main as job_main
from app.db import Base, get_db

job_main.register_with_consul = lambda *a, **k: None
Base.metadata.create_all = (lambda *a, **k: None)  # noqa: E731

test_engine = create_engine(
    "sqlite:///./test_job.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

published = []
job_main.publish = lambda topic, payload: published.append((topic, payload)) or True


def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


job_main.app.dependency_overrides[get_db] = override_db
client = TestClient(job_main.app)


def tok(sub: str, role: str) -> str:
    return jwt.encode({"sub": sub, "role": role}, "test-secret", algorithm="HS256")


REC = {"Authorization": f"Bearer {tok('rec-1', 'recruiter')}"}
REC2 = {"Authorization": f"Bearer {tok('rec-2', 'recruiter')}"}
CAND = {"Authorization": f"Bearer {tok('cand-1', 'candidate')}"}
PAYLOAD = {"title": "Backend Engineer", "description": "FastAPI + Kafka role", "skills": ["Python", "Kafka"]}


def setup_module():
    Base.metadata.tables["jobs"].drop(bind=test_engine, checkfirst=True)
    Base.metadata.tables["jobs"].create(bind=test_engine, checkfirst=True)
    published.clear()


def test_health():
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/jobs/health").status_code == 200


def test_create_no_token_401():
    assert client.post("/api/v1/jobs", json=PAYLOAD).status_code == 401


def test_create_candidate_403():
    assert client.post("/api/v1/jobs", json=PAYLOAD, headers=CAND).status_code == 403


def test_create_invalid_422():
    assert client.post("/api/v1/jobs", json={"title": "", "description": "x"}, headers=REC).status_code == 422


def test_create_ok_201_and_event():
    r = client.post("/api/v1/jobs", json=PAYLOAD, headers=REC)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["skills"] == ["Python", "Kafka"]
    assert body["created_by"] == "rec-1"
    assert published[-1] == ("job.created", {"job_id": body["id"]})


def test_list_and_search():
    assert len(client.get("/api/v1/jobs", headers=REC).json()) >= 1
    assert len(client.get("/api/v1/jobs", params={"q": "Backend"}, headers=CAND).json()) >= 1
    assert client.get("/api/v1/jobs", params={"q": "no-such-role-xyz"}, headers=REC).json() == []
    assert client.get("/api/v1/jobs").status_code == 401


def test_get_and_missing():
    job_id = client.post("/api/v1/jobs", json=PAYLOAD, headers=REC).json()["id"]
    assert client.get(f"/api/v1/jobs/{job_id}", headers=CAND).status_code == 200
    assert client.get("/api/v1/jobs/does-not-exist", headers=REC).status_code == 404


def test_update_owner_ok_other_recruiter_forbidden():
    job_id = client.post("/api/v1/jobs", json=PAYLOAD, headers=REC).json()["id"]
    assert client.patch(f"/api/v1/jobs/{job_id}", json={"title": "Senior Backend"}, headers=REC2).status_code == 403
    r = client.patch(f"/api/v1/jobs/{job_id}", json={"title": "Senior Backend", "skills": ["Go"]}, headers=REC)
    assert r.status_code == 200
    assert r.json()["title"] == "Senior Backend"
    assert r.json()["skills"] == ["Go"]


def test_delete_owner_ok_and_gone():
    job_id = client.post("/api/v1/jobs", json=PAYLOAD, headers=REC).json()["id"]
    assert client.delete(f"/api/v1/jobs/{job_id}", headers=REC2).status_code == 403
    assert client.delete(f"/api/v1/jobs/{job_id}", headers=REC).status_code == 204
    assert client.get(f"/api/v1/jobs/{job_id}", headers=REC).status_code == 404


def teardown_module():
    try:
        os.remove("test_job.db")
    except OSError:
        pass
