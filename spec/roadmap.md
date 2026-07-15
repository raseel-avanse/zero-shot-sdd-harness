# Roadmap

---

## What This Agent Does

Sentinel is a whitebox information-security agent for a security team. A user starts a scoped, authorized engagement against a target and the agent conducts an agentic, bounded multi-step security assessment — recon, prioritize, hunt four vulnerability classes, validate, and report — producing validated, remediated finding cards. Phase 1 assesses local source repositories: the agent reviews the code, validates each candidate vulnerability with static reasoning plus a generated PoC, and streams finding cards (severity, file:line, evidence, remediation patch) into the UI with live token/cost, all behind a hard in-code scope gate.

## Who Uses It

Security engineers / pentesters / AppSec reviewers on a security team who need audit-defensible, validated findings with minimal false positives and low cost — replacing slow, inconsistent manual code review and noisy unvalidated scanner output.

## Core Problem Being Solved

Manual security review is slow and inconsistent; automated scanners produce high-volume, unvalidated, false-positive-heavy output. Sentinel produces a smaller set of validated, evidence-backed, remediation-ready findings under an enforced authorization scope, at controlled cost.

## Success Criteria

- [ ] A user can create a scope-gated engagement and run a validated code review end-to-end against the real Gemini API, first try.
- [ ] Findings are validated (static reasoning + PoC), carry a confidence level, and unconfirmed ones are marked, not dropped.
- [ ] Every finding card has severity, file:line, evidence/PoC, remediation, and a suggested patch.
- [ ] The in-code scope allowlist refuses any out-of-scope target; no out-of-scope file is read.
- [ ] Each run reports token count + estimated cost and never exceeds its step budget.
- [ ] Raw source is never persisted off-box — only findings/metadata and bounded excerpts.

## What This Agent Does NOT Do (Out of Scope)

- No assessment of any target not in the recorded authorization allowlist.
- No destructive/state-changing testing — ever (live probing, Phase 2, is read-only only).
- No persistence of whole source files off-box.
- No multi-tenant auth / user accounts in the MVP (single-user localhost).
- No live-app probing, chat, export, or status lifecycle in Phase 1 (later phases; shown as labelled stubs).
- No CI/CD integration, ticketing sync, or scheduled scans.

## Key Constraints

- Stack FIXED: Python + FastAPI + LangGraph + PostgreSQL (psycopg3) + Gemini + Next.js static export at `/app`, port 8001, run `uv run python -m src`. Bare `src/` imports.
- Real PostgreSQL 16 for all gates (Docker `sec-agent-pg`, :5433) — never SQLite.
- Scope enforcement is IN CODE (allowlist), never prompt-only — safety-critical from Phase 1.
- Bounded step budget per run (cost is a product goal); low token cost prioritized (fast model tier for scanning).
- Observability (LangSmith + structlog) wired from Phase 1.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Backend real on the one core path; frontend visually complete with clearly-labelled non-functional stubs for later phases.

### Phase 1 — Scope-gated repository code review with streamed validated findings

- **Goal:** A user creates a scope-gated engagement (scope form), points it at a local source repo, starts a run against the real Gemini API, and watches validated finding cards (severity, file:line, evidence/PoC, remediation patch) stream in with live step-counter + token/cost. The full LangGraph skeleton (enforce_scope → recon → prioritize → hunt → validate → report + bounded budget) is wired even if some hunt sub-steps are lean.
- **Independent slices (parallel build units):**
  - `db-schema` (backend) — SQLAlchemy models + Alembic migration for `engagements`, `scope_records`, `assessment_runs`, `findings`; repurpose/replace boilerplate `RunRow`. deps: none. Owns: `src/db/models.py`, `alembic/`, `alembic.ini`.
  - `agent-graph` (backend) — repurpose `src/graph/` into the 7-node graph, state, edges, bounded budget, in-code `enforce_scope`; tools in `src/tools/`; prompts in `src/prompts/`; token/cost accounting in `src/llm/`. deps: `db-schema` (persist_finding writes findings) — declared dependency, serialize after db-schema. Owns: `src/graph/*.py`, `src/tools/*.py`, `src/prompts/*.md`, `src/llm/*.py`.
  - `api-routes` (backend) — engagements CRUD, run start (with in-code scope check + background task), SSE `/runs/{id}/events`, findings list, cost; `ok()` envelope; domain models. deps: `db-schema`, `agent-graph`. Owns: `src/api/*.py`, `src/domain/*.py`, `src/graph/runner.py`, `src/config/settings.py`.
  - `frontend` (frontend) — repurpose `frontend/src/app/page.tsx` into engagements list + scope form + run view (streaming finding cards, step counter, token/cost) + labelled stubs; `EventSource` client. deps: none (builds against API contract in `spec/api.md`). Owns: `frontend/src/**`.
  - `e2e-tests` (frontend) — Playwright smoke test of the primary journey (create engagement → start run → see a finding card). deps: none (built against contract; run at gate). Owns: `frontend/tests/e2e/**`.
