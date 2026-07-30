"""Connectivity scoring — pure functions for subscores, composite scoring, and band mapping."""

from connectivity.scoring.bands import StatusBand, score_to_band
from connectivity.scoring.composite import composite_score
from connectivity.scoring.subscore import download_subscore, latency_subscore, upload_subscore

__all__ = [
    "StatusBand",
    "composite_score",
    "download_subscore",
    "latency_subscore",
    "score_to_band",
    "upload_subscore",
]
