"""Real-Gemini deal-quality assessment — QUOTA-GUARDED (1 real grounded call max).

Makes ONE batched grounded call over a small fixed deal list and skips (never
fails) on 429/RESOURCE_EXHAUSTED or absent key. This is the ONLY real grounded
call in this module — combined with test_clarify.py the slice makes <= 2 real
Gemini calls total, per the free-tier guard.
"""
import pytest

from graph import nodes
from tools.deal_quality import VALID_LABELS


@pytest.fixture
def _require_gemini_key():
    from config.settings import get_settings
    if not get_settings().gemini_api_key:
        pytest.skip("No AGENT_GEMINI_API_KEY set in .env")


_QUOTA_MARKERS = ("429", "resource_exhausted", "quota", "rate limit", "too many requests")


def _run_id(engine):
    from sqlalchemy.orm import Session
    from db.models import RunRow
    with Session(engine) as s:
        run = RunRow(query_type="name", query_text="Sony WH-1000XM5 headphones", status="running")
        s.add(run)
        s.commit()
        return run.id


@pytest.mark.usefixtures("_require_gemini_key")
def test_deal_quality_labels_real(_isolated_db):
    rid = _run_id(_isolated_db)
    deals = [
        {"rank": 1, "site": "Amazon.in", "price_inr": 24990,
         "reason": "Lowest verified price with strong ratings."},
        {"rank": 2, "site": "Flipkart", "price_inr": 27990,
         "reason": "Slightly higher but faster delivery."},
    ]
    try:
        out = nodes.deal_quality({
            "run_id": rid, "query_text": "Sony WH-1000XM5 headphones",
            "deals": deals, "prompt_tokens": 0, "completion_tokens": 0,
        })
    except Exception as exc:  # noqa: BLE001 — node degrades, but guard anyway
        if any(m in str(exc).lower() for m in _QUOTA_MARKERS):
            pytest.skip(f"Gemini quota exhausted — skipping real call: {exc}")
        raise

    # Every deal carries a valid label + the run never errored (degrade, not fatal).
    assert out.get("error") is None
    assert len(out["deals"]) == 2
    for d in out["deals"]:
        assert d["quality_label"] in VALID_LABELS
