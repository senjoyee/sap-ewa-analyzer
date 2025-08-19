"""Storage-related FastAPI routes extracted from ewa_main.py.

Handles:
- /api/upload  (file upload to Azure Blob Storage)
- /api/files   (list blobs with processing / AI status)
- /api/download/{blob_name} (download blob)

This is a straight extraction; functionality is unchanged so existing frontend calls keep working.
"""

from __future__ import annotations

import os
from typing import Dict, Any, List

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Response, Body
from pydantic import BaseModel
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import json
import os
import re
from azure.core.exceptions import ResourceNotFoundError
from datetime import datetime

from workflow_orchestrator import EWAWorkflowOrchestrator

# ---------------------------------------------------------------------------
# Filename validation and metadata extraction
# ---------------------------------------------------------------------------

def generate_standardized_filename(file_metadata: Dict[str, Any], original_filename: str) -> str:
    """
    Generate standardized filename in format: <SID>_<DD>_<MON>_<YEAR>.pdf
    Example: ERP_07_Jun_25.pdf
    
    Args:
        file_metadata: Dict containing 'system_id' and 'report_date' or 'report_date_str'
        original_filename: Original filename to extract extension from
        
    Returns:
        Standardized filename string
    """
    try:
        system_id = file_metadata['system_id']
        
        # Handle different date formats from AI vs filename extraction
        if isinstance(file_metadata.get("report_date"), datetime):
            # AI extraction returns datetime object
            report_date = file_metadata["report_date"]
        else:
            # Try to parse from report_date_str or report_date
            date_str = file_metadata.get("report_date_str") or file_metadata.get("report_date")
            if date_str:
                # Try different date formats
                for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"]:
                    try:
                        report_date = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # If all parsing fails, use current date
                    report_date = datetime.now()
            else:
                report_date = datetime.now()
        
        # Get file extension from original filename
        _, ext = os.path.splitext(original_filename)
        if not ext:
            ext = '.pdf'  # Default to PDF
            
        # Format: <SID>_<DD>_<MON>_<YEAR>
        day = report_date.strftime("%d")
        month = report_date.strftime("%b")  # Short month name (Jan, Feb, etc.)
        year = report_date.strftime("%y")   # 2-digit year
        
        new_filename = f"{system_id}_{day}_{month}_{year}{ext}"
        
        print(f"Generated standardized filename: {original_filename} -> {new_filename}")
        return new_filename
        
    except Exception as e:
        print(f"Error generating standardized filename: {e}. Using original filename.")
        return original_filename

