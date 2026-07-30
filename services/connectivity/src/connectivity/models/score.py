"""Score response models for the customer connectivity-score endpoint.

Success responses use the ConnectivityScoreResponse data envelope.
Error responses use the ErrorResponse errors envelope (never inside a 200 body).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MetricBreakdown(BaseModel):
    """Normalised sub-score and measurement count for a single metric type."""

    sub_score: float = Field(
        ge=0.0,
        le=100.0,
        description="0-100 normalised sub-score for this metric",
    )
    sample_count: int = Field(
        ge=0,
        description="Measurements in the 30-day window contributing to this sub-score",
    )


class ComponentBreakdown(BaseModel):
    """Per-metric sub-scores; None when no measurements of that type exist in the window."""

    download: MetricBreakdown | None = None
    upload: MetricBreakdown | None = None
    latency: MetricBreakdown | None = None


class ScoreWindow(BaseModel):
    """Inclusive start and end of the trailing 30-day evaluation window (UTC)."""

    start: datetime
    end: datetime


class ConnectivityScorePayload(BaseModel):
    """Derived-only scoring payload; exposes no raw measurements or internal identifiers."""

    customer_id: str = Field(
        description="Opaque token echoed from the request path parameter",
    )
    score: float = Field(
        ge=0.0,
        le=100.0,
        description="Composite 0-100 connectivity score",
    )
    status: Literal["excellent", "good", "degraded", "critical"] = Field(
        description=(
            "Plain-language verdict derived from score bands: "
            ">=80 excellent, 60-<80 good, 40-<60 degraded, <40 critical"
        ),
    )
    window: ScoreWindow
    components: ComponentBreakdown
    measurements_considered: int = Field(
        ge=0,
        description="Total measurement count across all metric types in the 30-day window",
    )


class ConnectivityScoreResponse(BaseModel):
    """CASAS data envelope wrapping a successful connectivity-score payload."""

    data: ConnectivityScorePayload


class ErrorDetail(BaseModel):
    """Single entry in a CASAS error envelope."""

    message: str
    code: str


class ErrorResponse(BaseModel):
    """CASAS error envelope; returned with a non-2xx HTTP status, never in a 200 body."""

    errors: list[ErrorDetail]
