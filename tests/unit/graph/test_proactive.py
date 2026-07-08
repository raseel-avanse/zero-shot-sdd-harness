"""Phase-3 report-node tests: proactive next-probe suggestions (real Gemini) +
deterministic same-pattern-elsewhere flagging.

The suggestion test makes ONE real fast-tier LLM call (skipped without a key,
free-tier friendly). The grouping + error-path tests are pure/no-LLM. The DB is
the autouse isolated fixture from tests/conftest.py using the production models.
"""
from __future__ import annotations

from sqlalchemy import select

import graph.nodes as nodes
from graph.nodes import _assign_pattern_refs, report


def _seed_run_with_finding(**finding_kwargs) -> tuple[str, str]:
    """Persist an engagement + running run + one validated finding; return ids."""
    from db.models import AssessmentRun, Engagement, Finding, ScopeRecord
    from db.session import create_db_session

    with create_db_session() as session:
        eng = Engagement(
            name="proactive-test", target_type="repo", target_ref="/repo", status="active"
        )
        session.add(eng)
        session.flush()
        session.add(
            ScopeRecord(
                engagement_id=eng.id,
                authorized_targets=["/repo"],
                rules_of_engagement="read-only",
                authorized_by="tester",
                non_destructive_only=True,
            )
        )
        run = AssessmentRun(engagement_id=eng.id, status="running", step_budget=40)
        session.add(run)
        session.flush()
        defaults = dict(
            engagement_id=eng.id,
            run_id=run.id,
            category="injection",
            title="SQL injection in login handler",
            severity_label="high",
            cvss_score=8.1,
            location="app/db.py:12",
            description="User input is interpolated into a SQL query.",
            evidence="cur.execute(f'SELECT * FROM users WHERE name={name}')",
            confidence="confirmed",
            status="validated",
            remediation="Use parameterized queries.",
        )
        defaults.update(finding_kwargs)
        session.add(Finding(**defaults))
        session.flush()
        return run.id, eng.id


# --------------------------------------------------------------------------- #
# Happy path — real Gemini: >=2 concrete next-probe suggestions, persisted.
# --------------------------------------------------------------------------- #


def test_report_produces_and_persists_next_probe_suggestions(_require_llm_key):
    from db.models import AssessmentRun, Finding
    from db.session import create_db_session

    run_id, eng_id = _seed_run_with_finding()
    state = {
        "run_id": run_id,
        "engagement_id": eng_id,
        "findings": [
            {
                "category": "injection",
                "title": "SQL injection in login handler",
                "severity_label": "high",
                "location": "app/db.py:12",
                "confidence": "confirmed",
            }
        ],
        "recon": {"summary": "Small Flask app with a SQLite data layer."},
    }

    out = report(state)

    assert out["status"] == "completed"
    assert out["current_phase"] == "report"
    suggestions = out["suggestions"]
    assert isinstance(suggestions, list)
    non_empty = [s for s in suggestions if isinstance(s, str) and s.strip()]
    assert len(non_empty) >= 2, f"expected >=2 suggestions, got {suggestions!r}"

    # Persisted on the run so a later GET can surface them.
    with create_db_session() as session:
        run = session.get(AssessmentRun, run_id)
        assert isinstance(run.suggestions, list)
        assert len([s for s in run.suggestions if s and s.strip()]) >= 2
        assert run.status == "completed"
        assert run.completed_at is not None
        # And the finding row was linked with a pattern_ref.
        rows = session.execute(
            select(Finding).where(Finding.run_id == run_id)
        ).scalars().all()
        assert all(r.pattern_ref for r in rows)


# --------------------------------------------------------------------------- #
# Same-pattern-elsewhere flagging — pure/deterministic, no LLM.
# --------------------------------------------------------------------------- #


def test_same_pattern_findings_share_ref_unrelated_ones_differ():
    a = {"category": "injection", "title": "SQL injection in the login handler"}
    b = {"category": "injection", "title": "SQL injection in login handler"}
    c = {"category": "broken_auth", "title": "Missing authorization check on admin route"}

    _assign_pattern_refs([a, b, c])

    assert a["pattern_ref"]  # non-empty
    # Same category + equivalent normalized signature -> linked.
    assert a["pattern_ref"] == b["pattern_ref"]
    # Unrelated category/pattern -> distinct ref.
    assert a["pattern_ref"] != c["pattern_ref"]
    assert c["pattern_ref"]


def test_pattern_refs_persisted_group_shared_across_findings():
    """Two same-pattern findings on one run get the SAME persisted pattern_ref."""
    from db.models import Finding
    from db.session import create_db_session

    run_id, eng_id = _seed_run_with_finding()
    # Add a second, same-pattern finding at a different location.
    with create_db_session() as session:
        session.add(
            Finding(
                engagement_id=eng_id,
                run_id=run_id,
                category="injection",
                title="SQL Injection in login handler",  # same signature
                severity_label="high",
                location="app/api.py:40",
                description="Same injection pattern in a second location.",
                evidence="query = 'SELECT ... ' + user",
                confidence="tentative",
                status="validated",
                remediation="Parameterize.",
            )
        )

    nodes._persist_pattern_refs({"run_id": run_id})

    with create_db_session() as session:
        rows = session.execute(
            select(Finding).where(Finding.run_id == run_id)
        ).scalars().all()
        refs = {r.pattern_ref for r in rows}
        assert len(rows) == 2
        assert len(refs) == 1  # both linked to one shared pattern
        assert all(r.pattern_ref for r in rows)


# --------------------------------------------------------------------------- #
# Error path — LLM failure degrades gracefully; run still completes, no crash.
# --------------------------------------------------------------------------- #


def test_report_completes_when_suggestion_llm_fails(monkeypatch):
    from db.models import AssessmentRun
    from db.session import create_db_session

    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("simulated LLM outage")

    monkeypatch.setattr(nodes, "LLMClient", _Boom)

    run_id, eng_id = _seed_run_with_finding()
    state = {
        "run_id": run_id,
        "engagement_id": eng_id,
        "findings": [{"category": "injection", "title": "SQL injection in login handler"}],
        "recon": {},
    }

    out = report(state)

    assert out["status"] == "completed"
    assert out["suggestions"] == []
    with create_db_session() as session:
        run = session.get(AssessmentRun, run_id)
        assert run.status == "completed"
        assert run.suggestions == []
