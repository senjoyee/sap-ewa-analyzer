"""Storage-related FastAPI routes extracted from ewa_main.py.

Handles:
- /api/upload  (file upload to Azure Blob Storage)
- /api/files   (list blobs with processing / AI status)
- /api/download/{blob_name} (download blob)

This is a straight extraction; functionality is unchanged so existing frontend calls keep working.
"""

from __future__ import annotations

import os
from typing import Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Response
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Azure Blob setup (duplicated from main for now – we will unify later)
# ---------------------------------------------------------------------------
load_dotenv()

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

if not AZURE_STORAGE_CONNECTION_STRING:
    raise ValueError(
        "AZURE_STORAGE_CONNECTION_STRING not found in environment variables. Please set it in your .env file."
    )
if not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError(
        "AZURE_STORAGE_CONTAINER_NAME not found in environment variables. Please set it in your .env file."
    )

try:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
except Exception as e:
    print(f"Error initializing BlobServiceClient in storage_router: {e}")
    blob_service_client = None

# ---------------------------------------------------------------------------
# Router definition
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api", tags=["storage"])

# ------------------------- Upload endpoint ------------------------- #

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), customer_name: str = Form(...)):
    """Upload a document file to Azure Blob Storage."""

    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized. Check server logs and .env configuration.")
    if not file:
        raise HTTPException(status_code=400, detail="No file sent.")

    try:
        blob_name = file.filename  # In production you might generate a unique name
        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, blob=blob_name
        )

        print(
            f"Uploading {file.filename} to Azure Blob Storage in container {AZURE_STORAGE_CONTAINER_NAME} as blob {blob_name}..."
        )

        contents = await file.read()

        metadata: Dict[str, Any] = {"customer_name": customer_name}

        blob_client.upload_blob(contents, overwrite=True, metadata=metadata)

        print(
            f"Successfully uploaded {file.filename} to {blob_name} with customer: {customer_name}."
        )
        return {
            "filename": file.filename,
            "customer_name": customer_name,
            "message": "File uploaded successfully to Azure Blob Storage.",
        }

    except Exception as e:
        print(f"Error uploading file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not upload file: {str(e)}")


# ------------------------- List endpoint ------------------------- #

@router.get("/files")
async def list_files():
    """List all files stored in Azure Blob Storage with their processing status."""

    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")

    try:
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
        blob_list = list(container_client.list_blobs())

        print(f"Found {len(blob_list)} total blobs in container")

        json_files: Dict[str, bool] = {}
        md_files: Dict[str, bool] = {}
        ai_analyzed_files: Dict[str, bool] = {}

        for blob in blob_list:
            name_low = blob.name.lower()
            base_name, ext = os.path.splitext(blob.name)

            if ext == ".json":
                json_files[base_name] = True
                if base_name.endswith("_AI"):
                    ai_analyzed_files[base_name[:-3]] = True  # strip _AI
            elif ext == ".md":
                md_files[base_name] = True
                if base_name.endswith("_AI"):
                    ai_analyzed_files[base_name[:-3]] = True

        files: list[dict[str, Any]] = []
        for blob in blob_list:
            name_low = blob.name.lower()
            if name_low.endswith((".json", ".md")):
                continue  # skip auxiliary files in main listing

            blob_client = container_client.get_blob_client(blob.name)
            properties = blob_client.get_blob_properties()
            metadata = properties.metadata or {}

            base_name, _ = os.path.splitext(blob.name)
            files.append(
                {
                    "name": blob.name,
                    "last_modified": blob.last_modified,
                    "size": blob.size,
                    "report_date": metadata.get("report_date"),
                    "customer_name": metadata.get("customer_name", "Unknown"),
                    "processed": base_name in json_files or base_name in md_files,
                    "ai_analyzed": base_name in ai_analyzed_files,
                }
            )

        print(f"Returning {len(files)} files in the list")
        return files
    except Exception as e:
        print(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=f"Could not list files: {str(e)}")


# ------------------------- Download endpoint ------------------------- #

@router.get("/download/{blob_name}")
async def download_file(blob_name: str):
    """Download a file from Azure Blob Storage."""

    try:
        if not blob_service_client:
            raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized")

        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, blob=blob_name
        )

        if not blob_client.exists():
            raise HTTPException(status_code=404, detail=f"File {blob_name} not found")

        blob_data = blob_client.download_blob()
        content = blob_data.readall()

        if blob_name.endswith(".md"):
            content_type = "text/markdown"
        elif blob_name.endswith(".json"):
            content_type = "application/json"
        elif blob_name.endswith(".pdf"):
            content_type = "application/pdf"
        else:
            content_type = "application/octet-stream"

        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f"inline; filename={blob_name}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Error downloading file {blob_name}: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)
