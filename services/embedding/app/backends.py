"""Embedding backends behind one interface.

- st: sentence-transformers/all-mpnet-base-v2 (768d, needs requirements-ml.txt).
- hash: dependency-free deterministic baseline, same 768d shape.
Switching backends requires re-embedding (see POST /api/v1/embeddings/reindex-note).
"""

import hashlib
import logging
import os
import re

import numpy as np

log = logging.getLogger("embeddings")
DIM = 768
MODEL_NAME = os.getenv("EMBED_MODEL", "sentence-transformers/all-mpnet-base-v2")
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    return set(_WORD.findall(s.lower()))


class HashBackend:
    name = "hash"
    dim = DIM

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), DIM), dtype=np.float64)
        for i, text in enumerate(texts):
            for tok in _tokens(text):
                h = int(hashlib.sha256(tok.encode()).hexdigest()[:8], 16)
                for k in range(4):
                    vecs[i, (h + k * 0x9E3779B9) % DIM] += 1.0
            norm = float(np.linalg.norm(vecs[i]))
            if norm > 0:
                vecs[i] /= norm
        return vecs


class STBackend:
    name = "st"
    dim = DIM

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(MODEL_NAME)

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype=np.float64)


_backend = None


def get_backend():
    global _backend
    if _backend is not None:
        return _backend
    if os.getenv("EMBED_BACKEND", "hash") == "st":
        try:
            _backend = STBackend()
            log.info("embedding backend: st (%s)", MODEL_NAME)
            return _backend
        except Exception as e:
            log.warning("st backend failed, falling back to hash: %s", e)
    _backend = HashBackend()
    return _backend


def cosine_search(query_vec: np.ndarray, matrix: np.ndarray, top_k: int) -> tuple[list[int], list[float]]:
    if len(matrix) == 0:
        return [], []
    scores = matrix @ query_vec
    k = min(top_k, len(matrix))
    idx = np.argsort(-scores, kind="stable")[:k]
    return [int(i) for i in idx], [float(scores[i]) for i in idx]
