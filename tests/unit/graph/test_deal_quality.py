"""Deal-quality tool + node — LLM fully mocked."""
from unittest.mock import patch

import pytest

from graph import nodes
from tools.deal_quality import parse_quality_response, merge_quality, VALID_LABELS
from llm.result import LLMResult


class _FakeClient:
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc
        self.calls = []

    def generate(self, prompt, *, system=None, grounding=False):
        self.calls.append({"prompt": prompt, "grounding": grounding})
        if self._exc:
            raise self._exc
        return self._result

    @property
    def model(self):
        return "gemini-2.5-flash"


# --- parse_quality_response --------------------------------------------------

def test_parse_assessments_object():
    raw = '{"assessments": [{"rank": 1, "quality_label": "genuine_discount", "quality_reason": "cheap"}]}'
    out = parse_quality_response(raw)
    assert out[1]["quality_label"] == "genuine_discount"
    assert out[1]["quality_reason"] == "cheap"


def test_parse_bare_list():
    raw = '[{"rank": 2, "quality_label": "wait", "quality_reason": "inflated"}]'
    out = parse_quality_response(raw)
    assert out[2]["quality_label"] == "wait"


def test_parse_strips_fences():
    raw = '```json\n{"assessments":[{"rank":1,"quality_label":"unknown","quality_reason":"x"}]}\n```'
    out = parse_quality_response(raw)
    assert out[1]["quality_label"] == "unknown"


def test_parse_unknown_label_normalised():
    raw = '{"assessments": [{"rank": 1, "quality_label": "amazing_deal", "quality_reason": "x"}]}'
    out = parse_quality_response(raw)
    assert out[1]["quality_label"] == "unknown"  # invalid label -> unknown


def test_parse_invalid_json_raises():
    with pytest.raises(Exception):
        parse_quality_response("not json")


def test_all_labels_valid():
    assert VALID_LABELS == {"genuine_discount", "wait", "unknown"}


# --- merge_quality -----------------------------------------------------------

def test_merge_applies_labels_by_rank():
    deals = [{"rank": 1, "site": "A", "price_inr": 10, "reason": "r"}]
    assessments = {1: {"quality_label": "genuine_discount", "quality_reason": "low"}}
    merged = merge_quality(deals, assessments)
    assert merged[0]["quality_label"] == "genuine_discount"
    assert merged[0]["quality_reason"] == "low"


def test_merge_degrades_missing_to_unknown():
    deals = [{"rank": 1, "site": "A", "price_inr": 10, "reason": "r"},
             {"rank": 2, "site": "B", "price_inr": 20, "reason": "r2"}]
    assessments = {1: {"quality_label": "wait", "quality_reason": "hi"}}
    merged = merge_quality(deals, assessments)
    assert merged[0]["quality_label"] == "wait"
    assert merged[1]["quality_label"] == "unknown"  # no assessment for rank 2


def test_merge_empty_assessments_all_unknown():
    deals = [{"rank": 1, "site": "A", "price_inr": 10, "reason": "r"}]
    merged = merge_quality(deals, {})
    assert merged[0]["quality_label"] == "unknown"


# --- deal_quality node -------------------------------------------------------

def _run_id(engine):
    from sqlalchemy.orm import Session
    from db.models import RunRow
    with Session(engine) as s:
        run = RunRow(query_type="name", query_text="q", status="running")
        s.add(run)
        s.commit()
        return run.id


def test_node_labels_all_deals(_isolated_db):
    rid = _run_id(_isolated_db)
    deals = [
        {"rank": 1, "site": "A", "price_inr": 100, "reason": "r1"},
        {"rank": 2, "site": "B", "price_inr": 200, "reason": "r2"},
    ]
    fake = _FakeClient(result=LLMResult(
        text='{"assessments": [{"rank": 1, "quality_label": "genuine_discount", "quality_reason": "low"},'
             '{"rank": 2, "quality_label": "wait", "quality_reason": "high"}]}',
        prompt_tokens=80, completion_tokens=30,
    ))
    with patch.object(nodes, "LLMClient", return_value=fake):
        out = nodes.deal_quality({"run_id": rid, "query_text": "q", "deals": deals,
                                  "prompt_tokens": 10, "completion_tokens": 5})

    labels = {d["rank"]: d["quality_label"] for d in out["deals"]}
    assert labels == {1: "genuine_discount", 2: "wait"}
    # ONE batched grounded call, not one per deal
    assert len(fake.calls) == 1
    assert fake.calls[0]["grounding"] is True
    # tokens accumulated
    assert out["prompt_tokens"] == 90
    assert out["completion_tokens"] == 35


def test_node_degrades_on_llm_failure_never_fatal(_isolated_db):
    rid = _run_id(_isolated_db)
    deals = [{"rank": 1, "site": "A", "price_inr": 100, "reason": "r"}]
    fake = _FakeClient(exc=RuntimeError("grounding thin / provider error"))
    with patch.object(nodes, "LLMClient", return_value=fake):
        out = nodes.deal_quality({"run_id": rid, "query_text": "q", "deals": deals,
                                  "prompt_tokens": 0, "completion_tokens": 0})

    assert out["deals"][0]["quality_label"] == "unknown"
    assert out.get("error") is None  # never fatal


def test_node_degrades_on_bad_json(_isolated_db):
    rid = _run_id(_isolated_db)
    deals = [{"rank": 1, "site": "A", "price_inr": 100, "reason": "r"}]
    fake = _FakeClient(result=LLMResult(text="totally not json"))
    with patch.object(nodes, "LLMClient", return_value=fake):
        out = nodes.deal_quality({"run_id": rid, "query_text": "q", "deals": deals,
                                  "prompt_tokens": 0, "completion_tokens": 0})
    assert out["deals"][0]["quality_label"] == "unknown"


def test_node_empty_deals_no_llm_call(_isolated_db):
    rid = _run_id(_isolated_db)
    with patch.object(nodes, "LLMClient", side_effect=AssertionError("no call for empty deals")):
        out = nodes.deal_quality({"run_id": rid, "query_text": "q", "deals": [],
                                  "prompt_tokens": 0, "completion_tokens": 0})
    assert out["deals"] == []
