from __future__ import annotations

from typing import TYPE_CHECKING

from issuepilot.config import Settings
from issuepilot.github.models import Issue
from issuepilot.llm.factory import build_chat_model
from issuepilot.llm.prompts import load_prompt
from issuepilot.models.complexity import ComplexityAssessment, ComplexityReport
from issuepilot.models.issue_context import IssueContext
from issuepilot.observability.trace_store import TraceStore, trace
from issuepilot.rubric.scoring import DIMENSIONS, RUBRIC_PATH, DimensionScores, RubricConfig, score

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from issuepilot.graph.nodes.issue_investigation import StructuredChatModel


def analyze_complexity(
    issue: Issue,
    context: IssueContext,
    *,
    chat_model: "BaseChatModel | StructuredChatModel | None" = None,
    settings: Settings | None = None,
    trace_store: TraceStore | None = None,
    rubric: RubricConfig | None = None,
) -> ComplexityReport:
    rubric = rubric or RubricConfig.load(RUBRIC_PATH)
    prompt = load_prompt("complexity_analysis")
    model = chat_model or build_chat_model(settings)
    structured_model = model.with_structured_output(ComplexityAssessment)

    rubric_text = "\n".join(f"- {dim}: {rubric.descriptions.get(dim, '').strip()}" for dim in DIMENSIONS)
    system_message = f"{prompt.system}\n{rubric_text}"

    analysis = context.analysis
    user_message = (
        f"Title: {issue.title}\n"
        f"Labels: {', '.join(issue.labels) or '(none)'}\n"
        f"Comments: {issue.comment_count}\n\n"
        f"Body:\n{issue.body or '(empty)'}\n\n"
        f"Investigation summary: {analysis.summary}\n\n"
        f"Stated requirements:\n{_bullets(analysis.stated_requirements)}\n\n"
        f"Mentioned paths:\n{_bullets(analysis.likely_relevant_paths)}\n\n"
        f"Open questions:\n{_bullets(analysis.ambiguities)}"
    )
    messages = [("system", system_message), ("human", user_message)]

    if trace_store is not None:
        with trace(trace_store, "complexity_analysis", prompt.version):
            assessment = structured_model.invoke(messages)
    else:
        assessment = structured_model.invoke(messages)

    dimension_scores = DimensionScores(**assessment.model_dump(include=set(DIMENSIONS)))
    return ComplexityReport(
        result=score(dimension_scores, rubric),
        effort_estimate=assessment.effort_estimate,
        required_skills=assessment.required_skills,
        rationale=assessment.rationale,
    )


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "(none)"
