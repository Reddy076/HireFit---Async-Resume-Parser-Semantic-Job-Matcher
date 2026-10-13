import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import fitz
import app.worker as worker
from app.worker import handle_event


def make_pdf_bytes(lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 15
    buf = bytes(doc.tobytes())
    doc.close()
    return buf


def test_handle_event_parsed_path(monkeypatch):
    pdf = make_pdf_bytes(["Jane Doe", "Skills", "Python, Kafka"])
    monkeypatch.setattr(worker, "s3_get", lambda key: pdf)
    monkeypatch.setattr(worker, "producer", lambda: None)

    patched = {}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def patch(self, url, json):
            patched["url"] = url
            patched["json"] = json
            return None

    monkeypatch.setattr(worker.httpx, "Client", lambda timeout: FakeClient())
    out = handle_event({"resume_id": "r1", "s3_key": "r1/r.pdf"})
    assert out == {"resume_id": "r1", "status": "parsed"}
    assert patched["url"].endswith("/internal/resumes/r1/parsed")
    assert "Kafka" in patched["json"]["parsed"]["skills"]


def test_handle_event_scanned_marks_needs_ocr(monkeypatch):
    doc = fitz.open()
    doc.new_page()
    pdf = bytes(doc.tobytes())
    doc.close()
    monkeypatch.setattr(worker, "s3_get", lambda key: pdf)
    monkeypatch.setattr(worker, "producer", lambda: None)

    patched = {}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def patch(self, url, json):
            patched["json"] = json
            return None

    monkeypatch.setattr(worker.httpx, "Client", lambda timeout: FakeClient())
    out = handle_event({"resume_id": "r2", "s3_key": "r2/r.pdf"})
    assert out["status"] == "needs_ocr"
    assert patched["json"]["parsed"]["_needs_ocr"] is True
