from config.settings import get_settings
from llm.result import LLMResult


def _make_provider(force: str | None = None):
    s = get_settings()
    provider = force or s.llm_provider

    # auto-detect from whichever key is set
    if not provider:
        if s.anthropic_api_key:
            provider = "anthropic"
        elif s.gemini_api_key:
            provider = "gemini"
        else:
            raise RuntimeError(
                "No LLM provider configured. Set AGENT_ANTHROPIC_API_KEY or "
                "AGENT_GEMINI_API_KEY in .env, or set AGENT_LLM_PROVIDER explicitly."
            )

    if provider == "anthropic":
        from llm.providers.anthropic import AnthropicProvider
        return AnthropicProvider(api_key=s.anthropic_api_key, model=s.llm_model)
    if provider == "gemini":
        from llm.providers.gemini import GeminiProvider
        return GeminiProvider(api_key=s.gemini_api_key, model=s.llm_model)

    raise RuntimeError(f"Unknown LLM provider: {provider!r}. Supported: anthropic, gemini")


class LLMClient:
    def __init__(self, provider: str | None = None) -> None:
        self._provider = _make_provider(provider)

    @property
    def model(self) -> str:
        return getattr(self._provider, "model", "")

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self._provider.call_model(prompt, system=system)

    def generate(
        self, prompt: str, *, system: str | None = None, grounding: bool = False
    ) -> LLMResult:
        """Grounded/structured call — provider must implement `generate` (Gemini)."""
        return self._provider.generate(prompt, system=system, grounding=grounding)
