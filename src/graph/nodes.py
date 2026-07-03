"""LangGraph nodes for the data-analyst agent (see spec/agent.md)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from config.settings import get_settings
from db.models import RunRow, SessionRow
from db.session import create_db_session
from domain.dataset_store import get_store
from graph.executor import execute_pandas
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger
from observability.query_log import append_query_log

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_log = get_logger("graph")


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _accumulate(usage: dict, delta: dict) -> dict:
    return {
        "prompt": usage.get("prompt", 0) + delta.get("prompt", 0),
        "completion": usage.get("completion", 0) + delta.get("completion", 0),
        "total": usage.get("total", 0) + delta.get("total", 0),
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _extract_code(text: str) -> str:
    """Pull a pandas snippet out of the model reply; ensure it assigns `result`."""
    parsed = _parse_json(text)
    if isinstance(parsed, dict) and isinstance(parsed.get("code"), str):
        code = parsed["code"]
    else:
        code = _strip_fences(text)
    code = code.strip()
    # If the model returned a bare single expression, assign it to `result`.
    if "result" not in code:
        lines = [ln for ln in code.splitlines() if ln.strip()]
        if len(lines) == 1 and "=" not in lines[0].split("#")[0]:
            code = f"result = {lines[0].strip()}"
    return code


def _parse_json(text: str) -> dict | None:
    t = _strip_fences(text)
    if t.lower() == "null":
        return None
    try:
        return json.loads(t)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Conversation history (Phase 2)
# --------------------------------------------------------------------------- #

def _load_history(session_id: str | None, limit: int) -> list[dict]:
    """Load the last `limit` COMPLETED turns of a session, oldest-first, as a
    compact list of {question, method_note, executed_code}. Never includes the
    full result_repr (keeps token spend low). See spec/agent.md § Memory."""
    if not session_id or limit <= 0:
        return []
    with create_db_session() as session:
        rows = (
            session.execute(
                select(RunRow)
                .where(RunRow.session_id == session_id)
                .where(RunRow.status == "completed")
                .order_by(RunRow.created_at.desc(), RunRow.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        # Materialise fields inside the session — the ORM expires attributes on
        # commit/close, so we must read them before the context exits.
        history = [
            {
                "question": r.question,
                "method_note": r.method_note,
                "executed_code": r.executed_code,
            }
            for r in rows
        ]
    history.reverse()  # oldest-first for prompt coherence
    return history


def _history_block(history: list[dict] | None) -> str:
    """Render the compact last-N-turns summary for injection into prompts.
    Empty string when there is no history (prompt is then identical to Phase 1)."""
    if not history:
        return ""
    lines = ["Recent conversation (most recent last), for resolving follow-up references:"]
    for i, turn in enumerate(history, start=1):
        lines.append(f"  Turn {i}:")
        lines.append(f"    Question: {turn.get('question')}")
        if turn.get("method_note"):
            lines.append(f"    Method: {turn.get('method_note')}")
        if turn.get("executed_code"):
            lines.append(f"    Code: {turn.get('executed_code')}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #

def node_init(state: AgentState) -> AgentState:
    dataset_id = state["dataset_id"]
    question = state["question"]
    session_id = state.get("session_id")
    try:
        entry = get_store().get(dataset_id)
        if entry is None:
            return {**state, "error": "DATASET_NOT_FOUND"}

        # Load prior turns BEFORE creating this run's row so we don't include self.
        history = _load_history(session_id, get_settings().history_turns)

        with create_db_session() as session:
            run = RunRow(
                session_id=session_id,
                dataset_id=dataset_id,
                question=question,
                status="pending",
                attempts=0,
                used_fallback=False,
                created_at=_now(),
            )
            session.add(run)
            session.flush()
            run_id = run.id

        _log.info(
            "node_init",
            run_id=run_id,
            dataset_id=dataset_id,
            session_id=session_id,
            history_turns=len(history),
        )
        return {
            **state,
            "run_id": run_id,
            "history": history,
            "profile": entry.profile,
            "sample": entry.sample,
            "attempts": 0,
            "last_traceback": None,
            "used_fallback": False,
            "assumptions": [],
            "token_usage": {"prompt": 0, "completion": 0, "total": 0},
            "step_trace": [{"step": "profiling", "status": "done", "attempt": 0}],
            "chart_spec": None,
            "error": None,
        }
    except Exception as exc:
        _log.error("node_init_failed", error=str(exc))
        return {**state, "error": f"init failed: {exc}"}


def node_write_code(state: AgentState) -> AgentState:
    try:
        system = _load_prompt("write_code.md")
        profile = state["profile"]
        parts = [
            f"Question: {state['question']}",
            f"Profile: {json.dumps(profile)}",
            f"Sample:\n{state['sample']}",
        ]
        hist = _history_block(state.get("history"))
        if hist:
            parts.append(hist)
        if state.get("last_traceback"):
            parts.append(
                "Your previous code failed with this traceback. Fix it:\n"
                f"{state['last_traceback']}"
            )
        text, usage = LLMClient().call_model_with_usage(
            "\n\n".join(parts), system=system, json_mode=True
        )
        code = _extract_code(text)
        trace = list(state.get("step_trace", []))
        trace.append(
            {"step": "writing_code", "status": "done", "attempt": state.get("attempts", 0) + 1}
        )
        _log.info("node_write_code", run_id=state.get("run_id"), tokens=usage.get("total"))
        return {
            **state,
            "code": code,
            "token_usage": _accumulate(state.get("token_usage", {}), usage),
            "step_trace": trace,
        }
    except Exception as exc:
        _log.error("node_write_code_failed", error=str(exc))
        return {**state, "error": f"LLM_UNAVAILABLE: {exc}"}


def node_execute_code(state: AgentState) -> AgentState:
    settings = get_settings()
    entry = get_store().get(state["dataset_id"])
    trace = list(state.get("step_trace", []))
    attempts = state.get("attempts", 0) + 1

    if entry is None:
        return {**state, "attempts": attempts, "error": "DATASET_NOT_FOUND"}

    res = execute_pandas(state["code"], entry.dataframe, timeout_s=settings.code_timeout_s)

    if res.ok:
        trace.append({"step": "running_code", "status": "done", "attempt": attempts})
        _log.info("node_execute_code", run_id=state.get("run_id"), attempt=attempts, status="done")
        return {
            **state,
            "attempts": attempts,
            "result_repr": res.result_repr,
            "last_traceback": None,
            "step_trace": trace,
        }

    status = "retry" if attempts < settings.max_code_attempts else "error"
    trace.append({"step": "running_code", "status": status, "attempt": attempts})
    _log.info(
        "node_execute_code",
        run_id=state.get("run_id"),
        attempt=attempts,
        status=status,
        traceback=res.traceback,
    )
    return {
        **state,
        "attempts": attempts,
        "last_traceback": res.traceback,
        "step_trace": trace,
    }


def node_synthesize_answer(state: AgentState) -> AgentState:
    try:
        system = _load_prompt("synthesize.md")
        hist = _history_block(state.get("history"))
        prompt = (
            (f"{hist}\n\n" if hist else "")
            + f"Question: {state['question']}\n\n"
            + f"Executed code:\n{state.get('code')}\n\n"
            + f"Computed result:\n{state.get('result_repr')}"
        )
        text, usage = LLMClient().call_model_with_usage(
            prompt, system=system, json_mode=True
        )
        parsed = _parse_json(text) or {}
        trace = list(state.get("step_trace", []))
        trace.append({"step": "synthesizing", "status": "done", "attempt": 0})
        assumptions = parsed.get("assumptions") or []
        _log.info("node_synthesize_answer", run_id=state.get("run_id"), tokens=usage.get("total"))
        return {
            **state,
            "answer": parsed.get("answer") or (state.get("result_repr") or ""),
            "method_note": parsed.get("method_note"),
            "assumptions": list(assumptions),
            "token_usage": _accumulate(state.get("token_usage", {}), usage),
            "step_trace": trace,
        }
    except Exception as exc:
        _log.error("node_synthesize_failed", error=str(exc))
        return {**state, "error": f"LLM_UNAVAILABLE: {exc}"}


def node_build_chart(state: AgentState) -> AgentState:
    # Chart is optional — never fatal.
    try:
        system = _load_prompt("chart.md")
        prompt = (
            f"Question: {state['question']}\n\n"
            f"Computed result:\n{state.get('result_repr')}"
        )
        text, usage = LLMClient().call_model_with_usage(
            prompt, system=system, json_mode=True
        )
        spec = _parse_json(text)
        if not isinstance(spec, dict):
            spec = None
        _log.info("node_build_chart", run_id=state.get("run_id"), has_chart=spec is not None)
        return {
            **state,
            "chart_spec": spec,
            "token_usage": _accumulate(state.get("token_usage", {}), usage),
        }
    except Exception as exc:
        _log.warning("node_build_chart_failed", error=str(exc))
        return {**state, "chart_spec": None}


def node_fallback_reason(state: AgentState) -> AgentState:
    try:
        system = _load_prompt("fallback.md")
        hist = _history_block(state.get("history"))
        prompt = (
            (f"{hist}\n\n" if hist else "")
            + f"Question: {state['question']}\n\n"
            f"Profile: {json.dumps(state['profile'])}\n\n"
            f"Sample:\n{state['sample']}\n\n"
            f"Last error:\n{state.get('last_traceback')}"
        )
        text, usage = LLMClient().call_model_with_usage(
            prompt, system=system, json_mode=True
        )
        parsed = _parse_json(text) or {}
        assumptions = parsed.get("assumptions") or []
        if "answer is approximate, computed from a sample" not in assumptions:
            assumptions = list(assumptions) + ["answer is approximate, computed from a sample"]
        trace = list(state.get("step_trace", []))
        trace.append({"step": "synthesizing", "status": "done", "attempt": 0})
        _log.info("node_fallback_reason", run_id=state.get("run_id"))
        return {
            **state,
            "answer": parsed.get("answer") or "Unable to compute a precise answer.",
            "method_note": parsed.get("method_note") or "Reasoned over a sample of the data.",
            "assumptions": list(assumptions),
            "used_fallback": True,
            "chart_spec": None,
            "token_usage": _accumulate(state.get("token_usage", {}), usage),
            "step_trace": trace,
        }
    except Exception as exc:
        _log.error("node_fallback_failed", error=str(exc))
        return {**state, "error": f"LLM_UNAVAILABLE: {exc}"}


def node_finalize(state: AgentState) -> AgentState:
    usage = state.get("token_usage", {}) or {}
    with create_db_session() as session:
        run = session.get(RunRow, state["run_id"])
        if run is not None:
            run.status = "completed"
            run.answer = state.get("answer")
            run.method_note = state.get("method_note")
            run.executed_code = state.get("code")
            run.result_repr = state.get("result_repr")
            run.chart_spec = state.get("chart_spec")
            run.assumptions = state.get("assumptions") or []
            run.attempts = state.get("attempts", 0)
            run.used_fallback = bool(state.get("used_fallback", False))
            run.token_prompt = usage.get("prompt", 0)
            run.token_completion = usage.get("completion", 0)
            run.token_total = usage.get("total", 0)
            run.completed_at = _now()

    append_query_log(
        dataset_id=state["dataset_id"],
        question=state["question"],
        answer=state.get("answer"),
        token_total=usage.get("total", 0),
        attempts=state.get("attempts", 0),
        ok=True,
    )
    _log.info("node_finalize", run_id=state.get("run_id"), status="completed")
    return {**state, "checkpoint": "finalize"}


def node_handle_error(state: AgentState) -> AgentState:
    error = state.get("error")
    with create_db_session() as session:
        run_id = state.get("run_id")
        if run_id is not None:
            run = session.get(RunRow, run_id)
            if run is not None:
                run.status = "failed"
                run.error_message = error
                run.attempts = state.get("attempts", 0)
                run.completed_at = _now()
    append_query_log(
        dataset_id=state.get("dataset_id", ""),
        question=state.get("question", ""),
        answer=None,
        token_total=(state.get("token_usage") or {}).get("total", 0),
        attempts=state.get("attempts", 0),
        ok=False,
    )
    _log.error("node_handle_error", run_id=state.get("run_id"), error=error)
    return {**state, "checkpoint": "handle_error"}
