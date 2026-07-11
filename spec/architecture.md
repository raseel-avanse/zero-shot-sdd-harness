# Architecture — DealScout

---

## System Overview

DealScout is a single-user, single-origin web application. A Next.js UI (statically exported, served by FastAPI at `:8001/app/`) posts a shopping query to a FastAPI backend. The backend starts a LangGraph research run in the background and immediately returns a `run_id`; the UI polls the run's status to render a named-step progress bar. The graph drives Gemini (with the native `google_search` grounding tool) through a research pass and a ranking pass, persists the ranked deals plus token/cost usage to SQLite, and the UI renders the finished ranked list and cost footer. Every run is fully stateless — no data from prior runs is read.

## Component Map

```
Browser (Next.js UI @ :8001/app/)
    │  POST /runs  (start)          GET /runs/{id} (poll)
    ▼
FastAPI (src/api)  ──────────────►  Background run executor (thread)
    │                                     │
    ▼                                     ▼
SQLite (runs, deals)  ◄────────────  LangGraph graph (src/graph)
                                          │  research → rank
                                          ▼
                                   Gemini API + google_search grounding
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI (`frontend/`) | Query input (name in P1; url/category in P2), progress polling, ranked-list + cost render, clarify prompt (P2) |
| API (`src/api`) | `POST /runs` (start background run), `GET /runs/{id}` (status/progress/result), `POST /runs/{id}/answer` (resume clarify, P2) |
| Orchestration (`src/graph`) | LangGraph state machine: research → rank; routing + clarify + deal-quality in P2 |
| LLM (`src/llm`) | `LLMClient` → `GeminiProvider` with `google_search` grounding; returns text + grounding metadata + token usage |
| Tools (`src/tools`) | Pure functions: cost estimation from usage; deal-quality heuristics (P2) |
| Storage (`src/db`) | SQLAlchemy 2.0 models + SQLite; `runs` and `deals` tables |
| Observability (`src/observability`) | structlog JSON logging per node + LLM call (tokens/latency); LangSmith tracing when enabled |

## Data Flow

1. **Trigger:** user submits a query in the UI → `POST /runs` with `{query_type, query_text}`.
2. API creates a `runs` row (`status=running`, `progress_step="queued"`), launches the graph in a background thread, returns `run_id`.
3. **research node:** Gemini call with `google_search` grounding finds listings + reviews across Indian sites; writes trimmed research notes + grounding metadata + usage to state; updates `progress_step`.
4. **rank node:** Gemini call turns research notes into a structured ranked list of 3–5 deals (site, price, reason); usage accumulated; `progress_step` updated.
5. **finalize:** persists `deals` rows, total tokens, estimated INR cost, `status=completed`.
6. **Poll:** UI polls `GET /runs/{id}`; renders progress while `running`, then the ranked list + cost footer when `completed` (or a human-readable error when `failed`).
7. **Output:** ranked list of 3–5 deals + per-query tokens/cost.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (`google-genai`) | Grounded web research + ranking | Node sets `state.error`; run → `failed`; UI shows "Couldn't reach the research service — try again". Retry with backoff on transient errors. |
| Google Search grounding tool | Native web search inside Gemini | If grounding returns no results, rank node produces fewer/zero deals; UI shows an empty-state "No confident deals found" message. |
| SQLite (`AGENT_DATABASE_URL`) | Run + deal persistence | Startup fails fast if unreachable; per-run write errors → run `failed`. |

## Stack

> Concrete choices for DealScout. Generic rules (model-naming, DB driver, dev port, real-key tests) live in `harness/patterns/tech-stack.md`.

- **Language:** Python 3.12+ (backend), TypeScript (frontend).
- **Agent framework:** LangGraph (already wired in the skeleton; extended in place).
- **LLM provider + model:** Google Gemini via `google-genai`, using the native `google_search` grounding tool. Model: **`gemini-2.5-flash`** for both the research and rank nodes. Env-configurable via `AGENT_LLM_MODEL`.
  > **Chosen:** `gemini-2.5-flash` (verified live: supports the `google_search` grounding tool, returns `usage_metadata` for prompt/completion tokens plus grounding metadata, and has free-tier quota). `gemini-2.5-pro` (free-tier limit 0) and `gemini-3.1-pro` (404 — not present on this key) are not available on this API key. Env-overridable via `AGENT_LLM_MODEL`, so switching to another grounding-capable Gemini model is a one-line `.env` change.
- **Backend:** FastAPI (flat `src/` package; app is `api:app`; run via `uv run python -m src` on port 8001).
- **Database + ORM:** SQLite via `AGENT_DATABASE_URL` + SQLAlchemy 2.0 (declarative `Mapped`), Alembic migrations.
- **Frontend:** Next.js 15 + React 19, statically exported and served by FastAPI at `:8001/app/` (single origin — UI and API share `:8001`).
- **Dependency management:** uv + `pyproject.toml` (Python); pnpm (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | (skeleton) | Graph orchestration |
| google-genai | (skeleton) | Gemini client + `google_search` grounding + `usage_metadata` |
| fastapi + uvicorn | (skeleton) | API + static UI serving |
| sqlalchemy + alembic | 2.0 | ORM + migrations |
| structlog | (skeleton) | Structured JSON logging |
| next / react | 15 / 19 | UI |
| @playwright/test | (skeleton) | Headless E2E |

**Avoid:** third-party scraping libraries or external search APIs (all web research must go through Gemini's native `google_search` grounding); any persistence of user history/preferences/conversation (statelessness is a hard product rule); the Anthropic provider path (Gemini only for this project).

## Deployment Model

Long-running local service: one process (`uv run python -m src`, uvicorn on `:8001`) serves both the FastAPI API and the statically-exported Next.js UI at `/app/`. SQLite file on local disk. Single user, single machine. Background research runs execute in a thread pool within the same process (see [`agent.md`](agent.md#concurrency-model)).
