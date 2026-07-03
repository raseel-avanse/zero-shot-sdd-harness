# Roadmap

---

## What This Agent Does

A single-user, browser-based data-analyst agent. The user uploads a small tabular CSV and asks plain-English questions. On upload the agent auto-profiles the data (columns, types, row count, data-quality issues). For each question it writes real pandas code, runs it locally against the actual dataframe, self-corrects on error (bounded retry), and returns the key numbers plus a brief note on how it got there — with an auto-generated chart when one fits. All work is shown: executed code, live step-status, per-question token count, and an append-only query log.

## Who Uses It

A single analyst / data-curious individual doing ad-hoc exploration on their own machine. They act on the numbers, so the trust bar is high.

## Core Problem Being Solved

Replaces the write-pandas-yourself / spin-up-a-notebook loop for quick questions, while keeping the transparency (real executed code + shown work) needed to trust the answer.

## Success Criteria

- [ ] Upload a CSV → get an accurate profile (correct row count, dtypes, null flags).
- [ ] Ask a factual question → get the numerically correct answer, computed by real executed pandas code that is shown.
- [ ] A first-attempt code error is self-corrected within 3 attempts and still yields a correct answer.
- [ ] Every answer shows: method note, collapsible executed code, token count, and an auto-chart when the result fits.
- [ ] Every question/answer is appended to the query log file.

## What This Agent Does NOT Do (Out of Scope)

