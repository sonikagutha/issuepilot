from __future__ import annotations

from issuepilot.github.models import Comment, Issue
from issuepilot.graph.nodes.issue_investigation import extract_referenced_numbers, investigate_issue
from issuepilot.models.issue_context import IssueContextAnalysis


def _issue(body: str, comments: list[Comment] | None = None, number: int = 42) -> Issue:
    return Issue(
        number=number,
        title="Improve error handling",
        body=body,
        state="open",
        labels=["bug"],
        author="octocat",
        comment_count=len(comments or []),
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        html_url="https://github.com/octo/hello/issues/42",
        comments=comments or [],
    )


def test_extract_referenced_numbers_finds_and_dedupes() -> None:
    numbers = extract_referenced_numbers("See #12 and also #99.", "Also related to #12, see #99 again.")

    assert numbers == [12, 99]


def test_extract_referenced_numbers_excludes_self_and_ignores_bare_hash() -> None:
    numbers = extract_referenced_numbers("This is issue #42 itself, unrelated to color #fff.", exclude=42)

    assert numbers == []


def test_extract_referenced_numbers_handles_none_text() -> None:
    assert extract_referenced_numbers(None, "#7") == [7]


class _StubStructuredModel:
    def __init__(self, result: IssueContextAnalysis) -> None:
        self._result = result
        self.received_messages: list[tuple[str, str]] | None = None

    def invoke(self, messages: list[tuple[str, str]]) -> IssueContextAnalysis:
        self.received_messages = messages
        return self._result


class _StubChatModel:
    def __init__(self, result: IssueContextAnalysis) -> None:
        self.structured = _StubStructuredModel(result)

    def with_structured_output(self, schema: type) -> _StubStructuredModel:
        assert schema is IssueContextAnalysis
        return self.structured


def test_investigate_issue_combines_llm_analysis_and_regex_references() -> None:
    analysis = IssueContextAnalysis(
        summary="Add retries to the HTTP client.",
        stated_requirements=["Retry on 5xx", "Exponential backoff"],
        likely_relevant_paths=["issuepilot/github/client.py"],
        ambiguities=["Max retry count not specified"],
        reasoning="The issue explicitly asks for retry behavior on server errors.",
    )
    stub_model = _StubChatModel(analysis)
    comment = Comment(id=1, author="alice", body="Related to #7 as well.", created_at="2026-01-01T00:00:00Z")
    issue = _issue(body="Please add retries. See #99 for context.", comments=[comment], number=42)

    context = investigate_issue(issue, chat_model=stub_model)

    assert context.analysis == analysis
    assert context.referenced_numbers == [99, 7]

    # prompt actually carried the issue content through to the model
    system_msg, human_msg = stub_model.structured.received_messages
    assert system_msg[0] == "system"
    assert "Issue Investigation Agent" in system_msg[1]
    assert human_msg[0] == "human"
    assert "Please add retries" in human_msg[1]
    assert "@alice" in human_msg[1]
