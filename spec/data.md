# Data — DealScout

DealScout is stateless with respect to the user: no history, preferences, or conversation are persisted for reuse. The database stores only the record of each in-flight/completed research run and its ranked deals, so the UI can poll progress and render results. Rows are not read across runs to influence future answers.

## Entities

### Run (`runs` table — extends the skeleton `RunRow`)

| Field | Type | Notes |
|-------|------|-------|
| `id` | str (UUID) | primary key |
| `query_type` | str | `"name"` (P1) \| `"url"` \| `"category"` (P2) |
| `query_text` | str | the product name / URL / category the user entered |
| `status` | str | `pending` \| `running` \| `needs_input` (P2) \| `completed` \| `failed` |
| `progress_step` | str \| null | `queued`\|`searching`\|`reviewing`\|`ranking`\|`assessing`\|`done` — drives the progress bar |
| `clarifying_question` | str \| null | set when `status=needs_input` (P2) |
| `prompt_tokens` | int | accumulated prompt tokens for the run |
| `completion_tokens` | int | accumulated completion tokens for the run |
| `cost_inr` | float \| null | estimated INR cost for the run |
| `error_message` | str \| null | set when `status=failed` |
| `created_at` | timestamp | |
| `updated_at` | timestamp | bumped as the run progresses |

> The skeleton's `input_text`/`output_text` columns are repurposed/removed: `query_text` replaces `input_text`; the ranked result lives in the `deals` table, not a text column.

### Deal (`deals` table — new)

| Field | Type | Notes |
|-------|------|-------|
| `id` | str (UUID) | primary key |
| `run_id` | str (FK → runs.id) | owning run |
| `rank` | int | 1..5 |
| `site` | str | e.g. "Amazon.in", "Flipkart" |
| `price_inr` | float | listed price in INR |
| `reason` | str | one-line reason why ranked here |
| `quality_label` | str \| null | (P2) e.g. "genuine_discount" \| "wait" \| "unknown" |
| `quality_reason` | str \| null | (P2) one-line justification |
| `source_url` | str \| null | grounded listing URL when available |
| `created_at` | timestamp | |

## Relationships

- One `Run` has many `Deal` rows (0–5). Deals are created by the `finalize` node.

## Lifecycle

1. `POST /runs` → `Run` created `status=running`, `progress_step=queued`.
2. Graph updates `progress_step` and token counts as `research`/`rank`/`deal_quality` execute.
3. (P2) If ambiguous → `status=needs_input` + `clarifying_question`; `POST /runs/{id}/answer` resumes.
4. `finalize` writes `Deal` rows + `cost_inr`, sets `status=completed`.
5. On fatal error → `status=failed` + `error_message`.
6. Rows persist for the session but are never read to influence another run (statelessness).
