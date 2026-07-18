"""Pure cost-estimation tool: token usage -> estimated INR cost."""

from config.settings import get_settings


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None = None,
) -> float:
    """Estimate the INR cost of a run from its token usage.

    Uses a single configurable blended rate (`AGENT_COST_INR_PER_1K_TOKENS`)
    applied to the combined prompt + completion token count. Pure — cannot fail.
    `model` is accepted for forward-compatibility (per-model rates) but the P1
    estimate uses one blended rate.
    """
    rate_per_1k = get_settings().cost_inr_per_1k_tokens
    total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    return round(total_tokens / 1000.0 * rate_per_1k, 4)
