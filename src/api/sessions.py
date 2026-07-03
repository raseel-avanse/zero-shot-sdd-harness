"""Session list + replay endpoints (Phase 2). See spec/api.md."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select, func

from api._common import ok, api_error
from db.models import RunRow, SessionRow
from db.session import create_db_session
from domain.dataset_store import get_store
from observability.events import get_logger

router = APIRouter(prefix="/api")
_log = get_logger("api")


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _profile_summary(profile: dict | None) -> dict:
    profile = profile or {}
    columns = profile.get("columns") or []
    return {
        "row_count": profile.get("row_count"),
        "column_names": [c.get("name") for c in columns],
    }


def _turn_element(run: RunRow) -> dict:
    """The pinned GET /api/sessions/{id} turn element (spec/api.md)."""
    return {
        "run_id": run.id,
        "question": run.question,
        "created_at": _iso(run.created_at),
        "answer": run.answer,
        "method_note": run.method_note,
        "executed_code": run.executed_code,
        "result_repr": run.result_repr,
        "assumptions": run.assumptions or [],
        "chart_spec": run.chart_spec,
        "token_usage": {
            "prompt": run.token_prompt or 0,
            "completion": run.token_completion or 0,
            "total": run.token_total or 0,
        },
        "attempts": run.attempts or 0,
        "used_fallback": bool(run.used_fallback),
        "status": run.status,
    }


@router.get("/sessions")
def list_sessions() -> dict:
    store = get_store()
    with create_db_session() as session:
        sessions = (
            session.execute(
                select(SessionRow).order_by(
                    SessionRow.updated_at.desc(), SessionRow.created_at.desc()
                )
            )
            .scalars()
            .all()
        )
        # turn counts per session
        counts = dict(
            session.execute(
                select(RunRow.session_id, func.count(RunRow.id)).group_by(
                    RunRow.session_id
                )
            ).all()
        )
        out = [
            {
                "session_id": s.id,
                "title": s.title,
                "dataset_id": s.dataset_id,
                "profile_summary": _profile_summary(s.profile_snapshot),
                "turn_count": int(counts.get(s.id, 0)),
                "created_at": _iso(s.created_at),
                "updated_at": _iso(s.updated_at),
                "dataframe_loaded": s.dataset_id in store,
            }
            for s in sessions
        ]
    return ok(out)


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    store = get_store()
    with create_db_session() as session:
        sess = session.get(SessionRow, session_id)
        if sess is None:
            raise api_error("SESSION_NOT_FOUND", "Session not found.", 404)
        runs = (
            session.execute(
                select(RunRow)
                .where(RunRow.session_id == session_id)
                .order_by(RunRow.created_at.asc(), RunRow.id.asc())
            )
            .scalars()
            .all()
        )
        data = {
            "session_id": sess.id,
            "title": sess.title,
            "dataset_id": sess.dataset_id,
            "dataframe_loaded": sess.dataset_id in store,
            "profile": sess.profile_snapshot,
            "turns": [_turn_element(r) for r in runs],
        }
    return ok(data)
