"""Unit tests for the Sentinel assessment graph.

These run WITHOUT a live LLM key: they exercise the in-code scope gate, the
budget-bounded hunt routing, and graph compilation only. Any node reaching the
LLM would raise if invoked — the scope-refusal test asserts it never is.
"""
import graph.nodes as nodes
from graph.agent import _build_graph, agentic_ai
from graph.edges import route_after_hunt, route_after_scope
from graph.nodes import enforce_scope


def test_graph_compiles():
    assert agentic_ai is not None
    # Recompiling must also succeed (no hidden global state).
    assert _build_graph() is not None


def test_enforce_scope_refuses_out_of_scope_without_llm(monkeypatch):
    # Any LLM construction/call inside the gate would be a safety bug.
    def _boom(*a, **k):
        raise AssertionError("enforce_scope must NOT contact the LLM")

    monkeypatch.setattr(nodes, "LLMClient", _boom)

    state = {
        "run_id": "r1",
        "target_path": "/etc/passwd",
        "scope_allowlist": ["/authorized/repo"],
        "step_budget": 40,
    }
    out = enforce_scope(state)

    assert out.get("error")
    assert "scope violation" in out["error"]
    assert "/etc/passwd" in out["error"]
    # Router sends a refused scope straight to the fatal sink.
    assert route_after_scope(out) == "handle_error"


def test_enforce_scope_allows_in_scope_target(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("enforce_scope must NOT contact the LLM")

    monkeypatch.setattr(nodes, "LLMClient", _boom)

    allowed = tmp_path / "repo"
    allowed.mkdir()
    state = {
        "run_id": "r1",
        "target_path": str(allowed),
        "scope_allowlist": [str(tmp_path)],
        "step_budget": 40,
    }
    out = enforce_scope(state)

    assert not out.get("error")
    assert out["status"] == "running"
    assert route_after_scope(out) == "recon"


def test_enforce_scope_refuses_empty_allowlist():
    # Edge case: an empty allowlist authorizes nothing.
    out = enforce_scope({"target_path": "/anything", "scope_allowlist": []})
    assert out.get("error")
    assert route_after_scope(out) == "handle_error"


def test_hunt_loop_bounded_by_step_budget():
    # Categories remain but budget is exhausted -> stop looping, go to validate.
    exhausted = {"priorities": ["injection", "broken_auth"], "step_count": 40, "step_budget": 40}
    assert route_after_hunt(exhausted) == "validate"

    # Budget remains and categories remain -> keep hunting.
    more = {"priorities": ["injection"], "step_count": 3, "step_budget": 40}
    assert route_after_hunt(more) == "hunt"

    # No categories left -> validate regardless of budget.
    done = {"priorities": [], "step_count": 3, "step_budget": 40}
    assert route_after_hunt(done) == "validate"
