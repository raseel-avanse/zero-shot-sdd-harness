"""Real-Gemini re-test integration test (retest-backend slice).

Seeds a confirmed injection finding, points the engagement at a PATCHED
(parameterized) copy of the source, and asserts a real re-validation flips the
finding to `remediated`. Skipped when no LLM key is present; kept to a single
finding to respect free-tier limits.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_PATCHED_DB = '''\
"""Data-access layer. PATCHED copy — injection remediated."""
import sqlite3


def get_user(username):
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    # FIXED: parameterized query, no string interpolation.
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cur.fetchone()
'''


@pytest.fixture
def patched_repo(tmp_path) -> str:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "db.py").write_text(_PATCHED_DB, encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask==2.0.0\n", encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def findings_client(_isolated_db):
    import api.findings as findings_mod

    app = FastAPI()
    app.include_router(findings_mod.router)
    with TestClient(app) as client:
        yield client


def _seed(target: str) -> str:
    from db.models import AssessmentRun, Engagement, Finding, ScopeRecord
    from db.session import create_db_session

    with create_db_session() as session:
        eng = Engagement(name="retest", target_type="repo", target_ref=target, status="active")
        scope = ScopeRecord(
            engagement=eng,
            authorized_targets=[target],
            rules_of_engagement="read-only",
            authorized_by="tester",
            non_destructive_only=True,
        )
        run = AssessmentRun(engagement=eng, status="completed", step_budget=40)
        finding = Finding(
            engagement=eng,
            run=run,
            category="injection",
            title="SQL injection in get_user",
            severity_label="high",
            location="app/db.py:11",
            description="Untrusted username interpolated into a raw SQL string.",
            evidence="query = \"SELECT * FROM users WHERE username = '%s'\" % username",
            confidence="confirmed",
            status="validated",
            remediation="Use parameterized queries.",
        )
        session.add_all([eng, scope, run, finding])
        session.flush()
        return finding.id


def test_retest_patched_finding_flips_to_remediated(
    findings_client, patched_repo, _require_llm_key
):
    fid = _seed(patched_repo)

    r = findings_client.post(f"/findings/{fid}/retest")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["finding_id"] == fid
    # Against the patched source the issue no longer reproduces.
    assert data["status"] == "remediated"
    assert data["confidence"] == "unconfirmed"
