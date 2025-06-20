"""
SAP EWA Analysis Workflow Orchestration Module

This module implements a custom orchestration system for analyzing SAP Early Watch Alert (EWA) reports
using Azure OpenAI services. It manages the workflow for generating comprehensive analysis of EWA reports:

1. Summary Workflow - Generates an executive summary with findings and recommendations

Key Functionality:
- Orchestrating AI analysis workflow
- Specialized prompting for comprehensive information extraction
- Integration with Azure Blob Storage for document persistence
- Error handling and status reporting

The orchestrator ensures a cohesive end-to-end analysis process for SAP EWA reports.
"""

import os
import json
import re
import asyncio
import traceback # Added for exception logging
from typing import Dict, Any, List
from dataclasses import dataclass
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from dotenv import load_dotenv
from agent.ewa_agent import EWAAgent
from utils.markdown_utils import json_to_markdown
from converters import document_converter # Added for combined workflow

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Model deployment name
AZURE_OPENAI_SUMMARY_MODEL = os.getenv("AZURE_OPENAI_SUMMARY_MODEL", "gpt-4.1")

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

# System prompts for each workflow
# System prompts for each workflow
def load_summary_prompt():
    """Loads the summary system prompt from the prompts directory."""
    # Construct the absolute path to the prompts directory
    # __file__ is the path to the current script (workflow_orchestrator.py)
    # os.path.dirname(__file__) gives the directory of the current script (backend)
    # os.path.join then constructs prompts/summary_system_prompt.md relative to that
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "prompts", "summary_system_prompt.md")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERROR: Summary prompt file not found at {prompt_path}")
        # Fallback or raise an error, for now, let's raise
        raise FileNotFoundError(f"Summary prompt file not found: {prompt_path}")
    except Exception as e:
        print(f"ERROR: Could not read summary prompt file: {e}")
        raise

SUMMARY_PROMPT = load_summary_prompt()

# The metrics and parameters extraction prompts have been removed as they are no longer used


