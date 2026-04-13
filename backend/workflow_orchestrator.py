"""
SAP EWA Analysis Workflow Orchestration Module

This module implements a custom orchestration system for analyzing SAP Early Watch Alert (EWA) reports
using Azure OpenAI services. It manages the workflow for generating comprehensive analysis of EWA reports:

1. Summary Workflow - Generates an executive summary with findings and recommendations

Key Functionality:
- Orchestrating AI analysis workflow using single enhanced GPT-4.1 agent
- Specialized prompting for comprehensive information extraction
- Integration with Azure Blob Storage for document persistence
- Error handling and status reporting

The orchestrator ensures a cohesive end-to-end analysis process for SAP EWA reports.
"""

import os
import json
import asyncio
import re
import traceback  # Added for exception logging
import logging
from typing import Dict, Any
from dataclasses import dataclass
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from dotenv import load_dotenv
from agent.specialist_agents import run_all_specialists, DomainResult
from agent.deep_thinker_agent import DeepThinkerAgent, SupplementalFinding
from utils.ewa_slicer import slice_chapters
from utils.ewa_dispatcher import dispatch_chapters, RoutingEntry
from utils.excel_workbook_builder import build_workbook
from services.storage_service import StorageService
from core.runtime_config import (
    ANTHROPIC_TIMEOUT_SECONDS,
    ANTHROPIC_CONNECT_TIMEOUT_SECONDS,
    ANTHROPIC_TEMPERATURE,
    V2_ROUTER_MODEL,
    V2_SPECIALIST_MODEL,
    V2_DEEP_MODEL,
    V2_SPECIALIST_MAX_TOKENS,
    V2_DEEP_MAX_TOKENS,
    V2_SPECIALIST_REASONING,
    V2_DEEP_REASONING,
    V2_ANTHROPIC_ROUTER_MODEL,
    V2_ANTHROPIC_SPECIALIST_MODEL,
    V2_ANTHROPIC_DEEP_MODEL,
    V2_ANTHROPIC_SPECIALIST_MAX_TOKENS,
    V2_ANTHROPIC_DEEP_MAX_TOKENS,
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Provider selection: "openai" (default) or "anthropic"
PROVIDER = os.getenv("PROVIDER", "openai").lower()

# Azure AI Foundry / Anthropic configuration (used when PROVIDER=anthropic)
AZURE_ANTHROPIC_ENDPOINT = os.getenv("AZURE_ANTHROPIC_ENDPOINT")
AZURE_ANTHROPIC_API_KEY = os.getenv("AZURE_ANTHROPIC_API_KEY")

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
@dataclass
class WorkflowState:
    """State object for workflow execution"""
    blob_name: str
    markdown_content: str = ""
    error: str = ""
    # V2 pipeline fields
    domain_results: list = None
    supplemental_findings: list = None
    workbook_bytes: bytes = None
    v2_usage: dict = None
    routing_map: dict = None   # int -> RoutingEntry, populated by dispatch stage

class EWAWorkflowOrchestrator:
    """Custom orchestrator for EWA analysis workflows"""
    
    def __init__(self):
        self.client = None
        self.blob_service_client = None
        self.openai_client = None
        self.anthropic_client = None
        self.azure_openai_endpoint = AZURE_OPENAI_ENDPOINT
        self.azure_openai_api_key = AZURE_OPENAI_API_KEY
        self.azure_openai_api_version = AZURE_OPENAI_API_VERSION
        self.storage_service = StorageService()
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Azure OpenAI and Blob Storage clients"""
        try:
            # Initialize Blob Storage client
            self.blob_service_client = BlobServiceClient.from_connection_string(
                AZURE_STORAGE_CONNECTION_STRING
            )

            # Initialize OpenAI client (used for parameter extraction)
            if self.azure_openai_endpoint and self.azure_openai_api_key and self.azure_openai_api_version:
                self.openai_client = AzureOpenAI(
                    api_version=self.azure_openai_api_version,
                    azure_endpoint=self.azure_openai_endpoint,
                    api_key=self.azure_openai_api_key,
                )

            # Initialize Anthropic client when provider is anthropic
            if PROVIDER == "anthropic":
                try:
                    self.anthropic_client = self._create_anthropic_client()
                    logger.info("Successfully initialized Anthropic client for V2 pipeline")
                except Exception as e:
                    logger.warning("Failed to initialize Anthropic client: %s", e)
            
            logger.info("Successfully initialized Blob Storage client")
            
        except Exception as e:
            logger.exception("Error initializing clients: %s", e)
            raise

    def _extract_error_status_code(self, error_message: str | None) -> int:
        if not error_message:
            return 500
        match = re.search(r"Error code:\s*(\d{3})", error_message)
        if match:
            return int(match.group(1))
        lowered = error_message.lower()
        if "timeout" in lowered:
            return 504
        return 500

    def _build_error_hint(self, error_message: str | None) -> str:
        code = self._extract_error_status_code(error_message)
        lowered = (error_message or "").lower()
        if code == 429 or "too_many_requests" in lowered or "no_capacity" in lowered:
            return "429: Too many requests"
        if code == 504 or "timeout" in lowered:
            return "504: Timeout"
        if "context length" in lowered or "maximum context length" in lowered or "too many tokens" in lowered:
            return "500: Context length exceeded"
        if code == 500:
            return "500: Analysis failed"
        return f"{code}: Analysis failed"

    def _truncate_metadata_value(self, value: str | None, max_length: int = 240) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if len(text) <= max_length:
            return text
        return text[: max_length - 3].rstrip() + "..."

    def _create_anthropic_client(self):
        if not AZURE_ANTHROPIC_ENDPOINT:
            raise ValueError("AZURE_ANTHROPIC_ENDPOINT environment variable is required for PROVIDER=anthropic")
        if not AZURE_ANTHROPIC_API_KEY:
            raise ValueError("AZURE_ANTHROPIC_API_KEY environment variable is required for PROVIDER=anthropic")

        from anthropic import AnthropicFoundry
        import httpx

        return AnthropicFoundry(
            api_key=AZURE_ANTHROPIC_API_KEY,
            base_url=AZURE_ANTHROPIC_ENDPOINT,
            timeout=httpx.Timeout(
                timeout=float(ANTHROPIC_TIMEOUT_SECONDS),
                connect=float(ANTHROPIC_CONNECT_TIMEOUT_SECONDS),
            ),
        )
    
    async def download_markdown_from_blob(self, blob_name: str) -> str:
        """Download markdown content from Azure Blob Storage"""
        try:
            # Convert original filename to .md format
            base_name = os.path.splitext(blob_name)[0]
            md_blob_name = f"{base_name}.md"
            
            logger.info("Downloading markdown content from %s", md_blob_name)
            content = await asyncio.to_thread(self.storage_service.get_text_content, md_blob_name)
            
            logger.info("Successfully downloaded %s characters of markdown content", len(content))
            return content
            
        except FileNotFoundError as e:
            logger.warning("Markdown blob missing: %s", e)
            raise
        except Exception as e:
            error_message = f"Error downloading markdown from blob storage: {str(e)}"
            logger.exception(error_message)
            raise Exception(error_message)

    
    async def upload_to_blob(self, blob_name: str, content: str, content_type: str = "text/markdown", metadata: dict = None) -> str:
        """Upload content to Azure Blob Storage with optional metadata"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=blob_name
            )
            
            # Prepare upload parameters
            upload_params = {
                "data": content.encode('utf-8'),
                "overwrite": True,
                "content_type": content_type
            }
            
            # Add metadata if provided
            if metadata:
                upload_params["metadata"] = metadata
                logger.info("Uploading %s with metadata: %s", blob_name, metadata)
            
            # Offload blocking upload to a thread
            await asyncio.to_thread(lambda: blob_client.upload_blob(**upload_params))
            
            logger.info("Successfully uploaded content to %s", blob_name)
            return blob_name
            
        except Exception as e:
            error_message = f"Error uploading to blob storage: {str(e)}"
            logger.exception(error_message)
            raise Exception(error_message)
    
    async def get_blob_metadata(self, blob_name: str) -> dict:
        """Retrieve metadata from a blob"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=blob_name
            )
            
            properties = await asyncio.to_thread(blob_client.get_blob_properties)
            return properties.metadata or {}
            
        except Exception as e:
            logger.warning("Error retrieving metadata for %s: %s", blob_name, e)
            return {}

    async def set_processing_flag(self, blob_name: str, is_processing: bool) -> bool:
        """Ensure the original blob metadata reflects current processing state."""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME,
                blob=blob_name
            )

            properties = await asyncio.to_thread(blob_client.get_blob_properties)
            metadata = (properties.metadata or {}).copy()

            updated = False
            if is_processing:
                if metadata.get("processing") != "true":
                    metadata["processing"] = "true"
                    updated = True
                if metadata.get("last_status") != "processing":
                    metadata["last_status"] = "processing"
                    updated = True
                for key in ["last_error_status_code", "last_error_hint", "last_error_message"]:
                    if metadata.pop(key, None) is not None:
                        updated = True
            else:
                if metadata.pop("processing", None) is not None:
                    updated = True

            if not updated:
                return True

            await asyncio.to_thread(blob_client.set_blob_metadata, metadata)
            return True
        except Exception as e:
            state = "set" if is_processing else "clear"
            logger.warning("Could not %s processing metadata for %s: %s", state, blob_name, e)
            return False

    async def _set_metadata_field(self, blob_name: str, key: str, value: str | None) -> bool:
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME,
                blob=blob_name
            )
            properties = await asyncio.to_thread(blob_client.get_blob_properties)
            metadata = (properties.metadata or {}).copy()

            if value is None:
                metadata.pop(key, None)
            else:
                metadata[key] = value

            await asyncio.to_thread(blob_client.set_blob_metadata, metadata)
            return True
        except Exception as e:
            action = "set" if value is not None else "clear"
            logger.warning("Could not %s metadata '%s' for %s: %s", action, key, blob_name, e)
            return False

    async def _set_last_status(self, blob_name: str, status: str | None) -> bool:
        normalized = status.lower() if isinstance(status, str) else None
        return await self._set_metadata_field(blob_name, "last_status", normalized)

    async def _set_workflow_status_metadata(
        self,
        blob_name: str,
        status: str | None,
        error_message: str | None = None,
    ) -> bool:
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME,
                blob=blob_name,
            )
            properties = await asyncio.to_thread(blob_client.get_blob_properties)
            metadata = (properties.metadata or {}).copy()

            if status is None:
                metadata.pop("last_status", None)
            else:
                metadata["last_status"] = status.lower()

            if status and status.lower() == "failed":
                status_code = str(self._extract_error_status_code(error_message))
                metadata["last_error_status_code"] = status_code
                metadata["last_error_hint"] = self._truncate_metadata_value(self._build_error_hint(error_message), 120) or "500: Analysis failed"
                metadata["last_error_message"] = self._truncate_metadata_value(error_message, 240) or "Analysis failed"
            else:
                metadata.pop("last_error_status_code", None)
                metadata.pop("last_error_hint", None)
                metadata.pop("last_error_message", None)

            await asyncio.to_thread(blob_client.set_blob_metadata, metadata)
            return True
        except Exception as e:
            logger.warning("Could not update workflow status metadata for %s: %s", blob_name, e)
            return False

    # Workflow step functions
    async def download_content_step(self, state: WorkflowState, skip_conversion: bool = False) -> WorkflowState:
        """Step 1: Download markdown content from blob storage.

        When skip_conversion is True we avoid invoking the document converter fallback
        (callers already handled conversion), so we surface the original error instead.
        """
        try:
            logger.info("[STEP 1] Downloading content for %s", state.blob_name)
            state.markdown_content = await self.download_markdown_from_blob(state.blob_name)
            return state
        except Exception as e:
            error_text = str(e)
            missing_md = (
                isinstance(e, FileNotFoundError)
                or "not found in storage" in error_text
                or "filenotfound" in error_text.lower()
                or "blobnotfound" in error_text
                or "does not exist" in error_text
            )
            if missing_md:
                logger.error("[STEP 1] Markdown missing for %s. It should have been created during upload.", state.blob_name)
                state.error = f"Markdown file not found: {e}"
                return state
                
            state.error = error_text
            return state
    

    async def save_results_step(self, state: WorkflowState) -> WorkflowState:
        """Save V2 workbook and diagnostics to blob storage."""
        try:
            logger.info("[SAVE] Saving V2 results for %s", state.blob_name)
            base_name = os.path.splitext(state.blob_name)[0]

            # Retrieve metadata from original blob
            original_metadata = await self.get_blob_metadata(state.blob_name)
            logger.debug("Retrieved original metadata: %s", original_metadata)

            # Save Excel workbook
            if state.workbook_bytes:
                workbook_blob = f"{base_name}_workbook.xlsx"
                blob_client = self.blob_service_client.get_blob_client(
                    container=AZURE_STORAGE_CONTAINER_NAME,
                    blob=workbook_blob,
                )
                await asyncio.to_thread(
                    lambda: blob_client.upload_blob(
                        data=state.workbook_bytes,
                        overwrite=True,
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        metadata=original_metadata,
                    )
                )
                logger.info("[SAVE] Uploaded workbook (%d bytes) to %s", len(state.workbook_bytes), workbook_blob)

            # Save workbook payload JSON (domain results + supplements) for diagnostics
            if state.domain_results is not None:
                payload = {
                    "domain_results": [dr.to_dict() for dr in state.domain_results],
                    "supplemental_findings": [
                        sf.to_dict() if isinstance(sf, SupplementalFinding) else sf
                        for sf in (state.supplemental_findings or [])
                    ],
                }
                payload_blob = f"{base_name}_workbook_payload.json"
                await self.upload_to_blob(
                    payload_blob,
                    json.dumps(payload, indent=2, ensure_ascii=False),
                    "application/json",
                    original_metadata,
                )
                logger.info("[SAVE] Uploaded workbook payload to %s", payload_blob)

            # Save routing map for post-hoc dispatch visibility
            if state.routing_map:
                routing_map_payload = {
                    str(num): entry.to_dict()
                    for num, entry in sorted(state.routing_map.items())
                }
                routing_map_blob = f"{base_name}_routing_map.json"
                await self.upload_to_blob(
                    routing_map_blob,
                    json.dumps(routing_map_payload, indent=2, ensure_ascii=False),
                    "application/json",
                    original_metadata,
                )
                logger.info("[SAVE] Uploaded routing map (%d chapters) to %s", len(routing_map_payload), routing_map_blob)

            # Save V2 usage report
            if state.v2_usage:
                usage_blob = f"{base_name}_v2_usage.json"
                await self.upload_to_blob(
                    usage_blob,
                    json.dumps(state.v2_usage, indent=2, ensure_ascii=False),
                    "application/json",
                    original_metadata,
                )
                logger.info("[SAVE] Uploaded V2 usage to %s", usage_blob)

            return state
        except Exception as e:
            state.error = str(e)
            return state
    

    async def _run_v2_pipeline(self, state: WorkflowState) -> WorkflowState:
        """V2 agentic pipeline: slice → dispatch → specialists → deep thinker → workbook."""
        try:
            logger.info("[V2] Starting agentic pipeline for %s (provider=%s)", state.blob_name, PROVIDER)
            text = (state.markdown_content or "").strip()
            if not text:
                raise ValueError("Markdown content is empty; conversion must succeed before analysis.")

            # Select client and model config based on provider
            if PROVIDER == "anthropic":
                v2_client = self.anthropic_client
                router_model = V2_ANTHROPIC_ROUTER_MODEL
                specialist_model = V2_ANTHROPIC_SPECIALIST_MODEL
                deep_model = V2_ANTHROPIC_DEEP_MODEL
                specialist_max_tokens = V2_ANTHROPIC_SPECIALIST_MAX_TOKENS
                deep_max_tokens = V2_ANTHROPIC_DEEP_MAX_TOKENS
            else:
                v2_client = self.openai_client
                router_model = V2_ROUTER_MODEL
                specialist_model = V2_SPECIALIST_MODEL
                deep_model = V2_DEEP_MODEL
                specialist_max_tokens = V2_SPECIALIST_MAX_TOKENS
                deep_max_tokens = V2_DEEP_MAX_TOKENS

            # Stage 1: Slice markdown into chapters
            logger.info("[V2-SLICE] Parsing chapters from markdown (%d chars)", len(text))
            chapters = slice_chapters(text)
            logger.info("[V2-SLICE] Extracted %d chapters", len(chapters))

            # Stage 2: Dispatch chapters to domains
            logger.info("[V2-DISPATCH] Routing chapters to domains (router=%s)", router_model)
            domain_chapters, routing_map = await dispatch_chapters(
                chapters,
                ai_client=v2_client,
                router_model=router_model,
                provider=PROVIDER,
            )
            state.routing_map = routing_map
            for domain, chs in domain_chapters.items():
                if chs:
                    logger.info("[V2-DISPATCH] %s: %d chapters", domain, len(chs))

            # Stage 3a: Run 6 specialists in parallel
            logger.info("[V2-SPECIALISTS] Running 6 domain specialists (model=%s)", specialist_model)
            domain_results = await run_all_specialists(
                domain_chapters,
                client=v2_client,
                model=specialist_model,
                reasoning_effort=V2_SPECIALIST_REASONING,
                max_output_tokens=specialist_max_tokens,
                provider=PROVIDER,
            )
            state.domain_results = domain_results

            total_findings = sum(len(dr.findings) for dr in domain_results)
            total_params = sum(len(dr.parameters) for dr in domain_results)
            total_abstentions = sum(len(dr.abstentions) for dr in domain_results)
            logger.info("[V2-SPECIALISTS] Done: %d findings, %d parameters, %d abstentions",
                        total_findings, total_params, total_abstentions)

            # Stage 3b: Deep Thinker cross-domain analysis
            logger.info("[V2-DEEP] Running Deep Thinker (model=%s)", deep_model)
            deep_thinker = DeepThinkerAgent(
                client=v2_client,
                model=deep_model,
                reasoning_effort=V2_DEEP_REASONING,
                max_output_tokens=deep_max_tokens,
                provider=PROVIDER,
            )
            supplemental = await deep_thinker.run(domain_results)
            state.supplemental_findings = supplemental
            logger.info("[V2-DEEP] Produced %d supplemental findings", len(supplemental))

            # Stage 4: Build Excel workbook
            original_metadata = await self.get_blob_metadata(state.blob_name)
            system_metadata = {
                "system_id": original_metadata.get("system_id", ""),
                "report_date": original_metadata.get("report_date_str", original_metadata.get("report_date", "")),
                "customer_name": original_metadata.get("customer_name", ""),
            }
            logger.info("[V2-WORKBOOK] Building 7-tab workbook")
            state.workbook_bytes = build_workbook(
                domain_results,
                supplemental,
                domain_chapters=domain_chapters,
                system_metadata=system_metadata,
            )
            logger.info("[V2-WORKBOOK] Generated %d bytes", len(state.workbook_bytes))

            # Collect usage across all agents
            specialist_usages = [dr.usage for dr in domain_results if dr.usage]
            deep_usage = deep_thinker.last_usage or {}
            state.v2_usage = {
                "specialists": specialist_usages,
                "deep_thinker": deep_usage,
            }

            return state
        except Exception as e:
            state.error = str(e)
            logger.exception("[V2] Pipeline error: %s", e)
            return state

    async def execute_workflow(self, blob_name: str, skip_markdown: bool = False) -> Dict[str, Any]:
        """Execute the complete workflow.

        Args:
            blob_name: Name of the original PDF blob to analyze.
            skip_markdown: If True, assume markdown conversion already ran and skip converter fallback.
        """
        processing_flag_set = False
        try:
            processing_flag_set = await self.set_processing_flag(blob_name, True)
        except Exception as flag_err:
            logger.warning("Unable to mark %s as processing: %s", blob_name, flag_err)

        try:
            logger.info("Starting workflow for %s", blob_name)
            
            # Initialize state
            state = WorkflowState(blob_name=blob_name)
            
            # Execute workflow steps sequentially (markdown required)
            state = await self.download_content_step(state, skip_conversion=skip_markdown)
            if state.error:
                raise Exception(state.error)
            
            # Run V2 agentic pipeline
            state = await self._run_v2_pipeline(state)
            if state.error:
                raise Exception(state.error)
            
            # Save results (workbook + diagnostics)
            state = await self.save_results_step(state)
            if state.error:
                raise Exception(state.error)

            await self._set_workflow_status_metadata(blob_name, "completed")
            
            # Return success response
            base_name = os.path.splitext(blob_name)[0]
            total_findings = sum(len(dr.findings) for dr in (state.domain_results or []))
            total_params = sum(len(dr.parameters) for dr in (state.domain_results or []))
            return {
                "success": True,
                "message": "Workflow completed successfully",
                "original_file": blob_name,
                "workbook_file": f"{base_name}_workbook.xlsx",
                "workbook_payload_file": f"{base_name}_workbook_payload.json",
                "usage_file": f"{base_name}_v2_usage.json",
                "total_findings": total_findings,
                "total_parameters": total_params,
                "supplemental_findings": len(state.supplemental_findings or []),
            }
            
        except Exception as e:
            error_message = f"Workflow error: {str(e)}"
            logger.exception(error_message)
            status_code = self._extract_error_status_code(error_message)
            await self._set_workflow_status_metadata(blob_name, "failed", error_message)
            return {
                "success": False,
                "error": True,
                "status_code": status_code,
                "error_hint": self._build_error_hint(error_message),
                "message": error_message,
                "original_file": blob_name
            }
        finally:
            if processing_flag_set:
                await self.set_processing_flag(blob_name, False)

# Global orchestrator instance
ewa_orchestrator = EWAWorkflowOrchestrator()

async def execute_ewa_analysis(blob_name: str) -> Dict[str, Any]:
    """
    Convenience function to execute EWA analysis workflow
    
    Args:
        blob_name: Name of the file to analyze
    
    Returns:
        dict: Analysis result
    """
    return await ewa_orchestrator.execute_workflow(blob_name)
