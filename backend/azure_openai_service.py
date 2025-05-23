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
SYSTEM_PROMPT = """You are an expert analyst specializing in Enterprise Workplace Analytics (EWA) reports. Your task is to provide a comprehensive deep dive analysis of the provided document.

Please analyze the document and provide:

1. **Executive Summary**: A high-level overview of the key findings and insights
2. **Key Metrics Analysis**: Detailed breakdown of important metrics and their implications
3. **Trends and Patterns**: Identification of significant trends, patterns, or anomalies
4. **Risk Assessment**: Potential risks or areas of concern identified in the data
5. **Recommendations**: Actionable recommendations based on the analysis
6. **Technical Insights**: Any technical observations or system-related findings
7. **Business Impact**: How these findings might impact business operations or decisions

Format your response in clear, professional markdown with appropriate headers, bullet points, and emphasis where needed. Be thorough but concise, focusing on actionable insights rather than just restating the data."""

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
            
            # Upload the analysis content
            blob_client.upload_blob(
                analysis_content.encode('utf-8'), 
                overwrite=True,
                content_type='text/markdown'
            )
            
            print(f"Successfully uploaded AI analysis to {ai_blob_name}")
            return ai_blob_name
            
        except Exception as e:
            print(f"Error uploading AI analysis for {original_blob_name}: {str(e)}")
            raise
    
    async def analyze_with_gpt4(self, markdown_content: str) -> str:
        """Send markdown content to GPT-4 for analysis"""
        try:
            print("Sending content to Azure OpenAI for analysis...")
            
            response = self.client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Please analyze this EWA document:\n\n{markdown_content}"}
                ],
                temperature=0.7,
                max_tokens=4000,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0
            )
            
            analysis_result = response.choices[0].message.content
            print("Successfully received analysis from Azure OpenAI")
            return analysis_result
            
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
            
            # Step 2: Analyze with GPT-4
            analysis_result = await self.analyze_with_gpt4(markdown_content)
            
            if not analysis_result.strip():
                raise ValueError("AI analysis result is empty")
            
            # Step 3: Upload analysis result back to blob storage
            ai_blob_name = await self.upload_analysis_to_blob(blob_name, analysis_result)
            
            return {
                "success": True,
                "message": "AI analysis completed successfully",
                "original_file": blob_name,
                "analysis_file": ai_blob_name,
                "analysis_preview": analysis_result[:500] + "..." if len(analysis_result) > 500 else analysis_result
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
