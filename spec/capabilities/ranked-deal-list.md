# Capability: Ranked Deal List

## What It Does
Turns research notes into a clean, decision-ready ranked list of 3–5 deals, each with the site, the price (INR), and a one-line reason why it ranks there.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| research_notes | str | product-name-search node | Yes |
| grounding_sources | list[str] | research node | No |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| deals | list[Deal] (3–5) | `deals` table + `GET /runs/{id}` → UI cards |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | Rank + justify from notes, structured JSON | JSON parse fail → retry once → fatal |

## Business Rules
- Output is exactly the ranked list + one-line reasons — no chain-of-thought / reasoning dump.
- Each deal has: rank, site, `price_inr`, one-line `reason`, optional `source_url`.
- 3–5 deals when available; fewer/zero allowed → UI empty-state (not an error).
- Prices are INR.

## Success Criteria
- [ ] For a clear query the run returns 3–5 deal objects, each with site, INR price, and a reason.
- [ ] Output validates against the Deal schema (structured JSON), no free-text dump.
- [ ] Each deal's site/price traces to a grounded source, not a fabrication.
