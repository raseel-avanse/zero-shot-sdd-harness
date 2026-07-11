# Capability: URL-input Research

## What It Does
Lets the user paste a product URL; DealScout identifies the item and researches/ranks deals for that same product across Indian sites.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| query_text | str (URL) | UI URL input → `POST /runs` | Yes |
| query_type | str (`"url"`) | UI / API | Yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| deals | list[Deal] | `deals` table → UI cards |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini + google_search | Identify the product from the URL, then find + cross-check listings across sites | retry/backoff → fatal |

## Business Rules
- The pasted URL anchors the research to a specific product; the ranking compares that product across sites.
- Same grounded-only, trimmed-content, INR, stateless rules as product-name search.

## Success Criteria
- [ ] A valid Indian-marketplace product URL yields a ranked list for that product.
- [ ] The identified product matches the URL's item (not an unrelated result).
- [ ] Invalid/unreachable URL → graceful clarify or empty-state, not a crash.
