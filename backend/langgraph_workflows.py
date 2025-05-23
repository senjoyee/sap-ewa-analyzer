"""
LangGraph-based workflow orchestration for EWA analysis.
This module contains three separate workflows:
1. Summary workflow - Creates executive summary
2. Metrics extraction workflow - Extracts key metrics
3. Parameters extraction workflow - Extracts parameter recommendations
"""

import os
import json
import re
import asyncio
from typing import Dict, Any, List
from dataclasses import dataclass
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

# System prompts for each workflow
SUMMARY_PROMPT = """You are an expert SAP Basis Architect tasked with analyzing an SAP Early Watch Alert report. Your goal is to study the report thoroughly and extract actionable insights, categorizing them based on their importance. Here's how you should proceed:

First, carefully read and analyze the SAP Early Watch Alert report:

Now, follow these steps to provide your analysis:

1. Thoroughly examine the report, paying close attention to all sections and details.

2. Identify all actionable insights from the report. These should be specific findings that require attention or action from the SAP team.

3. Categorize each finding based on its importance using the following scale:
   - Very High
   - High
   - Medium
   - Low

4. For each finding, provide:
   a) A clear description of the issue
   b) The potential impact if not addressed
   c) Recommended actions to resolve or mitigate the issue
   d) The importance category (Very High, High, Medium, or Low)

5. Organize your findings in order of importance, starting with Very High and ending with Low.

6. Present your analysis in the following enhanced Markdown format:

# 📊 SAP Early Watch Alert Analysis Summary

> *Analysis Date: [Current Date]*  
> *System: [System Identifier from Report]*  
> *Report Period: [Period Covered]*

## 📋 Executive Summary

[Provide a brief, high-level summary of the most critical findings and recommendations]

---

## 🔴 Critical Priority Findings

### 🚨 Finding: [Brief Title of Issue]
**Description:** [Provide a clear description of the issue]  
**Impact:** [Explain the potential impact if not addressed]  
**Recommendation:** [Provide recommended actions to resolve or mitigate the issue]

---

## 🟠 High Priority Findings

### ⚠️ Finding: [Brief Title of Issue]
**Description:** [Provide a clear description of the issue]  
**Impact:** [Explain the potential impact if not addressed]  
**Recommendation:** [Provide recommended actions to resolve or mitigate the issue]

---

## 🟡 Medium Priority Findings

### ⚙️ Finding: [Brief Title of Issue]
**Description:** [Provide a clear description of the issue]  
**Impact:** [Explain the potential impact if not addressed]  
**Recommendation:** [Provide recommended actions to resolve or mitigate the issue]

---

## 🟢 Low Priority Findings

### 📝 Finding: [Brief Title of Issue]
**Description:** [Provide a clear description of the issue]  
**Impact:** [Explain the potential impact if not addressed]  
**Recommendation:** [Provide recommended actions to resolve or mitigate the issue]

Do NOT include any sections about metrics or parameters. End the report after the findings sections.
"""

METRICS_EXTRACTION_PROMPT = """You are an expert SAP Basis Architect tasked with extracting ALL key metrics from an SAP Early Watch Alert report.

Your goal is to identify and extract every important metric, KPI, and performance indicator mentioned in the report.

You MUST return ONLY valid, parseable JSON with no additional text, comments, or markdown formatting. The response should be a single JSON object that follows this exact structure:

{
  "metrics": [
    {
      "name": "METRIC_NAME",
      "current": "CURRENT_VALUE",
      "target": "TARGET_VALUE", 
      "status": "STATUS",
      "category": "CATEGORY",
      "description": "Brief description of what this metric measures"
    }
  ]
}

CRITICAL JSON FORMATTING REQUIREMENTS:
- All strings MUST be enclosed in double quotes
- Do not use single quotes anywhere in the JSON
- Ensure all quotation marks, braces, and brackets are properly closed and balanced
- Do not include any special characters or escape sequences that would make the JSON invalid
- No trailing commas
- No comments within the JSON

**Status values must be EXACTLY one of: "success", "warning", or "critical"**
**Category values should group related metrics (e.g., "Performance", "Availability", "Database", "Memory", etc.)**

INSTRUCTIONS:
- Extract ALL metrics mentioned in the report
- Include the current value and target/threshold value for each metric
- Classify each metric with the appropriate status based on how it compares to targets/thresholds
- Group metrics into logical categories
- Provide a brief description of what each metric measures
- Pay special attention to performance metrics, availability metrics, and resource utilization metrics

IMPORTANT: Your response MUST be a syntactically valid JSON object only. No preamble, no explanations, no additional text or markdown. Just the JSON.
- Do NOT use ellipsis ('...') or placeholders; provide the complete JSON without omissions.

**Wrap your JSON output in a fenced code block with ```json and ```**
"""

