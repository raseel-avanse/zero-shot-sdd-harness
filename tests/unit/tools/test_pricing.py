"""Cost-estimation tool tests — pure, no LLM key required."""
from tools.pricing import estimate_cost


def test_cost_scales_with_tokens(monkeypatch):
    monkeypatch.setenv("AGENT_COST_INR_PER_1K_TOKENS", "2.0")
    import config.settings as m
    m._settings = None
    # 1000 tokens total at 2.0 INR / 1k => 2.0
    assert estimate_cost(600, 400, "gemini-2.5-flash") == 2.0


def test_cost_zero_for_zero_tokens():
    assert estimate_cost(0, 0, "gemini-2.5-flash") == 0.0


def test_cost_handles_none_tokens():
    # missing usage must degrade to 0, never crash
    assert estimate_cost(None, None, "gemini-2.5-flash") == 0.0


def test_cost_default_rate_positive():
    import config.settings as m
    m._settings = None
    cost = estimate_cost(5000, 1000, "gemini-2.5-flash")
    assert cost > 0
