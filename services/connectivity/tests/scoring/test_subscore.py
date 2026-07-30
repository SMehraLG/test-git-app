"""Unit tests for per-component subscore functions."""

import pytest

from connectivity.scoring.subscore import download_subscore, latency_subscore, upload_subscore


class TestDownloadSubscore:
    def test_full_performance_ratio(self) -> None:
        assert download_subscore(1.0) == 100.0

    def test_half_performance_ratio(self) -> None:
        assert download_subscore(0.5) == 50.0

    def test_zero_performance_ratio(self) -> None:
        assert download_subscore(0.0) == 0.0

    def test_over_provisioned_clamps_to_100(self) -> None:
        assert download_subscore(1.5) == 100.0

    def test_negative_ratio_clamps_to_zero(self) -> None:
        assert download_subscore(-0.1) == 0.0

    def test_fractional_ratio(self) -> None:
        assert download_subscore(0.75) == pytest.approx(75.0)


class TestUploadSubscore:
    def test_full_performance_ratio(self) -> None:
        assert upload_subscore(1.0) == 100.0

    def test_half_performance_ratio(self) -> None:
        assert upload_subscore(0.5) == 50.0

    def test_zero_performance_ratio(self) -> None:
        assert upload_subscore(0.0) == 0.0

    def test_over_provisioned_clamps_to_100(self) -> None:
        assert upload_subscore(2.0) == 100.0

    def test_negative_ratio_clamps_to_zero(self) -> None:
        assert upload_subscore(-1.0) == 0.0


class TestLatencySubscore:
    def test_rtt_equals_tier_gives_100(self) -> None:
        assert latency_subscore(20.0, 20.0) == 100.0

    def test_rtt_below_tier_clamps_to_100(self) -> None:
        assert latency_subscore(10.0, 20.0) == 100.0

    def test_rtt_double_tier_gives_50(self) -> None:
        assert latency_subscore(40.0, 20.0) == pytest.approx(50.0)

    def test_rtt_ten_times_tier(self) -> None:
        assert latency_subscore(200.0, 20.0) == pytest.approx(10.0)

    def test_zero_rtt_gives_100(self) -> None:
        assert latency_subscore(0.0, 20.0) == 100.0

    def test_negative_rtt_gives_100(self) -> None:
        assert latency_subscore(-5.0, 20.0) == 100.0

    def test_very_high_rtt_clamps_to_zero(self) -> None:
        assert latency_subscore(1_000_000.0, 20.0) == pytest.approx(0.0, abs=0.01)

    def test_invalid_tier_rtt_raises(self) -> None:
        with pytest.raises(ValueError, match="tier_rtt_ms must be positive"):
            latency_subscore(20.0, 0.0)

    def test_negative_tier_rtt_raises(self) -> None:
        with pytest.raises(ValueError, match="tier_rtt_ms must be positive"):
            latency_subscore(20.0, -10.0)
