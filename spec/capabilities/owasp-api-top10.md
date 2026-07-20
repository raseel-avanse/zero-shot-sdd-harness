# Capability: OWASP API Security Top 10 (2023) Assessment

> Phase 4. A structured assessment PROFILE for `live_app` (API) targets that walks all ten OWASP API Security Top 10 (2023) categories, in place of the existing "General" live-probing walk. Reuses the Phase 2 non-destructive live path (recon → prioritize → live_hunt → validate → report) with an OWASP-API category taxonomy and profile-specific prompts. Strictly read-only, in-code scope/verb/budget guarded.

## What It Does
When a user creates a `live_app` engagement they pick an assessment profile: **General** (the existing generic live probing) or **OWASP API Top 10**. Under the OWASP profile the agent hunts each of the ten OWASP API Security Top 10 (2023) categories against the authorized API, optionally driven by a supplied OpenAPI/Swagger definition for endpoint enumeration, and produces validated finding cards tagged with the canonical OWASP API category ID + title. All existing behaviour (validate-before-report, streaming, token/cost, export, next-probe suggestions, same-pattern grouping, finding lifecycle) applies unchanged.

The ten categories (canonical IDs/titles, 2023):

| Machine key | OWASP ref (surfaced on findings) |
|-------------|----------------------------------|
| `api1_bola` | API1:2023 — Broken Object Level Authorization |
| `api2_broken_auth` | API2:2023 — Broken Authentication |
| `api3_bopla` | API3:2023 — Broken Object Property Level Authorization |
| `api4_resource_consumption` | API4:2023 — Unrestricted Resource Consumption |
| `api5_bfla` | API5:2023 — Broken Function Level Authorization |
| `api6_sensitive_flows` | API6:2023 — Unrestricted Access to Sensitive Business Flows |
| `api7_ssrf` | API7:2023 — Server Side Request Forgery |
| `api8_misconfig` | API8:2023 — Security Misconfiguration |
| `api9_inventory` | API9:2023 — Improper Inventory Management |
| `api10_unsafe_consumption` | API10:2023 — Unsafe Consumption of APIs |

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| engagement_id | string | UI/API | yes |
| target_type | must be `live_app` | engagement | yes |
| assessment_profile | enum `general` \| `owasp_api` | scope form (new-engagement) | yes (default `general`) |
| target_ref (base URL) | string | scope_record allowlist host | yes |
| api_spec_ref | string (OpenAPI/Swagger URL **or** local file path) or null | scope form | no (falls back to light discovery) |
| step_budget | int (optional override) | run start | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| OWASP-tagged findings | Finding rows (with `owasp_api_ref`) | Postgres + SSE stream |
| OWASP API Top 10 coverage | per-category { hunted?, finding_count } derived from findings | `GET /engagements/{id}/findings` + run view |
| enumerated endpoints | in-run `recon.endpoints` (ephemeral) | LangGraph state / LangSmith only |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Target HTTP API (read-only) | GET/HEAD/OPTIONS only, host- + budget-guarded probes for evidence | skip probe, continue (guard raises before any request) |
| OpenAPI/Swagger source (URL or file) | fetch/read + parse spec for endpoint list (host-guarded if a URL) | fall back to light base-URL discovery; log; never fatal |
| Gemini | per-OWASP-category hunt (fast tier) + validate (smart tier) reasoning | retry w/ backoff, then handle_error |
| PostgreSQL | persist findings + run counters | fatal on loss |

## Business Rules
- **Non-destructive, read-only ONLY — enforced in code, not by prompt.** Every probe goes through the existing `tools.http_probe.Prober`: the verb guard (GET/HEAD/OPTIONS only — mutating verbs can never be enabled), the host allowlist guard (`scope_guard.check_live` — off-host probes refused before any request), and the per-session request-budget guard (anti-DoS). Redirects are not followed. These guards are unchanged and authoritative regardless of LLM output.
- **API4 (Unrestricted Resource Consumption) is a BOUNDED, SAFE probe — never a DoS/flood.** It only checks for the *absence* of protective signals (missing `RateLimit`/`Retry-After`/`X-RateLimit-*` headers, missing pagination bounds / unbounded list responses, missing size limits advertised in the OpenAPI spec). It never issues high-volume traffic; the request-budget guard caps total requests.
- **BOLA (API1) / BFLA (API5) / auth (API2) tests are safe, evidence-gathering probes within scope only** — e.g. requesting object/function endpoints with and without credentials and comparing status/shape, probing for predictable/enumerable IDs on GET endpoints. They NEVER perform destructive or state-changing mutations (no POST/PUT/PATCH/DELETE — the verb guard forbids it) and stay on the allowlisted host.
- **SSRF (API7)** is probed only by inspecting whether URL-accepting parameters are documented/exposed and reasoning about them from responses to safe GET requests — Sentinel never asks the target to fetch an attacker-controlled or internal URL.
- The OWASP category taxonomy REPLACES the four generic vuln classes for the hunt loop ONLY when `assessment_profile = owasp_api`; the `general` profile is unchanged.
- Optional OpenAPI/Swagger definition drives endpoint enumeration when supplied (URL host-guarded like any probe, or a local file path). **Raw spec content is NOT persisted** — only the derived endpoint list is held in ephemeral run state, and only endpoints/paths that appear in a finding's `location`/`evidence` are stored (bounded excerpts only), consistent with the existing no-raw-persistence rule in `spec/data.md`.
- Findings carry the OWASP API category ID+title in the new `owasp_api_ref` field IN ADDITION to the existing severity/CVSS/confidence/location(endpoint)/evidence(PoC)/remediation fields; `category` holds the machine key (`api1_bola`…`api10_unsafe_consumption`). See `spec/data.md`.
- The OWASP profile is only selectable for `live_app` engagements; a `repo` engagement ignores it (stays on the repo path).

## Success Criteria
- [ ] Creating a `live_app` engagement with `assessment_profile=owasp_api` persists the profile (and optional `api_spec_ref`) on the engagement.
- [ ] A run under the OWASP profile hunts the OWASP API category taxonomy (not the four generic classes) and produces validated findings whose `owasp_api_ref` is one of the ten canonical `APIn:2023 — …` strings.
- [ ] Against the seeded vulnerable fixture API, the run yields ≥3 validated OWASP-tagged findings including at least API1:2023 (BOLA), API2:2023 (Broken Authentication), and API8:2023 (Security Misconfiguration).
- [ ] Only read-only verbs (GET/HEAD/OPTIONS) are ever issued (verified by request log); a mutating verb and an out-of-scope host are both refused in code before any request.
- [ ] Supplying an OpenAPI URL/file enumerates its documented endpoints for the walk; omitting it falls back to light base-URL discovery and still runs. Raw spec content is not written to Postgres.
- [ ] `step_count <= step_budget`; token/cost is non-zero and accumulated; findings stream over SSE with the OWASP badge.
