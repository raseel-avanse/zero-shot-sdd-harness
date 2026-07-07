"""Kick a Sentinel assessment run through the compiled LangGraph.

`run_assessment` is invoked from a FastAPI BackgroundTask after the API has
already created the `assessment_runs` row (so `run_id` exists for the graph
nodes to persist progress/findings against). It loads the engagement + its
scope record, builds the initial AgentState, marks the run `running`, and
invokes the graph. The graph nodes own all progress/finding persistence; on an
unexpected top-level failure we defensively mark the run `failed`.

Importable with no side effects.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from db.models import AssessmentRun, Engagement
from db.session import create_db_session
from graph.agent import agentic_ai
from graph.state import AgentState

log = logging.getLogger("sentinel.runner")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_initial_state(run: AssessmentRun, engagement: Engagement) -> AgentState:
    scope = engagement.scope_record
    allowlist = list(scope.authorized_targets) if scope else []
    non_destructive = bool(scope.non_destructive_only) if scope else True
    return {
        "run_id": run.id,
        "engagement_id": engagement.id,
        "target_path": engagement.target_ref,
        "scope_allowlist": allowlist,
        "non_destructive_only": non_destructive,
        "step_budget": int(run.step_budget or 0),
        "step_count": 0,
        "status": "running",
        "error": None,
    }


def run_assessment(run_id: str) -> None:
    """Execute the assessment graph for an already-created run row."""
    # Load run + engagement + scope, and flip the run to `running`.
    try:
        with create_db_session() as session:
            run = session.get(AssessmentRun, run_id)
            if run is None:
                log.error("run_assessment: run not found", extra={"run_id": run_id})
                return
            engagement = session.get(Engagement, run.engagement_id)
            if engagement is None:
                run.status = "failed"
                run.error_message = "engagement not found"
                run.completed_at = _now()
                return
            initial = _build_initial_state(run, engagement)
            run.status = "running"
            run.started_at = _now()
            run.step_budget = initial["step_budget"]
    except Exception:  # noqa: BLE001
        log.exception("run_assessment: init failed", extra={"run_id": run_id})
        _mark_failed(run_id, "run initialization failed")
        return

    # Invoke the graph. Nodes persist progress/findings and finalize the run
    # (report -> completed, handle_error -> failed). Recursion limit generously
    # bounds the hunt loop (<= 4 categories) well within budget.
    try:
        agentic_ai.invoke(initial, config={"recursion_limit": 100})
    except Exception as exc:  # noqa: BLE001
        log.exception("run_assessment: graph failed", extra={"run_id": run_id})
        _mark_failed(run_id, f"assessment failed: {exc}")


def _mark_failed(run_id: str, message: str) -> None:
    try:
        with create_db_session() as session:
            run = session.get(AssessmentRun, run_id)
            if run is None:
                return
            run.status = "failed"
            run.error_message = message
            run.completed_at = _now()
    except Exception:  # noqa: BLE001
        log.exception("run_assessment: could not mark failed", extra={"run_id": run_id})
