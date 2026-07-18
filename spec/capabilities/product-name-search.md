# Capability: Product-name Search

## What It Does
Runs a deep, multi-step web-grounded research pass across popular Indian shopping sites from a product name the user types.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| query_text | str | UI product-name box → `POST /runs` | Yes |
| query_type | str (`"name"`) | UI / API | Yes (defaults to `name`) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| research_notes | str (trimmed) | agent state → feeds ranking |
| grounding_sources | list[str] | agent state → deal `source_url` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini + google_search | Grounded search for listings + reviews across Amazon.in, Flipkart, Myntra/Ajio, quick-commerce, electronics sites | retry/backoff → fatal (run `failed`) |

## Business Rules
- All web research goes through Gemini's native `google_search` grounding — no external scrapers/search APIs.
- Only trimmed, relevant content is retained/forwarded to minimise tokens and exposure.
- Scope is Indian shopping sites only.
- Stateless — no prior run influences this research.

## Success Criteria
- [ ] A clear product-name query produces non-empty `research_notes` with grounding metadata present.
- [ ] The run completes within ~30–90s under normal conditions.
- [ ] Cross-checks the product across at least two Indian sites when available.
