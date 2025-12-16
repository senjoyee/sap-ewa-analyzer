"""
PDF to Markdown Conversion Module

This module specializes in converting PDF documents to markdown format using the pymupdf4llm
library. It handles the complete conversion workflow from downloading PDFs from Azure Blob Storage,
processing them with PyMuPDF, and uploading the resulting markdown files.

Key Functionality:
- Converting PDF files to structured markdown format
- Preserving document structure including headings, lists, and tables
- Managing conversion status tracking
- Handling Azure Blob Storage operations for document retrieval and storage
- Optimizing PDF content for downstream LLM processing

The module works directly with Azure Blob Storage and preserves the semantic structure
of documents during conversion for better analysis by AI systems.
"""

import os
import tempfile
from datetime import datetime

from azure.storage.blob import ContentSettings
import pymupdf4llm
import fitz  # PyMuPDF fallback for text extraction

from core.azure_clients import (
    blob_service_client,
    AZURE_STORAGE_CONTAINER_NAME,
)

# Dictionary to track the status of document conversion jobs
# Structure: {blob_name: {"status": "pending|processing|completed|failed", "start_time": timestamp, "end_time": timestamp, "message": "message", "progress": progress_percentage}}
conversion_status_tracker = {}

def convert_pdf_to_markdown(blob_name: str) -> dict:
    """
    Converts a PDF stored in Azure Blob Storage to markdown using pymupdf4llm
    and saves the markdown to the same container with a .md extension.
    
    Args:
        blob_name: The name of the blob to convert.
        
    Returns:
        A dictionary containing information about the conversion process, including status and result location.
    """
    if not blob_service_client:
        return {"error": True, "message": "Azure Blob Service client not initialized."}
    
    # Check if file exists and is a PDF
    if not blob_name.lower().endswith('.pdf'):
        return {"error": True, "message": f"File {blob_name} is not a PDF."}
    
    # Set initial status
    start_time = datetime.now()
    conversion_status_tracker[blob_name] = {
        "status": "processing",
        "start_time": start_time.isoformat(),
        "progress": 0,
        "message": "Started PDF to markdown conversion"
    }
    
    try:
        # Get the container client
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
        
        # Download the PDF from blob storage
        conversion_status_tracker[blob_name]["progress"] = 10
        conversion_status_tracker[blob_name]["message"] = "Downloading PDF from blob storage"
        
        blob_client = container_client.get_blob_client(blob_name)
        blob_properties = blob_client.get_blob_properties()
        metadata = blob_properties.metadata
        
        # Download blob content
        blob_data = blob_client.download_blob()
        pdf_content = blob_data.readall()
        
        # Save PDF temporarily (thread-safe)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(pdf_content)
            temp_pdf_path = temp_file.name
        
        conversion_status_tracker[blob_name]["progress"] = 30
        conversion_status_tracker[blob_name]["message"] = "Converting PDF to markdown"
        
        # Use pymupdf4llm to convert PDF to markdown; fallback to plain text on failure
        try:
            md_text = pymupdf4llm.to_markdown(temp_pdf_path)
        except Exception as conv_err:
            # Fallback: extract plain text with PyMuPDF to avoid hard failure
            conversion_status_tracker[blob_name]["message"] = (
                f"pymupdf4llm failed ({conv_err}); falling back to plain text extraction"
            )
            doc = fitz.open(temp_pdf_path)
            pages_text = []
            for page in doc:
                pages_text.append(page.get_text("text"))
            doc.close()
            md_text = "\n\n".join(pages_text)
        
        conversion_status_tracker[blob_name]["progress"] = 70
        conversion_status_tracker[blob_name]["message"] = "Uploading markdown to blob storage"
        
        # Create markdown blob name (same as original but with .md extension)
        markdown_blob_name = os.path.splitext(blob_name)[0] + ".md"
        
        # Upload markdown to blob storage
        markdown_blob_client = container_client.get_blob_client(markdown_blob_name)
        markdown_blob_client.upload_blob(
            md_text.encode(),
            overwrite=True,
            metadata=metadata,  # Preserve the same metadata as the source file
            content_settings=ContentSettings(content_type="text/markdown")
        )
        
        # Also create a JSON blob to maintain compatibility with existing system
        # The JSON contains minimal info to indicate processing is complete
        conversion_status_tracker[blob_name]["progress"] = 90
        conversion_status_tracker[blob_name]["message"] = "Creating JSON status file"
        
        json_blob_name = os.path.splitext(blob_name)[0] + ".json"
        json_content = f'{{"processed": true, "markdown_file": "{markdown_blob_name}"}}'
        
        json_blob_client = container_client.get_blob_client(json_blob_name)
        json_blob_client.upload_blob(
            json_content.encode(),
            overwrite=True,
            metadata=metadata,  # Preserve the same metadata as the source file
            content_settings=ContentSettings(content_type="application/json")
        )
        
        # Clean up temporary file
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        
        # Update status to completed
        end_time = datetime.now()
        conversion_status_tracker[blob_name].update({
            "status": "completed",
            "end_time": end_time.isoformat(),
            "progress": 100,
            "message": "Conversion completed successfully",
            "markdown_blob": markdown_blob_name,
            "json_blob": json_blob_name
        })
        
        return {
            "status": "completed",
            "message": "PDF converted to markdown successfully",
            "markdown_file": markdown_blob_name,
            "json_file": json_blob_name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds()
        }
        
    except Exception as e:
        end_time = datetime.now()
        error_message = f"Error converting PDF to markdown: {str(e)}"
        conversion_status_tracker[blob_name].update({
            "status": "failed",
            "end_time": end_time.isoformat(),
            "progress": 0,
            "message": error_message
        })
        
        print(error_message)
        return {
            "error": True,
            "status": "failed",
            "message": error_message,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }

def get_conversion_status(blob_name: str) -> dict:
    """
    Gets the current status of a document conversion job.
    
    Args:
        blob_name: The name of the blob being converted.
        
    Returns:
        A dictionary containing the current status information.
    """
    if blob_name not in conversion_status_tracker:
        return {
            "error": True,
            "message": f"No conversion job found for {blob_name}",
            "status": "unknown"
        }
    
    status_info = conversion_status_tracker[blob_name]
    
    # Check if the conversion is completed and a JSON file exists
    if status_info.get("status") == "completed":
        try:
            # Double-check that the JSON file actually exists in the blob storage
            container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
            json_blob_name = os.path.splitext(blob_name)[0] + ".json"
            json_blob_client = container_client.get_blob_client(json_blob_name)
            
            # This will raise an exception if the blob doesn't exist
            json_blob_client.get_blob_properties()
            
            # Also verify the markdown file exists
            markdown_blob_name = os.path.splitext(blob_name)[0] + ".md"
            markdown_blob_client = container_client.get_blob_client(markdown_blob_name)
            markdown_blob_client.get_blob_properties()
            
        except Exception as e:
            # If the files don't exist, update status to failed
            status_info.update({
                "status": "failed",
                "message": f"Conversion completed but files not found: {str(e)}"
            })
    
    return status_info

# Example usage (for testing this module directly):
if __name__ == "__main__":
    try:
        test_file_path = r"path/to/test.pdf"  # Change this to a valid PDF path
        print(f"Starting conversion of {test_file_path}")
        result = convert_pdf_to_markdown(test_file_path)
        print(f"Conversion result: {result}")
    except Exception as e:
        print(f"Error in main: {e}")
