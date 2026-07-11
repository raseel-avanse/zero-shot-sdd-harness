"""Graph routing tests — no LLM key required."""
from graph.edges import after_research, after_rank


def test_after_research_routes_to_rank_on_success():
    assert after_research({"research_notes": "notes", "error": None}) == "rank"


def test_after_research_routes_to_handle_error_on_error():
    assert after_research({"error": "boom"}) == "handle_error"


def test_after_rank_routes_to_finalize_on_success():
    assert after_rank({"deals": [], "error": None}) == "finalize"


def test_after_rank_routes_to_handle_error_on_error():
    assert after_rank({"error": "parse failed"}) == "handle_error"


def test_graph_has_expected_nodes():
    from graph.agent import agentic_ai
    nodes = set(agentic_ai.get_graph().nodes.keys())
    for name in ("research", "rank", "finalize", "handle_error"):
        assert name in nodes
