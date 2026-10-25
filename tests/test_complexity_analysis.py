from __future__ import annotations

import pytest
from pydantic import ValidationError

from issuepilot.github.models import Issue
from issuepilot.graph.nodes.complexity_analysis import analyze_complexity
from issuepilot.graph.pipeline import run_pipeline
from issuepilot.models.complexity import ComplexityAssessment
from issuepilot.models.issue_context import IssueContext, IssueContextAnalysis


def _issue() -> Issue:
    return Issue(
        number=42,
        title="Improve error handling",
        body="Errors are swallowed silently in the parser.",
        state="open",
        labels=["good first issue"],
        author="octocat",
        comment_count=0,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        html_url="https://github.com/octo/hello/issues/42",
    )


def _assessment(score: int) -> ComplexityAssessment:
    return ComplexityAssessment(
        code_complexity=score,
        components_affected=score,
        required_technical_knowledge=score,
        testing_complexity=score,
        dependencies=score,
        requirement_ambiguity=score,
        effort_estimate="half a day",
        required_skills=["Python", "pytest"],
        rationale="Small, well-scoped change.",
    )


ANALYSIS = IssueContextAnalysis(
    summary="Surface parser errors instead of swallowing them.",
    stated_requirements=["Raise on parse failure"],
    ambiguities=["Which exception type?"],
    reasoning="Explicit in the body.",
)


class _StubStructured:
    def __init__(self, result: object) -> None:
        self.result = result
        self.received: list[tuple[str, str]] | None = None

    def invoke(self, messages: list[tuple[str, str]]) -> object:
        self.received = messages
        return self.result


class _StubChatModel:
    """Returns the canned result matching whichever schema a node binds."""

    def __init__(self, by_schema: dict[type, object]) -> None:
        self.by_schema = by_schema
        self.structured: dict[type, _StubStructured] = {}

    def with_structured_output(self, schema: type) -> _StubStructured:
        self.structured[schema] = _StubStructured(self.by_schema[schema])
        return self.structured[schema]


@pytest.mark.parametrize("score,difficulty", [(1, "Easy"), (3, "Medium"), (5, "Difficult")])
def test_difficulty_comes_from_rubric(score: int, difficulty: str) -> None:
    model = _StubChatModel({ComplexityAssessment: _assessment(score)})

    report = analyze_complexity(_issue(), IssueContext(analysis=ANALYSIS), chat_model=model)

    assert report.result.difficulty == difficulty
    assert report.result.overall_score == float(score)
    assert report.effort_estimate == "half a day"
    assert report.required_skills == ["Python", "pytest"]


def test_prompt_carries_rubric_and_investigation() -> None:
    model = _StubChatModel({ComplexityAssessment: _assessment(2)})

    analyze_complexity(_issue(), IssueContext(analysis=ANALYSIS), chat_model=model)

    system_msg, human_msg = model.structured[ComplexityAssessment].received
    assert "Complexity Analysis Agent" in system_msg[1]
    assert "How intricate is the code" in system_msg[1]  # rubric description from rubric.yaml
    assert "Surface parser errors" in human_msg[1]
    assert "Which exception type?" in human_msg[1]


def test_assessment_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        ComplexityAssessment(**{**_assessment(3).model_dump(), "code_complexity": 7})


def test_pipeline_runs_both_agents() -> None:
    model = _StubChatModel({IssueContextAnalysis: ANALYSIS, ComplexityAssessment: _assessment(1)})

    result = run_pipeline(_issue(), chat_model=model)

    assert result.context.analysis == ANALYSIS
    assert result.complexity.result.difficulty == "Easy"
