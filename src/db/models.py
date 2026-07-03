from datetime import datetime, timezone

from sqlalchemy import Integer, Text, TIMESTAMP, Boolean, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    """One conversation against a loaded dataset (Phase 2). See spec/data.md § Session."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    profile_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )


class RunRow(Base):
    """One row per question asked (one agent run / Turn). See spec/data.md § Run."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Phase 2: FK to the session this turn belongs to. Nullable so the migration
    # applies cleanly on an existing DB with pre-Phase-2 runs (session_id=NULL).
    session_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("sessions.id"), nullable=True
    )
    dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    method_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_repr: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart_spec: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    assumptions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    token_prompt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_completion: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
