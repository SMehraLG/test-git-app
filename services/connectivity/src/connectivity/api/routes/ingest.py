"""Data ingestion endpoints for SamKnows test records.

POST /api/v1/ingest/{test_type}        — single record
POST /api/v1/ingest/{test_type}/batch  — batch with partial success
"""

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from connectivity.adapters.bigquery.base import BigQueryAdapter
from connectivity.dependencies import get_bq_adapter
from connectivity.models.scheduled import (
    HttpGetRecord,
    HttpPostRecord,
    UdpJitterRecord,
    UdpLatencyRecord,
)
from connectivity.security.auth import require_api_key

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])

TEST_TYPE_MODELS: dict[str, type[BaseModel]] = {
    "httpget": HttpGetRecord,
    "httppost": HttpPostRecord,
    "udplatency": UdpLatencyRecord,
    "udpjitter": UdpJitterRecord,
}

TEST_TYPE_TABLES: dict[str, str] = {
    "httpget": "fact_httpget",
    "httppost": "fact_httppost",
    "udplatency": "fact_udplatency",
    "udpjitter": "fact_udpjitter",
}


@router.post("/ingest/{test_type}")
async def ingest_record(
    test_type: Literal["httpget", "httppost", "udplatency", "udpjitter"],
    record: dict,
    bq: BigQueryAdapter = Depends(get_bq_adapter),
) -> dict:
    model_class = TEST_TYPE_MODELS[test_type]
    table = TEST_TYPE_TABLES[test_type]

    try:
        validated = model_class.model_validate(record)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from None

    count = await bq.insert_records(table, [validated])
    return {"inserted": count, "table": table}


class BatchRequest(BaseModel):
    records: list[dict]


@router.post("/ingest/{test_type}/batch")
async def ingest_batch(
    test_type: Literal["httpget", "httppost", "udplatency", "udpjitter"],
    body: BatchRequest,
    bq: BigQueryAdapter = Depends(get_bq_adapter),
) -> dict:
    model_class = TEST_TYPE_MODELS[test_type]
    table = TEST_TYPE_TABLES[test_type]

    validated = []
    errors = []
    for i, record in enumerate(body.records):
        try:
            validated.append(model_class.model_validate(record))
        except ValidationError as e:
            errors.append({"index": i, "errors": e.errors()})

    if not validated:
        raise HTTPException(
            status_code=422,
            detail={"message": "No valid records", "validation_errors": errors},
        )

    count = await bq.insert_records(table, validated)
    logger.info("Batch ingested", test_type=test_type, inserted=count, rejected=len(errors))

    result: dict = {"inserted": count, "table": table}
    if errors:
        result["rejected"] = len(errors)
        result["validation_errors"] = errors[:10]
    return result
