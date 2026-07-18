"""Node error handling maps raw provider exceptions to plain-language messages.

No real Gemini call — the LLM client's `generate` is monkeypatched to raise.
Guards against leaking provider JSON / stack traces into the user-facing error.
"""
import pytest

import graph.nodes as nodes
from graph.nodes import friendly_error


# Fragments that must NEVER surface to the user-facing `error`.
_RAW_LEAKS = ("RESOURCE_EXHAUSTED", "quotaId", "generativelanguage",
             "Traceback", "429", "{", "}")

_GEMINI_429 = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': "
    "'RESOURCE_EXHAUSTED', 'details': [{'quotaId': "
    "'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaValue': '50'}], "
    "'message': 'You exceeded your current quota', "
    "'links': 'https://generativelanguage.googleapis.com'}}"
)


def _assert_no_raw_leak(message: str) -> None:
    for frag in _RAW_LEAKS:
        assert frag not in message, f"raw provider text {frag!r} leaked: {message!r}"


# ---------------------------------------------------------------------------
# friendly_error mapping
# ---------------------------------------------------------------------------
def test_friendly_maps_rate_limit():
    msg = friendly_error(RuntimeError(_GEMINI_429), stage="research")
    assert msg == "The research service is busy right now — please try again in a minute."
    _assert_no_raw_leak(msg)


def test_friendly_maps_timeout():
    msg = friendly_error(TimeoutError("connection timed out after 30s"), stage="research")
    assert msg == "Couldn't reach the research service — please try again."
    _assert_no_raw_leak(msg)


def test_friendly_maps_5xx_reach():
    msg = friendly_error(RuntimeError("503 Service Unavailable"), stage="research")
    assert msg == "Couldn't reach the research service — please try again."


def test_friendly_rank_parse_default():
    msg = friendly_error(ValueError("Expected a JSON list of deals"), stage="rank")
    assert msg == "Couldn't rank the results — please try again."


def test_friendly_generic_research_default():
    msg = friendly_error(ValueError("weird internal thing"), stage="research")
    assert msg == "Something went wrong during research — please try again."


# ---------------------------------------------------------------------------
# node integration — mocked client raises, node returns friendly error
# ---------------------------------------------------------------------------
class _BoomClient:
    """Stand-in LLMClient whose generate() raises a Gemini-style 429."""
    model = "gemini-2.5-flash"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, *args, **kwargs):
        raise RuntimeError(_GEMINI_429)


@pytest.fixture
def _no_db(monkeypatch):
    # _update_run touches the DB; stub it so the test needs no real DB/keys.
    monkeypatch.setattr(nodes, "_update_run", lambda *a, **k: None)


def test_research_node_returns_plain_language(monkeypatch, _no_db):
    monkeypatch.setattr(nodes, "LLMClient", _BoomClient)
    out = nodes.research({"run_id": "r1", "query_text": "phone", "query_type": "name"})
    assert out["error"] == "The research service is busy right now — please try again in a minute."
    _assert_no_raw_leak(out["error"])


def test_rank_node_returns_plain_language(monkeypatch, _no_db):
    monkeypatch.setattr(nodes, "LLMClient", _BoomClient)
    out = nodes.rank({"run_id": "r1", "query_text": "phone", "research_notes": "notes"})
    assert out["error"] == "The research service is busy right now — please try again in a minute."
    _assert_no_raw_leak(out["error"])


def test_no_raw_provider_text_persisted_as_error_message(monkeypatch):
    """handle_error must persist the friendly message, not raw provider JSON."""
    captured = {}
    monkeypatch.setattr(
        nodes, "_update_run",
        lambda run_id, **fields: captured.update(fields),
    )
    friendly = "The research service is busy right now — please try again in a minute."
    nodes.handle_error({"run_id": "r1", "error": friendly})
    assert captured["status"] == "failed"
    assert captured["error_message"] == friendly
    _assert_no_raw_leak(captured["error_message"])
