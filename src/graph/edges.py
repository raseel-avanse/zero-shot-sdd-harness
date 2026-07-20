"""Conditional routing for the Sentinel assessment graph (see spec/agent.md)."""
from __future__ import annotations

from graph.state import AgentState


def route_after_scope(state: AgentState) -> str:
    """Scope refusal (set in code) is fatal — route straight to handle_error.

    Otherwise branch on target_type: a `live_app` engagement takes the
    non-destructive live-probing path; anything else takes the repo path.
    """
    if state.get("error"):
        return "handle_error"
    if state.get("target_type") == "live_app":
        return "live_recon"
    return "recon"


def route_after_recon(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "prioritize"


def route_after_live_recon(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "prioritize"


def route_after_prioritize(state: AgentState) -> str:
    """Hunt over the live target or the repo, depending on target_type."""
    return "live_hunt" if state.get("target_type") == "live_app" else "hunt"


def _budget_remains(state: AgentState) -> bool:
    priorities = state.get("priorities")
    step_count = int(state.get("step_count", 0))
    step_budget = int(state.get("step_budget", 0))
    return bool(priorities and step_count < step_budget)


def route_after_hunt(state: AgentState) -> str:
    """Loop hunt while categories remain AND the step budget is not exhausted."""
    return "hunt" if _budget_remains(state) else "validate"


def route_after_live_hunt(state: AgentState) -> str:
    """Loop live_hunt while categories remain AND the step budget is not exhausted."""
    return "live_hunt" if _budget_remains(state) else "validate"


def route_after_validate(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "report"
