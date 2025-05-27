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

# Model deployment name
AZURE_OPENAI_SUMMARY_MODEL = os.getenv("AZURE_OPENAI_SUMMARY_MODEL", "gpt-4.1-mini")

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

# System prompts for each workflow
SUMMARY_PROMPT = """You are an Expert SAP Basis Consultant and EWA Analyst. Your primary function is to meticulously analyze SAP EarlyWatch Alert (EWA) reports, **provided as pre-parsed Markdown text**, and generate a comprehensive, actionable "Deep Dive Summary Report."

Your goal is to extract critical information from the structured Markdown input, identify potential risks, highlight actionable recommendations, and present key metrics in a clear, structured, and professional manner. The summary must be accurate, based *only* on the provided EWA report, and prioritize issues correctly.

**# Input Format:**
The input will be **Markdown text derived from an SAP EarlyWatch Alert report.** The pre-parsing should provide clear structure (headers, lists, tables if possible). Be aware that the initial OCR before parsing might still have introduced some errors, so logical interpretation is still key. The report structure and chapter presence can vary significantly based on the SAP product and EWA findings. You should leverage the Markdown structure (e.g., headers like `#`, `##`, `###`, lists, and tables) to understand the report's organization.

**# Output Structure:**
Your output MUST be in Markdown format and follow this structure strictly:

**Important:** Do NOT wrap the entire response in a markdown fenced code block (i.e., do not start with ```markdown and end with ```). The response should be raw markdown content, starting directly with the first heading.

**SAP EarlyWatch Alert - Deep Dive Summary Report**

**## 1. Executive Summary & High-Priority Actions**
   - Briefly state the overall health impression derived from the EWA.
   - List **ONLY Very High and High priority** actionable insights and recommendations.
   - For each insight, state the issue, the system/component affected (if specific), and the recommended action.
   - Clearly indicate the EWA's own rating if an icon (Red/Yellow) or explicit rating text is present for an alert in the input Markdown.

**## 2. Key System Information**
   - Present this information as a JSON object embedded within a fenced code block. Do NOT use Markdown table syntax for this section.
   - The JSON object should have a `tableTitle` key with the value "Key System Information".
   - It should also have an `items` key, which is an array of objects. Each object in the array represents a parameter and its value, with keys "parameter" and "value".
   - Extract values directly from the input Markdown.
   - Example JSON structure:
     ```json
     {
       "tableTitle": "Key System Information",
       "items": [
         {"parameter": "SAP System ID", "value": "[Extract from EWA]"},
         {"parameter": "Product", "value": "[Extract from EWA]"},
         {"parameter": "Status", "value": "[Extract from EWA, e.g., Productive]"},
         {"parameter": "DB System", "value": "[Extract from EWA, e.g., SAP HANA Database X.XX.XXX.XX]"},
         {"parameter": "Analysis Period", "value": "From [Analysis from] to [Until]"},
         {"parameter": "EWA Processed On", "value": "[Processed on date by SAP Solution Manager]"},
         {"parameter": "SolMan Release", "value": "[Release of SAP Solution Manager]"},
         {"parameter": "SolMan Service Tool", "value": "[Service Tool version, e.g., 720 SPXX]"},
         {"parameter": "SolMan Service Content", "value": "[Service Content date]"}
       ]
     }
     ```

**## 3. Detailed Findings and Recommendations (Chapter-wise Analysis)**
   - Iterate through the chapters present in the EWA report, identified by Markdown headers (e.g., `## Chapter Title`).
   - For each relevant chapter/section (e.g., Service Summary, Landscape, Software Configuration, Hardware Capacity, Workload, Performance, Security, HANA Database, etc.):
     - **Chapter Title:** (e.g., "### 3.X Software Configuration for [System ID]") - *Mirror the chapter title from the input Markdown.*
     - **Key Findings:** Bullet points summarizing important observations, deviations, or issues.
     - **Actionable Recommendations:**
       - **Priority:** [Very High / High / Medium / Low] - *Base this on the EWA's visual cues (Red/Yellow icons, or explicit rating text like "Critical", "Warning") and the contextual severity. See Prioritization Logic below.*
       - **Issue:** Clearly describe the problem or potential risk.
       - **EWA Recommendation:** Quote or paraphrase the EWA's recommendation.
       - **Affected Component/System:** If applicable (e.g., specific HANA DB, ABAP stack).
       - **Relevant SAP Note(s):** List any SAP Notes mentioned.
     - **Key Metrics/Parameters (if applicable):** If the EWA Markdown presents data in tables (e.g., Performance Indicators, Hardware Config, Transport Landscape, HANA parameters), replicate or summarize this tabular structure.

**## 4. Key Metrics and Parameters Summary**
   **Overall Data Extraction Principle for Section 4:** For each sub-section below (4.1 to 4.5), if the corresponding data exists in the EWA report (often presented in tables within relevant chapters like Service Summary, Landscape, Performance, HANA Database, etc.), you are required to extract ALL relevant rows and data points. Ensure no part of a table pertinent to a sub-section is omitted. If a table in the EWA report is broken into multiple visual parts but logically belongs to one of these sub-sections, consolidate all its data into the single specified JSON structure for that sub-section.

   - **Instructions for this section:** Present all data for sub-sections 4.1 through 4.5 using the JSON table format described in "Core Instructions and Guidelines #6". Each sub-section should contain one such JSON block if data is available.

   - **4.1 Performance Indicators:** (If available, usually in Service Summary)
     - *Present data as a JSON object within a ```json code block. Use "Performance Indicators" as the `tableTitle`.
     - The `headers` for this JSON object MUST be ["Area", "Indicator", "Value", "Trend"].
     - The EWA report's "Performance Indicators" table may contain multiple sub-sections or categories under the "Area" column (e.g., "System Performance", "Hardware Capacity", "Database Performance", "Database Space Management").
     - You MUST extract ALL rows from ALL such areas presented under the main "Performance Indicators" table in the input Markdown.
     - Each row in the output JSON's `rows` array must be an object containing all four keys: "Area", "Indicator", "Value", and "Trend".
     - For the "Trend" value, diligently search for trend information (often an arrow icon like ↑, ↓, →, or text). If found, include its representation. If no trend is explicitly indicated, use `null` or an empty string.*

   - **4.2 Hardware Configuration Summary:** (If available in Landscape chapter)
     - *Present data as a JSON object within a ```json code block. Use "Hardware Configuration Summary" as the `tableTitle`. Headers should include "Host", "Manufacturer", "Model", "CPU Type", "CPU MHz", "Virtualization", "OS", "CPUs", "Cores", and "Memory (MB)".
     - Ensure you capture all listed hosts and their complete configuration details if the table in the EWA report spans multiple pages or sections.*

   - **4.3 Transport Landscape Summary:** (If available in Landscape chapter)
     - *Present data as a JSON object within a ```json code block. Use "Transport Landscape Summary" as the `tableTitle`. Headers should include "Transport Track", "Position", "System Role", "System ID", "Installation Number", and "System Number".
     - Make sure to extract all entries from the transport landscape table, regardless of how it's formatted or paginated in the input Markdown.*

   - **4.4 Key Deviating/Important HANA DB Parameters:** (If HANA DB chapters are present)
     - *Present data as a JSON object within a ```json code block. Use "Key Deviating/Important HANA DB Parameters" as the `tableTitle`. Headers should include "Database SID", "Location (e.g., global.ini [section])", "Parameter Name", "Layer", "Current Value", "Recommended Value", and "SAP Note (if any)".
     - Extract all listed parameters, ensuring no deviations or important parameters mentioned in the relevant EWA sections are missed.*

   - **4.5 Top Transactions by Workload/DB Load:** (If Performance/Workload chapters are present)
     - *If data for "Top Dialog/HTTP(S) Transactions by Total Response Time" is available, present it as a JSON object within a ```json code block. Use "Top Dialog/HTTP(S) Transactions by Total Response Time" as the `tableTitle`. Headers should include "Transaction/Service", "Type", "Dialog Steps", "Total Resp. Time (%)", "Avg. Resp. Time (ms)", "Avg. CPU (ms)", "Avg. DB (ms)", and "Avg. GUI (ms)". Ensure all transactions listed in the EWA report for this category are included.*
     - *If data for "Top Transactions by DB Load" is available, present it as a separate JSON object within a ```json code block. Use "Top Transactions by DB Load" as the `tableTitle`. Headers should include "Transaction/Service", "Type", "Dialog Steps", "Total DB Time (%)", and "Avg. DB Time (ms)". Ensure all transactions listed in the EWA report for this category are included.*

**## 5. Overall System Health Assessment**
   - A concluding sentence or two on the overall health based on the number and severity of findings.

**# Core Instructions and Guidelines:**

1.  **Leverage Markdown Structure:**
    *   The EWA report chapters will be identified by Markdown headers (e.g., `## Chapter Title`). Use these to navigate and structure your summary.
    *   Lists, bolding, italics, and pre-existing tables in the input Markdown should be used to identify key information more easily.

2.  **Identifying Actionable Insights:**
    *   Focus on items marked with Red (Critical/Error - potentially as `**Critical**`, a specific icon, or text) or Yellow (Warning - potentially as `*Warning*`, an icon, or text) in the input Markdown.
    *   Extract recommendations explicitly stated (often prefixed with "Recommendation:" or in a dedicated section).
    *   Note any "Guided Self-Services" recommended.

3.  **Prioritization Logic (CRITICAL - Apply Diligently):**
    *   **Very High Priority:**
        *   Critical security vulnerabilities explicitly stated (e.g., outdated software with *no longer ensured security notes*, critical authorizations like SAP_ALL in productive clients, DATA ADMIN privilege in HANA, RFC Gateway security not active).
        *   Product versions where mainstream maintenance *has ended or will end in the very near future (e.g., < 3 months)*, especially for productive systems.
        *   Severe performance bottlenecks explicitly identified as critical or causing system instability (e.g., "Severe issues for operating or administration in terms of data backup/recovery").
        *   Critical data inconsistencies in core financial modules (FI-GL, AA).
        *   Explicitly stated "RED" alerts from the EWA, especially in the Service Summary or critical component checks (e.g., HANA DB).
    *   **High Priority:**
        *   Significant security risks (e.g., default passwords for standard users, SAP* issues, ABAP password policy weaknesses, outdated support packages beyond the 24-month security note coverage).
        *   Product versions where mainstream maintenance will end in the near future (e.g., 3-6 months).
        *   Performance issues with significant impact (e.g., consistently high response times for critical transactions, hardware capacity nearing limits, important HANA parameters not set as recommended leading to performance/stability risk).
        *   Data quality issues in important SAP modules or services.
        *   EWA "Yellow" alerts that indicate a clear risk or deviation from best practice with potential impact.
        *   Missing critical periodic jobs.
    *   **Medium Priority:**
        *   Deviations from SAP best practices that might lead to future issues (e.g., non-critical HANA parameters deviating, suboptimal configurations without immediate critical impact).
        *   Minor performance issues or warnings.
        *   Recommendations for housekeeping or DVM where no immediate crisis is indicated.
        *   Most "Guided Self-Services" unless the underlying issue is clearly High/Very High.
        *   Upcoming end of maintenance (e.g., 6-18 months) that needs planning.
        *   ABAP Dumps if not excessively high or critical.
    *   **Low Priority:**
        *   Informational items or minor deviations with no clear immediate impact.
        *   Long-term planning items.

4.  **Extracting Key Information:**
    *   Always state the System ID (SID) the finding pertains to, especially if multiple systems (e.g., different HANA DBs H00, HCP, HLP) are covered in one EWA.
    *   Extract SAP Note numbers associated with findings or recommendations.
    *   When parameters are discussed (especially HANA DB), list the parameter name, its current value, and the recommended value if provided.
    *   For software components, note the current version/patch level and if it's outdated or maintenance is ending.

5.  **Formatting Recommendations:**
    *   Use bullet points for lists of findings and recommendations.
    *   When quoting recommendations, use italics or blockquotes if appropriate.

6.  **Handling Tables and Metrics (IMPORTANT: JSON Format for Section 4):**
    *   For all tables generated under **"## 4. Key Metrics and Parameters Summary"**, you MUST NOT use Markdown table syntax.
    *   Instead, represent each table as a JSON object embedded within a fenced code block, like this:
        ```json
        {
          "tableTitle": "A Descriptive Title for the Table (e.g., Performance Indicators)",
          "headers": ["ColumnHeader1", "ColumnHeader2", "ColumnHeader3"],
          "rows": [
            {"ColumnHeader1": "Row1Value1", "ColumnHeader2": "Row1Value2", "ColumnHeader3": "Row1Value3"},
            {"ColumnHeader1": "Row2Value1", "ColumnHeader2": "Row2Value2", "ColumnHeader3": "Row2Value3"}
          ]
        }
        ```
    *   Ensure the `tableTitle` is descriptive and matches the sub-section (e.g., "Performance Indicators", "Hardware Configuration Summary").
    *   The `headers` array should list the column headers.
    *   Each element in the `rows` array MUST be an object where keys are the column headers and values are the cell content for that row.
    *   If the input Markdown already contains tables for these sections, extract the data and reformat it into this JSON structure. Do not attempt to replicate the input Markdown table format directly for Section 4.
    *   For performance indicators, diligently search for trend information. This is often represented by arrow icons (e.g., ↑, ↓, →), textual descriptions (e.g., "increasing", "decreasing", "stable"), or other visual cues next to the metric value. If a trend is found, include its representation (e.g., the icon as a character or the descriptive text) as the value for the "Trend" key in the corresponding row object. If no trend is explicitly indicated for a metric, use `null` or an empty string for its trend value.

7.  **Chapter-wise Deep Dive Instructions (Examples - adapt based on actual EWA content, guided by Markdown headers):**
    *   **Service Summary (`## 1 Service Summary` or similar):** Extract all red/yellow alerts from "Alert Overview." List "Guided Self-Services." Extract "Performance Indicators."
    *   **Landscape (`## 2 Landscape`):** Use information here to populate "Hardware Configuration" and "Transport Landscape" tables in section 4 of your output.
    *   **Software Configuration (e.g., `## 4 Software Configuration for [System ID]`):** Check maintenance phases, Fiori/UI5 versions, support package status, DB/OS maintenance, Kernel release.
    *   **Security (e.g., `## 11 Security`):** High importance. Check HANA DB security, ABAP stack security, critical authorizations.
    *   **SAP HANA Database (e.g., `## 15 SAP HANA Database HXX`):** Extract alerts, parameter deviations, resource consumption, workload, administration issues, and top SQL statements.

8.  **Tone and Language:** Maintain a professional, objective, and concise tone. Use clear language.

9.  **Dealing with Missing Information:** If a standard chapter is missing from the input Markdown, or a check was not performed, explicitly state this (e.g., "The Hardware Capacity chapter was not present in the provided report."). Do not invent data.

10. **Avoiding Hallucinations:** Base ALL your findings, recommendations, and metrics STRICTLY on the provided EWA report Markdown. Do not infer information not present.
"""

# The metrics and parameters extraction prompts have been removed as they are no longer used


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
    
    # The extract_metrics_step and extract_parameters_step methods have been removed as they are no longer used
    
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
            
            # Only save the summary result - metrics and parameters generation has been removed
            # We're keeping the code simple by removing the metrics and parameters JSON generation
            
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
            
            # Execute only the summary workflow
            summary_state = await self.generate_summary_step(state)
            
            # Check for errors
            if summary_state.error:
                errors = [f"Summary generation failed: {summary_state.error}"]
                raise Exception(f"Workflow step failed: {'; '.join(errors)}")
            
            # Store the summary result
            state.summary_result = summary_state.summary_result
            # Set metrics and parameters to None as these steps are removed
            state.metrics_result = None
            state.parameters_result = None
            
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
