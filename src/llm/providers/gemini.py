import time

from google import genai
from google.genai import types

from llm.result import LLMResult

# Substrings that indicate a transient error worth retrying (rate limit / 5xx / timeout).
_TRANSIENT = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "unavailable",
    "deadline",
    "timeout",
    "resource_exhausted",
    "rate limit",
    "overloaded",
)


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    @property
    def model(self) -> str:
        return self._model

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        """Backwards-compatible plain-text call (no grounding)."""
        return self.generate(prompt, system=system, grounding=False).text

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        grounding: bool = False,
        max_retries: int = 2,
    ) -> LLMResult:
        """Generate content, optionally with the native google_search grounding tool.

        Retries transient failures (429/5xx/timeout) with exponential backoff.
        Returns text + grounding source URLs + token usage.
        """
        tools = (
            [types.Tool(google_search=types.GoogleSearch())] if grounding else None
        )
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=tools,
        )

        delay = 2.0
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
                return self._to_result(response)
            except Exception as exc:  # noqa: BLE001 — provider boundary
                last_exc = exc
                if attempt < max_retries and self._is_transient(exc):
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        # unreachable, but keeps type checkers happy
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        s = str(exc).lower()
        return any(tok in s for tok in _TRANSIENT)

    @staticmethod
    def _to_result(response) -> LLMResult:
        text = getattr(response, "text", None) or ""

        prompt_tokens = 0
        completion_tokens = 0
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
            completion_tokens = getattr(usage, "candidates_token_count", 0) or 0

        sources: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            gm = getattr(candidates[0], "grounding_metadata", None)
            if gm is not None:
                for chunk in getattr(gm, "grounding_chunks", None) or []:
                    web = getattr(chunk, "web", None)
                    uri = getattr(web, "uri", None) if web is not None else None
                    if uri:
                        sources.append(uri)

        return LLMResult(
            text=text,
            sources=sources,
            prompt_tokens=int(prompt_tokens),
            completion_tokens=int(completion_tokens),
        )