PARAMETERS_EXTRACTION_PROMPT = """You are an expert SAP Basis Architect tasked with extracting ALL parameter recommendations from an SAP Early Watch Alert report.

Your goal is to identify and extract every important parameter setting, configuration value, and tuning recommendation mentioned in the report.

You MUST return ONLY valid, parseable JSON with no additional text, comments, or markdown formatting. The response should be a single JSON object that follows this exact structure:

{
  "parameters": [
    {
      "name": "PARAMETER_NAME",
      "current": "CURRENT_VALUE",
      "recommended": "RECOMMENDED_VALUE",
      "impact": "IMPACT_LEVEL",
      "category": "CATEGORY",
      "system_type": "SYSTEM_TYPE",
      "description": "Description of what this parameter controls and why it should be changed"
    }
  ]
}

CRITICAL JSON FORMATTING REQUIREMENTS:
- All strings MUST be enclosed in double quotes
- Do not use single quotes anywhere in the JSON
- Ensure all quotation marks, braces, and brackets are properly closed and balanced
- Do not include any special characters or escape sequences that would make the JSON invalid
- No trailing commas
- No comments within the JSON

**Impact values must be EXACTLY one of: "high", "medium", or "low"**
**Category values should group related parameters (e.g., "Performance", "Memory Management", "Security", "Database Tuning", etc.)**
**System_type values must be EXACTLY one of: "HANA", "Application Server", "Both", or "System"**

CRITICAL REQUIREMENTS:
- Clearly distinguish between HANA database parameters and SAP Application Server parameters using the system_type field
- For HANA parameters: use system_type = "HANA"
- For SAP Application Server parameters: use system_type = "Application Server"  
- For parameters that affect both: use system_type = "Both"
- For general system parameters: use system_type = "System"

INSTRUCTIONS:
- Extract ALL parameter recommendations mentioned in the report
- Include current values and recommended values where available
- Assess impact level based on the criticality described in the report
- Provide clear descriptions of what each parameter does
- Look for memory parameters, performance tuning parameters, security parameters, etc.
- Pay special attention to database-specific vs application server-specific parameters

IMPORTANT: Your response MUST be a syntactically valid JSON object only. No preamble, no explanations, no additional text or markdown. Just the JSON.
- Do NOT use ellipsis ('...') or placeholders; provide the complete JSON without omissions.
- Wrap your JSON output in a fenced code block with ```json and ```**
"""


