# Capabilities Index

> Sentinel — a whitebox information-security agent. Each capability is one discrete behavior. Files use no number prefix.

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Scope-gated engagement (scope form + in-code allowlist) | 1 | [scope-gated-engagement.md](scope-gated-engagement.md) |
| Repository code review with streamed validated finding cards | 1 | [repo-code-review.md](repo-code-review.md) |
| Live-app probing, interactive chat, and re-test after remediation | 2 | [live-probing-chat-retest.md](live-probing-chat-retest.md) |
| Export, proactive suggestions, and finding lifecycle | 3 | [export-proactive-lifecycle.md](export-proactive-lifecycle.md) |

> **Scoping note:** Phase 1 delivers the two capabilities that form the smallest first-time-right win (scope-gated engagement + repo code review). Capabilities 3 and 4 each bundle three distinct user-facing sub-features (see their files), so each later requirements phase is a coherent multi-feature user story. Total product cap held to 4 capability files per the ruthless-MVP rule.

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer creates `<name>.md`, updates this index, flags dependencies, and self-reviews before returning.
