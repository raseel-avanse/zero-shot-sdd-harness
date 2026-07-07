# API

---

## API Style
REST over FastAPI, served at `http://localhost:8001` (uvicorn `api:app`). All JSON responses use the `ok(data)` envelope `{"data": ..., "error": null}`; errors raise `api_error(code, message, status)` → `{"detail": {"code","message"}}`. Streaming uses Server-Sent Events (SSE) — compatible with the Next.js static-export frontend served from `/app` on the same origin (no CORS). Phase markers: [P1] Phase 1, [P2]/[P3] later.

## Endpoints / Commands

### `POST /engagements` [P1]
**Purpose:** Create an engagement + its scope record (the scope form) atomically.
**Request:**
```json
{
  "name": "string",
  "target_type": "repo",
  "target_ref": "/abs/path/to/repo",
  "authorized_targets": ["/abs/path/to/repo"],
  "rules_of_engagement": "string",
  "authorized_by": "string",
  "non_destructive_only": true
}
```
**Response:** `ok({ "engagement_id": "uuid", "status": "draft" })`
**Errors:** 400 missing/invalid fields; 400 `target_type=live_app` ("not yet available" in P1); 500 DB write failure.

### `GET /engagements` [P1]
**Purpose:** List engagements. **Response:** `ok([{engagement_id, name, target_type, status, created_at}])`.

### `GET /engagements/{id}` [P1]
**Purpose:** Fetch one engagement + its scope record. **Response:** `ok({engagement, scope_record})`. **Errors:** 404.

### `POST /engagements/{id}/runs` [P1]
**Purpose:** Start an assessment run (executes in a background task). Enforces scope before running.
**Request:** `{}` (uses engagement's target + scope; optional `step_budget` override).
**Response:** `ok({ "run_id": "uuid", "status": "pending" })`.
**Errors:** 404 engagement; 409 run already in progress for engagement; 422 scope violation surfaced synchronously if target not in allowlist.

### `GET /runs/{id}` [P1]
**Purpose:** Run status snapshot incl. counters + cost.
**Response:** `ok({ run_id, status, current_phase, current_category, step_count, step_budget, prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, error_message })`. **Errors:** 404.

### `GET /runs/{id}/events` [P1]
**Purpose:** SSE stream of run progress + findings as validated. Emits event types: `progress` (phase/category/step/cost), `finding` (a finding card), `done` (final status), `error`. Server tails `assessment_runs` + `findings` from Postgres; client uses `EventSource`. Closes on `done`/`error`.

### `GET /engagements/{id}/findings` [P1]
**Purpose:** List all findings for an engagement (post-run canonical view — identical to streamed set).
**Response:** `ok([{ id, category, title, severity_label, cvss_score, location, description, evidence, confidence, status, remediation, suggested_patch, created_at }])`.

### `GET /runs/{id}/cost` [P1]
**Purpose:** Token + cost breakdown for a run. **Response:** `ok({ prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, model_rates })`.

### `POST /engagements/{id}/chat` [P2]
Interactive chat turn with conversation memory. Request `{ "message": "string" }` → `ok({ reply, turn_id })`.

### `POST /findings/{id}/retest` [P2]
Re-run validation for one finding → `ok({ finding_id, confidence, status })`.

### `PATCH /findings/{id}` [P3]
Update finding status. Request `{ "status": "validated|remediated|false_positive" }` → `ok({finding})`.

### `GET /engagements/{id}/export?format=md|pdf|json` [P3]
Export the engagement dossier as a file download.

## Authentication
Phase 1: none — single-user, localhost, single origin. Auth is out of scope for the MVP (see roadmap out-of-scope).
