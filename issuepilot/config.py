from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


Provider = Literal["anthropic", "openai", "google", "gemma"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    github_token: str
    github_api_base: str = "https://api.github.com"

    llm_provider: Provider = "anthropic"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    openai_model: str = "gpt-4o-mini"
    google_model: str = "gemini-3.6-flash"
    # Gemma runs on the Gemini API with the same GOOGLE_API_KEY.
    gemma_model: str = "gemma-4-26b-a4b-it"

    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "issuepilot"

    cache_db_path: Path = Path(".issuepilot/cache.db")
    trace_db_path: Path = Path(".issuepilot/traces.db")
    app_db_path: Path = Path(".issuepilot/app.db")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Process-wide cached Settings instance, loaded from .env on first use."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
