from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import research, rank, deal_quality, finalize, handle_error
from graph.edges import after_research, after_rank


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("research", research)
    g.add_node("rank", rank)
    g.add_node("deal_quality", deal_quality)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("research")

    g.add_conditional_edges(
        "research",
        after_research,
        # "END" is the application-level clarify pause (status=needs_input).
        {"rank": "rank", "handle_error": "handle_error", "END": END},
    )
    g.add_conditional_edges(
        "rank",
        after_rank,
        {"deal_quality": "deal_quality", "handle_error": "handle_error"},
    )
    g.add_edge("deal_quality", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
