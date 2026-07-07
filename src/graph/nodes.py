"""Sentinel security-assessment graph nodes (see spec/agent.md).

Bounded multi-step pipeline: enforce_scope -> recon -> prioritize ->
hunt(loop per category) -> validate -> report, with handle_error as the
fatal sink. Nodes call in-code tools directly; the LLM produces analysis,
never tool routing. scope_guard is enforced in code regardless of LLM output.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from db.models import AssessmentRun, Finding
from db.session import create_db_session
from graph.state import AgentState
from llm import cost as cost_mod
from llm.client import LLMClient
from tools import manifest as manifest_tool
from tools import repo_walk, scope_guard
from tools.read_excerpt import read_excerpt
from tools.sandbox import sandbox_run

log = logging.getLogger("sentinel.graph")

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"

# The four supported vulnerability classes (spec/data.md Finding.category).
_CATEGORIES = ["injection", "broken_auth", "secrets_misconfig", "vuln_deps"]

# Bound how much source we feed the hunt LLM per category (cost + prompt size).
_MAX_HUNT_FILES = 8
_MAX_VALIDATE_FINDINGS = 12


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_json(text: str) -> dict | list:
    """Defensively parse model JSON output, tolerating code fences/prose."""
    if not text:
        return {}
    t = text.strip()
    if t.startswith("```"):
        # strip leading ```json / ``` and trailing ```
        t = t.split("```", 2)
        t = t[1] if len(t) > 1 else text
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
        t = t.strip().rstrip("`").strip()
    try:
        return json.loads(t)
    except (json.JSONDecodeError, ValueError):
        # last resort: grab the outermost {...} or [...]
        for opener, closer in (("{", "}"), ("[", "]")):
            start = t.find(opener)
            end = t.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(t[start : end + 1])
                except (json.JSONDecodeError, ValueError):
                    pass
        return {}


def _accumulate(state: AgentState, usage: dict) -> dict:
    """Fold a call's token usage + cost into running totals. Returns updated fields."""
    pt = int(usage.get("prompt_tokens", 0) or 0)
    ct = int(usage.get("completion_tokens", 0) or 0)
    model = usage.get("model", "")
    prompt_tokens = int(state.get("prompt_tokens", 0)) + pt
    completion_tokens = int(state.get("completion_tokens", 0)) + ct
    added_cost = cost_mod.cost_usd(model, pt, ct)
    estimated_cost_usd = float(state.get("estimated_cost_usd", 0.0)) + added_cost
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": estimated_cost_usd,
    }


def _persist_progress(state: AgentState, **extra) -> None:
    """Update the assessment_runs row with live progress + token/cost."""
    run_id = state.get("run_id")
    if not run_id:
        return
    try:
        with create_db_session() as session:
            run = session.get(AssessmentRun, run_id)
            if run is None:
                return
            run.step_count = int(state.get("step_count", 0))
            run.current_phase = state.get("current_phase")
            run.current_category = state.get("current_category")
            run.prompt_tokens = int(state.get("prompt_tokens", 0))
            run.completion_tokens = int(state.get("completion_tokens", 0))
            run.total_tokens = run.prompt_tokens + run.completion_tokens
            run.estimated_cost_usd = float(state.get("estimated_cost_usd", 0.0))
            for key, val in extra.items():
                setattr(run, key, val)
    except Exception:  # noqa: BLE001 — progress persistence must not crash the run
        log.exception("progress persistence failed", extra={"run_id": run_id})


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #


def enforce_scope(state: AgentState) -> AgentState:
    """SAFETY-CRITICAL entry gate. Pure in-code allowlist check — NO LLM call.

    Refuses any target_path not contained inside scope_allowlist; on refusal it
    sets state.error and the graph routes straight to handle_error without ever
    reading files or contacting the model.
    """
    target = state.get("target_path", "")
    allowlist = state.get("scope_allowlist", []) or []
    budget = int(state.get("step_budget") or cost_mod.step_budget())

    base = {
        "step_budget": budget,
        "step_count": int(state.get("step_count", 0)),
        "status": "running",
        "current_phase": "enforce_scope",
    }

    if not scope_guard.check(target, allowlist):
        log.warning(
            "scope violation refused in code",
            extra={"run_id": state.get("run_id"), "target": target},
        )
        return {**base, "error": f"scope violation: {target}"}

    return {**base, "error": None}


