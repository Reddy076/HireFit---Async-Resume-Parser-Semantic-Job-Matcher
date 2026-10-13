import os

os.environ["EMBED_BACKEND"] = "hash"

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
from app.backends import HashBackend, cosine_search


def test_hash_deterministic_and_normalized():
    b = HashBackend()
    a = b.encode(["Python Kafka Postgres"])
    c = b.encode(["Python Kafka Postgres"])
    assert a.shape == (1, 768)
    assert np.allclose(a, c)
    assert abs(float(np.linalg.norm(a[0])) - 1.0) < 1e-9


def test_hash_ranks_related_first():
    b = HashBackend()
    mat = b.encode(["Python Kafka backend engineer", "sourdough bread baking recipes"])
    q = b.encode(["python backend engineer"])[0]
    idx, scores = cosine_search(q, mat, top_k=2)
    assert idx[0] == 0
    assert scores[0] > scores[1]


def test_cosine_search_empty_and_topk_cap():
    assert cosine_search(np.zeros(768), np.zeros((0, 768)), 50) == ([], [])
    b = HashBackend()
    mat = b.encode(["a", "b", "c"])
    idx, scores = cosine_search(b.encode(["a"])[0], mat, top_k=50)
    assert len(idx) == 3
