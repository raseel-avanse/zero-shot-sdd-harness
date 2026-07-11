from pydantic import BaseModel, Field

from domain.deal import Deal


class RunRequest(BaseModel):
    query_type: str = Field(default="name")
    query_text: str


class RunResponse(BaseModel):
    run_id: str
    status: str
    progress_step: str | None = None
    clarifying_question: str | None = None   # P2 field, always present for a stable contract
    deals: list[Deal] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_inr: float | None = None
    error: str | None = None
