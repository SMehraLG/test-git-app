"""Unit tests for the connectivity scoring module (pure functions, no I/O)."""

import pytest

from connectivity.scoring import (
    STATUS_BANDS,
    WEIGHTS,
    composite_score,
    download_subscore,
    latency_subscore,
    score_to_status,
    upload_subscore,
)


class TestWeightsAndBands:
    def test_weights_sum_to_one(self) -> None:
        assert sum(WEIGHTS.values()) == pytest.approx(1.0)

    def test_weights_keys(self) -> None:
        assert set(WEIGHTS.keys()) == {"download", "upload", "latency"}

    def test_bands_ordered_descending(self) -> None:
        thresholds = [t for t, _ in STATUS_BANDS]
        assert thresholds == sorted(thresholds, reverse=True)


class TestDownloadSubscore:
    def test_full_provisioned_scores_100(self) -> None:
        assert download_subscore(1.0) == pytest.approx(100.0)

    def test_above_provisioned_capped_at_100(self) -> None:
        assert download_subscore(1.5) == pytest.approx(100.0)

    def test_half_speed_scores_50(self) -> None:
        assert download_subscore(0.5) == pytest.approx(50.0)

    def test_zero_ratio_scores_0(self) -> None:
        assert download_subscore(0.0) == pytest.approx(0.0)

    def test_negative_ratio_clamped_to_0(self) -> None:
        assert download_subscore(-0.5) == pytest.approx(0.0)

    def test_quarter_speed_scores_25(self) -> None:
        assert download_subscore(0.25) == pytest.approx(25.0)


class TestUploadSubscore:
    def test_full_provisioned_scores_100(self) -> None:
        assert upload_subscore(1.0) == pytest.approx(100.0)

    def test_above_provisioned_capped_at_100(self) -> None:
        assert upload_subscore(2.0) == pytest.approx(100.0)

    def test_quarter_speed_scores_25(self) -> None:
        assert upload_subscore(0.25) == pytest.approx(25.0)

    def test_zero_ratio_scores_0(self) -> None:
        assert upload_subscore(0.0) == pytest.approx(0.0)


class TestLatencySubscore:
    def test_at_target_scores_100(self) -> None:
        assert latency_subscore(20.0, 20.0) == pytest.approx(100.0)

    def test_below_target_capped_at_100(self) -> None:
        assert latency_subscore(10.0, 20.0) == pytest.approx(100.0)

    def test_double_target_scores_50(self) -> None:
        assert latency_subscore(40.0, 20.0) == pytest.approx(50.0)

    def test_four_times_target_scores_25(self) -> None:
        assert latency_subscore(80.0, 20.0) == pytest.approx(25.0)

    def test_zero_rtt_scores_100(self) -> None:
        assert latency_subscore(0.0, 20.0) == pytest.approx(100.0)

    def test_very_high_rtt_approaches_0(self) -> None:
        assert latency_subscore(10_000.0, 20.0) == pytest.approx(0.2)


class TestCompositeScore:
    def test_all_100_gives_100(self) -> None:
        assert composite_score(100.0, 100.0, 100.0) == pytest.approx(100.0)

    def test_all_zero_gives_zero(self) -> None:
        assert composite_score(0.0, 0.0, 0.0) == pytest.approx(0.0)

    def test_all_none_gives_zero(self) -> None:
        assert composite_score(None, None, None) == pytest.approx(0.0)

    def test_known_weighted_result(self) -> None:
        # download=100 (w=0.5), upload=0 (w=0.2), latency=0 (w=0.3)
        # score = 100*0.5 + 0*0.2 + 0*0.3 = 50
        assert composite_score(100.0, 0.0, 0.0) == pytest.approx(50.0)

    def test_download_only_full_redistribution(self) -> None:
        # Only download present; its effective weight becomes 1.0
        assert composite_score(80.0, None, None) == pytest.approx(80.0)

    def test_upload_only_full_redistribution(self) -> None:
        assert composite_score(None, 60.0, None) == pytest.approx(60.0)

    def test_latency_only_full_redistribution(self) -> None:
        assert composite_score(None, None, 70.0) == pytest.approx(70.0)

    def test_download_and_latency_proportional_reweight(self) -> None:
        # upload absent; download=0.5, latency=0.3, total=0.8
        # download eff weight = 0.5/0.8 = 0.625, latency eff weight = 0.3/0.8 = 0.375
        # score = 100*0.625 + 0*0.375 = 62.5
        assert composite_score(100.0, None, 0.0) == pytest.approx(62.5)

    def test_download_and_upload_proportional_reweight(self) -> None:
        # latency absent; download=0.5, upload=0.2, total=0.7
        # download eff = 0.5/0.7, upload eff = 0.2/0.7
        # score = 0*(0.5/0.7) + 100*(0.2/0.7)
        expected = 100.0 * (0.2 / 0.7)
        assert composite_score(0.0, 100.0, None) == pytest.approx(expected)

    def test_upload_and_latency_proportional_reweight(self) -> None:
        # download absent; upload=0.2, latency=0.3, total=0.5
        # score = 100*(0.2/0.5) + 100*(0.3/0.5) = 40 + 60 = 100
        assert composite_score(None, 100.0, 100.0) == pytest.approx(100.0)

    def test_result_clamped_to_100(self) -> None:
        assert composite_score(200.0, 200.0, 200.0) == pytest.approx(100.0)

    def test_result_clamped_to_0(self) -> None:
        assert composite_score(-50.0, -50.0, -50.0) == pytest.approx(0.0)

    def test_deterministic_same_inputs(self) -> None:
        s1 = composite_score(75.0, 60.0, 80.0)
        s2 = composite_score(75.0, 60.0, 80.0)
        assert s1 == s2

    def test_deterministic_different_call_sites(self) -> None:
        inputs = (42.0, 55.0, 78.0)
        assert composite_score(*inputs) == composite_score(*inputs)


class TestScoreToStatus:
    # Boundary values (upper-inclusive: higher band wins)
    def test_80_is_excellent(self) -> None:
        assert score_to_status(80.0) == "excellent"

    def test_60_is_good(self) -> None:
        assert score_to_status(60.0) == "good"

    def test_40_is_degraded(self) -> None:
        assert score_to_status(40.0) == "degraded"

    # Interior values
    def test_100_is_excellent(self) -> None:
        assert score_to_status(100.0) == "excellent"

    def test_95_is_excellent(self) -> None:
        assert score_to_status(95.0) == "excellent"

    def test_79_9_is_good(self) -> None:
        assert score_to_status(79.9) == "good"

    def test_70_is_good(self) -> None:
        assert score_to_status(70.0) == "good"

    def test_59_9_is_degraded(self) -> None:
        assert score_to_status(59.9) == "degraded"

    def test_50_is_degraded(self) -> None:
        assert score_to_status(50.0) == "degraded"

    def test_39_9_is_critical(self) -> None:
        assert score_to_status(39.9) == "critical"

    def test_0_is_critical(self) -> None:
        assert score_to_status(0.0) == "critical"

    def test_returns_string(self) -> None:
        for score in (0.0, 40.0, 60.0, 80.0, 100.0):
            assert isinstance(score_to_status(score), str)
