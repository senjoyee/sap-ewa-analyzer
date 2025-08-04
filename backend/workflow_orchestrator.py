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
import re
import asyncio
import traceback # Added for exception logging
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from dotenv import load_dotenv
from agent.ewa_agent import EWAAgent
from utils.markdown_utils import json_to_markdown
from utils.kpi_extractor import KPIExtractor
from converters.document_converter import convert_document_to_markdown, get_conversion_status # Added for combined workflow
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
def load_summary_prompt():
    """Loads the summary system prompt from the prompts directory."""
    # Construct the absolute path to the prompts directory
    # __file__ is the path to the current script (workflow_orchestrator.py)
    # os.path.dirname(__file__) gives the directory of the current script (backend)
    # os.path.join then constructs prompts/summary_system_prompt.md relative to that
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "prompts", "ewa_summary_prompt.md")
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
    
    def _create_agent(self, model: str, summary_prompt: str) -> EWAAgent:
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
    
    async def download_pdf_from_blob(self, blob_name: str) -> bytes:
        """Download original PDF content from Azure Blob Storage for multimodal analysis"""
        try:
            print(f"Downloading PDF content from {blob_name}")
            
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=blob_name
            )
            
            # Download the blob content as bytes
            blob_data = blob_client.download_blob()
            content = blob_data.readall()
            
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
            
            blob_client.upload_blob(**upload_params)
            
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
            
            properties = blob_client.get_blob_properties()
            return properties.metadata or {}
            
        except Exception as e:
            print(f"Error retrieving metadata for {blob_name}: {str(e)}")
            return {}
    
    async def get_canonical_kpi_blob_name(self, customer_name: str, system_id: str) -> str:
        """Generate canonical KPI blob name for customer + system"""
        # Sanitize names for blob storage
        safe_customer = re.sub(r'[^a-zA-Z0-9]', '_', customer_name.lower())
        safe_system = re.sub(r'[^a-zA-Z0-9]', '_', system_id.lower())
        return f"canonical_kpis/{safe_customer}_{safe_system}_kpis.json"
    
    async def get_canonical_kpi_list(self, customer_name: str, system_id: str) -> dict:
        """Retrieve canonical KPI list for customer + system combination"""
        try:
            canonical_blob_name = await self.get_canonical_kpi_blob_name(customer_name, system_id)
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=canonical_blob_name
            )
            
            # Check if canonical KPI list exists
            if blob_client.exists():
                content = blob_client.download_blob().readall().decode('utf-8')
                return json.loads(content)
            else:
                print(f"No canonical KPI list found for {customer_name}/{system_id}")
                return None
                
        except Exception as e:
            print(f"Error retrieving canonical KPI list for {customer_name}/{system_id}: {str(e)}")
            return None
    
    async def save_canonical_kpi_list(self, customer_name: str, system_id: str, kpi_list: list) -> bool:
        """Save canonical KPI list for customer + system combination"""
        try:
            canonical_blob_name = await self.get_canonical_kpi_blob_name(customer_name, system_id)
            
            canonical_data = {
                "customer_name": customer_name,
                "system_id": system_id,
                "created_date": datetime.utcnow().isoformat(),
                "kpi_list": kpi_list
            }
            
            # Create metadata for canonical KPI file
            metadata = {
                "customer_name": customer_name,
                "system_id": system_id,
                "file_type": "canonical_kpis"
            }
            
            await self.upload_to_blob(
                canonical_blob_name, 
                json.dumps(canonical_data, indent=2), 
                "application/json", 
                metadata
            )
            
            print(f"Saved canonical KPI list for {customer_name}/{system_id} with {len(kpi_list)} KPIs")
            return True
            
        except Exception as e:
            print(f"Error saving canonical KPI list for {customer_name}/{system_id}: {str(e)}")
            return False
    
    async def get_previous_analysis_kpis(self, customer_name: str, system_id: str, current_report_date: str) -> list:
        """Get KPIs from the most recent previous analysis for trend calculation"""
        try:
            # List all blobs and find matching analyses
            container_client = self.blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
            matching_analyses = []
            
            # Use regular for loop since list_blobs() returns ItemPaged, not async iterable
            for blob in container_client.list_blobs(include=['metadata']):
                if blob.name.endswith('_AI.json') and blob.metadata:
                    blob_customer = blob.metadata.get('customer_name', '')
                    blob_system = blob.metadata.get('system_id', '')
                    blob_date = blob.metadata.get('report_date_str', '')
                    
                    if (blob_customer == customer_name and 
                        blob_system == system_id and 
                        blob_date != current_report_date):
                        matching_analyses.append((blob.name, blob_date, blob.metadata.get('report_date', '')))
            
            if not matching_analyses:
                print(f"No previous analyses found for {customer_name}/{system_id}")
                return []
            
            # Sort by report_date and find the most recent one BEFORE current date
            current_date_iso = datetime.strptime(current_report_date, "%d.%m.%Y").isoformat()
            
            # Filter for analyses before current report date, then get most recent
            previous_analyses = [
                (blob_name, blob_date_str, report_date_iso) 
                for blob_name, blob_date_str, report_date_iso in matching_analyses 
                if report_date_iso < current_date_iso
            ]
            
            if not previous_analyses:
                print(f"No previous analyses found before {current_report_date} for {customer_name}/{system_id}")
                return []
            
            # Sort by report_date (ISO format) and get the most recent before current
            previous_analyses.sort(key=lambda x: x[2], reverse=True)
            most_recent_blob = previous_analyses[0][0]
            
            print(f"Found chronologically previous analysis: {most_recent_blob} (before {current_report_date})")
            

            
            # Download and extract KPIs
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=most_recent_blob
            )
            
            content = blob_client.download_blob().readall().decode('utf-8')
            analysis_data = json.loads(content)
            
            return analysis_data.get('key_performance_indicators', [])
            
        except Exception as e:
            print(f"Error retrieving previous analysis KPIs for {customer_name}/{system_id}: {str(e)}")
            return []
    
    async def extract_kpis_deterministically(self, markdown_content: str, system_id: str, 
                                           customer_name: str, report_date_str: str) -> List[Dict[str, Any]]:
        """Extract KPIs using deterministic Python logic instead of AI"""
        try:
            print(f"[DETERMINISTIC KPI] Starting KPI extraction for {customer_name}/{system_id}")
            
            # Initialize KPI extractor
            kpi_extractor = KPIExtractor()
            
            # Extract current KPIs from markdown
            current_kpis = kpi_extractor.extract_kpis_from_markdown(markdown_content, system_id)
            
            if not current_kpis:
                print(f"[DETERMINISTIC KPI] No KPIs found in Performance Indicators table")
                return []
            
            print(f"[DETERMINISTIC KPI] Extracted {len(current_kpis)} KPIs from table")
            
            # Get previous KPIs for trend calculation
            previous_kpis = []
            if report_date_str:
                prev_analysis_kpis = await self.get_previous_analysis_kpis(customer_name, system_id, report_date_str)
                if prev_analysis_kpis:
                    # Convert previous AI-generated KPIs to simple format for comparison
                    previous_kpis = []
                    for prev_kpi in prev_analysis_kpis:
                        if isinstance(prev_kpi, dict):
                            previous_kpis.append({
                                'name': prev_kpi.get('name', ''),
                                'current_value': prev_kpi.get('current_value', '')
                            })
                    print(f"[DETERMINISTIC KPI] Found {len(previous_kpis)} previous KPIs for trend comparison")
            
            # Calculate trends
            kpis_with_trends = kpi_extractor.calculate_trend(current_kpis, previous_kpis)
            
            # Format for output
            formatted_kpis = kpi_extractor.format_kpis_for_output(kpis_with_trends)
            
            print(f"[DETERMINISTIC KPI] Successfully processed {len(formatted_kpis)} KPIs with trends")
            return formatted_kpis
            
        except Exception as e:
            print(f"[DETERMINISTIC KPI] Error in deterministic KPI extraction: {str(e)}")
            return []
    
    async def call_openai(self, prompt: str, content: str, model: str, max_tokens: int = 8000) -> str:
        """Make a call to Azure OpenAI with specified model"""
        try:
            # Create messages array
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Please analyze this EWA document:\n\n{content}"}
            ]
            
            # Standard parameters for GPT-4.1
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
                print(f"[TOKEN USAGE] Completion tokens used: {completion_tokens}/{max_tokens} ({(completion_tokens / max_tokens * 100):.1f}%)")
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
    

    async def run_analysis_step(self, state: WorkflowState) -> WorkflowState:
        """Step 2: Generate comprehensive EWA analysis with KPI trend and consistency management"""
        try:
            print(f"[STEP 2] Running EWA analysis for {state.blob_name}")
            
            # Get metadata from original blob for KPI management
            original_metadata = await self.get_blob_metadata(state.blob_name)
            customer_name = original_metadata.get('customer_name', '')
            system_id = original_metadata.get('system_id', '')
            report_date_str = original_metadata.get('report_date_str', '')
            
            print(f"Analysis - Customer: {customer_name}, System: {system_id}, Report Date: {report_date_str}")
            
            # Step 1: Extract KPIs using deterministic Python logic
            extracted_kpis = []
            if customer_name and system_id:
                extracted_kpis = await self.extract_kpis_deterministically(
                    state.markdown_content, system_id, customer_name, report_date_str
                )
            
            # Step 2: Run AI analysis for all other sections (excluding KPIs)
            # Update prompt to exclude KPI extraction since we handle it separately
            ai_prompt = SUMMARY_PROMPT.replace(
                "### KPIs\n- Create a list of key performance indicator objects with structured format.\n- Each KPI object must include: `name`, `current_value`, and `trend` information.\n- **Canonical KPI Enforcement**: If canonical KPIs are provided below, you MUST reuse exactly those KPI names. Do not create new KPI names.\n- **Trend Calculation Rules**:\n  - **FIRST ANALYSIS**: If no previous KPI data is provided below, set ALL trend directions to \"none\" with description \"First analysis - no previous data for comparison\"\n  - **SUBSEQUENT ANALYSIS**: If previous KPI data is provided below, compare current values with previous values:\n    - Extract numeric values from both current and previous (ignore units like ms, %, GB)\n    - `direction`: \"up\" if current > previous (+5% threshold), \"down\" if current < previous (-5% threshold), \"flat\" if within ±5%\n    - `percent_change`: calculate exact percentage change: ((current - previous) / previous) × 100\n    - `description`: brief explanation with actual values (e.g., \"Increased from 528ms to 629ms (+19%)\")\n  - **New KPIs**: For KPIs not found in previous data, use trend direction \"none\" and note \"New KPI - no previous data\"",
                "### KPIs\n- KPIs will be provided separately using deterministic extraction from Performance Indicators table. Do NOT include KPIs in your analysis output."
            )
            
            # Run AI analysis for all sections except KPIs
            agent = self._create_agent(AZURE_OPENAI_SUMMARY_MODEL, ai_prompt)
            
            # Determine input type based on model
            if is_gemini_model(AZURE_OPENAI_SUMMARY_MODEL):
                # For Gemini models, use original PDF if available
                try:
                    pdf_data = await self.download_pdf_from_blob(state.blob_name)
                    print(f"[Gemini Workflow] Using original PDF ({len(pdf_data)} bytes) for analysis")
                    ai_result = await agent.run(state.markdown_content, pdf_data=pdf_data)
                except Exception as e:
                    print(f"[Gemini Workflow] Failed to load PDF, falling back to markdown: {str(e)}")
                    ai_result = await agent.run(state.markdown_content)
            else:
                # For OpenAI models, continue using markdown
                print(f"[OpenAI Workflow] Using markdown content for analysis")
                ai_result = await agent.run(state.markdown_content)
            
            # Step 3: Combine AI results with deterministic KPIs
            if ai_result and extracted_kpis:
                # Replace AI-generated KPIs with deterministic ones
                final_json = ai_result.copy()
                final_json['key_performance_indicators'] = extracted_kpis
                
                print(f"[HYBRID ANALYSIS] Combined AI analysis with {len(extracted_kpis)} deterministic KPIs")
            elif ai_result:
                # No KPIs extracted, use AI result as-is
                final_json = ai_result
                print(f"[HYBRID ANALYSIS] Using AI analysis without KPI section")
            else:
                # Fallback - create minimal structure with KPIs only
                final_json = {
                    'key_performance_indicators': extracted_kpis,
                    'executive_summary': 'Analysis completed with KPI extraction only',
                    'system_metadata': {
                        'system_id': system_id,
                        'customer_name': customer_name,
                        'report_date': report_date_str
                    }
                }
                print(f"[HYBRID ANALYSIS] Created minimal analysis with {len(extracted_kpis)} KPIs")
            
            # Handle canonical KPI list management using deterministic KPIs
            if customer_name and system_id and extracted_kpis:
                # Check if canonical list exists
                canonical_data = await self.get_canonical_kpi_list(customer_name, system_id)
                
                if not canonical_data:
                    # Extract KPI names for canonical list
                    kpi_names = [kpi.get('name', '') for kpi in extracted_kpis if kpi.get('name')]
                    print(f"Creating canonical KPI list for {customer_name}/{system_id} with {len(kpi_names)} KPIs")
                    await self.save_canonical_kpi_list(customer_name, system_id, kpi_names)
                else:
                    # Validate that current KPIs match canonical list
                    # Handle case where canonical list contains dicts instead of strings
                    canonical_kpi_list = canonical_data.get('kpi_list', [])
                    canonical_names = set()
                    
                    for item in canonical_kpi_list:
                        if isinstance(item, str):
                            canonical_names.add(item)
                        elif isinstance(item, dict) and 'name' in item:
                            canonical_names.add(item['name'])
                        elif isinstance(item, dict):
                            # Skip malformed entries
                            print(f"Warning: Skipping malformed canonical KPI entry: {item}")
                    
                    current_names = set(kpi.get('name', '') for kpi in extracted_kpis if kpi.get('name'))
                    
                    new_kpis = current_names - canonical_names
                    if new_kpis:
                        print(f"Detected {len(new_kpis)} new KPIs not in canonical list: {list(new_kpis)}")
                        print(f"TODO: Implement approval workflow for new KPIs")
                    else:
                        print(f"All KPIs match canonical list for {customer_name}/{system_id}")
            
            # Add Quick Wins section: filter recommendations with both analysis and implementation effort = 'low'
            if 'recommendations' in final_json:
                quick_wins = []
                for rec in final_json['recommendations']:
                    # Check if Estimated Effort exists and both analysis and implementation are 'low'
                    if ('Estimated Effort' in rec and 
                        isinstance(rec['Estimated Effort'], dict) and
                        rec['Estimated Effort'].get('analysis', '').lower() == 'low' and
                        rec['Estimated Effort'].get('implementation', '').lower() == 'low'):
                        quick_wins.append(rec)
                
                # Add Quick Wins section to final JSON
                final_json['quick_wins'] = quick_wins
                print(f"[QUICK WINS] Extracted {len(quick_wins)} quick wins from {len(final_json['recommendations'])} recommendations")
            
            state.summary_json = final_json
            state.summary_result = json_to_markdown(final_json)
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
    
    async def process_files_sequentially(self, customer_name: str, system_id: str) -> List[Dict[str, Any]]:
        """
        Find and process multiple files with the same customer and SID in chronological order.
        This ensures proper trend analysis by processing files from oldest to newest.
        
        Args:
            customer_name: Customer name to match
            system_id: System ID to match
            
        Returns:
            List of processing results for each file
        """
        try:
            print(f"[SEQUENTIAL PROCESSING] Finding files for customer '{customer_name}' and SID '{system_id}'")
            
            if not self.blob_service_client:
                raise Exception("Blob service client not initialized")
            
            container_client = self.blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
            blob_list = list(container_client.list_blobs())
            
            # Find matching files
            matching_files = []
            for blob in blob_list:
                # Skip processed files (.md, .json)
                if blob.name.lower().endswith(('.md', '.json')):
                    continue
                
                try:
                    blob_client = container_client.get_blob_client(blob.name)
                    properties = blob_client.get_blob_properties()
                    metadata = properties.metadata or {}
                    
                    # Check if this file matches our criteria
                    if (metadata.get('customer_name') == customer_name and 
                        metadata.get('system_id') == system_id):
                        
                        matching_files.append({
                            'blob_name': blob.name,
                            'report_date': metadata.get('report_date'),
                            'report_date_str': metadata.get('report_date_str'),
                            'last_modified': blob.last_modified
                        })
                        
                except Exception as e:
                    print(f"[SEQUENTIAL PROCESSING] Error reading metadata for {blob.name}: {e}")
                    continue
            
            if not matching_files:
                print(f"[SEQUENTIAL PROCESSING] No files found for customer '{customer_name}' and SID '{system_id}'")
                return []
            
            # Sort by report date (chronological order: oldest first)
            def get_sort_key(file_info):
                try:
                    if file_info.get('report_date'):
                        # Parse ISO string back to datetime for proper comparison
                        return datetime.fromisoformat(file_info['report_date'])
                    else:
                        # Fall back to last_modified if no report_date
                        return file_info['last_modified']
                except (ValueError, TypeError) as e:
                    print(f"[SEQUENTIAL PROCESSING] Warning: Error parsing date for {file_info['blob_name']}: {e}")
                    return file_info['last_modified']
            
            matching_files.sort(key=get_sort_key)
            
            print(f"[SEQUENTIAL PROCESSING] Found {len(matching_files)} files to process in order:")
            for i, file_info in enumerate(matching_files):
                print(f"  {i+1}. {file_info['blob_name']} (Date: {file_info['report_date_str']})")
            
            # Process files sequentially
            results = []
            for i, file_info in enumerate(matching_files):
                blob_name = file_info['blob_name']
                print(f"[SEQUENTIAL PROCESSING] Processing file {i+1}/{len(matching_files)}: {blob_name}")
                
                try:
                    result = await self.process_and_analyze_ewa(blob_name)
                    results.append({
                        'blob_name': blob_name,
                        'result': result,
                        'order': i + 1
                    })
                    
                    if result.get('success'):
                        print(f"[SEQUENTIAL PROCESSING] Successfully processed {blob_name}")
                    else:
                        print(f"[SEQUENTIAL PROCESSING] Failed to process {blob_name}: {result.get('message')}")
                        
                except Exception as e:
                    error_msg = f"Error processing {blob_name}: {str(e)}"
                    print(f"[SEQUENTIAL PROCESSING] {error_msg}")
                    results.append({
                        'blob_name': blob_name,
                        'result': {'success': False, 'message': error_msg},
                        'order': i + 1
                    })
            
            print(f"[SEQUENTIAL PROCESSING] Completed processing {len(results)} files")
            return results
            
        except Exception as e:
            error_msg = f"Error in sequential processing: {str(e)}"
            print(f"[SEQUENTIAL PROCESSING] {error_msg}")
            return [{'error': error_msg}]
    
    async def process_and_analyze_ewa(self, original_blob_name: str) -> dict:
        """
        Orchestrates the combined workflow of converting a document to markdown and then performing AI analysis.
        It calls the existing self.execute_workflow for the AI analysis part after successful conversion.
        """
        try:
            print(f"Starting combined processing and analysis for: {original_blob_name}")

            # Step 1: Initiate document to markdown conversion
            init_conversion_result = convert_document_to_markdown(original_blob_name)

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
                status_result = get_conversion_status(original_blob_name)
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
