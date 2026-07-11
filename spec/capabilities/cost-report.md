# Capability: Cost Report

## What It Does
Shows the tokens used and the estimated INR cost for each query after the answer is produced.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| prompt_tokens | int | accumulated by nodes from Gemini `usage_metadata` | Yes |
| completion_tokens | int | accumulated by nodes | Yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| cost_inr | float | `runs.cost_inr` → UI footer |
| token totals | int | UI footer |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| `estimate_cost` (pure, `src/tools/pricing.py`) | tokens × per-token rate → INR | cannot fail (pure); if usage missing → tokens shown as 0 |

## Business Rules
- Token counts come from Gemini's real `usage_metadata`, accumulated across the research + rank (+ deal_quality) calls.
- Cost is an estimate from a configurable per-1K-token INR rate for the chosen model.
- Shown only after `status=completed`.

## Success Criteria
- [ ] After a completed run the UI footer shows total tokens and an estimated INR cost.
- [ ] Token totals are non-zero for a real run and reflect summed `usage_metadata`.
- [ ] `cost_inr` is persisted on the run row.
