import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from dotenv import load_dotenv
from pydantic import BaseModel
from document_converter import convert_document_to_markdown, get_conversion_status
from langgraph_workflows import execute_ewa_analysis
import uvicorn # For running the app
import os
import json

# Load environment variables from .env file
load_dotenv()

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

if not AZURE_STORAGE_CONNECTION_STRING:
    raise ValueError("AZURE_STORAGE_CONNECTION_STRING not found in environment variables. Please set it in your .env file.")
if not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError("AZURE_STORAGE_CONTAINER_NAME not found in environment variables. Please set it in your .env file.")

app = FastAPI()

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


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), customer_name: str = Form(...)):
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

@app.get("/api/files")
async def list_files():
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
        metrics_files = {}  # Track files that have metrics
        parameters_files = {}  # Track files that have parameters
        
        for blob in blob_list:
            name = blob.name.lower()
            if name.endswith('.json'):
                # Store the base name (without extension) as key
                base_name = os.path.splitext(blob.name)[0]
                json_files[base_name] = True
                print(f"Found JSON file: {blob.name}, base name: {base_name}")
                
                # Check if this is a metrics or parameters file
                if base_name.endswith('_metrics'):
                    original_base_name = base_name[:-8]  # Remove _metrics
                    metrics_files[original_base_name] = True
                    print(f"Found metrics file for: {original_base_name}")
                elif base_name.endswith('_parameters'):
                    original_base_name = base_name[:-11]  # Remove _parameters
                    parameters_files[original_base_name] = True
                    print(f"Found parameters file for: {original_base_name}")
                    
            elif name.endswith('.md'):
                # Store the base name (without extension) as key
                base_name = os.path.splitext(blob.name)[0]
                md_files[base_name] = True
                print(f"Found MD file: {blob.name}, base name: {base_name}")
                
                # Check if this is an AI analysis file
                if base_name.endswith('_AI'):
                    # Get the original file name by removing _AI suffix
                    original_base_name = base_name[:-3]  # Remove _AI
                    ai_analyzed_files[original_base_name] = True
                    print(f"Found AI analysis file for: {original_base_name}")
        
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
            # Check if this file has metrics
            has_metrics = base_name in metrics_files
            # Check if this file has parameters
            has_parameters = base_name in parameters_files
            print(f"File {blob.name} processed status: {is_processed}, AI analyzed: {is_ai_analyzed}, has metrics: {has_metrics}, has parameters: {has_parameters}")
            
            files.append({
                "name": blob.name, 
                "last_modified": blob.last_modified, 
                "size": blob.size,
                "customer_name": customer_name,
                "processed": is_processed,
                "ai_analyzed": is_ai_analyzed,
                "has_metrics": has_metrics,
                "has_parameters": has_parameters
            })
        
        print(f"Returning {len(files)} files in the list")
        return files
    except Exception as e:
        print(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=f"Could not list files: {str(e)}")


# Model for analyze request
class AnalyzeDocumentRequest(BaseModel):
    blob_name: str

# Model for AI analyze request  
class AIAnalyzeRequest(BaseModel):
    blob_name: str

@app.post("/api/analyze")
async def analyze_document(request: AnalyzeDocumentRequest):
    """
    Convert a document (PDF, DOCX, DOC) stored in Azure Blob Storage to markdown.
    The markdown result will be saved back to the same container with a .md extension,
    and a .json file will be created to maintain compatibility with existing system.
    
    Args:
        request: A request object containing the blob_name to convert
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
    
    Args:
        blob_name: The name of the blob being converted
    """
    try:
        status = get_conversion_status(blob_name)
        
        if status.get("error"):
            raise HTTPException(status_code=404, detail=status.get("message"))
        
        return status
    except Exception as e:
        print(f"Error in get_document_analysis_status endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting conversion status: {str(e)}")


@app.post("/api/analyze-ai")
async def analyze_document_with_ai_endpoint(request: AIAnalyzeRequest):
    """
    Analyze a processed document using Azure OpenAI GPT-4.
    Downloads the .md file from blob storage, sends it to GPT-4 for analysis,
    and saves the result back to blob storage with _AI suffix.
    
    Args:
        request: A request object containing the blob_name to analyze
    """
    try:
        print(f"Starting AI analysis for document: {request.blob_name}")
        
        # Call the AI analysis service
        result = await execute_ewa_analysis(request.blob_name)
        
        if result.get("error"):
            print(f"Error in AI analysis: {result.get('message')}")
            raise HTTPException(status_code=500, detail=result.get('message'))
        
        print(f"AI analysis completed successfully for {request.blob_name}")
        return result
        
    except Exception as e:
        error_message = f"Error in AI analysis endpoint: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)


@app.get("/api/download/{blob_name}")
async def download_file(blob_name: str):
    """
    Download a file from Azure Blob Storage.
    
    Args:
        blob_name: The name of the blob to download
    
    Returns:
        Response with the file content and appropriate content type
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


@app.get("/api/metrics/{blob_name}")
async def get_metrics_data(blob_name: str):
    """
    Get metrics data for a specific file.
    
    Args:
        blob_name: The base name of the file (without extension)
    
    Returns:
        JSON response with metrics data
    """
    try:
        if not blob_service_client:
            raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized")
        
        # Construct metrics file name
        base_name = os.path.splitext(blob_name)[0]
        metrics_blob_name = f"{base_name}_metrics.json"
        
        # Get blob client
        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, 
            blob=metrics_blob_name
        )
        
        # Check if blob exists
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail=f"Metrics file not found for {blob_name}")
        
        # Download and parse JSON content
        blob_data = blob_client.download_blob()
        content = blob_data.readall().decode('utf-8')
        
        import json
        metrics_data = json.loads(content)
        
        return metrics_data
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Error getting metrics data for {blob_name}: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)


@app.get("/api/parameters/{blob_name}")
async def get_parameters_data(blob_name: str):
    """
    Get parameters data for a specific file.
    
    Args:
        blob_name: The base name of the file (without extension)
    
    Returns:
        JSON response with parameters data
    """
    try:
        if not blob_service_client:
            raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized")
        
        # Construct parameters file name
        base_name = os.path.splitext(blob_name)[0]
        parameters_blob_name = f"{base_name}_parameters.json"
        
        # Get blob client
        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, 
            blob=parameters_blob_name
        )
        
        # Check if blob exists
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail=f"Parameters file not found for {blob_name}")
        
        # Download and parse JSON content
        blob_data = blob_client.download_blob()
        content = blob_data.readall().decode('utf-8')
        
        import json
        parameters_data = json.loads(content)
        
        return parameters_data
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Error getting parameters data for {blob_name}: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)


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
    Uses the original document content as context for answering questions.
    
    Args:
        request: A request object containing the chat message and document context
    
    Returns:
        JSON response with the AI's response
    """
    try:
        # Validate environment variables
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1-nano")  # Using nano for faster responses
        
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
    return {"status": "ok", "message": "Server is running"}


# To run the app (for development): uvicorn main:app --reload --port 8000
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
