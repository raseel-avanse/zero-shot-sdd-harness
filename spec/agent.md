# Agent

---

## Agent Architecture Pattern

**Chosen:** **Graph (LangGraph)** — the assessment is a bounded multi-step pipeline with a conditional hunt loop (recon → prioritize → hunt-per-category → validate → report), an early-exit on step budget, and a scope-gate entry node. A single loop cannot express the per-category branching + budget-bounded routing cleanly. Repurposes the wired boilerplate graph in `src/graph/` in place.

---

## LLM Provider & Model

Provider auto-detected as **Gemini** (google-genai) from `AGENT_GEMINI_API_KEY`. Per-node model tier keeps cost low (cost is a product goal); both env-configurable.

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| recon | Gemini | `gemini-3.1-flash` (`AGENT_LLM_MODEL_FAST`) | cheap summarization of inventory |
| prioritize | Gemini | `gemini-3.1-flash` | short ranking task |
| hunt (per category) | Gemini | `gemini-3.1-flash` | high-volume code scanning, cost-sensitive |
| validate | Gemini | `gemini-3.1-pro` (`AGENT_LLM_MODEL_SMART`) | deep data/control-flow reasoning + PoC quality |

> **Assumed:** model IDs `gemini-3.1-flash` (fast tier) and `gemini-3.1-pro` (smart tier). The boilerplate `GeminiProvider.DEFAULT_MODEL` is `gemini-3.1-pro`; the fast tier is a new setting. If these IDs are unavailable, override via `AGENT_LLM_MODEL_FAST` / `AGENT_LLM_MODEL_SMART` in `.env`.

**Fallback behaviour:** on Gemini error/rate-limit, retry with exponential backoff (max 3); on persistent failure the node sets `state.error` and routes to `handle_error` (run → failed). Findings already persisted are retained. No offline stub — tests call the real API via `.env`.

**Prompt strategy:** system/user split; system prompt per node loaded from `src/prompts/` (repurpose `transform.md` → `recon.md`, plus `prioritize.md`, `hunt.md`, `validate.md`). Structured JSON output requested for prioritization and findings (parsed defensively).

---

## Tools & Tool Calling

Deterministic, in-code tools (not LLM-freeform) invoked by nodes:

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `scope_guard.check(target)` | In-code allowlist containment check | target path/host, allowlist | allow/refuse | none (pure) |
| `repo_walk(path)` | Read-only scoped file inventory + manifest detection | scoped path | file list, languages, manifest paths | filesystem read only |
| `read_excerpt(file, span)` | Read a bounded code excerpt (never whole file persisted) | file, line span | excerpt string | filesystem read only |
| `parse_manifest(path)` | Extract deps for CVE matching | manifest path | dep list w/ versions | filesystem read only |
| `sandbox_run(script)` | Execute generated PoC in isolated subprocess (no network, time+mem bounded) | script text | exit code, stdout/stderr | temp sandbox exec |
| `persist_finding(f)` | Insert a validated finding immediately (streamable) | finding dict | finding id | DB write |

**Tool selection strategy:** rule-based — nodes call tools directly in code; the LLM produces analysis/findings, not tool routing. `scope_guard` is enforced in code regardless of LLM output.

**Tool failure handling:** `scope_guard` refusal → fatal (route to handle_error). `sandbox_run` failure/timeout → finding stays `unconfirmed`, keep static evidence, continue. DB write failure → fatal.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                       # set at init
    engagement_id: str                # set at init

    # Input (from engagement + scope_record)
    target_path: str                  # repo path
    scope_allowlist: list[str]        # in-code enforced allowlist
    non_destructive_only: bool

    # Control / budget
    step_budget: int                  # bounded (default AGENT_STEP_BUDGET=40)
    step_count: int                   # incremented by each node action
    current_phase: str                # recon|prioritize|hunt|validate|report
    current_category: str | None

    # Pipeline data
    recon: dict                       # {files, languages, manifests}
    priorities: list[str]             # ordered categories still to hunt
    candidate_findings: list[dict]    # pre-validation
    findings: list[dict]              # validated (also persisted as produced)

    # Cost accounting
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float

    # Output / status
    status: str                       # running|completed|failed
    error: str | None
