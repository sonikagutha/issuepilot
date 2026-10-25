from __future__ import annotations

from pydantic import BaseModel, Field


class IssueContextAnalysis(BaseModel):
    """Structured output the LLM must produce - bound via
    with_structured_output, never parsed from free text."""

    summary: str = Field(description="Concise 1-3 sentence restatement of what the issue is asking for")
    stated_requirements: list[str] = Field(
        default_factory=list, description="Explicit requirements stated in the issue or comments"
    )
    likely_relevant_paths: list[str] = Field(
        default_factory=list, description="File paths, modules, or symbols explicitly mentioned"
    )
    ambiguities: list[str] = Field(
        default_factory=list, description="Things left unclear or underspecified"
    )
    reasoning: str = Field(description="Brief rationale for the analysis above")


class IssueContext(BaseModel):
    """Full output of the Issue Investigation Agent: the LLM's qualitative
    analysis plus deterministically-extracted issue/PR references."""

    analysis: IssueContextAnalysis
    referenced_numbers: list[int] = Field(
        default_factory=list,
        description="Issue/PR numbers (#N) referenced in the body or comments, extracted by regex",
    )
