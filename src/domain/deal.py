from pydantic import BaseModel, Field


class Deal(BaseModel):
    """A single ranked deal surfaced by the research + rank pipeline."""

    rank: int = Field(ge=1)
    site: str
    price_inr: float = Field(ge=0)
    reason: str
    quality_label: str | None = None   # P2
    quality_reason: str | None = None  # P2
    source_url: str | None = None
