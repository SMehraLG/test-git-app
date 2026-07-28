"""FastAPI dependency injection — adapter singletons set by lifespan."""

from fastapi import HTTPException

from connectivity.adapters.bigquery.base import BigQueryAdapter
from connectivity.adapters.llm.base import LLMAdapter

bq_adapter: BigQueryAdapter | None = None
llm_adapter: LLMAdapter | None = None


def get_bq_adapter() -> BigQueryAdapter:
    if bq_adapter is None:
        raise HTTPException(status_code=503, detail="BQ adapter not initialised")
    return bq_adapter


def get_llm_adapter() -> LLMAdapter:
    if llm_adapter is None:
        raise HTTPException(status_code=503, detail="LLM adapter not initialised")
    return llm_adapter
