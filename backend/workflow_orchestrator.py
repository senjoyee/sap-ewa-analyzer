"""
SAP EWA Analysis Workflow Orchestration Module

This module implements a custom orchestration system for analyzing SAP Early Watch Alert (EWA) reports
using Azure OpenAI services. It manages the complete workflow through parallel execution of three
specialized analysis tasks:

1. Summary Workflow - Generates an executive summary with findings and recommendations
2. Metrics Extraction Workflow - Extracts key metrics as structured JSON data
3. Parameters Extraction Workflow - Extracts parameter recommendations as structured JSON

Key Functionality:
- Orchestrating complex multi-step AI analysis workflows
- Parallel execution of multiple analysis tasks for efficiency
- Specialized prompting for different types of information extraction
- JSON response validation and repair
- Integration with Azure Blob Storage for document persistence
- Error handling and status reporting

The orchestrator ensures each workflow component operates independently while maintaining
a cohesive end-to-end analysis process for SAP EWA reports.
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

# Model deployment names
AZURE_OPENAI_SUMMARY_MODEL = os.getenv("AZURE_OPENAI_SUMMARY_MODEL", "gpt-4.1-mini")
AZURE_OPENAI_METRICS_MODEL = os.getenv("AZURE_OPENAI_METRICS_MODEL", "gpt-4.1-mini")
AZURE_OPENAI_PARAMETERS_MODEL = os.getenv("AZURE_OPENAI_PARAMETERS_MODEL", "gpt-4.1-mini")

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

# System prompts for each workflow
SUMMARY_PROMPT = """You are an expert SAP Basis Architect tasked with analyzing an SAP Early Watch Alert report. Your goal is to study the report thoroughly and extract actionable insights, categorizing them based on their importance. Here's how you should proceed:

First, carefully read and analyze the ENTIRE SAP Early Watch Alert report, making sure to examine EACH AND EVERY CHAPTER without exception:

STRICT REQUIREMENT: You MUST analyze every chapter of the report

Follow these steps to provide your comprehensive analysis:

1. Thoroughly examine EACH chapter of the report, ensuring you don't miss any sections or details. If a chapter contains no issues, explicitly state that the chapter was reviewed and no issues were found.

2. Identify ALL actionable insights from EVERY chapter of the report. These should be specific findings that require attention or action from the SAP team.

3. Categorize each finding based on its importance using the following scale:
   - Very High: Critical issues requiring immediate attention; significant risk to business operations
   - High: Important issues that should be addressed soon; potential impact on performance or stability
   - Medium: Issues that should be planned for resolution; moderate impact on system efficiency
   - Low: Minor optimizations or recommendations; minimal current impact

4. For each finding, provide:
   a) A clear description of the issue.
   b) The potential impact if not addressed.
   c) Recommended actions to resolve or mitigate the issue. Consider using bullet points, where applicable.
   d) The importance category (Very High, High, Medium, or Low).

5. Organize your findings in order of importance, starting with Very High and ending with Low.

6. Present your analysis in the following enhanced Markdown format:

# 📊 SAP Early Watch Alert Analysis Summary

> *Analysis Date: [Current Date]*  
> *System: [System Identifier from Report]*  
> *Report Period: [Period Covered]*

## 📋 Executive Summary

[Provide a brief, high-level summary of the most critical findings and recommendations. Include a count of findings by priority level and mention which chapters contained the most critical issues.]

---

## 🔴 Critical Priority Findings

### 🚨 Finding: [Brief Title of Issue]
**Description:** [Provide a clear description of the issue]  
**Impact:**  
- [First impact point]  
- [Second impact point]  

**Recommendation:**  
- [First recommendation point]  
- [Second recommendation point]

---

## 🟠 High Priority Findings

### ⚠️ Finding: [Brief Title of Issue]
**Description:** [Provide a clear description of the issue]  
**Impact:**  
- [First impact point]  
- [Second impact point]  

**Recommendation:**  
- [First recommendation point]  
- [Second recommendation point]

---

## 🟡 Medium Priority Findings

### ⚙️ Finding: [Brief Title of Issue]
**Description:** [Provide a clear description of the issue]  
**Impact:**  
- [First impact point]  
- [Second impact point]  

**Recommendation:**  
- [First recommendation point]  
- [Second recommendation point]

---

## 🟢 Low Priority Findings

### 📝 Finding: [Brief Title of Issue]
**Description:** [Provide a clear description of the issue]  
**Impact:**  
- [First impact point]  
- [Second impact point]  

