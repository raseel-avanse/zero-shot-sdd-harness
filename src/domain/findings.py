"""Pydantic response model for findings (spec/api.md + spec/data.md)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FindingOut(BaseModel):
    id: str
    engagement_id: str
    run_id: str
    category: str
    title: str
    severity_label: str
    cvss_score: float | None = None
    location: str
    description: str
    evidence: str
    confidence: str
    status: str
    remediation: str
    suggested_patch: str | None = None
    created_at: datetime
    updated_at: datetime
