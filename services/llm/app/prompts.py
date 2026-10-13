"""Prompt builders: deterministic context packing shared by all backends.

Context budget: top sections by length, truncated so prompts stay small.
Citations use [section] markers that map to resume sections.
"""

MAX_CHARS = 3000


def pack_context(parsed: dict, max_chars: int = MAX_CHARS) -> tuple[str, list[str]]:
    """Return (context_text, section_ids) with the largest sections first."""
    items = [(k, v) for k, v in parsed.items() if not k.startswith("_") and (v or "").strip()]
    items.sort(key=lambda kv: len(kv[1]), reverse=True)
    parts, ids, budget = [], [], max_chars
    for section, body in items:
        chunk = body.strip()[:budget]
        if not chunk:
            continue
        parts.append(f"[{section}]\n{chunk}")
        ids.append(section)
        budget -= len(chunk)
        if budget <= 0:
            break
    return "\n\n".join(parts), ids


def explain_prompt(job: dict, match: dict, context: str) -> str:
    return (
        "You are a hiring assistant. Explain the candidate fit using ONLY the context. "
        "Cite evidence as [section].\n"
        f"Job: {job.get('title', '')}\n"
        f"Skills: {', '.join(job.get('skills', []))}\n"
        f"Scores: final={match.get('final_score', 0):.2f} rerank={match.get('ce_score', 0):.2f} skills={match.get('skill_score', 0):.2f}\n"
        f"Matched: {', '.join(match.get('matched_skills', [])) or 'none'}\n"
        f"Missing: {', '.join(match.get('missing_skills', [])) or 'none'}\n"
        f"Context:\n{context}"
    )


def gaps_prompt(job: dict, match: dict, context: str) -> str:
    return (
        "You are a career coach. For each missing skill propose one concrete 2-week learning step. "
        "Use ONLY the context and missing list.\n"
        f"Missing: {', '.join(match.get('missing_skills', [])) or 'none'}\n"
        f"Candidate context:\n{context}"
    )


def rewrite_prompt(job: dict, match: dict, context: str) -> str:
    return (
        "Rewrite the candidate's experience as 3 resume bullets tailored to the job. "
        "Only reuse facts from the context; cite the source section per bullet.\n"
        f"Job: {job.get('title', '')} | Skills: {', '.join(job.get('skills', []))}\n"
        f"Context:\n{context}"
    )


PROMPTS = {"explain": explain_prompt, "gaps": gaps_prompt, "rewrite": rewrite_prompt}
