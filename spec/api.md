# API

---

## API Style

REST over HTTP (FastAPI), JSON. Every response uses the envelope:
- Success: `ok(data)` → `{"ok": true, "data": {...}}`
- Error: `api_error(code, detail)` → `{"ok": false, "error": {"code": "STRING", "detail": "..."}}`

Frontend static export is mounted at `/app`; API is under `/api`.

## Endpoints

### `POST /api/datasets`
**Purpose:** Upload a CSV, profile it, hold the dataframe in-process. See [upload-and-profile.md](capabilities/upload-and-profile.md).

**Request:** `multipart/form-data` with field `file` (CSV).

**Phase 2:** each upload also **creates a new session** by default and attaches this dataset to it. The response gains `session_id`. The session's `profile_snapshot` is captured here so history can render after the dataframe is evicted (see [data.md](data.md)).

**Response (`ok`):**
```json
{ "session_id": "uuid",
  "dataset_id": "uuid",
  "profile": {
    "row_count": 1234,
    "columns": [{"name": "age", "dtype": "int64", "non_null": 1200, "null_count": 34, "sample_values": [23, 45]}],
    "dq_flags": ["column 'age' has 34 nulls (3%)"]
  } }
```

**Error cases:**
| Status / code | Condition |
|--------|-----------|
| 400 `PARSE_FAILED` | File is not valid CSV |
| 400 `UNSUPPORTED_TYPE` | Non-CSV extension (Sheets/JSON/DB are later phases) |
| 413 `FILE_TOO_LARGE` | Exceeds `AGENT_MAX_UPLOAD_MB` |

### `POST /api/datasets/from-google-sheet` (Phase 3)
**Purpose:** Load a dataset from a **public** Google Sheets URL, profile it, hold the dataframe in-process — behaving **identically** to a CSV upload. See [data-sources.md](capabilities/data-sources.md).

**Request:** `application/json`
```json
{ "url": "https://docs.google.com/spreadsheets/d/<id>/edit#gid=<gid>" }
```
The server extracts the spreadsheet `<id>` (and `gid` if present, else `0`), builds the public CSV-export URL `https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=<gid>`, does a plain HTTP `GET` (**no API key, no OAuth**), and parses the body with the **same** `pandas.read_csv` path as `POST /api/datasets`. Works for sheets shared "anyone with the link can view". PRIVATE sheets are **out of scope**: an auth-gated sheet returns Google's HTML login page instead of CSV, which surfaces as `SHEET_NOT_ACCESSIBLE`.

**Response (`ok`):** **byte-for-byte the same shape** as `POST /api/datasets` — `{ "session_id", "dataset_id", "profile" }`, same profile shape, same session-creation-on-ingest (Phase 2 `create_session`) and `profile_snapshot` capture. `title` = a derived name (`"Google Sheet <short-id>"`). The resulting in-memory dataframe is indistinguishable from a CSV upload, so `/ask`, `/api/sessions`, and replay are **all unchanged**.

**Error cases:**
| Status / code | Condition |
|--------|-----------|
| 400 `INVALID_SHEET_URL` | `url` missing/blank, or not a parseable Google Sheets URL (no extractable spreadsheet id) |
| 400 `SHEET_NOT_ACCESSIBLE` | Fetch returned non-CSV (HTML/login page) — sheet is not shared publicly; error tells the user to share it as "anyone with the link" |
| 400 `PARSE_FAILED` | Fetched content is CSV-shaped but `pandas.read_csv` failed / yielded zero rows or columns |
| 502 `FETCH_FAILED` | Network error, timeout (`AGENT_FETCH_TIMEOUT_S`), or non-200 HTTP status |
| 413 `FILE_TOO_LARGE` | Fetched bytes exceed `AGENT_MAX_UPLOAD_MB` |

### `POST /api/datasets/from-json-api` (Phase 3)
**Purpose:** Load a dataset from a JSON-API endpoint, normalize it to a dataframe, profile it, hold it in-process — behaving **identically** to a CSV upload. See [data-sources.md](capabilities/data-sources.md).

