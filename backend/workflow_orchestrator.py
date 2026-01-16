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
import traceback  # Added for exception logging
import logging
from datetime import datetime
from typing import Dict, Any
from dataclasses import dataclass
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from dotenv import load_dotenv
from agent.openai_ewa_agent import OpenAIEWAAgent
from agent.anthropic_ewa_agent import AnthropicEWAAgent
from agent.parameter_extraction_agent import ParameterExtractionAgent
from utils.markdown_utils import json_to_markdown
from converters.document_converter import convert_document_to_markdown
from services.storage_service import StorageService
from core.runtime_config import ANTHROPIC_TIMEOUT_SECONDS, ANTHROPIC_CONNECT_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Model deployment names
AZURE_OPENAI_SUMMARY_MODEL = os.getenv("AZURE_OPENAI_SUMMARY_MODEL", "gpt-4.1")
AZURE_OPENAI_FAST_MODEL = (
    os.getenv("AZURE_OPENAI_FAST_MODEL")
    or AZURE_OPENAI_SUMMARY_MODEL
    or "gpt-4.1-mini"
)

# Provider selection: "openai" (default) or "anthropic"
PROVIDER = os.getenv("PROVIDER", "openai").lower()

# Azure AI Foundry / Anthropic configuration (used when PROVIDER=anthropic)
ANTHROPIC_SUMMARY_MODEL = os.getenv("ANTHROPIC_SUMMARY_MODEL", "claude-sonnet-4-5")
AZURE_ANTHROPIC_ENDPOINT = os.getenv("AZURE_ANTHROPIC_ENDPOINT")
AZURE_ANTHROPIC_API_KEY = os.getenv("AZURE_ANTHROPIC_API_KEY")

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

