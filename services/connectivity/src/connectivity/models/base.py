"""Base record model shared across all SamKnows test types."""

from datetime import datetime

from pydantic import BaseModel, Field


class SKBaseRecord(BaseModel):
    """Base fields present in all SamKnows test records."""

    # VMO2 enrichment columns
    customer_id: str | None = Field(default=None)
    account_number: str | None = Field(default=None)
    line_id: str | None = Field(default=None)
    cm_mac: str | None = Field(default=None)
    hub: str | None = Field(default=None)
    technology: str | None = Field(default=None)
    package_name: str | None = Field(default=None)
    postcode_outcode: str | None = Field(default=None)
    cpe_type: str | None = Field(default=None)

    # SK Data Stream Dictionary fields
    dtime: datetime = Field(description="Test completion time in unit local time")
    dtime_utc: datetime = Field(description="Test completion time in UTC")
    processed_at: datetime | None = Field(default=None)
    unit_id: int = Field(description="Unique unit identifier")
    base: str = Field(description="Hardware type")
    successes: int = Field(default=1)
    failures: int = Field(default=0)
    mac: str = Field(description="Unit MAC address")
    target: str | None = Field(default=None)
    address: str | None = Field(default=None)
    ip_version: int | None = Field(default=None)
