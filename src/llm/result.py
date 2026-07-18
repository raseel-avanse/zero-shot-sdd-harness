from dataclasses import dataclass, field


@dataclass
class LLMResult:
    """Structured result from an LLM call — text plus grounding sources and token usage."""

    text: str
    sources: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