# System prompts for each workflow
# System prompts for each workflow
def load_summary_prompt() -> str | None:
    """Return the first available summary prompt content, or None if none found."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_dir = os.path.join(current_dir, "prompts")

    candidate_files = [
        "ewa_summary_prompt_openai.md",
        "ewa_summary_prompt.md",
    ]

    for filename in candidate_files:
        path = os.path.join(prompt_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    logger.info("Loaded summary prompt from %s", path)
                    return f.read()
            except Exception as e:
                logger.warning("Could not read prompt file %s: %s", path, e)
    # No prompt files found – return None so that downstream logic can fall back
    logger.warning("No summary prompt files found; EWAAgent will use its internal default prompts.")
    return None

SUMMARY_PROMPT: str | None = load_summary_prompt()




@dataclass
class WorkflowState:
    """State object for workflow execution"""
    blob_name: str
    markdown_content: str = ""
    summary_result: str = ""
    summary_json: dict = None
    parameters_json: dict = None
    alert_index: dict = None  # Vision-extracted alerts from PDF
    error: str = ""

class EWAWorkflowOrchestrator:
    """Custom orchestrator for EWA analysis workflows"""
    
    def __init__(self):
        self.client = None
        self.blob_service_client = None
        self.openai_client = None
        self.summary_model = AZURE_OPENAI_SUMMARY_MODEL
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
            
            logger.info("Successfully initialized Blob Storage client")
            
        except Exception as e:
            logger.exception("Error initializing clients: %s", e)
            raise
    
    def _create_agent(self, model: str | None = None, summary_prompt: str | None = None) -> OpenAIEWAAgent:
        model_name = model or self.summary_model
        logger.info("Creating OpenAIEWAAgent with model: %s", model_name)
        if not self.azure_openai_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
        if not self.azure_openai_api_key:
            raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
        if not self.azure_openai_api_version:
            raise ValueError("AZURE_OPENAI_API_VERSION environment variable is required")
        client = AzureOpenAI(
            api_version=self.azure_openai_api_version,
            azure_endpoint=self.azure_openai_endpoint,
            api_key=self.azure_openai_api_key,
        )
        return OpenAIEWAAgent(client=client, model=model_name, summary_prompt=summary_prompt)
    
    def _create_anthropic_agent(self, model: str | None = None, summary_prompt: str | None = None) -> AnthropicEWAAgent:
        """Create an AnthropicEWAAgent for Azure AI Foundry (Claude) models."""
        model_name = model or ANTHROPIC_SUMMARY_MODEL
        logger.info("Creating AnthropicEWAAgent with model: %s", model_name)
        
        if not AZURE_ANTHROPIC_ENDPOINT:
            raise ValueError("AZURE_ANTHROPIC_ENDPOINT environment variable is required for PROVIDER=anthropic")
        if not AZURE_ANTHROPIC_API_KEY:
            raise ValueError("AZURE_ANTHROPIC_API_KEY environment variable is required for PROVIDER=anthropic")
        
        # Import AnthropicFoundry from anthropic SDK
        from anthropic import AnthropicFoundry
        import httpx
        
        # Configure extended timeout for long-running requests
        client = AnthropicFoundry(
            api_key=AZURE_ANTHROPIC_API_KEY,
            base_url=AZURE_ANTHROPIC_ENDPOINT,
            timeout=httpx.Timeout(
                timeout=float(ANTHROPIC_TIMEOUT_SECONDS),
                connect=float(ANTHROPIC_CONNECT_TIMEOUT_SECONDS),
            ),
        )
        return AnthropicEWAAgent(client=client, model=model_name, summary_prompt=summary_prompt)
    
    def _fix_report_date_if_invalid(self, summary_json: dict, blob_name: str) -> dict:
        """Validate report_date; if obviously wrong, extract from filename pattern {SID}_{DD}_{Mon}_{YY}.pdf."""
        import re
        MONTH_MAP = {
            "jan": "01", "feb": "02", "mar": "03", "apr": "04",
            "may": "05", "jun": "06", "jul": "07", "aug": "08",
            "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        }
        
        VALID_REPORT_YEAR_MIN = 2020
        VALID_REPORT_YEAR_MAX = 2039

        def is_valid_date(d: str) -> bool:
            if not d:
                return False
            # Accept DD.MM.YYYY or YYYY-MM-DD in 2020-2039 range
            m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", d)
            if m:
                year = int(m.group(3))
                return VALID_REPORT_YEAR_MIN <= year <= VALID_REPORT_YEAR_MAX
            m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", d)
            if m:
                year = int(m.group(1))
                return VALID_REPORT_YEAR_MIN <= year <= VALID_REPORT_YEAR_MAX
            return False
        
        def extract_date_from_filename(fname: str) -> str | None:
            # Pattern: {SID}_{DD}_{Mon}_{YY}.pdf  e.g. ERP_09_Nov_25.pdf
            m = re.match(r"^[A-Za-z0-9]+_(\d{2})_([A-Za-z]{3})_(\d{2})", fname)
            if m:
                day, mon, yy = m.group(1), m.group(2).lower(), m.group(3)
                mm = MONTH_MAP.get(mon)
                if mm:
                    year = 2000 + int(yy)
                    return f"{day}.{mm}.{year}"
            return None
        
        # Locate report_date in JSON (could be top-level or nested under System Metadata)
        meta = summary_json.get("System Metadata") or summary_json.get("system_metadata") or {}
        report_date = meta.get("Report Date") or meta.get("report_date") or summary_json.get("Report Date") or summary_json.get("report_date")
        
        if is_valid_date(report_date):
            return summary_json
        
        # Attempt extraction from filename
        fallback = extract_date_from_filename(blob_name)
        if fallback:
            logger.warning(
                "[_fix_report_date_if_invalid] Invalid date '%s'; using filename fallback '%s'",
                report_date,
                fallback,
            )
            # Update in-place
            if "System Metadata" in summary_json and isinstance(summary_json["System Metadata"], dict):
                summary_json["System Metadata"]["Report Date"] = fallback
            elif "system_metadata" in summary_json and isinstance(summary_json["system_metadata"], dict):
                summary_json["system_metadata"]["report_date"] = fallback
            else:
                # Create System Metadata if missing
                summary_json["System Metadata"] = {"Report Date": fallback}
        else:
            logger.warning(
                "[_fix_report_date_if_invalid] Invalid date '%s' and no filename fallback available",
                report_date,
            )
        
        return summary_json
    
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
            
        except Exception as e:
            error_message = f"Error downloading markdown from blob storage: {str(e)}"
            logger.exception(error_message)
            raise Exception(error_message)
    
    async def download_pdf_from_blob(self, blob_name: str) -> bytes:
        """Download original PDF content from Azure Blob Storage for multimodal analysis"""
        try:
            logger.info("Downloading PDF content from %s", blob_name)
            content = await asyncio.to_thread(self.storage_service.get_bytes, blob_name)
            logger.info("Successfully downloaded %s bytes of PDF content", len(content))
            return content
            
        except Exception as e:
            error_message = f"Error downloading PDF from blob storage: {str(e)}"
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
            if skip_conversion and not missing_md:
                state.error = error_text
                return state
            # Attempt to generate markdown via converter when missing
            try:
                logger.info(
                    "[STEP 1] Markdown not found for %s; attempting conversion to markdown",
                    state.blob_name,
                )
                result = await asyncio.to_thread(convert_document_to_markdown, state.blob_name)
                if isinstance(result, dict) and not result.get("error") and result.get("status") == "completed":
                    # Re-download newly created markdown
                    state.markdown_content = await self.download_markdown_from_blob(state.blob_name)
                    return state
                else:
                    msg = result.get("message") if isinstance(result, dict) else None
                    state.error = msg or str(e)
                    return state
            except Exception as conv_e:
                state.error = str(conv_e)
                return state
    
    async def extract_alerts_step(self, state: WorkflowState) -> WorkflowState:
        """Step 1.5: Extract alert list from PDF using vision."""
        try:
            logger.info("[STEP 1.5] Extracting alerts from PDF via vision for %s", state.blob_name)
            from utils.alert_vision_extractor import extract_alerts_with_vision
            
            # Download PDF bytes
            pdf_bytes = await self.download_pdf_from_blob(state.blob_name)
            
            # Extract alerts using vision
            state.alert_index = await extract_alerts_with_vision(
                pdf_bytes,
                client=self.openai_client,
                model=self.summary_model,
            )
            
            alert_count = len(state.alert_index.get("alerts", []))
            logger.info("[STEP 1.5] Extracted %d alerts via vision", alert_count)
            
            return state
        except Exception as e:
            # Non-fatal: log warning and continue without alert index
            logger.warning("[STEP 1.5] Alert extraction failed (non-fatal): %s", e)
            state.alert_index = {"alerts": [], "extraction_notes": f"Extraction failed: {str(e)}"}
            return state
    

    async def run_analysis_step(self, state: WorkflowState) -> WorkflowState:
        """Step 2: Generate comprehensive EWA analysis; then extract KPIs via image agent"""
        try:
            logger.info("[STEP 2] Running EWA analysis for %s", state.blob_name)
            
            # Get metadata from original blob for KPI management
            original_metadata = await self.get_blob_metadata(state.blob_name)
            customer_name = original_metadata.get('customer_name', '')
            system_id = original_metadata.get('system_id', '')
            report_date_str = original_metadata.get('report_date_str', '')
            
            logger.info(
                "Analysis - Customer: %s, System: %s, Report Date: %s",
                customer_name,
                system_id,
                report_date_str,
            )
            
            # Step 1: Run AI analysis for all other sections (excluding KPIs)
            # Update prompt to exclude KPI extraction since we handle it separately
            if isinstance(SUMMARY_PROMPT, str):
                ai_prompt = SUMMARY_PROMPT.replace(
                    "### KPIs\n- Create a list of key performance indicator objects with structured format.\n- Each KPI object must include: `name`, `current_value`, and `trend` information.\n- **Canonical KPI Enforcement**: If canonical KPIs are provided below, you MUST reuse exactly those KPI names. Do not create new KPI names.\n- **Trend Calculation Rules**:\n  - **FIRST ANALYSIS**: If no previous KPI data is provided below, set ALL trend directions to \"none\" with description \"First analysis - no previous data for comparison\"\n  - **SUBSEQUENT ANALYSIS**: If previous KPI data is provided below, compare current values with previous values:\n    - Extract numeric values from both current and previous (ignore units like ms, %, GB)\n    - `direction`: \"up\" if current > previous (+5% threshold), \"down\" if current < previous (-5% threshold), \"flat\" if within ±5%\n    - `percent_change`: calculate exact percentage change: ((current - previous) / previous) × 100\n    - `description`: brief explanation with actual values (e.g., \"Increased from 528ms to 629ms (+19%)\")\n  - **New KPIs**: For KPIs not found in previous data, use trend direction \"none\" and note \"New KPI - no previous data\"",
                    "### KPIs\n- KPIs will be provided separately via an image-based KPI extraction step. Do NOT include KPIs in your analysis output."
                )
            else:
                ai_prompt = SUMMARY_PROMPT  # None -> EWAAgent will use its internal default
            
            # Run AI analysis for all sections except KPIs
            # Branch based on PROVIDER environment variable
            text_input = (state.markdown_content or "").strip()
            if not text_input:
                raise ValueError("Markdown content is empty; conversion must succeed before analysis.")

            # Inject vision-extracted alert index if available
            if state.alert_index and state.alert_index.get("alerts"):
                alert_json = json.dumps(state.alert_index, indent=2)
                alert_prefix = (
                    "## Pre-Extracted Alert Index (Vision-Based)\n"
                    "The following alerts were extracted from the PDF using vision analysis of the 'Alert Overview' section.\n"
                    "Use this as the **authoritative source** for Key Findings. Each alert MUST become a Key Finding.\n"
                    "The 'severity' field is derived from the visual icon colors (red=critical/high, yellow=medium).\n\n"
                    f"```json\n{alert_json}\n```\n\n"
                    "---\n\n"
                )
                text_input = alert_prefix + text_input
                logger.info("[ANALYSIS] Injected %d vision-extracted alerts into prompt", len(state.alert_index["alerts"]))

            logger.info(
                "[ANALYSIS] Using PROVIDER=%s, markdown input (%s chars)",
                PROVIDER,
                len(text_input),
            )
            
            if PROVIDER == "anthropic":
                # Use Claude via Azure AI Foundry
                agent = self._create_anthropic_agent(ANTHROPIC_SUMMARY_MODEL, ai_prompt)
            else:
                # Default: Use OpenAI via Azure OpenAI
                agent = self._create_agent(AZURE_OPENAI_SUMMARY_MODEL, ai_prompt)
            
            ai_result = await agent.run(text_input, pdf_data=None)
            
            state.summary_json = ai_result if ai_result else {}
            
            # Validate and fix report_date if obviously wrong (fallback to filename)
            state.summary_json = self._fix_report_date_if_invalid(state.summary_json, state.blob_name)
            
            state.summary_result = json_to_markdown(state.summary_json)

            # Step 2b: Extract parameters using fast model
            try:
                logger.info("[STEP 2b] Extracting parameters for %s", state.blob_name)
                if not self.openai_client:
                    raise RuntimeError("OpenAI client not initialized")
                param_agent = ParameterExtractionAgent(self.openai_client)
                state.parameters_json = await param_agent.extract(text_input)
                param_count = len(state.parameters_json.get("parameters", []))
                logger.info("[STEP 2b] Extracted %s parameters", param_count)
            except Exception as param_e:
                logger.warning("[STEP 2b] Parameter extraction failed (non-fatal): %s", param_e)
                state.parameters_json = {"parameters": [], "extraction_notes": f"Extraction failed: {str(param_e)}"}
            
            return state
        except Exception as e:
            state.error = str(e)
            logger.exception("Error in run_analysis_step: %s", e)
            return state

    
    async def save_results_step(self, state: WorkflowState) -> WorkflowState:
        """Step 5: Save all results to blob storage with metadata propagation"""
        try:
            logger.info("[STEP 5] Saving results for %s", state.blob_name)
            base_name = os.path.splitext(state.blob_name)[0]
            
            # Retrieve metadata from original blob
            original_metadata = await self.get_blob_metadata(state.blob_name)
            logger.debug("Retrieved original metadata: %s", original_metadata)
            
            # Save summary markdown with metadata
            summary_blob_name = f"{base_name}_AI.md"
            await self.upload_to_blob(summary_blob_name, state.summary_result, "text/markdown", original_metadata)
            
            # Save structured JSON as well with metadata
            summary_json_blob_name = f"{base_name}_AI.json"
            if state.summary_json is not None:
                await self.upload_to_blob(summary_json_blob_name, json.dumps(state.summary_json, indent=2), "application/json", original_metadata)

                # Persist report_date as blob metadata so that list_files can group by week/month
                report_date = state.summary_json.get("report_date")
                if report_date is None:
                    report_date = state.summary_json.get("system_metadata", {}).get("report_date")
                if report_date:
                    try:
                        orig_blob_client = self.blob_service_client.get_blob_client(
                            container=AZURE_STORAGE_CONTAINER_NAME,
                            blob=state.blob_name
                        )
                        # Offload property retrieval to a thread
                        existing_properties = await asyncio.to_thread(orig_blob_client.get_blob_properties)
                        existing_metadata = (existing_properties.metadata or {}).copy()
                        # Azure metadata keys must be lowercase
                        existing_metadata["report_date"] = report_date
                        # Offload setting metadata to a thread
                        await asyncio.to_thread(orig_blob_client.set_blob_metadata, existing_metadata)
                        logger.info(
                            "Set report_date metadata (%s) on %s",
                            report_date,
                            state.blob_name,
                        )
                    except Exception as meta_e:
                        # Non-fatal; continue even if metadata update fails
                        logger.warning(
                            "Could not set report_date metadata for %s: %s",
                            state.blob_name,
                            meta_e,
                        )

            # Save extracted parameters JSON
            if state.parameters_json is not None:
                params_blob_name = f"{base_name}_parameters.json"
                await self.upload_to_blob(params_blob_name, json.dumps(state.parameters_json, indent=2), "application/json", original_metadata)
                param_count = len(state.parameters_json.get("parameters", []))
                logger.info("Saved %s parameters to %s", param_count, params_blob_name)
            
            return state
        except Exception as e:
            state.error = str(e)
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
            
            # Step 1.5: Extract alerts from PDF using vision (non-fatal if fails)
            state = await self.extract_alerts_step(state)
            
            # Run the EWA analysis using single enhanced agent
            summary_state = await self.run_analysis_step(state)
            
            # Check for errors
            if summary_state.error:
                errors = [f"Agent summary generation failed: {summary_state.error}"]
                raise Exception(f"Workflow step failed: {'; '.join(errors)}")
            
            # Store the summary results
            state.summary_result = summary_state.summary_result
            state.summary_json = summary_state.summary_json
            
            # Save all results
            state = await self.save_results_step(state)
            if state.error:
                raise Exception(state.error)
            
            # Return success response
            base_name = os.path.splitext(blob_name)[0]
            return {
                "success": True,
                "message": "Workflow completed successfully",
                "original_file": blob_name,
                "summary_file": f"{base_name}_AI.md",
                "summary_json_file": f"{base_name}_AI.json",
                "summary_data": state.summary_result,
                "summary_preview": state.summary_result[:500] + "..." if len(state.summary_result) > 500 else state.summary_result
            }
            
        except Exception as e:
            error_message = f"Workflow error: {str(e)}"
            logger.exception(error_message)
            return {
                "success": False,
                "error": True,
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
