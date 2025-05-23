import os
import asyncio
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

# System prompt for deep dive analysis
SYSTEM_PROMPT = """You are an expert SAP Basis Architect tasked with analyzing an SAP Early Watch Alert report. Your goal is to study the report thoroughly and extract actionable insights, categorizing them based on their importance. Here's how you should proceed:

First, carefully read and analyze the following SAP Early Watch Alert report:

<sap_early_watch_report>
{{SAP_EARLY_WATCH_REPORT}}
</sap_early_watch_report>

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

---

## 📈 Summary of Key Metrics

**IMPORTANT: Include BOTH a structured JSON metrics object AND a standard markdown table**

### JSON Metrics Data (Do not modify this format)

```json
{
  "metrics": [
    {
      "name": "Avg. Availability per Week",
      "current": "100%",
      "target": "100%",
      "status": "success",
      "category": "Availability"
    },
    {
      "name": "Avg. Response Time in Dialog Task",
      "current": "663 ms",
      "target": "<1200 ms",
      "status": "success",
      "category": "Performance" 
    },
    {
      "name": "Max CPU Utilization on DB Server",
      "current": "75%",
      "target": "<90%",
      "status": "warning",
      "category": "Resource Usage"
    },
    {
      "name": "ABAP Dumps (weekly)",
      "current": "384",
      "target": "<30",
      "status": "critical",
      "category": "Errors"
    }
  ]
}
```

**Status values must be one of: "success", "warning", or "critical"**
**Category values should group related metrics (e.g., "Performance", "Security", "Availability", etc.)**

Additional guidelines:
- Focus on technical aspects related to SAP system performance, security, and stability.
- Use your expertise as an SAP Basis Architect to provide insights that may not be explicitly stated in the report but can be inferred from the data.
- If you encounter any ambiguous or unclear information in the report, mention it in your analysis and provide the best possible interpretation based on your expertise.
- Ensure that your recommendations are specific, actionable, and relevant to the SAP environment described in the report.

Remember to think critically and provide insights that would be valuable to an SAP team looking to improve their system's performance and stability.
"""

