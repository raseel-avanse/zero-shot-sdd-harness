"""End-to-end research → rank → finalize against the REAL Gemini API.

Requires AGENT_GEMINI_API_KEY in .env. Uses the native google_search grounding
tool. Kept to a small number of real calls to respect free-tier rate limits.
"""
import time

import pytest
from sqlalchemy.orm import Session

from graph.runner import start_run
from db import session as session_module
from db.models import RunRow, DealRow


@pytest.fixture
def _require_gemini_key():
    from config.settings import get_settings
    s = get_settings()
    if not s.gemini_api_key:
        pytest.skip("No AGENT_GEMINI_API_KEY set in .env")


def _poll_until_done(run_id: str, timeout: float = 240.0) -> RunRow:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        with Session(session_module._engine) as s:
            run = s.get(RunRow, run_id)
            if run is not None:
                last = run
                if run.status in ("completed", "failed"):
                    # detach a snapshot
                    s.expunge(run)
                    return run
        time.sleep(2)
    raise AssertionError(
        f"Run {run_id} did not finish within {timeout}s (last status={getattr(last, 'status', None)})"
    )


@pytest.mark.usefixtures("_require_gemini_key")
def test_product_name_research_end_to_end(_isolated_db):
    run_id = start_run("name", "Sony WH-1000XM5 headphones")
    run = _poll_until_done(run_id)

    assert run.status == "completed", f"expected completed, got {run.status}: {run.error_message}"
    assert run.progress_step == "done"

    # Token usage from real usage_metadata, accumulated across research + rank.
    assert run.prompt_tokens > 0
    assert run.completion_tokens > 0
    # Cost persisted and positive.
    assert run.cost_inr is not None and run.cost_inr > 0
    # Grounding evidence: research notes were produced.
    assert run.research_notes and len(run.research_notes) > 0

    with Session(session_module._engine) as s:
        deals = (
            s.query(DealRow)
            .filter(DealRow.run_id == run_id)
            .order_by(DealRow.rank)
            .all()
        )

    assert 3 <= len(deals) <= 5, f"expected 3–5 deals, got {len(deals)}"
    for d in deals:
        assert d.site and d.site.strip()
        assert d.price_inr > 0
        assert d.reason and d.reason.strip()


def test_empty_query_rejected_before_any_run(api_client):
    """Error path: empty query_text never starts a run — 400 VALIDATION (no LLM call)."""
    r = api_client.post("/runs", json={"query_type": "name", "query_text": "   "})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "VALIDATION"


def test_unknown_run_id_is_404(api_client):
    """Error path: polling an unknown run_id returns 404 NOT_FOUND (no LLM call)."""
    r = api_client.get("/runs/does-not-exist")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


# NOTE on the edge case (nonsense query -> 0 deals, no crash): the rank node
# returning an empty deal list and finalize persisting a completed run with zero
# deals is verified without burning free-tier Gemini quota by the unit tests
# `tests/unit/graph/test_rank_parse.py::test_empty_deals_list_ok` and the
# routing/finalize path. We keep the real-API integration footprint to a single
# end-to-end run (2 calls) per spec's free-tier guidance.