def recon(state: AgentState) -> AgentState:
    """Read-only inventory + LLM (fast) tech summary. No raw source persisted."""
    step = int(state.get("step_count", 0)) + 1
    target = state.get("target_path", "")
    try:
        inventory = repo_walk.walk(target)
        deps: list[dict] = []
        for man in inventory.get("manifests", []):
            deps.extend(manifest_tool.parse_manifest(target, man))
        inventory["dependencies"] = deps

        usage = LLMClient().complete(
            f"Repository inventory (JSON):\n{json.dumps(inventory)[:20000]}",
            system=_load_prompt("recon.md"),
            tier="fast",
        )
        parsed = _parse_json(usage.get("text", ""))
        if isinstance(parsed, dict):
            inventory["summary"] = parsed.get("summary", "")
            inventory["frameworks"] = parsed.get("frameworks", [])
            inventory["hotspot_files"] = parsed.get("hotspot_files", [])

        update = {
            "recon": inventory,
            "step_count": step,
            "current_phase": "recon",
            **_accumulate(state, usage),
        }
        _persist_progress({**state, **update})
        return update
    except Exception as exc:  # noqa: BLE001
        log.exception("recon failed", extra={"run_id": state.get("run_id")})
        return {"step_count": step, "current_phase": "recon", "error": f"recon failed: {exc}"}


def prioritize(state: AgentState) -> AgentState:
    """LLM (fast) ranking of the four vuln categories to hunt."""
    step = int(state.get("step_count", 0)) + 1
    recon_data = state.get("recon", {})
    try:
        usage = LLMClient().complete(
            f"Recon summary (JSON):\n{json.dumps(recon_data)[:12000]}",
            system=_load_prompt("prioritize.md"),
            tier="fast",
        )
        parsed = _parse_json(usage.get("text", ""))
        priorities = parsed.get("priorities", []) if isinstance(parsed, dict) else []
        # Keep only known categories; fall back to the full set if empty/garbage.
        priorities = [c for c in priorities if c in _CATEGORIES]
        for cat in _CATEGORIES:
            if cat not in priorities:
                priorities.append(cat)

        update = {
            "priorities": priorities,
            "candidate_findings": state.get("candidate_findings", []),
            "step_count": step,
            "current_phase": "prioritize",
            **_accumulate(state, usage),
        }
        _persist_progress({**state, **update})
        return update
    except Exception as exc:  # noqa: BLE001
        log.exception("prioritize failed", extra={"run_id": state.get("run_id")})
        return {
            "step_count": step,
            "current_phase": "prioritize",
            "error": f"prioritize failed: {exc}",
        }


def hunt(state: AgentState) -> AgentState:
    """Scan ONE category (popped from priorities) over bounded excerpts (LLM fast)."""
    step = int(state.get("step_count", 0)) + 1
    priorities = list(state.get("priorities", []))
    if not priorities:
        return {"step_count": step, "current_phase": "hunt"}

    category = priorities.pop(0)
    recon_data = state.get("recon", {})
    target = state.get("target_path", "")
    candidates = list(state.get("candidate_findings", []))

    try:
        hotspots = recon_data.get("hotspot_files") or recon_data.get("files", [])
        excerpts = []
        for rel in hotspots[:_MAX_HUNT_FILES]:
            try:
                excerpts.append(f"### {rel}\n{read_excerpt(target, rel)}")
            except OSError:
                continue
        excerpt_blob = "\n\n".join(excerpts)[:60000]

        usage = LLMClient().complete(
            f"Category: {category}\n\nExcerpts:\n{excerpt_blob}",
            system=_load_prompt("hunt.md"),
            tier="fast",
        )
        parsed = _parse_json(usage.get("text", ""))
        found = parsed.get("candidates", []) if isinstance(parsed, dict) else []
        for cand in found:
            if isinstance(cand, dict):
                cand["category"] = category
                candidates.append(cand)

        update = {
            "priorities": priorities,
            "candidate_findings": candidates,
            "current_category": category,
            "step_count": step,
            "current_phase": "hunt",
            **_accumulate(state, usage),
        }
        _persist_progress({**state, **update})
        return update
    except Exception as exc:  # noqa: BLE001
        # A single category failure is non-fatal: log, drop it, continue the loop.
        log.exception(
            "hunt failed for category", extra={"run_id": state.get("run_id"), "category": category}
        )
        return {
            "priorities": priorities,
            "candidate_findings": candidates,
            "current_category": category,
            "step_count": step,
            "current_phase": "hunt",
        }


