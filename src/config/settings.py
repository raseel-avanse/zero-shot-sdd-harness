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


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
