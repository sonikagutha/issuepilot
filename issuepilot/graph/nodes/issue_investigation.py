from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from issuepilot.config import Settings
from issuepilot.github.models import Issue
from issuepilot.llm.factory import build_chat_model
from issuepilot.llm.prompts import load_prompt
from issuepilot.models.issue_context import IssueContext, IssueContextAnalysis
from issuepilot.observability.trace_store import TraceStore, trace

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

_REFERENCE_RE = re.compile(r"(?<!\w)#(\d+)")


class StructuredChatModel(Protocol):
    """The one method this node needs from a chat model - lets tests
    inject a stub instead of a real langchain_anthropic/openai client."""

    def with_structured_output(self, schema: type[IssueContextAnalysis]) -> "_StructuredInvoker": ...


class _StructuredInvoker(Protocol):
    def invoke(self, messages: list[tuple[str, str]]) -> IssueContextAnalysis: ...


def extract_referenced_numbers(*texts: str | None, exclude: int | None = None) -> list[int]:
    """Pull #123-style issue/PR references out of free text.

    Deliberately not an LLM's job: exact number extraction is exactly
    the kind of thing a regex does perfectly and a model occasionally
    hallucinates.
    """
    numbers: list[int] = []
    seen: set[int] = set()
    for text in texts:
        for match in _REFERENCE_RE.finditer(text or ""):
            number = int(match.group(1))
            if number == exclude or number in seen:
                continue
            seen.add(number)
            numbers.append(number)
    return numbers


def investigate_issue(
    issue: Issue,
    *,
    chat_model: "BaseChatModel | StructuredChatModel | None" = None,
    settings: Settings | None = None,
    trace_store: TraceStore | None = None,
) -> IssueContext:
    prompt = load_prompt("issue_investigation")
    model = chat_model or build_chat_model(settings)
    structured_model = model.with_structured_output(IssueContextAnalysis)

    comments_text = "\n\n".join(f"@{c.author}: {c.body}" for c in issue.comments)
    user_message = (
        f"Title: {issue.title}\n"
        f"Labels: {', '.join(issue.labels) or '(none)'}\n\n"
        f"Body:\n{issue.body or '(empty)'}\n\n"
        f"Comments:\n{comments_text or '(none)'}"
    )

    if trace_store is not None:
        with trace(trace_store, "issue_investigation", prompt.version):
            analysis = structured_model.invoke([("system", prompt.system), ("human", user_message)])
    else:
        analysis = structured_model.invoke([("system", prompt.system), ("human", user_message)])

    referenced_numbers = extract_referenced_numbers(issue.body, comments_text, exclude=issue.number)

    return IssueContext(analysis=analysis, referenced_numbers=referenced_numbers)
