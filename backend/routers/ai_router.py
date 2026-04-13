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

    # Set processing flag in metadata
    try:
        await ewa_orchestrator.set_processing_flag(original_blob_name, True)
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

        # Ensure markdown exists; in the new workflow, it MUST be created during upload
        try:
            markdown_client = container_client.get_blob_client(markdown_blob_name)
            if not markdown_client.exists():
                logger.error("[PROCESS] Markdown missing for %s", original_blob_name)
                raise HTTPException(status_code=404, detail=f"Markdown file {markdown_blob_name} not found. Please re-upload the zip.")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("[PROCESS] Missing markdown file: %s", e)
            raise HTTPException(status_code=500, detail=f"Error accessing markdown file: {str(e)}")

        # Run analysis (markdown guaranteed to exist)
        logger.info("[PROCESS] Starting workflow execution for %s", original_blob_name)
        result = await ewa_orchestrator.execute_workflow(original_blob_name, skip_markdown=True)
        logger.info("[PROCESS] Workflow completed with result: %s", result)
        return result
    except HTTPException as http_err:
        await ewa_orchestrator._set_workflow_status_metadata(
            original_blob_name,
            "failed",
            str(getattr(http_err, "detail", http_err)),
        )
        raise
    except Exception as exc:
        await ewa_orchestrator._set_workflow_status_metadata(
            original_blob_name,
            "failed",
            str(exc),
        )
        raise
    finally:
        # Clear processing flag after completion (success or failure)
        try:
            await ewa_orchestrator.set_processing_flag(original_blob_name, False)
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
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("error_hint") or result.get("message", "Workflow failed"),
            )
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
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("error_hint") or result.get("message", "Analysis failed"),
            )
        return {
            "success": True,
            "message": "Agentic analysis completed successfully",
            "original_file": blob_name,
            "workbook_file": result.get("workbook_file"),
            "workbook_payload_file": result.get("workbook_payload_file"),
            "usage_file": result.get("usage_file"),
            "total_findings": result.get("total_findings", 0),
            "total_parameters": result.get("total_parameters", 0),
            "supplemental_findings": result.get("supplemental_findings", 0),
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
            error_msg = result.get("error_hint") or result.get("message", "Unknown error")
            logger.warning("[REPROCESS] Workflow failed: %s", error_msg)
            raise HTTPException(status_code=result.get("status_code", 500), detail=error_msg)

        logger.info("[REPROCESS] Re-analysis completed successfully for %s", original_blob_name)
        return {
            "success": True,
            "message": "Agentic re-analysis completed successfully.",
            "workbook_file": result.get("workbook_file"),
            "workbook_payload_file": result.get("workbook_payload_file"),
            "usage_file": result.get("usage_file"),
            "total_findings": result.get("total_findings", 0),
            "total_parameters": result.get("total_parameters", 0),
            "supplemental_findings": result.get("supplemental_findings", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[REPROCESS] Exception during workflow execution: %s", e)
        raise HTTPException(status_code=500, detail=f"Re-analysis failed: {str(e)}")
