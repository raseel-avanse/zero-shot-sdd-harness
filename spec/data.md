# Data Model

---

## Storage Technology

SQLite (`AGENT_DATABASE_URL=sqlite:///./data/agent.db`) via SQLAlchemy 2.0 + Alembic. Single-user local tool; SQLite is sufficient and is the fixed stack choice. Uploaded dataframes are held **in-process, not in the DB** (see [architecture.md](architecture.md#trust-boundary-local-code-execution)). Query/answer pairs are ALSO appended to an append-only JSON-lines **query log file** (`AGENT_QUERY_LOG_PATH`, default `data/queries.log`), complementary to the `runs` table.

## Entities

### Entity: Run
One row per question asked (one agent run). This is the persistent query log in the DB.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (pk) | yes | Primary key |
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

### Entity: DatasetProfile (in-memory only, not persisted)
Held in the in-process dataframe registry keyed by `dataset_id`; documented here for coherence, not a DB table.

| Field | Type | Description |
|-------|------|-------------|
| dataset_id | str | uuid key |
| dataframe | pandas.DataFrame | The loaded data (in-memory) |
| profile | dict | columns[], row_count, dq_flags[] (see [upload-and-profile.md](capabilities/upload-and-profile.md)) |
| created_at | datetime | Upload time |

### Relationships

`Run.dataset_id` references the in-memory `DatasetProfile.dataset_id`. No FK (the profile is not a DB table). One dataset → many runs.

## Data Lifecycle

- **DatasetProfile:** created on upload, lives in-process, evicted on process restart or when a configurable max number of datasets is exceeded (LRU). Not persisted.
- **Run:** created at question start, updated at finalize/error, retained indefinitely (single-user local log).
- **Query log file:** append-only, never rotated by the app (user manages).

## Sensitive Data

The uploaded dataset may contain the user's own PII; it stays in-process and in the local SQLite/log only. No data leaves the machine except the profile + a small sample sent to Gemini for code-writing (documented trade-off — the user controls what they upload). No auth/secrets stored beyond the Gemini API key in `.env`.
