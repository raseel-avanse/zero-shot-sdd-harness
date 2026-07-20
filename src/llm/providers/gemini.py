import logging
import re
import time

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

log = logging.getLogger("agent.llm.gemini")

# Free-tier Gemini enforces a per-minute request cap (e.g. 15/min). A long
# assessment can burst past it, so retry 429s with a bounded backoff that
# honors the server's suggested retryDelay when present.
_MAX_RETRIES = 4
_MAX_BACKOFF_SECONDS = 30.0


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    """Seconds to wait before retrying a 429, from the server hint or backoff."""
    m = re.search(r"retry(?:Delay)?['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)", str(exc))
    if m:
        return min(float(m.group(1)) + 1.0, _MAX_BACKOFF_SECONDS)
    return min(2.0 ** attempt, _MAX_BACKOFF_SECONDS)


class GeminiProvider:
    DEFAULT_MODEL = "gemini-3.1-pro"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def _generate_with_retry(self, *, model: str, contents: str, config):
        """Call Gemini, retrying rate-limit (429) errors with bounded backoff."""
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return self._client.models.generate_content(
                    model=model, contents=contents, config=config
                )
            except genai_errors.ClientError as exc:
                status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                if status != 429 or attempt == _MAX_RETRIES:
                    raise
                delay = _retry_delay_seconds(exc, attempt)
                log.warning(
                    "gemini 429 rate-limited; retrying in %.1fs (attempt %d/%d)",
                    delay, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(delay)

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
        response = self._generate_with_retry(
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
