from __future__ import annotations

import pytest

from issuepilot.llm.prompts import load_prompt


def test_load_real_issue_investigation_prompt() -> None:
    prompt = load_prompt("issue_investigation")

    assert prompt.version == "v1"
    assert "Issue Investigation Agent" in prompt.system


def test_load_prompt_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")
