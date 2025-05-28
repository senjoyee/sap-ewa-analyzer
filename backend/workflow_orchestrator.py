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
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI, AsyncAzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

# Environment variable keys
AZURE_OPENAI_SUMMARY_MODEL_ENV = "AZURE_OPENAI_SUMMARY_MODEL"
AZURE_OPENAI_VISION_DEPLOYMENT_NAME_ENV = "AZURE_OPENAI_VISION_DEPLOYMENT_NAME"
AZURE_OPENAI_CHAT_MODEL_ENV = "AZURE_OPENAI_CHAT_MODEL"

# Load deployment names with defaults
AZURE_OPENAI_SUMMARY_MODEL = os.getenv(AZURE_OPENAI_SUMMARY_MODEL_ENV)
AZURE_OPENAI_VISION_DEPLOYMENT_NAME = os.getenv(AZURE_OPENAI_VISION_DEPLOYMENT_NAME_ENV)
AZURE_OPENAI_CHAT_MODEL = os.getenv(AZURE_OPENAI_CHAT_MODEL_ENV)

AZURE_OPENAI_TOKEN_USAGE_LOG = os.getenv("AZURE_OPENAI_TOKEN_USAGE_LOG", "ewa_token_usage.json")

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
   - Present this information as simple markdown bullet points for better readability.
   - Extract all values directly from the input EWA report.
   - Follow this format exactly:

```markdown
## 2. Key System Information

* **SAP System ID**: [Extract from EWA]
* **Product**: [Extract from EWA]
* **Status**: [Extract from EWA, e.g., Productive]
* **DB System**: [Extract from EWA, e.g., SAP HANA Database X.XX.XXX.XX]
* **Analysis Period**: From [Analysis from] to [Until]
* **EWA Processed On**: [Processed on date by SAP Solution Manager]
* **SolMan Release**: [Release of SAP Solution Manager]
* **SolMan Service Tool**: [Service Tool version, e.g., 720 SPXX]
* **SolMan Service Content**: [Service Content date]
```

   - Ensure all bullet points are included even if some information is not available in the EWA report (indicate with "Not specified" or similar).
   - Maintain consistent formatting with bold parameter names followed by their values.

**## 3. Detailed Findings and Recommendations (Chapter-wise Analysis)**
   - Iterate through the chapters present in the EWA report, identified by Markdown headers (e.g., `## Chapter Title`).
   - For each relevant chapter/section (e.g., Service Summary, Landscape, Software Configuration, Hardware Capacity, Workload, Performance, Security, HANA Database, etc.):
     - **Chapter Title:** (e.g., "### 3.X Software Configuration for [System ID]") - *Mirror the chapter title from the input Markdown.*
     - **Key Findings:** Bullet points summarizing important observations, deviations, or issues.
     - **Actionable Recommendations:**
       - **Priority:** [Very High / High / Medium / Low] - *Base this on the EWA's visual cues (Red/Yellow icons, or explicit rating text like "Critical", "Warning") and the contextual severity. See Prioritization Logic below.*
       - **Issue:** Clearly describe the problem or potential risk.
       - **EWA Recommendation:** Quote or paraphrase the EWA's recommendation.
       - **Affected Component/System:** If applicable (e.g., specific DB like HANA or Oracle or application layer like ABAP or JAVA stack).
       - **Relevant SAP Note(s):** List any SAP Notes mentioned.
     - **Key Metrics/Parameters (if applicable):** If the EWA Markdown presents data in tables (e.g., Performance Indicators, Hardware Config, Transport Landscape, HANA parameters), replicate or summarize this tabular structure.

