# Architecture

---

## System Overview

A single long-running FastAPI service that serves both the JSON API and the statically-exported Next.js frontend (mounted at `/app`). One trusted browser user uploads a small CSV; the server profiles it with pandas and holds the dataframe in-process. Each question drives a LangGraph agent that uses Gemini to write pandas code, executes that code locally against the in-memory dataframe, self-corrects on error, and returns the answer plus full shown-work (code, tokens, step trace, optional chart). Query/answer pairs are appended to a log file and recorded in SQLite.

## Component Map

```
Browser (Next.js /app)
    │  upload CSV / ask question (REST)
    ▼
FastAPI  ── mounts ─►  frontend/out (static export at /app)
    │
    ├─► In-memory dataframe store  (keyed by dataset_id, pandas)
    │
    ├─► LangGraph runner ──► Gemini (gemini-2.5-flash)  [write code / synthesize / chart]
    │        │
    │        └─► Local pandas executor (runs generated code in-process)
    │
    ├─► SQLite (runs / query-log table, SQLAlchemy 2.0 + Alembic)
    └─► Query log file (append-only JSON lines) + structlog to stdout
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| API (`src/api/`) | Upload, ask, health endpoints; `ok()`/`api_error()` envelope |
| Dataframe store (`src/domain/`) | In-process dataframe registry keyed by `dataset_id`; profiling |
| Source adapters (`src/domain/sources/`, Phase 3) | `sheets` + `json_api` adapters fetch remote data and return a dataframe + a derived title, converging on the **same** profile/session-creation logic as CSV upload (no separate analysis path) |
| Agent graph (`src/graph/`) | LangGraph: profile → write-code → execute → self-correct → synthesize → chart → finalize |
| Local executor (`src/graph/`) | Runs generated pandas code against the dataframe, captures tracebacks |
| LLM (`src/llm/`) | Gemini provider (already wired); usage-token reporting |
| Storage (`src/db/`) | SQLAlchemy models, session; query log file writer (`src/observability/`) |

## Data Flow

1. Trigger: user uploads a CSV → `POST /api/datasets`.
2. Server parses with pandas, builds a profile (columns, types, row count, DQ flags), stores the dataframe in-process under a new `dataset_id`, returns the profile.
3. User asks a question → `POST /api/datasets/{id}/ask`.
4. LangGraph run: reuse profile → Gemini writes pandas code → execute locally → on error, feed traceback back and retry (bounded) → on success, Gemini synthesizes the answer + method note and (if it fits) a chart spec.
5. Output: answer + method note + executed code + result + chart spec + token usage + step trace; persisted to `runs` and appended to the query log file.

## Trust Boundary: Local Code Execution

**The agent executes LLM-generated Python (pandas) code locally, in-process, against the uploaded dataframe.** This is intentional and acceptable ONLY because this is a single-user, single-trusted-user, locally-run tool. There is **no sandbox**. Consequences and mitigations documented as accepted risk:
- The service must never be exposed to untrusted users or the public internet.
- No authentication is implemented (single local user) — see [api.md](api.md#authentication).
- Execution is bounded by an attempt cap and a per-execution wall-clock timeout (`AGENT_CODE_TIMEOUT_S`, default 15) to prevent runaway loops.
- Generated code runs with the same privileges as the server process. Do not run this on a shared or production host with sensitive data.
- **Phase 3 remote fetch:** the Sheets/JSON source adapters `GET` an arbitrary user-supplied URL server-side (an SSRF surface). Accepted within this same single-trusted-user boundary — **no blocklist is built**. Fetches are bounded by `AGENT_FETCH_TIMEOUT_S` (default 15) and the `AGENT_MAX_UPLOAD_MB` byte cap.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (`gemini-2.5-flash`) | Write pandas code, synthesize answers, build chart specs | Retry/backoff in LLM client; surfaced as `api_error` if unavailable |
| Local filesystem | Query log file, SQLite DB, uploaded temp file | Log + degrade (query log); fatal for DB |
| Remote HTTP source (Phase 3: Google Sheets CSV export, user JSON endpoint) | Fetch a dataset from a public URL | Bounded by `AGENT_FETCH_TIMEOUT_S`; surfaced as `FETCH_FAILED`/`SHEET_NOT_ACCESSIBLE` (see [api.md](api.md)) |

## Stack

- **Language:** Python 3.11+
- **Agent framework:** LangGraph (already wired in `src/graph/`)
- **LLM provider + model:** Gemini via the `google-genai` SDK; default model **`gemini-2.5-flash`** (fast, low-cost, strong at code-writing and analysis — matches the low-spend + code-gen requirement). Key env var `AGENT_GEMINI_API_KEY`. Provider is auto-detected from whichever `AGENT_*` key is set.
- **Backend:** FastAPI (serves API + mounts the static frontend at `/app`); run with `uv run python -m src` on port 8001.
- **Database + ORM:** SQLite (`AGENT_DATABASE_URL=sqlite:///./data/agent.db`) + SQLAlchemy 2.0 + Alembic.
- **Frontend:** Next.js 15 (React 19) static export → `frontend/out/`, built with `cd frontend && pnpm build`, mounted by FastAPI at `/app`.
- **Dependency management:** uv + `pyproject.toml` (Python); pnpm (frontend).

> **Assumed:** the Python package is `src` itself — imports are top-level (`from db.session import ...`, `from graph.runner import ...`), NOT `src.`-prefixed (repo convention).

| Key library | Version | Purpose |
|-------------|---------|---------|
| fastapi | current | API + static mount |
| langgraph | current | Agent graph |
| google-genai | current | Gemini SDK (already a dependency) |
| sqlalchemy | 2.0.x | ORM |
| alembic | current | Migrations |
| structlog | current | Structured request/LLM/tool logging to stdout |
| pandas | current | Dataframe profiling + local code execution |

> **Assumed:** charting is done by returning a declarative chart spec (JSON, shape defined in [auto-chart.md](capabilities/auto-chart.md)) that the frontend renders — no server-side image rendering, so no matplotlib/plotly dependency on the backend. The frontend renders the spec with a lightweight React chart library (**Assumed:** Recharts).

**Avoid:** server-side image rendering (matplotlib/plotly on the backend); code-execution sandboxing frameworks (out of scope — trust boundary is documented instead); any non-SQLite DB (stated constraint is SQLite).

## Observability

Structured logging via structlog from day one (Phase 1): every request logs input question, generated code, execution result/traceback, LLM token usage, latency, and outcome to stdout. Query/answer pairs additionally append to the query log file. LangSmith is NOT used (Gemini/LangGraph build; structured logging satisfies the observability requirement).

## Deployment Model

Local long-running service on the user's own machine: `uv run python -m src` serves API + UI on port 8001. Not deployed to shared infrastructure (see trust boundary).
