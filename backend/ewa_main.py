"""
SAP EWA Analyzer API Server (modular)

This minimal main module wires together configuration, CORS, and router
registration. All endpoint logic now resides in dedicated router modules.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
import uvicorn

# ---------------------------------------------------------------------------
# Environment & shared clients
# ---------------------------------------------------------------------------
load_dotenv()
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
    print(f"[WARN] Unable to initialise BlobServiceClient: {exc}")
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
    allow_origins=["*"],  # Relaxed for dev; tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