@dataclass
class WorkflowState:
    """State object for workflow execution"""
    blob_name: str
    markdown_content: str = ""
    summary_result: str = ""
    summary_json: dict = None
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
            
            # Download the blob content
            blob_data = blob_client.download_blob()
            content = blob_data.readall().decode('utf-8')
            
            print(f"Successfully downloaded {len(content)} characters of markdown content")
            return content
            
        except Exception as e:
            error_message = f"Error downloading markdown from blob storage: {str(e)}"
            print(error_message)
            raise Exception(error_message)
    
    async def upload_to_blob(self, blob_name: str, content: str, content_type: str = "text/markdown") -> str:
        """Upload content to Azure Blob Storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=blob_name
            )
            
            if content_type == "application/json":
                blob_client.upload_blob(
                    content.encode('utf-8'), 
                    overwrite=True,
                    content_type=content_type
                )
            else:
                blob_client.upload_blob(
                    content.encode('utf-8'), 
                    overwrite=True,
                    content_type=content_type
                )
            
            print(f"Successfully uploaded content to {blob_name}")
            return blob_name
            
        except Exception as e:
            error_message = f"Error uploading to blob storage: {str(e)}"
            print(error_message)
            raise Exception(error_message)
    
    async def call_openai(self, prompt: str, content: str, model: str, max_tokens: int = 8000) -> str:
        """Make a call to Azure OpenAI with specified model"""
        try:
            # Create messages array (common for all models)
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Please analyze this EWA document:\n\n{content}"}
            ]
            
            # Handle model-specific parameters
            if "o4-mini" in model:
                # o4-mini parameters
                params = {
                    "model": model,
                    "messages": messages,
                    "max_completion_tokens": 32000,
                    "reasoning_effort": "medium"
                }
                print(f"[MODEL INFO] Using model: {model} with max_completion_tokens=32000")
                print(f"[MODEL PARAMS] Using reasoning_effort=medium with {model} model")
            else:
                # Parameters for other models
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.0,
                    "top_p": 0.0,
                    "max_tokens": max_tokens,
                    "frequency_penalty": 0,
                    "presence_penalty": 0
                }
                print(f"[MODEL INFO] Using model: {model} with max_tokens={max_tokens}")
            
            response = self.client.chat.completions.create(**params)
            
            # Extract and log token usage information
            if hasattr(response, 'usage') and response.usage is not None:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens
                
                print(f"[TOKEN USAGE] Prompt: {prompt_tokens} | Completion: {completion_tokens} | Total: {total_tokens}")
                print(f"[TOKEN USAGE] Completion tokens used: {completion_tokens}/{32000 if 'o4-mini' in model else max_tokens} ({(completion_tokens / (32000 if 'o4-mini' in model else max_tokens) * 100):.1f}%)")
            else:
                print("[TOKEN USAGE] Token usage information not available in the response")
            
            return response.choices[0].message.content
            
        except Exception as e:
            error_message = f"Error calling Azure OpenAI: {str(e)}"
            print(error_message)
            raise Exception(error_message)
    
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
    
    async def generate_summary_step(self, state: WorkflowState) -> WorkflowState:
        """Step 2: Generate executive summary (no metrics/parameters)"""
        try:
            # model_to_use = AZURE_OPENAI_SUMMARY_MODEL # This variable is not strictly needed if passed directly
            print(f"[STEP 2] Generating summary for {state.blob_name} using model: {AZURE_OPENAI_SUMMARY_MODEL}")
            state.summary_result = await self.call_openai(
                SUMMARY_PROMPT, 
                state.markdown_content,
                model=AZURE_OPENAI_SUMMARY_MODEL, # Pass the model name directly
                max_tokens=16000 # As per the original apparent arguments
            )
            return state
        except Exception as e:
            state.error = str(e)
            return state
    
    # The extract_metrics_step and extract_parameters_step methods have been removed as they are no longer used

    async def run_agent_step(self, state: WorkflowState) -> WorkflowState:
        """Step 2: Generate structured JSON summary using EWAAgent"""
        try:
            print(f"[STEP 2] Running EWAAgent for {state.blob_name}")
            agent = EWAAgent(client=self.client, model=AZURE_OPENAI_SUMMARY_MODEL, summary_prompt=SUMMARY_PROMPT)
            summary_json = await agent.run(state.markdown_content)
            state.summary_json = summary_json
            state.summary_result = json_to_markdown(summary_json)
            return state
        except Exception as e:
            state.error = str(e)
            return state
    
    async def save_results_step(self, state: WorkflowState) -> WorkflowState:
        """Step 5: Save all results to blob storage"""
        try:
            print(f"[STEP 5] Saving results for {state.blob_name}")
            base_name = os.path.splitext(state.blob_name)[0]
            
            # Save summary markdown
            summary_blob_name = f"{base_name}_AI.md"
            await self.upload_to_blob(summary_blob_name, state.summary_result, "text/markdown")
            
            # Save structured JSON as well
            summary_json_blob_name = f"{base_name}_AI.json"
            if state.summary_json is not None:
                await self.upload_to_blob(summary_json_blob_name, json.dumps(state.summary_json, indent=2), "application/json")

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
                        existing_metadata = orig_blob_client.get_blob_properties().metadata or {}
                        # Azure metadata keys must be lowercase
                        existing_metadata["report_date"] = report_date
                        orig_blob_client.set_blob_metadata(existing_metadata)
                        print(f"Set report_date metadata ({report_date}) on {state.blob_name}")
                    except Exception as meta_e:
                        # Non-fatal; continue even if metadata update fails
                        print(f"Warning: could not set report_date metadata for {state.blob_name}: {meta_e}")
            
            return state
        except Exception as e:
            state.error = str(e)
            return state
    
    async def process_and_analyze_ewa(self, original_blob_name: str) -> dict:
        """
        Orchestrates the combined workflow of converting a document to markdown and then performing AI analysis.
        It calls the existing self.execute_workflow for the AI analysis part after successful conversion.
        """
        try:
            print(f"Starting combined processing and analysis for: {original_blob_name}")

            # Step 1: Initiate document to markdown conversion
            init_conversion_result = document_converter.convert_document_to_markdown(original_blob_name)

            if init_conversion_result.get("error") or init_conversion_result.get("status") == "failed":
                error_msg = f"Initial call to convert_document_to_markdown failed for {original_blob_name}: {init_conversion_result.get('message')}"
                print(error_msg)
                return {"success": False, "message": error_msg, "blob_name": original_blob_name, "details": init_conversion_result}

            print(f"Document conversion initiated for {original_blob_name}. Polling for completion...")

            # Step 2: Poll for markdown conversion completion
            max_retries = 60  # Poll for up to 5 minutes (60 retries * 5 seconds/retry)
            poll_interval_seconds = 5
            retries = 0
            conversion_completed = False
            final_conversion_status_result = None

            while retries < max_retries:
                await asyncio.sleep(poll_interval_seconds)
                status_result = document_converter.get_conversion_status(original_blob_name)
                final_conversion_status_result = status_result # Store last status
                current_status = status_result.get("status")
                
                print(f"Polling for {original_blob_name} (attempt {retries + 1}/{max_retries}): status = {current_status}, progress = {status_result.get('progress', 'N/A')}")

                if current_status == "completed":
                    print(f"Markdown conversion completed for {original_blob_name}.")
                    conversion_completed = True
                    break
                elif current_status == "error" or current_status == "failed":
                    error_msg = f"Markdown conversion failed for {original_blob_name}: {status_result.get('message')}"
                    print(error_msg)
                    return {"success": False, "message": error_msg, "blob_name": original_blob_name, "details": status_result}
                
                retries += 1
            
            if not conversion_completed:
                error_msg = f"Markdown conversion timed out for {original_blob_name} after {max_retries * poll_interval_seconds} seconds."
                print(error_msg)
                return {"success": False, "message": error_msg, "blob_name": original_blob_name, "details": final_conversion_status_result}

            # Step 3: Execute AI analysis workflow (which includes downloading the .md and other steps)
            print(f"Markdown conversion successful. Starting AI analysis workflow for {original_blob_name}.")
            # self.execute_workflow handles the AI part and returns a comprehensive dictionary
            analysis_result_dict = await self.execute_workflow(original_blob_name)

            if analysis_result_dict.get("success"):
                print(f"AI analysis workflow completed successfully for {original_blob_name}.")
                # Adapt the result from execute_workflow for the combined endpoint's response
                return {
                    "success": True,
                    "message": "Document processed and AI analysis completed successfully.",
                    "blob_name": original_blob_name,
                    "analysis_output_blob": analysis_result_dict.get("summary_file")
                    # Optionally, include other details from analysis_result_dict if needed by frontend
                }
            else:
                # AI analysis workflow failed after successful conversion
                error_msg = f"AI analysis workflow failed after successful conversion for {original_blob_name}: {analysis_result_dict.get('message')}"
                print(error_msg)
                return {
                    "success": False, 
                    "message": error_msg, 
                    "blob_name": original_blob_name,
                    "details": analysis_result_dict # Pass along the error details from execute_workflow
                }

        except Exception as e:
            # Log the full traceback in a real scenario using logging module
            error_msg = f"Unexpected error in process_and_analyze_ewa for {original_blob_name}: {str(e)}"
            print(f"{error_msg} - Full traceback: {traceback.format_exc()}") # More detailed logging
            return {"success": False, "message": error_msg, "blob_name": original_blob_name}

    async def execute_workflow(self, blob_name: str) -> Dict[str, Any]:
        """Execute the complete workflow"""
        try:
            print(f"Starting workflow for {blob_name}")
            
            # Initialize state
            state = WorkflowState(blob_name=blob_name)
            
            # Execute workflow steps sequentially
            state = await self.download_content_step(state)
            if state.error:
                raise Exception(state.error)
            
            # Run the agentic structured summary workflow
            summary_state = await self.run_agent_step(state)
            
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

async def execute_ewa_analysis(blob_name: str) -> Dict[str, Any]:
    """
    Convenience function to execute EWA analysis workflow
    
    Args:
        blob_name: Name of the file to analyze
    
    Returns:
        dict: Analysis result
    """
    return await ewa_orchestrator.execute_workflow(blob_name)
