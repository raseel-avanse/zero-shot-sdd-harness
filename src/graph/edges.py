from config.settings import get_settings
from graph.state import AgentState


def route_after_init(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "write_code"


def route_after_write_code(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "execute_code"


def route_after_exec(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    if state.get("last_traceback") is None:
        return "synthesize"
    max_attempts = get_settings().max_code_attempts
    if state.get("attempts", 0) < max_attempts:
        return "write_code"
    return "fallback"


def route_after_synthesize(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "build_chart"


def route_after_fallback(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "finalize"
