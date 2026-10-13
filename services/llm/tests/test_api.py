import os

os.environ["DATABASE_URL"] = "sqlite:///./test_llm.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["LLM_BACKEND"] = "heuristic"

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.main as llm_main
from app.db import Base, get_db
from app.models import GenerationLog

llm_main.register_with_consul = lambda *a, **k: None
Base.metadata.create_all = (lambda *a, **k: None)  # noqa: E731

test_engine = create_engine(
    "sqlite:///./test_llm.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


llm_main.app.dependency_overrides[get_db] = override_db
client = TestClient(llm_main.app)


def tok(sub: str, role: str) -> str:
    return jwt.encode({"sub": sub, "role": role}, "test-secret", algorithm="HS256")


AUTH = {"Authorization": f"Bearer {tok('u1', 'candidate')}"}
PARSED = {"header": "Ann", "skills": "Python Kafka", "experience": "Built streaming billing with Python and Kafka"}
JOB = {"id": "j1", "title": "Backend Engineer", "description": "d", "skills": ["Python", "Kafka", "Go"]}
MATCH = {"resume_id": "r1", "job_id": "j1", "ret_score": 0.8, "ce_score": 0.9, "skill_score": 0.66, "final_score": 0.82, "matched_skills": ["Python", "Kafka"], "missing_skills": ["Go"]}


def setup_module():
    Base.metadata.tables["generation_logs"].drop(bind=test_engine, checkfirst=True)
    Base.metadata.tables["generation_logs"].create(bind=test_engine, checkfirst=True)
    llm_main.fetch_resume = lambda rid: {"resume_id": rid, "parsed": PARSED}
    llm_main.fetch_job = lambda jid: JOB
    llm_main.fetch_match = lambda rid, jid: MATCH


def test_explain_kinds_and_log_persisted():
    for kind in ("explain", "gaps", "rewrite"):
        r = client.post("/api/v1/explain", json={"resume_id": "r1", "job_id": "j1", "kind": kind}, headers=AUTH)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["model"] == "heuristic"
        assert body["citations"]
    with TestingSession() as db:
        assert db.query(GenerationLog).count() == 3
    logs = client.get("/api/v1/explain/logs", params={"resume_id": "r1"}, headers=AUTH).json()
    assert len(logs) == 3


def test_explain_invalid_kind_422():
    assert client.post("/api/v1/explain", json={"resume_id": "r1", "job_id": "j1", "kind": "nope"}, headers=AUTH).status_code == 422


def test_explain_requires_auth():
    assert client.post("/api/v1/explain", json={"resume_id": "r1", "job_id": "j1"}).status_code == 401


def teardown_module():
    try:
        os.remove("test_llm.db")
    except OSError:
        pass
