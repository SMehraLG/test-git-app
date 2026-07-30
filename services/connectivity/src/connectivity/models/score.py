"""Response models for the customer connectivity-score endpoint."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ConnectivityStatus(StrEnum):
    """Upper-inclusive status band derived from the composite score."""

    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class MetricScore(BaseModel):
    """Per-component sub-score and sample count for one metric type."""

    sub_score: float = Field(ge=0.0, le=100.0)
    sample_count: int = Field(ge=0)


class ConnectivityScorePayload(BaseModel):
    """Derived-only payload for a successful connectivity-score response.

    Contains no raw measurement rows, device or line identifiers, or
    internal operator identifiers — only aggregate and derived fields.
    """

    customer_id: str
    score: float = Field(ge=0.0, le=100.0)
    status: ConnectivityStatus
    window_start: datetime
    window_end: datetime
    measurements_considered: int = Field(ge=0)
    download: MetricScore | None = Field(default=None)
    upload: MetricScore | None = Field(default=None)
    latency: MetricScore | None = Field(default=None)


class ConnectivityScoreResponse(BaseModel):
    """CASAS data envelope wrapping the connectivity-score success payload."""

    data: ConnectivityScorePayload


class ErrorDetail(BaseModel):
    """Single error entry in the CASAS error envelope."""

    message: str
    code: str


class ErrorResponse(BaseModel):
    """CASAS error envelope returned on failure; failure is signalled via HTTP status code."""

    errors: list[ErrorDetail]
