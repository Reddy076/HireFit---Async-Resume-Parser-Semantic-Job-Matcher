import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.metrics import dcg_at_k, ndcg_at_k, recall_at_k


def test_recall_basic():
    assert recall_at_k(["a", "b", "c"], {"a", "c"}, 2) == 0.5
    assert recall_at_k(["a", "b", "c"], {"a", "c"}, 3) == 1.0
    assert recall_at_k(["a"], set(), 1) == 0.0


def test_ndcg_perfect_is_one():
    gains = {"a": 3.0, "b": 1.0}
    assert ndcg_at_k(["a", "b"], gains, 2) == 1.0


def test_ndcg_worst_below_one():
    gains = {"a": 3.0, "b": 1.0}
    assert 0.0 < ndcg_at_k(["b", "a"], gains, 2) < 1.0


def test_ndcg_no_relevant_is_zero():
    assert ndcg_at_k(["a"], {}, 1) == 0.0
    assert dcg_at_k(["a"], {}, 1) == 0.0
