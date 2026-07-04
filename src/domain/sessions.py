"""Session lifecycle helpers (Phase 2). See spec/data.md § Session.

A Session owns one conversation against a loaded dataset. It is created on upload
and its `dataset_id` tracks the current in-memory dataframe key. A Turn is a
`runs` row scoped by `session_id`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from db.models import SessionRow


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_session(session: OrmSession, *, dataset_id: str, title: str | None, profile: dict) -> str:
    """Create a new session for a fresh upload; returns the new session_id."""
    session_id = str(uuid4())
    now = _now()
    row = SessionRow(
        id=session_id,
        title=title or None,
        dataset_id=dataset_id,
        profile_snapshot=profile,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return session_id


def resolve_session_for_dataset(session: OrmSession, dataset_id: str) -> SessionRow | None:
    """Find the session that currently owns this dataset_id (most recent)."""
    return (
        session.execute(
            select(SessionRow)
            .where(SessionRow.dataset_id == dataset_id)
            .order_by(SessionRow.updated_at.desc(), SessionRow.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def touch_session(session: OrmSession, session_id: str) -> None:
    """Bump updated_at on activity (ask)."""
    row = session.get(SessionRow, session_id)
    if row is not None:
        row.updated_at = _now()
