# Capability: Additional Data Sources (Google Sheets / JSON API)

## What It Does
Loads a dataset from a **public Google Sheet URL** or a **JSON-API endpoint** into the same in-memory dataframe store as a CSV upload, so it flows through the identical profile → ask → answer → session path (no separate analysis code path).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| Google Sheet share URL | str | `POST /api/datasets/from-google-sheet` `{url}` | one-of |
| JSON-API URL | str | `POST /api/datasets/from-json-api` `{url}` | one-of |
| `records_path` | str (dot-path) | `POST /api/datasets/from-json-api` `{records_path}` | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| `{session_id, dataset_id, profile}` | JSON (identical to `POST /api/datasets`) | frontend → same ProfileCard → QuestionBox → AnswerCard → sessions |
| in-memory dataframe | pandas.DataFrame | dataframe store (keyed by `dataset_id`) |
| derived title | str | `Session.title` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Google Sheets CSV export (`.../export?format=csv&gid=<gid>`) | plain HTTP `GET`, no auth | `FETCH_FAILED` 502 (network/timeout/non-200); `SHEET_NOT_ACCESSIBLE` 400 (HTML/login body) |
| User-supplied JSON endpoint | HTTP `GET` | `FETCH_FAILED` 502; `JSON_PARSE_FAILED` 400 (bad JSON); `NO_TABULAR_DATA` 400 |

## Business Rules
- **Public sheets only — no credential.** The user pastes a normal share URL (`https://docs.google.com/spreadsheets/d/<ID>/edit#gid=<GID>`). The server extracts `<ID>` and optional `<GID>` (default `0`), fetches the CSV-export URL, and parses with the **same** `pandas.read_csv` path as an upload. Requires the sheet shared as "anyone with the link can view". **PRIVATE / auth-gated sheets are OUT OF SCOPE** — the fetch returns Google's HTML login page instead of CSV → `SHEET_NOT_ACCESSIBLE` with a message telling the user to share it as "anyone with the link". No credential is stored in `.env`.
- **JSON normalization order:** (1) `records_path` given → resolve dot-path to array → `pd.DataFrame(records)`; (2) top-level array of objects → `pd.DataFrame`; (3) top-level object with a single array-valued key → use that array; (4) fall back to `pd.json_normalize(body)`. Small responses only (bounded by `AGENT_MAX_UPLOAD_MB`).
- **Shared convergence:** all three sources (CSV upload, Sheets, JSON) call the SAME "create session + build profile + store dataframe" logic. The response is byte-for-byte the response of `POST /api/datasets`, so every downstream (ask / replay / sessions) is unchanged.
- **Fetch safety:** each fetch times out at `AGENT_FETCH_TIMEOUT_S` (default 15s) and is size-capped at `AGENT_MAX_UPLOAD_MB`. Fetch-to-arbitrary-URL (SSRF) is accepted within the existing single-trusted-user trust boundary; no blocklist is built (see [../architecture.md](../architecture.md#trust-boundary-local-code-execution)).
- **Error taxonomy:** Sheets — `INVALID_SHEET_URL` 400, `SHEET_NOT_ACCESSIBLE` 400, `PARSE_FAILED` 400, `FETCH_FAILED` 502, `FILE_TOO_LARGE` 413. JSON — `INVALID_URL` 400, `JSON_PARSE_FAILED` 400, `NO_TABULAR_DATA` 400, `FETCH_FAILED` 502, `FILE_TOO_LARGE` 413. See [../api.md](../api.md).

## Success Criteria
- [ ] A valid public Google Sheet share URL yields `{session_id, dataset_id, profile}` with a correct row count / dtypes, and a subsequent `/ask` returns a numerically correct answer — identical to CSV.
- [ ] A Sheets URL with no extractable id → `INVALID_SHEET_URL` 400; a fetch returning HTML/login → `SHEET_NOT_ACCESSIBLE` 400.
- [ ] A JSON endpoint returning an array of objects, and one returning `{data:{items:[...]}}` with `records_path=data.items`, both produce the correct dataframe + profile.
- [ ] Invalid/malformed JSON URL → `INVALID_URL`; non-JSON body → `JSON_PARSE_FAILED`; no resolvable array → `NO_TABULAR_DATA`.
- [ ] A fetch exceeding `AGENT_FETCH_TIMEOUT_S` → `FETCH_FAILED` 502; fetched bytes over `AGENT_MAX_UPLOAD_MB` → `FILE_TOO_LARGE` 413.
- [ ] The source picker replaces the Phase-1 "Connect Google Sheets" / "Connect JSON API" stub buttons with real forms; a loaded source drives the same ProfileCard/QuestionBox/AnswerCard as CSV.
