import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from dotenv import load_dotenv
from pydantic import BaseModel
from pdf_markdown_converter import convert_pdf_to_markdown, get_conversion_status
from azure_openai_service import analyze_document_with_ai
import uvicorn # For running the app

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
    # Add any other origins if necessary
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
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
        for blob in blob_list:
            name = blob.name.lower()
            if name.endswith('.json'):
                # Store the base name (without extension) as key
                base_name = os.path.splitext(blob.name)[0]
                json_files[base_name] = True
                print(f"Found JSON file: {blob.name}, base name: {base_name}")
            elif name.endswith('.md'):
                # Store the base name (without extension) as key
                base_name = os.path.splitext(blob.name)[0]
                md_files[base_name] = True
                print(f"Found MD file: {blob.name}, base name: {base_name}")
        
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
            print(f"File {blob.name} processed status: {is_processed}")
            
            files.append({
                "name": blob.name, 
                "last_modified": blob.last_modified, 
                "size": blob.size,
                "customer_name": customer_name,
                "processed": is_processed
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
    Convert a PDF document stored in Azure Blob Storage to markdown using pymupdf4llm.
    The markdown result will be saved back to the same container with a .md extension,
    and a .json file will be created to maintain compatibility with existing system.
    
    Args:
        request: A request object containing the blob_name to convert
    """
    try:
        # Call the convert_pdf_to_markdown function from the pdf_markdown_converter module
        result = convert_pdf_to_markdown(request.blob_name)
        
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
        result = await analyze_document_with_ai(request.blob_name)
        
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


# To run the app (for development): uvicorn main:app --reload --port 8000
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
