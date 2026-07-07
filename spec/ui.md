# UI

---

## UI Type
Web dashboard — Next.js 15 (App Router) static export in `frontend/`, built with `cd frontend && pnpm build` → `frontend/out/`, mounted by FastAPI at `/app` (single origin `http://localhost:8001/app/`). Repurposes the boilerplate `frontend/src/app/page.tsx`. React 19 + Tailwind. Findings stream via `EventSource` to `GET /runs/{id}/events`.

> **Assumed:** Product name "Sentinel" shown in the header; dark security-console visual tone.

## Views / Screens

### Screen: Engagements List (`/app`) [P1 real]
**Purpose:** Landing — see engagements and start a new one.
**Key elements:** list of engagement cards (name, target_type, status); "New Engagement" button.
**Actions:** open an engagement; create new.

### Screen: New Engagement / Scope Form [P1 real]
**Purpose:** Capture authorized target + rules-of-engagement BEFORE any assessment.
**Key elements:** name; target_type selector (only `repo` enabled — `live_app` visibly disabled with a "coming soon" badge); target_ref (repo path); authorized_targets (allowlist, add/remove rows); rules_of_engagement textarea; authorized_by; non_destructive_only toggle (default on).
**Actions:** Submit → `POST /engagements`. Validation errors shown inline.

### Screen: Run View [P1 real]
**Purpose:** Launch and watch an assessment stream.
**Key elements:**
- "Start Assessment" button → `POST /engagements/{id}/runs`.
- **Step counter** `step_count / step_budget` + **current phase** + **current category** (live from SSE `progress`).
- **Token/cost panel** — prompt/completion/total tokens + estimated cost USD (live).
- **Finding cards list** — streams in as findings validate: severity badge + CVSS, category, `file:line` location, evidence/PoC block, remediation, and a suggested patch shown as a diff. Confidence badge (confirmed/tentative/unconfirmed).
**Actions:** start run; watch stream; a finished run's findings load from `GET /engagements/{id}/findings`.

### Screen: Labelled Stubs [P1 non-functional, clearly marked]
Rendered but visibly tagged "Coming soon — not yet functional" so they read as roadmap, never as bugs:
- **Live-app active probing** toggle in scope form (disabled). [→ P2]
- **Interactive chat** panel on the engagement (disabled input, placeholder). [→ P2]
- **Re-test after fix** button on each finding card (disabled). [→ P2]
- **Export dossier (MD/PDF/JSON)** button (disabled). [→ P3]
- **Finding status controls** (new/validated/remediated/false-positive) shown read-only. [→ P3]
- **Next-probe suggestions** empty panel with "coming soon". [→ P3]

## Error States
- Network/API errors: red banner with the `detail.message`.
- Scope violation on run start: prominent "Target outside authorized scope — run refused" message.
- SSE disconnect: "Stream interrupted — reconnecting…"; on `error` event show run error and stop.
- Empty states: "No engagements yet", "No findings yet — start an assessment".

## Tech Stack
Next.js 15 + React 19 + Tailwind CSS, static export (`output: 'export'`), served under `/app` by FastAPI. E2E: Playwright in `frontend/tests/e2e/`.
