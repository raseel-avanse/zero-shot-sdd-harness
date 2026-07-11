# Capability: Category Exploration

## What It Does
Lets the user explore a category (optionally with constraints like budget) and surfaces the best-value deals within it across Indian sites.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| query_text | str (category) | UI category input → `POST /runs` | Yes |
| query_type | str (`"category"`) | UI / API | Yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| deals | list[Deal] (3–5 across products) | `deals` table → UI cards |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini + google_search | Discover strong products in the category, then find best listings | retry/backoff → fatal |

## Business Rules
- For a category, deals may span different products (best-value picks), each still with site, price, and reason.
- Honours in-query constraints (e.g. "under ₹5000") when present.
- Same grounded-only, INR, stateless rules.

## Success Criteria
- [ ] A category query returns 3–5 best-value picks with site, INR price, and reason.
- [ ] A stated budget constraint is respected in the returned prices.
- [ ] Distinct products appear when the category warrants it (not five listings of one item).
