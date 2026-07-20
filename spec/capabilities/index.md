# Capabilities Index

> Sentinel — a whitebox information-security agent. Each capability is one discrete behavior. Files use no number prefix.

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Scope-gated engagement (scope form + in-code allowlist) | 1 | [scope-gated-engagement.md](scope-gated-engagement.md) |
| Repository code review with streamed validated finding cards | 1 | [repo-code-review.md](repo-code-review.md) |
| Live-app probing, interactive chat, and re-test after remediation | 2 | [live-probing-chat-retest.md](live-probing-chat-retest.md) |
| Export, proactive suggestions, and finding lifecycle | 3 | [export-proactive-lifecycle.md](export-proactive-lifecycle.md) |
| OWASP API Security Top 10 (2023) assessment profile | 4 | [owasp-api-top10.md](owasp-api-top10.md) |

> **Scoping note:** Phase 1 delivers the two capabilities that form the smallest first-time-right win (scope-gated engagement + repo code review). Capabilities 3 and 4 each bundle three distinct user-facing sub-features (see their files). Capability 5 (Phase 4) is a single focused addition — a structured OWASP API Top 10 assessment profile — layered on the existing Phase 2 non-destructive live path; it adds one new user-facing choice (the profile) plus richer, standards-mapped findings rather than three separate features.

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer creates `<name>.md`, updates this index, flags dependencies, and self-reviews before returning.
