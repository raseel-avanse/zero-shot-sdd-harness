"""Real-Gemini chat memory test (spec/capabilities — chat references prior turn).

Skips when no LLM key is present. Kept to a single two-turn exchange to respect
free-tier limits. Asserts the assistant's second reply depends on context
established in the first turn (conversation memory).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def chat_client(_isolated_db):
    from api import chat

    app = FastAPI()
    app.include_router(chat.router)
    with TestClient(app) as client:
        yield client


def _make_engagement():
    from db.models import Engagement
    from db.session import create_db_session

    with create_db_session() as s:
        eng = Engagement(name="acme-api", target_type="repo", target_ref="/tmp/acme")
        s.add(eng)
        s.flush()
        return eng.id


def test_chat_reply_references_prior_turn(chat_client, _require_llm_key):
    eid = _make_engagement()

    # Turn 1 establishes a fact the model must recall in turn 2.
    r1 = chat_client.post(
        f"/engagements/{eid}/chat",
        json={"message": "Remember this codeword for our session: BLUEHERON. Acknowledge it."},
    )
    assert r1.status_code == 200, r1.text

    # Turn 2 depends entirely on the earlier turn's context.
    r2 = chat_client.post(
        f"/engagements/{eid}/chat",
        json={"message": "What was the codeword I gave you earlier? Reply with just the word."},
    )
    assert r2.status_code == 200, r2.text
    reply = r2.json()["data"]["reply"]
    assert "BLUEHERON" in reply.upper(), reply

    # Four turns persisted (2 user + 2 assistant), in order.
    turns = chat_client.get(f"/engagements/{eid}/chat").json()["data"]
    assert [t["role"] for t in turns] == ["user", "assistant", "user", "assistant"]