class AzureOpenAIService:
    def __init__(self):
        self.client = None
        self.blob_service_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Azure OpenAI and Blob Storage clients"""
        # Initialize Azure OpenAI client
        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
            raise ValueError("Azure OpenAI credentials not found. Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in your .env file.")
        
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION
        )
        
        # Initialize Blob Storage client
        if not AZURE_STORAGE_CONNECTION_STRING:
            raise ValueError("Azure Storage connection string not found. Please set AZURE_STORAGE_CONNECTION_STRING in your .env file.")
        
        self.blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    
    async def download_markdown_from_blob(self, blob_name: str) -> str:
        """Download markdown content from Azure Blob Storage"""
        try:
            # Construct the markdown file name (should already have .md extension)
            if not blob_name.endswith('.md'):
                md_blob_name = f"{os.path.splitext(blob_name)[0]}.md"
            else:
                md_blob_name = blob_name
            
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=md_blob_name
            )
            
            # Download the markdown content
            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode('utf-8')
            
            print(f"Successfully downloaded markdown content from {md_blob_name}")
            return content
            
        except Exception as e:
            print(f"Error downloading markdown from blob {blob_name}: {str(e)}")
            raise
    
    async def upload_analysis_to_blob(self, original_blob_name: str, analysis_content: str) -> str:
        """Upload AI analysis result to Azure Blob Storage with _AI suffix"""
        try:
            # Create the AI analysis file name
            base_name = os.path.splitext(original_blob_name)[0]
            ai_blob_name = f"{base_name}_AI.md"
            
            blob_client = self.blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, 
                blob=ai_blob_name
            )
            
            # Log analysis content size before upload
            content_size_kb = len(analysis_content) / 1024
            print(f"Uploading analysis content ({content_size_kb:.2f} KB) to blob storage")
            
            # Upload the analysis content
            blob_client.upload_blob(
                analysis_content.encode('utf-8'), 
                overwrite=True,
                content_type='text/markdown'
            )
            
            print(f"Successfully uploaded AI analysis to {ai_blob_name}")
            print(f"Analysis content start: {analysis_content[:100]}...")
            print(f"Analysis content end: ...{analysis_content[-100:]}")
            return ai_blob_name
            
        except Exception as e:
            print(f"Error uploading AI analysis for {original_blob_name}: {str(e)}")
            raise
    
    async def analyze_with_gpt4(self, markdown_content: str) -> dict:
        """Send markdown content to GPT-4 for analysis and extract structured metrics"""
        try:
            print("Sending content to Azure OpenAI for analysis...")
            
            # Calculate approximate token count of input for logging purposes
            # This is a rough estimation (1 token ≈ 4 chars for English text)
            input_token_estimate = (len(SYSTEM_PROMPT) + len(markdown_content)) // 4
            print(f"Estimated input tokens: {input_token_estimate}")
            
            # Increase max_tokens to handle larger responses (8000 is max for most deployments)
            response = self.client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Please analyze this EWA document:\n\n{markdown_content}"}
                ],
                temperature=0.1,
                max_tokens=16000,  # Increased from 4000 to 8000
                frequency_penalty=0,
                presence_penalty=0
            )
            
            analysis_result = response.choices[0].message.content
            
            # Log response information for debugging
            output_token_estimate = len(analysis_result) // 4
            print(f"Successfully received analysis from Azure OpenAI")
            print(f"Estimated response tokens: {output_token_estimate}")
            print(f"Response length (chars): {len(analysis_result)}")
            print(f"Response starts with: {analysis_result[:100]}...")
            
            # Check if the response might be truncated
            if output_token_estimate > 7500:  # Close to the 8000 limit
                print("WARNING: Response may be approaching token limit and could be truncated")
            
            # Extract JSON metrics data if present and remove it from the markdown content
            metrics_data = None
            cleaned_markdown = analysis_result
            import re
            import json
            
            # Look for JSON block between triple backticks with more flexible pattern
            json_patterns = [
                r'```json\s*({[\s\S]*?})\s*```',  # Standard markdown code block
                r'```\s*({\s*"metrics"[\s\S]*?})\s*```',  # Code block without language
                r'({\s*"metrics"\s*:\s*\[[\s\S]*?\]\s*})' # Raw JSON without code block
            ]
            
            # Patterns to match entire sections to remove
            section_patterns = [
                r'### JSON Metrics Data[\s\S]*?(?=###|$)',  # Match JSON section with heading
                r'## Summary of Key Metrics[\s\S]*?```json[\s\S]*?```[\s\S]*?(?=##|$)',  # Match entire metrics section
                r'### Markdown Table View[\s\S]*?(?=###|##|$)',  # Match markdown table view section
                r'\| Metric \| Current Value \| Target \| Status \|[\s\S]*?(?=\n\n|##|$)'  # Match markdown table directly
            ]
            
            # First extract the JSON data
            for pattern in json_patterns:
                json_match = re.search(pattern, analysis_result)
                if json_match:
                    try:
                        json_str = json_match.group(1).strip()
                        # Clean up the JSON string before parsing
                        json_str = re.sub(r'[\n\r\t]', '', json_str)
                        metrics_data = json.loads(json_str)
                        if 'metrics' in metrics_data and isinstance(metrics_data['metrics'], list):
                            print(f"Successfully extracted metrics data: {len(metrics_data.get('metrics', []))} metrics found")
                            break
                        else:
                            print("Found JSON but missing 'metrics' array, trying next pattern")
                            metrics_data = None
                    except json.JSONDecodeError as e:
                        print(f"Error parsing JSON metrics with pattern {pattern}: {str(e)}")
                        metrics_data = None
            
            # Then remove the JSON section and markdown tables from markdown content
            cleaned_markdown = analysis_result
            for pattern in section_patterns:
                section_match = re.search(pattern, cleaned_markdown)
                if section_match:
                    # Remove the matched section
                    cleaned_markdown = cleaned_markdown.replace(section_match.group(0), '')
                    print(f"Removed section matching pattern: {pattern[:30]}...")
            
            # Additional cleanup for markdown tables that might be in different formats
            table_start_pattern = r'\| [^|\n]+ \| [^|\n]+ \| [^|\n]+ \| [^|\n]+ \|'
            table_separator_pattern = r'\|[-:]+\|[-:]+\|[-:]+\|[-:]+\|'
            
            # Find and remove any remaining markdown tables
            if re.search(table_start_pattern, cleaned_markdown) and re.search(table_separator_pattern, cleaned_markdown):
                print("Found additional markdown table, removing it...")
                
                # Find the table boundaries
                table_lines = []
                in_table = False
                
                for line in cleaned_markdown.split('\n'):
                    if re.match(table_start_pattern, line) or re.match(table_separator_pattern, line):
                        in_table = True
                        table_lines.append(line)
                    elif in_table and line.strip().startswith('|') and line.strip().endswith('|'):
                        table_lines.append(line)
                    elif in_table:
                        in_table = False
                
                # Remove the table lines from markdown
                for line in table_lines:
                    cleaned_markdown = cleaned_markdown.replace(line, '')
                    
                print(f"Removed {len(table_lines)} lines of markdown table content")
                    
            # Clean up any duplicate newlines
            cleaned_markdown = re.sub(r'\n{3,}', '\n\n', cleaned_markdown)
            
            if metrics_data is None:
                print("No valid metrics JSON data found in the response")
                # Create a default metrics structure if none found
                metrics_data = {
                    "metrics": []
                }
            
            return {
                "markdown": cleaned_markdown,
                "metrics_data": metrics_data
            }
            
        except Exception as e:
            print(f"Error calling Azure OpenAI: {str(e)}")
            raise
    
    async def process_document_analysis(self, blob_name: str) -> dict:
        """
        Complete workflow: Download markdown, analyze with GPT-4, upload result
        
        Args:
            blob_name: Name of the original file (will look for corresponding .md file)
        
        Returns:
            dict: Result containing success status and file names
        """
        try:
            print(f"Starting AI analysis workflow for {blob_name}")
            
            # Step 1: Download markdown content from blob storage
            markdown_content = await self.download_markdown_from_blob(blob_name)
            
            if not markdown_content.strip():
                raise ValueError("Downloaded markdown content is empty")
            
            # Step 2: Analyze with GPT-4 - now returns a dict with markdown and metrics_data
            analysis_result = await self.analyze_with_gpt4(markdown_content)
            
            # Extract markdown content and metrics data
            markdown_analysis = analysis_result.get("markdown")
            metrics_data = analysis_result.get("metrics_data")
            
            if not markdown_analysis or not markdown_analysis.strip():
                raise ValueError("AI analysis result is empty")
            
            # Step 3: Upload analysis result back to blob storage
            ai_blob_name = await self.upload_analysis_to_blob(blob_name, markdown_analysis)
            
            # Step 4: Store metrics data separately in JSON format if available
            metrics_blob_name = None
            if metrics_data:
                # Create metrics file name with _metrics.json suffix
                base_name = os.path.splitext(blob_name)[0]
                metrics_blob_name = f"{base_name}_metrics.json"
                
                # Upload metrics as JSON
                import json
                blob_client = self.blob_service_client.get_blob_client(
                    container=AZURE_STORAGE_CONTAINER_NAME, 
                    blob=metrics_blob_name
                )
                
                blob_client.upload_blob(
                    json.dumps(metrics_data, indent=2).encode('utf-8'), 
                    overwrite=True,
                    content_type='application/json'
                )
                print(f"Successfully uploaded metrics data to {metrics_blob_name}")
            
            return {
                "success": True,
                "message": "AI analysis completed successfully",
                "original_file": blob_name,
                "analysis_file": ai_blob_name,
                "metrics_file": metrics_blob_name,
                "metrics_data": metrics_data,  # Include metrics data directly in response
                "analysis_preview": markdown_analysis[:500] + "..." if len(markdown_analysis) > 500 else markdown_analysis
            }
            
        except Exception as e:
            error_message = f"Error in AI analysis workflow: {str(e)}"
            print(error_message)
            return {
                "success": False,
                "error": True,
                "message": error_message,
                "original_file": blob_name
            }

# Global service instance
azure_openai_service = AzureOpenAIService()

async def analyze_document_with_ai(blob_name: str) -> dict:
    """
    Convenience function to analyze a document with AI
    
    Args:
        blob_name: Name of the file to analyze
    
    Returns:
        dict: Analysis result
    """
    return await azure_openai_service.process_document_analysis(blob_name)
