"""AI analysis and workflow routes extracted from ewa_main.py.

Endpoints:
- POST /api/process-and-analyze        (combined conversion + analysis)
- POST /api/analyze-ai                 (analyze markdown with AI)
- POST /api/reprocess-ai               (delete old AI files then analyze again)
"""

from __future__ import annotations

import os
import logging
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from models import BlobNameRequest
from models.request_models import ProcessAnalyzeRequest
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

from workflow_orchestrator import ewa_orchestrator

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _storage_settings() -> tuple[str, str]:
    """Return Azure storage connection string and container name."""
    load_dotenv()
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    if not connection_string or not container_name:
        raise RuntimeError("Azure storage environment variables not set")
    return connection_string, container_name


@lru_cache(maxsize=1)
def _blob_service_client() -> BlobServiceClient:
    connection_string, _ = _storage_settings()
    return BlobServiceClient.from_connection_string(connection_string)


def _get_blob_service_client() -> BlobServiceClient:
    try:
        return _blob_service_client()
    except RuntimeError as exc:
        logger.error("Azure storage configuration missing: %s", exc)
        raise HTTPException(status_code=500, detail="Azure storage configuration missing.")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to initialise Azure Blob Service client")
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")


def _get_container_client():
    client = _get_blob_service_client()
    _, container_name = _storage_settings()
    return client.get_container_client(container_name)

router = APIRouter(prefix="/api", tags=["ai-workflow"])




# ---------------------------------------------------------------------------
# Combined process + analyze
# ---------------------------------------------------------------------------

@router.post("/process-and-analyze")
async def process_and_analyze_document_endpoint(request: ProcessAnalyzeRequest):
    _get_blob_service_client()
    try:
        # Always analyze directly from PDF (skip markdown conversion)
        result = await ewa_orchestrator.execute_workflow(request.blob_name, skip_markdown=True)
        if not result.get("success", False):
            raise HTTPException(status_code=result.get("status_code", 500), detail=result.get("message", "Workflow failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# ---------------------------------------------------------------------------
# Analyze markdown only
# ---------------------------------------------------------------------------

@router.post("/analyze-ai")
async def analyze_document_with_ai_endpoint(request: BlobNameRequest):
    blob_name = request.blob_name
    base_name, extension = os.path.splitext(blob_name)
    markdown_file = blob_name if extension.lower() == ".md" else f"{base_name}.md"

    container_client = _get_container_client()
    try:
        blob_client = container_client.get_blob_client(markdown_file)
        blob_client.get_blob_properties()
    except Exception:
        raise HTTPException(status_code=404, detail=f"Markdown file {markdown_file} not found. Please process the document first.")

    try:
        result = await ewa_orchestrator.execute_workflow(markdown_file)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=f"Analysis failed: {result.get('message', 'Unknown error')}")
        return {
            "success": True,
            "message": "Analysis completed successfully with structured JSON output",
            "original_file": blob_name,
            "analysis_file": result.get("summary_file"),
            "analysis_json_file": result.get("summary_json_file"),
            "preview": result.get("summary_preview", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ---------------------------------------------------------------------------
# Re-process AI
# ---------------------------------------------------------------------------

@router.post("/reprocess-ai")
async def reprocess_document_with_ai(request: BlobNameRequest):
    original_blob_name = request.blob_name
    base_name, ext = os.path.splitext(original_blob_name)

    # Determine AI filenames
    ai_md_blob = f"{base_name}_AI.md"
    ai_json_blob = f"{base_name}_AI.json"

    container_client = _get_container_client()

    try:
        for blob_name in (ai_md_blob, ai_json_blob):
            blob_client = container_client.get_blob_client(blob_name)
            if blob_client.exists():
                blob_client.delete_blob()
                logger.info("Deleted existing blob during reprocess: %s", blob_name)
    except Exception as e:
        logger.warning("Error deleting old AI blobs: %s", e)
        # Proceed anyway

    # Run analysis again (always from PDF)
    try:
        result = await ewa_orchestrator.execute_workflow(original_blob_name, skip_markdown=True)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=f"Re-analysis failed: {result.get('message', 'Unknown error')}")
        return {
            "success": True,
            "message": "Re-analysis completed successfully.",
            "analysis_file": result.get("summary_file"),
            "analysis_json_file": result.get("summary_json_file"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-analysis failed: {str(e)}")
