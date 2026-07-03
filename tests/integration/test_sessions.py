"""Phase-2 session tests — real Gemini via .env, isolated SQLite per test.

Covers: session creation on upload, multi-turn persistence + replay shape,
the headline follow-up-uses-context capability, dataframe_loaded/eviction, and
the SESSION_NOT_FOUND error path. All Phase-1 tests remain green (test_ask.py).
"""
import io

import pandas as pd
import pytest


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def _sales_csv() -> bytes:
    """A dataset with a groupable categorical column (region) so a follow-up
    'break that down by region' is genuinely answerable only via prior context."""
    rows = []
    regions = ["north", "south", "east", "west"]
    for i in range(1, 41):
        region = regions[i % 4]
        # deterministic revenue so the aggregate is checkable
        rows.append(f"item{i},{region},{i * 10}")
    body = "\n".join(rows)
    return (f"product,region,revenue\n{body}\n").encode()


def _upload(api_client) -> tuple[str, str]:
    up = api_client.post(
        "/api/datasets",
        files={"file": ("sales_2024.csv", io.BytesIO(_sales_csv()), "text/csv")},
    )
    assert up.status_code == 200, up.text
    data = up.json()["data"]
    return data["session_id"], data["dataset_id"]


_TURN_KEYS = {
    "run_id", "question", "created_at", "answer", "method_note", "executed_code",
    "result_repr", "assumptions", "chart_spec", "token_usage", "attempts",
    "used_fallback", "status",
}


# --------------------------------------------------------------------------- #
# Upload creates a session; ask carries session_id
# --------------------------------------------------------------------------- #
def test_upload_returns_session_id(api_client):
    session_id, dataset_id = _upload(api_client)
    assert session_id
    # session appears in the list, dataframe resident
    lst = api_client.get("/api/sessions")
    assert lst.status_code == 200
    sessions = lst.json()["data"]
    match = [s for s in sessions if s["session_id"] == session_id]
    assert match, "uploaded session must appear in list"
    s = match[0]
    assert s["title"] == "sales_2024.csv"
    assert s["dataset_id"] == dataset_id
    assert s["dataframe_loaded"] is True
    assert s["turn_count"] == 0
    assert s["profile_summary"]["row_count"] == 40
    assert "region" in s["profile_summary"]["column_names"]


# --------------------------------------------------------------------------- #
# Happy path: 3 questions recorded as ordered turns with full pinned shape
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("fake_llm")
def test_three_turns_recorded_and_replayed(api_client):
    session_id, dataset_id = _upload(api_client)

    questions = [
        "What is the total revenue?",
        "How many rows are there?",
        "What is the average revenue?",
    ]
    run_ids = []
    for q in questions:
        r = api_client.post(f"/api/datasets/{dataset_id}/ask", json={"question": q})
        assert r.status_code == 200, r.text
        card = r.json()["data"]
        assert card["session_id"] == session_id  # answer-card carries session_id
        run_ids.append(card["run_id"])

    # Replay: all 3 turns in order, full pinned keys, correct token_usage
    rep = api_client.get(f"/api/sessions/{session_id}")
    assert rep.status_code == 200
    data = rep.json()["data"]
    assert data["session_id"] == session_id
    assert data["title"] == "sales_2024.csv"
    assert data["dataframe_loaded"] is True
    assert data["profile"]["row_count"] == 40
    turns = data["turns"]
    assert len(turns) == 3
    assert [t["question"] for t in turns] == questions  # created_at order
    for t in turns:
        assert set(t.keys()) == _TURN_KEYS, f"turn key mismatch: {set(t.keys())}"
        assert set(t["token_usage"].keys()) == {"prompt", "completion", "total"}
        assert t["token_usage"]["total"] > 0
        assert t["status"] == "completed"

    # turn_count in the list reflects 3
    lst = api_client.get("/api/sessions").json()["data"]
    s = [x for x in lst if x["session_id"] == session_id][0]
    assert s["turn_count"] == 3


# --------------------------------------------------------------------------- #
# HEADLINE: follow-up resolves ONLY via prior-turn context injection
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("_require_llm_key")
def test_followup_uses_prior_turn_context(api_client):
    session_id, dataset_id = _upload(api_client)

    # First turn: a single aggregate over the whole column.
    r1 = api_client.post(
        f"/api/datasets/{dataset_id}/ask",
        json={"question": "What is the total revenue?"},
    )
    assert r1.status_code == 200, r1.text
    card1 = r1.json()["data"]
    assert card1["executed_code"]

    # Elliptical follow-up: only answerable using the prior turn as context.
    r2 = api_client.post(
        f"/api/datasets/{dataset_id}/ask",
        json={"question": "Now break that down by region."},
    )
    assert r2.status_code == 200, r2.text
    card2 = r2.json()["data"]
    code2 = (card2["executed_code"] or "").lower()

    # The follow-up must have resolved 'that' = total revenue and re-scoped it by
    # region → the code references the region column (a groupby on region).
    assert "region" in code2, f"follow-up code should group by region: {code2!r}"
    assert "revenue" in code2, f"follow-up code should still concern revenue: {code2!r}"

    # And it produced a real per-region result (4 regions in the fixture).
    repr2 = (card2["result_repr"] or "").lower()
    assert any(reg in repr2 for reg in ("north", "south", "east", "west")), (
        f"per-region result expected, got: {card2['result_repr']!r}"
    )


# --------------------------------------------------------------------------- #
# dataframe_loaded reflects eviction; history survives; ask 404s after eviction
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("fake_llm")
def test_dataframe_eviction_keeps_history(api_client):
    from domain.dataset_store import get_store

    session_id, dataset_id = _upload(api_client)
    r = api_client.post(
        f"/api/datasets/{dataset_id}/ask",
        json={"question": "What is the total revenue?"},
    )
    assert r.status_code == 200, r.text

    # Before eviction: resident.
    lst = api_client.get("/api/sessions").json()["data"]
    s = [x for x in lst if x["session_id"] == session_id][0]
    assert s["dataframe_loaded"] is True

    # Simulate eviction / restart: clear the in-memory store.
    store = get_store()
    with store._lock:
        store._entries.clear()

    # dataframe_loaded now false, but the turn history still lists.
    lst2 = api_client.get("/api/sessions").json()["data"]
    s2 = [x for x in lst2 if x["session_id"] == session_id][0]
    assert s2["dataframe_loaded"] is False
    assert s2["turn_count"] == 1

    rep = api_client.get(f"/api/sessions/{session_id}").json()["data"]
    assert rep["dataframe_loaded"] is False
    assert len(rep["turns"]) == 1  # history renders from profile_snapshot + runs
    assert rep["profile"]["row_count"] == 40

    # Asking against the evicted dataset → DATASET_NOT_FOUND 404.
    ask = api_client.post(
        f"/api/datasets/{dataset_id}/ask", json={"question": "anything?"}
    )
    assert ask.status_code == 404
    assert ask.json()["error"]["code"] == "DATASET_NOT_FOUND"


# --------------------------------------------------------------------------- #
# Error path: unknown session → SESSION_NOT_FOUND 404
# --------------------------------------------------------------------------- #
def test_get_bogus_session_returns_404(api_client):
    r = api_client.get("/api/sessions/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "SESSION_NOT_FOUND"


# --------------------------------------------------------------------------- #
# Edge case: empty session list is a valid empty envelope
# --------------------------------------------------------------------------- #
def test_empty_session_list(api_client):
    r = api_client.get("/api/sessions")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["data"] == []
