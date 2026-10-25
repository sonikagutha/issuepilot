from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator

Difficulty = Literal["Easy", "Medium", "Difficult"]

DIMENSIONS: tuple[str, ...] = (
    "code_complexity",
    "components_affected",
    "required_technical_knowledge",
    "testing_complexity",
    "dependencies",
    "requirement_ambiguity",
)


class DimensionScores(BaseModel):
    """Raw 1-5 scores for each rubric dimension, as produced by the
    Complexity Analysis Agent from the evidence gathered upstream."""

    code_complexity: int
    components_affected: int
    required_technical_knowledge: int
    testing_complexity: int
    dependencies: int
    requirement_ambiguity: int

    @field_validator("*")
    @classmethod
    def _in_range(cls, value: int) -> int:
        if not 1 <= value <= 5:
            raise ValueError("dimension scores must be between 1 and 5")
        return value


class RubricConfig(BaseModel):
    """Weights and difficulty thresholds, loaded from config/rubric.yaml.

    Kept as data rather than hard-coded constants so tuning the rubric
    never requires touching Python.
    """

    weights: dict[str, float]
    easy_max: float
    medium_max: float

    @classmethod
    def load(cls, path: Path) -> "RubricConfig":
        raw = yaml.safe_load(path.read_text())
        try:
            weights = {dim: raw["dimensions"][dim]["weight"] for dim in DIMENSIONS}
        except KeyError as exc:
            raise ValueError(f"rubric config at {path} is missing dimension {exc}") from exc
        return cls(
            weights=weights,
            easy_max=raw["thresholds"]["easy_max"],
            medium_max=raw["thresholds"]["medium_max"],
        )


class ComplexityResult(BaseModel):
    scores: DimensionScores
    overall_score: float
    difficulty: Difficulty


def score(dimension_scores: DimensionScores, rubric: RubricConfig) -> ComplexityResult:
    total_weight = sum(rubric.weights.values())
    if total_weight <= 0:
        raise ValueError("rubric weights must sum to a positive number")

    weighted_sum = sum(
        getattr(dimension_scores, dim) * rubric.weights[dim] for dim in DIMENSIONS
    )
    overall = round(weighted_sum / total_weight, 2)

    return ComplexityResult(scores=dimension_scores, overall_score=overall, difficulty=_label(overall, rubric))


def _label(overall_score: float, rubric: RubricConfig) -> Difficulty:
    if overall_score <= rubric.easy_max:
        return "Easy"
    if overall_score <= rubric.medium_max:
        return "Medium"
    return "Difficult"
