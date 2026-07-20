# Sentinel — Whitebox Security-Assessment Agent

> **All commands in this README run from the repository root.** The repo root IS the project — there is no subdirectory to `cd` into except where a block explicitly says so (the frontend build). Every command is prefixed with `uv run`; a bare `alembic`/`pytest`/`python` will fail unless you have manually activated the venv.

Sentinel is a whitebox information-security agent for a security team. A user creates a scope-gated engagement, points it at a local source repository, and starts an agentic, bounded multi-step assessment. The agent runs a LangGraph pipeline — **enforce_scope → recon → prioritize → hunt (four vulnerability classes) → validate → report** — and streams validated finding cards (severity, file:line, evidence/PoC, remediation + suggested patch) into the UI with a live step counter and token/cost panel, all behind a hard **in-code scope gate**.

## What Sentinel Does (Phase 1)

- Scope-gated repository code review: an in-code allowlist refuses any out-of-scope target; no out-of-scope file is read.
- Validates each candidate vulnerability with static LLM reasoning plus a generated PoC executed in an **isolated sandbox copy** of the target (the real repo is never mutated).
- Streams validated findings live; unconfirmed findings are marked, never dropped.
- Reports token count + estimated cost per run and never exceeds its step budget.
- Raw source is never persisted off-box — only findings/metadata and bounded excerpts.

**Phase 2 is live:** non-destructive live-app active probing (read-only, in-code host/verb guard against the recorded scope), an interactive chat mode with turn memory to direct follow-up probes, and re-test after remediation (a fixed finding transitions to `remediated`).

**Phase 3 is live:** one-click dossier export (Markdown / PDF / JSON), proactive next-probe suggestions after each run, same-pattern-elsewhere flagging (findings sharing a vulnerability pattern are linked), and full finding status lifecycle (`new → validated → remediated`, plus `false_positive`).

**Phase 4 is live — OWASP API Security Top 10 (2023):** when creating a `live_app` engagement you can pick the **OWASP API Top 10** assessment profile (optionally supplying an OpenAPI/Swagger source). The agent walks all ten OWASP API categories (API1 BOLA … API10 Unsafe Consumption) non-destructively, tags each finding with its canonical `APIn:2023 — …` reference, and shows an OWASP API Top 10 coverage panel on the run view. The default `general` profile keeps the original live-probing behavior.

---

## Prerequisites

- **Docker Postgres** — a PostgreSQL 16 container named `sec-agent-pg` listening on port **5433**, database `secagent`. Start it with:

  ```bash
  docker start sec-agent-pg
  ```

  (If it does not exist yet, create it, e.g. `docker run -d --name sec-agent-pg -e POSTGRES_DB=secagent -e POSTGRES_PASSWORD=... -p 5433:5432 postgres:16`.)

- **`.env`** at the repo root with:
  - `AGENT_DATABASE_URL` — the psycopg3 URL, e.g. `postgresql+psycopg://<user>:<pass>@localhost:5433/secagent`
  - `AGENT_GEMINI_API_KEY` — a real Google Gemini API key (all gates and tests call the real API)

  See `.env.example` for the full list of variables.

- **`uv`** (Python env/runner) and **`pnpm`** (frontend build).

---

## Setup

Install Python dependencies (from the repo root):

```bash
uv sync
```

---

## Database

Apply migrations, then verify the tables were actually created (from the repo root):

```bash
uv run alembic upgrade head
uv run alembic current
```

`uv run alembic current` must print a revision id ending in `(head)`. Blank output means the migration silently failed — fix that before continuing.

---

## Run

Start Sentinel from the repo root with the run script:

```bash
./run.sh
```

`run.sh` does everything in the right order, every time: starts the Postgres container, applies migrations, **rebuilds the frontend**, and starts the server. Rebuilding on every start is deliberate — `frontend/out/` is a gitignored build artifact, so switching git branches does **not** update it. Without a rebuild you can serve another branch's stale UI (e.g. a build left behind by `dealscout-v0.1`). The script honors `PORT` (default **8003**):

```bash
PORT=8003 ./run.sh
```

Then open **http://localhost:8003/app/** in a browser.

Health check: **http://localhost:8003/health** returns `{"data":{"status":"ok"},"error":null}`.

### Manual run (if you prefer the individual steps)

From the repo root — always rebuild the frontend before starting, for the reason above:

```bash
docker start sec-agent-pg
uv run alembic upgrade head
cd frontend && pnpm install && pnpm build && cd ..
uv run python -m src
```

### Using it

1. Click **New Engagement** and fill the scope form, pointing it at a local repository path and adding that path to the allowlist. Submit.
2. Open the engagement and click **Start Assessment**.
3. Watch the step counter and phase/category advance, finding cards stream in (severity, file:line, evidence/PoC, remediation + suggested patch), and the token/cost panel update.

Phase 2 adds three live features: choose a **live-app** target type for non-destructive active probing, use the **chat** panel to direct follow-up probes over the loaded engagement, and click **re-test** on a finding after fixing it to confirm remediation.

Phase 3 completes the tool: **export** the engagement dossier (MD/PDF/JSON), review the **next-probe suggestions** panel, see **same-pattern** findings linked, and move findings through the **status lifecycle**. No stubs remain.

---

## Tests / Gate

The full Phase 1 gate (real Gemini via `.env`, real Postgres on :5433) runs from the repo root:

```bash
uv run alembic upgrade head && uv run pytest -q && cd frontend && pnpm build && pnpm exec playwright test
```

To run just the Python suite:

```bash
uv run pytest -q
```

The integration suite includes an end-to-end run over a seeded vulnerable-repo fixture and asserts: multiple categories yield validated findings, `step_count <= step_budget`, non-zero token/cost, no full-source persistence, and that a scope-violation run is refused in code.

---

## Layout (Phase 1 surfaces)

```
src/
  __main__.py       ← entry point (`uv run python -m src`)
  api/              ← FastAPI routers: engagements, runs (SSE), findings, health
  config/           ← settings (AGENT_* env vars)
  db/               ← SQLAlchemy models + session (engagements, scope_records, assessment_runs, findings)
  domain/           ← Pydantic request/response models
  graph/            ← LangGraph 7-node assessment pipeline + runner + state
  tools/            ← repo_walk, manifest, scope_guard, read_excerpt, sandbox (isolated PoC exec)
  prompts/          ← recon / prioritize / hunt / validate prompts (.md)
  llm/              ← Gemini client + token/cost accounting
frontend/           ← Next.js static export served at /app
alembic/            ← migrations
tests/
  unit/             ← no key needed
  integration/      ← real Gemini + real Postgres
```
