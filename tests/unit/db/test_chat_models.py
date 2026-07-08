"""Unit tests for the Phase 2 ChatTurn model (spec/data.md — ChatTurn).

Runs against the SQLite fixture (portable types) from conftest; the GATE
re-runs schema creation against real Postgres via alembic.
"""
from datetime import datetime


def test_chat_turn_importable_with_columns():
    from db.models import ChatTurn

    cols = {c.name for c in ChatTurn.__table__.columns}
    assert cols == {"id", "engagement_id", "role", "content", "created_at"}
    assert ChatTurn.__tablename__ == "chat_turns"


def test_chat_turns_table_registered():
    from db.models import Base

    assert "chat_turns" in Base.metadata.tables


def test_existing_phase1_tables_intact():
    from db.models import Base

    assert {
        "engagements",
        "scope_records",
        "assessment_runs",
        "findings",
        "chat_turns",
    } <= set(Base.metadata.tables)


def test_chat_turn_persist_and_relationship(_isolated_db):
    from sqlalchemy.orm import Session

    from db.models import ChatTurn, Engagement

    with Session(_isolated_db) as s:
        eng = Engagement(name="e", target_type="repo", target_ref="/tmp/repo")
        turn = ChatTurn(engagement=eng, role="user", content="hello")
        s.add(turn)
        s.commit()
        s.refresh(turn)
        assert turn.id
        assert turn.role == "user"
        assert turn.content == "hello"
        assert isinstance(turn.created_at, datetime)
        assert eng.chat_turns == [turn]
