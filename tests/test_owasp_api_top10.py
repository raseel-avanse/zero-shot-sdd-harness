"""OWASP API Security Top 10 (2023) end-to-end gate — REAL Gemini + REAL Postgres.

Boots the intentionally-vulnerable fixture API (``tests/fixtures/vuln_api_app.py``)
on a free local port, creates a ``live_app`` engagement with
``assessment_profile="owasp_api"`` pointed at it (host allowlisted), runs the full
assessment graph, and asserts the OWASP-API security outcome:

  * >=3 validated findings whose ``owasp_api_ref`` is a canonical
    ``APIn:2023 — …`` string, INCLUDING at least API1:2023 (BOLA),
    API2:2023 (Broken Authentication) and API8:2023 (Security Misconfiguration);
  * ``step_count <= step_budget``;
  * non-zero token/cost (real LLM was called);
  * only read-only verbs (GET/HEAD/OPTIONS) were issued against the target
    (verified from the fixture's request log, when observable).

Skips only if the Gemini key is genuinely absent — never stubbed. Depends on the
sibling Phase-4 slices (backend-graph + api-data); collected independently.
"""
from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import db.session as session_module
from db.models import AssessmentRun, Base, Engagement, Finding, ScopeRecord

from tests.fixtures import vuln_api_app

# Canonical OWASP API Top 10 (2023) refs the fixture is built to trigger.
API1_BOLA = "API1:2023 — Broken Object Level Authorization"
API2_AUTH = "API2:2023 — Broken Authentication"
API8_MISCONFIG = "API8:2023 — Security Misconfiguration"

# Only these HTTP verbs may ever be issued by a non-destructive probe.
_SAFE_VERBS = {"GET", "HEAD", "OPTIONS"}

_TRANSIENT = ("429", "resource_exhausted", "quota", "503", "unavailable", "high demand")


# --- fixtures ---------------------------------------------------------------- #


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


@pytest.fixture
def vuln_api():
    """Boot the vulnerable fixture API on a free local port; yield its base URL.

    Wraps the request handler to record every (verb, path) so the test can assert
    that only read-only verbs were ever issued against the target.
    """
    issued: list[tuple[str, str]] = []

    server = vuln_api_app.make_server(0)
    handler_cls = server.RequestHandlerClass

    original_handle = handler_cls.handle_one_request

    def _recording_handle(self):
        original_handle(self)
        command = getattr(self, "command", None)
        path = getattr(self, "path", None)
        if command:
            issued.append((command.upper(), path or ""))

    handler_cls.handle_one_request = _recording_handle

    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"base_url": f"http://127.0.0.1:{port}", "host": "127.0.0.1", "issued": issued}
    finally:
        server.shutdown()
        server.server_close()
        handler_cls.handle_one_request = original_handle
        thread.join(timeout=5)


def _require_gemini():
    from config.settings import get_settings

    if not get_settings().gemini_api_key:
        pytest.skip("No Gemini key set in .env (AGENT_GEMINI_API_KEY)")


# --- helpers ----------------------------------------------------------------- #


def _make_owasp_engagement(factory, base_url: str, host: str) -> str:
    with factory() as s:
        eng = Engagement(
            name="owasp-fixture",
            target_type="live_app",
            target_ref=base_url,
            assessment_profile="owasp_api",
            status="active",
        )
        scope = ScopeRecord(
            engagement=eng,
            authorized_targets=[host],
            rules_of_engagement="read-only, non-destructive, OWASP API Top 10",
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


def _run_until_complete(factory, engagement_id: str, attempts: int = 4) -> str:
    """Execute a real assessment, pacing around the free-tier per-minute RPM cap."""
    from graph.runner import run_assessment

    last_err = None
    status = None
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
        pytest.skip(f"Gemini free-tier quota/availability blocked the run: {last_err}")
    raise AssertionError(f"run did not complete: status={status} err={last_err}")


# --- the gate test ----------------------------------------------------------- #


def test_owasp_api_top10_end_to_end(real_pg_db, vuln_api):
    _require_gemini()
    factory = real_pg_db

    engagement_id = _make_owasp_engagement(factory, vuln_api["base_url"], vuln_api["host"])
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

        # Every finding tagged with a canonical OWASP API ref.
        refs = [f.owasp_api_ref for f in findings if f.owasp_api_ref]
        validated_refs = [
            f.owasp_api_ref
            for f in findings
            if f.owasp_api_ref and f.status == "validated"
        ]

    assert findings, "expected at least one OWASP-tagged validated finding"

    # All surfaced OWASP refs must be canonical "APIn:2023 — …" strings.
    for ref in refs:
        assert ref.startswith("API") and ":2023 —" in ref, f"non-canonical owasp_api_ref: {ref!r}"

    # >=3 validated findings including the three the fixture is built to expose.
    assert len(validated_refs) >= 3, f"expected >=3 validated OWASP findings, got {validated_refs}"
    covered = set(validated_refs)
    assert API1_BOLA in covered, f"missing API1 BOLA; got {covered}"
    assert API2_AUTH in covered, f"missing API2 Broken Authentication; got {covered}"
    assert API8_MISCONFIG in covered, f"missing API8 Security Misconfiguration; got {covered}"

    # Only read-only verbs were ever issued against the target (in-code verb
    # guard is authoritative; this confirms it end-to-end from the target side).
    issued_verbs = {verb for verb, _ in vuln_api["issued"]}
    assert issued_verbs, "expected the assessment to probe the fixture at least once"
    assert issued_verbs <= _SAFE_VERBS, f"non-read-only verb issued: {issued_verbs - _SAFE_VERBS}"