**## 4. Key Metrics and Parameters Summary**
   **Overall Data Extraction Principle for Section 4:** For each sub-section below (4.1 to 4.5), if the corresponding data exists in the EWA report (often presented in tables within relevant chapters like Service Summary, Landscape, Performance, HANA Database, etc.), you are required to extract ALL relevant rows and data points. Ensure no part of a table pertinent to a sub-section is omitted. If a table in the EWA report is broken into multiple visual parts but logically belongs to one of these sub-sections, consolidate all its data into the single specified JSON structure for that sub-section.

   - **Instructions for this section:** Present all data for sub-sections 4.1 through 4.5 using the JSON table format described in "Core Instructions and Guidelines #6". Each sub-section should contain one such JSON block if data is available.

   - **4.1 Performance Indicators:** (If available, usually in Service Summary)
     - *Present data as a JSON object within a ```json code block. Use "Performance Indicators" as the `tableTitle`.
     - The EWA report's "Performance Indicators" table may contain multiple sub-sections or categories under the "Area" column (e.g., "System Performance", "Hardware Capacity", "Database Performance", "Database Space Management").
     - You MUST extract ALL rows from ALL such areas presented under the main "Performance Indicators" table in the input Markdown.\n
     
     
   - **4.2 Hardware Configuration Summary:** (If available in Landscape chapter)
     - *Present data as a JSON object within a ```json code block. Use "Hardware Configuration Summary" as the `tableTitle`. Headers should include "Host", "Manufacturer", "Model", "CPU Type", "CPU MHz", "Virtualization", "OS", "CPUs", "Cores", and "Memory (MB)".
     - Ensure you capture all listed hosts and their complete configuration details if the table in the EWA report spans multiple pages or sections.*

   - **4.3 Transport Landscape Summary:** (If available in Landscape chapter)
     - *Present data as a JSON object within a ```json code block. Use "Transport Landscape Summary" as the `tableTitle`. Headers should include "Transport Track", "Position", "System Role", "System ID", "Installation Number", and "System Number".
     - Make sure to extract all entries from the transport landscape table, regardless of how it's formatted or paginated in the input Markdown.*

   - **4.4 Key Deviating/Important DB Parameters(HANA or Oracle):** (If DB chapters are present)
     - *Present data as a JSON object within a ```json code block. Use "Key Deviating/Important DB Parameters" as the `tableTitle`. Headers should include "Database SID", "Location (e.g., global.ini [section])", "Parameter Name", "Layer", "Current Value", "Recommended Value", and "SAP Note (if any)".
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
    *   Extract SAP Note numbers associated with findings or recommendations.
    *   When parameters are discussed (especially DB), list the parameter name, its current value, and the recommended value if provided.
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
    *   **Database like HANA or Oracle (e.g., `## 15 Database HXX`):** Extract alerts, parameter deviations, resource consumption, workload, administration issues, and top SQL statements.

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
    
    # Remove JavaScript/JSON comments
    json_string = re.sub(r'//.*(?=\n)', '', json_string)
    json_string = re.sub(r'/\*.*?\*/', '', json_string, flags=re.DOTALL)
    # Remove Python-style comments
    json_string = re.sub(r'#.*(?=\n)', '', json_string)
    
    # Remove control characters that cause parsing errors
    json_string = re.sub(r'[\x00-\x1F\x7F]', '', json_string)
    
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
    
    # Fix missing commas between properties (common LLM error)
    json_string = re.sub(r'("[^"]*"|\d+|true|false|null)\s*\n\s*("[^"]*"\s*:)', r'\1,\n\2', json_string)
    
    # Replace array-like descriptions with quoted strings (e.g., [varies from 0 to 11])
    json_string = re.sub(r'\[varies from \d+ to \d+\]', '"varies"', json_string)
    json_string = re.sub(r'\[\s*varies\s*\]', '"varies"', json_string)
    
    # Replace complex arrays described in text with a placeholder
    json_string = re.sub(r'\[[^\[\]]*?\d+[^\[\]]*?\](?!\s*[,}\]])', '"array_value"', json_string)
    
    # Fix missing quotes around property names
    json_string = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_string)
    
    # Fix single quotes used instead of double quotes for property names
    json_string = re.sub(r'([{,])\s*\'([^\']+)\'\s*:', r'\1"\2":', json_string)
    
    # Fix single quotes used instead of double quotes for string values
    json_string = re.sub(r':\s*\'([^\']*)\'', r':"\1"', json_string)
    
    # Replace text descriptions of numbers with quoted strings
    json_string = re.sub(r':\s*(varies|unknown|multiple|various|none)\s*([,}])', r':"\1"\2', json_string, flags=re.IGNORECASE)
    
    # Fix empty values or invalid formats with null or empty strings
    json_string = re.sub(r':\s*,', ':null,', json_string)
    json_string = re.sub(r':\s*\}', ':null}', json_string)
    
    # Log the repaired string
    print(f"Repaired JSON string: {json_string[:100]}..." if len(json_string) > 100 else f"Repaired JSON string: {json_string}")
    
    # Unescape any escaped quotes for proper JSON
    json_string = json_string.replace('\\"', '"')
    
    return json_string


@dataclass
class WorkflowState:
    """Data class to track workflow state"""
    def __init__(self, blob_name: str):
        self.blob_name: str = blob_name  # Original blob name
        self.markdown_content: str = ""  # Content downloaded from blob storage
        self.summary_result: str = ""   # Result of summary generation
        self.image_analysis: str = ""   # Result of image analysis with structured data extraction
        self.image_descriptions: List[Dict] = []  # Pure descriptions of images
        self.structured_image_data: List[Dict] = []  # Structured data extracted from images
        self.error: Optional[str] = None  # Error message if any
        
        # Token tracking
        self.total_prompt_tokens: int = 0  # Total prompt tokens (input)
        self.total_completion_tokens: int = 0  # Total completion tokens (output)
        self.total_tokens: int = 0  # Total tokens (input + output)
        
        # Image processing tracking
        self.total_images_found: int = 0  # Total images found before filtering
        self.images_filtered_size: int = 0  # Images filtered due to small size
        self.images_filtered_dimensions: int = 0  # Images filtered due to small dimensions
        self.images_processed: int = 0  # Images actually processed


