from config.settings import get_settings


def _make_provider():
    s = get_settings()
    provider = s.llm_provider

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
    def __init__(self) -> None:
        self._provider = _make_provider()

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self._provider.call_model(prompt, system=system)

    def complete(self, prompt: str, *, system: str | None = None, tier: str = "fast") -> dict:
        """Call the model for a tier and return text + token usage.

        Returns {text, prompt_tokens, completion_tokens, model}. Falls back to a
        zero-usage result for providers that do not expose usage metadata.
        """
        from llm.cost import model_for_tier

        model = model_for_tier(tier)
        provider = self._provider
        if hasattr(provider, "call_with_usage"):
            return provider.call_with_usage(prompt, system=system, model=model)
        text = provider.call_model(prompt, system=system)
        return {"text": text, "prompt_tokens": 0, "completion_tokens": 0, "model": model}
