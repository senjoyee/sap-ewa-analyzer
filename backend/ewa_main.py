"""
SAP EWA Analyzer API Server

This is the main FastAPI application that serves as the backend for the SAP Early Watch Alert (EWA)
Analyzer system. It provides a comprehensive set of REST APIs for document processing,
AI analysis, and interactive chat functionality.

Key Functionality:
- File upload and management with Azure Blob Storage
- Document processing (converting various formats to markdown)
- AI analysis of SAP EWA reports using Azure OpenAI
- Document chat capabilities with context-aware responses
- Status tracking for all asynchronous operations

The API is designed to be consumed by a React frontend, with endpoints organized by function
(file management, document processing, AI analysis, and chat).
"""

import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from pydantic import BaseModel
from converters.document_converter import convert_document_to_markdown, get_conversion_status
from workflow_orchestrator import ewa_orchestrator
import uvicorn # For running the app
import json
import markdown2
from weasyprint import HTML

# Load environment variables from .env file
load_dotenv()

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

if not AZURE_STORAGE_CONNECTION_STRING:
    raise ValueError("AZURE_STORAGE_CONNECTION_STRING not found in environment variables. Please set it in your .env file.")
if not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError("AZURE_STORAGE_CONTAINER_NAME not found in environment variables. Please set it in your .env file.")

app = FastAPI()

# ---------------------------------------------------------------------------
# Register modular routers
# ---------------------------------------------------------------------------
from routers.storage_router import router as storage_router
app.include_router(storage_router)

# CORS Configuration
origins = [
    "http://localhost:3000",  # Allow your React frontend
    "http://127.0.0.1:3000",  # Alternative localhost
    "*",                      # Allow all origins for testing
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Allow all origins for troubleshooting
    allow_credentials=True,
    allow_methods=["*"],      # Allows all methods
    allow_headers=["*"],      # Allows all headers
)

# Initialize BlobServiceClient
try:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
except Exception as e:
    print(f"Error initializing BlobServiceClient: {e}")
    # Depending on your error handling strategy, you might raise an exception or exit
    # For now, we'll let it proceed but uploads will fail.
    blob_service_client = None


# @app.post("/api/upload")  # migrated to storage_router
async def upload_file(file: UploadFile = File(...), customer_name: str = Form(...)):
    """
    Upload a document file to Azure Blob Storage.
    
    This endpoint accepts file uploads (PDF, DOCX, DOC) and stores them in Azure Blob Storage
    with customer metadata. The uploaded file is later processed by the document analysis pipeline.
    
    Parameters:
    - file: The document file to upload (multipart/form-data)
    - customer_name: Customer identifier associated with this document
    
    Returns:
    - JSON response with file details and upload confirmation
    
    Raises:
    - 400 Bad Request: If no file is provided
    - 500 Internal Server Error: If Azure Blob Storage is not properly configured
    """
    
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized. Check server logs and .env configuration.")
    if not file:
        raise HTTPException(status_code=400, detail="No file sent.")

    try:
        # Create a unique blob name if needed, or use file.filename
        # For simplicity, using the original filename. BEWARE: this can overwrite existing files.
        # In a production system, you'd want to generate unique names.
        blob_name = file.filename 
        blob_client = blob_service_client.get_blob_client(container=AZURE_STORAGE_CONTAINER_NAME, blob=blob_name)

        print(f"Uploading {file.filename} to Azure Blob Storage in container {AZURE_STORAGE_CONTAINER_NAME} as blob {blob_name}...")

        # Upload the file
        # For large files, consider using file.file (a SpooledTemporaryFile) and streaming
        contents = await file.read() # Reads the entire file into memory
        
        # Create metadata dictionary with customer name
        metadata = {
            "customer_name": customer_name
        }
        
        # Upload the file with metadata
        blob_client.upload_blob(
            contents, 
            overwrite=True,  # Set overwrite=True to replace if exists
            metadata=metadata  # Include the metadata
        )

        print(f"Successfully uploaded {file.filename} to {blob_name} with customer: {customer_name}.")
        return {
            "filename": file.filename, 
            "customer_name": customer_name,
            "message": "File uploaded successfully to Azure Blob Storage."
        }

    except Exception as e:
        print(f"Error uploading file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not upload file: {str(e)}")


