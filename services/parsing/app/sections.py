"""Deterministic resume section splitter (baseline for Cycle 2)."""

import re

HEADINGS = {
    "experience": ("experience", "experiences", "work experience", "employment", "work history"),
    "skills": ("skills", "skill", "technical skills", "core skills", "competencies", "tech stack"),
    "education": ("education", "academic", "qualification", "qualifications"),
    "projects": ("projects", "project", "personal projects"),
    "certifications": ("certifications", "certification", "certificate", "licenses"),
    "summary": ("summary", "objective", "profile", "about me"),
}

MAX_HEADING_LEN = 48


def _normalize(line: str) -> str:
    return re.sub(r"[^a-z ]", "", line.strip().lower()).strip()


def detect_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > MAX_HEADING_LEN:
        return None
    norm = _normalize(stripped)
    if not norm:
        return None
    for section, keys in HEADINGS.items():
        for key in keys:
            if norm == key or norm.startswith(key + " ") or norm.endswith(" " + key):
                return section
    return None


def split_sections(full_text: str) -> dict:
    """Split resume text into sections. Lines before the first heading -> header."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for raw in full_text.splitlines():
        if not raw.strip():
            continue
        heading = detect_heading(raw)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(raw.rstrip())
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}
