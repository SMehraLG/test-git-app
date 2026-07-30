"""Health check endpoints — /health (liveness) and /ready (readiness)."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from connectivity.adapters.bigquery.base import BigQueryAdapter
from connectivity.dependencies import get_bq_adapter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready")
async def ready(bq: BigQueryAdapter = Depends(get_bq_adapter)) -> dict[str, str]:
    healthy = await bq.health_check()
    if not healthy:
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
    return {"status": "ok"}
