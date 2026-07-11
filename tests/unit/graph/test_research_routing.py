"""Query-type routing + clarify gate in the research node — LLM fully mocked."""
from unittest.mock import patch

import pytest

from graph import nodes
from llm.result import LLMResult


class _FakeClient:
    """Records prompts/systems and returns scripted LLMResults per call."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def generate(self, prompt, *, system=None, grounding=False):
        self.calls.append({"prompt": prompt, "system": system, "grounding": grounding})
        return self._results.pop(0)

    @property
    def model(self):
        return "gemini-2.5-flash"


def _persist_run(engine, query_type, query_text, status="running"):
    from sqlalchemy.orm import Session
    from db.models import RunRow

    with Session(engine) as s:
        run = RunRow(query_type=query_type, query_text=query_text, status=status)
        s.add(run)
        s.commit()
        return run.id


# --- _build_research_prompt: mode branching ---------------------------------

def test_build_prompt_url_mode_has_url_instruction():
    p = nodes._build_research_prompt("url", "https://amazon.in/x", None)
    assert "MODE: PRODUCT URL" in p
    assert "https://amazon.in/x" in p


def test_build_prompt_category_mode_has_category_instruction():
    p = nodes._build_research_prompt("category", "gaming laptops under 80k", None)
    assert "MODE: CATEGORY" in p
    assert "gaming laptops under 80k" in p


def test_build_prompt_name_mode_default():
    p = nodes._build_research_prompt("name", "Sony WH-1000XM5", None)
    assert "MODE: PRODUCT NAME" in p


def test_build_prompt_folds_in_clarify_answer():
    p = nodes._build_research_prompt("name", "phone", "Under 20k, for photography")
    assert "Under 20k, for photography" in p


# --- clarify gate: check_clarification --------------------------------------

def test_check_clarification_ambiguous(_isolated_db):
    fake = _FakeClient([LLMResult(
        text='{"needs_clarification": true, "question": "What is your budget?"}'
    )])
    with patch.object(nodes, "LLMClient", return_value=fake):
        needs, q = nodes.check_clarification("name", "good phone")
    assert needs is True
    assert q == "What is your budget?"
    # non-grounded, single call
    assert len(fake.calls) == 1
    assert fake.calls[0]["grounding"] is False


def test_check_clarification_clear_query_not_gated(_isolated_db):
    fake = _FakeClient([LLMResult(text='{"needs_clarification": false, "question": ""}')])
    with patch.object(nodes, "LLMClient", return_value=fake):
        needs, q = nodes.check_clarification("name", "Sony WH-1000XM5 headphones")
    assert needs is False


def test_check_clarification_url_skips_llm_entirely(_isolated_db):
    # URL mode must not spend a Gemini call.
    with patch.object(nodes, "LLMClient", side_effect=AssertionError("must not be called")):
        needs, q = nodes.check_clarification("url", "https://amazon.in/x")
    assert needs is False


def test_check_clarification_degrades_on_llm_failure(_isolated_db):
    def _boom(*a, **k):
        raise RuntimeError("provider down")

    with patch.object(nodes, "LLMClient", side_effect=_boom):
        needs, q = nodes.check_clarification("name", "phone")
    assert needs is False  # never gate on failure


def test_check_clarification_gates_off_when_no_question(_isolated_db):
    fake = _FakeClient([LLMResult(text='{"needs_clarification": true, "question": ""}')])
    with patch.object(nodes, "LLMClient", return_value=fake):
        needs, q = nodes.check_clarification("name", "phone")
    assert needs is False  # no usable question -> proceed


# --- research node: gate triggers pause / clears on resume ------------------

def test_research_pauses_on_ambiguous_query(_isolated_db):
    run_id = _persist_run(_isolated_db, "name", "good phone")
    fake = _FakeClient([LLMResult(
        text='{"needs_clarification": true, "question": "Budget and use?"}'
    )])
    with patch.object(nodes, "LLMClient", return_value=fake):
        out = nodes.research({"run_id": run_id, "query_type": "name", "query_text": "good phone"})

    assert out["needs_clarification"] is True
    assert out["clarifying_question"] == "Budget and use?"
    # Only the clarify call happened — no grounded research call.
    assert len(fake.calls) == 1
    # persisted status=needs_input + question
    from sqlalchemy.orm import Session
    from db.models import RunRow
    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.status == "needs_input"
        assert run.clarifying_question == "Budget and use?"


def test_research_proceeds_on_clear_query(_isolated_db):
    run_id = _persist_run(_isolated_db, "name", "Sony WH-1000XM5")
    fake = _FakeClient([
        LLMResult(text='{"needs_clarification": false, "question": ""}'),  # clarify
        LLMResult(text="Amazon.in — ₹24990 — 4.5 stars", sources=["https://amazon.in/x"],
                  prompt_tokens=100, completion_tokens=20),  # research
    ])
    with patch.object(nodes, "LLMClient", return_value=fake):
        out = nodes.research({"run_id": run_id, "query_type": "name", "query_text": "Sony WH-1000XM5"})

    assert not out.get("needs_clarification")
    assert out["research_notes"].startswith("Amazon.in")
    assert len(fake.calls) == 2  # clarify + research
    assert fake.calls[1]["grounding"] is True  # research grounded


def test_research_on_resume_skips_gate_and_uses_answer(_isolated_db):
    run_id = _persist_run(_isolated_db, "name", "good phone", status="running")
    fake = _FakeClient([
        LLMResult(text="Flipkart — ₹18000 — good camera", prompt_tokens=50, completion_tokens=10),
    ])
    with patch.object(nodes, "LLMClient", return_value=fake):
        out = nodes.research({
            "run_id": run_id, "query_type": "name", "query_text": "good phone",
            "clarify_answer": "Under 20k, for photography",
        })

    # No clarify call — went straight to a single grounded research call.
    assert len(fake.calls) == 1
    assert fake.calls[0]["grounding"] is True
    assert "Under 20k, for photography" in fake.calls[0]["prompt"]
    assert out["research_notes"].startswith("Flipkart")
