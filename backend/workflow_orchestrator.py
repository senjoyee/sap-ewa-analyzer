"""
EWA Workflow Orchestrator — LangGraph Pipeline Integration.

Thin wrapper that bridges the target project's Azure Blob Storage infrastructure
with the v1 LangGraph-based analysis pipeline (ewa_pipeline).

Flow:
  1. Download markdown from Azure Blob Storage
  2. Save to a temp file on disk
  3. Run ewa_pipeline.services.pipeline.run_pipeline() (LangGraph analysis)
  4. Upload resulting Excel workbook + JSON artifacts back to Blob Storage
  5. Set processing/status metadata on the original blob
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from core.azure_clients import (
    blob_service_client,
    AZURE_STORAGE_CONTAINER_NAME,
)
from services.storage_service import StorageService

logger = logging.getLogger(__name__)

storage_service = StorageService()


class EWAWorkflowOrchestrator:
    """Orchestrate the v1 LangGraph analysis pipeline with Azure Blob Storage."""

    def __init__(self):
        self._config = None

    def _get_config(self):
        """Lazy-load pipeline config from config.yaml."""
        if self._config is None:
            from ewa_pipeline.config import load_config
            self._config = load_config()
        return self._config

    async def set_processing_flag(self, blob_name: str, is_processing: bool) -> bool:
        """Set or clear the processing flag in blob metadata."""
        try:
            blob_client = blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME,
                blob=blob_name,
            )
            properties = await asyncio.to_thread(blob_client.get_blob_properties)
            metadata = dict(properties.metadata or {})
            metadata["processing"] = str(is_processing).lower()
            if not is_processing:
                metadata.pop("processing", None)
            await asyncio.to_thread(blob_client.set_blob_metadata, metadata)
            return True
        except Exception as e:
            logger.warning("Could not set processing flag on %s: %s", blob_name, e)
            return False

    async def _set_workflow_status_metadata(
        self,
        blob_name: str,
        status: str,
        error_message: str | None = None,
    ) -> bool:
        """Update the workflow status metadata on the blob."""
        try:
            blob_client = blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME,
                blob=blob_name,
            )
            properties = await asyncio.to_thread(blob_client.get_blob_properties)
            metadata = dict(properties.metadata or {})
            metadata["last_status"] = status

            if error_message:
                # Azure metadata values are limited; truncate long messages
                metadata["last_error_message"] = error_message[:512]
                if "rate limit" in error_message.lower() or "429" in error_message:
                    metadata["last_error_status_code"] = "429"
                    metadata["last_error_hint"] = (
                        "The AI service is temporarily overloaded. Please try again in a few minutes."
                    )
                elif "timeout" in error_message.lower():
                    metadata["last_error_status_code"] = "504"
                    metadata["last_error_hint"] = (
                        "The analysis timed out. The document may be too large."
                    )
                else:
                    metadata["last_error_status_code"] = "500"
                    metadata["last_error_hint"] = (
                        "An unexpected error occurred during analysis. Check server logs."
                    )
            else:
                metadata.pop("last_error_message", None)
                metadata.pop("last_error_status_code", None)
                metadata.pop("last_error_hint", None)

            await asyncio.to_thread(blob_client.set_blob_metadata, metadata)
            return True
        except Exception as e:
            logger.warning("Could not set status metadata on %s: %s", blob_name, e)
            return False

    async def execute_workflow(
        self,
        blob_name: str,
        skip_markdown: bool = False,
    ) -> dict:
        """
        Execute the full analysis workflow on a blob.

        Args:
            blob_name: Name of the blob to analyze (can be .md or .pdf/.zip).
            skip_markdown: If True, markdown already exists — skip conversion step.

        Returns:
            Dict with success/error info and artifact blob names.
        """
        base_name = os.path.splitext(blob_name)[0]
        md_blob_name = f"{base_name}.md"

        try:
            # 1. Download markdown content from blob
            logger.info("[WORKFLOW] Downloading markdown: %s", md_blob_name)
            try:
                md_content = await asyncio.to_thread(
                    storage_service.get_text_content, md_blob_name
                )
            except FileNotFoundError:
                return {
                    "success": False,
                    "message": f"Markdown file {md_blob_name} not found in storage.",
                    "status_code": 404,
                    "error_hint": "Please upload and process the document first.",
                }

            # 2. Run the LangGraph pipeline in a background thread
            result = await asyncio.to_thread(
                self._run_pipeline_sync, md_content, base_name
            )

            if not result["success"]:
                await self._set_workflow_status_metadata(
                    blob_name, "failed", result.get("message", "Pipeline failed")
                )
                return result

            # 3. Upload artifacts back to blob storage
            logger.info("[WORKFLOW] Uploading artifacts for %s", base_name)
            artifact_names = await self._upload_artifacts(base_name, result)

            # 4. Set success metadata
            await self._set_workflow_status_metadata(blob_name, "completed")

            return {
                "success": True,
                "message": "Analysis completed successfully.",
                "workbook_file": artifact_names.get("workbook"),
                "workbook_payload_file": artifact_names.get("payload"),
                "usage_file": artifact_names.get("usage"),
                "total_findings": result.get("total_findings", 0),
                "total_parameters": 0,
                "supplemental_findings": 0,
            }

        except Exception as e:
            logger.exception("[WORKFLOW] Unexpected error: %s", e)
            await self._set_workflow_status_metadata(blob_name, "failed", str(e))
            return {
                "success": False,
                "message": f"Workflow failed: {str(e)}",
                "status_code": 500,
                "error_hint": "An unexpected error occurred. Check server logs.",
            }

    def _run_pipeline_sync(self, md_content: str, base_name: str) -> dict:
        """
        Run the v1 LangGraph pipeline synchronously in a temp directory.

        This is called via asyncio.to_thread() so it doesn't block the event loop.
        """
        from ewa_pipeline.services.pipeline import run_pipeline

        config = self._get_config()

        with tempfile.TemporaryDirectory(prefix="ewa_pipeline_") as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Write markdown to temp file
            md_path = tmpdir_path / f"{base_name}.md"
            md_path.write_text(md_content, encoding="utf-8")

            # Output workbook path
            output_xlsx = tmpdir_path / f"{base_name}_workbook.xlsx"

            # Null progress callback for server context (no SSE)
            progress_cb = lambda msg: logger.info("[PIPELINE] %s", msg)

            try:
                # Run the LangGraph pipeline
                logger.info("[PIPELINE] Starting analysis for %s", base_name)
                analysis_result, cost_tracker, artifacts = run_pipeline(
                    input_path=md_path,
                    output_path=output_xlsx,
                    config=config,
                    progress_callback=progress_cb,
                )
                logger.info(
                    "[PIPELINE] Analysis complete — %d domain analyses",
                    len(analysis_result.domain_analyses),
                )

                # Count total findings
                total_findings = sum(
                    len(da.findings) for da in analysis_result.domain_analyses
                )

                # Read generated artifacts
                result = {
                    "success": True,
                    "analysis_result": analysis_result,
                    "total_findings": total_findings,
                }

                if artifacts.output_path.exists():
                    result["workbook_bytes"] = artifacts.output_path.read_bytes()

                if artifacts.cost_path.exists():
                    result["cost_json"] = artifacts.cost_path.read_text(encoding="utf-8")

                # Serialize AnalysisResult to JSON for the workbook payload
                result["payload_json"] = analysis_result.model_dump_json(indent=2)

                return result

            except Exception as e:
                logger.exception("[PIPELINE] Pipeline failed: %s", e)
                return {
                    "success": False,
                    "message": str(e),
                    "status_code": 500,
                }

    async def _upload_artifacts(self, base_name: str, result: dict) -> dict:
        """Upload pipeline output artifacts back to Azure Blob Storage."""
        artifact_names = {}

        container_client = blob_service_client.get_container_client(
            AZURE_STORAGE_CONTAINER_NAME
        )

        # Upload workbook (.xlsx)
        if "workbook_bytes" in result:
            wb_name = f"{base_name}_workbook.xlsx"
            blob_client = container_client.get_blob_client(wb_name)
            await asyncio.to_thread(
                blob_client.upload_blob,
                result["workbook_bytes"],
                overwrite=True,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            artifact_names["workbook"] = wb_name
            logger.info("[UPLOAD] Uploaded workbook: %s", wb_name)

        # Upload workbook payload (JSON)
        if "payload_json" in result:
            payload_name = f"{base_name}_workbook_payload.json"
            blob_client = container_client.get_blob_client(payload_name)
            await asyncio.to_thread(
                blob_client.upload_blob,
                result["payload_json"].encode("utf-8"),
                overwrite=True,
                content_type="application/json",
            )
            artifact_names["payload"] = payload_name
            logger.info("[UPLOAD] Uploaded payload: %s", payload_name)

        # Upload cost/usage report (JSON)
        if "cost_json" in result:
            usage_name = f"{base_name}_v2_usage.json"
            blob_client = container_client.get_blob_client(usage_name)
            await asyncio.to_thread(
                blob_client.upload_blob,
                result["cost_json"].encode("utf-8"),
                overwrite=True,
                content_type="application/json",
            )
            artifact_names["usage"] = usage_name
            logger.info("[UPLOAD] Uploaded usage: %s", usage_name)

        return artifact_names


# Module-level singleton used by ai_router.py
ewa_orchestrator = EWAWorkflowOrchestrator()
