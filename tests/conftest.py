import pytest


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    import config.settings as m
    m._settings = None
    yield
    m._settings = None


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.models import Base
    import db.session as session_module

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield engine
    engine.dispose()


@pytest.fixture
def _require_llm_key():
    """Skip if no LLM provider key is set — works for Anthropic or Gemini."""
    from config.settings import get_settings
    s = get_settings()
    if not s.anthropic_api_key and not s.gemini_api_key:
        pytest.skip("No LLM key set in .env (AGENT_ANTHROPIC_API_KEY or AGENT_GEMINI_API_KEY)")


_FAKE_USAGE = {"prompt": 20, "completion": 10, "total": 30}


def _fake(self, prompt, *, system=None, json_mode=False, **kwargs):
    """Deterministic in-process LLM stand-in for PLUMBING tests.

    Branches by stable markers in the USER prompt built by src/graph/nodes.py.
    Order matters: the fallback prompt also contains "Profile:", so "Last error:"
    must be checked first; the synthesize prompt contains "Executed code:" while
    the chart prompt only has "Computed result:".
    """
    import json

    if "Last error:" in prompt:
        # node_fallback_reason
        text = json.dumps(
            {"answer": "approx", "method_note": "sampled", "assumptions": []}
        )
    elif "Executed code:" in prompt:
        # node_synthesize_answer
        text = json.dumps(
            {"answer": "Computed.", "method_note": "Ran pandas.", "assumptions": []}
        )
    elif "Profile:" in prompt:
        # node_write_code — df.shape[0] is valid against ANY df (row count)
        text = json.dumps({"code": "result = df.shape[0]"})
    else:
        # node_build_chart
        text = json.dumps(
            {
                "type": "bar",
                "x": "region",
                "y": "revenue",
                "series": [{"label": "v", "points": [{"x": "north", "y": 1}]}],
                "title": "t",
            }
        )
    return text, dict(_FAKE_USAGE)


@pytest.fixture
def fake_llm(monkeypatch):
    """Run the graph end-to-end WITHOUT a network call (plumbing tests only).

    Opt-in per test — never autouse — so the real-LLM floor tests stay live.
    """
    monkeypatch.setattr("llm.client.LLMClient.call_model_with_usage", _fake)


@pytest.fixture
def api_client(_isolated_db):
    """FastAPI test client with isolated DB."""
    from fastapi.testclient import TestClient
    from api import app
    with TestClient(app) as client:
        yield client
