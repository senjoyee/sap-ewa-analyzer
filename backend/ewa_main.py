"""
SAP EWA Analyzer API Server (modular)

This minimal main module wires together configuration, CORS, and router
registration. All endpoint logic now resides in dedicated router modules.

Supports deployment to:
- Local development (uvicorn with .env)
- Azure Web Apps (Docker container)
- SAP BTP Cloud Foundry (Python buildpack with VCAP_SERVICES)
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
# Load .env for local development (ignored on Cloud Foundry)
load_dotenv()

# Import BTP configuration helper (handles both local and CF environments)
from core.btp_config import init_config, is_running_on_cf

# Initialize configuration (reads from .env locally, VCAP_SERVICES on CF)
try:
    config = init_config()
    AZURE_STORAGE_CONNECTION_STRING = config.azure_storage_connection_string
    AZURE_STORAGE_CONTAINER_NAME = config.azure_storage_container_name
    print(f"[INFO] Running on Cloud Foundry: {config.is_cloud_foundry}")
    print(f"[INFO] App: {config.app_name}, Space: {config.space_name}")
except ValueError as e:
    # Fallback to direct env vars for backwards compatibility
    print(f"[WARN] BTP config init failed, falling back to env vars: {e}")
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError("Azure Blob Storage environment variables not set – check .env file or BTP service binding")

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
app = FastAPI(
    title="SAP EWA Analyzer API",
    description="AI-powered Early Watch Alert analysis for SAP systems",
    version="1.0.0",
)

# CORS configuration - adjust for production
# On BTP, the App Router handles CORS, but we keep this for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Relaxed for dev; App Router handles in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# XSUAA Middleware (only active on Cloud Foundry)
# ---------------------------------------------------------------------------
if is_running_on_cf():
    from core.xsuaa_middleware import XSUAAMiddleware
    app.add_middleware(XSUAAMiddleware)
    print("[INFO] XSUAA middleware enabled for Cloud Foundry")

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
    # Get port from environment (Cloud Foundry assigns PORT)
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("ewa_main:app", host="0.0.0.0", port=port, reload=True)
