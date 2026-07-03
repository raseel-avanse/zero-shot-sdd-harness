# Capability: Per-Question Transparency (Shown Code + Tokens + Step Status + Query Log)

## What It Does
Surfaces how each answer was produced — the executed pandas code, live step-status while working, and the per-question token count — and appends every query/answer pair to a durable log file (and the `runs` table).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| step events | object[] | Emitted by graph nodes during a run | yes |
| executed_code | string | [ask-question](ask-question.md) | yes |
| token_usage | object | LLM client usage metadata | yes |
| question / answer | string / string | Ask flow | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| step_trace | object[] (`step`, `status`, `attempt`) | Live step-status UI |
| executed_code | string | Collapsible code view |
| token_usage | object | Token badge |
| log line | JSON line | `AGENT_QUERY_LOG_PATH` (default `data/queries.log`) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | Append JSON line to query log | Log the failure via structlog; never fail the request |

## Business Rules
- Step statuses are emitted in order: `profiling` (reused from upload) → `writing_code` → `running_code` (repeated per attempt) → `synthesizing`. Each carries a status (`running`/`done`/`retry`/`error`).
- Executed code shown is the FINAL successful code (or the last attempted code if all failed).
- Token count is the true usage reported by the Gemini SDK for that question (sum across attempts).
- The query log file is append-only JSON lines: `{ts, dataset_id, question, answer, token_total, attempts, ok}`. This is separate from and complementary to the `runs` DB row.

## Success Criteria
- [ ] After asking a question, the query log file contains a new JSON line with the question, answer, and token total.
- [ ] The API response `step_trace` reflects at least one `running_code` entry and a final `synthesizing` entry.
- [ ] The `token_usage.total` shown equals the sum of usage across all LLM calls for that question.
