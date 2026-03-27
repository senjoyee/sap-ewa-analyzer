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
from datetime import datetime
from typing import Dict, Any
from dataclasses import dataclass
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from dotenv import load_dotenv
from agent.openai_ewa_agent import OpenAIEWAAgent
from agent.anthropic_ewa_agent import AnthropicEWAAgent
from agent.parameter_extraction_agent import ParameterExtractionAgent
from agent.specialist_agents import run_all_specialists, DomainResult
from agent.deep_thinker_agent import DeepThinkerAgent, SupplementalFinding
from utils.markdown_utils import json_to_markdown
from utils.ewa_slicer import slice_chapters, truncate_large_chapter
from utils.ewa_dispatcher import dispatch_chapters
from utils.excel_workbook_builder import build_workbook
from services.storage_service import StorageService
from core.runtime_config import (
    ANTHROPIC_TIMEOUT_SECONDS,
    ANTHROPIC_CONNECT_TIMEOUT_SECONDS,
    SUMMARY_MAX_OUTPUT_TOKENS,
    PARAM_MAX_OUTPUT_TOKENS,
    PDF_METADATA_TEXT_LIMIT,
    PDF_METADATA_MAX_TOKENS,
    SUMMARY_REASONING_EFFORT,
    PARAM_REASONING_EFFORT,
    ANTHROPIC_THINKING_BUDGET_TOKENS,
    ANTHROPIC_TEMPERATURE,
    V2_ROUTER_MODEL,
    V2_SPECIALIST_MODEL,
    V2_DEEP_MODEL,
    V2_SPECIALIST_MAX_TOKENS,
    V2_DEEP_MAX_TOKENS,
    V2_SPECIALIST_REASONING,
    V2_DEEP_REASONING,
    V2_LARGE_CHAPTER_LIMIT,
)

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

    if PROVIDER == "anthropic":
        candidate_files = [
            "ewa_summary_prompt_anthropic.md",
            "ewa_summary_prompt.md",
        ]
    else:
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
    summary_usage: dict = None
    parameter_usage: dict = None
    usage_report: dict = None
    error: str = ""
    # V2 pipeline fields
    domain_results: list = None
    supplemental_findings: list = None
    workbook_bytes: bytes = None
    v2_usage: dict = None


MODEL_PRICING_USD_PER_1M = {
    "gpt-5.4": {"input": 2.5, "cached_input": 0.625, "output": 20.0},
    "gpt-5.2": {"input": 1.75, "cached_input": 0.175, "output": 14.0},
    "gpt-5.1": {"input": 1.25, "cached_input": 0.125, "output": 10.0},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.0},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.0},
    "claude-haiku-4.5": {"input": 1.0, "cached_input": 0.1, "output": 5.0},
    "claude-haiku-4-5": {"input": 1.0, "cached_input": 0.1, "output": 5.0},
    "claude-sonnet-4.6": {"input": 3.0, "cached_input": 0.3, "output": 15.0},
    "claude-sonnet-4-6": {"input": 3.0, "cached_input": 0.3, "output": 15.0},
    "claude-opus-4.6": {"input": 15.0, "cached_input": 1.5, "output": 75.0},
    "claude-opus-4-6": {"input": 15.0, "cached_input": 1.5, "output": 75.0},
}

OPENAI_PRICING_SOURCE_URL = "https://openai.com/api/pricing/"
ANTHROPIC_PRICING_SOURCE_URL = "https://www.anthropic.com/pricing"

