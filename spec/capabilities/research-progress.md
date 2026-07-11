# Capability: Research Progress

## What It Does
Shows named progress steps in the UI during the ~30–90s research run, reflecting the real stage of work.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| progress_step | str | agent nodes update `runs.progress_step` | Yes |
| run_id | str | UI poll of `GET /runs/{id}` | Yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| named step label | str | UI progress bar |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| (none) | UI polls the local API | show last known step; on repeated poll failure → error state |

## Business Rules
- Steps map to real nodes: `searching` → "Searching Indian shopping sites…", `reviewing` → "Reading reviews & cross-checking prices…", `ranking` → "Ranking deals…", (P2) `assessing` → "Checking deal quality…".
- Progress must reflect real backend work — never a fake/animated-only bar.
- The UI polls `GET /runs/{id}` roughly every second while `status=running`.

## Success Criteria
- [ ] While a run executes, the UI displays the current named step matching `runs.progress_step`.
- [ ] The step advances through at least "searching" and "ranking" during a real run.
- [ ] On completion the progress area is replaced by the ranked list.
