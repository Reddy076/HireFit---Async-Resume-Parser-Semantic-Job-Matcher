import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import fitz
import pytest
from app.extract import extract_pdf


def make_pdf(lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 15
    buf = doc.tobytes()
    doc.close()
    return bytes(buf)


def test_extract_roundtrip():
    data = make_pdf(["Jane Doe", "Experience", "Built things at Acme"])
    out = extract_pdf(data)
    assert out["pages"] == 1
    assert "Acme" in out["text"]
    assert out["needs_ocr"] is False


def test_extract_scanned_pdf_flags_ocr():
    doc = fitz.open()
    doc.new_page()  # blank page, no text layer
    buf = bytes(doc.tobytes())
    doc.close()
    out = extract_pdf(buf)
    assert out["needs_ocr"] is True


def test_extract_invalid_raises():
    with pytest.raises(ValueError):
        extract_pdf(b"definitely not a pdf")
