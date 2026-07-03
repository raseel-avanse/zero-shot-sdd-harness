"""Runner: drive the agent graph for one question and return the answer-card dict.

The returned dict shape is pinned by spec/api.md (POST /api/datasets/{id}/ask).
"""
from __future__ import annotations

from graph.agent import agentic_ai
from graph.state import AgentState
from observability.events import get_logger

_log = get_logger("runner")


class DatasetNotFound(Exception):
    pass


class LLMUnavailable(Exception):
    pass


class RunFailed(Exception):
    pass


def run_ask(dataset_id: str, question: str) -> dict:
    """Run the graph. Raises typed errors mapped to api_error by the router."""
    initial: AgentState = {
        "dataset_id": dataset_id,
        "question": question,
        "error": None,
    }
    final = agentic_ai.invoke(initial)

    error = final.get("error")
    if error:
        if error == "DATASET_NOT_FOUND":
            raise DatasetNotFound(dataset_id)
        if str(error).startswith("LLM_UNAVAILABLE"):
            raise LLMUnavailable(str(error))
        raise RunFailed(str(error))

    usage = final.get("token_usage") or {"prompt": 0, "completion": 0, "total": 0}
    return {
        "run_id": final.get("run_id"),
        "answer": final.get("answer"),
        "method_note": final.get("method_note"),
        "executed_code": final.get("code"),
        "result_repr": final.get("result_repr"),
        "assumptions": final.get("assumptions") or [],
        "chart_spec": final.get("chart_spec"),
        "token_usage": {
            "prompt": usage.get("prompt", 0),
            "completion": usage.get("completion", 0),
            "total": usage.get("total", 0),
        },
        "attempts": final.get("attempts", 0),
        "used_fallback": bool(final.get("used_fallback", False)),
        "step_trace": final.get("step_trace") or [],
    }