- **Key surfaces / files:** as listed per slice (disjoint: backend `src/…` + `alembic/` vs frontend `frontend/…`; no shared file).
- **Gate command:** `uv run alembic upgrade head && uv run pytest -q && cd frontend && pnpm build && pnpm exec playwright test` — runs against real Gemini via `.env` and real Postgres (:5433). The pytest suite includes an end-to-end run over a seeded vulnerable repo fixture (large enough that multiple categories yield findings; a sampled scan and full scan differ), asserting ≥3 categories produce validated findings, `step_count <= step_budget`, non-zero token/cost, no full-source persistence, and a scope-violation run is refused.
- **How the user tests it (handoff seed):** `docker start sec-agent-pg`, ensure `.env` has `AGENT_GEMINI_API_KEY` + `AGENT_DATABASE_URL`; run `uv run alembic upgrade head` then `uv run python -m src`; open `http://localhost:8001/app/`. Click "New Engagement", fill the scope form pointing at a local repo path (add it to the allowlist), submit; open the engagement, click "Start Assessment". Expect: step counter + phase/category advance, finding cards stream in with severity/file:line/evidence/remediation+patch, and a token/cost panel updates. Labelled "coming soon" stubs (live probing, chat, re-test, export, status controls, next-probe suggestions) are visible but disabled — these are intentional, not bugs.

### Phase 2 — Live-app probing, interactive chat, and re-test after remediation

- **Goal:** Extend beyond repos: non-destructive (read-only, in-code verb+host guard) active probing of a scope-approved live app, an interactive chat mode with turn memory to direct follow-ups, and re-testing a finding to confirm a fix. (Capability: `live-probing-chat-retest` — 3 sub-features.)
- **Independent slices (parallel build units):**
  - `live-probe-backend` (backend) — non-destructive HTTP probe tools + in-code verb/host guard, live-app graph path. deps: none (extends existing graph). Owns: `src/tools/http_probe.py`, `src/graph/nodes.py` (new live nodes).
  - `chat-backend` (backend) — `chat_turns` model + migration, `POST /engagements/{id}/chat` with conversation memory. deps: none. Owns: `src/db/models.py` (additive migration), `src/api/chat.py`.
  - `retest-backend` (backend) — `POST /findings/{id}/retest` re-running validation. deps: none. Owns: `src/api/findings.py`.
  - `frontend` (frontend) — enable live-app toggle, chat panel, re-test button. deps: none (API contract). Owns: `frontend/src/**`.
- **Key surfaces / files:** disjoint backend modules + additive migration; frontend separate.
- **Gate command:** `uv run alembic upgrade head && uv run pytest -q && cd frontend && pnpm build && pnpm exec playwright test` — real Gemini + real Postgres; tests assert only read-only verbs are issued, out-of-scope hosts refused in code, chat references prior-turn context, and re-test transitions a fixed finding to `remediated`.
- **How the user tests it (handoff seed):** create a `live_app` engagement (now enabled) with a scope-approved host; run a probe and confirm only GET/HEAD/OPTIONS are issued; use the chat panel to ask a follow-up that depends on an earlier turn; click "Re-test" on a finding and see its status update.

### Phase 3 — Export dossier, proactive suggestions, and finding lifecycle

- **Goal:** Turn accumulated findings into decision-ready output: one-click MD/PDF/JSON export, proactive next-probe suggestions + same-pattern-elsewhere flagging, and full finding status lifecycle management. (Capability: `export-proactive-lifecycle` — 3 sub-features.)
- **Independent slices (parallel build units):**
  - `export-backend` (backend) — `GET /engagements/{id}/export?format=` rendering MD/PDF/JSON. deps: none. Owns: `src/api/export.py`, `src/export/`.
  - `proactive-backend` (backend) — next-probe suggestions + same-pattern detection in `report` node, `pattern_ref` links. deps: none. Owns: `src/graph/nodes.py` (report node), `src/prompts/suggest.md`.
  - `lifecycle-backend` (backend) — `PATCH /findings/{id}` status transitions with timestamps. deps: none. Owns: `src/api/findings.py`.
  - `frontend` (frontend) — enable export button, next-probe panel, finding status controls. deps: none. Owns: `frontend/src/**`.
- **Key surfaces / files:** disjoint backend modules; frontend separate.
- **Gate command:** `uv run alembic upgrade head && uv run pytest -q && cd frontend && pnpm build && pnpm exec playwright test` — real Gemini + real Postgres; tests assert export produces valid MD/PDF/JSON with all findings+scope+cost, ≥2 next-probe suggestions returned, a same-pattern occurrence flagged on a seeded duplicated-pattern repo, and status transitions persist.
- **How the user tests it (handoff seed):** open a completed engagement; export the dossier in each format and open the files; review the next-probe suggestions panel and same-pattern flags; move a finding through new → validated → remediated and mark one false-positive, confirming persistence on refresh.

