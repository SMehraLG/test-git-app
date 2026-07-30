"""GET /api/v1/customers/{customer_id}/connectivity-score endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from connectivity.adapters.bigquery.base import BigQueryAdapter
from connectivity.config.settings import Settings, get_settings
from connectivity.dependencies import get_bq_adapter
from connectivity.models.score import (
    ConnectivityScoreResponse,
    ErrorDetail,
    ErrorResponse,
)
from connectivity.repositories.measurements import MeasurementRepository
from connectivity.security.auth import CallerScope, require_api_key
from connectivity.services.score_service import NoMeasurementsError, compute_score

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


@router.get(
    "/customers/{customer_id}/connectivity-score",
    response_model=ConnectivityScoreResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_connectivity_score(
    customer_id: str,
    scope: CallerScope = Depends(require_api_key),
    bq: BigQueryAdapter = Depends(get_bq_adapter),
    settings: Settings = Depends(get_settings),
) -> ConnectivityScoreResponse | JSONResponse:
    repo = MeasurementRepository(bq, settings)

    try:
        payload = await compute_score(customer_id, scope, repo, settings)
    except NoMeasurementsError:
        logger.info("no_measurements", customer_id_present=True)
        body = ErrorResponse(
            errors=[
                ErrorDetail(
                    message=f"No measurements found for customer {customer_id}",
                    code="NOT_FOUND",
                )
            ]
        )
        return JSONResponse(status_code=404, content=body.model_dump())

    return ConnectivityScoreResponse(data=payload)
