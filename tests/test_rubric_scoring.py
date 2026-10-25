from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from issuepilot.rubric.scoring import DIMENSIONS, DimensionScores, RubricConfig, score

RUBRIC_PATH = Path(__file__).resolve().parent.parent / "config" / "rubric.yaml"


def _scores(default: int = 3, **overrides: int) -> DimensionScores:
    values = {dim: default for dim in DIMENSIONS}
    values.update(overrides)
    return DimensionScores(**values)


def test_load_real_rubric_config_weights_sum_to_one() -> None:
    rubric = RubricConfig.load(RUBRIC_PATH)

    assert set(rubric.weights) == set(DIMENSIONS)
    assert sum(rubric.weights.values()) == pytest.approx(1.0)
    assert rubric.easy_max < rubric.medium_max


def test_all_ones_is_easy() -> None:
    rubric = RubricConfig.load(RUBRIC_PATH)

    result = score(_scores(default=1), rubric)

    assert result.overall_score == 1.0
    assert result.difficulty == "Easy"


def test_all_fives_is_difficult() -> None:
    rubric = RubricConfig.load(RUBRIC_PATH)

    result = score(_scores(default=5), rubric)

    assert result.overall_score == 5.0
    assert result.difficulty == "Difficult"


def test_all_threes_is_medium() -> None:
    rubric = RubricConfig.load(RUBRIC_PATH)

    result = score(_scores(default=3), rubric)

    assert result.overall_score == 3.0
    assert result.difficulty == "Medium"


def test_dimension_score_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        _scores(code_complexity=6)

    with pytest.raises(ValidationError):
        _scores(dependencies=0)


def test_thresholds_are_inclusive_at_the_boundary() -> None:
    two_dim_rubric = RubricConfig(
        weights={dim: (0.5 if dim in ("code_complexity", "components_affected") else 0.0) for dim in DIMENSIONS},
        easy_max=2.0,
        medium_max=3.5,
    )

    at_easy_boundary = score(_scores(default=1, code_complexity=2, components_affected=2), two_dim_rubric)
    at_medium_boundary = score(_scores(default=1, code_complexity=2, components_affected=5), two_dim_rubric)

    assert at_easy_boundary.overall_score == 2.0
    assert at_easy_boundary.difficulty == "Easy"
    assert at_medium_boundary.overall_score == 3.5
    assert at_medium_boundary.difficulty == "Medium"


def test_weights_need_not_sum_to_one() -> None:
    # weights are normalized by total_weight, so un-normalized configs
    # still produce a sane 1-5 overall score rather than something wild.
    unequal_rubric = RubricConfig(
        weights={dim: 2.0 for dim in DIMENSIONS},  # all equal, but not summing to 1
        easy_max=2.0,
        medium_max=3.5,
    )

    result = score(_scores(default=4), unequal_rubric)

    assert result.overall_score == 4.0


def test_missing_dimension_in_yaml_raises_clear_error(tmp_path: Path) -> None:
    broken = tmp_path / "rubric.yaml"
    broken.write_text(
        "dimensions:\n  code_complexity:\n    weight: 1.0\n"
        "thresholds:\n  easy_max: 2.0\n  medium_max: 3.5\n"
    )

    with pytest.raises(ValueError, match="missing dimension"):
        RubricConfig.load(broken)
