from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: int                          # DB runs row id
    dataset_id: str                      # in-memory dataframe key

    # Input
    question: str
    profile: dict
    sample: str

    # Pipeline data (populated progressively)
    code: str | None
    attempts: int
    last_traceback: str | None
    result_repr: str | None
    used_fallback: bool

    # Output
    answer: str | None
    method_note: str | None
    assumptions: list
    chart_spec: dict | None
    token_usage: dict                    # {prompt, completion, total} summed
    step_trace: list                     # ordered {step, status, attempt}

    # Control
    error: str | None
    checkpoint: str | None