def validate_filename_and_extract_metadata(filename: str) -> Dict[str, Any]:
    """
    Validate filename format and extract system ID and report date.
    Expected format: <SID>_ddmmyy.pdf (e.g., ERP_090625.pdf)
    
    Returns:
        Dict with 'system_id', 'report_date', and 'report_date_str'
    
    Raises:
        ValueError: If filename doesn't match expected format
    """
    # Remove extension and check format
    name_without_ext = os.path.splitext(filename)[0]
    
    # Pattern: SID_ddmmyy
    pattern = r'^([A-Z0-9]+)_(\d{6})$'
    match = re.match(pattern, name_without_ext)
    
    if not match:
        raise ValueError(
            f"Filename '{filename}' must follow format <SID>_ddmmyy.pdf (e.g., ERP_090625.pdf). "
            f"SID should be alphanumeric uppercase, date should be 6 digits (ddmmyy)."
        )
    
    system_id = match.group(1)
    date_str = match.group(2)
    
    # Parse date: ddmmyy
    try:
        day = int(date_str[:2])
        month = int(date_str[2:4])
        year = int(date_str[4:6])
        
        # Assume years 00-30 are 2000s, 31-99 are 1900s
        if year <= 30:
            year += 2000
        else:
            year += 1900
            
        report_date = datetime(year, month, day)
        report_date_str = report_date.strftime("%d.%m.%Y")
        
    except ValueError as e:
        raise ValueError(f"Invalid date in filename '{filename}': {date_str}. Error: {str(e)}")
    
    return {
        "system_id": system_id,
        "report_date": report_date,
        "report_date_str": report_date_str
    }

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
    """Upload a document file to Azure Blob Storage with AI-based metadata extraction."""

    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized. Check server logs and .env configuration.")
    if not file:
        raise HTTPException(status_code=400, detail="No file sent.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    try:
        contents = await file.read()
        
        # Try AI-based metadata extraction first
        try:
            from utils.pdf_metadata_extractor import extract_metadata_with_ai
            file_metadata = await extract_metadata_with_ai(contents)
            print(f"AI extraction successful - System ID: {file_metadata['system_id']}, Report Date: {file_metadata['report_date_str']}")
        except Exception as ai_error:
            # If AI extraction fails, fall back to filename validation
            print(f"AI extraction failed, falling back to filename validation: {str(ai_error)}")
            try:
                file_metadata = validate_filename_and_extract_metadata(file.filename)
                print(f"Filename validation successful - System ID: {file_metadata['system_id']}, Report Date: {file_metadata['report_date_str']}")
            except ValueError as filename_error:
                raise HTTPException(status_code=400, detail=f"{str(ai_error)} | {str(filename_error)}")
            
        # Generate new filename based on extracted metadata
        new_filename = generate_standardized_filename(file_metadata, file.filename)
        blob_name = new_filename
        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, blob=blob_name
        )

        print(
            f"Uploading {file.filename} to Azure Blob Storage in container {AZURE_STORAGE_CONTAINER_NAME} as blob {blob_name}..."
        )
        print(
            f"Extracted metadata - System ID: {file_metadata['system_id']}, Report Date: {file_metadata['report_date_str']}, Customer: {customer_name}"
        )

        # Create comprehensive metadata
        # Handle both AI extraction (datetime object) and filename validation (already parsed) results
        if isinstance(file_metadata["report_date"], datetime):
            report_date_iso = file_metadata["report_date"].isoformat()
            report_date_str = file_metadata["report_date_str"]
        else:
            # AI extraction returns string dates
            try:
                dt = datetime.strptime(file_metadata["report_date"], "%d.%m.%Y")
                report_date_iso = dt.isoformat()
                report_date_str = file_metadata["report_date"]
            except ValueError:
                # Fallback
                report_date_iso = datetime.now().isoformat()
                report_date_str = file_metadata.get("report_date_str", "Unknown")

        metadata: Dict[str, Any] = {
            "customer_name": customer_name,
            "system_id": file_metadata["system_id"],
            "report_date": report_date_iso,
            "report_date_str": report_date_str
        }

        blob_client.upload_blob(contents, overwrite=True, metadata=metadata)

        print(
            f"Successfully uploaded {file.filename} to {blob_name} with metadata: {metadata}"
        )
        return {
            "filename": blob_name,  # Return the new standardized filename
            "original_filename": file.filename,  # Include original for reference
            "customer_name": customer_name,
            "system_id": file_metadata["system_id"],
            "report_date": report_date_str,
            "message": "File uploaded successfully to Azure Blob Storage with extracted metadata and standardized filename.",
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"Error uploading file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not upload file: {str(e)}")


# ------------------------- List endpoint ------------------------- #