# @app.get("/api/files")  # migrated to storage_router
async def list_files():
    """
    List all files stored in Azure Blob Storage with their processing status.
    
    This endpoint retrieves a list of all files in the storage container along with metadata
    about their processing status. It detects whether files have been processed by Document Intelligence
    or analyzed by AI, and includes this information in the response.
    
    Returns:
    - JSON array of file objects, each containing:
      * id: Unique identifier for the file
      * name: Original filename
      * uploadDate: When the file was uploaded
      * size: File size in bytes
      * type: File type/extension
      * customerName: Associated customer name from metadata
      * processed: Boolean indicating if the file has been processed
      * ai_analyzed: Boolean indicating if AI analysis has been performed
    
    Raises:
    - 500 Internal Server Error: If Azure Blob Storage is not properly configured
    """
    
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")
    
    try:
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
        blob_list = list(container_client.list_blobs())  # Convert to list to iterate multiple times
        
        print(f"Found {len(blob_list)} total blobs in container")
        
        # First, identify all .json and .md files to detect processed files
        json_files = {}
        md_files = {}
        ai_analyzed_files = {}  # Track files that have been AI-analyzed
        
        for blob in blob_list:
            name = blob.name.lower()
            if name.endswith('.json'):
                # Store the base name (without extension) as key
                base_name = os.path.splitext(blob.name)[0]
                json_files[base_name] = True
                print(f"Found JSON file: {blob.name}, base name: {base_name}")
                
                # Check if this is an AI analysis JSON file
                if base_name.endswith('_AI'):
                    # Get the original file name by removing _AI suffix
                    original_base_name = base_name[:-3]  # Remove _AI
                    ai_analyzed_files[original_base_name] = True
                    print(f"Found AI analysis JSON file for: {original_base_name}")
                    
            elif name.endswith('.md'):
                # Store the base name (without extension) as key
                base_name = os.path.splitext(blob.name)[0]
                md_files[base_name] = True
                print(f"Found MD file: {blob.name}, base name: {base_name}")
                
                # Check if this is an AI analysis markdown file
                if base_name.endswith('_AI'):
                    # Get the original file name by removing _AI suffix
                    original_base_name = base_name[:-3]  # Remove _AI
                    ai_analyzed_files[original_base_name] = True
                    print(f"Found AI analysis markdown file for: {original_base_name}")
        
        # Now process all files, marking those that have been processed
        # but excluding .json and .md files from the final list
        files = []
        for blob in blob_list:
            # Get the blob name and check if it's a file type we want to display
            name = blob.name.lower()
            
            # Skip .json and .md files in the main list
            if name.endswith('.json') or name.endswith('.md'):
                print(f"Skipping file in list: {blob.name}")
                continue
                
            # Get the blob client to access properties and metadata
            blob_client = container_client.get_blob_client(blob.name)
            properties = blob_client.get_blob_properties()
            
            # Extract metadata (including customer_name)
            metadata = properties.metadata
            customer_name = metadata.get('customer_name', 'Unknown') if metadata else 'Unknown'
            report_date = metadata.get('report_date') if metadata else None
            
            # Check if this file has been processed (has corresponding .json or .md file)
            base_name = os.path.splitext(blob.name)[0]
            
            # Debug
            print(f"Checking file: {blob.name}, base name: {base_name}")
            print(f"JSON files: {list(json_files.keys())}")
            print(f"MD files: {list(md_files.keys())}")
            
            # A file is processed if there's a .json or .md file with the same base name
            is_processed = base_name in json_files or base_name in md_files
            # Check if this file has been AI-analyzed
            is_ai_analyzed = base_name in ai_analyzed_files
            print(f"File {blob.name} processed status: {is_processed}, AI analyzed: {is_ai_analyzed}")
            
            files.append({
                "name": blob.name, 
                "last_modified": blob.last_modified, 
                "size": blob.size,
                "report_date": report_date,
                "customer_name": customer_name,
                "processed": is_processed,
                "ai_analyzed": is_ai_analyzed
            })
        
        print(f"Returning {len(files)} files in the list")
        return files
    except Exception as e:
        print(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=f"Could not list files: {str(e)}")


# Model for requests that only need a blob_name
class BlobNameRequest(BaseModel):
    blob_name: str

