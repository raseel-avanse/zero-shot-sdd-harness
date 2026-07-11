from graph.state import AgentState


def after_research(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    # P2 clarify gate: the research node paused the run (status=needs_input) and
    # set needs_clarification — end the graph early without ranking. It resumes
    # via POST /runs/{id}/answer, which re-enters the graph from research.
    if state.get("needs_clarification"):
        return "END"
    return "rank"


def after_rank(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    # P2: assess deal quality before finalising.
    return "deal_quality"