**Recommendation:**  
- [First recommendation point]  
- [Second recommendation point]

IMPORTANT FORMATTING AND CONTENT INSTRUCTIONS:
- Always format both Impact and Recommendation sections with bullet points
- Ensure consistent indentation for all bullet points
- Leave a blank line after the 'Impact:' and 'Recommendation:' headers before starting bullet points
- Each bullet point should start with a hyphen followed by a space ('- ')
- Maintain consistent spacing throughout the document
- Include the source chapter/section for each finding to provide context (e.g., "Source: Database Performance Chapter")
- If no issues are found in a particular chapter, still acknowledge that chapter was reviewed with a statement like: "No issues were identified in the [Chapter Name] section"
- For each finding, include specific values, metrics, or configuration settings mentioned in the report when available

EXTREMELY IMPORTANT: You MUST analyze EVERY chapter and section of the report. Missing any section is unacceptable. If a chapter contains no issues, explicitly state this.

Do NOT include any sections about metrics or parameters as separate JSON data. End the report after the findings sections.
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
- No HTML tags (<br>, <p>, etc.) in any values, especially metric names

**Status values must be EXACTLY one of: "success", "warning", or "critical"**
**Category values should group related metrics (e.g., "Performance", "Availability", "Database", "Memory", etc.)**

INSTRUCTIONS:
- Extract ALL metrics mentioned in the report
- Include the current value and target/threshold value for each metric
- Classify each metric with the appropriate status based on how it compares to targets/thresholds
- Group metrics into logical categories
- Provide a brief description of what each metric measures
- Pay special attention to performance metrics, availability metrics, and resource utilization metrics
- Metric names must be plain text without any HTML formatting or tags
- If a metric name appears to be split with HTML tags (like "availability<br>rate"), combine it into a single clean name ("availabilityrate")

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
- No HTML tags (<br>, <p>, etc.) in any values, especially parameter names

**IMPACT_LEVEL must be EXACTLY one of: "high", "medium", or "low"**
**SYSTEM_TYPE must be EXACTLY one of: "Database", "Application Server", "Both", or "System"**

CRITICAL REQUIREMENTS:
- Clearly distinguish between database parameters and SAP Application Server parameters using the system_type field
- For database parameters: use SYSTEM_TYPE = "Database"
- For SAP Application Server parameters: use SYSTEM_TYPE = "Application Server"  
- For parameters that affect both: use SYSTEM_TYPE = "Both"
- For general system parameters: use SYSTEM_TYPE = "System"
- Parameter names must be plain text without any HTML formatting or tags

