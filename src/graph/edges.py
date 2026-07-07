"""Conditional routing for the Sentinel assessment graph (see spec/agent.md)."""
from __future__ import annotations

from graph.state import AgentState


def route_after_scope(state: AgentState) -> str:
    """Scope refusal (set in code) is fatal — route straight to handle_error."""
    return "handle_error" if state.get("error") else "recon"


def route_after_recon(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "prioritize"


def route_after_hunt(state: AgentState) -> str:
    """Loop hunt while categories remain AND the step budget is not exhausted."""
    priorities = state.get("priorities")
    step_count = int(state.get("step_count", 0))
    step_budget = int(state.get("step_budget", 0))
    if priorities and step_count < step_budget:
        return "hunt"
    return "validate"


def route_after_validate(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "report"
