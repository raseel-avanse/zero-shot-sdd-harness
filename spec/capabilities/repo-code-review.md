# Capability: Repository Code Review with Streamed Validated Finding Cards

## What It Does
Runs an agentic, bounded multi-step whitebox review of a scope-approved local source repository across four vulnerability classes, validates each candidate, and streams validated finding cards (severity, location, PoC evidence, remediation patch) into the UI as they are confirmed, with live token/cost accounting.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| engagement_id | string | run start (UI/API) | yes |
| target_path | string (local repo path) | engagement.target_ref | yes |
| scope_allowlist | string[] | engagement's scope_record | yes |
| step_budget | int | settings `AGENT_STEP_BUDGET` (default 40) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| finding cards | Finding rows (streamed as validated) | Postgres (`findings`) + SSE stream |
| run progress | phase, category, step_count/step_budget | `assessment_runs` + SSE stream |
| token/cost | prompt/completion/total tokens + est. cost USD | `assessment_runs` + SSE stream |

Vulnerability classes hunted: (1) injection (SQLi/XSS/command injection); (2) broken auth & access control (authz/IDOR/session/privesc); (3) secrets & misconfiguration (hardcoded secrets, insecure defaults); (4) vulnerable dependencies (known-CVE packages in the manifest).

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (google-genai) | recon summary, prioritization, per-category hunt, PoC generation, validation reasoning | log + set `state.error`, route to handle_error; partial findings already persisted are retained |
| Local filesystem (read-only, within scope) | walk repo, read code excerpts | fatal if path unreadable/out of scope |
| Sandbox subprocess | execute generated PoC script (no network, time+memory bounded) | mark finding `unconfirmed`, keep static evidence, continue |
| PostgreSQL | persist findings + run counters | fatal on connection loss |

## Business Rules
- Bounded step budget: recon, each hunt iteration, and each validation consume steps; when `step_count >= step_budget` the graph routes early to validate/report. No unbounded looping.
- RAW SOURCE IS NEVER PERSISTED — only minimal code excerpts embedded in a finding's evidence are stored; whole files stay on-box.
- Every finding carries a `confidence` (`confirmed` | `tentative` | `unconfirmed`). Unconfirmed findings are marked, not dropped.
- Validation = static data/control-flow reasoning + a generated PoC; sandboxed execution is attempted when the PoC is self-contained and safe; a confirmed run of the PoC raises confidence to `confirmed`.
- Each finding card includes severity (CVSS-ish 0–10 + label), location (file:line), evidence (the exact validation step shown), remediation text, and a suggested code patch/diff.
- Findings are persisted the moment they are validated so the SSE stream and a page refresh show identical state.
- Cost is a first-class goal: recon/hunt use the cheaper model tier; validation uses the higher-reasoning tier (both env-configurable).

## Success Criteria
- [ ] Running against a seeded vulnerable repo produces ≥1 validated finding in each of at least three of the four categories.
- [ ] Each finding card has non-empty severity, file:line location, evidence, remediation, and a suggested patch.
- [ ] The run never exceeds `step_budget` steps (assert `step_count <= step_budget`).
- [ ] `assessment_runs` records non-zero prompt/completion tokens and a computed est. cost USD after the run.
- [ ] No row in `findings` and no persisted field contains a full source file (only bounded excerpts).
- [ ] Findings appear in the SSE stream and are identical to those returned by `GET /engagements/{id}/findings` after completion.
- [ ] A run against a repo with a known-CVE dependency manifest flags that dependency in the `vuln_deps` category.