def repair_json(json_string: str) -> str:
    """
    Attempt to repair common JSON syntax errors in the string.
    
    Args:
        json_string: The JSON string to repair
        
    Returns:
        A repaired JSON string that might be parseable
    """
    # Log the original string for debugging
    print(f"Attempting to repair JSON string of length {len(json_string)}")
    
    # Remove placeholder ellipsis to avoid incomplete JSON
    json_string = re.sub(r'\.{3,}', '', json_string)
    
    # Remove any markdown code block markers
    json_string = re.sub(r'```(?:json)?|```', '', json_string)
    
    # Remove any leading/trailing whitespace and non-JSON content
    json_string = json_string.strip()
    
    # If the string doesn't start with '{', try to find the first occurrence
    if not json_string.startswith('{'): 
        start_idx = json_string.find('{')
        if start_idx >= 0:
            json_string = json_string[start_idx:]
    
    # If the string doesn't end with '}', try to find the last occurrence
    if not json_string.endswith('}'):
        end_idx = json_string.rfind('}')
        if end_idx >= 0:
            json_string = json_string[:end_idx+1]
    
    # Fix trailing commas in objects and arrays (common JSON syntax error)
    json_string = re.sub(r',\s*([\]}])', r'\1', json_string)
    
    # Fix missing quotes around property names
    json_string = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_string)
    
    # Fix single quotes used instead of double quotes for property names
    json_string = re.sub(r'([{,])\s*\'([^\']+)\'\s*:', r'\1"\2":', json_string)
    
    # Fix single quotes used instead of double quotes for string values
    # First, handle the case where the string value is followed by a comma
    json_string = re.sub(r':\s*\'([^\']*)\'\s*([,}])', r':"\1"\2', json_string)
    
    # Handle the case where the string value is the last one in an object/array
    json_string = re.sub(r':\s*\'([^\']*)\'\s*$', r':"\1"', json_string)
    
    # Log the repaired string
    print(f"Repaired JSON string: {json_string[:100]}..." if len(json_string) > 100 else f"Repaired JSON string: {json_string}")
    
    # Unescape any escaped quotes for proper JSON
    json_string = json_string.replace('\\"', '"')
    
    return json_string


@dataclass
class WorkflowState:
    """State object for workflow execution"""
    blob_name: str
    markdown_content: str = ""
    summary_result: str = ""
    metrics_result: Dict[str, Any] = None
    parameters_result: Dict[str, Any] = None
    error: str = ""

