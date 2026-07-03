# Zero Shot SDD Harness for Building Agents

Give it a one-line idea. Walk away with a working, tested, phased agent.

A lean, Claude-Code-native harness for building agentic software **spec-first**. One person with an idea and one API key can drive a real, production-shaped agent into existence — and a senior engineer opening the result finds a conventional, reviewable stack, not generated mush.

---

## The Spirit

Six convictions the whole repo is built around:

1. **Spec is the source of truth.** The spec is written before the code, always. When spec and code disagree, the spec wins and the code is fixed (`/zero-shot-sync`). Every AI session reads the same requirements instead of re-deriving them.
2. **Built for two audiences at once.** A non-coder drives it with a single sentence; a senior engineer inherits a clean FastAPI + LangGraph stack they can read, review, and own. Neither audience is an afterthought.
3. **Lean harness, not a framework.** `harness/` is engineering *mindfulness* — rules and patterns that keep every session consistent — deliberately Claude-Code-only and kept small. The product runtime stays provider-agnostic; the harness does not.
4. **Smallest first-time-right win, phase by phase.** Each phase ships the smallest increment a human can actually test, and it must work the *first* time they test it — real on the tested path, with clearly-labelled stubs for everything still to come. No rough edges on the path you're handed.
5. **A human gates every phase.** The build is autonomous *within* a phase and stops at each boundary for you to test the increment. You stay in control of what "done" means.
6. **Real LLM/API or it doesn't count.** Gates, tests, and evals run against the real model with keys from `.env`. A stubbed pass is not a pass.

---

## What This Is

A starting point for building AI agents spec-first. The repo ships with:

- A working **baseline agent** in `src/` (FastAPI + LangGraph + SQLite, provider-agnostic LLM — Anthropic or Gemini, `transform_text` as the capability slot) — tests pass out of the box
- A **spec template** in `spec/` covering roadmap, architecture, capabilities, data model, API, UI, and agent graph
- Three **zero-shot skills** (`/zero-shot-build`, `/zero-shot-fix`, `/zero-shot-sync`)
- A four-agent **team** — agent-builder orchestrates (plans, fans out, owns git/PR); spec-writer is the single design authority; code-generator implements one slice per instance (parallelised); qa-auditor reviews and gates
- Engineering rules and patterns in `harness/` so every Claude Code session is consistent
- **Human testing gate between phases** — autonomous within a phase, you test each increment before the next starts

---

## How to Use This

### Step 1 — Clone

```bash
git clone https://github.com/smallTechOrg/zero-shot-sdd-harness.git my-agent
cd my-agent
```

### Step 2 — Open in Claude Code

```bash
claude
```

### Step 3 — Build

```
/zero-shot-build An agent that monitors my Shopify store for low-inventory products and drafts restock emails to suppliers
```

One intake round (scope, stack, API keys → fill `.env`), then the agent builds phase by phase and stops at each boundary for you to test.

---

## What Happens (Intake → Phase by Phase)

```
Your idea
    ↓
INTAKE — scope, stack, LLM provider, constraints; fill .env with the required API key
    ↓
[spec-writer]  → Full spec: architecture + agent-graph + phased plan (self-reviewed)
    ↓
[agent-builder] → Feature branch + PR, scaffold
    ↓
per phase — all slices concurrently:
    [code-generator: slice-a]  ──→  [qa-auditor: slice-a]  ─┐
    [code-generator: slice-b]  ──→  [qa-auditor: slice-b]  ─┤→  commit + push
    [code-generator: slice-c]  ──→  [qa-auditor: slice-c]  ─┘
    ↓
HUMAN TESTING GATE — exact run commands + expected result; you confirm before next phase
    ↓
(issue → qa-auditor classifies SPEC-vs-CODE → code-generator fixes → re-gate)
    ↓
repeat per phase → SHIP
```

Phase 1 is the smallest first-time-right win — real on the tested path, with labelled stubs for everything coming later. Each later phase wires one more stub into real functionality.

---

## Repo Layout

```
src/                ← baseline agent (FastAPI + LangGraph + SQLite, Anthropic/Gemini)
  api/              ← FastAPI routers (create_app, health, runs)
  config/           ← Pydantic BaseSettings
  db/               ← SQLAlchemy models + session
  domain/           ← Pydantic request/response models
  graph/            ← LangGraph nodes, edges, state, runner  ← CAPABILITY SLOT
  llm/              ← LLM client + providers/ (anthropic, gemini)
  prompts/          ← prompt templates (.md)
  observability/
frontend/           ← Next.js static export (served by FastAPI at /app)
tests/
  unit/             ← passes with no API key
  integration/      ← requires real key in .env
spec/               ← your spec: roadmap, architecture, capabilities/, data, api, ui, agent
harness/
  rules/            ← ai-agents, git, secret-hygiene
  patterns/         ← spec-driven, phases, project-layout, tech-stack, code, test-driven, ui-ux, agentic-ai, engineering-practices
.claude/
  skills/           ← /zero-shot-build, /zero-shot-fix, /zero-shot-sync
  agents/           ← agent-builder, spec-writer, code-generator, qa-auditor
CLAUDE.md
pyproject.toml
alembic.ini        ← Alembic migrations (alembic/)
agent.py            ← verify setup (default); --run to start the server
.env.example
```

