# Data Model

---

## Storage Technology

PostgreSQL 16 (real, Dockerized — container `sec-agent-pg`, host port 5433) via SQLAlchemy 2.0 ORM + Alembic migrations. Driver: `psycopg` (psycopg3), URL `postgresql+psycopg://…`. NEVER SQLite — gates run against this Postgres. The existing `runs` table from the boilerplate is superseded by `assessment_runs` (the boilerplate `RunRow` is repurposed/replaced in the Phase 1 DB slice).

> **Assumed:** `id` columns are UUID-as-Text (matching the boilerplate `_uuid()` convention) rather than serial ints, for consistency with the existing baseline.

## Entities

### Entity: Engagement
A scoped security assessment against one target.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key |
| name | Text | yes | Human label |
| target_type | Text enum `repo`\|`live_app` | yes | Phase 1: `repo` only |
| target_ref | Text | yes | Local repo path (later: base URL) |
| status | Text enum `draft`\|`active`\|`completed`\|`archived` | yes | Default `draft` |
| created_at / updated_at | timestamptz | yes | Lifecycle timestamps |

### Entity: ScopeRecord
The authorization record; 1:1 with an engagement. Persists bound to the engagement.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key |
| engagement_id | Text FK → engagements.id | yes | Owning engagement (unique) |
| authorized_targets | JSONB (string[]) | yes | In-code allowlist: absolute repo paths / hosts |
| rules_of_engagement | Text | yes | Free-text ROE |
| authorized_by | Text | yes | Who authorized |
| non_destructive_only | bool | yes | Default true; must be true for live_app |
| created_at | timestamptz | yes | |

### Entity: AssessmentRun
One assessment run over the engagement's target. Holds progress + token/cost.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key |
| engagement_id | Text FK → engagements.id | yes | Owning engagement |
| status | Text enum `pending`\|`running`\|`completed`\|`failed` | yes | Default `pending` |
| current_phase | Text | no | recon\|prioritize\|hunt\|validate\|report |
| current_category | Text | no | Active vuln category during hunt |
| step_count | int | yes | Steps consumed (default 0) |
| step_budget | int | yes | Bounded budget for the run |
| prompt_tokens | int | yes | Accumulated (default 0) |
| completion_tokens | int | yes | Accumulated (default 0) |
| total_tokens | int | yes | Accumulated (default 0) |
| estimated_cost_usd | numeric(10,6) | yes | Computed from tokens × model rate |
| error_message | Text | no | Set on failure |
| started_at / completed_at | timestamptz | no | Run window |

### Entity: Finding
One validated (or unconfirmed) vulnerability finding. Accumulates and persists per engagement.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key |
| engagement_id | Text FK → engagements.id | yes | Owning engagement |
| run_id | Text FK → assessment_runs.id | yes | Producing run |
| category | Text enum `injection`\|`broken_auth`\|`secrets_misconfig`\|`vuln_deps` | yes | Vuln class |
| title | Text | yes | Short label |
| severity_label | Text enum `critical`\|`high`\|`medium`\|`low`\|`info` | yes | |
| cvss_score | numeric(3,1) | no | 0.0–10.0 CVSS-ish |
| location | Text | yes | file:line (later: endpoint) |
| description | Text | yes | What/why |
| evidence | Text | yes | The exact validation step / PoC output shown (bounded excerpts only) |
| confidence | Text enum `confirmed`\|`tentative`\|`unconfirmed` | yes | |
| status | Text enum `new`\|`validated`\|`remediated`\|`false_positive` | yes | Default `new` |
| remediation | Text | yes | Remediation guidance |
| suggested_patch | Text | no | Unified-diff patch suggestion |
| pattern_ref | Text (uuid) | no | Links same-pattern occurrences (Phase 3) |
| created_at / updated_at | timestamptz | yes | |

### Entity: ChatTurn (Phase 2)
Conversation memory for interactive chat over an engagement.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key |
| engagement_id | Text FK → engagements.id | yes | Owning engagement |
| role | Text enum `user`\|`assistant` | yes | Turn role |
| content | Text | yes | Turn text |
| created_at | timestamptz | yes | Ordering |

### Relationships
- Engagement 1—1 ScopeRecord.
- Engagement 1—N AssessmentRun.
- Engagement 1—N Finding; AssessmentRun 1—N Finding.
- Engagement 1—N ChatTurn (Phase 2).

## Data Lifecycle
- Engagement + ScopeRecord created together at scope-form submit.
- AssessmentRun created on run start; counters updated live during the run; finalized at report/handle_error.
- Findings inserted the moment each is validated (streamable); status updated by user (Phase 3) or re-test (Phase 2).
- Step-level agent detail is EPHEMERAL (in LangGraph state / logs / LangSmith), not persisted as rows.

## Sensitive Data
- **RAW SOURCE IS NOT PERSISTED.** Only findings/metadata and bounded code excerpts inside `evidence` are stored. Whole source files never leave the box and are never written to Postgres. Code excerpts MAY be sent to Gemini for analysis.
- Scope records may name internal hosts/paths — treated as engagement-confidential; not exported outside the dossier.
