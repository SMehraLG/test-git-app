"""Ingestion endpoint tests."""

import pytest
from httpx import AsyncClient

from connectivity.adapters.bigquery.mock import MockBigQueryAdapter

SAMPLE_HTTPGET = {
    "dtime": "2026-02-25T10:00:00",
    "dtime_utc": "2026-02-25T10:00:00Z",
    "unit_id": 12345,
    "base": "lgone-mv2p",
    "mac": "AA:BB:CC:DD:EE:01",
    "bytes_sec": 34000000,
    "bytes_total": 340000000,
    "fetch_time": 10000000,
    "successes": 1,
    "failures": 0,
}

SAMPLE_HTTPPOST = {
    "dtime": "2026-02-25T10:00:00",
    "dtime_utc": "2026-02-25T10:00:00Z",
    "unit_id": 12345,
    "base": "lgone-mv2p",
    "mac": "AA:BB:CC:DD:EE:01",
    "bytes_sec": 4500000,
    "bytes_total": 45000000,
    "fetch_time": 10000000,
    "successes": 1,
    "failures": 0,
}


@pytest.mark.asyncio
async def test_ingest_httpget(client: AsyncClient, mock_bq: MockBigQueryAdapter) -> None:
    before = len(mock_bq.get_table_rows("fact_httpget"))
    resp = await client.post("/api/v1/ingest/httpget", json=SAMPLE_HTTPGET)
    assert resp.status_code == 200
    data = resp.json()
    assert data["inserted"] == 1
    assert data["table"] == "fact_httpget"
    assert len(mock_bq.get_table_rows("fact_httpget")) == before + 1


@pytest.mark.asyncio
async def test_ingest_httppost(client: AsyncClient, mock_bq: MockBigQueryAdapter) -> None:
    resp = await client.post("/api/v1/ingest/httppost", json=SAMPLE_HTTPPOST)
    assert resp.status_code == 200
    assert resp.json()["table"] == "fact_httppost"


@pytest.mark.asyncio
async def test_ingest_batch(client: AsyncClient, mock_bq: MockBigQueryAdapter) -> None:
    before = len(mock_bq.get_table_rows("fact_httpget"))
    resp = await client.post(
        "/api/v1/ingest/httpget/batch",
        json={"records": [SAMPLE_HTTPGET, SAMPLE_HTTPGET]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["inserted"] == 2
    assert len(mock_bq.get_table_rows("fact_httpget")) == before + 2


@pytest.mark.asyncio
async def test_ingest_invalid_record(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/ingest/httpget", json={"bad": "data"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_batch_partial(client: AsyncClient, mock_bq: MockBigQueryAdapter) -> None:
    before = len(mock_bq.get_table_rows("fact_httpget"))
    resp = await client.post(
        "/api/v1/ingest/httpget/batch",
        json={"records": [SAMPLE_HTTPGET, {"bad": "data"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["inserted"] == 1
    assert data["rejected"] == 1
    assert len(mock_bq.get_table_rows("fact_httpget")) == before + 1
