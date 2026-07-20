# Capability: Scope-Gated Engagement

## What It Does
Creates a security engagement bound to an authorization/scope record and enforces that scope IN CODE — every assessment target and tool operation is refused unless it falls inside the recorded allowlist.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| name | string | scope form (UI) | yes |
| target_type | enum `repo` \| `live_app` | scope form | yes (Phase 1: `repo` only) |
| target_ref | string (local repo path; later: base URL) | scope form | yes |
| authorized_targets | string[] (allowlist: absolute repo paths / hosts) | scope form | yes |
| rules_of_engagement | string | scope form | yes |
| authorized_by | string | scope form | yes |
| non_destructive_only | bool | scope form (defaults true) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| engagement | Engagement row | Postgres (`engagements`) |
| scope_record | ScopeRecord row (1:1 with engagement) | Postgres (`scope_records`) |
| allowlist decision | allow / refuse (per target check) | agent graph `enforce_scope` node + tool guards |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| PostgreSQL | insert engagement + scope_record in one transaction | return 500, no partial write |

## Business Rules
- No assessment run may start unless the engagement has a scope_record.
- The `enforce_scope` node is the graph entry point; a target outside `authorized_targets` sets `state.error` and routes to `handle_error` — the run never touches out-of-scope files.
- Scope enforcement is a pure in-code allowlist check (path containment / host match), never delegated to the LLM prompt.
- Phase 1 restricts `target_type` to `repo`; a `live_app` value is rejected at the API with a clear "not yet available" error.
- `non_destructive_only` must be true for any `live_app` target (enforced from Phase 2).

## Success Criteria
- [ ] Creating an engagement with a scope form persists exactly one engagement + one scope_record atomically.
- [ ] Starting a run whose `target_ref` is not contained in `authorized_targets` fails fast with a scope-violation error and produces zero findings.
- [ ] A run whose target IS in the allowlist passes the gate and proceeds to recon.
- [ ] Submitting `target_type=live_app` in Phase 1 returns a 400 "not yet available" error.
