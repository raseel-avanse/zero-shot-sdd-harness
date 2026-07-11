"""Pure helpers for the deal-quality assessment node.

Parsing the batched Gemini JSON and merging labels onto ranked deals is kept
here (pure, no external systems) so it is fully unit-testable without any LLM
call. The node in `graph/nodes.py` owns the single grounded Gemini call.
"""
import json

VALID_LABELS = {"genuine_discount", "wait", "unknown"}


def parse_quality_response(raw: str) -> dict[int, dict]:
    """Parse the model's batched quality JSON into a {rank: {label, reason}} map.

    Accepts either {"assessments": [...]} or a bare list. Strips markdown fences
    if present. Raises on invalid JSON so the caller can degrade gracefully.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip()
    data = json.loads(text)
    items = data.get("assessments", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("Expected a JSON list of assessments")

    out: dict[int, dict] = {}
    for item in items:
        if not isinstance(item, dict) or "rank" not in item:
            continue
        rank = int(item["rank"])
        label = str(item.get("quality_label", "unknown")).strip().lower()
        if label not in VALID_LABELS:
            label = "unknown"
        reason = str(item.get("quality_reason", "") or "").strip()
        out[rank] = {"quality_label": label, "quality_reason": reason}
    return out


def merge_quality(deals: list[dict], assessments: dict[int, dict]) -> list[dict]:
    """Return a new deals list with quality_label/quality_reason merged in.

    Any deal without a matching assessment (or on empty input) degrades to
    the `unknown` label — never fatal.
    """
    merged: list[dict] = []
    for deal in deals:
        d = dict(deal)
        a = assessments.get(d.get("rank"))
        if a:
            d["quality_label"] = a["quality_label"]
            d["quality_reason"] = a["quality_reason"] or None
        else:
            d["quality_label"] = "unknown"
            d["quality_reason"] = d.get("quality_reason") or None
        merged.append(d)
    return merged
