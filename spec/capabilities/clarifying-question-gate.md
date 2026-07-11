# Capability: Clarifying-Question Gate

## What It Does
When the input is too ambiguous to rank confidently, DealScout pauses before researching and asks exactly ONE clarifying question, then resumes once answered.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| query_text | str | `POST /runs` | Yes |
| clarify_answer | str | `POST /runs/{id}/answer` | On resume |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| clarifying_question | str | `runs.clarifying_question` → UI prompt |
| status = needs_input | str | run status → UI shows the question |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | Judge ambiguity + compose ONE question | retry/backoff → fatal |

## Business Rules
- Ask at most ONE question, only when confident ranking is not possible from the input.
- The question pauses the run (`status=needs_input`); research proceeds only after `POST /runs/{id}/answer`.
- Clear inputs skip the gate entirely (Phase 1 assumes clear input).
- No memory: the answer applies only to the current run.

## Success Criteria
- [ ] A deliberately ambiguous query (e.g. "good phone") returns `status=needs_input` with one question before any ranking.
- [ ] A clear query does NOT trigger the gate.
- [ ] Answering via `POST /runs/{id}/answer` resumes the run and produces a ranked list.
