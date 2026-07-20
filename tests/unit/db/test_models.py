"""Unit tests for the Phase 1 Sentinel DB schema.

Runs against the SQLite fixture (portable types) from conftest; the GATE
re-runs the same assertions against real Postgres via alembic.
"""
from datetime import datetime

import pytest

from db.models import (
    AssessmentRun,
    Base,
    Engagement,
    Finding,
    ScopeRecord,
)


def test_no_boilerplate_runrow_remains():
    # RunRow slot must be replaced by the Sentinel schema.
    assert not hasattr(
        __import__("db.models", fromlist=["x"]), "RunRow"
    ), "boilerplate RunRow must be removed"


def test_expected_tables_registered():
    tables = set(Base.metadata.tables)
    assert {
        "engagements",
        "scope_records",
        "assessment_runs",
        "findings",
    } <= tables
    # Phase 1 must not persist raw source; no such column anywhere.
    for table in Base.metadata.tables.values():
        for col in table.columns:
            assert col.name not in {"source", "raw_source", "source_code", "input_text"}


def test_engagement_defaults(_isolated_db):
    from sqlalchemy.orm import Session

    with Session(_isolated_db) as s:
        eng = Engagement(name="test", target_type="repo", target_ref="/tmp/repo")
        s.add(eng)
        s.commit()
        s.refresh(eng)
        assert eng.id
        assert eng.status == "draft"
        assert isinstance(eng.created_at, datetime)
        assert isinstance(eng.updated_at, datetime)


def test_scope_record_relationship_and_allowlist(_isolated_db):
    from sqlalchemy.orm import Session

    with Session(_isolated_db) as s:
        eng = Engagement(name="e", target_type="repo", target_ref="/tmp/repo")
        scope = ScopeRecord(
            engagement=eng,
            authorized_targets=["/tmp/repo", "/srv/app"],
            rules_of_engagement="read-only",
            authorized_by="alice",
        )
        s.add(scope)
        s.commit()
        s.refresh(scope)
        assert scope.non_destructive_only is True
        assert scope.authorized_targets == ["/tmp/repo", "/srv/app"]
        assert eng.scope_record is scope


def test_assessment_run_counters_default_zero(_isolated_db):
    from sqlalchemy.orm import Session

    with Session(_isolated_db) as s:
        eng = Engagement(name="e", target_type="repo", target_ref="/tmp/repo")
        run = AssessmentRun(engagement=eng, step_budget=50)
        s.add(run)
        s.commit()
        s.refresh(run)
        assert run.status == "pending"
        assert run.step_count == 0
        assert run.prompt_tokens == 0
        assert run.completion_tokens == 0
        assert run.total_tokens == 0
        assert float(run.estimated_cost_usd) == 0.0
        assert run.step_budget == 50


def test_finding_defaults_and_relationships(_isolated_db):
    from sqlalchemy.orm import Session

    with Session(_isolated_db) as s:
        eng = Engagement(name="e", target_type="repo", target_ref="/tmp/repo")
        run = AssessmentRun(engagement=eng, step_budget=10)
        finding = Finding(
            engagement=eng,
            run=run,
            category="injection",
            title="SQLi in login",
            severity_label="high",
            cvss_score=8.1,
            location="app/db.py:42",
            description="user input concatenated into SQL",
            evidence="query = 'SELECT ... ' + user_input",
            confidence="confirmed",
            remediation="use parameterized queries",
            suggested_patch="--- a\n+++ b\n",
        )
        s.add(finding)
        s.commit()
        s.refresh(finding)
        assert finding.status == "new"
        assert finding.engagement is eng
        assert finding.run is run
        assert finding.pattern_ref is None
        assert float(finding.cvss_score) == 8.1