INSTRUCTIONS:
- Extract ALL parameter recommendations mentioned in the report
- Include current values and recommended values where available
- Assess impact level based on the criticality described in the report
- Provide clear descriptions of what each parameter does
- Look for ALL parameter recommendations
- Pay special attention to database-specific vs application server-specific parameters
- If a parameter name appears to be split with HTML tags (like "sslsessioncach<br>emode"), combine it into a single clean name ("sslsessioncachemode")

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
            response = self.client.chat.completions.create(
                model=model,
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
            print(f"[STEP 2] Generating summary for {state.blob_name} using {AZURE_OPENAI_SUMMARY_MODEL}")
            state.summary_result = await self.call_openai(
                SUMMARY_PROMPT, 
                state.markdown_content,
                model=AZURE_OPENAI_SUMMARY_MODEL,
                max_tokens=16000
            )
            return state
        except Exception as e:
            state.error = str(e)
            return state
    
    async def extract_metrics_step(self, state: WorkflowState) -> WorkflowState:
        """Step 3: Extract metrics as JSON"""
        try:
            print(f"[STEP 3] Extracting metrics for {state.blob_name} using {AZURE_OPENAI_METRICS_MODEL}")
            metrics_response = await self.call_openai(
                METRICS_EXTRACTION_PROMPT, 
                state.markdown_content,
                model=AZURE_OPENAI_METRICS_MODEL,
                max_tokens=16000
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
            print(f"[STEP 4] Extracting parameters for {state.blob_name} using {AZURE_OPENAI_PARAMETERS_MODEL}")
            parameters_response = await self.call_openai(
                PARAMETERS_EXTRACTION_PROMPT, 
                state.markdown_content,
                model=AZURE_OPENAI_PARAMETERS_MODEL,
                max_tokens=16000
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
    
    def clean_html_from_json_object(self, json_obj):
        """Remove HTML tags from all string values in a JSON object recursively"""
        if isinstance(json_obj, dict):
            result = {}
            for key, value in json_obj.items():
                # Clean the key if it's a string
                if isinstance(key, str):
                    # Remove all HTML tags completely
                    key = re.sub(r'<[^>]*>|</[^>]*>', '', key)
                # Clean the value recursively
                result[key] = self.clean_html_from_json_object(value)
            return result
        elif isinstance(json_obj, list):
            return [self.clean_html_from_json_object(item) for item in json_obj]
        elif isinstance(json_obj, str):
            # More thorough HTML tag removal that handles nested tags
            # First, try with a proper HTML parser if the string is complex
            if '<' in json_obj and '>' in json_obj and len(json_obj) > 20:
                # Use regex to handle complex cases with nested tags
                # This approach removes all HTML tags while preserving the text content
                clean_str = re.sub(r'<[^>]*>|</[^>]*>', '', json_obj)
                
                # Remove any duplicate whitespace created by tag removal
                clean_str = re.sub(r'\s+', ' ', clean_str).strip()
                
                return clean_str
            else:
                # Simple HTML tag removal for less complex strings
                return re.sub(r'<[^>]+>', '', json_obj)
        else:
            return json_obj
    
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
                # Clean any HTML tags from metrics data
                cleaned_metrics = self.clean_html_from_json_object(state.metrics_result)
                
                # Special handling for metric names - ensure they're clean
                if 'metrics' in cleaned_metrics and isinstance(cleaned_metrics['metrics'], list):
                    for metric in cleaned_metrics['metrics']:
                        if 'name' in metric and isinstance(metric['name'], str):
                            # Remove any HTML tags and normalize spacing
                            metric['name'] = re.sub(r'\s+', ' ', re.sub(r'<[^>]*>|</[^>]*>', '', metric['name'])).strip()
                            
                        # Also clean current and target values which might contain HTML
                        for field in ['current', 'target', 'description']:
                            if field in metric and isinstance(metric[field], str):
                                # Process complex HTML content in values
                                metric[field] = re.sub(r'\s+', ' ', re.sub(r'<[^>]*>|</[^>]*>', '', metric[field])).strip()
                
                metrics_blob_name = f"{base_name}_metrics.json"
                metrics_json = json.dumps(cleaned_metrics, indent=2)
                await self.upload_to_blob(metrics_blob_name, metrics_json, "application/json")
            
            # Save parameters as JSON
            if state.parameters_result:
                # Clean any HTML tags from parameters data
                cleaned_parameters = self.clean_html_from_json_object(state.parameters_result)
                
                # Special handling for parameter names - ensure they're clean
                if 'parameters' in cleaned_parameters and isinstance(cleaned_parameters['parameters'], list):
                    for param in cleaned_parameters['parameters']:
                        if 'name' in param and isinstance(param['name'], str):
                            # Remove any HTML tags and normalize spacing
                            param['name'] = re.sub(r'\s+', ' ', re.sub(r'<[^>]*>|</[^>]*>', '', param['name'])).strip()
                            
                            # Handle special cases where HTML might break parameter names
                            # For example: "sslsessioncach<br>emode" -> "sslsessioncachemode"
                            param['name'] = param['name'].replace('|', '_').replace('=', '_')
                            
                        # Also clean current and recommended values which might contain HTML
                        for field in ['current', 'recommended', 'description']:
                            if field in param and isinstance(param[field], str):
                                # Process complex HTML content in values
                                raw_value = param[field]
                                
                                # Handle potential pipe and bracket syntax seen in screenshot
                                if '|' in raw_value or '[' in raw_value:
                                    # Preserve important parts of the parameter value syntax
                                    clean_value = re.sub(r'<[^>]*>|</[^>]*>', '', raw_value)
                                    param[field] = re.sub(r'\s+', ' ', clean_value).strip()
                                else:
                                    param[field] = re.sub(r'\s+', ' ', re.sub(r'<[^>]*>|</[^>]*>', '', raw_value)).strip()
                
                parameters_blob_name = f"{base_name}_parameters.json"
                parameters_json = json.dumps(cleaned_parameters, indent=2)
                await self.upload_to_blob(parameters_blob_name, parameters_json, "application/json")
            
            return state
        except Exception as e:
            state.error = str(e)
            return state
    
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
                "message": "Workflow completed successfully",
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
