from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from issuepilot.config import Settings
from issuepilot.github.models import Issue
from issuepilot.graph.nodes.complexity_analysis import analyze_complexity
from issuepilot.graph.nodes.issue_investigation import investigate_issue
from issuepilot.llm.factory import build_chat_model
from issuepilot.models.complexity import ComplexityReport
from issuepilot.models.issue_context import IssueContext
from issuepilot.observability.trace_store import TraceStore

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from issuepilot.graph.nodes.issue_investigation import StructuredChatModel


class PipelineState(TypedDict, total=False):
    issue: Issue
    context: IssueContext
    complexity: ComplexityReport


class PipelineResult(BaseModel):
    context: IssueContext
    complexity: ComplexityReport


def run_pipeline(
    issue: Issue,
    *,
    chat_model: "BaseChatModel | StructuredChatModel | None" = None,
    settings: Settings | None = None,
    trace_store: TraceStore | None = None,
) -> PipelineResult:
    """Issue Investigation → Complexity Analysis, as a compiled LangGraph.

    One chat model is built up front and shared by every node, so a
    provider misconfiguration fails before any LLM call is made.
    """
    model = chat_model or build_chat_model(settings)

    def investigate(state: PipelineState) -> PipelineState:
        return {"context": investigate_issue(state["issue"], chat_model=model, trace_store=trace_store)}

    def complexity(state: PipelineState) -> PipelineState:
        return {
            "complexity": analyze_complexity(
                state["issue"], state["context"], chat_model=model, trace_store=trace_store
            )
        }

    graph = StateGraph(PipelineState)
    graph.add_node("issue_investigation", investigate)
    graph.add_node("complexity_analysis", complexity)
    graph.add_edge(START, "issue_investigation")
    graph.add_edge("issue_investigation", "complexity_analysis")
    graph.add_edge("complexity_analysis", END)

    final = graph.compile().invoke({"issue": issue})
    return PipelineResult(context=final["context"], complexity=final["complexity"])
