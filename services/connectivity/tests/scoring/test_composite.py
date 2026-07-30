"""Unit tests for the weighted composite score function."""

import pytest

from connectivity.scoring.composite import composite_score


class TestCompositeScore:
    def test_all_perfect_gives_100(self) -> None:
        assert composite_score(download=100.0, upload=100.0, latency=100.0) == 100.0

    def test_all_zero_gives_zero(self) -> None:
        assert composite_score(download=0.0, upload=0.0, latency=0.0) == 0.0

    def test_all_absent_gives_zero(self) -> None:
        assert composite_score() == 0.0

    def test_weighted_average_all_present(self) -> None:
        # download=100 (w=0.5), upload=0 (w=0.2), latency=0 (w=0.3)
        # expected = 100*0.5 + 0*0.2 + 0*0.3 = 50.0
        assert composite_score(download=100.0, upload=0.0, latency=0.0) == pytest.approx(50.0)

    def test_only_download_present(self) -> None:
        # only download present → full weight → score = download score
        assert composite_score(download=80.0) == pytest.approx(80.0)

    def test_only_upload_present(self) -> None:
        assert composite_score(upload=70.0) == pytest.approx(70.0)

    def test_only_latency_present(self) -> None:
        assert composite_score(latency=60.0) == pytest.approx(60.0)

    def test_download_and_upload_absent_latency(self) -> None:
        # download(w=0.5) and upload(w=0.2) present; latency absent
        # redistributed weights: download=0.5/0.7, upload=0.2/0.7
        # score = (0.5*100 + 0.2*0) / 0.7 = 50/0.7 ≈ 71.43
        result = composite_score(download=100.0, upload=0.0)
        assert result == pytest.approx(50.0 / 0.7, rel=1e-6)

    def test_download_and_latency_absent_upload(self) -> None:
        # download(w=0.5) and latency(w=0.3) present; upload absent
        # total_weight = 0.8
        # score = (0.5*80 + 0.3*60) / 0.8 = (40 + 18) / 0.8 = 72.5
        result = composite_score(download=80.0, latency=60.0)
        assert result == pytest.approx(72.5)

    def test_upload_and_latency_absent_download(self) -> None:
        # upload(w=0.2) and latency(w=0.3) present; download absent
        # total_weight = 0.5
        # score = (0.2*50 + 0.3*100) / 0.5 = (10 + 30) / 0.5 = 80.0
        result = composite_score(upload=50.0, latency=100.0)
        assert result == pytest.approx(80.0)

    def test_output_clamped_to_100(self) -> None:
        assert composite_score(download=110.0, upload=110.0, latency=110.0) == 100.0

    def test_output_clamped_to_zero(self) -> None:
        assert composite_score(download=-10.0, upload=-10.0, latency=-10.0) == 0.0

    def test_uniform_scores_give_same_result_regardless_of_absent(self) -> None:
        # When all components share the same value, the composite equals that value
        # regardless of which are absent (weight redistribution preserves it).
        score = 65.0
        assert composite_score(download=score, upload=score, latency=score) == pytest.approx(score)
        assert composite_score(download=score, upload=score) == pytest.approx(score)
        assert composite_score(download=score, latency=score) == pytest.approx(score)
        assert composite_score(upload=score, latency=score) == pytest.approx(score)
