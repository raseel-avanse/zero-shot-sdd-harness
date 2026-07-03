from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    node_init,
    node_write_code,
    node_execute_code,
    node_synthesize_answer,
    node_build_chart,
    node_fallback_reason,
    node_finalize,
    node_handle_error,
)
from graph.edges import (
    route_after_init,
    route_after_write_code,
    route_after_exec,
    route_after_synthesize,
    route_after_fallback,
)


def _build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("init", node_init)
    graph.add_node("write_code", node_write_code)
    graph.add_node("execute_code", node_execute_code)
    graph.add_node("synthesize", node_synthesize_answer)
    graph.add_node("build_chart", node_build_chart)
    graph.add_node("fallback", node_fallback_reason)
    graph.add_node("finalize", node_finalize)
    graph.add_node("handle_error", node_handle_error)

    graph.set_entry_point("init")

    graph.add_conditional_edges(
        "init", route_after_init,
        {"handle_error": "handle_error", "write_code": "write_code"},
    )
    graph.add_conditional_edges(
        "write_code", route_after_write_code,
        {"handle_error": "handle_error", "execute_code": "execute_code"},
    )
    graph.add_conditional_edges(
        "execute_code", route_after_exec,
        {
            "synthesize": "synthesize",
            "write_code": "write_code",
            "fallback": "fallback",
            "handle_error": "handle_error",
        },
    )
    graph.add_conditional_edges(
        "synthesize", route_after_synthesize,
        {"handle_error": "handle_error", "build_chart": "build_chart"},
    )
    graph.add_edge("build_chart", "finalize")
    graph.add_conditional_edges(
        "fallback", route_after_fallback,
        {"handle_error": "handle_error", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("handle_error", END)

    return graph.compile()


# Compiled once at import.
agentic_ai = _build_graph()
compiled_graph = agentic_ai
