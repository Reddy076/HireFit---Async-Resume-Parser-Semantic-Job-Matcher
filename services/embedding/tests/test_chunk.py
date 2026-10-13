import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.chunk import chunk_sections, chunk_text


def test_chunk_text_window_overlap():
    words = [f"w{i}" for i in range(250)]
    chunks = chunk_text(" ".join(words), words=100, overlap=10)
    assert len(chunks) == 3
    assert chunks[0].split()[-10:] == chunks[1].split()[:10]
    assert chunks[1].split()[-1] == "w199" or chunks[2].split()[-1] == "w249"


def test_chunk_text_short_and_empty():
    assert chunk_text("hello world") == ["hello world"]
    assert chunk_text("   ") == []


def test_chunk_sections_skips_metadata():
    parsed = {"header": "Jane", "skills": "Python Kafka", "_pages": 2, "empty": "  "}
    out = chunk_sections(parsed)
    assert (out[0][0], out[0][1]) == ("header", "Jane")
    assert out[1] == ("skills", "Python Kafka")
    assert len(out) == 2
