"""
DOC to Markdown Conversion Module (Pandoc)

This module provides a function to convert legacy .doc files to markdown format using Pandoc via subprocess.
It is intended to be called only for .doc files (not .docx).
"""

import os
import subprocess
import tempfile
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError(
        "Azure Storage connection string and container name must be set in .env file "
        "(AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER_NAME)"
    )

blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

# Conversion status tracker (optional, for integration)
conversion_status_tracker = {}

def convert_doc_to_markdown(blob_name: str) -> dict:
    """
    Converts a .doc file stored in Azure Blob Storage to markdown.
    Steps:
      1. Download .doc from blob
      2. Convert .doc to .docx using LibreOffice CLI
      3. Use docx_markdown_converter.convert_docx_to_markdown for .docx to markdown
      4. Clean up temp files
    Args:
        blob_name: The name of the .doc blob to convert.
    Returns:
        A dictionary with status and output file info.
    """
    from converters.docx_markdown_converter import convert_docx_to_markdown
    start_time = datetime.now()
    conversion_status_tracker[blob_name] = {
        "status": "processing",
        "start_time": start_time.isoformat(),
        "progress": 0,
        "message": "Starting DOC to DOCX conversion"
    }
    try:
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
        blob_client = container_client.get_blob_client(blob_name)
        blob_properties = blob_client.get_blob_properties()
        metadata = blob_properties.metadata
        # Download blob
        doc_data = blob_client.download_blob().readall()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as temp_doc_file:
            temp_doc_file.write(doc_data)
            temp_doc_path = temp_doc_file.name
        temp_docx_path = temp_doc_path + "x"  # .docx
        conversion_status_tracker[blob_name]["progress"] = 30
        conversion_status_tracker[blob_name]["message"] = "Converting DOC to DOCX via LibreOffice CLI"
        # LibreOffice CLI conversion
        result = subprocess.run([
            "libreoffice", "--headless", "--convert-to", "docx", "--outdir", os.path.dirname(temp_doc_path), temp_doc_path
        ], capture_output=True, text=True)
        if result.returncode != 0 or not os.path.exists(temp_docx_path):
            raise RuntimeError(f"LibreOffice failed to convert DOC to DOCX: {result.stderr}")
        conversion_status_tracker[blob_name]["progress"] = 60
        conversion_status_tracker[blob_name]["message"] = "Converting DOCX to markdown"
        # Use docx_markdown_converter for .docx to markdown
        # Temporarily upload .docx as a blob for compatibility
        temp_docx_blob_name = os.path.splitext(blob_name)[0] + ".docx"
        temp_docx_blob_client = container_client.get_blob_client(temp_docx_blob_name)
        with open(temp_docx_path, "rb") as f:
            temp_docx_blob_client.upload_blob(
                f.read(),
                overwrite=True,
                metadata=metadata,
                content_settings=ContentSettings(content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            )
        # Now call the docx converter
        md_result = convert_docx_to_markdown(temp_docx_blob_name)
        # Clean up temp files and temp .docx blob
        os.remove(temp_doc_path)
        if os.path.exists(temp_docx_path):
            os.remove(temp_docx_path)
        temp_docx_blob_client.delete_blob()
        # Return the markdown result
        end_time = datetime.now()
        conversion_status_tracker[blob_name].update({
            "status": md_result.get("status", "completed"),
            "end_time": end_time.isoformat(),
            "progress": 100 if md_result.get("status") == "completed" else 0,
            "message": md_result.get("message", "DOC to markdown conversion completed"),
            "markdown_blob": md_result.get("markdown_file"),
            "json_blob": md_result.get("json_file")
        })
        return {
            **md_result,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds()
        }
    except Exception as e:
        end_time = datetime.now()
        error_message = f"Error converting DOC to markdown: {str(e)}"
        conversion_status_tracker[blob_name].update({
            "status": "failed",
            "end_time": end_time.isoformat(),
            "progress": 0,
            "message": error_message
        })
        return {
            "error": True,
            "status": "failed",
            "message": error_message,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
