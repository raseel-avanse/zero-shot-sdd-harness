"""Chat API contract tests (spec/api.md — POST/GET /engagements/{id}/chat).

The chat router is wired into the app by agent-builder; here we mount it on a
dedicated app so the slice can be gated independently. The LLM is stubbed so
these run without a key — the real-Gemini prior-turn-context assertion lives in
tests/integration/test_chat_memory.py.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def chat_client(_isolated_db):
    from fastapi import FastAPI

    from api import chat

    app = FastAPI()
    app.include_router(chat.router)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def _stub_llm(monkeypatch):
    calls = {}

    class _StubClient:
        def complete(self, prompt, *, system=None, tier="fast"):
            calls["prompt"] = prompt
            calls["system"] = system
            return {
                "text": "stub reply",
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "model": "stub",
            }

    import llm.client as client_module

    monkeypatch.setattr(client_module, "LLMClient", _StubClient)
    return calls


def _make_engagement():
    from db.models import Engagement
    from db.session import create_db_session

    with create_db_session() as s:
        eng = Engagement(name="e", target_type="repo", target_ref="/tmp/repo")
        s.add(eng)
        s.flush()
        return eng.id


def test_chat_happy_path_persists_both_turns(chat_client, _stub_llm):
    eid = _make_engagement()

    r = chat_client.post(f"/engagements/{eid}/chat", json={"message": "what is SQLi?"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["reply"] == "stub reply"
    assert data["turn_id"]

    lst = chat_client.get(f"/engagements/{eid}/chat")
    turns = lst.json()["data"]
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[0]["content"] == "what is SQLi?"
    assert turns[1]["content"] == "stub reply"


def test_chat_passes_prior_turns_to_model(chat_client, _stub_llm):
    eid = _make_engagement()
    chat_client.post(f"/engagements/{eid}/chat", json={"message": "first question"})

    chat_client.post(f"/engagements/{eid}/chat", json={"message": "follow up"})
    # The second call's prompt must include the earlier turns (conversation memory).
    prompt = _stub_llm["prompt"]
    assert "first question" in prompt
    assert "stub reply" in prompt
    assert "follow up" in prompt


def test_chat_unknown_engagement_404(chat_client, _stub_llm):
    r = chat_client.post("/engagements/does-not-exist/chat", json={"message": "hi"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_chat_empty_message_rejected(chat_client, _stub_llm):
    eid = _make_engagement()
    r = chat_client.post(f"/engagements/{eid}/chat", json={"message": ""})
    assert r.status_code == 422


def test_chat_missing_message_field_rejected(chat_client, _stub_llm):
    eid = _make_engagement()
    r = chat_client.post(f"/engagements/{eid}/chat", json={})
    assert r.status_code == 422


def test_list_chat_empty_engagement(chat_client, _stub_llm):
    eid = _make_engagement()
    r = chat_client.get(f"/engagements/{eid}/chat")
    assert r.status_code == 200
    assert r.json()["data"] == []
