"""Ranking metrics for offline eval (MLflow tracking lands in Cycle 10)."""
import math


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def dcg_at_k(ranked: list[str], gains: dict[str, float], k: int) -> float:
    return sum(gains.get(doc, 0.0) / math.log2(i + 2) for i, doc in enumerate(ranked[:k]))


def ndcg_at_k(ranked: list[str], gains: dict[str, float], k: int) -> float:
    ideal = dcg_at_k(sorted(gains, key=gains.get, reverse=True), gains, k)
    if ideal == 0:
        return 0.0
    return dcg_at_k(ranked, gains, k) / ideal