**Request:** `application/json`
```json
{ "url": "https://api.example.com/records", "records_path": "data.items" }
```
- `url` — the HTTP(S) JSON endpoint to `GET`.
- `records_path` — optional dot-path (e.g. `"data.items"`) selecting the nested array of record objects. Normalization rules (see [data-sources.md](capabilities/data-sources.md)):
  1. If `records_path` is given, resolve it to the array and `pd.DataFrame(records)`.
  2. Else if the top-level JSON is an **array of objects** → `pd.DataFrame(records)`.
  3. Else if the top-level is an **object with a single array-valued key** → use that array.
  4. Else fall back to `pd.json_normalize(body)`.

**Response (`ok`):** **byte-for-byte the same shape** as `POST /api/datasets` — `{ "session_id", "dataset_id", "profile" }`, same session-creation-on-ingest and `profile_snapshot` capture. `title` = a derived name (the URL host/path). The dataframe is indistinguishable from a CSV upload, so `/ask`, `/api/sessions`, and replay are unchanged.

**Error cases:**
| Status / code | Condition |
|--------|-----------|
| 400 `INVALID_URL` | `url` missing/blank/malformed |
| 400 `JSON_PARSE_FAILED` | Response body is not valid JSON |
| 400 `NO_TABULAR_DATA` | Could not resolve an array of records / `json_normalize` failed / result has zero rows or columns |
| 502 `FETCH_FAILED` | Network error, timeout (`AGENT_FETCH_TIMEOUT_S`), or non-200 HTTP status |
| 413 `FILE_TOO_LARGE` | Fetched bytes exceed `AGENT_MAX_UPLOAD_MB` |

