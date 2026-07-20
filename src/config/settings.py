from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./data/agent.db")
    log_level: str = Field(default="INFO")

    # LLM provider — auto-detected from whichever key is set if left blank
    llm_provider: str = Field(default="")   # "anthropic" | "gemini"
    llm_model: str = Field(default="")      # uses provider default when blank

    # Provider keys — set exactly one
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")

    # Model tiers (env: AGENT_LLM_MODEL_FAST / AGENT_LLM_MODEL_SMART).
    # Read defensively by llm/cost.py; blank falls back to provider defaults.
    # NOTE: the provided Gemini key is free-tier. *-pro models have a 0 quota
    # and gemini-2.5-flash a very small daily cap there, so both tiers default
    # to flash-lite (a larger free-tier bucket) so runs complete. Override
    # AGENT_LLM_MODEL_FAST/SMART with flash/pro models on a paid key.
    llm_model_fast: str = Field(default="gemini-flash-lite-latest")
    llm_model_smart: str = Field(default="gemini-flash-lite-latest")

    # Bounded agent step budget per assessment run (env: AGENT_STEP_BUDGET).
    step_budget: int = Field(default=40)

    # ---- Live-app probing (Phase 2) — SAFETY-CRITICAL guard knobs. ----
    # Only these HTTP verbs may EVER be issued against a live target. This is
    # an in-code allowlist (never prompt-driven); mutating verbs are refused.
    probe_allowed_methods: list[str] = Field(
        default_factory=lambda: ["GET", "HEAD", "OPTIONS"]
    )
    # Hard cap on the number of requests a single probe session may issue
    # (anti-DoS; bounds cost + blast radius).
    probe_max_requests: int = Field(default=20)
    # Per-request timeout in seconds (anti-hang / anti-DoS).
    probe_timeout_seconds: float = Field(default=10.0)
    # Bound on how much response body we retain as a bounded excerpt — never a
    # full dump; keeps prompts small and avoids persisting large/raw payloads.
    probe_max_body_bytes: int = Field(default=2048)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