class EWALangGraphOrchestrator:
    """LangGraph orchestrator for EWA analysis workflows"""
    
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
    
    async def call_openai(self, prompt: str, content: str, max_tokens: int = 8000) -> str:
        """Make a call to Azure OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Please analyze this EWA document:\n\n{content}"}
                ],
                temperature=0.1,
                max_tokens=max_tokens,
                frequency_penalty=0,
                presence_penalty=0
            )
            
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
            print(f"[STEP 2] Generating summary for {state.blob_name}")
            state.summary_result = await self.call_openai(
                SUMMARY_PROMPT, 
                state.markdown_content, 
                max_tokens=6000
            )
            return state
        except Exception as e:
            state.error = str(e)
            return state
    
    async def extract_metrics_step(self, state: WorkflowState) -> WorkflowState:
        """Step 3: Extract metrics as JSON"""
        try:
            print(f"[STEP 3] Extracting metrics for {state.blob_name}")
            metrics_response = await self.call_openai(
                METRICS_EXTRACTION_PROMPT, 
                state.markdown_content, 
                max_tokens=8000
            )
            
            # Parse JSON response with improved error handling
            try:
                # First try direct parsing
                state.metrics_result = json.loads(metrics_response.strip())
                print("Successfully parsed metrics JSON directly")
            except json.JSONDecodeError as e:
                print(f"Direct JSON parsing failed: {e}")
                print(f"Raw response (first 500 chars): {metrics_response[:500]}...")
                
                # Try to repair the JSON string
                try:
                    repaired_json = repair_json(metrics_response)
                    state.metrics_result = json.loads(repaired_json)
                    print("Successfully parsed metrics JSON after repair")
                except json.JSONDecodeError as e2:
                    print(f"JSON repair failed: {e2}")
                    
                    # If repair failed, try to extract JSON from response if it's wrapped in text
                    # Pattern 1: JSON wrapped in code blocks
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', metrics_response, re.DOTALL | re.IGNORECASE)
                    if json_match:
                        try:
                            extracted_json = repair_json(json_match.group(1))  # Apply repair to extracted JSON too
                            state.metrics_result = json.loads(extracted_json)
                            print("Successfully extracted and repaired JSON from code block")
                        except json.JSONDecodeError as e3:
                            print(f"Code block JSON parsing failed: {e3}")
                            json_match = None
                    
                    if not json_match:
                        # Pattern 2: Look for raw JSON object
                        json_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', metrics_response, re.DOTALL)
                        if json_match:
                            try:
                                extracted_json = repair_json(json_match.group(1))
                                state.metrics_result = json.loads(extracted_json)
                                print("Successfully extracted and repaired raw JSON object")
                            except json.JSONDecodeError as e4:
                                print(f"Raw JSON parsing failed: {e4}")
                                json_match = None
                    
                    if not json_match:
                        # If all parsing fails, create a fallback structure
                        print("All JSON parsing and repair attempts failed, creating fallback structure")
                        
                        # Create a basic structure but preserve the raw content for debugging
                        state.metrics_result = {
                            "error": "JSON parsing failed",
                            "raw_response": metrics_response[:1000] if len(metrics_response) > 1000 else metrics_response,
                            "metrics": []
                        }
            
            return state
        except Exception as e:
            print(f"Error in extract_metrics_step: {e}")
            state.error = str(e)
            return state
    
    async def extract_parameters_step(self, state: WorkflowState) -> WorkflowState:
        """Step 4: Extract parameters as JSON"""
        try:
            print(f"[STEP 4] Extracting parameters for {state.blob_name}")
            parameters_response = await self.call_openai(
                PARAMETERS_EXTRACTION_PROMPT, 
                state.markdown_content, 
                max_tokens=8000
            )
            
            # Parse JSON response with improved error handling
            try:
                # First try direct parsing
                state.parameters_result = json.loads(parameters_response.strip())
                print("Successfully parsed parameters JSON directly")
            except json.JSONDecodeError as e:
                print(f"Direct JSON parsing failed: {e}")
                print(f"Raw response (first 500 chars): {parameters_response[:500]}...")
                
                # Try to repair the JSON string
                try:
                    repaired_json = repair_json(parameters_response)
                    state.parameters_result = json.loads(repaired_json)
                    print("Successfully parsed parameters JSON after repair")
                except json.JSONDecodeError as e2:
                    print(f"JSON repair failed: {e2}")
                    
                    # If repair failed, try to extract JSON from response if it's wrapped in text
                    # Pattern 1: JSON wrapped in code blocks
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', parameters_response, re.DOTALL | re.IGNORECASE)
                    if json_match:
                        try:
                            extracted_json = repair_json(json_match.group(1))  # Apply repair to extracted JSON too
                            state.parameters_result = json.loads(extracted_json)
                            print("Successfully extracted and repaired JSON from code block")
                        except json.JSONDecodeError as e3:
                            print(f"Code block JSON parsing failed: {e3}")
                            json_match = None
                    
                    if not json_match:
                        # Pattern 2: Look for raw JSON object
                        json_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', parameters_response, re.DOTALL)
                        if json_match:
                            try:
                                extracted_json = repair_json(json_match.group(1))
                                state.parameters_result = json.loads(extracted_json)
                                print("Successfully extracted and repaired raw JSON object")
                            except json.JSONDecodeError as e4:
                                print(f"Raw JSON parsing failed: {e4}")
                                json_match = None
                    
                    if not json_match:
                        # If all parsing fails, create a fallback structure
                        print("All JSON parsing and repair attempts failed, creating fallback structure")
                        
                        # Create a basic structure but preserve the raw content for debugging
                        state.parameters_result = {
                            "error": "JSON parsing failed",
                            "raw_response": parameters_response[:1000] if len(parameters_response) > 1000 else parameters_response,
                            "parameters": []
                        }
            
            return state
        except Exception as e:
            print(f"Error in extract_parameters_step: {e}")
            state.error = str(e)
            return state
    
    async def save_results_step(self, state: WorkflowState) -> WorkflowState:
        """Step 5: Save all results to blob storage"""
        try:
            print(f"[STEP 5] Saving results for {state.blob_name}")
            base_name = os.path.splitext(state.blob_name)[0]
            
            # Save summary as markdown
            summary_blob_name = f"{base_name}_AI.md"
            await self.upload_to_blob(summary_blob_name, state.summary_result, "text/markdown")
            
            # Save metrics as JSON
            if state.metrics_result:
                metrics_blob_name = f"{base_name}_metrics.json"
                await self.upload_to_blob(
                    metrics_blob_name, 
                    json.dumps(state.metrics_result, indent=2), 
                    "application/json"
                )
            
            # Save parameters as JSON
            if state.parameters_result:
                parameters_blob_name = f"{base_name}_parameters.json"
                await self.upload_to_blob(
                    parameters_blob_name, 
                    json.dumps(state.parameters_result, indent=2), 
                    "application/json"
                )
            
            return state
        except Exception as e:
            state.error = str(e)
            return state
    
    async def execute_workflow(self, blob_name: str) -> Dict[str, Any]:
        """Execute the complete LangGraph workflow"""
        try:
            print(f"Starting LangGraph workflow for {blob_name}")
            
            # Initialize state
            state = WorkflowState(blob_name=blob_name)
            
            # Execute workflow steps sequentially
            state = await self.download_content_step(state)
            if state.error:
                raise Exception(state.error)
            
            # Execute all three workflows in parallel for efficiency
            summary_task = self.generate_summary_step(state)
            metrics_task = self.extract_metrics_step(state)
            parameters_task = self.extract_parameters_step(state)
            
            # Wait for all to complete
            summary_state, metrics_state, parameters_state = await asyncio.gather(
                summary_task, metrics_task, parameters_task
            )
            
            # Check for errors and collect them
            errors = []
            if summary_state.error:
                errors.append(f"Summary generation failed: {summary_state.error}")
            if metrics_state.error:
                errors.append(f"Metrics extraction failed: {metrics_state.error}")
            if parameters_state.error:
                errors.append(f"Parameters extraction failed: {parameters_state.error}")
            
            # If all three failed, raise an exception
            if len(errors) == 3:
                raise Exception(f"All workflow steps failed: {'; '.join(errors)}")
            
            # If some failed, log warnings but continue
            if errors:
                print(f"Some workflow steps failed: {'; '.join(errors)}")
                # Continue with partial results
            
            # Combine results
            state.summary_result = summary_state.summary_result
            state.metrics_result = metrics_state.metrics_result  
            state.parameters_result = parameters_state.parameters_result
            
            # Save all results
            state = await self.save_results_step(state)
            if state.error:
                raise Exception(state.error)
            
            # Return success response
            base_name = os.path.splitext(blob_name)[0]
            return {
                "success": True,
                "message": "LangGraph workflow completed successfully",
                "original_file": blob_name,
                "summary_file": f"{base_name}_AI.md",
                "metrics_file": f"{base_name}_metrics.json" if state.metrics_result else None,
                "parameters_file": f"{base_name}_parameters.json" if state.parameters_result else None,
                "summary_data": state.summary_result,
                "metrics_data": state.metrics_result,
                "parameters_data": state.parameters_result,
                "summary_preview": state.summary_result[:500] + "..." if len(state.summary_result) > 500 else state.summary_result
            }
            
        except Exception as e:
            error_message = f"LangGraph workflow error: {str(e)}"
            print(error_message)
            return {
                "success": False,
                "error": True,
                "message": error_message,
                "original_file": blob_name
            }

# Global orchestrator instance
ewa_orchestrator = EWALangGraphOrchestrator()

async def execute_ewa_analysis(blob_name: str) -> Dict[str, Any]:
    """
    Convenience function to execute EWA analysis workflow
    
    Args:
        blob_name: Name of the file to analyze
    
    Returns:
        dict: Analysis result
    """
    return await ewa_orchestrator.execute_workflow(blob_name)
