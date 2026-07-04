# Build Status — Data Analyst Agent

_Last updated: 2026-07-04_

## Summary

A single-user, browser-based **Data Analyst Agent**: upload/connect a dataset, ask plain-English
questions, and get trustworthy answers backed by real pandas code (run locally, self-correcting),
with charts, shown work, token counts, and persisted sessions.

- **Stack:** Python + FastAPI + LangGraph + SQLite (backend), Next.js (frontend)
- **LLM:** Gemini `gemini-2.5-flash`
- **Branch:** `feature/data-analyst-agent-v0.1-build` → PR #1 (base `main`)
- **HEAD:** `463d389` (Phase 3)
- **Working tree:** clean

## Phases

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Upload CSV → ask → shown-work answer (pandas codegen + local exec + self-correct), chart, tokens, step-status, query log | ✅ Done, tested-good, pushed |
| 2 | Persisted multi-question sessions (DB history survives reload, session-scoped context for follow-ups, session list+replay) | ✅ Done, tested-good, pushed |
| 3 | Additional data sources — load from a public Google Sheet URL or a JSON-API endpoint; real source-picker forms | ✅ Done, tested-good, pushed |
| 4 | **Live database connection** — connect a read-only SQL DB, browse tables, load a table/query result as the dataset | ⏳ **Not started** (next up) |
| 5 | Export dataset — download a cleaned/filtered dataset or report | 🔲 Planned (still stubbed in UI) |

Testing policy (standing user request): keep the gate lean — only the ~4 real-Gemini floor tests
run live; all plumbing runs against stubs/fakes with no network; a single consolidated Playwright
golden-path spec.

## Where to resume (Phase 4)

- Roadmap for Phase 4 is in `spec/roadmap.md`; flesh out the Phase 4 capability spec via spec-writer
  if incomplete before building.
- Goal: wire the existing "Live database" stub in the source picker into a real form; a loaded
  table/query flows through the SAME profile → ask → answer → session path as CSV/Sheets/JSON.
- Guardrails: enforce read-only (SELECT only), cap rows into memory, never log credentials.
- Suggested DB support: SQLite file + a Postgres/MySQL SQLAlchemy URL. Tests use a local/ephemeral
  SQLite fixture (no external server, no live LLM).

## How to run locally (from project root)

```
cd frontend && pnpm build && cd ..
uv run alembic upgrade head
uv run python -m src
```
Then open http://localhost:8001/app/ (trailing slash — served under the `/app` base path).

## Environment notes

- `.env` holds a real `AGENT_GEMINI_API_KEY`.
- `gh` is **not authenticated** in the build environment, so the PR *body* on GitHub has not been
  auto-updated — commits/pushes to the branch are the durable record. Run `gh auth login` to enable
  PR-body updates.

## Still-stubbed in the UI (intentional, not bugs)

- **Live database** (Phase 4)
- **Export dataset** (Phase 5)
