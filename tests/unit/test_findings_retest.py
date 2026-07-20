"""Unit tests for POST /findings/{id}/retest (retest-backend slice).

The LLM/validation is mocked here (no key required); a real-Gemini retest lives
in tests/integration/test_retest_real.py. Uses the isolated SQLite DB + settings
reset from tests/conftest.py, and mounts the findings router on a standalone app
so it does not depend on agent-builder wiring the router into api.app yet.
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeLLM:
    """Stand-in LLMClient whose .complete returns canned validate-style JSON."""

    payload: dict = {}

    def __init__(self) -> None:  # noqa: D401 — mirrors real signature
        pass

    def complete(self, prompt: str, *, system: str | None = None, tier: str = "fast") -> dict:
        return {
            "text": json.dumps(_FakeLLM.payload),
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "model": "gemini-3.1-pro",
        }


@pytest.fixture
def findings_client(_isolated_db, monkeypatch):
    import api.findings as findings_mod

    monkeypatch.setattr(findings_mod, "LLMClient", _FakeLLM)
    app = FastAPI()
    app.include_router(findings_mod.router)
    with TestClient(app) as client:
        yield client


def _seed_finding(target: str, *, allow: list[str] | None = None, status: str = "validated") -> str:
    """Insert an engagement + scope + run + one finding; return the finding id."""
    from db.models import AssessmentRun, Engagement, Finding, ScopeRecord
    from db.session import create_db_session

    allow = allow if allow is not None else [target]
    with create_db_session() as session:
        eng = Engagement(name="e", target_type="repo", target_ref=target, status="active")
        scope = ScopeRecord(
            engagement=eng,
            authorized_targets=list(allow),
            rules_of_engagement="read-only",
            authorized_by="tester",
            non_destructive_only=True,
        )
        run = AssessmentRun(engagement=eng, status="completed", step_budget=40)
        finding = Finding(
            engagement=eng,
            run=run,
            category="injection",
            title="SQL injection",
            severity_label="high",
            location="app.py:10",
            description="Unsanitized query",
            evidence="cursor.execute(f'... {user}')",
            confidence="confirmed",
            status=status,
            remediation="Use parameterized queries",
        )
        session.add_all([eng, scope, run, finding])
        session.flush()
        return finding.id


def test_retest_finding_not_found_404(findings_client):
    r = findings_client.post("/findings/does-not-exist/retest")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_retest_fixed_finding_transitions_to_remediated(findings_client, tmp_path):
    # Fix confirmed: the LLM can no longer substantiate the issue -> unconfirmed.
    _FakeLLM.payload = {
        "confidence": "unconfirmed",
        "evidence": "The vulnerable call is now parameterized; no reproduction.",
        "poc": "",
    }
    fid = _seed_finding(str(tmp_path))

    r = findings_client.post(f"/findings/{fid}/retest")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["finding_id"] == fid
    assert data["status"] == "remediated"
    assert data["confidence"] == "unconfirmed"
    assert data["finding"]["status"] == "remediated"

    # Persisted transition.
    from db.models import Finding
    from db.session import create_db_session

    with create_db_session() as session:
        f = session.get(Finding, fid)
        assert f.status == "remediated"
        assert f.confidence == "unconfirmed"


def test_retest_unfixed_finding_stays_validated(findings_client, tmp_path):
    # Still reproduces: keep it validated with fresh evidence.
    _FakeLLM.payload = {
        "confidence": "confirmed",
        "evidence": "Still exploitable: user input flows into the raw query.",
        "poc": "",
    }
    fid = _seed_finding(str(tmp_path))

    r = findings_client.post(f"/findings/{fid}/retest")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "validated"
    assert data["confidence"] == "confirmed"
    assert "Still exploitable" in data["evidence"]


def test_retest_out_of_scope_target_refused_422(findings_client, tmp_path):
    # Recorded scope does NOT contain the target -> refuse before any re-probe.
    target = str(tmp_path / "repo")
    fid = _seed_finding(target, allow=[str(tmp_path / "other")])

    r = findings_client.post(f"/findings/{fid}/retest")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "SCOPE_VIOLATION"


def test_retest_cost_attributed_to_run(findings_client, tmp_path):
    _FakeLLM.payload = {"confidence": "unconfirmed", "evidence": "fixed", "poc": ""}
    fid = _seed_finding(str(tmp_path))

    r = findings_client.post(f"/findings/{fid}/retest")
    assert r.status_code == 200

    from db.models import Finding
    from db.session import create_db_session

    with create_db_session() as session:
        f = session.get(Finding, fid)
        run = f.run
        assert run.prompt_tokens == 11
        assert run.completion_tokens == 7
        assert run.total_tokens == 18
        assert float(run.estimated_cost_usd) > 0.0
