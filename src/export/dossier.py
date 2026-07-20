"""Assemble the structured engagement dossier from persisted rows.

The dossier is a plain, JSON-serialisable dict — the single source the MD /
JSON / PDF renderers all consume, so the three formats never drift.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import AssessmentRun, Engagement, Finding, ScopeRecord


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _num(value) -> float | None:
    return float(value) if value is not None else None


def _finding_dict(f: Finding) -> dict:
    return {
        "id": f.id,
        "run_id": f.run_id,
        "category": f.category,
        "title": f.title,
        "severity_label": f.severity_label,
        "cvss_score": _num(f.cvss_score),
        "confidence": f.confidence,
        "status": f.status,
        "location": f.location,
        "description": f.description,
        # Bounded excerpt / PoC evidence only — never whole source files.
        "evidence": f.evidence,
        "remediation": f.remediation,
        "suggested_patch": f.suggested_patch,
        "created_at": _iso(f.created_at),
        "updated_at": _iso(f.updated_at),
    }


def _scope_dict(scope: ScopeRecord | None) -> dict | None:
    if scope is None:
        return None
    return {
        "authorized_targets": list(scope.authorized_targets or []),
        "rules_of_engagement": scope.rules_of_engagement,
        "authorized_by": scope.authorized_by,
        "non_destructive_only": scope.non_destructive_only,
        "created_at": _iso(scope.created_at),
    }


def _run_dict(run: AssessmentRun) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "current_phase": run.current_phase,
        "step_count": run.step_count,
        "step_budget": run.step_budget,
        "prompt_tokens": int(run.prompt_tokens or 0),
        "completion_tokens": int(run.completion_tokens or 0),
        "total_tokens": int(run.total_tokens or 0),
        "estimated_cost_usd": _num(run.estimated_cost_usd) or 0.0,
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
    }


def build_dossier(session: Session, engagement: Engagement) -> dict:
    """Return the full structured dossier dict for one engagement."""
    findings = session.execute(
        select(Finding)
        .where(Finding.engagement_id == engagement.id)
        .order_by(Finding.created_at.asc())
    ).scalars().all()

    runs = session.execute(
        select(AssessmentRun)
        .where(AssessmentRun.engagement_id == engagement.id)
        .order_by(AssessmentRun.started_at.asc().nullslast())
    ).scalars().all()

    run_dicts = [_run_dict(r) for r in runs]
    cost_totals = {
        "prompt_tokens": sum(r["prompt_tokens"] for r in run_dicts),
        "completion_tokens": sum(r["completion_tokens"] for r in run_dicts),
        "total_tokens": sum(r["total_tokens"] for r in run_dicts),
        "estimated_cost_usd": round(
            sum(r["estimated_cost_usd"] for r in run_dicts), 6
        ),
    }

    # Severity rollup for the dossier summary.
    severity_counts: dict[str, int] = {}
    for f in findings:
        severity_counts[f.severity_label] = severity_counts.get(f.severity_label, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engagement": {
            "id": engagement.id,
            "name": engagement.name,
            "target_type": engagement.target_type,
            "target_ref": engagement.target_ref,
            "status": engagement.status,
            "created_at": _iso(engagement.created_at),
            "updated_at": _iso(engagement.updated_at),
        },
        "scope": _scope_dict(engagement.scope_record),
        "summary": {
            "finding_count": len(findings),
            "severity_counts": severity_counts,
        },
        "findings": [_finding_dict(f) for f in findings],
        "runs": run_dicts,
        "cost_totals": cost_totals,
    }
