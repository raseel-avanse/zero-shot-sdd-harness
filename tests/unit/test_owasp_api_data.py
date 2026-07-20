"""Phase 4 OWASP API data-slice tests — no LLM required (isolated DB via conftest).

Covers the additive engagement fields (assessment_profile, api_spec_ref) and the
new finding field (owasp_api_ref) round-tripping through the HTTP surface.
"""
from __future__ import annotations


def _payload(target: str, allow: list[str]) -> dict:
    return {
        "name": "OWASP API engagement",
        "target_type": "live_app",
        "target_ref": target,
        "authorized_targets": allow,
        "rules_of_engagement": "read-only, non-destructive",
        "authorized_by": "tester",
        "non_destructive_only": True,
    }


def test_owasp_profile_persists_and_echoes(api_client):
    payload = _payload("http://localhost:9999", ["localhost:9999"])
    payload["assessment_profile"] = "owasp_api"
    payload["api_spec_ref"] = "http://localhost:9999/openapi.json"

    r = api_client.post("/engagements", json=payload)
    assert r.status_code == 200, r.text
    eid = r.json()["data"]["engagement_id"]

    # GET detail echoes both new fields.
    detail = api_client.get(f"/engagements/{eid}").json()["data"]["engagement"]
    assert detail["assessment_profile"] == "owasp_api"
    assert detail["api_spec_ref"] == "http://localhost:9999/openapi.json"

    # List echoes them too.
    items = api_client.get("/engagements").json()["data"]
    mine = next(i for i in items if i["engagement_id"] == eid)
    assert mine["assessment_profile"] == "owasp_api"
    assert mine["api_spec_ref"] == "http://localhost:9999/openapi.json"


def test_default_profile_is_general(api_client):
    payload = _payload("http://localhost:9999", ["localhost:9999"])
    r = api_client.post("/engagements", json=payload)
    assert r.status_code == 200, r.text
    eid = r.json()["data"]["engagement_id"]
    detail = api_client.get(f"/engagements/{eid}").json()["data"]["engagement"]
    assert detail["assessment_profile"] == "general"
    assert detail["api_spec_ref"] is None


def test_invalid_profile_rejected_400(api_client):
    payload = _payload("http://localhost:9999", ["localhost:9999"])
    payload["assessment_profile"] = "bogus"
    r = api_client.post("/engagements", json=payload)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_PROFILE"


def test_finding_owasp_ref_returned_via_findings_endpoint(api_client):
    # Create the engagement via the API, then seed a run + OWASP-tagged finding.
    payload = _payload("http://localhost:9999", ["localhost:9999"])
    payload["assessment_profile"] = "owasp_api"
    eid = api_client.post("/engagements", json=payload).json()["data"]["engagement_id"]

    from db.models import AssessmentRun, Finding
    from db.session import create_db_session

    with create_db_session() as session:
        run = AssessmentRun(engagement_id=eid, status="completed", step_budget=10)
        session.add(run)
        session.flush()
        finding = Finding(
            engagement_id=eid,
            run_id=run.id,
            category="api1_bola",
            owasp_api_ref="API1:2023 — Broken Object Level Authorization",
            title="BOLA on /orders/{id}",
            severity_label="high",
            location="GET /orders/{id}",
            description="Object accessible without ownership check.",
            evidence="200 returned for another user's order id.",
            confidence="confirmed",
            status="validated",
            remediation="Enforce per-object authorization.",
        )
        session.add(finding)

    rows = api_client.get(f"/engagements/{eid}/findings").json()["data"]
    assert len(rows) == 1
    assert rows[0]["owasp_api_ref"] == "API1:2023 — Broken Object Level Authorization"
    assert rows[0]["category"] == "api1_bola"
