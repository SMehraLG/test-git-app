"""Unit tests for the score-to-status band mapping."""

import pytest

from connectivity.scoring.bands import score_to_band


class TestScoreToBand:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (100.0, "excellent"),
            (80.0, "excellent"),  # boundary: higher band wins
            (79.9, "good"),
            (75.0, "good"),
            (60.0, "good"),  # boundary: higher band wins
            (59.9, "degraded"),
            (50.0, "degraded"),
            (40.0, "degraded"),  # boundary: higher band wins
            (39.9, "critical"),
            (20.0, "critical"),
            (0.0, "critical"),
        ],
    )
    def test_band_thresholds(self, score: float, expected: str) -> None:
        assert score_to_band(score) == expected

    def test_negative_score_is_critical(self) -> None:
        assert score_to_band(-1.0) == "critical"

    def test_score_above_100_is_excellent(self) -> None:
        assert score_to_band(101.0) == "excellent"