```

---

## Nodes / Steps

### `enforce_scope` (entry)
**Reads:** `target_path`, `scope_allowlist`. **Writes:** `error`, `current_phase`.
**LLM call:** no. **Behaviour:** in-code allowlist containment check (path must be inside an authorized target). On violation sets `state.error="scope violation: <target>"` and the graph routes to `handle_error` — nothing is read or sent to the LLM. This is the SAFETY-CRITICAL code gate.

### `recon`
**Reads:** `target_path`, `scope_allowlist`. **Writes:** `recon`, `step_count`, `current_phase`.
**LLM call:** yes (fast tier) — summarize inventory/tech. **External:** `repo_walk`, `parse_manifest` (fatal if unreadable). Builds file inventory, languages, manifest locations.

### `prioritize`
**Reads:** `recon`. **Writes:** `priorities`, `step_count`. **LLM (fast):** rank the four categories by relevance; allocate remaining budget. Output JSON list of categories.

### `hunt` (looping)
**Reads:** `priorities`, `recon`, `step_count`, `step_budget`. **Writes:** `candidate_findings`, `current_category`, `step_count`, pops the handled category from `priorities`.
**LLM (fast):** scan the category's relevant files (via `read_excerpt`) → candidate findings. Loops (conditional edge back to `hunt`) while `priorities` non-empty AND `step_count < step_budget`; otherwise routes to `validate`.

### `validate`
**Reads:** `candidate_findings`. **Writes:** `findings`, `step_count`, per-finding confidence.
**LLM (smart):** static data/control-flow reasoning + generate PoC. **External:** `sandbox_run` (best-effort), `persist_finding` (each finding inserted immediately → streams to UI). Assigns `confidence`; unconfirmed findings are persisted and marked, not dropped. Honors remaining budget.

### `report` (finalize)
**Reads:** all. **Writes:** `status="completed"`, final cost. Marks `assessment_runs` completed, `completed_at`, final token/cost. (Phase 3 adds next-probe suggestions + same-pattern flags here.)

### `handle_error`
**Reads:** `error`, `run_id`. Marks `assessment_runs` status=`failed`, `error_message`, `completed_at`; logs with `run_id`. Terminates.

---

## Graph / Flow Topology

```
START
  │
  ▼
enforce_scope ──(error)──► handle_error ──► END
  │ (ok)
  ▼
recon ──(error)──► handle_error
  │
  ▼
prioritize
  │
  ▼
hunt ◄─────────────┐
  │                │ (priorities left AND step_count < step_budget)
  ├────────────────┘
  │ (done OR budget exhausted)
  ▼
validate ──(error)──► handle_error
  │
  ▼
report ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| enforce_scope | `state.error` set | handle_error |
| enforce_scope | otherwise | recon |
| recon | `state.error` set | handle_error |
| recon | otherwise | prioritize |
| hunt | `priorities` non-empty AND `step_count < step_budget` | hunt |
| hunt | otherwise | validate |
| validate | `state.error` set | handle_error |
| validate | otherwise | report |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| Within a run | LangGraph state | recon, priorities, candidate/validated findings, budget, cost |
| Across runs | Postgres | engagements, scope, findings (accumulate), per-run token/cost |
| Conversation | Phase 2: `chat_turns` table (turn memory) | interactive chat history per engagement |

**Context window management:** only bounded code excerpts (`read_excerpt`) are sent, per-category, not whole repos — keeps prompts small and cost low.

---

## Error Handling & Recovery

**Node-level:** each node try/excepts; fatal → set `state.error`, route to `handle_error`.
**Graph-level (`handle_error`):** run → `failed`, store `error_message`, `completed_at`; log with `run_id`; terminate. Findings persisted before failure are retained.
**Resume/retry:** no mid-run resume in Phase 1; a failed run can be re-started as a new run. LLM calls retry with backoff internally.
**Partial failure:** `sandbox_run` failure degrades a finding to `unconfirmed` but the run continues.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| Trace | one trace/run, one span/node | LangSmith (`LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`) — wired Phase 1 |
| LLM calls | prompt/completion tokens, latency, model, node | structlog JSON to stdout + LangSmith |
| Tool calls | tool, inputs (redacted), success/latency | structlog JSON |
| Run outcome | status, phase, step_count, total tokens, cost | Postgres `assessment_runs` + structlog |
| Live progress | phase/category/step/cost + each finding | SSE `GET /runs/{id}/events` |

Token/cost accounting: `LLMClient.call_model` is extended to return usage (`prompt_tokens`, `completion_tokens` from Gemini `usage_metadata`); nodes accumulate into state; cost = tokens × per-model rate (`AGENT_COST_RATE_*` settings). Persisted on the run.

---

## Concurrency Model

- **Run isolation:** one active run per engagement — `POST /engagements/{id}/runs` returns 409 if a run is already `running`. Runs execute in a FastAPI background task; state scoped by `run_id`.
- **Parallel nodes within a run:** none in Phase 1 (sequential pipeline; hunt loops serially per category to keep the step budget deterministic).
- **Checkpointing:** none in Phase 1 (no human-in-the-loop mid-run). SSE tails DB state, so no cross-process in-memory queue is required.

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)
graph.add_node("enforce_scope", enforce_scope)
graph.add_node("recon", recon)
graph.add_node("prioritize", prioritize)
graph.add_node("hunt", hunt)
graph.add_node("validate", validate)
graph.add_node("report", report)          # finalize
graph.add_node("handle_error", handle_error)

graph.set_entry_point("enforce_scope")

graph.add_conditional_edges("enforce_scope",
    lambda s: "handle_error" if s.get("error") else "recon",
    {"handle_error": "handle_error", "recon": "recon"})
graph.add_conditional_edges("recon",
    lambda s: "handle_error" if s.get("error") else "prioritize",
    {"handle_error": "handle_error", "prioritize": "prioritize"})
graph.add_edge("prioritize", "hunt")
graph.add_conditional_edges("hunt",
    lambda s: "hunt" if (s.get("priorities") and s["step_count"] < s["step_budget"]) else "validate",
    {"hunt": "hunt", "validate": "validate"})
graph.add_conditional_edges("validate",
    lambda s: "handle_error" if s.get("error") else "report",
    {"handle_error": "handle_error", "report": "report"})
graph.add_edge("report", END)
graph.add_edge("handle_error", END)

agentic_ai = graph.compile()
```
