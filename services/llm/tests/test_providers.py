import os

os.environ["LLM_BACKEND"] = "heuristic"

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.providers import generate, heuristic_generate

JOB = {"title": "Backend Engineer", "skills": ["Python", "Kafka"]}
MATCH = {"final_score": 0.82, "ce_score": 0.9, "skill_score": 0.66, "matched_skills": ["Python"], "missing_skills": ["Kafka"]}


def test_heuristic_explain_cites_and_scores():
    out = heuristic_generate("explain", JOB, MATCH, ["experience", "skills"])
    assert "[experience]" in out and "[skills]" in out
    assert "82%" in out and "Kafka" in out


def test_heuristic_gaps_plan_per_skill():
    out = heuristic_generate("gaps", JOB, MATCH, ["skills"])
    assert "Kafka" in out and "2-week" in out


def test_heuristic_gaps_none_missing():
    out = heuristic_generate("gaps", JOB, {**MATCH, "missing_skills": []}, ["skills"])
    assert "No missing skills" in out


def test_heuristic_rewrite_bullets():
    out = heuristic_generate("rewrite", JOB, MATCH, ["experience"])
    assert out.count("\n- ") >= 2 or out.startswith("- ")


def test_generate_falls_back_when_ollama_down(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    out, model = generate("explain", "prompt", JOB, MATCH, ["skills"])
    assert model == "heuristic"
    assert "[skills]" in out