class EWAWorkflowOrchestrator:
    """Custom orchestrator for EWA analysis workflows"""
    
    SUMMARY_PROMPT = SUMMARY_PROMPT
    
    def __init__(self):
        self.client = None
        self.async_client = None
        self.blob_service_client = None
        self.summary_deployment_name = AZURE_OPENAI_SUMMARY_MODEL
        self.vision_deployment_name = AZURE_OPENAI_VISION_DEPLOYMENT_NAME
        self.chat_deployment_name = AZURE_OPENAI_CHAT_MODEL
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Azure OpenAI and Blob Storage clients"""
        try:
            # Initialize Azure OpenAI client
            self.client = AzureOpenAI(
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")
            )
            
            # Initialize Async Azure OpenAI client
            self.async_client = AsyncAzureOpenAI(
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")
            )
            
            # Initialize Azure Blob Storage client
            connect_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
            self.blob_service_client = BlobServiceClient.from_connection_string(connect_str)
            print("Initialized Azure OpenAI, Async OpenAI, and Blob Storage clients successfully")
            
        except Exception as e:
            error_message = f"Error initializing clients: {str(e)}"
            print(error_message)
            raise Exception(error_message)

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
    
    async def call_openai(self, prompt: str, content: str, model: str) -> str:
        """Make a call to Azure OpenAI with specified model"""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Please analyze this EWA document:\n\n{content}"}
                ],
                temperature=0.1,
                frequency_penalty=0,
                presence_penalty=0
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            error_message = f"Error calling Azure OpenAI: {str(e)}"
            print(error_message)
            raise Exception(error_message)
            
    async def generate_sas_url(self, blob_name, expiry_minutes=30):
        """Generate a SAS URL for a blob with specified expiry time"""
        try:
            from datetime import datetime, timedelta
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            
            # Get account name and key from connection string - properly handle = characters in account key
            conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
            # Process each part safely
            parts = {}
            for part in conn_str.split(';'):
                if not part or '=' not in part:
                    continue
                    
                # Split only at the first = to preserve any = in the value
                key, value = part.split('=', 1)
                parts[key] = value
                
            account_name = parts.get('AccountName')
            account_key = parts.get('AccountKey')
            
            # Validate account details
            if not account_name or not account_key:
                raise ValueError("Invalid connection string: missing AccountName or AccountKey")
            
            # Set expiry time
            expiry = datetime.utcnow() + timedelta(minutes=expiry_minutes)
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=AZURE_STORAGE_CONTAINER_NAME,
                blob_name=blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry
            )
            
            # Generate the full URL
            blob_url = f"https://{account_name}.blob.core.windows.net/{AZURE_STORAGE_CONTAINER_NAME}/{blob_name}?{sas_token}"
            return blob_url
        except Exception as e:
            print(f"Error generating SAS URL: {str(e)}")
            # Log additional debug information
            print(f"Blob name: {blob_name}")
            return None
    
    async def detect_and_analyze_images_step(self, state: WorkflowState) -> WorkflowState:
        """Detect extracted images and process them in two phases: 1) Generate pure descriptions, 2) Analyze with context"""
        try:
            print(f"Detecting images for {state.blob_name}")
            
            # Configuration for image filtering and async processing
            MIN_IMAGE_SIZE_KB = 20  # Skip images smaller than 20 KB
            MIN_IMAGE_WIDTH = 200   # Skip images narrower than 200 pixels
            MIN_IMAGE_HEIGHT = 200  # Skip images shorter than 200 pixels
            MAX_CONCURRENT_REQUESTS = 5  # Maximum number of concurrent API calls
            
            # Get base name for image detection
            base_name = os.path.splitext(state.blob_name)[0]
            
            # List all blobs to find extracted images
            container_client = self.blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
            blob_list = container_client.list_blobs()
            
            # Find images extracted for this document
            image_blobs = []
            for blob in blob_list:
                # Check for images in the images folder (e.g., ERP_08.05.2025_images/)
                images_folder = f"{base_name}_images/"
                if blob.name.startswith(images_folder) and blob.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_blobs.append(blob.name)
                # Also check for images with the old pattern (document.pdf-pX-Y.png)
                elif blob.name.startswith(f"{state.blob_name}-p") and blob.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_blobs.append(blob.name)
                # Also check for temp.pdf pattern which seems to be used
                elif blob.name.startswith("temp.pdf-") and blob.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_blobs.append(blob.name)
            
            if not image_blobs:
                print(f"No extracted images found for {state.blob_name}")
                state.image_analysis = "No images were extracted from this document."
                return state
            
            print(f"Found {len(image_blobs)} extracted images before filtering: {image_blobs}")
            
            # Track image insights - we'll collect both pure descriptions and analyses
            image_descriptions = []
            image_analyses = []
            
            # Filter images by size and dimensions
            filtered_images = []
            image_metadata = {}  # Store image metadata for scoring
            
            # First pass: Filter by size and dimensions
            for image_blob_name in image_blobs:
                try:
                    # Get image blob properties
                    blob_client = self.blob_service_client.get_blob_client(
                        container=AZURE_STORAGE_CONTAINER_NAME,
                        blob=image_blob_name
                    )
                    blob_properties = blob_client.get_blob_properties()
                    
                    # Check size
                    size_kb = blob_properties.size / 1024
                    if size_kb < MIN_IMAGE_SIZE_KB:
                        print(f"Skipping {image_blob_name} - too small: {size_kb:.2f} KB")
                        continue
                    
                    # Download image to check dimensions
                    image_data = blob_client.download_blob().readall()
                    
                    # Use PIL to get image dimensions
                    from io import BytesIO
                    from PIL import Image
                    
                    img = Image.open(BytesIO(image_data))
                    width, height = img.size
                    
                    # Check dimensions
                    if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                        print(f"Skipping {image_blob_name} - too small dimensions: {width}x{height}")
                        continue
                    
                    # Store image metadata for scoring
                    image_metadata[image_blob_name] = {
                        "size_kb": size_kb,
                        "dimensions": (width, height),
                        "data": image_data,  # Store image data to avoid downloading again
                        "page": None,  # Will be set if page pattern is matched
                        "score": 0    # Initial score
                    }
                    
                    filtered_images.append(image_blob_name)
                    
                except Exception as e:
                    print(f"Error checking image {image_blob_name}: {str(e)}")
            
            print(f"After size/dimension filtering: {len(filtered_images)} images remain")
            
            # Score images based on page number and content keywords
            page_pattern = re.compile(r'.*-p(\d+)-\d+\..*')
            
            # Calculate scores for each image
            for img_name in filtered_images:
                score = 0
                
                # Score based on page number if available
                match = page_pattern.match(img_name)
                if match:
                    page_num = int(match.group(1))
                    image_metadata[img_name]["page"] = page_num
                    
                    # Early pages often contain important information (but not too early like covers)
                    if 1 <= page_num <= 5:
                        score += 10
                
                # Score based on image size (larger images likely contain more information)
                size_kb = image_metadata[img_name]["size_kb"]
                # Normalize size score: 0-5 points based on size
                size_score = min(5, int(size_kb / 50))  # 1 point per 50KB up to 5 points
                score += size_score
                
                # Get image content to check for keywords
                try:
                    # If we're working with a markdown document, let's try to find the page content
                    # to check for relevant keywords near this image
                    if state.markdown_content:
                        # Extract page number if available
                        page_num = image_metadata[img_name].get("page")
                        
                        if page_num is not None:
                            # Look for page markers in the markdown content
                            page_markers = re.finditer(r'\n## Page (\d+)', state.markdown_content)
                            page_content = ""
                            
                            for marker in page_markers:
                                marker_page = int(marker.group(1))
                                if marker_page == page_num:
                                    # Found the right page, extract content until next page marker
                                    start_pos = marker.end()
                                    next_marker = re.search(r'\n## Page \d+', state.markdown_content[start_pos:])
                                    
                                    if next_marker:
                                        end_pos = start_pos + next_marker.start()
                                        page_content = state.markdown_content[start_pos:end_pos]
                                    else:
                                        # Last page, take until end
                                        page_content = state.markdown_content[start_pos:]
                                    break
                            
                            # Check for important keywords in the page content
                            if page_content:
                                # Keywords and their scores
                                keywords = {
                                    "Performance Indicator": 20,
                                    "Performance": 15,
                                    "Hardware": 15,
                                    "Trend": 15,
                                    "Critical": 15,
                                    "Warning": 10,
                                    "Memory": 10,
                                    "CPU": 10,
                                    "Disk": 10,
                                    "Database": 8,
                                    "HANA": 10,
                                    "Recommendation": 10
                                }
                                
                                for keyword, keyword_score in keywords.items():
                                    if keyword.lower() in page_content.lower():
                                        score += keyword_score
                except Exception as e:
                    print(f"Error analyzing page content for {img_name}: {str(e)}")
                
                # Store the final score
                image_metadata[img_name]["score"] = score
                print(f"Image {img_name} score: {score}")
            
            # Sort images by score (highest first)
            sorted_images = sorted(filtered_images, key=lambda x: image_metadata[x]["score"], reverse=True)
            
            print(f"Processing all {len(sorted_images)} filtered images (sorted by score):")
            for img in sorted_images:
                print(f"  - {img}: score={image_metadata[img]['score']}, size={image_metadata[img]['size_kb']:.2f}KB, dimensions={image_metadata[img]['dimensions']}")
            
            # Track token usage (now using state variables)
            image_count = 0
            
            # Create async functions for the two phases of image processing

            
            async def process_image_description(self, image_blob_name, image_data, semaphore):
                """Process an image to generate a pure description using Vision API"""
                async with semaphore:
                    try:
                        # Generate a SAS URL for the image (30 minute expiry)
                        image_url = await self.generate_sas_url(image_blob_name, expiry_minutes=30)
                        
                        if not image_url:
                            raise Exception(f"Failed to generate SAS URL for {image_blob_name}")
                        
                        # PHASE 1: Generate pure description with GPT-4 Vision
                        description_prompt = """Describe this image extracted from an SAP EWA (Early Watch Alert) report in detail. 

