from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str

    # Input
    query_type: str                # "name" (P1) | "url" | "category" (P2)
    query_text: str
    clarify_answer: str | None     # P2 (resume)

    # Pipeline data (populated progressively by nodes)
    progress_step: str             # queued|searching|reviewing|ranking|assessing|done
    research_notes: str
    grounding_sources: list
    prompt_tokens: int
    completion_tokens: int

    # Control (clarify gate, P2)
    needs_clarification: bool
    clarifying_question: str | None

    # Output
    deals: list                    # [{rank, site, price_inr, reason, ...}]
    cost_inr: float
    status: str

    # Error
    error: str | None
