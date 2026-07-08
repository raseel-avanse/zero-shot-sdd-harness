"""Engagements surface: scope-gated engagement create/list/get + findings list.

Scope is persisted here (the scope form) and enforced IN CODE: creating an
engagement records the allowlist; a run whose target is not contained in that
allowlist is refused (422) — see api/runs.py and the enforce_scope graph node.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import api_error, ok
from db.models import Engagement, Finding, ScopeRecord
from db.session import get_session
from domain.engagements import (
    CreateEngagementRequest,
    EngagementDetail,
    EngagementListItem,
    EngagementOut,
    ScopeRecordOut,
)
from domain.findings import FindingOut

router = APIRouter()


def _scope_out(scope: ScopeRecord) -> ScopeRecordOut:
    return ScopeRecordOut(
        id=scope.id,
        engagement_id=scope.engagement_id,
        authorized_targets=list(scope.authorized_targets or []),
        rules_of_engagement=scope.rules_of_engagement,
        authorized_by=scope.authorized_by,
        non_destructive_only=scope.non_destructive_only,
        created_at=scope.created_at,
    )


@router.post("/engagements")
def create_engagement(
    req: CreateEngagementRequest, session: Session = Depends(get_session)
) -> dict:
    if req.target_type not in ("repo", "live_app"):
        raise api_error("INVALID_TARGET", f"unknown target_type: {req.target_type}", 400)

    try:
        engagement = Engagement(
            name=req.name,
            target_type=req.target_type,
            target_ref=req.target_ref,
            status="draft",
        )
        scope = ScopeRecord(
            engagement=engagement,
            authorized_targets=list(req.authorized_targets),
            rules_of_engagement=req.rules_of_engagement,
            authorized_by=req.authorized_by,
            non_destructive_only=req.non_destructive_only,
        )
        session.add(engagement)
        session.add(scope)
        session.flush()
        engagement_id = engagement.id
        status = engagement.status
    except Exception as exc:  # noqa: BLE001
        raise api_error("DB_WRITE_FAILED", f"could not persist engagement: {exc}", 500)

    return ok({"engagement_id": engagement_id, "status": status})


@router.get("/engagements")
def list_engagements(session: Session = Depends(get_session)) -> dict:
    rows = session.execute(
        select(Engagement).order_by(Engagement.created_at.desc())
    ).scalars().all()
    items = [
        EngagementListItem(
            engagement_id=e.id,
            name=e.name,
            target_type=e.target_type,
            status=e.status,
            created_at=e.created_at,
        ).model_dump()
        for e in rows
    ]
    return ok(items)


@router.get("/engagements/{engagement_id}")
def get_engagement(engagement_id: str, session: Session = Depends(get_session)) -> dict:
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise api_error("NOT_FOUND", f"engagement {engagement_id} not found", 404)
    detail = EngagementDetail(
        engagement=EngagementOut(
            id=engagement.id,
            name=engagement.name,
            target_type=engagement.target_type,
            target_ref=engagement.target_ref,
            status=engagement.status,
            created_at=engagement.created_at,
            updated_at=engagement.updated_at,
        ),
        scope_record=_scope_out(engagement.scope_record)
        if engagement.scope_record
        else None,
    )
    return ok(detail.model_dump())


@router.get("/engagements/{engagement_id}/findings")
def list_findings(engagement_id: str, session: Session = Depends(get_session)) -> dict:
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise api_error("NOT_FOUND", f"engagement {engagement_id} not found", 404)
    rows = session.execute(
        select(Finding)
        .where(Finding.engagement_id == engagement_id)
        .order_by(Finding.created_at.asc())
    ).scalars().all()
    items = [
        FindingOut(
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
        ).model_dump()
        for f in rows
    ]
    return ok(items)