Focus ONLY on providing a clear, objective description of what you see in the image. DO NOT provide analysis, interpretations, or recommendations at this stage.

Include details about:
1. What type of visual element this is (chart, graph, table, diagram, screenshot, etc.)
2. The content visible in the image (titles, labels, data points, column headers, etc.)
3. Any colors, symbols, or visual indicators present
4. The apparent structure and organization of the information
5. Any text that is clearly readable in the image

If this is a table, describe:
- The table's structure and column headers
- The data visible in each column
- Any visual indicators like colors, arrows, or symbols

If this is a chart or graph, describe:
- The type of chart/graph (bar, line, pie, etc.)
- The axes and what they represent
- The data points or trends visible
- Any color coding or legends present

DO NOT interpret what the data means or make recommendations. Just describe what you see."""
                        
                        messages = [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": description_prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": image_url
                                        }
                                    }
                                ]
                            }
                        ]
                        
                        description_response = await self.async_client.chat.completions.create(
                            model=self.vision_deployment_name,
                            messages=messages,
                            max_tokens=800, 
                            temperature=0.0 
                        )
                        
                        # Extract token usage
                        tokens = {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0
                        }
                        
                        if hasattr(description_response, 'usage'):
                            tokens["prompt_tokens"] = description_response.usage.prompt_tokens
                            tokens["completion_tokens"] = description_response.usage.completion_tokens
                            tokens["total_tokens"] = description_response.usage.total_tokens
                            
                            print(f"Image Description for {image_blob_name} token usage: {tokens['prompt_tokens']} prompt + {tokens['completion_tokens']} completion = {tokens['total_tokens']} total tokens")
                        
                        image_description = description_response.choices[0].message.content
                        print(f"Generated description for image {image_blob_name}")
                        
                        return {
                            "name": image_blob_name,
                            "description": image_description,
                            "tokens": tokens
                        }
                        
                    except Exception as e:
                        error_msg = f"Error in description phase for {image_blob_name}: {str(e)}"
                        print(error_msg)
                        return {
                            "name": image_blob_name,
                            "description": f"Description failed - {str(e)}",
                            "error": error_msg,
                            "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                        }
            
            async def process_image_analysis(self, image_blob_name, image_data, semaphore):
                """Process an image to generate structured analysis using Vision API"""
                async with semaphore:
                    try:
                        # Generate a SAS URL for the image (30 minute expiry)
                        image_url = await self.generate_sas_url(image_blob_name, expiry_minutes=30)
                        
                        if not image_url:
                            raise Exception(f"Failed to generate SAS URL for {image_blob_name}")
                        
                        # PHASE 2: Analyze with structured data extraction
                        vision_prompt = """Analyze this image extracted from an SAP EWA (Early Watch Alert) report. 

IMPORTANT: If this image contains any table, you MUST provide a structured JSON output in addition to your analysis.

