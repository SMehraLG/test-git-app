"""Scheduled test record models (SamKnows Data Stream Dictionary)."""

from pydantic import Field

from connectivity.models.base import SKBaseRecord


class HttpGetRecord(SKBaseRecord):
    """Download speed test (httpget) record."""

    bytes_sec_interval: int = Field(default=0)
    warmup_time: int = Field(default=0)
    threads: int = Field(default=1)
    bytes_total: int
    fetch_time: int
    sequence: int = Field(default=0)
    bytes_sec: int
    tcp_retransmissions: int = Field(default=0)
    warmup_bytes: int = Field(default=0)

    speed_mbps: float | None = Field(default=None)
    provisioned_mbps: float | None = Field(default=None)
    performance_ratio: float | None = Field(default=None)
    is_failure: bool | None = Field(default=None)
    is_degraded: bool | None = Field(default=None)
    is_high_retransmission: bool | None = Field(default=None)


class HttpPostRecord(SKBaseRecord):
    """Upload speed test (httppost) record."""

    bytes_sec_interval: int = Field(default=0)
    warmup_time: int = Field(default=0)
    threads: int = Field(default=1)
    bytes_total: int
    fetch_time: int
    sequence: int = Field(default=0)
    bytes_sec: int
    tcp_retransmissions: int = Field(default=0)
    warmup_bytes: int = Field(default=0)

    speed_mbps: float | None = Field(default=None)
    provisioned_mbps: float | None = Field(default=None)
    performance_ratio: float | None = Field(default=None)
    is_failure: bool | None = Field(default=None)
    is_degraded: bool | None = Field(default=None)
    is_high_retransmission: bool | None = Field(default=None)


class UdpLatencyRecord(SKBaseRecord):
    """UDP latency (ping) test record. RTT fields in microseconds."""

    rtt_avg: int
    rtt_min: int
    rtt_max: int
    rtt_std: int = Field(default=0)

    rtt_avg_ms: float | None = Field(default=None)
    is_failure: bool | None = Field(default=None)
    is_high_latency: bool | None = Field(default=None)


class UdpJitterRecord(SKBaseRecord):
    """UDP jitter / VoIP quality test record. Jitter/latency in microseconds."""

    packet_size: int
    stream_rate: int
    duration: int
    packets_up_sent: int
    packets_down_sent: int
    packets_up_recv: int
    packets_down_recv: int
    jitter_up: int
    jitter_down: int
    latency: int
    mos: float

    jitter_avg_ms: float | None = Field(default=None)
    packet_loss_up_pct: float | None = Field(default=None)
    packet_loss_down_pct: float | None = Field(default=None)
    is_failure: bool | None = Field(default=None)
    is_poor_mos: bool | None = Field(default=None)
