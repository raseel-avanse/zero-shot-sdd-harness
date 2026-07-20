"""End-to-end assessment gate — REAL Gemini + REAL Postgres.

Creates an engagement scoped to the vulnerable fixture repo, runs the full
assessment graph synchronously, and asserts the security outcome: findings
across multiple categories, bounded step budget, non-zero token/cost, bounded
evidence (never a whole source file), and in-code scope refusal.

Skips only if the Gemini key is genuinely absent — never stubbed.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import db.session as session_module
from db.models import AssessmentRun, Base, Engagement, Finding, ScopeRecord

FIXTURE_REPO = str((Path(__file__).parent.parent / "fixtures" / "vulnerable_repo").resolve())


@pytest.fixture
def real_pg_db(_isolated_db, monkeypatch):
    """Re-point db.session at the real Postgres, overriding the SQLite autouse.

    Depends on `_isolated_db` so this runs AFTER it and its patch wins.
    Skips if the production Postgres URL is not configured.
    """
    from config.settings import get_settings

    url = get_settings().database_url
    if not url.startswith("postgresql"):
        pytest.skip(f"real Postgres not configured (database_url={url!r})")

    engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    yield factory
    engine.dispose()


def _require_gemini():
    from config.settings import get_settings

    if not get_settings().gemini_api_key:
        pytest.skip("No Gemini key set in .env (AGENT_GEMINI_API_KEY)")


def _make_engagement(factory, target: str, allowlist: list[str]) -> str:
    with factory() as s:
        eng = Engagement(name="fixture", target_type="repo", target_ref=target, status="active")
        scope = ScopeRecord(
            engagement=eng,
            authorized_targets=list(allowlist),
            rules_of_engagement="read-only, non-destructive",
            authorized_by="pytest",
            non_destructive_only=True,
        )
        s.add(eng)
        s.add(scope)
        s.commit()
        return eng.id


def _make_run(factory, engagement_id: str, budget: int = 40) -> str:
    with factory() as s:
        run = AssessmentRun(engagement_id=engagement_id, status="pending", step_budget=budget)
        s.add(run)
        s.commit()
        return run.id


_TRANSIENT = ("429", "resource_exhausted", "quota", "503", "unavailable", "high demand")


def _run_until_complete(factory, engagement_id: str, attempts: int = 4):
    """Execute a real assessment, pacing around the free-tier per-minute RPM cap.

    The free-tier Gemini key allows ~15 requests/minute; a full run bursts more
    than that, so on a transient rate-limit/availability failure we cool down and
    retry the whole run with a fresh run row (real calls throughout — never
    stubbed). Skips only if every attempt is blocked by provider quota.
    """
    from graph.runner import run_assessment

    last_err = None
    for i in range(attempts):
        run_id = _make_run(factory, engagement_id, budget=40)
        run_assessment(run_id)
        with factory() as s:
            run = s.get(AssessmentRun, run_id)
            status = run.status
            last_err = run.error_message
        if status == "completed":
            return run_id
        if status == "failed" and last_err and any(t in last_err.lower() for t in _TRANSIENT):
            if i < attempts - 1:
                time.sleep(65)  # let the per-minute quota window reset
                continue
        break
    if last_err and any(t in last_err.lower() for t in _TRANSIENT):
        import pytest as _pytest

        _pytest.skip(f"Gemini free-tier quota/availability blocked the run: {last_err}")
    raise AssertionError(f"run did not complete: status={status} err={last_err}")


def test_assessment_end_to_end(real_pg_db):
    _require_gemini()
    factory = real_pg_db

    engagement_id = _make_engagement(factory, FIXTURE_REPO, [FIXTURE_REPO])
    run_id = _run_until_complete(factory, engagement_id)

    with factory() as s:
        run = s.get(AssessmentRun, run_id)
        assert run is not None
        assert run.status == "completed", f"run status={run.status} err={run.error_message}"
        # Bounded budget honoured.
        assert run.step_count <= run.step_budget
        # Non-zero token accounting + cost (real LLM was called).
        assert run.total_tokens > 0
        assert float(run.estimated_cost_usd) > 0

        findings = s.execute(
            select(Finding).where(Finding.run_id == run_id)
        ).scalars().all()

    assert findings, "expected at least one validated finding"
    categories = {f.category for f in findings}
    assert len(categories) >= 3, f"expected >=3 categories, got {categories}"

    # Evidence must be a bounded excerpt, never a whole persisted source file.
    fixture_files = list(Path(FIXTURE_REPO).rglob("*"))
    full_contents = {
        p.read_text(encoding="utf-8", errors="ignore")
        for p in fixture_files
        if p.is_file()
    }
    for f in findings:
        assert f.evidence, "finding evidence must be present"
        assert len(f.evidence) <= 5000, "evidence excerpt must be bounded"
        assert f.evidence not in full_contents, "must not persist a whole source file as evidence"


def test_run_outside_scope_is_refused(real_pg_db):
    """A run whose target is OUTSIDE the allowlist must be refused (no findings)."""
    _require_gemini()
    factory = real_pg_db

    outside = os.path.dirname(FIXTURE_REPO)  # parent dir, not the fixture itself
    engagement_id = _make_engagement(factory, outside, [FIXTURE_REPO])
    run_id = _make_run(factory, engagement_id, budget=40)

    from graph.runner import run_assessment

    run_assessment(run_id)

    with factory() as s:
        run = s.get(AssessmentRun, run_id)
        assert run.status == "failed"
        assert "scope" in (run.error_message or "").lower()
        findings = s.execute(
            select(Finding).where(Finding.run_id == run_id)
        ).scalars().all()
    assert not findings, "a scope-refused run must persist no findings"
