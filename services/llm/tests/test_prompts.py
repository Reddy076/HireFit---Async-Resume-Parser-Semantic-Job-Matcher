import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.prompts import pack_context

PARSED = {
    "header": "Ann",
    "skills": "Python Kafka",
    "experience": "Built streaming billing with Python and Kafka over three years",
    "_pages": 1,
}


def test_pack_context_skips_metadata_and_orders_by_size():
    ctx, ids = pack_context(PARSED, max_chars=10000)
    assert "_pages" not in ids
    assert ids[0] == "experience"
    assert "[experience]" in ctx


def test_pack_context_budget_truncates():
    ctx, ids = pack_context(PARSED, max_chars=20)
    assert len(ctx) <= 60
    assert ids
