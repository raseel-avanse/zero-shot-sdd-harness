"""Findings surface: re-test-after-remediation (spec/api.md [P2]).

`POST /findings/{id}/retest` re-runs Sentinel's validation stage for ONE
existing finding against the CURRENT state of its target, then transitions the
finding's status based on whether the issue still reproduces:

  * issue no longer present/confirmed  -> `remediated` (with a fresh timestamp)
  * issue still present                -> kept `validated` (fresh evidence returned)

Re-validation reuses the SAME approach as the graph's `validate` node WITHOUT
editing `src/graph/nodes.py` (owned by another slice this phase): it reuses the
`src/prompts/validate.md` system prompt, the shared `LLMClient` (smart tier),
`tools.read_excerpt` for a bounded fresh code excerpt at the finding's location,
and the bounded `tools.sandbox` PoC check. The recorded engagement scope is
respected in code — a target outside the allowlist is refused before any read.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import api_error, ok
from db.models import AssessmentRun, Engagement, Finding
from db.session import get_session
from domain.findings import FindingOut, RetestResponse
from llm import cost as cost_mod
from llm.client import LLMClient
from tools import scope_guard
from tools.read_excerpt import read_excerpt
from tools.sandbox import sandbox_run

log = logging.getLogger("sentinel.findings")

router = APIRouter()

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
# Confidence values that mean the vulnerability still reproduces.
_STILL_PRESENT = {"confirmed", "tentative"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_validate_prompt() -> str:
    return (_PROMPT_DIR / "validate.md").read_text(encoding="utf-8").strip()


def _parse_json(text: str) -> dict:
    """Defensively parse model JSON output, tolerating code fences/prose."""
    if not text:
        return {}
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("```", 2)
        t = parts[1] if len(parts) > 1 else text
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
        t = t.strip().rstrip("`").strip()
    try:
        parsed = json.loads(t)
    except (json.JSONDecodeError, ValueError):
        start = t.find("{")
        end = t.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(t[start : end + 1])
            except (json.JSONDecodeError, ValueError):
                return {}
        else:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _fresh_excerpt(target: str, location: str) -> str:
    """Bounded read of the CURRENT source at the finding's `file:line` location.

    Best-effort: if the file no longer exists / cannot be read (a strong signal
    the code was changed), fall back to an empty excerpt.
    """
    if not target or not location:
        return ""
    rel = location
    start = 1
    if ":" in location:
        rel, _, line_part = location.rpartition(":")
        try:
            line = int(line_part.strip())
            start = max(1, line - 20)
        except ValueError:
            rel = location
            start = 1
    try:
        return read_excerpt(target, rel, start=start, end=start + 60)
    except OSError:
        return ""


def _finding_out(f: Finding) -> FindingOut:
    return FindingOut(
        id=f.id,
        engagement_id=f.engagement_id,
        run_id=f.run_id,
        category=f.category,
        title=f.title,
        severity_label=f.severity_label,
        cvss_score=float(f.cvss_score) if f.cvss_score is not None else None,
        location=f.location,
        description=f.description,
        evidence=f.evidence,
        confidence=f.confidence,
        status=f.status,
        remediation=f.remediation,
        suggested_patch=f.suggested_patch,
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


@router.post("/findings/{finding_id}/retest")
def retest_finding(
    finding_id: str, session: Session = Depends(get_session)
) -> dict:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise api_error("NOT_FOUND", f"finding {finding_id} not found", 404)

    engagement = session.get(Engagement, finding.engagement_id)
    if engagement is None:
        raise api_error(
            "NOT_FOUND", f"engagement {finding.engagement_id} not found", 404
        )

    target = engagement.target_ref or ""
    allowlist = (
        list(engagement.scope_record.authorized_targets or [])
        if engagement.scope_record is not None
        else []
    )

    # SAFETY-CRITICAL: respect the recorded scope. Never re-probe out of scope.
    if not scope_guard.check(target, allowlist):
        log.warning(
            "retest refused: target out of recorded scope",
            extra={"finding_id": finding_id, "target": target},
        )
        raise api_error(
            "SCOPE_VIOLATION",
            f"target not in recorded engagement scope: {target}",
            422,
        )

    # Rebuild the candidate from the stored finding + a FRESH excerpt of the
    # current source at its location, then re-run the SAME validation prompt.
    fresh = _fresh_excerpt(target, finding.location)
    candidate = {
        "category": finding.category,
        "title": finding.title,
        "severity_label": finding.severity_label,
        "cvss_score": float(finding.cvss_score)
        if finding.cvss_score is not None
        else None,
        "location": finding.location,
        "description": finding.description,
        "evidence": fresh or finding.evidence,
        "current_excerpt": fresh,
    }

    try:
        usage = LLMClient().complete(
            "RE-TEST MODE. This finding was reported earlier; the code may since "
            "have been fixed. Judge ONLY the CURRENT source below (the historical "
            "title/description may be stale). Decide whether the SAME vulnerability "
            "STILL exists in the current code.\n\n"
            "In addition to the normal JSON keys, you MUST include a boolean field "
            '`"reproduces"`: true if the vulnerability STILL EXISTS in the current '
            "source, false if it has been fixed/remediated. When it has been fixed, "
            'set `"reproduces": false` and `"confidence": "unconfirmed"`.\n\n'
            "Existing finding + current source (JSON):\n"
            + json.dumps(candidate)[:12000],
            system=_load_validate_prompt(),
            tier="smart",
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("retest LLM call failed", extra={"finding_id": finding_id})
        raise api_error("RETEST_FAILED", f"re-validation failed: {exc}", 502)

    parsed = _parse_json(usage.get("text", ""))
    confidence = parsed.get("confidence", "unconfirmed")
    if confidence not in {"confirmed", "tentative", "unconfirmed"}:
        confidence = "unconfirmed"
    evidence = parsed.get("evidence") or fresh or "Re-test found no reproducing evidence."

    # Prefer the explicit re-test signal when present: the validate prompt's
    # `confidence` reflects confidence in the ANALYSIS, not whether the vuln is
    # still present, so a model can be "confident" that a bug is now fixed. The
    # `reproduces` boolean (requested in the re-test wrapper) disambiguates.
    reproduces_signal = parsed.get("reproduces")
    if isinstance(reproduces_signal, bool):
        if reproduces_signal:
            # Still present but the model claimed to be unconfirmed → treat as
            # tentative so the finding stays validated with fresh evidence.
            if confidence == "unconfirmed":
                confidence = "tentative"
        else:
            # Fixed: no reproduction regardless of analysis confidence.
            confidence = "unconfirmed"

    explicitly_fixed = reproduces_signal is False

    # Bounded PoC sandbox re-check (best-effort), mirroring the validate node.
    # Skipped when the re-test already determined the issue is fixed — a passing
    # PoC on remediated code must never resurrect the finding.
    poc = parsed.get("poc", "")
    if poc and not explicitly_fixed:
        sb = sandbox_run(poc, workdir=target if target else None)
        if sb.get("ran") and sb.get("exit_code") == 0:
            evidence = (evidence + "\n[sandbox] " + (sb.get("stdout", "")[:1000])).strip()
            if confidence != "confirmed":
                confidence = "tentative"
        else:
            # PoC no longer reproduces: downgrade a claimed confirmation.
            if confidence == "confirmed":
                confidence = "tentative"

    still_present = confidence in _STILL_PRESENT
    new_status = "validated" if still_present else "remediated"

    # Attribute the re-test token/cost to the producing run.
    pt = int(usage.get("prompt_tokens", 0) or 0)
    ct = int(usage.get("completion_tokens", 0) or 0)
    added_cost = cost_mod.cost_usd(usage.get("model", ""), pt, ct)
    if pt or ct:
        run = session.get(AssessmentRun, finding.run_id)
        if run is not None:
            run.prompt_tokens = int(run.prompt_tokens or 0) + pt
            run.completion_tokens = int(run.completion_tokens or 0) + ct
            run.total_tokens = run.prompt_tokens + run.completion_tokens
            run.estimated_cost_usd = float(run.estimated_cost_usd or 0.0) + added_cost

    finding.confidence = confidence
    finding.status = new_status
    finding.evidence = evidence
    finding.updated_at = _now()
    session.flush()
    session.refresh(finding)

    log.info(
        "retest complete",
        extra={
            "finding_id": finding_id,
            "confidence": confidence,
            "status": new_status,
        },
    )

    resp = RetestResponse(
        finding_id=finding.id,
        confidence=finding.confidence,
        status=finding.status,
        evidence=finding.evidence,
        finding=_finding_out(finding),
    )
    return ok(resp.model_dump())
