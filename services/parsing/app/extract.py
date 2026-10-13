"""Text extraction for Cycle 2: PyMuPDF with scanned-PDF detection.

LayoutLMv3 section classification lands in a later cycle behind the same
`split_sections` interface; the deterministic splitter in sections.py is the
baseline we will beat with measured F1.
"""

import fitz  # PyMuPDF


def extract_pdf(data: bytes) -> dict:
    """Return {pages, text, page_texts, needs_ocr} from raw PDF bytes."""
    if not data.startswith(b"%PDF"):
        raise ValueError("not a valid PDF")
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        page_texts = [page.get_text("text") or "" for page in doc]
    finally:
        doc.close()
    full = "\n".join(page_texts)
    return {
        "pages": len(page_texts),
        "text": full,
        "page_texts": page_texts,
        "needs_ocr": not full.strip(),
    }
