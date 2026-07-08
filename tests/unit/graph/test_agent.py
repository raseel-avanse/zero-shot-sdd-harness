"""Unit tests for the Sentinel assessment graph.

These run WITHOUT a live LLM key: they exercise the in-code scope gate, the
budget-bounded hunt routing, and graph compilation only. Any node reaching the
LLM would raise if invoked — the scope-refusal test asserts it never is.
"""
import graph.nodes as nodes
from graph.agent import _build_graph, agentic_ai
from graph.edges import (
    route_after_hunt,
    route_after_live_hunt,
    route_after_prioritize,
    route_after_scope,
)
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


# --------------------------------------------------------------------------- #
# Phase 2 — live-app branch (SAFETY-CRITICAL): branch on target_type, refuse
# out-of-scope hosts in code without any LLM call, and bound the live loop.
# --------------------------------------------------------------------------- #


def test_scope_gate_branches_live_app_to_live_recon(monkeypatch):
    # An in-scope live target routes to the non-destructive live path, NOT recon.
    def _boom(*a, **k):
        raise AssertionError("enforce_scope must NOT contact the LLM")

    monkeypatch.setattr(nodes, "LLMClient", _boom)

    state = {
        "run_id": "r1",
        "target_type": "live_app",
        "target_path": "https://app.example.com/",
        "scope_allowlist": ["app.example.com"],
        "step_budget": 40,
    }
    out = enforce_scope(state)
    assert not out.get("error")
    # The router must send a live_app target down the live path.
    assert route_after_scope({**out, "target_type": "live_app"}) == "live_recon"


def test_scope_gate_refuses_out_of_scope_live_host_without_llm(monkeypatch):
    # An out-of-scope host is refused in code — no LLM, no probe, straight to sink.
    def _boom(*a, **k):
        raise AssertionError("enforce_scope must NOT contact the LLM")

    monkeypatch.setattr(nodes, "LLMClient", _boom)

    def _no_probe(*a, **k):
        raise AssertionError("no probe may be constructed for an out-of-scope host")

    monkeypatch.setattr(nodes.http_probe, "Prober", _no_probe)

    state = {
        "run_id": "r1",
        "target_type": "live_app",
        "target_path": "https://evil.example.net/steal",
        "scope_allowlist": ["app.example.com"],
        "step_budget": 40,
    }
    out = enforce_scope(state)
    assert out.get("error")
    assert "scope violation" in out["error"]
    assert route_after_scope({**out, "target_type": "live_app"}) == "handle_error"


def test_prioritize_branches_hunt_vs_live_hunt():
    assert route_after_prioritize({"target_type": "live_app"}) == "live_hunt"
    assert route_after_prioritize({"target_type": "repo"}) == "hunt"
    # Default (no target_type) is the repo path — backward compatible.
    assert route_after_prioritize({}) == "hunt"


def test_live_hunt_loop_bounded_by_step_budget():
    # Categories remain but budget exhausted -> stop looping, go to validate.
    exhausted = {"priorities": ["injection"], "step_count": 40, "step_budget": 40}
    assert route_after_live_hunt(exhausted) == "validate"
    # Budget + categories remain -> keep probing.
    more = {"priorities": ["injection"], "step_count": 2, "step_budget": 40}
    assert route_after_live_hunt(more) == "live_hunt"
    # No categories left -> validate regardless of budget.
    done = {"priorities": [], "step_count": 2, "step_budget": 40}
    assert route_after_live_hunt(done) == "validate"
