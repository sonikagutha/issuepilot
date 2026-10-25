from __future__ import annotations

from typing import TYPE_CHECKING

from issuepilot.config import Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


def build_chat_model(settings: Settings | None = None, *, temperature: float = 0.0) -> "BaseChatModel":
    """Provider-agnostic chat model factory.

    Every graph node asks this for a model instead of importing a
    provider SDK directly, so swapping providers (anthropic/openai/
    google) — or A/B-ing them in evals — never touches node logic,
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

    raise ValueError(f"unknown LLM provider: {settings.llm_provider}")
