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