Focus on extracting:
1. Performance metrics, values, and KPIs from the table
2. Chart data points, graphs, or visualizations
3. Status indicators (red, yellow, green indicators)
4. System parameters or configuration values

For all tables, include EVERY row and ensure every column is populated with the simplified text values."""
                        
                        messages = [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": vision_prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": image_url
                                        }
                                    }
                                ]
                            }
                        ]
                        
                        analysis_response = await self.async_client.chat.completions.create(
                            model=self.vision_deployment_name,
                            messages=messages,
                            max_tokens=1500,
                            temperature=0.1
                        )
                        
                        # Extract token usage
                        tokens = {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0
                        }
                        
                        if hasattr(analysis_response, 'usage'):
                            tokens["prompt_tokens"] = analysis_response.usage.prompt_tokens
                            tokens["completion_tokens"] = analysis_response.usage.completion_tokens
                            tokens["total_tokens"] = analysis_response.usage.total_tokens
                            
                            print(f"Image Analysis for {image_blob_name} token usage: {tokens['prompt_tokens']} prompt + {tokens['completion_tokens']} completion = {tokens['total_tokens']} total tokens")
                        
                        image_analysis = analysis_response.choices[0].message.content
                        print(f"Analyzed image {image_blob_name}")
                        
                        return {
                            "name": image_blob_name,
                            "analysis": image_analysis,
                            "tokens": tokens
                        }
                        
                    except Exception as e:
                        error_msg = f"Error in analysis phase for {image_blob_name}: {str(e)}"
                        print(error_msg)
                        return {
                            "name": image_blob_name,
                            "analysis": f"Analysis failed - {str(e)}",
                            "error": error_msg,
                            "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                        }
            
            # Run image processing in parallel with asyncio
            print(f"Running image processing in parallel with max {MAX_CONCURRENT_REQUESTS} concurrent requests")
            
            async def process_all_images(self):
                # Create a semaphore to limit concurrent API calls
                semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
                
                # Create tasks for description phase
                description_tasks = []
                for image_blob_name in sorted_images:
                    # With SAS URLs, we don't need to download the image data anymore
                    # Just pass the blob name to the processing function
                    task = process_image_description(self, image_blob_name, None, semaphore)
                    description_tasks.append(task)
                
                # Run all description tasks in parallel (bounded by semaphore)
                print(f"PHASE 1: Generating descriptions for {len(description_tasks)} images in parallel")
                description_results = await asyncio.gather(*description_tasks)
                
                # Process description results
                for result in description_results:
                    image_descriptions.append({"name": result["name"], "description": result["description"]})
                    
                    # Update token counters
                    if "tokens" in result:
                        state.total_prompt_tokens += result["tokens"]["prompt_tokens"]
                        state.total_completion_tokens += result["tokens"]["completion_tokens"]
                        state.total_tokens += result["tokens"]["total_tokens"]
                
                # Create tasks for analysis phase
                analysis_tasks = []
                for image_blob_name in sorted_images:
                    # With SAS URLs, we don't need to download the image data anymore
                    # Just pass the blob name to the processing function
                    task = process_image_analysis(self, image_blob_name, None, semaphore)
                    analysis_tasks.append(task)
                
                # Run all analysis tasks in parallel (bounded by semaphore)
                print(f"PHASE 2: Generating analysis for {len(analysis_tasks)} images in parallel")
                analysis_results = await asyncio.gather(*analysis_tasks)
                
                # Process analysis results
                for result in analysis_results:
                    image_analyses.append(f"Image {result['name']}:\n{result['analysis']}")
                    
                    # Update token counters
                    if "tokens" in result:
                        state.total_prompt_tokens += result["tokens"]["prompt_tokens"]
                        state.total_completion_tokens += result["tokens"]["completion_tokens"]
                        state.total_tokens += result["tokens"]["total_tokens"]
                
                return len(description_results)
            
            # Run the async processing (we're already in an async context, so just await)
            image_count = await process_all_images(self)
            print(f"Completed parallel processing of {image_count} images")
            
                # Function to parse JSON with multiple fallback strategies
            def parse_json_with_fallbacks(json_str):
                import json
                
                # Strategy 1: Try direct parsing
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"Direct JSON parsing failed: {e}")
                
                # Strategy 2: Use our repair_json function
                try:
                    repaired_json = repair_json(json_str)
                    return json.loads(repaired_json)
                except json.JSONDecodeError as e:
                    print(f"Repaired JSON parsing failed: {e}")
                
                # Strategy 3: Extract portions that might be valid
                try:
                    # Find the start and end of valid JSON objects
                    start_idx = json_str.find('{')
                    end_idx = json_str.rfind('}')
                    
                    if start_idx >= 0 and end_idx > start_idx:
                        partial_json = json_str[start_idx:end_idx+1]
                        repaired_partial = repair_json(partial_json)
                        return json.loads(repaired_partial)
                except json.JSONDecodeError as e:
                    print(f"Partial JSON extraction failed: {e}")
                
                # Strategy 4: Try to extract just key information if it's a specific type
                # For example, try to salvage performance metrics even with malformed JSON
                try:
                    if "performance_metrics" in json_str:
                        # Create a minimal valid structure with what we can extract
                        return {"type": "performance_metrics", "partial": True, "error": "JSON parsing failed", "raw_text": json_str[:500]}
                    elif "tables" in json_str:
                        return {"type": "table_data", "partial": True, "error": "JSON parsing failed", "raw_text": json_str[:500]}
                except Exception as e:
                    print(f"Key information extraction failed: {e}")
                
                # Final fallback: Return an error object with the raw text
                return {"error": "All JSON parsing strategies failed", "raw_text": json_str[:200] + "..."}     

            # Function to extract JSON data from image analysis text
            def extract_json_from_analysis(text):
                import re
                import json
                
                # Remove code fences from text
                text_clean = re.sub(r'```json?|```', '', text)
                
                # Manual extraction of balanced JSON blocks
                json_matches = []
                stack = []
                start_idx = None
                for idx, char in enumerate(text_clean):
                    if char == '{':
                        if not stack:
                            start_idx = idx
                        stack.append('{')
                    elif char == '}' and stack:
                        stack.pop()
                        if not stack and start_idx is not None:
                            json_matches.append(text_clean[start_idx:idx+1])
                            start_idx = None
                
                # Fallback to simple regex if no balanced matches found
                if not json_matches:
                    json_matches = re.findall(r'{[^{}]*}', text_clean, re.DOTALL)
                
                extracted_data = []
                
                for json_str in json_matches:
                    try:
                        # Use our multi-strategy parsing approach
                        json_data = parse_json_with_fallbacks(json_str)
                        
                        # For Performance Indicators table, ensure trend values are simplified
                        if isinstance(json_data, dict):
                            # Potentially, other tableType specific logic could go here in the future
                            pass # Placeholder if we need to re-introduce specific logic for other table types
                        
                        # Add successfully parsed data to the results
                        extracted_data.append(json_data)
                    except Exception as e:
                        print(f"Error processing JSON: {e}")
                        # Still try to salvage something by adding a debug entry
                        extracted_data.append({"error": str(e), "partial_content": json_str[:100] + "..."})
                
                return extracted_data
            
            # Process each image analysis to extract structured data
            structured_data = []
            for insight in image_analyses:
                json_data = extract_json_from_analysis(insight)
                if json_data:
                    structured_data.extend(json_data)
            
            # Store structured data in the state if available
            if structured_data:
                print(f"Extracted {len(structured_data)} structured data elements from image analysis")
                if not hasattr(state, 'structured_image_data'):
                    state.structured_image_data = []
                state.structured_image_data = structured_data
                
                # Add a note about structured data to the image analysis
                image_analyses.append("\n\nStructured data has been extracted from the image analysis for enhanced processing.")
            
            # Store image descriptions in the state
            state.image_descriptions = image_descriptions
            print(f"Stored {len(image_descriptions)} image descriptions")
            
            # Store image processing stats in state
            state.total_images_found = len(image_blobs)
            state.images_processed = image_count
            state.images_filtered_size = len([img for img in image_blobs if img not in filtered_images and (img in image_metadata and image_metadata[img].get("size_kb", 0) < MIN_IMAGE_SIZE_KB)])
            state.images_filtered_dimensions = len(image_blobs) - len(filtered_images) - state.images_filtered_size
            
            # Add token usage and image processing summary to the image analysis
            processing_summary = f"""
