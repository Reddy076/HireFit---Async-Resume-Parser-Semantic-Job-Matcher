"""Pair scoring + bulk ranking. Pure logic; HTTP fetching lives in main.py."""

import json

from sqlalchemy.orm import Session

from .models import Match
from .rerank import get_reranker

CE_WEIGHT = 0.7
SKILL_WEIGHT = 0.3


def job_text(job: dict) -> str:
    return "\n".join([job.get("title", ""), job.get("description", ""), " ".join(job.get("skills", []))])


def resume_text(parsed: dict) -> str:
    return "\n".join(v for k, v in parsed.items() if not k.startswith("_") and (v or "").strip())


def skill_split(job_skills: list[str], text: str) -> tuple[list[str], list[str], float]:
    low = text.lower()
    matched = [s for s in job_skills if s.strip() and s.strip().lower() in low]
    missing = [s for s in job_skills if s not in matched]
    return matched, missing, len(matched) / max(1, len(job_skills))


def score_pair(job: dict, parsed: dict) -> dict:
    jt, rt = job_text(job), resume_text(parsed)
    ce = float(get_reranker().score(jt, [rt])[0])
    matched, missing, skill = skill_split(job.get("skills", []), rt)
    return {
        "ce_score": ce,
        "skill_score": skill,
        "final_score": CE_WEIGHT * ce + SKILL_WEIGHT * skill,
        "matched_skills": matched,
        "missing_skills": missing,
    }


def store_match(db: Session, resume_id: str, job_id: str, scores: dict, ret_score: float | None = None) -> Match:
    row = db.query(Match).filter(Match.resume_id == resume_id, Match.job_id == job_id).first()
    if row is None:
        row = Match(resume_id=resume_id, job_id=job_id)
        db.add(row)
    row.ret_score = ret_score
    row.ce_score = scores["ce_score"]
    row.skill_score = scores["skill_score"]
    row.final_score = scores["final_score"]
    row.matched_json = json.dumps(scores["matched_skills"])
    row.missing_json = json.dumps(scores["missing_skills"])
    db.commit()
    db.refresh(row)
    return row


def rank_candidates(db: Session, job: dict, hits: list[dict], fetch_parsed, limit: int = 20) -> list[dict]:
    """hits: [{resume_id, score}] from embedding search. Returns ranked match dicts."""
    best: dict[str, float] = {}
    for hit in hits:
        rid = hit["resume_id"]
        best[rid] = max(best.get(rid, 0.0), float(hit.get("score", 0.0)))
    ranked = []
    for resume_id in sorted(best, key=best.get, reverse=True):
        parsed = fetch_parsed(resume_id)
        if not parsed:
            continue
        scores = score_pair(job, parsed)
        row = store_match(db, resume_id, str(job["id"]), scores, ret_score=best[resume_id])
        ranked.append(_to_dict(row))
    ranked.sort(key=lambda m: m["final_score"], reverse=True)
    return ranked[:limit]


def _to_dict(row: Match) -> dict:
    return {
        "resume_id": row.resume_id,
        "job_id": row.job_id,
        "ret_score": row.ret_score,
        "ce_score": row.ce_score,
        "skill_score": row.skill_score,
        "final_score": row.final_score,
        "matched_skills": json.loads(row.matched_json),
        "missing_skills": json.loads(row.missing_json),
    }
