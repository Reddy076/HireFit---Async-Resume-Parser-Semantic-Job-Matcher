import io
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_resume.db"
os.environ["MAX_UPLOAD_BYTES"] = str(10 * 1024 * 1024)

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.main as resume_main
from app.db import Base, get_db

resume_main.register_with_consul = lambda *a, **k: None
Base.metadata.create_all = (lambda *a, **k: None)  # noqa: E731

test_engine = create_engine(
    "sqlite:///./test_resume.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
Base.metadata.tables["resumes"].create(bind=test_engine, checkfirst=True)

calls = {"s3": [], "events": []}
resume_main.put_bytes = lambda key, data, content_type="application/pdf": calls["s3"].append((key, len(data)))
resume_main.publish = lambda topic, payload: calls["events"].append((topic, payload)) or True


def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


resume_main.app.dependency_overrides[get_db] = override_db
client = TestClient(resume_main.app)

VALID_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def setup_module():
    Base.metadata.tables["resumes"].drop(bind=test_engine, checkfirst=True)
    Base.metadata.tables["resumes"].create(bind=test_engine, checkfirst=True)
    calls["s3"].clear()
    calls["events"].clear()


def _upload(data: bytes, filename="r.pdf", ctype="application/pdf"):
    return client.post(
        "/api/v1/resumes/upload",
        files={"file": (filename, io.BytesIO(data), ctype)},
    )


def test_health():
    assert client.get("/health").status_code == 200
    body = client.get("/api/v1/resumes/health").json()
    assert body["status"] == "ok"


def test_reject_non_pdf_content_type_415():
    r = _upload(b"hello", ctype="text/plain")
    assert r.status_code == 415


def test_reject_fake_pdf_422():
    r = _upload(b"not a pdf at all")
    assert r.status_code == 422


def test_reject_empty_413():
    r = _upload(b"")
    assert r.status_code == 413


def test_reject_oversize_413(monkeypatch):
    monkeypatch.setattr(resume_main, "MAX_BYTES", 10)
    r = _upload(VALID_PDF)
    assert r.status_code == 413


def test_upload_ok_202_and_side_effects():
    r = _upload(VALID_PDF)
    assert r.status_code == 202, r.text
    resume_id = r.json()["resume_id"]
    assert r.json()["status"] == "queued"
    assert len(calls["s3"]) == 1
    assert calls["events"][0][0] == "resume.uploaded"
    assert calls["events"][0][1]["resume_id"] == resume_id
    g = client.get(f"/api/v1/resumes/{resume_id}")
    assert g.status_code == 200
    assert g.json()["size_bytes"] == len(VALID_PDF)


def test_get_missing_404():
    assert client.get("/api/v1/resumes/does-not-exist").status_code == 404


def test_internal_set_parsed():
    r = _upload(VALID_PDF)
    resume_id = r.json()["resume_id"]
    p = client.patch(f"/internal/resumes/{resume_id}/parsed", json={"status": "parsed", "parsed": {"skills": ["python"]}})
    assert p.status_code == 200
    g = client.get(f"/api/v1/resumes/{resume_id}").json()
    assert g["status"] == "parsed"
    assert g["has_parsed"] is True
    assert g["parsed"]["skills"] == ["python"]


def test_internal_set_parsed_missing_404():
    assert client.patch("/internal/resumes/does-not-exist/parsed", json={"parsed": {}}).status_code == 404


def teardown_module():
    try:
        os.remove("test_resume.db")
    except OSError:
        pass
