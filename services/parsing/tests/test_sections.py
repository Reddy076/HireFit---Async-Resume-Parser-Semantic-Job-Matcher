import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.sections import detect_heading, split_sections


def test_detect_heading_exact():
    assert detect_heading("Experience") == "experience"
    assert detect_heading("TECHNICAL SKILLS") == "skills"
    assert detect_heading("Education") == "education"


def test_detect_heading_ignores_body_lines():
    assert detect_heading("Built microservices with FastAPI and Kafka in production") is None
    assert detect_heading("Senior Backend Engineer, 2021-2024, Acme Corp") is None
    assert detect_heading("") is None


def test_split_sections_assigns_all_parts():
    text = """Jane Doe
jane@example.com

Experience
Backend Engineer at Acme (2021-2024)
Shipped billing service.

Skills
Python, Kafka, Postgres

Education
B.Tech, 2021
"""
    out = split_sections(text)
    assert "jane@example.com" in out["header"].lower()
    assert "Acme" in out["experience"]
    assert "Kafka" in out["skills"]
    assert "B.Tech" in out["education"]


def test_split_sections_no_headings_all_header():
    out = split_sections("Just some text\nMore text")
    assert set(out) == {"header"}
