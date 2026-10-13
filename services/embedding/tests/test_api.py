import os

os.environ["DATABASE_URL"] = "sqlite:///./test_embedding.db"
os.environ["EMBED_BACKEND"] = "hash"

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.main as emb_main
from app.db import Base, get_db
from app.models import JobEmbedding, ResumeChunk

emb_main.register_with_consul = lambda *a, **k: None
Base.metadata.create_all = (lambda *a, **k: None)  # noqa: E731

test_engine = create_engine(
    "sqlite:///./test_embedding.db",
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


emb_main.app.dependency_overrides[get_db] = override_db
client = TestClient(emb_main.app)

RESUME_A = {"resume_id": "ra", "parsed": {"header": "Ann", "skills": "Python Kafka Postgres backend engineer"}}
RESUME_B = {"resume_id": "rb", "parsed": {"header": "Bob", "skills": "sourdough bread baking recipes"}}
JOB = {"id": "j1", "title": "Backend Engineer", "description": "Python Kafka service role", "skills": ["Python"]}


def setup_module():
    Base.metadata.tables["resume_chunks"].drop(bind=test_engine, checkfirst=True)
    Base.metadata.tables["job_embeddings"].drop(bind=test_engine, checkfirst=True)
    Base.metadata.tables["resume_chunks"].create(bind=test_engine, checkfirst=True)
    Base.metadata.tables["job_embeddings"].create(bind=test_engine, checkfirst=True)


def _seed():
    emb_main.fetch_parsed_resume = lambda rid: RESUME_A if rid == "ra" else RESUME_B
    assert client.post("/api/v1/embeddings/resumes/ra").json()["chunks"] >= 1
    assert client.post("/api/v1/embeddings/resumes/rb").json()["chunks"] >= 1


def test_health_reports_backend():
    body = client.get("/health").json()
    assert body["backend"] == "hash"
    assert body["dim"] == 768


def test_embed_resume_and_rerun_idempotent():
    emb_main.fetch_parsed_resume = lambda rid: RESUME_A
    first = client.post("/api/v1/embeddings/resumes/ra").json()["chunks"]
    second = client.post("/api/v1/embeddings/resumes/ra").json()["chunks"]
    assert first == second
    with TestingSession() as db:
        assert db.query(ResumeChunk).filter(ResumeChunk.resume_id == "ra").count() == first


def test_embed_resume_unparsed_409():
    emb_main.fetch_parsed_resume = lambda rid: {"resume_id": rid, "parsed": None}
    assert client.post("/api/v1/embeddings/resumes/rz").status_code == 409


def test_embed_job_upsert():
    emb_main.fetch_job = lambda jid: JOB
    assert client.post("/api/v1/embeddings/jobs/j1").json() == {"job_id": "j1"}
    assert client.post("/api/v1/embeddings/jobs/j1").json() == {"job_id": "j1"}
    with TestingSession() as db:
        assert db.query(JobEmbedding).count() == 1


def test_search_ranks_relevant_resume_first():
    _seed()
    hits = client.post("/api/v1/embeddings/search", json={"text": "python backend engineer", "top_k": 10}).json()["hits"]
    assert hits[0]["resume_id"] == "ra"
    assert hits[0]["score"] > 0


def test_search_empty_query_422():
    assert client.post("/api/v1/embeddings/search", json={"text": "  "}).status_code == 422


def teardown_module():
    try:
        os.remove("test_embedding.db")
    except OSError:
        pass
