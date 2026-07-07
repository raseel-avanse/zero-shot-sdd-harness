# Capability: Live-App Probing, Interactive Chat, and Re-Test After Remediation

> Phase 2. Bundles three user-facing sub-features that share the running-engagement surface.

## What It Does
Extends assessment beyond source repos: (a) non-destructive active probing of a scope-approved live web app/API (read-only only), (b) an interactive chat mode to direct follow-up probes over a loaded target with turn memory, and (c) a re-test-after-remediation flow that re-runs validation on a finding to confirm a fix.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| engagement_id | string | UI/API | yes |
| target_ref (base URL) | string | scope_record | yes for live-app |
| chat_message | string | chat UI | yes for chat |
| finding_id | string | finding card | yes for re-test |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| live findings | Finding rows | Postgres + stream |
| chat turns | messages[] | Postgres (`chat_turns`) — conversation memory |
| re-test result | updated finding confidence/status | Postgres |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Target HTTP endpoints (read-only) | GET/HEAD/OPTIONS only; no state-changing verbs | abort probe, log |
| Gemini | chat turns (with history), probe planning, re-test reasoning | log + surface error |
| PostgreSQL | persist findings, chat turns, status updates | fatal on loss |

## Business Rules
- Active testing against live targets is NON-DESTRUCTIVE ONLY, enforced in code: an in-code verb allowlist (GET/HEAD/OPTIONS) and host allowlist reject anything else, independent of the LLM.
- Chat mode carries conversation history (turn memory) scoped to the engagement — each follow-up sees prior turns.
- Re-test re-runs the validation node against the current target state for one finding and updates its confidence/status (e.g. `remediated` when the PoC no longer reproduces).

## Success Criteria
- [ ] A live-app probe against a scope-approved host issues only read-only verbs (verified by request log); a state-changing verb is refused in code.
- [ ] A probe against an out-of-scope host is refused before any request is sent.
- [ ] A chat follow-up correctly references context established in an earlier turn of the same engagement.
- [ ] Re-testing a fixed finding transitions it to `remediated`; re-testing an unfixed one keeps it `validated`.
