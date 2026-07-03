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

**Response (`ok`):**
```json
{ "dataset_id": "uuid",
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

### `POST /api/datasets/{dataset_id}/ask`
**Purpose:** Ask a question against a loaded dataset. Drives the agent graph. See [ask-question.md](capabilities/ask-question.md).

**Request:**
```json
{ "question": "What is the average revenue per region?" }
```

**Response (`ok`) — the pinned answer-card contract (frontend builds against this):**
```json
{ "run_id": 1,
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
| 404 `DATASET_NOT_FOUND` | `dataset_id` not in the in-memory store (e.g. after restart) |
| 422 `EMPTY_QUESTION` | Blank question |
| 502 `LLM_UNAVAILABLE` | Gemini API failed after retries |
| 500 `RUN_FAILED` | Graph reached `handle_error` |

### `GET /api/health`
**Purpose:** Liveness. **Response:** `ok({"status": "healthy"})`.

## Authentication

None. Single trusted local user — see the trust boundary in [architecture.md](architecture.md#trust-boundary-local-code-execution). The service must not be exposed publicly.
