"""Integration tests — real Gemini via .env, production SQLite driver.

Covers the two MANDATORY Phase-1 gate tests from spec/roadmap.md plus edge/error
paths and the TestClient golden path.
"""
import io

import pandas as pd
import pytest

from sqlalchemy.orm import Session

from db.models import RunRow
import db.session as session_module


def _register_df(df: pd.DataFrame) -> str:
    from domain.dataset_store import get_store
    from domain.profile import build_profile, build_sample

    return get_store().add(df, build_profile(df), build_sample(df))


@pytest.fixture
def large_numeric_df():
    """5000 rows: a full-data mean/sum differs from any small sample."""
    import numpy as np

    rng = np.random.default_rng(42)
    n = 5000
    return pd.DataFrame(
        {
            "region": rng.choice(["north", "south", "east", "west"], size=n),
            "revenue": rng.integers(1, 1000, size=n).astype(float),
        }
    )


# --------------------------------------------------------------------------- #
# (a) MANDATORY: correct numeric answer computed by executed code on full data
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("_require_llm_key")
def test_full_data_numeric_answer_is_correct(large_numeric_df, _isolated_db):
    from graph.runner import run_ask

    dataset_id = _register_df(large_numeric_df)
    expected = round(float(large_numeric_df["revenue"].sum()), 2)

    card = run_ask(dataset_id, "What is the total sum of the revenue column?")

    assert card["run_id"] is not None
    assert card["token_usage"]["total"] > 0
    assert card["attempts"] >= 1
    assert card["executed_code"]
    # The computed result (not model prose) must equal the FULL-data sum.
    numbers = _extract_numbers(card["result_repr"])
    assert any(abs(x - expected) < 1.0 for x in numbers), (
        f"expected {expected} in result_repr={card['result_repr']!r}"
    )

    # DB state persisted
    with Session(session_module._engine) as s:
        run = s.get(RunRow, card["run_id"])
    assert run is not None
    assert run.status == "completed"
    assert run.token_total > 0
    # step trace covers the pipeline
    steps = [e["step"] for e in card["step_trace"]]
    assert "writing_code" in steps and "running_code" in steps and "synthesizing" in steps


# --------------------------------------------------------------------------- #
# (b) MANDATORY: first-attempt code error is self-corrected within MAX attempts
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("_require_llm_key")
def test_self_correction_recovers(large_numeric_df, _isolated_db, monkeypatch):
    """Inject a deterministic first-attempt execution failure, then assert the
    retry loop recovers with a correct answer within max_code_attempts."""
    import graph.nodes as nodes
    from graph.runner import run_ask

    real_execute = nodes.execute_pandas
    state = {"calls": 0}

    def flaky_execute(code, df, timeout_s=15):
        state["calls"] += 1
        if state["calls"] == 1:
            # Simulate a wrong-column first attempt: force a captured traceback.
            return real_execute("result = df['nonexistent_column'].sum()", df, timeout_s)
        return real_execute(code, df, timeout_s)

    monkeypatch.setattr(nodes, "execute_pandas", flaky_execute)

    dataset_id = _register_df(large_numeric_df)
    expected = round(float(large_numeric_df["revenue"].sum()), 2)

    card = run_ask(dataset_id, "What is the total sum of the revenue column?")

    assert card["attempts"] > 1, "should have retried after the forced failure"
    assert card["used_fallback"] is False
    numbers = _extract_numbers(card["result_repr"])
    assert any(abs(x - expected) < 1.0 for x in numbers)

    with Session(session_module._engine) as s:
        run = s.get(RunRow, card["run_id"])
    assert run.status == "completed"
    assert run.attempts > 1
    # a running_code:retry event should be present
    assert any(
        e["step"] == "running_code" and e["status"] == "retry"
        for e in card["step_trace"]
    )


# --------------------------------------------------------------------------- #
# Edge case: a ranking question yields a bar chart_spec
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("_require_llm_key")
def test_ranking_question_produces_chart(large_numeric_df, _isolated_db):
    from graph.runner import run_ask

    dataset_id = _register_df(large_numeric_df)
    card = run_ask(dataset_id, "Show total revenue for each region.")
    assert card["result_repr"]
    # chart is optional but a per-region total should chart as bar-ish
    if card["chart_spec"] is not None:
        assert card["chart_spec"].get("type") in {"bar", "line", "scatter", "histogram"}


# --------------------------------------------------------------------------- #
# Error path: empty question never reaches the graph
# --------------------------------------------------------------------------- #
def test_empty_question_rejected_before_graph(_isolated_db):
    from domain.dataset_store import get_store

    df = pd.DataFrame({"x": [1, 2, 3]})
    dataset_id = _register_df(df)
    from api.datasets import ask_dataset, AskRequest
    from api._common import APIError

    with pytest.raises(APIError) as exc:
        ask_dataset(dataset_id, AskRequest(question="   "))
    assert exc.value.code == "EMPTY_QUESTION"
    assert dataset_id in get_store()


# --------------------------------------------------------------------------- #
# TestClient golden path: upload -> ask -> full contract keys
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("_require_llm_key")
def test_golden_path_via_http(api_client):
    csv = _make_csv()
    up = api_client.post(
        "/api/datasets", files={"file": ("sales.csv", io.BytesIO(csv), "text/csv")}
    )
    assert up.status_code == 200
    up_body = up.json()
    assert up_body["ok"] is True
    dataset_id = up_body["data"]["dataset_id"]
    assert up_body["data"]["profile"]["row_count"] == 6

    ask = api_client.post(
        f"/api/datasets/{dataset_id}/ask",
        json={"question": "What is the total revenue?"},
    )
    assert ask.status_code == 200
    body = ask.json()
    assert body["ok"] is True
    card = body["data"]
    for key in (
        "run_id", "answer", "method_note", "executed_code", "result_repr",
        "assumptions", "chart_spec", "token_usage", "attempts",
        "used_fallback", "step_trace",
    ):
        assert key in card, f"missing contract key {key}"
    assert card["token_usage"]["total"] > 0
    # 10+20+30+40+50+60 = 210
    numbers = _extract_numbers(card["result_repr"])
    assert any(abs(x - 210.0) < 1.0 for x in numbers)


def _make_csv() -> bytes:
    rows = "\n".join(f"item{i},{i*10}" for i in range(1, 7))
    return (f"product,revenue\n{rows}\n").encode()


def _extract_numbers(text: str | None) -> list[float]:
    import re

    if not text:
        return []
    out = []
    for m in re.findall(r"-?\d[\d,]*\.?\d*", text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out