def validate(state: AgentState) -> AgentState:
    """LLM (smart) static reasoning + PoC + bounded sandbox check; persist findings."""
    step = int(state.get("step_count", 0)) + 1
    candidates = list(state.get("candidate_findings", []))
    findings = list(state.get("findings", []))
    target = state.get("target_path", "")
    run_state = {**state, "step_count": step, "current_phase": "validate"}

    try:
        for cand in candidates[:_MAX_VALIDATE_FINDINGS]:
            usage = LLMClient().complete(
                f"Candidate finding (JSON):\n{json.dumps(cand)[:12000]}",
                system=_load_prompt("validate.md"),
                tier="smart",
            )
            run_state.update(_accumulate(run_state, usage))
            parsed = _parse_json(usage.get("text", ""))
            if not isinstance(parsed, dict):
                parsed = {}

            confidence = parsed.get("confidence", "unconfirmed")
            evidence = parsed.get("evidence") or cand.get("evidence", "")

            # Bounded PoC sandbox check (best-effort). Failure/timeout downgrades
            # a would-be 'confirmed' to 'unconfirmed' but never drops the finding.
            poc = parsed.get("poc", "")
            if poc:
                sb = sandbox_run(poc, workdir=target if target else None)
                if sb.get("ran") and sb.get("exit_code") == 0:
                    evidence = (evidence + "\n[sandbox] " + (sb.get("stdout", "")[:1000])).strip()
                    if confidence != "confirmed":
                        confidence = "tentative"
                else:
                    if confidence == "confirmed":
                        confidence = "tentative"

            finding = {
                "category": cand.get("category", "injection"),
                "title": parsed.get("title") or cand.get("title", "Untitled finding"),
                "severity_label": parsed.get("severity_label")
                or cand.get("severity_label", "info"),
                "cvss_score": parsed.get("cvss_score", cand.get("cvss_score")),
                "location": cand.get("location", "unknown"),
                "description": parsed.get("description") or cand.get("description", ""),
                "evidence": evidence,
                "confidence": confidence,
                "remediation": parsed.get("remediation", "See description."),
                "suggested_patch": parsed.get("suggested_patch"),
            }
            _persist_finding(state, finding)
            findings.append(finding)

        update = {
            "findings": findings,
            "step_count": step,
            "current_phase": "validate",
            "prompt_tokens": run_state.get("prompt_tokens", state.get("prompt_tokens", 0)),
            "completion_tokens": run_state.get(
                "completion_tokens", state.get("completion_tokens", 0)
            ),
            "estimated_cost_usd": run_state.get(
                "estimated_cost_usd", state.get("estimated_cost_usd", 0.0)
            ),
        }
        _persist_progress({**state, **update})
        return update
    except Exception as exc:  # noqa: BLE001
        log.exception("validate failed", extra={"run_id": state.get("run_id")})
        return {
            "findings": findings,
            "step_count": step,
            "current_phase": "validate",
            "error": f"validate failed: {exc}",
        }


def _persist_finding(state: AgentState, finding: dict) -> None:
    """Insert one validated/unconfirmed finding immediately (streamable to UI)."""
    run_id = state.get("run_id")
    engagement_id = state.get("engagement_id")
    if not run_id or not engagement_id:
        return
    cvss = finding.get("cvss_score")
    try:
        cvss = float(cvss) if cvss is not None else None
    except (TypeError, ValueError):
        cvss = None
    with create_db_session() as session:
        session.add(
            Finding(
                engagement_id=engagement_id,
                run_id=run_id,
                category=finding.get("category", "injection"),
                title=finding.get("title", "Untitled finding"),
                severity_label=finding.get("severity_label", "info"),
                cvss_score=cvss,
                location=finding.get("location", "unknown"),
                description=finding.get("description", ""),
                evidence=finding.get("evidence", ""),
                confidence=finding.get("confidence", "unconfirmed"),
                status="validated",
                remediation=finding.get("remediation", "See description."),
                suggested_patch=finding.get("suggested_patch"),
            )
        )


def report(state: AgentState) -> AgentState:
    """Finalize: mark the run completed with final token/cost totals."""
    update = {"status": "completed", "current_phase": "report"}
    _persist_progress(
        {**state, **update},
        status="completed",
        completed_at=_now(),
    )
    return update


def handle_error(state: AgentState) -> AgentState:
    """Fatal sink: mark the run failed; retain findings already persisted."""
    error = state.get("error") or "unknown error"
    log.error("run failed", extra={"run_id": state.get("run_id"), "error": error})
    update = {"status": "failed", "error": error}
    _persist_progress(
        {**state, **update},
        status="failed",
        error_message=error,
        completed_at=_now(),
    )
    return update
