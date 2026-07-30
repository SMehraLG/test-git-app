"""Connectivity scoring: pure functions for subscores, weighting, and band mapping."""

from connectivity.scoring._score import (
    STATUS_BANDS,
    WEIGHTS,
    composite_score,
    download_subscore,
    latency_subscore,
    score_to_status,
    upload_subscore,
)

__all__ = [
    "STATUS_BANDS",
    "WEIGHTS",
    "composite_score",
    "download_subscore",
    "latency_subscore",
    "score_to_status",
    "upload_subscore",
]