@router.get("/files")
async def list_files():
    """List all files stored in Azure Blob Storage with their processing status and sequential processing opportunities."""

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
        file_groups: dict[str, list[dict[str, Any]]] = {}  # Group by customer+SID
        
        for blob in blob_list:
            name_low = blob.name.lower()
            if name_low.endswith((".json", ".md")):
                continue  # skip auxiliary files in main listing

            blob_client = container_client.get_blob_client(blob.name)
            properties = blob_client.get_blob_properties()
            metadata = properties.metadata or {}

            base_name, _ = os.path.splitext(blob.name)
            customer_name = metadata.get("customer_name", "Unknown")
            system_id = metadata.get("system_id", "Unknown")
            processed = base_name in json_files or base_name in md_files
            ai_analyzed = base_name in ai_analyzed_files
            
            file_info = {
                "name": blob.name,
                "last_modified": blob.last_modified,
                "size": blob.size,
                "report_date": metadata.get("report_date"),
                "report_date_str": metadata.get("report_date_str"),
                "customer_name": customer_name,
                "system_id": system_id,
                "processed": processed,
                "ai_analyzed": ai_analyzed,
            }
            
            files.append(file_info)
            
            # Group files by customer+SID for sequential processing detection
            group_key = f"{customer_name}|{system_id}"
            if group_key not in file_groups:
                file_groups[group_key] = []
            file_groups[group_key].append(file_info)
        
        # Detect sequential processing opportunities
        sequential_groups = []
        for group_key, group_files in file_groups.items():
            if len(group_files) > 1:
                customer_name, system_id = group_key.split('|')
                unprocessed_files = [f for f in group_files if not f['processed']]
                
                if len(unprocessed_files) > 1:
                    # Sort by report date for proper ordering display
                    unprocessed_files.sort(key=lambda f: f['report_date'] if f['report_date'] else f['last_modified'])
                    
                    sequential_groups.append({
                        "customer_name": customer_name,
                        "system_id": system_id,
                        "total_files": len(group_files),
                        "unprocessed_files": len(unprocessed_files),
                        "files": unprocessed_files,
                        "earliest_date": unprocessed_files[0]['report_date_str'],
                        "latest_date": unprocessed_files[-1]['report_date_str']
                    })
        
        # Add sequential processing metadata to individual files
        for file_info in files:
            group_key = f"{file_info['customer_name']}|{file_info['system_id']}"
            group_files = file_groups.get(group_key, [])
            unprocessed_in_group = [f for f in group_files if not f['processed']]
            
            file_info['sequential_processing_available'] = len(unprocessed_in_group) > 1
            file_info['files_in_group'] = len(group_files)
            file_info['unprocessed_in_group'] = len(unprocessed_in_group)

        print(f"Returning {len(files)} files with {len(sequential_groups)} sequential processing opportunities")
        return {
            "files": files,
            "sequential_groups": sequential_groups
        }
    except Exception as e:
        print(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=f"Could not list files: {str(e)}")


# ------------------------- Delete Analysis endpoint ------------------------- #

class DeleteAnalysisRequest(BaseModel):
    fileName: str
    baseName: str

class DeleteAnalysisResponse(BaseModel):
    message: str
    deleted_files: List[str]
    errors: List[str]

@router.delete("/delete-analysis", response_model=DeleteAnalysisResponse)
async def delete_analysis(request_data: DeleteAnalysisRequest):
    """Delete an analysis and all related files from Azure Blob Storage."""
    
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized.")
    
    try:
        file_name = request_data.fileName
        base_name = request_data.baseName
        
        if not file_name or not base_name:
            raise HTTPException(status_code=400, detail="File name or base name not provided")
            
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
        
        # Delete all blobs whose names start with the base_name (remove all traces)
        deleted_files = []
        errors = []
        try:
            blob_list = container_client.list_blobs()
            for blob in blob_list:
                if blob.name.startswith(base_name):
                    try:
                        blob_client = container_client.get_blob_client(blob.name)
                        blob_client.delete_blob()
                        deleted_files.append(blob.name)
                    except Exception as e:
                        errors.append(f"Failed to delete {blob.name}: {str(e)}")
        except Exception as e:
            errors.append(f"Failed to list blobs: {str(e)}")
        
        return {
            "message": f"Analysis for {file_name} deletion processed",
            "deleted_files": deleted_files,
            "errors": errors
        }
        
    except Exception as e:
        print(f"Error deleting analysis for {request_data.get('fileName', 'unknown file')}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not delete analysis files: {str(e)}")


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
