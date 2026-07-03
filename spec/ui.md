# UI

---

## UI Type

Single-page web app (Next.js 15 static export, React 19, served at `/app`). One screen; the running conversation stays in view.

## Views / Screens

### Screen: Analyst Workspace (single page)

**Purpose:** Upload a dataset, see its profile, ask questions, read answers with full shown-work, and keep the Q&A history visible.

**Layout (top to bottom):**

1. **Upload zone** (real) — drag/drop or pick a CSV → `POST /api/datasets`. Shows filename + size; rejects non-CSV / oversized with a readable message.
2. **Dataset profile card** (real) — after upload: row count, per-column name/dtype/null-count, and data-quality flags. Renders from the `profile` in the upload response.
3. **Question box** (real) — text input + Ask button → `POST /api/datasets/{id}/ask`. Disabled until a dataset is loaded.
4. **Live step-status** (real) — while a question runs, shows ordered steps (profiling → writing code → running code [with attempt count] → synthesizing) from `step_trace`.
5. **Answer card** (real) — for each answered question, renders the pinned contract from [api.md](api.md):
   - Key numbers + answer text
   - Method note ("how it got there")
   - Assumptions block (only when non-empty; visually flagged as best-guess)
   - Collapsible "Show code" view of `executed_code`
   - Auto-chart (rendered from `chart_spec` when not null; Recharts)
   - Token count badge (`token_usage.total`) and attempt count
6. **Conversation history** (real, client-held) — answered questions stack in view, newest at top/bottom; each is an answer card. Phase 1 history is in the browser only.

**Labelled NON-FUNCTIONAL stubs (must never read as bugs — disabled + "Coming soon" badge):**
- **More data sources** panel: "Connect Google Sheets", "Connect JSON API" buttons — disabled, labelled *Coming soon (Phase 3)*.
- **Live database** button — disabled, labelled *Coming soon (Phase 4)*.
- **Export cleaned/filtered dataset** button on the answer card — disabled, labelled *Coming soon (Phase 5)*.

## Error States

- Upload errors (parse / type / size): inline message on the upload zone.
- Ask errors (`DATASET_NOT_FOUND`, `LLM_UNAVAILABLE`, `RUN_FAILED`): red inline banner on the answer card with the `error.detail`; the question stays in history marked failed.
- Loading: the live step-status component IS the loading state for a question; a spinner on the upload zone during profiling.

## Tech Stack

Next.js 15 + React 19 + Tailwind, static export → `frontend/out/`, mounted at `/app`. Charts via Recharts. E2E: Playwright in `frontend/tests/e2e/`.
