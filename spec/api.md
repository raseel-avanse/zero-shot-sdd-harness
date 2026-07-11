# API — DealScout

REST API served by FastAPI on `:8001`. Every route returns the envelope `{"data": ..., "error": null}` (via `ok()`) or raises `api_error()`. The statically-exported UI is served at `:8001/app/` (single origin — no CORS).

## Endpoints

### `POST /runs` — start a research run
Starts a background research run and returns immediately (non-blocking, so the UI can poll for progress).

Request:
```json
{ "query_type": "name", "query_text": "Sony WH-1000XM5 headphones" }
```
- `query_type`: `"name"` (P1); `"url"` | `"category"` (P2). Defaults to `"name"` if omitted.
- `query_text`: required, non-empty.

Response (`200`):
```json
{ "data": { "run_id": "…", "status": "running" }, "error": null }
```
Errors: `400 VALIDATION` (empty `query_text`).

### `GET /runs/{run_id}` — poll status + result
Response while running (`200`):
```json
{ "data": { "run_id": "…", "status": "running", "progress_step": "searching",
            "clarifying_question": null, "deals": [], "prompt_tokens": 0,
            "completion_tokens": 0, "cost_inr": null, "error": null }, "error": null }
```
Response when completed (`200`):
```json
{ "data": { "run_id": "…", "status": "completed", "progress_step": "done",
            "deals": [ { "rank": 1, "site": "Amazon.in", "price_inr": 24990,
                         "reason": "Lowest verified price with 4.5★ over 12k reviews",
                         "quality_label": null, "quality_reason": null,
                         "source_url": "https://www.amazon.in/…" } ],
            "prompt_tokens": 5120, "completion_tokens": 890, "cost_inr": 1.42,
            "clarifying_question": null, "error": null }, "error": null }
```
- `status=needs_input` (P2): `clarifying_question` is populated, `deals` empty.
- `status=failed`: `error` holds a plain-language message.
- Errors: `404 NOT_FOUND` (unknown `run_id`).

### `POST /runs/{run_id}/answer` — resume a clarify pause (P2)
Request: `{ "answer": "Around ₹25000, over-ear, for travel" }`
Resumes a `needs_input` run by re-entering the graph with `clarify_answer` set; returns `{ "data": { "run_id": "…", "status": "running" }, "error": null }`. Errors: `404 NOT_FOUND`, `409 CONFLICT` (run not in `needs_input`).

### `GET /health` — liveness (skeleton, unchanged)

## Notes
- The `deals` array is empty until `status=completed`; the UI renders the progress bar from `progress_step` while `running`.
- Token/cost fields are `0`/`null` until `finalize` populates them.
- No pagination/auth — single-user local tool.
