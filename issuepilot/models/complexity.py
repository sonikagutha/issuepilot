from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from issuepilot.rubric.scoring import ComplexityResult

EffortEstimate = Literal["under 2 hours", "half a day", "1-2 days", "several days"]


class ComplexityAssessment(BaseModel):
    """Structured output the Complexity Analysis Agent must produce.

    Only raw 1-5 dimension scores: the Easy/Medium/Difficult label is
    computed afterwards by the weighted rubric, never by the model.
    """

    code_complexity: int = Field(ge=1, le=5, description="1 = simple isolated logic, 5 = intricate/stateful code")
    components_affected: int = Field(ge=1, le=5, description="1 = single file, 5 = cross-cutting change")
    required_technical_knowledge: int = Field(
        ge=1, le=5, description="1 = generic skills, 5 = deep codebase/domain internals"
    )
    testing_complexity: int = Field(ge=1, le=5, description="1 = simple unit test, 5 = integration/E2E/manual")
    dependencies: int = Field(ge=1, le=5, description="1 = no blockers, 5 = hard external blockers")
    requirement_ambiguity: int = Field(ge=1, le=5, description="1 = precise spec/repro, 5 = vague ask")
    effort_estimate: EffortEstimate = Field(description="Rough time for a newcomer to this codebase")
    required_skills: list[str] = Field(
        default_factory=list, description="3-6 concrete skills/technologies a contributor needs"
    )
    rationale: str = Field(description="2-3 sentences justifying the scores, citing the issue")


class ComplexityReport(BaseModel):
    """Full output of the Complexity Analysis Agent: rubric result plus
    the model's qualitative effort/skills assessment."""

    result: ComplexityResult
    effort_estimate: EffortEstimate
    required_skills: list[str]
    rationale: str
