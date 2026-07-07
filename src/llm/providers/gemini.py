from google import genai
from google.genai import types


class GeminiProvider:
    DEFAULT_MODEL = "gemini-3.1-pro"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self.call_with_usage(prompt, system=system)["text"]

    def call_with_usage(
        self, prompt: str, *, system: str | None = None, model: str | None = None
    ) -> dict:
        """Call Gemini and return text plus token usage for cost accounting."""
        used_model = model or self._model
        config = types.GenerateContentConfig(
            system_instruction=system,
        ) if system else None
        response = self._client.models.generate_content(
            model=used_model,
            contents=prompt,
            config=config,
        )
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
        return {
            "text": response.text or "",
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "model": used_model,
        }
