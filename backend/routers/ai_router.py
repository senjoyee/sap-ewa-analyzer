"""AI analysis and workflow routes extracted from ewa_main.py.

Endpoints:
- POST /api/process-and-analyze        (combined conversion + analysis)
- POST /api/analyze-ai                 (analyze markdown with AI)
- POST /api/reprocess-ai               (delete old AI files then analyze again)
"""

from __future__ import annotations

import asyncio
import os
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from models import BlobNameRequest
from models.request_models import ProcessAnalyzeRequest
from converters.document_converter import convert_document_to_markdown

from core.azure_clients import (
    blob_service_client,
    AZURE_STORAGE_CONTAINER_NAME,
)
from workflow_orchestrator import ewa_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ai-workflow"])


async def _run_processing_flow(original_blob_name: str) -> Dict[str, Any]:
    base_name, _ = os.path.splitext(original_blob_name)
    markdown_blob_name = f"{base_name}.md"
    container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
    orig_blob_client = blob_service_client.get_blob_client(
        container=AZURE_STORAGE_CONTAINER_NAME,
        blob=original_blob_name,
    )

    # Set processing flag in metadata
    try:
        existing_properties = orig_blob_client.get_blob_properties()
        existing_metadata = (existing_properties.metadata or {}).copy()
        existing_metadata["processing"] = "true"
        orig_blob_client.set_blob_metadata(existing_metadata)
        logger.info("[PROCESS] Set processing=true metadata on %s", original_blob_name)
    except Exception as meta_err:
        logger.warning("[PROCESS] Could not set processing metadata: %s", meta_err)

    try:
        # Delete all derived artifacts except the original PDF and markdown
        logger.info("[PROCESS] Cleaning derived blobs for %s", base_name)
        try:
            preserved = {original_blob_name, markdown_blob_name}
            blob_list = container_client.list_blobs(name_starts_with=base_name)
            for blob in blob_list:
                if blob.name in preserved:
                    continue
                blob_client = container_client.get_blob_client(blob.name)
                blob_client.delete_blob()
                logger.info("[PROCESS] Deleted %s", blob.name)
        except Exception as e:
            logger.warning("[PROCESS] Error deleting derived blobs: %s", e)

        # Ensure markdown exists; if missing, convert the PDF to markdown
        try:
            markdown_client = container_client.get_blob_client(markdown_blob_name)
            if not markdown_client.exists():
                logger.info("[PROCESS] Markdown missing for %s; converting PDF", original_blob_name)
                conversion_result = await asyncio.to_thread(convert_document_to_markdown, original_blob_name)
                if not conversion_result or conversion_result.get("status") != "completed":
                    error_msg = conversion_result.get("message") if isinstance(conversion_result, dict) else "Unknown conversion error"
                    raise HTTPException(status_code=500, detail=f"Markdown conversion failed: {error_msg}")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("[PROCESS] Markdown conversion failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Markdown conversion failed: {str(e)}")

        # Run analysis (markdown guaranteed to exist)
        logger.info("[PROCESS] Starting workflow execution for %s", original_blob_name)
        result = await ewa_orchestrator.execute_workflow(original_blob_name, skip_markdown=True)
        logger.info("[PROCESS] Workflow completed with result: %s", result)
        return result
    finally:
        # Clear processing flag after completion (success or failure)
        try:
            existing_properties = orig_blob_client.get_blob_properties()
            existing_metadata = (existing_properties.metadata or {}).copy()
            existing_metadata.pop("processing", None)
            orig_blob_client.set_blob_metadata(existing_metadata)
            logger.info("[PROCESS] Cleared processing metadata on %s", original_blob_name)
        except Exception as meta_err:
            logger.warning("[PROCESS] Could not clear processing metadata: %s", meta_err)




# ---------------------------------------------------------------------------
# Combined process + analyze
# ---------------------------------------------------------------------------

@router.post("/process-and-analyze")
async def process_and_analyze_document_endpoint(request: ProcessAnalyzeRequest):
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")
    try:
        result = await _run_processing_flow(request.blob_name)
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
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")

    blob_name = request.blob_name
    base_name, extension = os.path.splitext(blob_name)
    markdown_file = blob_name if extension.lower() == ".md" else f"{base_name}.md"

    container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
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
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")

    original_blob_name = request.blob_name
    logger.info("[REPROCESS] Starting reprocess for %s", original_blob_name)

    try:
        result = await _run_processing_flow(original_blob_name)
        if not result.get("success", False):
            error_msg = result.get("message", "Unknown error")
            logger.warning("[REPROCESS] Workflow failed: %s", error_msg)
            raise HTTPException(status_code=500, detail=f"Re-analysis failed: {error_msg}")

        logger.info("[REPROCESS] Re-analysis completed successfully for %s", original_blob_name)
        return {
            "success": True,
            "message": "Re-analysis completed successfully.",
            "analysis_file": result.get("summary_file"),
            "analysis_json_file": result.get("summary_json_file"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[REPROCESS] Exception during workflow execution: %s", e)
        raise HTTPException(status_code=500, detail=f"Re-analysis failed: {str(e)}")
