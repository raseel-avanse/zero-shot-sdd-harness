# Capability: Ask Question → Codegen → Local Execute → Self-Correct → Answer

## What It Does
Takes a plain-English question about a loaded dataset, writes real pandas code with the LLM, runs it locally against the actual dataframe, self-corrects on error within a bounded retry loop, and returns key numbers plus a brief method note explaining how the answer was derived.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string (uuid) | Prior upload (see [upload-and-profile](upload-and-profile.md)) | yes |
| question | string | Question box UI | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer | string (key numbers + brief method note) | Answer card |
| executed_code | string (final pandas code that ran) | Collapsible code view |
| result_repr | string (stringified computed result) | Answer card |
| assumptions | string[] (flagged best-guess assumptions, may be empty) | Answer card |
| token_usage | object (`prompt`, `completion`, `total`) | Per-question token count badge |
| step_trace | object[] (`step`, `status`, `attempt`) | Live step-status |
| chart_spec | object \| null | see [auto-chart](auto-chart.md) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`gemini-2.5-flash`) | Write pandas code / synthesize answer | Retry with backoff; if still failing set `error`, return partial via `api_error` |
| Local pandas exec | Run generated code against in-memory df | Capture traceback → feed back to LLM as a self-correction attempt |

## Business Rules
- Code executes **locally on the server** in-process against the loaded dataframe. This is the documented trust boundary: single trusted user only. See [architecture.md](../architecture.md#trust-boundary-local-code-execution).
- Self-correction is a bounded loop: at most `AGENT_MAX_CODE_ATTEMPTS` (default 3) execution attempts. Each failed attempt appends the traceback to the LLM context for the next attempt.
- If code cannot be produced or all attempts fail, fall back to **reasoning over a sample** (head/describe of the df passed in-context) and clearly flag that the answer is approximate.
- When the model is unsure, it MUST still return a best-guess answer with assumptions listed in `assumptions`.
- The method note is one to three sentences describing the actual operation performed (e.g. "Grouped by region and summed revenue; sorted descending").
- Correctness and shown-work are prioritized over speed; LLM spend kept low by using the cheap `gemini-2.5-flash` tier and sending only the profile + small sample (not the whole dataframe) in prompts.
- Every question and its answer are appended to a query log file (see [transparency-log](transparency-log.md)) and recorded in the `runs` table (see [data.md](../data.md)).

## Success Criteria
- [ ] A factual question ("what is the average of column X?") returns the numerically correct value computed by executed pandas code.
- [ ] The `executed_code` field contains runnable pandas that reproduces `result_repr`.
- [ ] A question that triggers a first-attempt code error is self-corrected and still returns a correct answer within 3 attempts (asserted by a test that forces a common error like a wrong column name and confirms recovery).
- [ ] `token_usage.total > 0` and is returned for every question.
- [ ] `step_trace` contains ordered entries covering profiling(reused)/write-code/execute/synthesize.
