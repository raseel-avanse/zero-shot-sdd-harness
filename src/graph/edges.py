from graph.state import AgentState


def after_research(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    # P2: needs_clarification -> clarify pause. P1: always proceed to rank.
    return "rank"


def after_rank(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    # P2 will route to "deal_quality" first; P1 goes straight to finalize.
    return "finalize"