- No multi-user / auth / public deployment (single trusted local user; executes generated code un-sandboxed — see [architecture.md](architecture.md#trust-boundary-local-code-execution)).
- No large / out-of-memory datasets (few-MB in-memory files only).
- Phase 1: no server-persisted multi-question session memory (history is client-held), no Google Sheets / JSON-API / live-DB sources, no dataset export. These are labelled stubs and later phases.
- No server-side image charts (returns a declarative chart spec the frontend renders).

## Key Constraints

- Small in-memory files (few MB).
- Correctness + shown-work prioritized over speed.
- Keep LLM spend low (cheap Gemini tier; profile+sample only in prompts).
- SQLite + the fixed repo stack (see [architecture.md § Stack](architecture.md#stack)).

## Phases of Development

> Phase 1 is the smallest first-time-right user-testable win. Everything beyond it appears in the UI as clearly-labelled non-functional stubs.

### Phase 1 — Upload → Ask → Answer (with shown work)

- **Goal:** Upload a CSV, ask one plain-English question, and get an accurate answer computed by locally-executed, self-correcting pandas — with key numbers + method note + collapsible code + auto-chart-when-it-fits, per-question token count, live step-status, and the Q&A appended to the query log.
- **Independent slices (parallel build units):**
  - `backend` (backend, deps: none) — CSV upload+profiling, in-memory dataframe store, LangGraph graph (init → write_code → execute → self-correct loop → synthesize → chart → finalize), local pandas executor, Gemini prompts, `runs` model + Alembic migration, query-log file writer, structlog wiring, the two API endpoints + health, and pytest tests. Owns `src/`, `alembic/`, `tests/` (backend), `pyproject.toml` deps (pandas), `src/prompts/`.
  - `frontend` (frontend, deps: **API contract in [api.md](api.md)** — buildable in parallel because the answer-card contract is pinned there) — upload zone, profile card, question box, live step-status, answer card (numbers/method-note/collapsible code/token badge/chart via Recharts), client-held conversation history, and the labelled Coming-soon stubs. Owns `frontend/`, `frontend/tests/e2e/` (Playwright smoke test).
- **Key surfaces / files:**
  - backend: `src/api/datasets.py`, `src/api/ask.py` (or extend `src/api/runs.py`), `src/domain/dataset_store.py`, `src/domain/profile.py`, `src/graph/{state,nodes,edges,agent,runner}.py`, `src/graph/executor.py`, `src/prompts/{write_code,synthesize,chart}.md`, `src/db/models.py` (Run), `alembic/versions/*`, `src/observability/query_log.py`, `tests/`.
  - frontend: `frontend/src/app/page.tsx`, `frontend/src/components/{UploadZone,ProfileCard,QuestionBox,StepStatus,AnswerCard,Chart,Stubs}.tsx`, `frontend/tests/e2e/smoke.spec.ts`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest` (backend, real Gemini via `.env`), plus `cd frontend && pnpm build && pnpm exec playwright test` (frontend E2E against the built app). Backend pytest MUST include a test that (a) computes a correct numeric answer via executed code on a fixture large enough that a sampled answer would differ from the full-data answer, and (b) forces a first-attempt code error (e.g. a wrong-column hint) and asserts self-correction recovers within 3 attempts.
- **How the user tests it (handoff seed):** Run `uv run python -m src`, open `http://localhost:8001/app`. Upload a CSV → see the profile card (row count, columns, null flags). Type "what is the average of &lt;numeric column&gt;?" → watch step-status advance, then read the answer card: key number, method note, "Show code" reveals the pandas, a token count badge, and a chart if the result fits. Ask a "top 5 by X" question → expect a bar chart. The "Connect Google Sheets / JSON API", "Live database", and "Export dataset" controls are visibly disabled with *Coming soon* badges — those are stubs, not bugs.

### Phase 2 — Persisted multi-question session

- **Goal:** Ask many questions against the same loaded dataset with server-persisted conversation history that survives reload, and the agent uses prior turns as context.
- **Capabilities:** (1) session-scoped conversation memory persisted in DB; (2) history reload/replay endpoint + UI; (3) follow-up questions that reference prior answers ("and by month?").
- **Independent slices:**
  - `backend` (deps: Phase 1 backend) — `Session` model + `runs.session_id` FK + Alembic migration, session-scoped memory (last N=3 turns) injected into `write_code`/`synthesize` prompts via `node_init`, `GET /api/sessions` + `GET /api/sessions/{id}` list/replay endpoints, `session_id` added to `POST /api/datasets` + ask responses. Owns `src/` + `alembic/` + `tests/`.
  - `frontend` (deps: pinned session API contract in [api.md](api.md)) — history loads from server on reload, session picker, follow-up handling, and the "re-upload to continue this session" state when `dataframe_loaded` is false. Owns `frontend/`.
- **Key files:** `src/db/models.py` (Session; a Turn is a `runs` row), `src/api/sessions.py`, `src/graph/nodes.py` (context injection in `node_init`), `frontend/src/components/History.tsx`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/test_sessions.py` + `cd frontend && pnpm build && pnpm exec playwright test e2e/session.spec.ts` (real Gemini via `.env`).
- **How the user tests it:** Ask 3 questions, reload the page → history is still there; ask a follow-up ("and broken down by region?") → answer uses the prior context.

### Phase 3 — Additional data sources (Google Sheets / JSON API)

- **Goal:** Load a dataset from a Google Sheet URL or a JSON-API endpoint (not just CSV upload), then analyze it **identically** to a CSV — the loaded dataset flows through the SAME profile → ask → answer → session path from Phases 1–2 (no separate analysis code path).
- **Capabilities:** (1) Google Sheets ingest → dataframe + profile; (2) JSON-API ingest → dataframe + profile; (3) unified source picker replacing the Phase-1 stub buttons. See [../spec/capabilities/data-sources.md](capabilities/data-sources.md).
- **Independent slices:**
  - `backend` (deps: Phase 1 dataframe store) — `sheets` + `json_api` source adapters that fetch remote data and return a dataframe + derived title, converging on the SAME create-session/build-profile/store-dataframe logic as `POST /api/datasets`; two new ingest endpoints. Owns `src/domain/sources/`, `src/api/datasets.py`, `src/settings.py` (add `AGENT_FETCH_TIMEOUT_S`), `tests/`.
  - `frontend` (deps: **ingest API contract pinned in [api.md](api.md)** — buildable in parallel) — wire the "Connect Google Sheets" / "Connect JSON API" stub buttons into real forms; on success reuse the exact same downstream (ProfileCard → QuestionBox → AnswerCard → sessions). Owns `frontend/`.
- **Key files:** `src/domain/sources/{sheets,json_api}.py`, `src/api/datasets.py` (`POST /api/datasets/from-google-sheet`, `POST /api/datasets/from-json-api`), `frontend/src/components/SourcePicker.tsx`.
- **Gate command:** `uv run pytest` + `cd frontend && pnpm build && pnpm exec playwright test`.
- **Lean-gate policy (Phase 3):** the mandatory real-Gemini floor is **unchanged** (~4 live tests from Phases 1–2) — do NOT add new live-Gemini tests. All source-loading plumbing (Sheets-URL id/gid parsing, sheet→dataframe, JSON→dataframe normalization for all four rules, and the full error taxonomy incl. `SHEET_NOT_ACCESSIBLE`/`NO_TABULAR_DATA`/`FETCH_FAILED` timeout) is tested against **deterministic fakes / local fixtures with NO network** (monkeypatch the HTTP fetch to return fixture bytes/JSON, HTML-login, timeout). E2E stays ONE consolidated Playwright spec — at most assert one new-source load within it.
- **How the user tests it:** Click "Connect Google Sheets", paste a public share URL (shared "anyone with the link") → profile card appears → ask a question exactly as with a CSV. Try "Connect JSON API" with a URL returning an array of records → same result. A private sheet shows a clear "share as anyone with the link" error, not a crash.

### Phase 4 — Live database connection

- **Goal:** Connect a read-only SQL database, browse tables, load a table/query result as the dataset, and analyze it.
- **Capabilities:** (1) DB connection + table listing; (2) load a table or SQL query into a dataframe + profile; (3) DB source in the unified picker.
- **Independent slices:** `backend` (deps: Phase 3 source framework) owns `src/domain/sources/db.py` + endpoints + tests; `frontend` (deps: DB API contract) wires the "Live database" stub.
- **Gate command:** `uv run pytest tests/test_db_source.py` (against a real fixture DB) + `cd frontend && pnpm build && pnpm exec playwright test e2e/db.spec.ts`.
- **How the user tests it:** Click "Live database", enter a connection string → pick a table → profile appears → ask questions.

### Phase 5 — Exportable cleaned/filtered datasets + richer output

- **Goal:** Export the result of a question (or a cleaned/filtered view) as a downloadable file, plus richer answer output.
- **Capabilities:** (1) export computed result as CSV; (2) apply + persist a cleaning/filtering step and export it; (3) richer answer formatting (tables, multi-chart).
- **Independent slices:** `backend` (deps: Phase 1 executor) owns export endpoints + tests in `src/`; `frontend` (deps: export API contract) wires the "Export dataset" stub + download UX.
- **Gate command:** `uv run pytest tests/test_export.py` + `cd frontend && pnpm build && pnpm exec playwright test e2e/export.spec.ts`.
- **How the user tests it:** After an answer, click "Export dataset" → a CSV of the computed/filtered result downloads.
