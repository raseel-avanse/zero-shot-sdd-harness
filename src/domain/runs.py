"""Pydantic request/response models for the runs surface (spec/api.md)."""
from __future__ import annotations

from pydantic import BaseModel


class StartRunRequest(BaseModel):
    # Uses the engagement's target + scope; optional budget override.
    step_budget: int | None = None


class StartRunResponse(BaseModel):
    run_id: str
    status: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    current_phase: str | None = None
    current_category: str | None = None
    step_count: int
    step_budget: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    error_message: str | None = None


class RunCostResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    model_rates: dict
