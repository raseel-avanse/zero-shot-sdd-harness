"""Model-tier resolution and token-cost accounting.

Defensive settings access: the api-routes slice owns settings.py. Where the
model-tier / step-budget / cost-rate fields do not yet exist on Settings, we
fall back to the AGENT_* env var and then a sane default. New Settings fields
requested from the api-routes slice are listed in the slice hand-off.
"""
from __future__ import annotations

import os

from config.settings import get_settings

# Defaults (per-1M-token USD rates; env-overridable).
_FAST_MODEL = "gemini-3.1-flash"
_SMART_MODEL = "gemini-3.1-pro"
_RATE_FAST = (0.075, 0.30)     # (input, output) per 1M tokens
_RATE_SMART = (1.25, 5.00)
DEFAULT_STEP_BUDGET = 40


def _field(name: str, env: str, default):
    s = get_settings()
    val = getattr(s, name, None)
    if val:
        return val
    env_val = os.getenv(env)
    if env_val:
        return env_val
    return default


def model_for_tier(tier: str) -> str:
    if tier == "smart":
        return _field("llm_model_smart", "AGENT_LLM_MODEL_SMART", _SMART_MODEL)
    return _field("llm_model_fast", "AGENT_LLM_MODEL_FAST", _FAST_MODEL)


def step_budget() -> int:
    return int(_field("step_budget", "AGENT_STEP_BUDGET", DEFAULT_STEP_BUDGET))


def _rate_for(model: str) -> tuple[float, float]:
    if model and "pro" in model.lower():
        return (
            float(os.getenv("AGENT_COST_RATE_SMART_IN", _RATE_SMART[0])),
            float(os.getenv("AGENT_COST_RATE_SMART_OUT", _RATE_SMART[1])),
        )
    return (
        float(os.getenv("AGENT_COST_RATE_FAST_IN", _RATE_FAST[0])),
        float(os.getenv("AGENT_COST_RATE_FAST_OUT", _RATE_FAST[1])),
    )


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rate_in, rate_out = _rate_for(model)
    return (prompt_tokens / 1_000_000) * rate_in + (completion_tokens / 1_000_000) * rate_out