class EWAWorkflowOrchestrator:
    """Custom orchestrator for EWA analysis workflows"""
    
    def __init__(self):
        self.client = None
        self.blob_service_client = None
        self.openai_client = None
        self.summary_model = ANTHROPIC_SUMMARY_MODEL if PROVIDER == "anthropic" else AZURE_OPENAI_SUMMARY_MODEL
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

    def _normalize_model_key(self, model_name: str | None) -> str | None:
        if not model_name:
            return None
        normalized = model_name.strip().lower()
        for key in MODEL_PRICING_USD_PER_1M:
            if normalized == key or normalized.startswith(f"{key}-"):
                return key
        return None

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

    def _calculate_usage_cost(self, usage: dict | None) -> dict | None:
        if not usage:
            return None
        model_name = usage.get("model")
        model_key = self._normalize_model_key(model_name)
        pricing = MODEL_PRICING_USD_PER_1M.get(model_key)
        input_tokens = int(usage.get("input_tokens") or 0)
        cached_input_tokens = int(usage.get("cached_input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        reasoning_tokens = int(usage.get("reasoning_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
        non_cached_input_tokens = max(input_tokens - cached_input_tokens, 0)

        cost_breakdown = {
            "input_non_cached_usd": None,
            "input_cached_usd": None,
            "output_usd": None,
            "total_usd": None,
        }

        if pricing:
            cost_breakdown["input_non_cached_usd"] = round((non_cached_input_tokens / 1_000_000) * pricing["input"], 6)
            cost_breakdown["input_cached_usd"] = round((cached_input_tokens / 1_000_000) * pricing["cached_input"], 6)
            cost_breakdown["output_usd"] = round((output_tokens / 1_000_000) * pricing["output"], 6)
            cost_breakdown["total_usd"] = round(
                cost_breakdown["input_non_cached_usd"] + cost_breakdown["input_cached_usd"] + cost_breakdown["output_usd"],
                6,
            )

        return {
            "model": model_name,
            "model_pricing_key": model_key,
            "reasoning_effort": usage.get("reasoning_effort"),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "non_cached_input_tokens": non_cached_input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": total_tokens,
            "reasoning_tokens_billed_as_output_tokens": True,
            "pricing_usd_per_1m_tokens": pricing,
            "cost_usd": cost_breakdown,
        }

    def _sanitize_report_name_part(self, value: str | None, fallback: str) -> str:
        raw = (value or "").strip()
        if not raw:
            raw = fallback
        cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in raw)
        cleaned = cleaned.strip("_")
        return cleaned or fallback

    def _resolve_report_system_id(self, state: WorkflowState, metadata: dict | None) -> str:
        metadata = metadata or {}
        candidates = [
            metadata.get("system_id"),
            state.summary_json.get("system_id") if isinstance(state.summary_json, dict) else None,
            (state.summary_json.get("system_metadata") or {}).get("system_id") if isinstance(state.summary_json, dict) and isinstance(state.summary_json.get("system_metadata"), dict) else None,
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip().upper()
        return "UNKNOWN"

    def _build_usage_report(self, state: WorkflowState, original_metadata: dict | None) -> dict:
        generated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        summary_usage = self._calculate_usage_cost(state.summary_usage)
        parameter_usage = self._calculate_usage_cost(state.parameter_usage)
        items = [item for item in [summary_usage, parameter_usage] if item]
        aggregate = {
            "input_tokens": sum(item.get("input_tokens", 0) for item in items),
            "cached_input_tokens": sum(item.get("cached_input_tokens", 0) for item in items),
            "non_cached_input_tokens": sum(item.get("non_cached_input_tokens", 0) for item in items),
            "output_tokens": sum(item.get("output_tokens", 0) for item in items),
            "reasoning_tokens": sum(item.get("reasoning_tokens", 0) for item in items),
            "total_tokens": sum(item.get("total_tokens", 0) for item in items),
            "total_cost_usd": round(sum((item.get("cost_usd") or {}).get("total_usd", 0) or 0 for item in items), 6),
        }
        return {
            "generated_at_utc": generated_at,
            "source_blob": state.blob_name,
            "provider": PROVIDER,
            "system_id": self._resolve_report_system_id(state, original_metadata),
            "pricing_source": {
                "url": ANTHROPIC_PRICING_SOURCE_URL if PROVIDER == "anthropic" else OPENAI_PRICING_SOURCE_URL,
                "notes": [
                    f"{'Anthropic' if PROVIDER == 'anthropic' else 'OpenAI'} pricing retrieved from official documentation.",
                    "Cached inputs are billed at a significantly reduced rate.",
                ],
            },
            "summary": summary_usage,
            "parameter_extraction": parameter_usage,
            "aggregate": aggregate,
        }

    def _build_usage_report_blob_name(self, state: WorkflowState, original_metadata: dict | None) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        system_id = self._sanitize_report_name_part(self._resolve_report_system_id(state, original_metadata), "UNKNOWN")
        base_name = self._sanitize_report_name_part(os.path.splitext(state.blob_name)[0], "analysis")
        return f"{system_id}_{timestamp}_{base_name}_token_usage.json"
    
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
        return OpenAIEWAAgent(client=client, model=model_name, summary_prompt=summary_prompt, reasoning_effort=SUMMARY_REASONING_EFFORT)

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
    
    def _create_anthropic_agent(self, model: str | None = None, summary_prompt: str | None = None) -> AnthropicEWAAgent:
        """Create an AnthropicEWAAgent for Azure AI Foundry (Claude) models."""
        model_name = model or ANTHROPIC_SUMMARY_MODEL
        logger.info("Creating AnthropicEWAAgent with model: %s", model_name)

        client = self._create_anthropic_client()
        return AnthropicEWAAgent(
            client=client,
            model=model_name,
            summary_prompt=summary_prompt,
            reasoning_effort=SUMMARY_REASONING_EFFORT,
            thinking_budget=ANTHROPIC_THINKING_BUDGET_TOKENS,
            temperature=ANTHROPIC_TEMPERATURE,
        )
    
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
                "Analysis - Customer: %s, System: %s, Report Date: %s, Provider: %s",
                customer_name,
                system_id,
                report_date_str,
                PROVIDER
            )
            
            # Run AI analysis using the full prompt
            ai_prompt = SUMMARY_PROMPT
            
            # Branch based on PROVIDER environment variable
            text_input = (state.markdown_content or "").strip()
            if not text_input:
                raise ValueError("Markdown content is empty; conversion must succeed before analysis.")

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
            state.summary_usage = getattr(agent, "last_usage", {}) or {}
            
            # Validate and fix report_date if obviously wrong (fallback to filename)
            state.summary_json = self._fix_report_date_if_invalid(state.summary_json, state.blob_name)
            
            state.summary_result = json_to_markdown(state.summary_json)

            # Step 2b: Extract parameters using fast model
            try:
                logger.info("[STEP 2b] Extracting parameters for %s", state.blob_name)
                if PROVIDER == "anthropic":
                    param_client = self._create_anthropic_client()
                    param_agent = ParameterExtractionAgent(
                        param_client,
                        model=ANTHROPIC_SUMMARY_MODEL,
                        provider="anthropic",
                        reasoning_effort=PARAM_REASONING_EFFORT,
                        thinking_budget=ANTHROPIC_THINKING_BUDGET_TOKENS,
                    )
                else:
                    if not self.openai_client:
                        raise RuntimeError("OpenAI client not initialized")
                    param_agent = ParameterExtractionAgent(
                        self.openai_client,
                        model=os.getenv("AZURE_OPENAI_PARAM_MODEL", "gpt-5.1"),
                        provider="openai",
                    )
                state.parameters_json = await param_agent.extract(text_input)
                state.parameter_usage = getattr(param_agent, "last_usage", {}) or {}
                param_count = len(state.parameters_json.get("parameters", []))
                logger.info("[STEP 2b] Extracted %s parameters", param_count)
            except Exception as param_e:
                logger.warning("[STEP 2b] Parameter extraction failed (non-fatal): %s", param_e)
                state.parameters_json = {"parameters": [], "extraction_notes": f"Extraction failed: {str(param_e)}"}
                state.parameter_usage = getattr(locals().get("param_agent"), "last_usage", {}) or {}
            
            return state
        except Exception as e:
            state.error = str(e)
            logger.exception("Error in run_analysis_step: %s", e)
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
            logger.info("[V2] Starting agentic pipeline for %s", state.blob_name)
            text = (state.markdown_content or "").strip()
            if not text:
                raise ValueError("Markdown content is empty; conversion must succeed before analysis.")

            # Stage 1: Slice markdown into chapters
            logger.info("[V2-SLICE] Parsing chapters from markdown (%d chars)", len(text))
            chapters = slice_chapters(text)
            logger.info("[V2-SLICE] Extracted %d chapters", len(chapters))

            # Truncate oversized chapters (e.g. ch19 SQL statements)
            for num, ch in chapters.items():
                if len(ch.raw_content) > V2_LARGE_CHAPTER_LIMIT:
                    chapters[num] = truncate_large_chapter(ch, V2_LARGE_CHAPTER_LIMIT)
                    logger.info("[V2-SLICE] Truncated chapter %d from %d to %d chars",
                                num, len(ch.raw_content), len(chapters[num].raw_content))

            # Stage 2: Dispatch chapters to domains
            logger.info("[V2-DISPATCH] Routing chapters to domains (router=%s)", V2_ROUTER_MODEL)
            domain_chapters = await dispatch_chapters(
                chapters,
                ai_client=self.openai_client,
                router_model=V2_ROUTER_MODEL,
            )
            for domain, chs in domain_chapters.items():
                if chs:
                    logger.info("[V2-DISPATCH] %s: %d chapters", domain, len(chs))

            # Stage 3a: Run 6 specialists in parallel
            logger.info("[V2-SPECIALISTS] Running 6 domain specialists (model=%s)", V2_SPECIALIST_MODEL)
            domain_results = await run_all_specialists(
                domain_chapters,
                client=self.openai_client,
                model=V2_SPECIALIST_MODEL,
                reasoning_effort=V2_SPECIALIST_REASONING,
                max_output_tokens=V2_SPECIALIST_MAX_TOKENS,
            )
            state.domain_results = domain_results

            total_findings = sum(len(dr.findings) for dr in domain_results)
            total_params = sum(len(dr.parameters) for dr in domain_results)
            total_abstentions = sum(len(dr.abstentions) for dr in domain_results)
            logger.info("[V2-SPECIALISTS] Done: %d findings, %d parameters, %d abstentions",
                        total_findings, total_params, total_abstentions)

            # Stage 3b: Deep Thinker cross-domain analysis
            logger.info("[V2-DEEP] Running Deep Thinker (model=%s)", V2_DEEP_MODEL)
            deep_thinker = DeepThinkerAgent(
                client=self.openai_client,
                model=V2_DEEP_MODEL,
                reasoning_effort=V2_DEEP_REASONING,
                max_output_tokens=V2_DEEP_MAX_TOKENS,
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
            state.workbook_bytes = build_workbook(domain_results, supplemental, system_metadata)
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
