from __future__ import annotations

import pytest

from issuepilot.config import Settings
from issuepilot.llm.factory import build_chat_model


def test_anthropic_provider_builds_chat_anthropic() -> None:
    from langchain_anthropic import ChatAnthropic

    settings = Settings(
        github_token="x", llm_provider="anthropic", anthropic_api_key="sk-ant-test", anthropic_model="claude-sonnet-5"
    )

    model = build_chat_model(settings)

    assert isinstance(model, ChatAnthropic)
    assert model.model == "claude-sonnet-5"


def test_openai_provider_builds_chat_openai() -> None:
    from langchain_openai import ChatOpenAI

    settings = Settings(
        github_token="x", llm_provider="openai", openai_api_key="sk-test", openai_model="gpt-4o-mini"
    )

    model = build_chat_model(settings)

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-4o-mini"


def test_anthropic_missing_key_raises() -> None:
    settings = Settings(github_token="x", llm_provider="anthropic", anthropic_api_key=None)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_chat_model(settings)


def test_openai_missing_key_raises() -> None:
    settings = Settings(github_token="x", llm_provider="openai", openai_api_key=None)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_chat_model(settings)


def test_google_provider_builds_chat_google_generative_ai() -> None:
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = Settings(
        github_token="x", llm_provider="google", google_api_key="test-key", google_model="gemini-2.5-flash"
    )

    model = build_chat_model(settings)

    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.model == "gemini-2.5-flash"


def test_google_missing_key_raises() -> None:
    settings = Settings(github_token="x", llm_provider="google", google_api_key=None)

    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        build_chat_model(settings)


def test_gemma_provider_builds_google_client_with_gemma_model() -> None:
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = Settings(
        github_token="x", llm_provider="gemma", google_api_key="test-key", gemma_model="gemma-4-31b-it"
    )

    model = build_chat_model(settings)

    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.model == "gemma-4-31b-it"


def test_gemma_missing_key_raises() -> None:
    settings = Settings(github_token="x", llm_provider="gemma", google_api_key=None)

    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        build_chat_model(settings)


def test_available_providers_follow_configured_keys() -> None:
    from issuepilot.llm.factory import available_providers

    settings = Settings(github_token="x", anthropic_api_key=None, openai_api_key=None, google_api_key="k")

    assert available_providers(settings) == ["google", "gemma"]


def test_model_label() -> None:
    from issuepilot.llm.factory import model_label

    settings = Settings(github_token="x", llm_provider="gemma", gemma_model="gemma-4-26b-a4b-it")

    assert model_label(settings) == "Gemma 4 · gemma-4-26b-a4b-it"
