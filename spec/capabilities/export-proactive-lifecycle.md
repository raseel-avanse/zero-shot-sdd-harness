# Capability: Export, Proactive Suggestions, and Finding Lifecycle

> Phase 3. Bundles three user-facing sub-features over the accumulated findings surface.

## What It Does
Turns accumulated engagement findings into decision-ready output: (a) one-click exportable engagement dossier (MD/PDF/JSON), (b) proactive behavior — after findings the agent suggests 2–3 next probes and flags the same vulnerability pattern elsewhere in the target, and (c) full finding status lifecycle management (new / validated / remediated / false-positive).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| engagement_id | string | UI/API | yes |
| export_format | enum `md` \| `pdf` \| `json` | export control | yes for export |
| finding_id + new_status | string + enum | finding card | yes for lifecycle |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| engagement dossier | file (MD/PDF/JSON) | download response |
| next-probe suggestions | suggestion[] | UI + run metadata |
| same-pattern flags | Finding rows tagged `pattern_ref` | Postgres |
| status change | updated finding.status | Postgres |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | generate suggestions, detect same-pattern occurrences | log + surface error |
| PDF renderer (library) | render MD → PDF | fall back to MD download with warning |
| PostgreSQL | read findings, update status | fatal on loss |

## Business Rules
- A dossier rolls up every finding for the engagement with severity, location, evidence/PoC, and remediation patch; it is audit-defensible (includes scope record + per-run token/cost).
- After a hunt produces a finding of a given pattern, the agent scans for the same pattern elsewhere and emits linked `pattern_ref` findings.
- Status lifecycle: `new → validated → remediated`, or any → `false_positive`; transitions are user-driven and persisted with a timestamp.

## Success Criteria
- [ ] Exporting an engagement yields a valid MD, PDF, and JSON containing all findings + scope + cost.
- [ ] After a finding is produced, the agent returns 2–3 concrete next-probe suggestions.
- [ ] When one injection pattern is found, at least one same-pattern occurrence elsewhere is flagged with a `pattern_ref` link (on a repo seeded with a duplicated pattern).
- [ ] A user can move a finding through new → validated → remediated and mark any as false-positive, with each change persisted.
