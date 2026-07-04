from google import genai
from google.genai import types


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def _config(self, system: str | None, json_mode: bool):
        kwargs = {}
        if system:
            kwargs["system_instruction"] = system
        if json_mode:
            kwargs["response_mime_type"] = "application/json"
        return types.GenerateContentConfig(**kwargs) if kwargs else None

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._config(system, json_mode=False),
        )
        return response.text

    def call_model_with_usage(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> tuple[str, dict]:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._config(system, json_mode=json_mode),
        )
        usage = _extract_usage(response)
        return response.text, usage


def _extract_usage(response) -> dict:
    meta = getattr(response, "usage_metadata", None)
    prompt = int(getattr(meta, "prompt_token_count", 0) or 0) if meta else 0
    completion = int(getattr(meta, "candidates_token_count", 0) or 0) if meta else 0
    total = int(getattr(meta, "total_token_count", 0) or 0) if meta else 0
    if total == 0:
        total = prompt + completion
    return {"prompt": prompt, "completion": completion, "total": total}
