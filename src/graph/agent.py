"""Assemble + compile the Sentinel assessment StateGraph (see spec/agent.md)."""
from langgraph.graph import END, StateGraph

from graph.edges import (
    route_after_hunt,
    route_after_live_hunt,
    route_after_live_recon,
    route_after_prioritize,
    route_after_recon,
    route_after_scope,
    route_after_validate,
)
from graph.nodes import (
    enforce_scope,
    handle_error,
    hunt,
    live_hunt,
    live_recon,
    prioritize,
    recon,
    report,
    validate,
)
from graph.state import AgentState


def _build_graph():
    g = StateGraph(AgentState)

    g.add_node("enforce_scope", enforce_scope)
    g.add_node("recon", recon)
    g.add_node("live_recon", live_recon)
    g.add_node("prioritize", prioritize)
    g.add_node("hunt", hunt)
    g.add_node("live_hunt", live_hunt)
    g.add_node("validate", validate)
    g.add_node("report", report)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("enforce_scope")

    # Branch on target_type: repo -> recon/hunt, live_app -> live_recon/live_hunt.
    g.add_conditional_edges(
        "enforce_scope",
        route_after_scope,
        {"handle_error": "handle_error", "recon": "recon", "live_recon": "live_recon"},
    )
    g.add_conditional_edges(
        "recon",
        route_after_recon,
        {"handle_error": "handle_error", "prioritize": "prioritize"},
    )
    g.add_conditional_edges(
        "live_recon",
        route_after_live_recon,
        {"handle_error": "handle_error", "prioritize": "prioritize"},
    )
    g.add_conditional_edges(
        "prioritize",
        route_after_prioritize,
        {"hunt": "hunt", "live_hunt": "live_hunt"},
    )
    g.add_conditional_edges(
        "hunt",
        route_after_hunt,
        {"hunt": "hunt", "validate": "validate"},
    )
    g.add_conditional_edges(
        "live_hunt",
        route_after_live_hunt,
        {"live_hunt": "live_hunt", "validate": "validate"},
    )
    g.add_conditional_edges(
        "validate",
        route_after_validate,
        {"handle_error": "handle_error", "report": "report"},
    )
    g.add_edge("report", END)
    g.add_edge("handle_error", END)

    return g.compile()


agentic_ai = _build_graph()
