"""Pydantic request/response models for the engagements surface (spec/api.md)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateEngagementRequest(BaseModel):
    name: str = Field(min_length=1)
    target_type: str = "repo"
    target_ref: str = Field(min_length=1)
    authorized_targets: list[str] = Field(min_length=1)
    rules_of_engagement: str = Field(min_length=1)
    authorized_by: str = Field(min_length=1)
    non_destructive_only: bool = True


class CreateEngagementResponse(BaseModel):
    engagement_id: str
    status: str


class EngagementListItem(BaseModel):
    engagement_id: str
    name: str
    target_type: str
    status: str
    created_at: datetime


class ScopeRecordOut(BaseModel):
    id: str
    engagement_id: str
    authorized_targets: list[str]
    rules_of_engagement: str
    authorized_by: str
    non_destructive_only: bool
    created_at: datetime


class EngagementOut(BaseModel):
    id: str
    name: str
    target_type: str
    target_ref: str
    status: str
    created_at: datetime
    updated_at: datetime


class EngagementDetail(BaseModel):
    engagement: EngagementOut
    scope_record: ScopeRecordOut | None
