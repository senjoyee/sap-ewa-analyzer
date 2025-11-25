"""
SAP EWA Analysis Workflow Orchestration Module

This module implements a 3-phase agentic pipeline for analyzing SAP Early Watch Alert (EWA) reports
using Azure OpenAI Responses API with Structured Outputs.

Pipeline Architecture:
- Phase 1 (Extraction): gpt-4o-mini, effort=low - Pure data extraction
- Phase 2 (Analysis): gpt-5, effort=high - Deep analytical assessment  
- Phase 3 (Strategy): gpt-4o, effort=medium - Executive synthesis

Key Functionality:
- 3-phase sequential agent pipeline with phase-specific models and reasoning effort
- Progressive validation between phases
- Integration with Azure Blob Storage for document persistence
- Error handling and status reporting

The orchestrator ensures a cohesive end-to-end analysis process for SAP EWA reports.
"""

import os
import json
import asyncio
import traceback
from datetime import datetime
from typing import Dict, Any
from dataclasses import dataclass
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from dotenv import load_dotenv
from agent.extraction_agent import ExtractionAgent
from agent.analysis_agent import AnalysisAgent
from agent.strategy_agent import StrategyAgent
from utils.markdown_utils import json_to_markdown
from converters.document_converter import convert_document_to_markdown

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Model deployment names for each phase
# Phase 1 (Extraction): Fast, cheap model
EXTRACTION_MODEL = os.getenv("AZURE_OPENAI_FAST_MODEL") or os.getenv("AZURE_OPENAI_SUMMARY_MODEL") or "gpt-4o-mini"
# Phase 2 (Analysis): Most capable model with high reasoning
ANALYSIS_MODEL = os.getenv("AZURE_OPENAI_SUMMARY_MODEL") or "gpt-5"
# Phase 3 (Strategy): Mid-tier model
STRATEGY_MODEL = os.getenv("AZURE_OPENAI_STRATEGY_MODEL") or os.getenv("AZURE_OPENAI_SUMMARY_MODEL") or "gpt-4o"

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")




@dataclass
class WorkflowState:
    """State object for workflow execution"""
    blob_name: str
    markdown_content: str = ""
    summary_result: str = ""
    summary_json: dict = None
    error: str = ""

