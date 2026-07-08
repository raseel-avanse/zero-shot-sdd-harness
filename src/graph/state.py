from typing import TypedDict


class AgentState(TypedDict, total=False):
    """Bounded security-assessment pipeline state (see spec/agent.md)."""

    # Identity
    run_id: str
    engagement_id: str

    # Input (from engagement + scope_record)
    target_type: str              # repo | live_app  (routes the graph, Phase 2)
    target_path: str              # repo path OR live-app base URL (target_ref)
    scope_allowlist: list[str]
    non_destructive_only: bool

    # Control / budget
    step_budget: int
    step_count: int
    current_phase: str            # recon | prioritize | hunt | validate | report
    current_category: str | None

    # Pipeline data
    recon: dict                   # {files, languages, manifests}
    priorities: list[str]         # ordered categories still to hunt
    candidate_findings: list[dict]
    findings: list[dict]          # validated (also persisted as produced)
    suggestions: list[str]        # proactive next-probe suggestions (Phase 3, report node)

    # Cost accounting
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float

    # Output / status
    status: str                   # running | completed | failed
    error: str | None
