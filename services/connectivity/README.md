# Connectivity Backend (Demo)

Minimal demo slice of the connectivity backend service from casas-horizon-v2.

Provides:
- `GET /health` — liveness probe
- `GET /ready` — readiness probe (checks BigQuery adapter)
- `POST /api/v1/ingest/{test_type}` — ingest a single SamKnows test record
- `POST /api/v1/ingest/{test_type}/batch` — bulk ingest with partial success

Runs fully offline with the built-in mock BigQuery adapter (`CONNECTIVITY_BQ_ADAPTER=mock`, default).

## Run locally

```bash
uv venv && uv pip install -e ".[dev]"
uvicorn connectivity.main:app --reload --port 8001
```

## Test

```bash
uv run pytest
```