@app.post("/api/analyze")
async def analyze_document(request: BlobNameRequest):
    """
    Process a document using Azure Document Intelligence.
    
    This endpoint triggers the document processing pipeline which converts the document
    (PDF, DOCX, DOC) to markdown format for further analysis. The processing is performed
    asynchronously, and the status can be checked using the /api/status/{blob_name} endpoint.
    
    Parameters:
    - request: An AnalyzeDocumentRequest object containing:
      * blob_name: The name of the file in Azure Blob Storage to process
    
    Returns:
    - JSON response with processing status and job information
    
    Raises:
    - 404 Not Found: If the specified file doesn't exist
    - 500 Internal Server Error: If processing fails for any reason
    """
    try:
        # Call the unified document converter function
        result = convert_document_to_markdown(request.blob_name)
        
        if result.get("error"):
            print(f"Error converting document: {result.get('message')}")
            raise HTTPException(status_code=500, detail=result.get('message'))
        
        return result
    except Exception as e:
        print(f"Error in analyze_document endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error converting document: {str(e)}")


@app.get("/api/analysis-status/{blob_name}")
async def get_document_analysis_status(blob_name: str):
    """
    Get the status of a document conversion job.
    
    This endpoint retrieves the current status of an asynchronous document processing job.
    It provides information about the progress of converting a document to markdown format.
    
    Parameters:
    - blob_name: The name of the file in Azure Blob Storage being processed
    
    Returns:
    - JSON object with status information including:
      * status: Current status ("pending", "processing", "completed", "error")
      * progress: Percentage of completion (0-100)
      * message: Human-readable status message
      * output_file: Name of the output file when processing is complete
      * start_time: When processing started
      * end_time: When processing completed (if finished)
    
    Raises:
    - 404 Not Found: If the specified file or job doesn't exist
    - 500 Internal Server Error: If retrieving status fails
    """
    try:
        status = get_conversion_status(blob_name)
        
        if status.get("error"):
            raise HTTPException(status_code=404, detail=status.get("message"))
        
        return status
    except Exception as e:
        print(f"Error in get_document_analysis_status endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting conversion status: {str(e)}")


@app.post("/api/process-and-analyze")
async def process_and_analyze_document_endpoint(request: BlobNameRequest):
    """
    Process a document to markdown and then perform AI analysis in a single combined workflow.
    
    This endpoint triggers a sequential operation:
    1. Converts the specified document (PDF, DOCX, DOC) to markdown format.
    2. If conversion is successful, performs AI analysis using the new agentic workflow with structured JSON schema validation.
    
    The entire operation is blocking from the client's perspective until both steps are complete
    or an error occurs. The AI analysis creates both human-readable markdown and machine-readable JSON output.
    
    Parameters:
    - request: A ProcessAndAnalyzeRequest object containing:
      * blob_name: The name of the original file in Azure Blob Storage to process and analyze.
    
    Returns:
    - JSON response with the overall status, including success/failure, messages, and 
      references to output files (e.g., AI analysis markdown and JSON files).
    
    Raises:
    - 404 Not Found: If the specified file doesn't exist at the start of conversion.
    - 500 Internal Server Error: If any part of the combined workflow fails.
    """
    if not blob_service_client: # Ensure blob service is available
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")

    try:
        # The ewa_orchestrator instance is globally available in workflow_orchestrator.py
        # and process_and_analyze_ewa uses the new agentic workflow
        from workflow_orchestrator import ewa_orchestrator # Ensure direct access if not already structured
        
        result = await ewa_orchestrator.process_and_analyze_ewa(request.blob_name)
        
        if not result.get("success", False):
            # If the orchestrator indicates failure, return appropriate HTTP error
            # The orchestrator should provide a 'message' in its result
            status_code = result.get("status_code", 500) # Allow orchestrator to suggest status code
            raise HTTPException(status_code=status_code, detail=result.get('message', 'Combined processing and analysis failed.'))
        
        return result # Return the success response from the orchestrator (includes JSON file info)
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly (e.g., from the check above or if orchestrator raises one)
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors
        print(f"Error in /api/process-and-analyze endpoint for {request.blob_name}: {str(e)}")
        # Consider logging the full traceback here: import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during combined processing and analysis: {str(e)}")


