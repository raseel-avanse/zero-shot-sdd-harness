# Capability: Auto-Chart When It Fits

## What It Does
When the answer to a question is naturally visual (a distribution, a ranking, a trend, a comparison across categories), the agent emits a compact chart spec (JSON) that the frontend renders; otherwise it emits `null` and no chart is shown.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| computed result | dataframe/series/scalar | Output of executed pandas code ([ask-question](ask-question.md)) | yes |
| question | string | Ask flow | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| chart_spec | object \| null | Answer card chart area |

Chart spec is a simple declarative shape the frontend renders (no server-side image rendering):
```json
{ "type": "bar|line|scatter|histogram", "x": "col_or_label", "y": "col_or_label",
  "series": [{ "label": "string", "points": [{"x": ..., "y": ...}] }],
  "title": "string" }
```

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`gemini-2.5-flash`) | Decide chart-fit + build spec from the computed result | On failure emit `chart_spec: null` (chart is optional, never fatal) |

## Business Rules
- A chart is generated only when the result is a suitable shape (>1 category or a numeric sequence). Scalars and single-value answers get `null`.
- Chart data is derived from the **already-computed** result — no extra data pass, no full-dataframe transfer.
- Chart generation must never fail the request: any error degrades to `chart_spec: null`.

## Success Criteria
- [ ] A "top 5 by revenue" style question returns a `chart_spec` of type `bar` whose points match the computed ranking.
- [ ] A single-scalar answer ("what is the total?") returns `chart_spec: null`.
- [ ] A malformed chart attempt degrades to `null` without failing the question.
