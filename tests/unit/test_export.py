"""Export surface tests (Phase 3) — no LLM required.

Seeds an engagement + scope record + assessment run + findings directly via the
DB session (the same isolated engine the api_client is bound to), then asserts
the MD / JSON / PDF dossier downloads contain the right content and attachment
headers.
"""
from __future__ import annotations

import json


def _seed_engagement(session, *, with_finding=True):
    from db.models import AssessmentRun, Engagement, Finding, ScopeRecord

    engagement = Engagement(
        name="Acme API Audit",
        target_type="repo",
        target_ref="/srv/acme-repo",
        status="active",
    )
    scope = ScopeRecord(
        engagement=engagement,
        authorized_targets=["/srv/acme-repo"],
        rules_of_engagement="Read-only, non-destructive review of /srv/acme-repo.",
        authorized_by="Jane Auditor",
        non_destructive_only=True,
    )
    run = AssessmentRun(
        engagement=engagement,
        status="completed",
        prompt_tokens=1200,
        completion_tokens=800,
        total_tokens=2000,
        estimated_cost_usd=0.0345,
    )
    session.add_all([engagement, scope, run])
    session.flush()

    if with_finding:
        finding = Finding(
            engagement_id=engagement.id,
            run_id=run.id,
            category="injection",
            title="SQL Injection in login handler",
            severity_label="critical",
            cvss_score=9.8,
            location="src/auth/login.py:42",
            description="User input concatenated directly into a SQL query.",
            evidence='query = "SELECT * FROM users WHERE name=" + name',
            confidence="confirmed",
            status="validated",
            remediation="Use parameterized queries / an ORM.",
            suggested_patch="cur.execute('SELECT * FROM users WHERE name=%s', (name,))",
        )
        session.add(finding)
        session.flush()

    return engagement.id


def _seed_via_app(session_module):
    with session_module.create_db_session() as session:
        return _seed_engagement(session)


def test_export_json_contains_finding_scope_and_cost(api_client):
    import db.session as session_module

    eid = _seed_via_app(session_module)

    r = api_client.get(f"/engagements/{eid}/export?format=json")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers["content-disposition"]
    assert ".json" in r.headers["content-disposition"]

    doc = json.loads(r.content)
    assert doc["engagement"]["id"] == eid
    assert doc["engagement"]["name"] == "Acme API Audit"

    # Scope / authorization record.
    assert doc["scope"]["authorized_by"] == "Jane Auditor"
    assert doc["scope"]["authorized_targets"] == ["/srv/acme-repo"]

    # Finding fields.
    assert len(doc["findings"]) == 1
    f = doc["findings"][0]
    assert f["title"] == "SQL Injection in login handler"
    assert f["severity_label"] == "critical"
    assert f["cvss_score"] == 9.8
    assert f["confidence"] == "confirmed"
    assert f["category"] == "injection"
    assert f["remediation"].startswith("Use parameterized")
    assert "SELECT" in f["evidence"]

    # Per-run cost totals.
    assert doc["cost_totals"]["total_tokens"] == 2000
    assert doc["cost_totals"]["prompt_tokens"] == 1200
    assert abs(doc["cost_totals"]["estimated_cost_usd"] - 0.0345) < 1e-9


def test_export_markdown_contains_title_and_severity(api_client):
    import db.session as session_module

    eid = _seed_via_app(session_module)

    r = api_client.get(f"/engagements/{eid}/export?format=md")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/markdown")
    assert "attachment" in r.headers["content-disposition"]

    text = r.content.decode("utf-8")
    assert len(text) > 100
    assert "Acme API Audit" in text
    assert "SQL Injection in login handler" in text
    assert "critical" in text
    assert "Jane Auditor" in text
    assert "2000" in text  # token total


def test_export_default_format_is_markdown(api_client):
    import db.session as session_module

    eid = _seed_via_app(session_module)

    r = api_client.get(f"/engagements/{eid}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")


def test_export_pdf_is_valid_and_nontrivial(api_client):
    import db.session as session_module

    eid = _seed_via_app(session_module)

    r = api_client.get(f"/engagements/{eid}/export?format=pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert "attachment" in r.headers["content-disposition"]
    assert ".pdf" in r.headers["content-disposition"]

    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 1000


def test_export_empty_engagement_no_findings(api_client):
    """Edge case: engagement with no findings still exports cleanly."""
    import db.session as session_module

    with session_module.create_db_session() as session:
        eid = _seed_engagement(session, with_finding=False)

    r = api_client.get(f"/engagements/{eid}/export?format=json")
    assert r.status_code == 200
    doc = json.loads(r.content)
    assert doc["findings"] == []
    assert doc["summary"]["finding_count"] == 0

    # MD + PDF must also render with zero findings.
    md = api_client.get(f"/engagements/{eid}/export?format=md")
    assert md.status_code == 200
    assert "No findings recorded" in md.content.decode("utf-8")

    pdf = api_client.get(f"/engagements/{eid}/export?format=pdf")
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_export_unknown_engagement_404(api_client):
    r = api_client.get("/engagements/does-not-exist/export?format=json")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_export_invalid_format_400(api_client):
    import db.session as session_module

    eid = _seed_via_app(session_module)

    r = api_client.get(f"/engagements/{eid}/export?format=csv")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_FORMAT"
