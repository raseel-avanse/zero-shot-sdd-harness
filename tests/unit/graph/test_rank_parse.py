"""Rank-node JSON parsing / Deal validation — no LLM key required."""
import pytest

from graph.nodes import _parse_deals
from domain.deal import Deal


def test_parses_object_with_deals_key():
    raw = '{"deals": [{"rank": 1, "site": "Amazon.in", "price_inr": 24990, "reason": "cheapest"}]}'
    deals = _parse_deals(raw)
    assert len(deals) == 1
    assert isinstance(deals[0], Deal)
    assert deals[0].site == "Amazon.in"
    assert deals[0].price_inr == 24990


def test_parses_bare_list():
    raw = '[{"rank": 1, "site": "Flipkart", "price_inr": 100, "reason": "ok"}]'
    deals = _parse_deals(raw)
    assert deals[0].site == "Flipkart"


def test_strips_markdown_fences():
    raw = '```json\n{"deals": [{"rank": 1, "site": "Croma", "price_inr": 500, "reason": "x"}]}\n```'
    deals = _parse_deals(raw)
    assert deals[0].site == "Croma"


def test_caps_at_five_deals():
    items = [
        {"rank": i, "site": f"S{i}", "price_inr": i, "reason": "r"} for i in range(1, 9)
    ]
    import json
    deals = _parse_deals(json.dumps({"deals": items}))
    assert len(deals) == 5


def test_empty_deals_list_ok():
    assert _parse_deals('{"deals": []}') == []


def test_invalid_json_raises():
    with pytest.raises(Exception):
        _parse_deals("not json at all")


def test_missing_required_field_raises():
    with pytest.raises(Exception):
        _parse_deals('{"deals": [{"rank": 1, "site": "X"}]}')  # no price/reason
