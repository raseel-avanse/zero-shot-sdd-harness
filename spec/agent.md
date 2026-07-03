# Agent

---

## Agent Architecture Pattern

**Chosen:** **Graph (LangGraph)** composing **Tool Use** (local pandas execution as the tool), **Reflection / self-correction** (bounded retry loop that feeds execution tracebacks back to the code-writer), and a **fallback** path (reason-over-sample when code can't be produced or all attempts fail). A graph is warranted because the flow has conditional edges (retry vs. proceed vs. fallback vs. error) and a bounded loop — more than a linear chain, less than multi-agent.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `write_code` | Gemini | `gemini-2.5-flash` | Cheap, capable at code-writing; keeps spend low |
| `synthesize_answer` | Gemini | `gemini-2.5-flash` | Short natural-language method note from computed result |
| `build_chart` | Gemini | `gemini-2.5-flash` | Small structured chart-spec generation |
| `fallback_reason` | Gemini | `gemini-2.5-flash` | Reason over a sample when code path fails |

Model is env-configurable (`AGENT_GEMINI_MODEL`, default `gemini-2.5-flash`).

**Fallback behaviour:** LLM client retries with backoff on transient API errors. If the API is unavailable after retries, the node sets `state["error"]` and the graph routes to `handle_error`, surfaced as `api_error`. This is production resilience, not a test stub — tests call the real Gemini API via `.env`.

**Prompt strategy:** System/user split. Prompts include ONLY the dataset profile + a small sample (head + describe), never the full dataframe, to keep tokens low. `write_code` uses structured output requesting a single pandas snippet that assigns to `result`. `build_chart` uses JSON-mode structured output for the chart spec.

---

## Tools & Tool Calling

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `execute_pandas` | Runs generated pandas code locally against the in-memory dataframe | code string, dataframe | `result` value + captured stdout, or traceback string | None (reads df in-process); bounded by timeout |

**Tool selection strategy:** Deterministic — `write_code` always emits code, `execute_code` always runs it. No LLM tool-choice; the graph topology fixes the sequence.

**Tool failure handling:** Execution traceback is captured (not raised) and fed back into the next `write_code` attempt. After `AGENT_MAX_CODE_ATTEMPTS` failures, route to `fallback_reason`.

---

## Agent State

```python
class AgentState(TypedDict):
    # Identity
    run_id: int                          # set at initialisation (DB runs row)
    dataset_id: str                      # in-memory dataframe key

    # Input
    question: str                        # user question
    profile: dict                        # dataset profile (reused from upload)
    sample: str                          # small head+describe string for prompts

    # Pipeline data (populated progressively)
    code: str | None                     # latest generated pandas code
    attempts: int                        # execution attempts so far (starts 0)
    last_traceback: str | None           # traceback from last failed execution
    result_repr: str | None              # stringified computed result
    used_fallback: bool                  # True if reason-over-sample path taken

    # Output
    answer: str | None                   # key numbers + method note
    method_note: str | None              # how the answer was derived
    assumptions: list[str]               # flagged best-guess assumptions
    chart_spec: dict | None              # None if no chart fits
    token_usage: dict                    # {prompt, completion, total} summed
    step_trace: list[dict]               # ordered {step, status, attempt} events

    # Control
    error: str | None                    # set by any node on fatal failure
    checkpoint: str | None               # last completed node
```

---

## Nodes / Steps

### `node_init`
**Reads:** `dataset_id`, `question`. **Writes:** `run_id`, `profile`, `sample`, `attempts=0`, `step_trace=[]`, `token_usage`, `assumptions=[]`, `used_fallback=False`.
**LLM call:** no. Creates the `runs` DB row, loads the profile/sample for the dataset. Emits step `profiling: done` (profile reused from upload).

### `node_write_code`
**Reads:** `profile`, `sample`, `question`, `last_traceback`, `attempts`. **Writes:** `code`, `token_usage` (accumulated), `step_trace`.
**LLM call:** yes — `gemini-2.5-flash`, structured output = pandas snippet assigning to `result`. On retry, includes `last_traceback`. Emits step `writing_code`.

### `node_execute_code`
**Reads:** `code`, `dataset_id`. **Writes:** `result_repr` or `last_traceback`, `attempts += 1`, `step_trace`.
**LLM call:** no. Runs `execute_pandas` tool locally with a wall-clock timeout. Emits `running_code: done` or `running_code: retry`.
| System | Operation | On Failure |
|--------|-----------|------------|
| Local pandas exec | Run generated code | Capture traceback → route back to `write_code` (bounded) |

### `node_synthesize_answer`
**Reads:** `question`, `result_repr`, `used_fallback`. **Writes:** `answer`, `method_note`, `assumptions`, `token_usage`, `step_trace`.
**LLM call:** yes — turns the computed result into key-numbers + a 1–3 sentence method note; flags assumptions. Emits `synthesizing: done`.

### `node_build_chart`
**Reads:** `question`, `result_repr`. **Writes:** `chart_spec` (or `None`), `token_usage`.
**LLM call:** yes — JSON-mode chart spec if the result fits; any error → `chart_spec=None` (never fatal).

### `node_fallback_reason`
**Reads:** `question`, `profile`, `sample`. **Writes:** `answer`, `method_note`, `assumptions` (includes "answer is approximate, computed from a sample"), `used_fallback=True`, `token_usage`.
**LLM call:** yes — reason over the sample. Entered when code can't be produced or all attempts fail.

### `node_finalize`
**Reads:** all output fields. **Writes:** DB `runs` row (status, answer, code, tokens, attempts), appends query log line. Emits nothing new.

### `node_handle_error`
**Reads:** `error`, `run_id`. **Writes:** `runs` status → failed, `error_message`, `completed_at`; logs with `run_id`.

---

## Graph / Flow Topology

```
START
  │
  ▼
node_init ──(error)──► node_handle_error ──► END
  │
  ▼
node_write_code ──(error)──► node_handle_error
  │
  ▼
node_execute_code
  │
  ├─(success)──────────────► node_synthesize_answer
  │
  ├─(fail & attempts<MAX)──► node_write_code   (retry loop)
  │
  └─(fail & attempts>=MAX)─► node_fallback_reason ──► node_finalize
                                   │
node_synthesize_answer ──► node_build_chart ──► node_finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| node_init | `state["error"]` | node_handle_error |
| node_init | else | node_write_code |
| node_write_code | `state["error"]` | node_handle_error |
| node_write_code | else | node_execute_code |
| node_execute_code | `last_traceback is None` (success) | node_synthesize_answer |
| node_execute_code | fail and `attempts < MAX` | node_write_code |
| node_execute_code | fail and `attempts >= MAX` | node_fallback_reason |
| node_synthesize_answer | always | node_build_chart |
| node_build_chart | always | node_finalize |
| node_fallback_reason | always | node_finalize |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state | All in-progress data incl. attempts + traceback |
| **Across runs** | SQLite `runs` table + query log file | Every Q&A, code, tokens, attempts (see [data.md](data.md)) |
| **Conversation** | Phase 1: history kept in the browser view (client-side); Phase 2: persisted per-session in DB | Prior Q&A pairs |

> **Assumed:** Phase 1 keeps conversation history in the browser view only (the running Q&A list is client-held); server-persisted multi-question session memory is Phase 2. Justified: Phase 1 sessions are one-shot per the brief, and each question already carries `dataset_id`; the primary journey (upload → ask → answer) works first-time without cross-turn server memory.

**Context window management:** Prompts carry only the profile + a small head/describe sample, never the full dataframe — keeps within limits and keeps spend low.

---

## Error Handling & Recovery

**Node-level:** each node catches its own exceptions; fatal errors set `state["error"]` and route to `node_handle_error`.

**Graph-level (`node_handle_error`):** sets `runs` status → failed, records `error_message` and `completed_at`, logs with `run_id`, terminates.

**Resume / retry strategy:** the code self-correction loop is the in-run retry (bounded by `AGENT_MAX_CODE_ATTEMPTS`, default 3). No cross-request resume — a failed run is re-asked by the user.

**Partial failure:** chart generation is non-critical — its failure degrades to `chart_spec=None`, never aborts. Code-execution failure degrades to the fallback-reason path.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One log context per run (`run_id`), one event per node | structlog → stdout |
| **LLM calls** | Prompt/completion tokens, latency, model | structlog + accumulated into `token_usage` |
| **Tool calls** | `execute_pandas` code, success/traceback, attempt no. | structlog |
| **Run outcome** | Status, attempts, tokens, answer | SQLite `runs` + query log file |

---

## Concurrency Model

- **Run isolation:** single-user tool — runs are keyed by `run_id`/`dataset_id`; concurrent requests are allowed but expected to be one-at-a-time in practice.
- **Parallel nodes within a run:** none (linear with a retry loop).
- **Checkpointing:** none (no human-in-the-loop; runs are short).

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)

graph.add_node("init", node_init)
graph.add_node("write_code", node_write_code)
graph.add_node("execute_code", node_execute_code)
graph.add_node("synthesize", node_synthesize_answer)
graph.add_node("build_chart", node_build_chart)
graph.add_node("fallback", node_fallback_reason)
graph.add_node("finalize", node_finalize)
graph.add_node("handle_error", node_handle_error)

graph.set_entry_point("init")

graph.add_conditional_edges("init",
    lambda s: "handle_error" if s.get("error") else "write_code")
graph.add_conditional_edges("write_code",
    lambda s: "handle_error" if s.get("error") else "execute_code")

def route_after_exec(s):
    if s.get("last_traceback") is None:
        return "synthesize"
    return "write_code" if s["attempts"] < MAX_ATTEMPTS else "fallback"

graph.add_conditional_edges("execute_code", route_after_exec)
graph.add_edge("synthesize", "build_chart")
graph.add_edge("build_chart", "finalize")
graph.add_edge("fallback", "finalize")
graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

compiled_graph = graph.compile()
```
