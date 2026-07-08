"""Runs surface: start an assessment (scope-gated background task), read status/
cost, and stream live progress + findings over SSE by tailing Postgres.

Scope is enforced IN CODE here (422) before any run row is created: the
engagement's target_ref must be contained in its ScopeRecord.authorized_targets
allowlist. The SSE stream polls the assessment_runs row + findings rows and emits
`progress`, `finding`, `done`, `error` named events until a terminal status.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import api_error, ok
from db.models import AssessmentRun, Engagement, Finding
from db.session import create_db_session, get_session
from domain.findings import FindingOut
from domain.runs import RunCostResponse, RunStatusResponse, StartRunRequest
from graph import runner
from llm import cost as cost_mod
from tools import scope_guard

log = logging.getLogger("sentinel.api.runs")

router = APIRouter()

# SSE poll cadence + a generous ceiling so a stuck run never streams forever.
_POLL_SECONDS = 1.0
_MAX_STREAM_SECONDS = 15 * 60
_TERMINAL = {"completed", "failed"}


def _finding_out(f: Finding) -> dict:
    return FindingOut(
        id=f.id,
        engagement_id=f.engagement_id,
        run_id=f.run_id,
        category=f.category,
        title=f.title,
        severity_label=f.severity_label,
        cvss_score=float(f.cvss_score) if f.cvss_score is not None else None,
        location=f.location,
        description=f.description,
        evidence=f.evidence,
        confidence=f.confidence,
        status=f.status,
        remediation=f.remediation,
        suggested_patch=f.suggested_patch,
        created_at=f.created_at,
        updated_at=f.updated_at,
    ).model_dump(mode="json")


@router.post("/engagements/{engagement_id}/runs")
def start_run(
    engagement_id: str,
    req: StartRunRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise api_error("NOT_FOUND", f"engagement {engagement_id} not found", 404)

    # Refuse a second concurrent run for the same engagement.
    in_progress = session.execute(
        select(AssessmentRun)
        .where(AssessmentRun.engagement_id == engagement_id)
        .where(AssessmentRun.status.in_(["pending", "running"]))
    ).scalars().first()
    if in_progress is not None:
        raise api_error(
            "RUN_IN_PROGRESS",
            f"a run is already in progress for engagement {engagement_id}",
            409,
        )

    # IN-CODE SCOPE ENFORCEMENT (surfaced synchronously, before any run row).
    # Dispatch on target_type: repo -> path containment, live_app -> host
    # allowlist. A live-app engagement whose target host is not authorized is
    # refused here (422) before any run row is created or any probe is issued.
    scope = engagement.scope_record
    allowlist = list(scope.authorized_targets) if scope else []
    if not scope_guard.check_target(
        engagement.target_ref, allowlist, engagement.target_type
    ):
        raise api_error(
            "SCOPE_VIOLATION",
            f"target '{engagement.target_ref}' is not within the authorized scope allowlist",
            422,
        )

    budget = req.step_budget if req.step_budget else cost_mod.step_budget()
    run = AssessmentRun(
        engagement_id=engagement_id,
        status="pending",
        step_budget=int(budget),
    )
    session.add(run)
    # Commit (not just flush) so the row is durably visible to the background
    # worker, which reads it on a SEPARATE connection via create_db_session().
    # A flush stays inside this request's uncommitted transaction and the
    # worker's fresh session would not see it (Postgres READ COMMITTED).
    run.status = "pending"
    session.commit()
    run_id = run.id
    status = run.status

    background_tasks.add_task(runner.run_assessment, run_id)
    return ok({"run_id": run_id, "status": status})


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(AssessmentRun, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"run {run_id} not found", 404)
    return ok(
        RunStatusResponse(
            run_id=run.id,
            status=run.status,
            current_phase=run.current_phase,
            current_category=run.current_category,
            step_count=run.step_count,
            step_budget=run.step_budget,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            total_tokens=run.total_tokens,
            estimated_cost_usd=float(run.estimated_cost_usd or 0),
            error_message=run.error_message,
        ).model_dump()
    )


@router.get("/runs/{run_id}/cost")
def get_run_cost(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(AssessmentRun, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"run {run_id} not found", 404)
    return ok(
        RunCostResponse(
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            total_tokens=run.total_tokens,
            estimated_cost_usd=float(run.estimated_cost_usd or 0),
            model_rates={
                "fast": {
                    "model": cost_mod.model_for_tier("fast"),
                    "per_million": list(cost_mod._rate_for(cost_mod.model_for_tier("fast"))),
                },
                "smart": {
                    "model": cost_mod.model_for_tier("smart"),
                    "per_million": list(cost_mod._rate_for(cost_mod.model_for_tier("smart"))),
                },
            },
        ).model_dump()
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _snapshot(run_id: str, seen_ids: set[str]) -> tuple[dict | None, list[dict], str | None, str | None]:
    """One DB tail read: (progress_payload, new_findings, terminal_status, error).

    Returns progress=None when the run row is missing. Session is opened and
    closed per poll so we never hold a connection across the await sleep.
    """
    with create_db_session() as session:
        run = session.get(AssessmentRun, run_id)
        if run is None:
            return None, [], None, "run not found"
        progress = {
            "current_phase": run.current_phase,
            "current_category": run.current_category,
            "step_count": run.step_count,
            "step_budget": run.step_budget,
            "prompt_tokens": run.prompt_tokens,
            "completion_tokens": run.completion_tokens,
            "total_tokens": run.total_tokens,
            "estimated_cost_usd": float(run.estimated_cost_usd or 0),
        }
        rows = session.execute(
            select(Finding)
            .where(Finding.run_id == run_id)
            .order_by(Finding.created_at.asc())
        ).scalars().all()
        new_findings = [_finding_out(f) for f in rows if f.id not in seen_ids]
        for f in rows:
            seen_ids.add(f.id)
        terminal = run.status if run.status in _TERMINAL else None
        error = run.error_message if run.status == "failed" else None
        return progress, new_findings, terminal, error


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    async def event_gen():
        seen: set[str] = set()
        last_progress: dict | None = None
        elapsed = 0.0
        while True:
            if await request.is_disconnected():
                return
            progress, new_findings, terminal, error = await asyncio.to_thread(
                _snapshot, run_id, seen
            )
            if progress is None:
                yield _sse("error", {"message": error or "run not found"})
                return
            if progress != last_progress:
                yield _sse("progress", progress)
                last_progress = progress
            for finding in new_findings:
                yield _sse("finding", finding)
            if terminal == "completed":
                yield _sse("done", {"status": "completed"})
                return
            if terminal == "failed":
                yield _sse("error", {"message": error or "assessment failed"})
                return
            if elapsed >= _MAX_STREAM_SECONDS:
                yield _sse("error", {"message": "stream timed out waiting for run to finish"})
                return
            await asyncio.sleep(_POLL_SECONDS)
            elapsed += _POLL_SECONDS

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
