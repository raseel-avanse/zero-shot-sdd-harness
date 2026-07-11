# Capability: Deal-Quality Flag

## What It Does
For each ranked deal, judges whether the discount is genuine and whether now is a good time to buy, adding a quality label and a one-line justification.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| deals | list[Deal] | rank node | Yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| quality_label | str (`genuine_discount`\|`wait`\|`unknown`) | `deals.quality_label` → UI badge |
| quality_reason | str | `deals.quality_reason` → UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini + google_search | Ground current price vs. typical/historical price to judge discount genuineness | thin grounding → label `unknown` (degrade, not fatal) |

## Business Rules
- Each deal gets one label + one-line justification.
- Grounded judgement — no fabricated "MRP was ₹X" claims.
- Degrades to `unknown` rather than failing the run when price history is unavailable.

## Success Criteria
- [ ] Each ranked deal carries a quality label and a one-line justification.
- [ ] A clearly-inflated "discount" is labelled `wait`, a genuine low price `genuine_discount`.
- [ ] Missing price history yields `unknown`, and the run still completes.
