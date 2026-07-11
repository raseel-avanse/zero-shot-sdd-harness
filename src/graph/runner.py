import os
from concurrent.futures import ThreadPoolExecutor

from graph.agent import agentic_ai
from graph.state import AgentState
from db.session import create_db_session, init_db
from db.models import RunRow
from observability.events import get_logger

log = get_logger("graph.runner")

# Module-level executor: background research runs share this pool. POST /runs
# returns immediately; the graph updates progress + persists as it executes.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dealscout-run")


def _maybe_langsmith() -> None:
    if os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true":
        log.info("langsmith.tracing.enabled")


def _execute(run_id: str, query_type: str, query_text: str) -> None:
    _maybe_langsmith()
    log.info("run.started", run_id=run_id, query_type=query_type)
    initial: AgentState = {
        "run_id": run_id,
        "query_type": query_type,
        "query_text": query_text,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "error": None,
    }
    try:
        agentic_ai.invoke(initial)
    except Exception as exc:  # noqa: BLE001 — last-resort guard for the worker thread
        log.error("run.crashed", run_id=run_id, error=str(exc))
        with create_db_session() as session:
            run = session.get(RunRow, run_id)
            if run is not None:
                run.status = "failed"
                run.error_message = f"Research failed: {exc}"


def start_run(query_type: str, query_text: str) -> str:
    """Create a run row (status=running) and launch the graph in the background."""
    init_db()
    with create_db_session() as session:
        run = RunRow(
            query_type=query_type or "name",
            query_text=query_text,
            status="running",
            progress_step="queued",
        )
        session.add(run)
        session.flush()
        run_id = run.id

    _executor.submit(_execute, run_id, query_type or "name", query_text)
    return run_id