This build implements the **Data Analyst Agent**: upload a CSV, ask a plain-English
question, and get an answer computed by locally-executed, self-correcting pandas
(LangGraph graph in `src/graph/`, Gemini prompts in `src/prompts/`, in-memory
dataframe store + profiling in `src/domain/`).

---

## Running the Data Analyst Agent (Phase 1)

> All commands run from the repo root. Every Python command is `uv run`-prefixed.

```bash
cp .env.example .env
# edit .env: set your Gemini key — AGENT_GEMINI_API_KEY=<your key>
# (the provider is auto-detected from whichever key is set)
uv sync --extra dev

# 1. Apply DB migrations, then confirm a revision is applied:
uv run alembic upgrade head
uv run alembic current            # → shows the head revision id

# 2. (optional, for the UI) build the frontend static export:
cd frontend && pnpm build && cd ..

# 3. Start the server on port 8001:
uv run python -m src
```

Once running, open `http://localhost:8001/app` for the UI (when the frontend is built).

### API endpoints

| Method / path | What |
|---------------|------|
| `POST /api/datasets` | Upload a CSV (`multipart/form-data`, field `file`) → returns `{session_id, dataset_id, profile}`. Each upload starts a new **session** and snapshots the profile |
| `POST /api/datasets/{dataset_id}/ask` | Body `{"question": "..."}` → the answer-card contract (answer, method note, executed code, result, chart spec, token usage, attempts, step trace) plus `session_id`. Prior turns of the session are injected as context so follow-ups ("now break that down by region") resolve against them |
| `GET /api/sessions` | List sessions, most recent first: `{session_id, title, dataset_id, profile_summary, turn_count, created_at, updated_at, dataframe_loaded}` |
| `GET /api/sessions/{session_id}` | Replay a session: `{session_id, title, dataset_id, dataframe_loaded, profile, turns[]}` where each turn carries every answer-card key plus `question`, `created_at`, `status` |
| `GET /api/health` | Liveness → `{"ok": true, "data": {"status": "healthy"}}` |

Every response uses the envelope `{"ok": true, "data": {...}}` on success and
`{"ok": false, "error": {"code", "detail"}}` on error.

### Sessions & history (Phase 2)

Conversation history is persisted per session in SQLite, so it survives page
reload and process restart. A session's uploaded **dataframe is held in memory
only** — after a process restart or LRU eviction the dataframe is gone
(`dataframe_loaded: false` in `GET /api/sessions`): history still renders from the
stored `profile_snapshot`, but asking a new question against the evicted dataset
returns `DATASET_NOT_FOUND` (404) — re-upload the CSV to continue the session.
The agent injects the last `AGENT_HISTORY_TURNS` (default 3) completed turns
(question + method note + executed code, compact) into the `write_code` and
`synthesize` prompts so follow-ups resolve against prior turns.

### Tests

```bash
uv run pytest tests/unit          # no key needed
uv run pytest                     # full suite; integration tests use real Gemini via .env
```

### Environment variables

| Var | Default | Purpose |
|-----|---------|---------|
| `AGENT_DATABASE_URL` | `sqlite:///./data/agent.db` | SQLite DB path |
| `AGENT_GEMINI_API_KEY` | — | Gemini API key (provider auto-detected) |
| `AGENT_LLM_MODEL` | `gemini-2.5-flash` | Model id |
| `AGENT_MAX_UPLOAD_MB` | `10` | Reject uploads larger than this |
| `AGENT_MAX_CODE_ATTEMPTS` | `3` | Bounded self-correction retries |
| `AGENT_CODE_TIMEOUT_S` | `15` | Per-execution wall-clock timeout |
| `AGENT_QUERY_LOG_PATH` | `data/queries.log` | Append-only JSON-lines query log |
| `AGENT_MAX_DATASETS` | `16` | In-memory dataframe LRU cap |

---

## Rules AI Agents Follow

Full rules in `harness/rules/ai-agents.md`. Summary:

- Read the full spec before writing any code
- Never skip a phase; commit every logical unit
- Tests run against the real LLM/API using keys from `.env` — stubbed runs do not count as passing
- Each phase is tested by the human before the next phase starts
- The build record is git history + the PR + the per-phase test-handoffs

---

## FAQ

**What if I already have a stack in mind?**
State it in the idea: `/zero-shot-build [idea] — use Python + FastAPI + PostgreSQL`. Stack choices are binding.

**What if something breaks?**
Run `/zero-shot-fix [what's broken]` — qa-auditor classifies the problem (SPEC vs CODE), the right generator fixes it, qa-auditor re-gates.

**What if spec and code drift?**
Run `/zero-shot-sync` — qa-auditor classifies each divergence, generators fix, spec wins.
