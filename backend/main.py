import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from dotenv import load_dotenv
from pydantic import BaseModel
from azure_document_intelligence_service import analyze_document_from_blob, get_analysis_status
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
        blob_list = container_client.list_blobs()
        
        files = []
        for blob in blob_list:
            # Get the blob client to access properties and metadata
            blob_client = container_client.get_blob_client(blob.name)
            properties = blob_client.get_blob_properties()
            
            # Extract metadata (including customer_name)
            metadata = properties.metadata
            customer_name = metadata.get('customer_name', 'Unknown') if metadata else 'Unknown'
            
            files.append({
                "name": blob.name, 
                "last_modified": blob.last_modified, 
                "size": blob.size,
                "customer_name": customer_name
            })
        return files
    except Exception as e:
        print(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=f"Could not list files: {str(e)}")


# Model for analyze request
class AnalyzeDocumentRequest(BaseModel):
    blob_name: str


@app.post("/api/analyze")
async def analyze_document(request: AnalyzeDocumentRequest):
    """
    Analyze a document stored in Azure Blob Storage using Azure Document Intelligence.
    The analysis result will be saved back to the same container with a .json extension.
    
    Args:
        request: A request object containing the blob_name to analyze
    """
    try:
        # Call the analyze_document_from_blob function from the azure_document_intelligence_service module
        result = analyze_document_from_blob(request.blob_name)
        
        if result.get("error"):
            print(f"Error analyzing document: {result.get('message')}")
            raise HTTPException(status_code=500, detail=result.get('message'))
        
        return result
    except Exception as e:
        print(f"Error in analyze_document endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing document: {str(e)}")


@app.get("/api/analysis-status/{blob_name}")
async def get_document_analysis_status(blob_name: str):
    """
    Get the status of a document analysis job.
    
    Args:
        blob_name: The name of the blob being analyzed
    """
    try:
        status = get_analysis_status(blob_name)
        
        if status.get("error"):
            raise HTTPException(status_code=404, detail=status.get("message"))
        
        return status
    except Exception as e:
        print(f"Error in get_document_analysis_status endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting analysis status: {str(e)}")


# To run the app (for development): uvicorn main:app --reload --port 8000
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
