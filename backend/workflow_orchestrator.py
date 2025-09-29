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
import traceback # Added for exception logging
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from dotenv import load_dotenv
from agent.ewa_agent import EWAAgent
from agent.kpi_image_agent import KPIImageAgent
from agent.document_structure_agent import DocumentStructureAgent
from utils.markdown_utils import json_to_markdown
from models.gemini_client import GeminiClient, is_gemini_model, create_gemini_client

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Model deployment name
AZURE_OPENAI_SUMMARY_MODEL = os.getenv("AZURE_OPENAI_SUMMARY_MODEL", "gpt-4.1")
AZURE_OPENAI_FAST_MODEL = os.getenv("AZURE_OPENAI_FAST_MODEL", "gpt-4.1-mini")

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

# System prompts for each workflow
# System prompts for each workflow
def load_summary_prompt() -> str | None:
    """Return the first available summary prompt content, or None if none found.
    Preference order:
    - If Gemini model is configured, prefer the Gemini-specific prompt.
    - Otherwise, prefer the GPT-5 optimized OpenAI prompt when present.
    - Fallback to OpenAI or legacy prompts.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_dir = os.path.join(current_dir, "prompts")

    # Prefer model-appropriate prompt
    if is_gemini_model(AZURE_OPENAI_SUMMARY_MODEL):
        candidate_files = [
            "ewa_summary_prompt_openai_google.md", # Gemini-specific
            "ewa_summary_prompt_openai_gpt5.md",   # Fallback to GPT-5 optimized
            "ewa_summary_prompt_openai.md",        # OpenAI-specific
            "ewa_summary_prompt.md",               # legacy path
        ]
    else:
        candidate_files = [
            "ewa_summary_prompt_openai_gpt5.md",   # GPT-5 optimized (preferred for OpenAI models)
            "ewa_summary_prompt_openai.md",        # OpenAI-specific
            "ewa_summary_prompt.md",               # legacy path
            "ewa_summary_prompt_openai_google.md", # Gemini-specific (as last resort)
        ]

    for filename in candidate_files:
        path = os.path.join(prompt_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    print(f"Loaded summary prompt from {path}")
                    return f.read()
            except Exception as e:
                print(f"Warning: Could not read prompt file {path}: {e}")
    # No prompt files found – return None so that downstream logic can fall back
    print("No summary prompt files found; EWAAgent will use its internal default prompts.")
    return None

SUMMARY_PROMPT: str | None = load_summary_prompt()




@dataclass
class WorkflowState:
    """State object for workflow execution"""
    blob_name: str
    markdown_content: str = ""
    summary_result: str = ""
    summary_json: dict = None
    pdf_bytes: bytes = None
    chapters: list = None
    error: str = ""

class EWAWorkflowOrchestrator:
    """Custom orchestrator for EWA analysis workflows"""
    
    def __init__(self):
        self.client = None
        self.blob_service_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Azure OpenAI and Blob Storage clients"""
        try:
            # Initialize Azure OpenAI client
            self.client = AzureOpenAI(
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                api_version=AZURE_OPENAI_API_VERSION
            )
            
            # Initialize Blob Storage client
            self.blob_service_client = BlobServiceClient.from_connection_string(
                AZURE_STORAGE_CONNECTION_STRING
            )
            
            print("Successfully initialized Azure OpenAI and Blob Storage clients")
            
        except Exception as e:
            print(f"Error initializing clients: {str(e)}")
            raise
    
    def _create_agent(self, model: str, summary_prompt: str | None = None) -> EWAAgent:
        """Create appropriate agent (OpenAI or Gemini) based on model name"""
        try:
            if is_gemini_model(model):
                # Create Gemini client
                gemini_client = create_gemini_client(model)
                print(f"Creating EWAAgent with Gemini model: {model}")
                return EWAAgent(client=gemini_client, model=model, summary_prompt=summary_prompt)
            else:
                # Use Azure OpenAI client
                print(f"Creating EWAAgent with Azure OpenAI model: {model}")
                return EWAAgent(client=self.client, model=model, summary_prompt=summary_prompt)
                
        except Exception as e:
            print(f"Error creating agent for model {model}: {str(e)}")
            raise
    
    def _validate_chapter_coverage(self, expected_chapters: list[str], analysis_json: dict) -> None:
        """Validate that the analysis covered all expected chapters and log results."""
        try:
            analyzed_chapters = analysis_json.get("Chapters Analyzed", [])
            
            if not analyzed_chapters:
                print("[CHAPTER COVERAGE] WARNING: No 'Chapters Analyzed' field in output")
                return
            
            print(f"[CHAPTER COVERAGE] Expected {len(expected_chapters)} chapters, analyzed {len(analyzed_chapters)} chapters")
            
            # Normalize chapter names for comparison (case-insensitive, strip whitespace)
            def normalize(ch: str) -> str:
                return ch.lower().strip()
            
            expected_set = {normalize(ch) for ch in expected_chapters}
            analyzed_set = {normalize(ch) for ch in analyzed_chapters}
            
            # Find missing chapters
            missing = expected_set - analyzed_set
            if missing:
                print(f"[CHAPTER COVERAGE] WARNING: {len(missing)} chapters may have been missed:")
                for ch in missing:
                    # Find original casing
                    original = next((c for c in expected_chapters if normalize(c) == ch), ch)
                    print(f"  - {original}")
            else:
                print("[CHAPTER COVERAGE] ✓ All expected chapters were analyzed")
            
            # Check for extra chapters (informational only)
            extra = analyzed_set - expected_set
            if extra:
                print(f"[CHAPTER COVERAGE] INFO: {len(extra)} additional chapters were analyzed:")
                for ch in extra:
                    original = next((c for c in analyzed_chapters if normalize(c) == ch), ch)
                    print(f"  - {original}")
            
            # Validate source chapter tracking in findings
            key_findings = analysis_json.get("Key Findings", [])
            findings_without_source = [
                f.get("Issue ID", "Unknown") 
                for f in key_findings 
                if not f.get("Source Chapter")
            ]
            if findings_without_source:
                print(f"[CHAPTER COVERAGE] WARNING: {len(findings_without_source)} Key Findings missing 'Source Chapter':")
                for fid in findings_without_source[:5]:  # Show first 5
                    print(f"  - {fid}")
            else:
                print(f"[CHAPTER COVERAGE] ✓ All {len(key_findings)} Key Findings have source chapter tracking")
                
        except Exception as e:
            print(f"[CHAPTER COVERAGE] Error during validation: {e}")
    
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
 
    
    # Workflow step functions
    async def download_content_step(self, state: WorkflowState) -> WorkflowState:
        """Step 1: Download markdown content from blob storage"""
        try:
            print(f"[STEP 1] Downloading content for {state.blob_name}")
            state.markdown_content = await self.download_markdown_from_blob(state.blob_name)
            return state
        except Exception as e:
            state.error = str(e)
            return state
    

    async def extract_document_structure_step(self, state: WorkflowState) -> WorkflowState:
        """Step 1.5: Extract document chapter structure for comprehensive analysis coverage"""
        try:
            print(f"[STEP 1.5] Extracting document structure for {state.blob_name}")
            
            # Ensure PDF is downloaded
            if state.pdf_bytes is None:
                state.pdf_bytes = await self.download_pdf_from_blob(state.blob_name)
            
            # Extract chapter structure
            structure_agent = DocumentStructureAgent(client=self.client)
            structure_result = await asyncio.to_thread(
                structure_agent.extract_structure_from_pdf_bytes,
                state.pdf_bytes
            )
            
            # Extract chapter names from the result
            chapters_data = structure_result.get("chapters", [])
            state.chapters = []
            for ch in chapters_data:
                ch_num = ch.get("chapter_number", "")
                ch_name = ch.get("chapter_name", "")
                if ch_num and ch_name:
                    state.chapters.append(f"{ch_num} {ch_name}")
                elif ch_name:
                    state.chapters.append(ch_name)
            
            print(f"[STEP 1.5] Extracted {len(state.chapters)} chapters for analysis coverage")
            return state
        except Exception as e:
            # Non-fatal: continue without chapter structure if extraction fails
            print(f"[STEP 1.5] Warning: Chapter extraction failed: {e}")
            print("[STEP 1.5] Continuing analysis without chapter structure guidance")
            state.chapters = []
            return state

    async def run_analysis_step(self, state: WorkflowState) -> WorkflowState:
        """Step 2: Generate comprehensive EWA analysis with chapter awareness; then extract KPIs via image agent"""
        try:
            print(f"[STEP 2] Running chapter-aware EWA analysis for {state.blob_name}")
            
            # Get metadata from original blob for KPI management
            original_metadata = await self.get_blob_metadata(state.blob_name)
            customer_name = original_metadata.get('customer_name', '')
            system_id = original_metadata.get('system_id', '')
            report_date_str = original_metadata.get('report_date_str', '')
            
            print(f"Analysis - Customer: {customer_name}, System: {system_id}, Report Date: {report_date_str}")
            
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
            agent = self._create_agent(AZURE_OPENAI_SUMMARY_MODEL, ai_prompt)
            
            # Ensure PDF is downloaded if not already
            if state.pdf_bytes is None:
                state.pdf_bytes = await self.download_pdf_from_blob(state.blob_name)
            
            pdf_length = len(state.pdf_bytes) if state.pdf_bytes is not None else 0
            
            # Determine input type based on model
            if is_gemini_model(AZURE_OPENAI_SUMMARY_MODEL):
                # For Gemini models, use original PDF. On failure, propagate error (no markdown fallback).
                print(f"[Gemini Workflow] Using original PDF ({pdf_length} bytes) for analysis")
                ai_result = await agent.run(state.markdown_content, pdf_data=state.pdf_bytes, chapters=state.chapters)
            else:
                # For OpenAI models, use original PDF via Responses API. On failure, propagate error (no markdown fallback).
                print(f"[OpenAI Workflow] Using original PDF ({pdf_length} bytes) for analysis via Responses API")
                if state.chapters:
                    print(f"[OpenAI Workflow] Providing {len(state.chapters)} chapters for comprehensive coverage")
                ai_result = await agent.run(state.markdown_content, pdf_data=state.pdf_bytes, chapters=state.chapters)
            
            # Step 2: Extract KPIs via image-based agent (single high-res page to GPT-5)
            final_json = ai_result.copy() if ai_result else {}
            try:
                kpi_agent = KPIImageAgent(client=self.client)
                kpi_result = await asyncio.to_thread(kpi_agent.extract_kpis_from_pdf_bytes, state.pdf_bytes)
                final_json['kpis'] = kpi_result.get('kpis', [])
                print(f"[KPI IMAGE AGENT] Extracted {len(final_json['kpis'])} KPI rows")
            except Exception as kpi_e:
                print(f"[KPI IMAGE AGENT] KPI extraction failed: {kpi_e}")
            
            state.summary_json = final_json
            state.summary_result = json_to_markdown(final_json)
            
            # Validate chapter coverage if chapters were provided
            if state.chapters:
                self._validate_chapter_coverage(state.chapters, final_json)
            
            return state
        except Exception as e:
            state.error = str(e)
            print(f"Error in run_analysis_step: {str(e)}")
            traceback.print_exc()
            return state

    
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
            skip_markdown: If True, do not download or rely on converted markdown; run analysis directly on the PDF.
        """
        try:
            print(f"Starting workflow for {blob_name}")
            
            # Initialize state
            state = WorkflowState(blob_name=blob_name)
            
            # Execute workflow steps sequentially
            if skip_markdown:
                print("[WORKFLOW] skip_markdown=True: Skipping markdown download; proceeding with PDF-first analysis")
            else:
                state = await self.download_content_step(state)
                if state.error:
                    raise Exception(state.error)
            
            # Extract document structure for chapter-aware analysis
            state = await self.extract_document_structure_step(state)
            # Note: structure extraction errors are non-fatal; we continue even if it fails
            
            # Run the EWA analysis using single enhanced agent (now chapter-aware)
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

# Global orchestrator instance
ewa_orchestrator = EWAWorkflowOrchestrator()

async def execute_ewa_analysis(blob_name: str, pdf_first: bool = False) -> Dict[str, Any]:
    """
    Convenience function to execute EWA analysis workflow
    
    Args:
        blob_name: Name of the file to analyze
        pdf_first: If True, skip markdown and analyze directly from PDF
    
    Returns:
        dict: Analysis result
    """
    return await ewa_orchestrator.execute_workflow(blob_name, skip_markdown=pdf_first)


async def execute_ewa_analysis_pdf_first(blob_name: str) -> Dict[str, Any]:
    """Explicit helper to run PDF-first analysis (skips markdown parsing)."""
    return await ewa_orchestrator.execute_workflow(blob_name, skip_markdown=True)
