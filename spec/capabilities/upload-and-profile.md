# Capability: Upload & Auto-Profile Dataset

## What It Does
Accepts a small tabular file upload, loads it into an in-memory pandas dataframe, and returns an auto-generated profile (columns, inferred types, row count, and obvious data-quality flags).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | multipart file (CSV, few MB) | Browser upload | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset_id | string (uuid) | API response + in-memory store key |
| profile | object (`columns[]`, `row_count`, `dq_flags[]`) | API response → profile card UI |

Profile shape: each column entry is `{name, dtype, non_null, null_count, sample_values[]}`; `dq_flags` is a list of strings like `"column 'age' has 12 nulls (4%)"`, `"column 'id' has 8 duplicate values"`, `"column 'date' parsed as string, may be a date"`.

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas (local) | `read_csv` + profiling | Return `api_error("PARSE_FAILED", detail)` — no LLM call |

## Business Rules
- Files above a configurable size cap (`AGENT_MAX_UPLOAD_MB`, default 10) are rejected before parsing.
- Only CSV is accepted in Phase 1; other extensions rejected with a clear message. (Google Sheets / JSON-API / live DB are later phases — labelled stubs in the UI.)
- Dataframe is held **in-process** keyed by `dataset_id`; it is not persisted to disk beyond the uploaded temp file. Trust boundary documented in [architecture.md](../architecture.md#trust-boundary-local-code-execution).
- Profiling is pure pandas — no LLM tokens consumed.

## Success Criteria
- [ ] Uploading a valid CSV returns HTTP 200 with `row_count` equal to the true number of data rows.
- [ ] Each column reports the correct pandas dtype and null count.
- [ ] A CSV with a known null-heavy column produces a `dq_flags` entry naming that column.
- [ ] Uploading a non-CSV or oversized file returns `api_error` with a readable message (not a 500 stack trace).
