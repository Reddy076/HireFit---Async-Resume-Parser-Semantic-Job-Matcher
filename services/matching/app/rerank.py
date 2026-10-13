"""Rerankers: heuristic token-overlap default, cross-encoder in Docker.

Cross-encoder (ms-marco-MiniLM-L-6-v2) needs requirements-ml.txt; any load
failure falls back to heuristic so the service still boots.
"""

import logging
import os
import re

log = logging.getLogger("rerank")
MODEL_NAME = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    return set(_WORD.findall(s.lower()))


class HeuristicRerank:
    name = "heuristic"

    def score(self, query: str, docs: list[str]) -> list[float]:
        q = _tokens(query)
        out = []
        for doc in docs:
            d = _tokens(doc)
            if not q or not d:
                out.append(0.0)
                continue
            out.append(len(q & d) / ((len(q) * len(d)) ** 0.5))
        return out


class CERerank:
    name = "ce"

    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(MODEL_NAME)

    def score(self, query: str, docs: list[str]) -> list[float]:
        return [float(s) for s in self.model.predict([(query, d) for d in docs])]


_reranker = None


def get_reranker():
    global _reranker
    if _reranker is not None:
        return _reranker
    if os.getenv("RERANK_BACKEND", "heuristic") == "ce":
        try:
            _reranker = CERerank()
            log.info("rerank backend: ce (%s)", MODEL_NAME)
            return _reranker
        except Exception as e:
            log.warning("ce backend failed, falling back to heuristic: %s", e)
    _reranker = HeuristicRerank()
    return _reranker
