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




# ---------------------------------------------------------------------------
# Combined process + analyze
# ---------------------------------------------------------------------------

@router.post("/process-and-analyze")
async def process_and_analyze_document_endpoint(request: ProcessAnalyzeRequest):
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")
    try:
        try:
            conversion_result = await asyncio.to_thread(convert_document_to_markdown, request.blob_name)
        except Exception as conv_err:
            logger.exception("Markdown conversion crashed for %s: %s", request.blob_name, conv_err)
            raise HTTPException(status_code=500, detail=f"Markdown conversion failed: {conv_err}")

        if not conversion_result or conversion_result.get("status") != "completed":
            error_msg = conversion_result.get("message") if isinstance(conversion_result, dict) else "Unknown conversion error"
            raise HTTPException(status_code=500, detail=f"Markdown conversion failed: {error_msg}")

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
    base_name, ext = os.path.splitext(original_blob_name)
    
    logger.info("[REPROCESS] Starting reprocess for %s", original_blob_name)

    # Determine AI filenames
    ai_md_blob = f"{base_name}_AI.md"
    ai_json_blob = f"{base_name}_AI.json"

    container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)

    # Set processing flag in metadata BEFORE deleting old files
    try:
        orig_blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME,
            blob=original_blob_name
        )
        existing_properties = orig_blob_client.get_blob_properties()
        existing_metadata = (existing_properties.metadata or {}).copy()
        existing_metadata["processing"] = "true"
        orig_blob_client.set_blob_metadata(existing_metadata)
        logger.info("[REPROCESS] Set processing=true metadata on %s", original_blob_name)
    except Exception as meta_err:
        logger.warning("[REPROCESS] Could not set processing metadata: %s", meta_err)

    # Delete old AI files
    logger.info("[REPROCESS] Deleting old AI files: %s, %s", ai_md_blob, ai_json_blob)
    try:
        for blob_name in (ai_md_blob, ai_json_blob):
            blob_client = container_client.get_blob_client(blob_name)
            if blob_client.exists():
                blob_client.delete_blob()
                logger.info("[REPROCESS] Deleted existing %s", blob_name)
            else:
                logger.info("[REPROCESS] %s does not exist, skipping delete", blob_name)
    except Exception as e:
        logger.warning("[REPROCESS] Error deleting old AI blobs: %s", e)
        # Proceed anyway

    # Run analysis again (skip conversion, use existing .md)
    logger.info("[REPROCESS] Starting workflow execution for %s", original_blob_name)
    try:
        result = await ewa_orchestrator.execute_workflow(original_blob_name, skip_markdown=True)
        logger.info("[REPROCESS] Workflow completed with result: %s", result)
        
        # Clear processing flag after completion (success or failure)
        try:
            existing_properties = orig_blob_client.get_blob_properties()
            existing_metadata = (existing_properties.metadata or {}).copy()
            existing_metadata.pop("processing", None)
            orig_blob_client.set_blob_metadata(existing_metadata)
            logger.info("[REPROCESS] Cleared processing metadata on %s", original_blob_name)
        except Exception as meta_err:
            logger.warning("[REPROCESS] Could not clear processing metadata: %s", meta_err)
        
        if not result.get("success", False):
            error_msg = result.get('message', 'Unknown error')
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
        # Clear processing flag on error
        try:
            existing_properties = orig_blob_client.get_blob_properties()
            existing_metadata = (existing_properties.metadata or {}).copy()
            existing_metadata.pop("processing", None)
            orig_blob_client.set_blob_metadata(existing_metadata)
        except:
            pass
        
        logger.exception("[REPROCESS] Exception during workflow execution: %s", e)
        raise HTTPException(status_code=500, detail=f"Re-analysis failed: {str(e)}")
