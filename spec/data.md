# Data Model

---

## Storage Technology

SQLite (`AGENT_DATABASE_URL=sqlite:///./data/agent.db`) via SQLAlchemy 2.0 + Alembic. Single-user local tool; SQLite is sufficient and is the fixed stack choice. Uploaded dataframes are held **in-process, not in the DB** (see [architecture.md](architecture.md#trust-boundary-local-code-execution)). Query/answer pairs are ALSO appended to an append-only JSON-lines **query log file** (`AGENT_QUERY_LOG_PATH`, default `data/queries.log`), complementary to the `runs` table.

## Entities

### Entity: Session (Phase 2)
One conversation against a loaded dataset. Created on the first upload (a new upload starts a new session by default). Every question asked against that session's dataset appends a Turn (a `runs` row). Persisted in SQLite so history survives page reload and process restart.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (pk, uuid) | yes | Session id |
| title | str | no | Human label (default derived from filename/first question) |
| dataset_id | str | yes | The **most recent** in-memory dataframe key this session points at |
| profile_snapshot | JSON | yes | Snapshot of the dataset `profile` (columns[], row_count, dq_flags[]) captured at upload, so history renders column context **even after the in-memory dataframe is evicted** |
| created_at | datetime | yes | Session start |
| updated_at | datetime | yes | Last activity (last upload or ask) |

A **Turn** is a `runs` row (see below); a session's history is its runs ordered by `created_at`. The Session row persists indefinitely, but the in-memory dataframe keyed by `dataset_id` may be **gone after a process restart or LRU eviction** — history still renders from `profile_snapshot`, but asking new questions requires a re-upload (see [api.md](api.md)).

### Entity: Run (a Turn)
One row per question asked (one agent run). This is the persistent query log in the DB. Each run is a Turn belonging to a Session.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (pk) | yes | Primary key |
| session_id | str (fk → Session.id) | yes | Session this turn belongs to (Phase 2; FK added by migration) |
| dataset_id | str | yes | In-memory dataframe key the question ran against |
| question | text | yes | The plain-English question |
| answer | text | no | Final answer + method note (null if failed) |
| method_note | text | no | How the answer was derived |
| executed_code | text | no | Final pandas code that ran (or last attempted) |
| result_repr | text | no | Stringified computed result |
| chart_spec | JSON | no | Chart spec, null if none |
| assumptions | JSON | no | List of flagged assumptions |
| attempts | int | yes | Number of code-execution attempts |
| used_fallback | bool | yes | True if reason-over-sample fallback was used |
| token_prompt | int | yes | Prompt tokens (summed across LLM calls) |
| token_completion | int | yes | Completion tokens |
| token_total | int | yes | Total tokens for this question |
| status | str | yes | `completed` / `failed` |
| error_message | text | no | Set when status = failed |
| created_at | datetime | yes | Run start |
| completed_at | datetime | no | Run end |

> **Phase 3 (no new tables):** datasets loaded from a Google Sheet or a JSON-API endpoint are stored in the **same** in-memory dataframe store and produce the **same** `Session` (its `title` reflects the source, e.g. "Google Sheet abc123" or the JSON URL) + `runs` turns as a CSV. `profile_snapshot` is captured identically at ingest. There is no source-type column; the source is only reflected in the derived title.

### Entity: DatasetProfile (in-memory only, not persisted)
Held in the in-process dataframe registry keyed by `dataset_id`; documented here for coherence, not a DB table.

| Field | Type | Description |
|-------|------|-------------|
| dataset_id | str | uuid key |
| dataframe | pandas.DataFrame | The loaded data (in-memory) |
| profile | dict | columns[], row_count, dq_flags[] (see [upload-and-profile.md](capabilities/upload-and-profile.md)) |
| created_at | datetime | Upload time |

### Relationships

`Run.dataset_id` references the in-memory `DatasetProfile.dataset_id`. No FK (the profile is not a DB table). One dataset → many runs. **`Run.session_id` → `Session.id` (FK, Phase 2):** one Session → many Runs (Turns). `Session.dataset_id` tracks the session's current dataframe key; it is not an FK (the dataframe is in-memory only).

### Migration (Phase 2)

An Alembic migration adds the `sessions` table and a nullable-then-backfilled `runs.session_id` column with an FK to `sessions.id`. Existing Phase 1 rows may be left with `session_id = NULL` or backfilled into a synthetic legacy session — documented as acceptable for the single-user local log.

## Data Lifecycle

- **DatasetProfile:** created on upload, lives in-process, evicted on process restart or when a configurable max number of datasets is exceeded (LRU). Not persisted.
- **Session (Phase 2):** created on first upload, `updated_at` bumped on each ask/upload, retained indefinitely. The session row survives restarts; its in-memory dataframe (keyed by `dataset_id`) does NOT — after eviction the session shows history but needs a re-upload to answer new questions.
- **Run (Turn):** created at question start, updated at finalize/error, retained indefinitely (single-user local log).
- **Query log file:** append-only, never rotated by the app (user manages).

## Sensitive Data

The uploaded dataset may contain the user's own PII; it stays in-process and in the local SQLite/log only. No data leaves the machine except the profile + a small sample sent to Gemini for code-writing (documented trade-off — the user controls what they upload). No auth/secrets stored beyond the Gemini API key in `.env`.
