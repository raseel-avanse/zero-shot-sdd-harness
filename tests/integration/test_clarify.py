"""Real-Gemini clarify-gate check — QUOTA-GUARDED (1 real call max).

Free-tier Gemini (~20 grounded req/day). This makes ONE cheap non-grounded call
and skips (does not fail) on a 429/RESOURCE_EXHAUSTED or absent key.
"""
import pytest

from graph import nodes


@pytest.fixture
def _require_gemini_key():
    from config.settings import get_settings
    if not get_settings().gemini_api_key:
        pytest.skip("No AGENT_GEMINI_API_KEY set in .env")


_QUOTA_MARKERS = ("429", "resource_exhausted", "quota", "rate limit", "too many requests")


@pytest.mark.usefixtures("_require_gemini_key")
def test_ambiguous_query_is_gated_real(_isolated_db):
    """A deliberately vague query -> Gemini asks ONE clarifying question."""
    try:
        needs, question = nodes.check_clarification("name", "good phone")
    except Exception as exc:  # noqa: BLE001
        if any(m in str(exc).lower() for m in _QUOTA_MARKERS):
            pytest.skip(f"Gemini quota exhausted — skipping real call: {exc}")
        raise

    assert needs is True, "expected 'good phone' to be judged ambiguous"
    assert question and question.strip(), "expected a single clarifying question"
