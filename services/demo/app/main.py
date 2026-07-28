"""Simplistic demo service for the platform factory.

It does nothing useful — it just proves the factory works: it reports which
backends the platform wired into its environment (project, Cloud SQL, Redis,
Vertex). Deployed to Cloud Run by the tenant pipeline.
"""
import os

from fastapi import FastAPI

app = FastAPI(title="platform-factory demo")

# Env vars injected by the tenant module from the provisioned resources.
WIRED_KEYS = [
    "GCP_PROJECT",
    "DB_MAIN_CONNECTION",
    "DB_MAIN_HOST",
    "REDIS_CACHE_HOST",
    "REDIS_CACHE_PORT",
    "VERTEX_LOCATION",
]


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "service": os.environ.get("SERVICE_NAME", "demo"),
        "message": "Provisioned by platform-factory 🌮",
        "wired": {k: bool(os.environ.get(k)) for k in WIRED_KEYS},
    }
