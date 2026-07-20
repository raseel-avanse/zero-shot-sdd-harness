from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Portable JSON: JSONB on Postgres (the gate DB), plain JSON on SQLite (unit fixture).
_JSON = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class Engagement(Base):
    """A scoped security assessment against one target."""

    __tablename__ = "engagements"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # target_type enum: repo | live_app  (Phase 1: repo only)
    target_type: Mapped[str] = mapped_column(Text, nullable=False, default="repo")
    target_ref: Mapped[str] = mapped_column(Text, nullable=False)
    # assessment_profile enum: general | owasp_api (Phase 4). Selects the
    # live-hunt category taxonomy; only meaningful for live_app.
    assessment_profile: Mapped[str] = mapped_column(
        Text, nullable=True, default="general"
    )
    # Optional OpenAPI/Swagger source (URL or local file path) for endpoint
    # enumeration (Phase 4). Raw spec content is NOT persisted.
    api_spec_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    # status enum: draft | active | completed | archived
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    scope_record: Mapped["ScopeRecord | None"] = relationship(
        back_populates="engagement", uselist=False, cascade="all, delete-orphan"
    )
    runs: Mapped[list["AssessmentRun"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    chat_turns: Mapped[list["ChatTurn"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )


class ScopeRecord(Base):
    """The authorization record; 1:1 with an engagement."""

    __tablename__ = "scope_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(
        Text, ForeignKey("engagements.id"), nullable=False, unique=True
    )
    # In-code allowlist: absolute repo paths / hosts (JSON string[])
    authorized_targets: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    rules_of_engagement: Mapped[str] = mapped_column(Text, nullable=False)
    authorized_by: Mapped[str] = mapped_column(Text, nullable=False)
    non_destructive_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )

    engagement: Mapped["Engagement"] = relationship(back_populates="scope_record")


class AssessmentRun(Base):
    """One assessment run over the engagement's target; holds progress + token/cost."""

    __tablename__ = "assessment_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(
        Text, ForeignKey("engagements.id"), nullable=False
    )
    # status enum: pending | running | completed | failed
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    # recon | prioritize | hunt | validate | report
    current_phase: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(
        Numeric(10, 6), nullable=False, default=0
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Proactive next-probe suggestions produced by the report node (Phase 3):
    # a JSON array of concrete "what to investigate next" strings.
    suggestions: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    engagement: Mapped["Engagement"] = relationship(back_populates="runs")
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Finding(Base):
    """One validated (or unconfirmed) vulnerability finding."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(
        Text, ForeignKey("engagements.id"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assessment_runs.id"), nullable=False
    )
    # category enum: injection | broken_auth | secrets_misconfig | vuln_deps
    category: Mapped[str] = mapped_column(Text, nullable=False)
    # Canonical OWASP API category ID+title (Phase 4), e.g.
    # "API1:2023 — Broken Object Level Authorization". Null for non-OWASP findings.
    owasp_api_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # severity_label enum: critical | high | medium | low | info
    severity_label: Mapped[str] = mapped_column(Text, nullable=False)
    cvss_score: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Bounded excerpts only — never whole source files.
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    # confidence enum: confirmed | tentative | unconfirmed
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    # status enum: new | validated | remediated | false_positive
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    remediation: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_patch: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Links same-pattern occurrences (Phase 3)
    pattern_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    engagement: Mapped["Engagement"] = relationship(back_populates="findings")
    run: Mapped["AssessmentRun"] = relationship(back_populates="findings")


class ChatTurn(Base):
    """Conversation memory for interactive chat over an engagement (Phase 2)."""

    __tablename__ = "chat_turns"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(
        Text, ForeignKey("engagements.id"), nullable=False
    )
    # role enum: user | assistant
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )

    engagement: Mapped["Engagement"] = relationship(back_populates="chat_turns")
