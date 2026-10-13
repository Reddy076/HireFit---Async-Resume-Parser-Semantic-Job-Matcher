import os

os.environ["DATABASE_URL"] = "sqlite:///./test_matching.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["RERANK_BACKEND"] = "heuristic"

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.main as match_main
from app.db import Base, get_db
from app.metrics import ndcg_at_k, recall_at_k
from app.pipeline import score_pair

match_main.register_with_consul = lambda *a, **k: None
Base.metadata.create_all = (lambda *a, **k: None)  # noqa: E731

test_engine = create_engine(
    "sqlite:///./test_matching.db",
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


match_main.app.dependency_overrides[get_db] = override_db
client = TestClient(match_main.app)


def tok(sub: str, role: str) -> str:
    return jwt.encode({"sub": sub, "role": role}, "test-secret", algorithm="HS256")


REC = {"Authorization": f"Bearer {tok('rec-1', 'recruiter')}"}
CAND = {"Authorization": f"Bearer {tok('cand-1', 'candidate')}"}

JOB = {"id": "j1", "title": "Python Kafka Backend Engineer", "description": "Build streaming services with Python and Kafka", "skills": ["Python", "Kafka", "Postgres"]}
PARSED = {
    "r1": {"header": "Ann", "skills": "Python Kafka Postgres backend engineer", "experience": "Built streaming billing with Python and Kafka"},
    "r2": {"header": "Bob", "skills": "sourdough bread baking", "experience": "Head baker for five years"},
    "r3": {"header": "Cat", "skills": "Python scripting", "experience": "Wrote Python automation scripts"},
}


def setup_module():
    Base.metadata.tables["matches"].drop(bind=test_engine, checkfirst=True)
    Base.metadata.tables["matches"].create(bind=test_engine, checkfirst=True)
    match_main.fetch_resume = lambda rid: {"resume_id": rid, "parsed": PARSED[rid]}
    match_main.fetch_job = lambda jid: JOB


def test_score_pair_ranks_relevant_text_higher():
    s1 = score_pair(JOB, PARSED["r1"])
    s2 = score_pair(JOB, PARSED["r2"])
    assert s1["final_score"] > s2["final_score"]
    assert s1["matched_skills"] == ["Python", "Kafka", "Postgres"]
    assert s2["missing_skills"] == ["Python", "Kafka", "Postgres"]


def test_single_ok_and_stored():
    r = client.post("/api/v1/match/single", json={"resume_id": "r1", "job_id": "j1"}, headers=CAND)
    assert r.status_code == 201, r.text
    assert r.json()["final_score"] > 0
    g = client.get("/api/v1/match/resume/r1/job/j1", headers=CAND)
    assert g.status_code == 200


def test_single_requires_auth():
    assert client.post("/api/v1/match/single", json={"resume_id": "r1", "job_id": "j1"}).status_code == 401


def test_internal_get_no_auth():
    client.post("/api/v1/match/single", json={"resume_id": "r1", "job_id": "j1"}, headers=CAND)
    r = client.get("/api/v1/match/resume/r1/job/j1".replace("/api/v1/match", "/internal/matches"))
    assert r.status_code == 200
    assert r.json()["resume_id"] == "r1"
    assert client.get("/internal/matches/resume/zz/job/j1").status_code == 404


def test_bulk_ranks_and_gates_role():
    match_main.search_chunks = lambda text, top_k: [
        {"resume_id": "r2", "score": 0.1},
        {"resume_id": "r1", "score": 0.9},
        {"resume_id": "r3", "score": 0.5},
    ]
    match_main.fetch_parsed = lambda rid: PARSED.get(rid)
    assert client.post("/api/v1/match/job/j1", json={}, headers=CAND).status_code == 403
    r = client.post("/api/v1/match/job/j1", json={"top_k": 50, "limit": 10}, headers=REC)
    assert r.status_code == 200, r.text
    ids = [m["resume_id"] for m in r.json()["matches"]]
    assert ids[0] == "r1"
    assert recall_at_k(ids, {"r1"}, 1) == 1.0
    assert ndcg_at_k(ids, {"r1": 3.0, "r3": 1.0}, 3) > 0.5


def teardown_module():
    try:
        os.remove("test_matching.db")
    except OSError:
        pass