class EWAWorkflowOrchestrator:
    """Custom orchestrator for 3-phase EWA analysis workflow"""
    
    def __init__(self):
        self.blob_service_client = None
        self.azure_openai_endpoint = AZURE_OPENAI_ENDPOINT
        self.azure_openai_api_key = AZURE_OPENAI_API_KEY
        self.azure_openai_api_version = AZURE_OPENAI_API_VERSION
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Azure Blob Storage client"""
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                AZURE_STORAGE_CONNECTION_STRING
            )
            print("Successfully initialized Blob Storage client")
        except Exception as e:
            print(f"Error initializing clients: {str(e)}")
            raise
    
    def _create_openai_client(self) -> AzureOpenAI:
        """Create Azure OpenAI client for agent use."""
        if not self.azure_openai_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
        if not self.azure_openai_api_key:
            raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
        if not self.azure_openai_api_version:
            raise ValueError("AZURE_OPENAI_API_VERSION environment variable is required")
        return AzureOpenAI(
            api_version=self.azure_openai_api_version,
            azure_endpoint=self.azure_openai_endpoint,
            api_key=self.azure_openai_api_key,
        )
    
    async def download_markdown_from_blob(self, blob_name: str) -> str:
        """Download markdown content from Azure Blob Storage"""
        try:
            # Convert original filename to .md format
            base_name = os.path.splitext(blob_name)[0]
            md_blob_name = f"{base_name}.md"
            
            print(f"Downloading markdown content from {md_blob_name}")
            
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=md_blob_name
            )
            
            # Download the blob content off the event loop to avoid blocking
            def _read_md() -> str:
                downloader = blob_client.download_blob()
                return downloader.readall().decode('utf-8')
            content = await asyncio.to_thread(_read_md)
            
            print(f"Successfully downloaded {len(content)} characters of markdown content")
            return content
            
        except Exception as e:
            error_message = f"Error downloading markdown from blob storage: {str(e)}"
            print(error_message)
            raise Exception(error_message)
    
    async def download_pdf_from_blob(self, blob_name: str) -> bytes:
        """Download original PDF content from Azure Blob Storage for multimodal analysis"""
        try:
            print(f"Downloading PDF content from {blob_name}")
            
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=blob_name
            )
            
            # Download the blob content as bytes off the event loop
            def _read_pdf() -> bytes:
                downloader = blob_client.download_blob()
                return downloader.readall()
            content = await asyncio.to_thread(_read_pdf)
            
            print(f"Successfully downloaded {len(content)} bytes of PDF content")
            return content
            
        except Exception as e:
            error_message = f"Error downloading PDF from blob storage: {str(e)}"
            print(error_message)
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
                print(f"Uploading {blob_name} with metadata: {metadata}")
            
            # Offload blocking upload to a thread
            await asyncio.to_thread(lambda: blob_client.upload_blob(**upload_params))
            
            print(f"Successfully uploaded content to {blob_name}")
            return blob_name
            
        except Exception as e:
            error_message = f"Error uploading to blob storage: {str(e)}"
            print(error_message)
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
            print(f"Error retrieving metadata for {blob_name}: {str(e)}")
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
            print(f"Warning: could not {state} processing metadata for {blob_name}: {e}")
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
            print(f"Warning: could not {action} metadata '{key}' for {blob_name}: {e}")
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
            print(f"[STEP 1] Downloading content for {state.blob_name}")
            state.markdown_content = await self.download_markdown_from_blob(state.blob_name)
            return state
        except Exception as e:
            if skip_conversion:
                state.error = str(e)
                return state
            # Attempt to generate markdown via converter when missing
            try:
                print(f"[STEP 1] Markdown not found for {state.blob_name}; attempting conversion to markdown")
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
    

    async def run_analysis_step(self, state: WorkflowState) -> WorkflowState:
        """Step 2: Run 3-phase agentic pipeline for EWA analysis.
        
        Phase 1 (Extraction): gpt-4o-mini, effort=low - Pure data extraction
        Phase 2 (Analysis): gpt-5, effort=high - Deep analytical assessment
        Phase 3 (Strategy): gpt-4o, effort=medium - Executive synthesis
        """
        try:
            print(f"[STEP 2] Running 3-phase EWA analysis for {state.blob_name}")
            
            text_input = (state.markdown_content or "").strip()
            if not text_input:
                raise ValueError("Markdown content is empty; conversion must succeed before analysis.")

            print(f"[3-PHASE] Input: {len(text_input)} chars of markdown")
            
            # Create shared OpenAI client
            client = self._create_openai_client()
            
            # ─────────────────────────────────────────────────────────────────
            # PHASE 1: Extraction (gpt-4o-mini, effort=low)
            # ─────────────────────────────────────────────────────────────────
            print(f"[PHASE 1] Starting extraction with model: {EXTRACTION_MODEL}")
            extraction_agent = ExtractionAgent(client=client, model=EXTRACTION_MODEL)
            phase1_result = await extraction_agent.run(text_input)
            print(f"[PHASE 1] Complete - SID: {phase1_result.get('System Metadata', {}).get('System ID', 'Unknown')}")
            
            # ─────────────────────────────────────────────────────────────────
            # PHASE 2: Analysis (gpt-5, effort=high)
            # ─────────────────────────────────────────────────────────────────
            print(f"[PHASE 2] Starting analysis with model: {ANALYSIS_MODEL}")
            analysis_agent = AnalysisAgent(client=client, model=ANALYSIS_MODEL)
            phase2_result = await analysis_agent.run(text_input, phase1_result)
            findings_count = len(phase2_result.get("Key Findings", []))
            print(f"[PHASE 2] Complete - {findings_count} findings, risk: {phase2_result.get('Overall Risk', 'unknown')}")
            
            # ─────────────────────────────────────────────────────────────────
            # PHASE 3: Strategy (gpt-4o, effort=medium)
            # ─────────────────────────────────────────────────────────────────
            print(f"[PHASE 3] Starting strategy with model: {STRATEGY_MODEL}")
            strategy_agent = StrategyAgent(client=client, model=STRATEGY_MODEL)
            phase3_result = await strategy_agent.run(phase1_result, phase2_result)
            rec_count = len(phase3_result.get("Recommendations", []))
            print(f"[PHASE 3] Complete - {rec_count} recommendations")
            
            # ─────────────────────────────────────────────────────────────────
            # MERGE: Combine all phases into final output
            # ─────────────────────────────────────────────────────────────────
            final_json = self._merge_phase_results(phase1_result, phase2_result, phase3_result)
            print(f"[MERGE] Final JSON assembled with {len(final_json)} top-level keys")
            
            state.summary_json = final_json
            state.summary_result = json_to_markdown(final_json)
            return state
            
        except Exception as e:
            state.error = str(e)
            print(f"Error in run_analysis_step: {str(e)}")
            traceback.print_exc()
            return state

    def _merge_phase_results(
        self,
        phase1: Dict[str, Any],
        phase2: Dict[str, Any],
        phase3: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge outputs from all 3 phases into final schema-compliant JSON."""
        return {
            "Schema Version": "1.1",
            # From Phase 1
            "System Metadata": phase1.get("System Metadata", {}),
            "Chapters Reviewed": phase1.get("Chapters Reviewed", []),
            # From Phase 2
            "System Health Overview": phase2.get("System Health Overview", {}),
            "Positive Findings": phase2.get("Positive Findings", []),
            "Key Findings": phase2.get("Key Findings", []),
            "Capacity Outlook": phase2.get("Capacity Outlook", {}),
            "Overall Risk": phase2.get("Overall Risk", "medium"),
            # From Phase 3
            "Executive Summary": phase3.get("Executive Summary", ""),
            "Recommendations": phase3.get("Recommendations", []),
        }

    
    async def save_results_step(self, state: WorkflowState) -> WorkflowState:
        """Step 5: Save all results to blob storage with metadata propagation"""
        try:
            print(f"[STEP 5] Saving results for {state.blob_name}")
            base_name = os.path.splitext(state.blob_name)[0]
            
            # Retrieve metadata from original blob
            original_metadata = await self.get_blob_metadata(state.blob_name)
            print(f"Retrieved original metadata: {original_metadata}")
            
            # Save summary markdown with metadata
            summary_blob_name = f"{base_name}_AI.md"
            await self.upload_to_blob(summary_blob_name, state.summary_result, "text/markdown", original_metadata)
            
            # Save structured JSON as well with metadata
            summary_json_blob_name = f"{base_name}_AI.json"
            if state.summary_json is not None:
                await self.upload_to_blob(summary_json_blob_name, json.dumps(state.summary_json, indent=2), "application/json", original_metadata)

                # Persist report_date as blob metadata so that list_files can group by week/month
                # Support both Title Case (3-phase output) and snake_case (legacy)
                report_date = state.summary_json.get("Report Date")
                if report_date is None:
                    report_date = state.summary_json.get("System Metadata", {}).get("Report Date")
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
                        print(f"Set report_date metadata ({report_date}) on {state.blob_name}")
                    except Exception as meta_e:
                        # Non-fatal; continue even if metadata update fails
                        print(f"Warning: could not set report_date metadata for {state.blob_name}: {meta_e}")
            
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
            print(f"Warning: unable to mark {blob_name} as processing: {flag_err}")

        try:
            print(f"Starting workflow for {blob_name}")
            
            # Initialize state
            state = WorkflowState(blob_name=blob_name)
            
            # Execute workflow steps sequentially (markdown required)
            state = await self.download_content_step(state, skip_conversion=skip_markdown)
            if state.error:
                raise Exception(state.error)
            
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
            print(error_message)
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