@app.post("/api/analyze-ai")
async def analyze_document_with_ai_endpoint(request: BlobNameRequest):
    """
    Analyze a processed document using Azure OpenAI GPT-4.1 models with structured JSON output.
    
    This endpoint takes a previously processed document (in markdown format) and performs
    AI analysis using the new agentic workflow. The analysis includes generating an executive summary
    with structured JSON schema validation and creates both markdown and JSON output files.
    
    Parameters:
    - request: An AIAnalyzeRequest object containing:
      * blob_name: The name of the processed markdown file in Azure Blob Storage to analyze
    
    Returns:
    - JSON response with analysis status and information about the generated files
    
    Raises:
    - 404 Not Found: If the specified markdown file doesn't exist
    - 500 Internal Server Error: If analysis fails for any reason
    """
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")
    
    # Extract blob name from request
    blob_name = request.blob_name
    
    # Construct the markdown file name
    base_name, extension = os.path.splitext(blob_name)
    markdown_file = blob_name
    
    # If the extension is not .md, assume we're looking for a processed markdown file
    if extension.lower() != ".md":
        markdown_file = f"{base_name}.md"
    
    # Check if the markdown file exists
    container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
    
    try:
        # Check if blob exists
        blob_client = container_client.get_blob_client(markdown_file)
        blob_properties = blob_client.get_blob_properties()
        print(f"Found markdown file {markdown_file} for analysis.")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Markdown file {markdown_file} not found. Please process the document first.")
    
    try:
        # Execute the new agentic AI analysis workflow
        result = await ewa_orchestrator.execute_workflow(markdown_file)
        
        # Check if analysis was successful
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=f"Analysis failed: {result.get('message', 'Unknown error')}")
        
        # Return the analysis result with new JSON file information
        return {
            "success": True,
            "message": "Analysis completed successfully with structured JSON output",
            "original_file": blob_name,
            "analysis_file": result.get("summary_file"),
            "analysis_json_file": result.get("summary_json_file"),
            "preview": result.get("summary_preview", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/reprocess-ai")
async def reprocess_document_with_ai(request: BlobNameRequest):
    """
    Reprocess a document with AI by deleting existing analysis files and running analysis again.
    
    This endpoint takes a previously analyzed document and:
    1. Deletes the existing AI analysis files (_AI.md and _AI.json)
    2. Runs the AI analysis again using the new agentic workflow to generate fresh results
    
    Parameters:
    - request: An AIReprocessRequest object containing:
      * blob_name: The name of the file in Azure Blob Storage to reprocess
    
    Returns:
    - JSON response with reprocessing status and information about the generated files
    
    Raises:
    - 404 Not Found: If the specified file doesn't exist
    - 500 Internal Server Error: If reprocessing fails for any reason
    """
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")
    
    try:
        # Extract blob name from request
        blob_name = request.blob_name
        print(f"Reprocessing AI analysis for {blob_name}")
        
        # Check if the container exists
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
        
        # Get the base name without extension
        base_name = os.path.splitext(blob_name)[0]
        ai_md_file = f"{base_name}_AI.md"
        ai_json_file = f"{base_name}_AI.json"
        
        # Track deleted files
        deleted_files = []
        
        # Check if AI files exist
        blobs_list = container_client.list_blobs(name_starts_with=base_name)
        
        # Collect all file names
        existing_files = [blob.name for blob in blobs_list]
        
        # Check for and delete AI markdown file
        if ai_md_file in existing_files:
            print(f"Found existing AI analysis file: {ai_md_file}")
            try:
                blob_client = container_client.get_blob_client(ai_md_file)
                blob_client.delete_blob()
                deleted_files.append(ai_md_file)
                print(f"Deleted existing AI analysis file: {ai_md_file}")
            except Exception as delete_error:
                print(f"Error deleting AI file {ai_md_file}: {str(delete_error)}")
        
        # Check for and delete AI JSON file
        if ai_json_file in existing_files:
            print(f"Found existing AI JSON file: {ai_json_file}")
            try:
                blob_client = container_client.get_blob_client(ai_json_file)
                blob_client.delete_blob()
                deleted_files.append(ai_json_file)
                print(f"Deleted existing AI JSON file: {ai_json_file}")
            except Exception as delete_error:
                print(f"Error deleting AI JSON file {ai_json_file}: {str(delete_error)}")
        
        # Run the AI analysis again using the new agentic workflow
        result = await ewa_orchestrator.execute_workflow(blob_name)
        
        if result.get("error"):
            print(f"Error in AI reprocessing: {result.get('message')}")
            raise HTTPException(status_code=500, detail=result.get('message'))
        
        # Log success
        print(f"AI reprocessing completed successfully for {blob_name}")
        return {
            "message": "Reprocessing completed successfully with structured JSON output",
            "deleted_files": deleted_files,
            "analysis_file": result.get("summary_file"),
            "analysis_json_file": result.get("summary_json_file"),
            "result": result
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        error_message = f"Error in AI reprocessing endpoint for {request.blob_name}: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)

# @app.get("/api/download/{blob_name}")  # migrated to storage_router
async def download_file(blob_name: str):
    """
    Download a file from Azure Blob Storage.
    
    This endpoint retrieves a file from Azure Blob Storage and returns it as a downloadable response
    with the appropriate content type. It supports various file types including PDF, DOCX, markdown, 
    and JSON files.
    
    Parameters:
    - blob_name: The name of the file in Azure Blob Storage to download
    
    Returns:
    - File response with appropriate content type and filename
    - For markdown files: text/markdown content type
    - For JSON files: application/json content type
    - For other files: application/octet-stream or the detected MIME type
    
    Raises:
    - 404 Not Found: If the specified file doesn't exist
    - 500 Internal Server Error: If file retrieval fails
    """
    try:
        if not blob_service_client:
            raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized")
        
        # Get blob client
        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, 
            blob=blob_name
        )
        
        # Check if blob exists
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail=f"File {blob_name} not found")
        
        # Download blob content
        blob_data = blob_client.download_blob()
        content = blob_data.readall()
        
        # Determine content type based on file extension
        if blob_name.endswith('.md'):
            content_type = "text/markdown"
        elif blob_name.endswith('.json'):
            content_type = "application/json"
        elif blob_name.endswith('.pdf'):
            content_type = "application/pdf"
        else:
            content_type = "application/octet-stream"
        
        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f"inline; filename={blob_name}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Error downloading file {blob_name}: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)


# Endpoint: Export Markdown to PDF
@app.get("/api/export-pdf")
async def export_markdown_to_pdf(blob_name: str):
    """
    Convert a Markdown blob stored in Azure Blob Storage to a high-quality PDF using WeasyPrint.

    Parameters:
    - blob_name: The name of the **.md** file in Azure Blob Storage.

    Returns:
    - PDF file as `application/pdf` response.
    """
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")

    if not blob_name.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="blob_name must point to a .md file.")

    try:
        blob_client = blob_service_client.get_blob_client(container=AZURE_STORAGE_CONTAINER_NAME, blob=blob_name)
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail=f"Markdown file {blob_name} not found in storage")

        md_bytes = blob_client.download_blob().readall()
        md_text = md_bytes.decode("utf-8", errors="ignore")

        # Convert Markdown to HTML with extras for tables & code blocks
        body_html = markdown2.markdown(md_text, extras=["tables", "fenced-code-blocks", "footnotes"])

        # Basic optional print stylesheet
        styles = '''
            @page { size: A4 landscape; margin: 20mm; }
            body { font-family: "Helvetica", sans-serif; color: #000; }
            code, pre { background: #f5f5f5; font-family: "Courier New", monospace; }
            pre { padding: 8px; overflow-x: auto; }
            table { border-collapse: collapse; width: 100%; table-layout: fixed; margin-bottom: 1em; }
            th { 
                border: 1px solid #666; 
                padding: 8px; 
                background-color: #f2f2f2; 
                text-align: center; 
                font-weight: bold;
            }
            td { 
                border: 1px solid #ddd; 
                padding: 8px; 
                word-break: break-word; 
                overflow-wrap: break-word; 
                vertical-align: top;
            }
        '''
        full_html = f"<html><head><meta charset='utf-8'><style>{styles}</style></head><body>{body_html}</body></html>"

        pdf_bytes = HTML(string=full_html, base_url=".").write_pdf()

        pdf_filename = os.path.splitext(blob_name)[0] + ".pdf"
        return Response(content=pdf_bytes,
                        media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=\"{pdf_filename}\""})

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error exporting markdown to PDF for {blob_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting markdown to PDF: {str(e)}")

# Model for chat request
class ChatRequest(BaseModel):
    message: str
    fileName: str
    documentContent: str
    fileOrigin: str = ''
    contentLength: int = 0
    chatHistory: list = []


@app.post("/api/chat")
async def chat_with_document(request: ChatRequest):
    """
    Chat with a document using Azure OpenAI GPT-4.
    
    This endpoint enables interactive Q&A with SAP EWA reports by using the document content
    as context for answering user questions. It leverages Azure OpenAI's GPT-4o models
    to provide contextually relevant responses based on the specific document content.
    
    The endpoint maintains conversation history to enable follow-up questions and
    references to previous parts of the conversation.
    
    Parameters:
    - request: A ChatRequest object containing:
      * message: The user's question or message
      * fileName: Name of the document being queried
      * documentContent: The full text content of the document (original .md file preferred)
      * fileOrigin: Source of the document content (optional)
      * contentLength: Length of the document content (optional)
      * chatHistory: Previous conversation messages (optional)
    
    Returns:
    - JSON response containing:
      * response: The AI's answer to the question
      * document_reference: References to specific parts of the document (if applicable)
      * message_id: Unique identifier for this message
      * updated_history: Updated conversation history including this exchange
    
    Raises:
    - 400 Bad Request: If required parameters are missing or invalid
    - 500 Internal Server Error: If chat processing fails
    """
    try:
        # Validate environment variables
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")
        
        if not api_key or not azure_endpoint:
            raise ValueError("Missing required environment variables: AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT")
        
        print(f"Using Azure OpenAI model: {model_name}")
        print(f"API version: {api_version}")
        print(f"Endpoint: {azure_endpoint[:20]}...")
        
        from openai import AzureOpenAI
        
        # Get Azure OpenAI client
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint
        )
        
        # Limit document content length to avoid token limits
        doc_content = request.documentContent
        
        # Debug document content in detail
        print(f"Document content length: {len(doc_content)} characters")
        if len(doc_content) < 100:
            print(f"WARNING: Very short document content: '{doc_content}'")
            # Try to add a default placeholder for debugging
            doc_content = f"The document appears to be too short or empty. Original content: '{doc_content}'"
        elif not doc_content or doc_content.strip() == '':
            print("WARNING: Empty document content!")
            doc_content = "No document content was provided. Please ensure the document was properly processed."
        else:
            # Print first and last 100 characters to see content structure
            print(f"Content STARTS with: '{doc_content[:100].replace('\n', '\\n')}'")
            print(f"Content ENDS with: '{doc_content[-100:].replace('\n', '\\n')}'")
            
            # Check for HTML content
            if '<html' in doc_content.lower() or '</html>' in doc_content.lower():
                print("WARNING: Document appears to be HTML rather than processed markdown!")
            
            # Check for meaningful content markers
            if 'SAP' in doc_content or 'EWA' in doc_content or 'Early Watch' in doc_content:
                print("GOOD: Document contains SAP-related content markers")
            else:
                print("WARNING: Document doesn't contain expected SAP content markers!")
        
        # We'll avoid truncating the document content to preserve all information
        print(f"Using full document content of {len(doc_content)} characters")
        
        # Build conversation context with document content
        system_prompt = f"""You are an expert SAP Basis Architect specialized in analyzing SAP Early Watch Alert (EWA) reports. 
        
You have access to the following SAP EWA report document:

DOCUMENT: {request.fileName}
CONTENT:
{doc_content}

IMPORTANT INSTRUCTIONS:
1. This is an SAP Early Watch Alert (EWA) report which contains system performance metrics, issues, warnings, and recommendations.
2. The report typically covers areas like database statistics, memory usage, backup frequency, system availability, and performance parameters.
3. When answering questions, focus on extracting SPECIFIC INFORMATION from the document, even if it's just a brief mention.
4. If information is present but brief, explain it and note that limited details are available.
5. Be especially attentive to technical metrics, parameter recommendations, and critical warnings in the report.
6. Quote specific sections and values from the report whenever possible.
7. If you truly cannot find ANY mention of a topic, only then state that it's not in the document.

DIRECTING USERS TO SPECIALIZED SECTIONS:
1. This application has DEDICATED SECTIONS for Key Metrics and Parameters that provide more detailed and structured information.
2. When users ask about specific metrics (KPIs, performance indicators, thresholds), give a brief summary, excluding any specific values, explain that the information is available in the "Key Metrics" section, and then EXPLICITLY direct them to the "Key Metrics" section with text like: "For more detailed metrics information with current values and status indicators, please refer to the Key Metrics section."
3. When users ask about parameters or configuration recommendations, provide a brief overview, excluding any specific values, explain that the information is available in the "Parameters" section, and then EXPLICITLY direct them to the "Parameters" section with text like: "For complete parameter recommendations with current and suggested values, please refer to the Parameters section."
4. These specialized sections provide interactive, structured data that's easier to navigate than the text summary.

Keep your responses informative and technically precise, as you're assisting an SAP administrator. Use markdown formatting for better readability."""
        
        # Build message history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history (limited to last 10 messages to avoid token limits)
        recent_history = request.chatHistory[-10:] if len(request.chatHistory) > 10 else request.chatHistory
        for msg in recent_history:
            role = "user" if msg.get("isUser") else "assistant"
            messages.append({"role": role, "content": msg.get("text", "")})
        
        # Add current message
        messages.append({"role": "user", "content": request.message})
        
        # Print request information for debugging
        print(f"Chat request for document: {request.fileName}")
        print(f"Message: {request.message[:50]}...")
        print(f"History length: {len(request.chatHistory)}")
        
        try:
            # Get response from Azure OpenAI
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=2000,       # Increased token limit for more detailed responses
                temperature=0.2,       # Lower temperature for more focused answers
                top_p=0.95,           # Slightly constrained sampling for more accurate responses
                presence_penalty=0.0,  # No penalty for repeating topics
                frequency_penalty=0.0  # No penalty for repeating specific tokens
            )
            
            ai_response = response.choices[0].message.content
            print(f"Got response of length: {len(ai_response)}")
            return {"response": ai_response}
            
        except Exception as api_error:
            print(f"API ERROR: {repr(api_error)}")
            # Check for common OpenAI errors
            error_str = str(api_error).lower()
            error_msg = f"API ERROR: {str(api_error)}"
            
            if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
                error_msg = f"Model '{model_name}' not found. Please check your AZURE_OPENAI_DEPLOYMENT_NAME setting in the .env file."
            elif "authenticate" in error_str or "key" in error_str or "cred" in error_str:
                error_msg = "Authentication error. Please check your Azure OpenAI API key and endpoint."
            elif "rate limit" in error_str or "too many" in error_str:
                error_msg = "Rate limit exceeded. Please try again in a moment."
                
            print(f"Returning error message to client: {error_msg}")
            return {"response": f"Error: {error_msg}", "error": True}
        
    except Exception as e:
        error_message = f"Error in chat endpoint: {str(e)}"
        print(f"DETAILED ERROR: {repr(e)}")
        import traceback
        traceback_str = traceback.format_exc()
        print(f"TRACEBACK: {traceback_str}")
        
        # Return the error message for debugging
        return {"response": f"Error: {error_message}", "error": True}


# Simple test endpoint to check server availability
@app.get("/api/ping")
async def ping():
    """
    Health check endpoint to verify the server is running.
    
    This simple endpoint provides a way to check if the API server is operational
    without testing any specific functionality. It's useful for monitoring systems,
    health checks, and verifying basic connectivity to the backend service.
    
    Returns:
    - JSON response with status "ok" and a message indicating the server is running
    """
    return {"status": "ok", "message": "Server is running"}


# To run the app (for development): uvicorn ewa_main:app --reload --port 8001
if __name__ == "__main__":
    try:
        # Any other critical initializations that happen before uvicorn.run
        # and after imports can also be moved inside this try block if needed.
        print("Attempting to start EWA Analyzer backend...")
        uvicorn.run("ewa_main:app", host="0.0.0.0", port=8001, reload=True)
    except BaseException as e:
        import traceback
        print("--- STARTUP FAILED ---")
        print(f"An error occurred during application startup: {type(e).__name__} - {e}")
        print("Full traceback:")
        traceback.print_exc()
        print("--- END OF TRACEBACK ---")
        # Optionally, re-raise the exception if you want the process to exit with an error code
        # raise
