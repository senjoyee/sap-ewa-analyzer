"""
Azure OpenAI Service Module

This module provides services for analyzing SAP Early Watch Alert (EWA) reports
using Azure OpenAI's GPT models. It handles the complete workflow from retrieving
processed documents to generating AI-enhanced analysis.

Key Functionality:
- Connecting to Azure OpenAI service with proper authentication
- Sending processed EWA documents to GPT models for in-depth analysis
- Generating structured insights, recommendations, and metrics
- Managing the analysis workflow (download → analyze → upload results)
- Integration with Azure Blob Storage for document persistence

The analysis uses specialized system prompts designed for SAP EWA reports
to extract actionable insights organized by priority levels.
"""

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

def get_azure_openai_client():
    """Get Azure OpenAI client instance"""
    return AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )

# Note: This file contains legacy code that has been replaced by the workflow_orchestrator.py implementation.
# It is kept for reference purposes but is no longer actively used in the application.

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
            input_token_estimate = len(markdown_content) // 4
            print(f"Estimated input tokens: {input_token_estimate}")
            
            # Increase max_tokens to handle larger responses (8000 is max for most deployments)
            # Legacy implementation - this would use a system prompt
            # but has been replaced by the workflow_orchestrator.py implementation
            response = self.client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": "You are an expert SAP Basis Architect analyzing an SAP Early Watch Alert report."},
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
                r'({\s*"metrics"\s*:\s*\[[\s\S]*?\]\s*})',  # Raw JSON without code block
                r'```json\s*({\s*"parameters"[\s\S]*?})\s*```',  # Parameters JSON block
                r'```\s*({\s*"parameters"[\s\S]*?})\s*```',  # Parameters code block without language
                r'({\s*"parameters"\s*:\s*\[[\s\S]*?\]\s*})'  # Parameters JSON without code block
            ]
            
            # Patterns to match entire sections to remove
            section_patterns = [
                r'### JSON Metrics Data[\s\S]*?(?=###|$)',  # Match JSON section with heading
                r'## Summary of Key Metrics[\s\S]*?```json[\s\S]*?```[\s\S]*?(?=##|$)',  # Match entire metrics section
                r'### Markdown Table View[\s\S]*?(?=###|##|$)',  # Match markdown table view section
                r'\| Metric \| Current Value \| Target \| Status \|[\s\S]*?(?=\n\n|##|$)',  # Match markdown table directly
                r'### JSON Parameters Data[\s\S]*?(?=###|$)',  # Match JSON parameters section with heading
                r'## Recommended Parameters[\s\S]*?```json[\s\S]*?```[\s\S]*?(?=##|$)',  # Match entire parameters section
                r'\| Parameter \| Current Value \| Recommended \| Impact \|[\s\S]*?(?=\n\n|##|$)'  # Match parameters table directly
            ]
            
            # Extract metrics and parameters data separately
            metrics_data = {"metrics": []}
            parameters_data = {"parameters": []}
            
            # First look for metrics data
            for pattern in json_patterns:
                json_match = re.search(pattern, analysis_result)
                if json_match:
                    try:
                        json_str = json_match.group(1).strip()
                        # Clean up the JSON string before parsing
                        json_str = re.sub(r'[\n\r\t]', '', json_str)
                        data = json.loads(json_str)
                        
                        # Check if we found metrics data
                        if 'metrics' in data and isinstance(data['metrics'], list):
                            metrics_data = data
                            print(f"Successfully extracted metrics data: {len(data.get('metrics', []))} metrics found")
                            break
                    except json.JSONDecodeError as e:
                        print(f"Error parsing metrics JSON with pattern {pattern}: {str(e)}")
                        continue
            
            # Then look for parameters data
            for pattern in json_patterns:
                json_match = re.search(pattern, analysis_result)
                if json_match:
                    try:
                        json_str = json_match.group(1).strip()
                        # Clean up the JSON string before parsing
                        json_str = re.sub(r'[\n\r\t]', '', json_str)
                        data = json.loads(json_str)
                        
                        # Check if we found parameters data
                        if 'parameters' in data and isinstance(data['parameters'], list):
                            parameters_data = data
                            print(f"Successfully extracted parameters data: {len(data.get('parameters', []))} parameters found")
                            break
                    except json.JSONDecodeError as e:
                        print(f"Error parsing parameters JSON with pattern {pattern}: {str(e)}")
                        continue
            
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
            
            if not metrics_data["metrics"]:
                print("No valid metrics data found in the response")
                # Create a default metrics structure
                metrics_data = {"metrics": []}
                
            if not parameters_data["parameters"]:
                print("No valid parameters data found in the response")
                # Create a default parameters structure
                parameters_data = {"parameters": []}
            
            return {
                "markdown": cleaned_markdown,
                "metrics_data": metrics_data,
                "parameters_data": parameters_data
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
            
            # Extract markdown content, metrics data, and parameters data
            markdown_analysis = analysis_result.get("markdown")
            metrics_data = analysis_result.get("metrics_data")
            parameters_data = analysis_result.get("parameters_data")
            
            if not markdown_analysis or not markdown_analysis.strip():
                raise ValueError("AI analysis result is empty")
            
            # Step 3: Upload analysis result back to blob storage
            ai_blob_name = await self.upload_analysis_to_blob(blob_name, markdown_analysis)
            
            # Step 4: Store metrics data separately in JSON format if available
            metrics_blob_name = None
            if metrics_data and metrics_data.get("metrics"):
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
            
            # Step 5: Store parameters data separately in JSON format if available
            parameters_blob_name = None
            if parameters_data and parameters_data.get("parameters"):
                # Create parameters file name with _parameters.json suffix
                base_name = os.path.splitext(blob_name)[0]
                parameters_blob_name = f"{base_name}_parameters.json"
                
                # Upload parameters as JSON
                import json
                blob_client = self.blob_service_client.get_blob_client(
                    container=AZURE_STORAGE_CONTAINER_NAME, 
                    blob=parameters_blob_name
                )
                
                blob_client.upload_blob(
                    json.dumps(parameters_data, indent=2).encode('utf-8'), 
                    overwrite=True,
                    content_type='application/json'
                )
                print(f"Successfully uploaded parameters data to {parameters_blob_name}")
            
            return {
                "success": True,
                "message": "AI analysis completed successfully",
                "original_file": blob_name,
                "analysis_file": ai_blob_name,
                "metrics_file": metrics_blob_name,
                "parameters_file": parameters_blob_name,
                "metrics_data": metrics_data,  # Include metrics data directly in response
                "parameters_data": parameters_data,  # Include parameters data directly in response
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
