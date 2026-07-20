# Architecture

---

## System Overview

Sentinel is a single-origin web application: a Next.js static-export dashboard (served at `/app`) talking to a FastAPI backend on `http://localhost:8003`, which drives a LangGraph agent that performs whitebox security assessments against a scope-approved local source repository using the Gemini API, persisting engagements, scope records, findings, and per-run token/cost in PostgreSQL. A security-team user creates a scope-gated engagement, starts an assessment run, and watches validated finding cards stream in over SSE.

## Component Map

```
[Next.js static UI @ /app]
        │  fetch + EventSource (same origin :8003)
        ▼
[FastAPI  api:app]  ──► [ScopeRecord allowlist guard (in-code)]
        │                        │
        ▼                        ▼
[graph.runner (background task)] ──► [LangGraph agent]
        │                                │  recon→prioritize→hunt→validate→report
        │                                ▼
        │                        [Gemini API (google-genai)] + [sandbox subprocess] + [read-only FS]
        ▼
[PostgreSQL 16 (psycopg3)]  ◄──► [SSE tails runs + findings]
        │
        ▼
[structlog stdout + LangSmith traces]
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI (`frontend/`) | Scope form, run view, streaming finding cards, token/cost; labelled stubs for later phases |
| API (`src/api/`) | REST endpoints, `ok()` envelope, SSE stream, in-code scope validation at run start |
| Orchestration (`src/graph/runner.py`) | Create run row, launch background task, invoke compiled graph |
| Agent (`src/graph/`) | LangGraph nodes/edges, bounded step budget, scope-gate node, cost accounting |
| Tools (`src/tools/`) | scope_guard, repo_walk, read_excerpt, parse_manifest, sandbox_run, persist_finding |
| LLM (`src/llm/`) | Gemini provider (auto-detected), usage/token reporting |
| Data (`src/db/`) | SQLAlchemy models, session, Alembic migrations |
| Observability (`src/observability/`) | structlog JSON + LangSmith tracing |

## Data Flow

1. Trigger: user submits the scope form → `POST /engagements` persists engagement + scope_record.
2. User starts a run → `POST /engagements/{id}/runs`; API checks in-code scope, creates an `assessment_runs` row, launches a background task.
3. `graph.runner` invokes the compiled LangGraph: `enforce_scope → recon → prioritize → hunt(loop) → validate → report`, bounded by the step budget.
4. Each validated finding is persisted immediately; the UI's `EventSource` on `GET /runs/{id}/events` receives `progress` + `finding` events; token/cost update live.
5. Output: finding cards (severity, file:line, evidence/PoC, remediation patch) + final run status + total token/cost, all persisted; canonical list via `GET /engagements/{id}/findings`.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (google-genai) | recon/prioritize/hunt/validate reasoning + PoC | retry w/ backoff; then run → failed, partial findings kept |
| PostgreSQL 16 (`sec-agent-pg`, :5433) | persist engagements, scope, findings, run cost | fatal — API 500 / run failed |
| LangSmith | tracing (optional but wired) | degrade: tracing disabled if key absent, run continues |
| Sandbox subprocess | execute generated PoC (no network, bounded) | finding → unconfirmed, run continues |
| Local filesystem (read-only, scoped) | read repo excerpts | fatal if scoped path unreadable |

## Stack

- **Language:** Python 3.12+ (backend/agent), TypeScript (frontend)
- **Agent framework:** LangGraph
- **LLM provider + model:** Gemini via google-genai — fast tier `gemini-3.1-flash`, smart tier `gemini-3.1-pro` (auto-detected from `AGENT_GEMINI_API_KEY`)
- **Backend:** FastAPI (uvicorn, `api:app`, port 8003); run via `uv run python -m src`
- **Database + ORM:** PostgreSQL 16 + SQLAlchemy 2.0 + Alembic; driver `psycopg` (psycopg3), URL `postgresql+psycopg://…`
- **Frontend:** Next.js 15 + React 19 + Tailwind, static export (`output: 'export'`) mounted at `/app`
- **Dependency management:** uv + pyproject.toml (Python), pnpm (frontend)

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | latest | agent graph |
| google-genai | latest | Gemini client |
| fastapi + uvicorn | latest | API + server |
| sqlalchemy | 2.0.x | ORM |
| alembic | latest | migrations |
| psycopg[binary] | 3.x | Postgres driver (add to deps) |
| structlog | latest | JSON logging |
| langsmith | latest | tracing |
| sse-starlette | latest | SSE responses |
| reportlab / weasyprint | latest | PDF export (Phase 3) |
| Playwright | latest | frontend E2E |

**Avoid:** SQLite for any gate or persistence (Postgres is mandatory); persisting raw source files; LLM-driven scope decisions (scope is in-code only); destructive HTTP verbs against live targets (Phase 2 in-code guard).

## Deployment Model
Local long-running service: `uv run python -m src` serves FastAPI + the static UI under `/app` on port 8003; PostgreSQL runs in Docker (`sec-agent-pg`, host :5433). Single origin, single user (localhost) for the MVP.
