# Agent — DealScout research graph

---

## Agent Architecture Pattern

**Chosen: Graph (LangGraph).** DealScout is a multi-step research pipeline with conditional branches (query-type routing, a clarify pause, and error routing). It composes **Prompt Chaining** (#1: research → rank), **Tool Use / Knowledge Retrieval** (#5/#14: Gemini's native `google_search` grounding), **Human-in-the-Loop** (#13: the clarify gate, P2), and **Exception Handling** (#12: node-level error → `handle_error`). It is deliberately NOT a free-running ReAct loop: the steps are fixed and ordered (research then rank), grounding is the only tool, and determinism of flow makes the ~30–90s run predictable and observable. Memory Management (#8) is explicitly excluded — every run is stateless.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `research` | Gemini | `gemini-2.5-flash` (env `AGENT_LLM_MODEL`) | Deep grounded search across sites; grounding tool required. |
| `rank` | Gemini | `gemini-2.5-flash` | Turns research notes into a defensible structured ranking; quality-sensitive. |
| `clarify` (P2) | Gemini | `gemini-2.5-flash` | Judges ambiguity + composes ONE question; low volume. |
| `deal_quality` (P2) | Gemini | `gemini-2.5-flash` | Judges discount genuineness per deal, grounded in price-history search. |

**Fallback behaviour:** On a transient Gemini error (timeout/5xx/rate-limit) each node retries with exponential backoff (up to 2 retries). On persistent failure the node sets `state.error` and routes to `handle_error`; the run is marked `failed` and the UI surfaces a plain-language message. No offline stub on the tested path — tests call the real API with keys from `.env`.

**Prompt strategy:** System instruction + user content split. Prompts are `.md` files in `src/prompts/`. The `research` node enables the `google_search` tool. The `rank` node requests **structured JSON** (a list of deal objects) validated against a Pydantic model; on parse failure the node retries once with a "return valid JSON only" reminder, then errors. Only trimmed research notes (not raw page dumps) are passed from `research` to `rank` to minimise tokens/exposure.

---

## Tools & Tool Calling

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `google_search` (native Gemini) | Web search grounding across Indian shopping sites | query text (model-driven) | grounded text + grounding metadata (source URLs) | none (read-only web) |
| `estimate_cost` (`src/tools/pricing.py`) | Converts token usage → estimated INR cost | prompt/completion tokens, model | `float` INR | none (pure) |
| `assess_deal_quality` (`src/tools/deal_quality.py`, P2) | Heuristic + grounded judgement of discount genuineness | deal (price, site), grounded price context | quality label + one-line justification | none (pure) |

**Tool selection strategy:** Forced, not free-choice. The `research` node always runs with the `google_search` tool enabled (Gemini decides how many searches to issue). `estimate_cost` / `assess_deal_quality` are called directly by node code, not chosen by the LLM.

**Tool failure handling:** `google_search` empty results → degrade (fewer/zero deals, empty-state in UI), not fatal. Gemini call failure → retry/backoff then fatal per node. Pure tools cannot fail on external systems.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                    # set at initialisation

    # Input
    query_type: str                # "name" (P1) | "url" | "category" (P2)
    query_text: str                # the product name / URL / category
    clarify_answer: str | None     # user's answer to a clarify question (P2, on resume)

    # Pipeline data (populated progressively by nodes)
    progress_step: str             # "queued"|"searching"|"reviewing"|"ranking"|"assessing"|"done"
    research_notes: str            # trimmed grounded findings from research node
    grounding_sources: list        # source URLs from grounding metadata
    prompt_tokens: int             # accumulated across LLM calls
    completion_tokens: int         # accumulated across LLM calls

    # Control (clarify gate, P2)
    needs_clarification: bool      # research node / clarify node sets when ambiguous
    clarifying_question: str | None

    # Output
    deals: list                    # [{rank, site, price_inr, reason, quality_label, quality_reason}]
    cost_inr: float                # estimate_cost(prompt+completion tokens)

    # Error
    error: str | None              # set by any node on fatal failure
```

The Phase-1 skeleton keeps `input_text`/`output_text` compatibility removed — nodes are rewritten in place. `messages` (chat history) is **removed**: DealScout is stateless with no conversation memory.

---

## Nodes / Steps

### `research`
**Reads from state:** `query_type`, `query_text`, `clarify_answer`
**Writes to state:** `research_notes`, `grounding_sources`, `prompt_tokens`, `completion_tokens`, `progress_step`, (`needs_clarification`, `clarifying_question` in P2), `error`
**LLM call:** yes — Gemini with `google_search` grounding; system prompt `src/prompts/research.md`; output = trimmed research notes (text) + grounding metadata.
**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini + google_search | Grounded multi-search across Indian sites | retry/backoff → fatal (set error) |

**Behaviour:** Sets `progress_step="searching"` then `"reviewing"`. Issues grounded searches to find listings + reviews across Amazon.in, Flipkart, Myntra/Ajio, quick-commerce, electronics sites; cross-checks prices; distils to trimmed notes. (P2) If input is too ambiguous to research confidently, sets `needs_clarification=True` and a single `clarifying_question`, and does not proceed.

### `clarify` (P2 — human-in-the-loop pause)
**Reads:** `needs_clarification`, `clarifying_question`, `clarify_answer`
**Writes:** `progress_step`, routes back into `research` once answered
**LLM call:** used within `research` to compose the question; the `clarify` node itself is a **pause point** (see checkpoints). On resume, `clarify_answer` is merged into state and flow re-enters `research`.

### `rank`
**Reads from state:** `research_notes`, `grounding_sources`, `query_text`
**Writes to state:** `deals`, `prompt_tokens`, `completion_tokens`, `progress_step`, `error`
**LLM call:** yes — Gemini; system prompt `src/prompts/rank.md`; **structured JSON** output validated to a list of 3–5 deal objects `{rank, site, price_inr, reason}`.
**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | Rank + justify from notes | JSON parse fail → retry once → fatal |

**Behaviour:** Sets `progress_step="ranking"`. Produces a clean ranked list of 3–5 deals, each with site, INR price, and one-line reason — no reasoning dump. If research found nothing rankable, returns an empty list (empty-state, not error).

### `deal_quality` (P2)
**Reads:** `deals`
**Writes:** `deals` (adds `quality_label`, `quality_reason` per deal), `prompt_tokens`, `completion_tokens`, `progress_step`
**LLM call:** yes — Gemini grounded price-history check; system prompt `src/prompts/deal_quality.md`.
**Behaviour:** Sets `progress_step="assessing"`. For each deal, judges whether the discount is genuine / a good time to buy, adding a label + one-line justification. Degrades (label "unknown") rather than failing the run if grounding is thin.

### `finalize`
**Reads:** `deals`, `prompt_tokens`, `completion_tokens`
**Writes:** `cost_inr`, `progress_step="done"`, `status`
**Behaviour:** Calls `estimate_cost`, persists deals + usage + cost to DB, marks run `completed`.

### `handle_error`
**Reads:** `error`, `run_id`
**Behaviour:** Marks run `failed`, writes `error_message`, logs with `run_id`, terminates.

---

## Graph / Flow Topology

```
START
  │
  ▼
research ──(error)──────────────► handle_error ──► END
  │
  ├─(P2: needs_clarification)──► clarify ──(PAUSE; on answer)──► research
  │
  ▼
rank ──(error)──────────────────► handle_error
  │
  ▼
deal_quality (P2) ──────────────► finalize ──► END
  │  (P1: research→rank→finalize directly)
  ▼
finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `research` | `state["error"]` is not None | `handle_error` |
| `research` | `state["needs_clarification"]` (P2) | `clarify` |
| `research` | otherwise | `rank` |
| `clarify` | resumed with `clarify_answer` | `research` |
| `rank` | `state["error"]` is not None | `handle_error` |
| `rank` | otherwise | `deal_quality` (P2) / `finalize` (P1) |
| `deal_quality` | always | `finalize` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state | All in-progress research + ranking data |
| **Across runs** | none (by design) | nothing — DealScout is stateless |
| **Conversation** | none (by design) | nothing — no turn/chat memory |

**Context window management:** Only trimmed research notes (not raw grounded page content) flow from `research` to `rank`, keeping prompts small and minimising cost/exposure.

---

## Human-in-the-Loop Checkpoints

| Checkpoint | What is shown to the user | Expected user action | Timeout / default |
|------------|--------------------------|----------------------|-------------------|
| `clarify` (P2) | ONE clarifying question when the query is too ambiguous to rank confidently | Type a one-line answer → run resumes | No auto-timeout; run stays paused (`status=needs_input`) until answered or abandoned |

Implemented via a run status `needs_input`: the graph pauses by returning early with `needs_clarification`, the API exposes the question, and `POST /runs/{id}/answer` re-invokes the graph with `clarify_answer` set.

---

## Error Handling & Recovery

**Node-level:** each node wraps its work in try/except; fatal errors set `state["error"]` and routing sends flow to `handle_error`. Gemini transient errors retry with backoff (2 retries) before becoming fatal.

**Graph-level (`handle_error`):**
- Reads: `state.error`, `state.run_id`
- Updates DB: run `status="failed"`, `error_message`, `updated_at`
- Logs error with `run_id` context
- Terminates graph

**Resume / retry strategy:** No checkpoint-resume for failed runs in P1 (stateless; the user simply re-submits). The only resume is the P2 clarify pause (`needs_input` → `answer`).

**Partial failure:** Empty grounding results → empty ranked list (empty-state), not an error. `deal_quality` (P2) grounding failure → per-deal "unknown" label, run still completes.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One trace per run, one span per node | LangSmith when `LANGCHAIN_TRACING_V2=true`; else structlog |
| **LLM calls** | prompt/completion tokens, latency, model, node | structlog JSON to stdout |
| **Tool calls** | grounding source count, cost estimate | structlog JSON |
| **Run outcome** | status, total duration, tokens, cost, error | DB (`runs`) + structlog |

Observability is wired in Phase 1 (structlog per node + LLM call; LangSmith env-gated) — never deferred.

---

## Concurrency Model

- **Run isolation:** each run is scoped by `run_id`; runs execute in a background thread launched by `POST /runs`. The single user issues one query at a time in practice; concurrent runs are independent (separate state, separate rows).
- **Parallel nodes within a run:** none — the pipeline is sequential (research → rank → [deal_quality] → finalize).
- **Checkpointing:** none in P1. P2 clarify uses an application-level pause (`status=needs_input`) rather than a LangGraph checkpointer, keeping the stateless model intact.

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)

graph.add_node("research", research)
graph.add_node("rank", rank)
graph.add_node("deal_quality", deal_quality)   # P2 (P1: no-op passthrough or absent)
graph.add_node("finalize", finalize)
graph.add_node("handle_error", handle_error)
# clarify handled as an application-level pause (P2), not a blocking node

graph.set_entry_point("research")

graph.add_conditional_edges(
    "research",
    after_research,   # -> "handle_error" | "clarify_pause" | "rank"
    {"handle_error": "handle_error", "rank": "rank", "END": END},  # clarify pause returns END early
)
graph.add_conditional_edges(
    "rank",
    after_rank,       # -> "handle_error" | "deal_quality"/"finalize"
    {"handle_error": "handle_error", "deal_quality": "deal_quality", "finalize": "finalize"},
)
graph.add_edge("deal_quality", "finalize")
graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

agentic_ai = graph.compile()
```
