from __future__ import annotations

from typing import TYPE_CHECKING

from issuepilot.config import Provider, Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


PROVIDER_NAMES: dict[Provider, str] = {
    "anthropic": "Claude",
    "openai": "OpenAI",
    "google": "Gemini",
    "gemma": "Gemma 4",
}


def available_providers(settings: Settings) -> list[Provider]:
    """Providers that have an API key configured, in display order."""
    keys: dict[Provider, str | None] = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "google": settings.google_api_key,
        "gemma": settings.google_api_key,
    }
    return [provider for provider, key in keys.items() if key]


def model_label(settings: Settings) -> str:
    """Human-readable 'Provider · model' for showing which model produced a result."""
    model = {
        "anthropic": settings.anthropic_model,
        "openai": settings.openai_model,
        "google": settings.google_model,
        "gemma": settings.gemma_model,
    }[settings.llm_provider]
    return f"{PROVIDER_NAMES[settings.llm_provider]} · {model}"


def build_chat_model(settings: Settings | None = None, *, temperature: float = 0.0) -> "BaseChatModel":
    """Provider-agnostic chat model factory.

    Every graph node asks this for a model instead of importing a
    provider SDK directly, so swapping providers (anthropic/openai/
    google/gemma) — or A/B-ing them in evals — never touches node logic,
    only LLM_PROVIDER in .env.
    """
    settings = settings or get_settings()

    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model_name=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            timeout=60.0,
        )

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
            timeout=60.0,
        )

    if settings.llm_provider == "google":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.google_model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
            timeout=60.0,
        )

    if settings.llm_provider == "gemma":
        # Gemma 4 on the Gemini API supports system prompts and json_schema
        # structured output (LangChain's default for this client), so the
        # nodes need no Gemma-specific handling.
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemma")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemma_model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
            timeout=120.0,
        )

    raise ValueError(f"unknown LLM provider: {settings.llm_provider}")