\n\n## Image Processing Summary
- Total Images Found: {state.total_images_found}
- Images Filtered (Too Small): {state.images_filtered_size}
- Images Filtered (Small Dimensions): {state.images_filtered_dimensions}
- Images Processed: {state.images_processed}
- Selection Criteria: Size threshold {MIN_IMAGE_SIZE_KB}KB, Dimension threshold {MIN_IMAGE_WIDTH}x{MIN_IMAGE_HEIGHT}px
"""
            
            token_usage_summary = f"""
## Token Usage Summary
- Total Input Tokens (Images + Text): {state.total_prompt_tokens:,}
- Total Output Tokens: {state.total_completion_tokens:,}
- Total Tokens: {state.total_tokens:,}
"""
            
            # Log the summaries
            print(processing_summary)
            print(token_usage_summary)
            
            # Combine all image analyses and add summaries
            if image_analyses:
                state.image_analysis = "\n\n".join(image_analyses) + processing_summary + token_usage_summary
            else:
                state.image_analysis = "No images could be analyzed." + processing_summary
            
            print(f"Completed image processing with {len(image_descriptions)} descriptions and {len(image_analyses)} analyses")
            
            return state
            
        except Exception as e:
            state.error = f"Error in image analysis: {str(e)}"
            print(state.error)
            return state
    
    async def download_content_step(self, state: WorkflowState) -> WorkflowState:
        """Step 1: Download markdown content from blob storage"""
        try:
            print(f"[STEP 1] Downloading content for {state.blob_name}")
            
            # Calculate the markdown file name
            base_name = os.path.splitext(state.blob_name)[0]
            markdown_file_name = f"{base_name}.md"
            
            # Download markdown content
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME,
                blob=markdown_file_name
            )
            
            if not blob_client.exists():
                state.error = f"Markdown file {markdown_file_name} not found. Document may not be processed yet."
                return state
            
            blob_data = blob_client.download_blob()
            state.markdown_content = blob_data.readall().decode('utf-8')
            
            print(f"Successfully downloaded {len(state.markdown_content)} characters of content")
            return state
            
        except Exception as e:
            state.error = f"Error downloading content: {str(e)}"
            print(state.error)
            return state
    
    def generate_summary_step(self, state: WorkflowState) -> WorkflowState:
        """Step 3: Generate comprehensive summary with integrated text and image content"""
        try:
            print("Generating comprehensive summary with integrated text and image content...")
            
            # Debug: log the model being used for summary
            print(f"Using summary model deployment: {self.summary_deployment_name}")
            
            # Start with integration instructions to ensure LLM compliance
            enhanced_content = "\n\nIMPORTANT INTEGRATION INSTRUCTIONS:\n"
            enhanced_content += "1. Create a comprehensive analysis that combines insights from BOTH the text content AND the visual elements described below.\n"
            enhanced_content += "2. For each finding, indicate whether it comes from textual content, visual elements, or both.\n"
            enhanced_content += "3. Pay special attention to performance metrics, trends, status indicators, and parameter values that appear in the images.\n"
            enhanced_content += "4. When metrics appear in both text and images, cross-reference them to provide a more complete picture.\n"
            enhanced_content += "5. Identify any discrepancies or complementary information between text and visual content.\n\n"
            
            # Add the original markdown content
            enhanced_content += "## DOCUMENT TEXT CONTENT:\n\n"
            enhanced_content += state.markdown_content
            
            # Add pure image descriptions to provide clear visual context
            if state.image_descriptions and len(state.image_descriptions) > 0:
                enhanced_content += "\n\n## PURE IMAGE DESCRIPTIONS:\n"
                enhanced_content += "_The following are objective descriptions of visual elements found in the report:_\n\n"
                
                for idx, img_desc in enumerate(state.image_descriptions, 1):
                    image_name = img_desc.get("name", f"Image {idx}")
                    description = img_desc.get("description", "No description available")
                    enhanced_content += f"### {image_name}\n{description}\n\n"
                
                enhanced_content += "\n_These descriptions provide visual context that may not be fully captured in the text content._\n\n"
            
            # Add structured data from images if available
            if state.structured_image_data and len(state.structured_image_data) > 0:
                enhanced_content += "\n\n## VISUAL ANALYSIS FROM EXTRACTED IMAGES:\n"
                enhanced_content += "_The following structured data, including tables with trend indicators (e.g., ⬆️, ⬇️, ➡️), was extracted from visual elements in the report:_\n\n"
                
                for data_item in state.structured_image_data:
                    # Check if it's a table and has the necessary components
                    if 'tableData' in data_item and \
                       isinstance(data_item.get('tableData'), dict) and \
                       'headers' in data_item['tableData'] and \
                       'rows' in data_item['tableData']:
                        
                        table_name = data_item.get('tableType', 'Extracted Table from Image')
                        enhanced_content += f"\n### {table_name}\n"
                        
                        # General note about potential trend value enhancement
                        enhanced_content += "_Note: Trend-like values (e.g., up, down, same, unknown) in the table may have been enhanced with visual indicators._\n\n"
                        
                        headers = data_item['tableData']['headers']
                        # Ensure headers are strings for join
                        str_headers = [str(h) for h in headers]
                        enhanced_content += "| " + " | ".join(str_headers) + " |\n"
                        enhanced_content += "| " + " | ".join(["-" * len(h) for h in str_headers]) + " |\n"
                        
                        for row in data_item['tableData']['rows']:
                            row_values = []
                            for value in row: # Assuming row is a list of values
                                cell_value = value 
                                if isinstance(cell_value, str):
                                    if cell_value.lower() == "up":
                                        cell_value = "⬆️ up"
                                    elif cell_value.lower() == "down":
                                        cell_value = "⬇️ down"
                                    elif cell_value.lower() == "same":
                                        cell_value = "➡️ same"
                                    elif cell_value.lower() == "unknown":
                                        cell_value = "❓ unknown"
                                row_values.append(str(cell_value)) # Ensure it's a string for join
                            enhanced_content += "| " + " | ".join(row_values) + " |\n"
                        enhanced_content += "\n"  # Add a newline after the table
            
            # We already added image descriptions above, so no need to add them again here

            # Add the technical image analysis
            if state.image_analysis and state.image_analysis != "No images were extracted from this document.":
                enhanced_content += f"\n\n## TECHNICAL ANALYSIS FROM EXTRACTED IMAGES:\n{state.image_analysis}\n\n"
            
            response = self.client.chat.completions.create(
                model=self.summary_deployment_name,
                messages=[
                    {"role": "system", "content": self.SUMMARY_PROMPT},
                    {"role": "user", "content": enhanced_content}
                ],
                max_tokens=16000,
                temperature=0.1
            )
            
            # Track token usage from summary generation
            if hasattr(response, 'usage'):
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens
                
                # Update state token counters
                state.total_prompt_tokens += prompt_tokens
                state.total_completion_tokens += completion_tokens
                state.total_tokens += total_tokens
                
                print(f"Summary generation token usage: {prompt_tokens:,} prompt + {completion_tokens:,} completion = {total_tokens:,} total tokens")
            
            state.summary_result = response.choices[0].message.content
            print(f"Generated summary: {len(state.summary_result)} characters")
            
            # Add final token usage summary to the end of the workflow
            print(f"\nFINAL TOKEN USAGE ACROSS ENTIRE WORKFLOW:\n- Total Input Tokens: {state.total_prompt_tokens:,}\n- Total Output Tokens: {state.total_completion_tokens:,}\n- Total Tokens: {state.total_tokens:,}\n")
            return state
        except Exception as e:
            state.error = str(e)
            return state
    
    async def save_results_step(self, state: WorkflowState) -> WorkflowState:
        """Step 5: Save all results to blob storage"""
        try:
            print(f"[STEP 5] Saving results for {state.blob_name}")
            base_name = os.path.splitext(state.blob_name)[0]
            
            # Save the summary markdown
            summary_blob_name = f"{base_name}_AI.md"
            
            # Upload the summary markdown
            await self.upload_to_blob(summary_blob_name, state.summary_result, "text/markdown")
            
            # Save the pure image descriptions as a separate JSON file
            if state.image_descriptions and len(state.image_descriptions) > 0:
                image_descriptions_blob_name = f"{base_name}_image_descriptions.json"
                image_descriptions_json = json.dumps(state.image_descriptions, indent=2)
                await self.upload_to_blob(image_descriptions_blob_name, image_descriptions_json, "application/json")
                print(f"Saved image descriptions to {image_descriptions_blob_name}")
                
                # Also save as a readable markdown file for easy viewing
                image_descriptions_md = f"# Image Descriptions from {state.blob_name}\n\n"
                for idx, img_desc in enumerate(state.image_descriptions, 1):
                    image_name = img_desc.get("name", f"Image {idx}")
                    description = img_desc.get("description", "No description available")
                    image_descriptions_md += f"## {image_name}\n{description}\n\n"
                
                image_descriptions_md_blob_name = f"{base_name}_image_descriptions.md"
                await self.upload_to_blob(image_descriptions_md_blob_name, image_descriptions_md, "text/markdown")
                print(f"Saved image descriptions markdown to {image_descriptions_md_blob_name}")
            
            # Save the technical image analysis as a separate file
            if state.image_analysis and state.image_analysis != "No images were extracted from this document.":
                image_analysis_blob_name = f"{base_name}_image_analysis.md"
                await self.upload_to_blob(image_analysis_blob_name, state.image_analysis, "text/markdown")
                print(f"Saved image analysis to {image_analysis_blob_name}")
            
            # Save structured image data if available
            if state.structured_image_data and len(state.structured_image_data) > 0:
                structured_data_blob_name = f"{base_name}_structured_image_data.json"
                structured_data_json = json.dumps(state.structured_image_data, indent=2)
                await self.upload_to_blob(structured_data_blob_name, structured_data_json, "application/json")
                print(f"Saved structured image data to {structured_data_blob_name}")
                
                # Also save specific table types as individual files for easier frontend access
                for data_item in state.structured_image_data:
                    if 'tableType' in data_item and data_item['tableType'] == 'PerformanceIndicators':
                        perf_indicators_blob_name = f"{base_name}_performance_indicators.json"
                        perf_indicators_json = json.dumps(data_item, indent=2)
                        await self.upload_to_blob(perf_indicators_blob_name, perf_indicators_json, "application/json")
                        print(f"Saved performance indicators data to {perf_indicators_blob_name}")
            
            return state
        except Exception as e:
            state.error = str(e)
            return state
    
    async def execute_workflow_async(self, blob_name: str) -> Dict[str, Any]:
        """Execute the complete workflow asynchronously"""
        try:
            print(f"Executing async workflow for {blob_name}")
            
            # Initialize workflow state
            state = WorkflowState(blob_name)
            
            # Step 1: Download markdown content from blob storage
            state = await self.download_content_step(state)
            if state.error:
                return {"success": False, "message": state.error, "original_file": blob_name}
                
            # Step 2: Detect and analyze images (if any)
            state = await self.detect_and_analyze_images_step(state)
            if state.error:
                return {"success": False, "message": state.error, "original_file": blob_name}
            
            # Step 3: Generate comprehensive summary with integrated text and image content
            state = self.generate_summary_step(state)
            if state.error:
                return {"success": False, "message": state.error, "original_file": blob_name}
            
            # Step 4: Save all results to blob storage
            state = await self.save_results_step(state)
            if state.error:
                return {"success": False, "message": state.error, "original_file": blob_name}
            
            return {
                "success": True,
                "message": "Workflow completed successfully",
                "original_file": state.blob_name,
                "summary_file": f"{os.path.splitext(state.blob_name)[0]}_AI.md",
                "summary_preview": state.summary_result[:500] + "..." if len(state.summary_result) > 500 else state.summary_result,
                "image_analysis_file": f"{os.path.splitext(state.blob_name)[0]}_image_analysis.md" if state.image_analysis else None,
                "token_usage": {
                    "prompt_tokens": state.total_prompt_tokens,
                    "completion_tokens": state.total_completion_tokens,
                    "total_tokens": state.total_tokens
                }
            }
            
        except Exception as e:
            import traceback; traceback.print_exc()
            error_message = f"Error in workflow execution: {str(e)}"
            print(error_message)
            return {"success": False, "message": error_message, "original_file": blob_name}
    
    def execute_workflow(self, blob_name: str) -> Dict[str, Any]:
        """Execute the complete workflow (synchronous wrapper for backward compatibility)"""
        try:
            print(f"Executing workflow for {blob_name}")
            import asyncio
            
            # We'll use this helper to run async steps in the sync context
            def run_async(coro):
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    # No event loop in this thread, create new one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                return loop.run_until_complete(coro)
            
            # Initialize workflow state
            state = WorkflowState(blob_name)
            
            # Step 1: Download markdown content from blob storage (async)
            state = run_async(self.download_content_step(state))
            if state.error:
                return {"success": False, "message": state.error, "original_file": blob_name}
                
            # Step 2: Detect and analyze images (if any) (async)
            state = run_async(self.detect_and_analyze_images_step(state))
            if state.error:
                return {"success": False, "message": state.error, "original_file": blob_name}
            
            # Step 3: Generate comprehensive summary with integrated text and image content
            state = self.generate_summary_step(state)
            if state.error:
                return {"success": False, "message": state.error, "original_file": blob_name}
            
            # Step 4: Save all results to blob storage (async)
            state = run_async(self.save_results_step(state))
            if state.error:
                return {"success": False, "message": state.error, "original_file": blob_name}
            
            # Return success response
            base_name = os.path.splitext(blob_name)[0]
            return {
                "success": True,
                "message": "Workflow completed successfully",
                "original_file": blob_name,
                "summary_file": f"{base_name}_AI.md",
                "summary_preview": state.summary_result[:500] + "..." if len(state.summary_result) > 500 else state.summary_result,
                "image_analysis_file": f"{base_name}_image_analysis.md" if state.image_analysis else None,
                "token_usage": {
                    "prompt_tokens": state.total_prompt_tokens,
                    "completion_tokens": state.total_completion_tokens,
                    "total_tokens": state.total_tokens
                }
            }
            
        except Exception as e:
            import traceback; traceback.print_exc()
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
    return await ewa_orchestrator.execute_workflow_async(blob_name)
