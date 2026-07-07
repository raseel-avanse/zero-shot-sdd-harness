"""API contract tests — no LLM key required, the graph is not invoked.

Covers the engagements + runs HTTP surface with an isolated DB (conftest).
"""
from __future__ import annotations


def _valid_payload(target: str, allow: list[str]) -> dict:
    return {
        "name": "Test engagement",
        "target_type": "repo",
        "target_ref": target,
        "authorized_targets": allow,
        "rules_of_engagement": "read-only, non-destructive",
        "authorized_by": "tester",
        "non_destructive_only": True,
    }


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_create_and_list_engagement(api_client, tmp_path):
    target = str(tmp_path)
    r = api_client.post("/engagements", json=_valid_payload(target, [target]))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["engagement_id"]
    assert data["status"] == "draft"

    lst = api_client.get("/engagements")
    assert lst.status_code == 200
    items = lst.json()["data"]
    assert any(i["engagement_id"] == data["engagement_id"] for i in items)


def test_get_engagement_includes_scope(api_client, tmp_path):
    target = str(tmp_path)
    eid = api_client.post(
        "/engagements", json=_valid_payload(target, [target])
    ).json()["data"]["engagement_id"]

    r = api_client.get(f"/engagements/{eid}")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["engagement"]["target_ref"] == target
    assert body["scope_record"]["authorized_targets"] == [target]


def test_create_engagement_missing_fields(api_client):
    r = api_client.post("/engagements", json={"name": "x"})
    assert r.status_code == 422


def test_live_app_target_rejected(api_client, tmp_path):
    payload = _valid_payload(str(tmp_path), [str(tmp_path)])
    payload["target_type"] = "live_app"
    r = api_client.post("/engagements", json=payload)
    assert r.status_code == 400


def test_start_run_scope_refusal_422(api_client, tmp_path):
    # target OUTSIDE the allowlist -> run refused synchronously with 422.
    target = str(tmp_path / "outside")
    allow = [str(tmp_path / "allowed")]
    eid = api_client.post(
        "/engagements", json=_valid_payload(target, allow)
    ).json()["data"]["engagement_id"]

    r = api_client.post(f"/engagements/{eid}/runs", json={})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "SCOPE_VIOLATION"


def test_start_run_unknown_engagement_404(api_client):
    r = api_client.post("/engagements/does-not-exist/runs", json={})
    assert r.status_code == 404


def test_get_run_not_found(api_client):
    r = api_client.get("/runs/nonexistent-id")
    assert r.status_code == 404


def test_get_run_cost_not_found(api_client):
    r = api_client.get("/runs/nonexistent-id/cost")
    assert r.status_code == 404
