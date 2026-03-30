"""
SAP EWA Analyzer API Server (modular)

This minimal main module wires together configuration, CORS, and router
registration. All endpoint logic now resides in dedicated router modules.
"""

from __future__ import annotations

import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from core.logging_config import setup_logging
import uvicorn

# ---------------------------------------------------------------------------
# Environment & shared clients
# ---------------------------------------------------------------------------
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# Parse CORS allowed origins from environment variable (comma-separated or JSON array)
def _parse_cors_origins() -> list[str]:
    """Parse CORS allowed origins from environment variable.
    
    Supports:
    - CORS_ALLOWED_ORIGINS env var as comma-separated list: "http://localhost:3000,https://example.com"
    
    Falls back to localhost for development if not set.
    """
    cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if cors_env:
        # Split by comma and strip whitespace
        origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
        if origins:
            logger.info("CORS allowed origins from env: %s", origins)
            return origins
    
    # Development default
    dev_origins = ["http://localhost:3000", "http://localhost:5000", "http://localhost:8080"]
    logger.warning(
        "CORS_ALLOWED_ORIGINS not set. Using development defaults: %s. "
        "For production, set CORS_ALLOWED_ORIGINS env variable.",
        dev_origins
    )
    return dev_origins

CORS_ALLOWED_ORIGINS = _parse_cors_origins()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError("Azure Blob Storage environment variables not set – check .env file")

# The BlobServiceClient is created here in case shared utilities need it.
try:
    blob_service_client: BlobServiceClient | None = BlobServiceClient.from_connection_string(
        AZURE_STORAGE_CONNECTION_STRING
    )
except Exception as exc:  # pragma: no cover – continue; routers handle None
    logger.warning("Unable to initialise BlobServiceClient: %s", exc)
    blob_service_client = None

# ---------------------------------------------------------------------------
# FastAPI app & CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="SAP EWA Analyzer API")

# Security Middleware (XSUAA)
from core.xsuaa_middleware import XSUAAMiddleware
app.add_middleware(XSUAAMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ---------------------------------------------------------------------------
# Routers registration
# ---------------------------------------------------------------------------
from routers.storage_router import router as storage_router  # noqa: E402
from routers.ai_router import router as ai_router  # noqa: E402
from routers.export_router import router as export_router  # noqa: E402
from routers.health_router import router as health_router  # noqa: E402
from routers.chat_router import router as chat_router  # noqa: E402


app.include_router(storage_router)
app.include_router(ai_router)
app.include_router(export_router)
app.include_router(health_router)
app.include_router(chat_router)


# ---------------------------------------------------------------------------
# Development entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("ewa_main:app", host="0.0.0.0", port=8001, reload=True)