### Phase 4 — OWASP API Security Top 10 (2023) assessment profile for live APIs

- **Goal:** A user creates a `live_app` engagement, selects the **OWASP API Top 10** profile (optionally supplying an OpenAPI/Swagger definition), runs it against an authorized API, and watches validated finding cards stream in tagged with canonical OWASP API category IDs+titles, plus a compact OWASP API Top 10 coverage view. Reuses the Phase 2 non-destructive live path (recon → prioritize → live_hunt → validate → report) with an OWASP-API category taxonomy and profile-specific prompts; all guards (verb/host/budget) unchanged. (Capability: `owasp-api-top10`.)
- **Independent slices (parallel build units):**
  - `backend-graph` (backend) — OWASP API category taxonomy + profile-driven prompts (`src/prompts/owasp_api_prioritize.md`, `src/prompts/owasp_api_hunt.md`), profile branching inside `live_recon`/`prioritize`/`live_hunt` and edges, new optional OpenAPI ingestion tool `src/tools/openapi_ingest.py`, safety limits reusing `scope_guard`/`http_probe`, and `assessment_profile`/`api_spec_ref` added to `AgentState` + `runner._build_initial_state` (reads via `getattr(engagement, "assessment_profile", "general")` so it does not hard-depend on the migration landing first). deps: none. Owns: `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/state.py`, `src/graph/runner.py`, `src/prompts/owasp_api_*.md`, `src/tools/openapi_ingest.py`.
  - `api-data` (backend) — `assessment_profile` + `api_spec_ref` columns on `Engagement` and `owasp_api_ref` on `Finding` in `src/db/models.py` + one additive Alembic migration; accept/echo the new fields in `src/domain/engagements.py` + `src/api/engagements.py`; surface `owasp_api_ref` in `src/domain/findings.py` (`FindingOut`) so the findings list + SSE `finding` event carry it. deps: none (disjoint files from the graph slice). Owns: `src/db/models.py`, `alembic/versions/*`, `src/domain/engagements.py`, `src/domain/findings.py`, `src/api/engagements.py`.
  - `frontend` (frontend) — profile selector + optional OpenAPI source input on the new-engagement form (shown when live-app chosen), OWASP API category badge on finding cards, and the compact OWASP API Top 10 coverage panel on the run view. deps: none (builds against the API contract). Owns: `frontend/src/**`.
  - `test-fixture` (backend/tests) — a seeded intentionally-vulnerable fixture API app (`tests/fixtures/vuln_api_app.py`, extending the throwaway `scratchpad/target_app.py` pattern into a proper committed fixture) exhibiting at least BOLA (API1: unauthenticated object access by predictable ID), broken/missing authentication (API2: a protected endpoint served without credentials), and security misconfiguration (API8: verbose error / missing security headers / debug endpoint); plus the pytest OWASP e2e test that boots it on a local port, creates an `owasp_api` `live_app` engagement pointed at it (host allowlisted), runs, and asserts the findings. deps: none (standalone). Owns: `tests/fixtures/**`, `tests/test_owasp_api_top10.py`.
- **Key surfaces / files:** disjoint — graph modules vs data/API modules vs frontend vs tests/fixtures; no shared file across slices.
- **Gate command:** `uv run alembic upgrade head && uv run pytest -q && cd frontend && pnpm build && pnpm exec playwright test` — runs against real Gemini via `.env` and real Postgres (:5433), never SQLite. The pytest suite includes `tests/test_owasp_api_top10.py`, which boots the seeded vulnerable fixture API, runs an `owasp_api`-profile assessment end-to-end, and asserts: ≥3 validated findings whose `owasp_api_ref` is a canonical `APIn:2023 — …` string INCLUDING at least API1:2023 (BOLA), API2:2023 (Broken Authentication), and API8:2023 (Security Misconfiguration); only GET/HEAD/OPTIONS verbs were issued (request log) and a mutating verb + an out-of-scope host are refused in code; `step_count <= step_budget`; non-zero token/cost; raw OpenAPI spec content not persisted.
- **How the user tests it (handoff seed):** `docker start sec-agent-pg`; run `uv run alembic upgrade head` then `uv run python -m src`; open `http://localhost:8001/app/`. Start the seeded fixture API (or any authorized API) locally; click "New Engagement", choose `target_type=live_app`, select the **OWASP API Top 10** profile, set `target_ref` + `authorized_targets` to the API host, optionally paste its OpenAPI URL, submit; open the engagement and click "Start Assessment". Expect: finding cards stream in each showing an OWASP API category badge (e.g. `API1:2023 — Broken Object Level Authorization`), the OWASP API Top 10 coverage panel fills in per category, and token/cost updates. Selecting the profile without an OpenAPI source still runs (light discovery).
