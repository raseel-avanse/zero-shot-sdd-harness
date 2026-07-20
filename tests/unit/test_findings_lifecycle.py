"""Phase 3 — finding status lifecycle via PATCH /findings/{finding_id}.

No LLM key required: PATCH is a pure status mutation, the graph is never invoked.
Uses the shared `api_client` fixture (isolated DB from tests/conftest.py) and
seeds an engagement + run + finding through the SAME session factory the app uses.
"""
from __future__ import annotations

import pytest


def _seed_finding(status: str = "new") -> tuple[str, str]:
    """Insert an engagement + run + finding; return (engagement_id, finding_id)."""
    from db.models import AssessmentRun, Engagement, Finding
    from db.session import create_db_session

    with create_db_session() as s:
        eng = Engagement(
            name="Lifecycle test",
            target_type="repo",
            target_ref="/tmp/repo",
            status="active",
        )
        s.add(eng)
        s.flush()
        run = AssessmentRun(engagement_id=eng.id, status="completed")
        s.add(run)
        s.flush()
        finding = Finding(
            engagement_id=eng.id,
            run_id=run.id,
            category="injection",
            title="SQL injection in login",
            severity_label="high",
            cvss_score=8.1,
            location="app/auth.py:42",
            description="User input concatenated into SQL.",
            evidence="query = 'SELECT * FROM users WHERE name=' + name",
            confidence="confirmed",
            status=status,
            remediation="Use parameterised queries.",
        )
        s.add(finding)
        s.flush()
        return eng.id, finding.id


def _status_via_list(api_client, engagement_id: str, finding_id: str) -> str:
    """Re-fetch the finding through the list endpoint to prove persistence."""
    r = api_client.get(f"/engagements/{engagement_id}/findings")
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    match = next(i for i in items if i["id"] == finding_id)
    return match["status"]


def test_patch_new_to_validated(api_client):
    eid, fid = _seed_finding(status="new")

    r = api_client.patch(f"/findings/{fid}", json={"status": "validated"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "validated"
    assert r.json()["error"] is None
    # Persisted (re-fetch via the list endpoint).
    assert _status_via_list(api_client, eid, fid) == "validated"


def test_patch_full_lifecycle_new_validated_remediated(api_client):
    eid, fid = _seed_finding(status="new")

    for target in ("validated", "remediated"):
        r = api_client.patch(f"/findings/{fid}", json={"status": target})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == target
        assert _status_via_list(api_client, eid, fid) == target


def test_patch_mark_false_positive(api_client):
    eid, fid = _seed_finding(status="validated")

    r = api_client.patch(f"/findings/{fid}", json={"status": "false_positive"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "false_positive"
    assert _status_via_list(api_client, eid, fid) == "false_positive"


@pytest.mark.parametrize("bad", ["closed", "", "NEW", "resolved"])
def test_patch_invalid_status_400(api_client, bad):
    eid, fid = _seed_finding(status="new")

    r = api_client.patch(f"/findings/{fid}", json={"status": bad})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "INVALID_STATUS"
    # Unchanged on rejection.
    assert _status_via_list(api_client, eid, fid) == "new"


def test_patch_unknown_finding_404(api_client):
    r = api_client.patch("/findings/does-not-exist", json={"status": "validated"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"