> **Trust boundary (noted, not built):** both endpoints fetch an arbitrary user-supplied URL server-side (an SSRF surface — a URL could point at localhost/metadata endpoints). Acceptable here **only** because this is a single-user, locally-run, non-exposed tool (same trust boundary as un-sandboxed code execution — see [architecture.md](architecture.md#trust-boundary-local-code-execution)). No SSRF allow-listing is built in Phase 3. Fetches are bounded by `AGENT_FETCH_TIMEOUT_S` (default 15s) and the `AGENT_MAX_UPLOAD_MB` size cap on the fetched bytes.

### `POST /api/datasets/{dataset_id}/ask`
**Purpose:** Ask a question against a loaded dataset. Drives the agent graph. See [ask-question.md](capabilities/ask-question.md).

**Request:**
```json
{ "question": "What is the average revenue per region?" }
```

**Phase 2:** the server resolves `dataset_id → session_id` and records this run as a **turn** of that session (bumps `Session.updated_at`). Prior turns of the session are injected as context so follow-ups resolve against them (see [agent.md § Memory & Context](agent.md#memory--context)). The answer-card shape is unchanged; the response gains `session_id`.

**Response (`ok`) — the pinned answer-card contract (frontend builds against this):**
```json
{ "run_id": 1,
  "session_id": "uuid",
  "answer": "Average revenue is highest in West ($4,210)...",
  "method_note": "Grouped by region and computed mean of revenue.",
  "executed_code": "result = df.groupby('region')['revenue'].mean()",
  "result_repr": "region\nWest    4210.0\n...",
  "assumptions": [],
  "chart_spec": { "type": "bar", "x": "region", "y": "revenue",
                  "series": [{"label": "avg revenue", "points": [{"x": "West", "y": 4210}]}],
                  "title": "Average revenue by region" },
  "token_usage": { "prompt": 812, "completion": 143, "total": 955 },
  "attempts": 1,
  "used_fallback": false,
  "step_trace": [
    {"step": "profiling", "status": "done", "attempt": 0},
    {"step": "writing_code", "status": "done", "attempt": 1},
    {"step": "running_code", "status": "done", "attempt": 1},
    {"step": "synthesizing", "status": "done", "attempt": 0}
  ] }
```
`chart_spec` is `null` when no chart fits. `assumptions` is `[]` when none. `used_fallback` is `true` when the reason-over-sample path was taken.

**Error cases:**
| Status / code | Condition |
|--------|-----------|
| 404 `DATASET_NOT_FOUND` | `dataset_id` not in the in-memory store (e.g. after restart/eviction) — the session's dataframe is gone; the frontend shows a "re-upload to continue this session" state (see [data.md](data.md)) |
| 422 `EMPTY_QUESTION` | Blank question |
| 502 `LLM_UNAVAILABLE` | Gemini API failed after retries |
| 500 `RUN_FAILED` | Graph reached `handle_error` |

### `GET /api/sessions` (Phase 2)
**Purpose:** List sessions, most recent first, for the history/session picker.

**Response (`ok`):** an array (envelope `data` is the list):
```json
[
  { "session_id": "uuid",
    "title": "sales_2024.csv",
    "dataset_id": "uuid",
    "profile_summary": { "row_count": 1234, "column_names": ["region", "revenue", "month"] },
    "turn_count": 3,
    "created_at": "2026-07-03T10:00:00Z",
    "updated_at": "2026-07-03T10:12:00Z",
    "dataframe_loaded": true }
]
```
`dataframe_loaded` reflects whether the in-memory dataframe for this session's `dataset_id` is still resident (`false` after a restart or LRU eviction → the UI shows "re-upload to continue"). `profile_summary` is derived from the session's `profile_snapshot`, so it renders even when `dataframe_loaded` is `false`.

### `GET /api/sessions/{session_id}` (Phase 2)
**Purpose:** Replay a session — the frontend loads this on page reload to restore the full history. This turn-array element shape is the pinned contract the History UI renders.

**Response (`ok`):**
```json
{ "session_id": "uuid",
  "title": "sales_2024.csv",
  "dataset_id": "uuid",
  "dataframe_loaded": false,
  "profile": {
    "row_count": 1234,
    "columns": [{"name": "age", "dtype": "int64", "non_null": 1200, "null_count": 34, "sample_values": [23, 45]}],
    "dq_flags": ["column 'age' has 34 nulls (3%)"]
  },
  "turns": [
    { "run_id": 1,
      "question": "What is the average revenue per region?",
      "created_at": "2026-07-03T10:05:00Z",
      "answer": "Average revenue is highest in West ($4,210)...",
      "method_note": "Grouped by region and computed mean of revenue.",
      "executed_code": "result = df.groupby('region')['revenue'].mean()",
      "result_repr": "region\nWest    4210.0\n...",
      "assumptions": [],
      "chart_spec": { "type": "bar", "x": "region", "y": "revenue",
                      "series": [{"label": "avg revenue", "points": [{"x": "West", "y": 4210}]}],
                      "title": "Average revenue by region" },
      "token_usage": { "prompt": 812, "completion": 143, "total": 955 },
      "attempts": 1,
      "used_fallback": false,
      "status": "completed" }
  ] }
```
Each element of `turns` carries `question`, `created_at`, `status`, plus **every Phase 1 answer-card key** (`run_id`, `answer`, `method_note`, `executed_code`, `result_repr`, `assumptions`, `chart_spec`, `token_usage`, `attempts`, `used_fallback`). `step_trace` is omitted from replay (it is live-run telemetry, not persisted per turn). `profile` comes from the session's `profile_snapshot`, so replay works even when `dataframe_loaded` is `false`; when `false`, the UI renders history and a "re-upload to continue this session" prompt.

**Error cases:**
| Status / code | Condition |
|--------|-----------|
| 404 `SESSION_NOT_FOUND` | `session_id` not in the `sessions` table |

### `GET /api/health`
**Purpose:** Liveness. **Response:** `ok({"status": "healthy"})`.

## Authentication

None. Single trusted local user — see the trust boundary in [architecture.md](architecture.md#trust-boundary-local-code-execution). The service must not be exposed publicly.
