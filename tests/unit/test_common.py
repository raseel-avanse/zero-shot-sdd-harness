"""Envelope + graph-compiles unit tests — no LLM."""
from api._common import ok, api_error


def test_ok_envelope_shape():
    assert ok({"a": 1}) == {"ok": True, "data": {"a": 1}}


def test_api_error_carries_code_and_detail():
    exc = api_error("PARSE_FAILED", "bad file", 400)
    assert exc.status_code == 400
    assert exc.detail == {"code": "PARSE_FAILED", "detail": "bad file"}


def test_graph_compiles():
    from graph.agent import agentic_ai, compiled_graph
    assert agentic_ai is not None
    assert compiled_graph is agentic_ai
