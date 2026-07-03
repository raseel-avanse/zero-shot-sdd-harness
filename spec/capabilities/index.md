# Capabilities Index

A capability is a single, discrete action or behavior the agent performs.

## Capabilities in This Project

| Capability | File | Phase |
|-----------|------|-------|
| Upload & auto-profile dataset | [upload-and-profile.md](upload-and-profile.md) | 1 |
| Ask question → codegen → local execute → self-correct → answer | [ask-question.md](ask-question.md) | 1 |
| Auto-chart when it fits | [auto-chart.md](auto-chart.md) | 1 |
| Per-question transparency (code + tokens + steps + query log) | [transparency-log.md](transparency-log.md) | 1 |
| Additional data sources (Google Sheets / JSON API) | [data-sources.md](data-sources.md) | 3 |

Later phases (multi-question session persistence, additional data sources, live DB, exportable datasets) are described in [../roadmap.md](../roadmap.md#phases-of-development) and appear as clearly-labelled non-functional stubs in [../ui.md](../ui.md).

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer creates a new `<name>.md`, updates this index, flags dependencies, and self-reviews fit against the architecture and data model.
