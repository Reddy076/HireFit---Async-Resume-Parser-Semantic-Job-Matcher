"""LLM backends: heuristic default, Ollama when configured.

Heuristic is a template renderer over real scores/skills — deterministic and
offline. Ollama (llama3.1 etc.) is tried only with LLM_BACKEND=ollama and
falls back to heuristic on any failure so deploys stay green.
"""

import logging
import os

log = logging.getLogger("llm")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


def heuristic_generate(kind: str, job: dict, match: dict, sections: list[str]) -> str:
    title = job.get("title", "this role")
    final = match.get("final_score", 0)
    matched = match.get("matched_skills", [])
    missing = match.get("missing_skills", [])
    cites = " ".join(f"[{s}]" for s in sections) or "[header]"
    if kind == "explain":
        lines = [
            f"Fit {final:.0%} for {title}.",
            f"Evidence: {cites} show {', '.join(matched) or 'no listed-skill overlap'}.",
        ]
        if missing:
            lines.append(f"Gaps to address: {', '.join(missing)}.")
        else:
            lines.append("No skill gaps against the listed requirements.")
        return " ".join(lines)
    if kind == "gaps":
        if not missing:
            return "No missing skills. Next step: deepen the strongest area with a portfolio piece."
        steps = [f"{s}: 2-week plan — docs + one mini-project using {s}." for s in missing]
        return "Learning plan: " + " ".join(steps)
    # rewrite
    skills = ", ".join(matched) or "core experience"
    return (
        f"- Shipped production work using {skills} {cites}.\n"
        f"- Improved reliability/perf of services in {title}-relevant stack {cites}.\n"
        f"- Collaborated with stakeholders to deliver {title} outcomes {cites}."
    )


class OllamaBackend:
    name = f"ollama:{OLLAMA_MODEL}"

    def generate(self, prompt: str) -> str:
        import httpx

        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            return str(r.json().get("response", ""))


def generate(kind: str, prompt: str, job: dict, match: dict, sections: list[str]) -> tuple[str, str]:
    """Return (output, model_name), falling back to heuristic on any LLM failure."""
    if os.getenv("LLM_BACKEND", "heuristic") == "ollama":
        try:
            return OllamaBackend().generate(prompt), OllamaBackend.name
        except Exception as e:
            log.warning("ollama failed, falling back to heuristic: %s", e)
    return heuristic_generate(kind, job, match, sections), "heuristic"
