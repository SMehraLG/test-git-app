"""Connectivity FastAPI application — demo slice.

Includes:
  - GET /health, /ready
  - POST /api/v1/ingest/{test_type} and /batch
  - Mock BigQuery adapter (no GCP credentials required)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import connectivity.dependencies as deps
from connectivity.config.settings import get_settings
from connectivity.security.rate_limiter import RateLimiterMiddleware

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    if settings.bq_adapter == "bigquery":
        from connectivity.adapters.bigquery.client import BigQueryClient  # type: ignore[import]

        deps.bq_adapter = BigQueryClient(
            project_id=settings.bq_project,
            dataset=settings.bq_dataset,
        )
    else:
        from connectivity.adapters.bigquery.mock import MockBigQueryAdapter

        deps.bq_adapter = MockBigQueryAdapter()

    from connectivity.adapters.llm.mock import MockLLMAdapter

    deps.llm_adapter = MockLLMAdapter()

    logger.info(
        "Connectivity starting",
        bq_adapter=settings.bq_adapter,
        bq_dataset=settings.bq_dataset or "(mock)",
    )

    yield

    logger.info("Connectivity shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Connectivity",
        description="Network performance monitoring API — SamKnows data ingestion.",
        version="0.1.0",
        lifespan=lifespan,
    )

    cors_origins = (
        [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        if settings.cors_origins
        else ["*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Rate limiter is outermost (added last) so it runs before CORS processing.
    app.add_middleware(RateLimiterMiddleware, enabled=settings.rate_limit_enabled)

    from connectivity.api.routes.health import router as health_router
    from connectivity.api.routes.ingest import router as ingest_router

    app.include_router(health_router)
    app.include_router(ingest_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)
