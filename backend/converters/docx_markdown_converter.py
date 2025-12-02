"""
DOCX to Markdown Conversion Module

This module specializes in converting Microsoft Word documents (.docx/.doc) to markdown format.
It handles the complete conversion workflow from downloading Word documents from Azure Blob Storage,
processing them with appropriate libraries, and uploading the resulting markdown files.

Key Functionality:
- Converting DOCX files to markdown format using docx2txt
- Supporting legacy DOC files through the doc_extractor module
- Managing conversion status tracking
- Handling Azure Blob Storage operations for document retrieval and storage
- Preserving document structure during conversion

The module works directly with Azure Blob Storage and doesn't require saving files
to the local filesystem except for temporary processing.
"""

import os
import tempfile
from datetime import datetime

from azure.storage.blob import ContentSettings
import docx2txt

from core.azure_clients import (
    blob_service_client,
    AZURE_STORAGE_CONTAINER_NAME,
)
from converters.doc_extractor import extract_text_from_doc

# Dictionary to track the status of document conversion jobs
# Structure: {blob_name: {"status": "pending|processing|completed|failed", "start_time": timestamp, "end_time": timestamp, "message": "message", "progress": progress_percentage}}
conversion_status_tracker = {}

def convert_docx_to_markdown(blob_name: str) -> dict:
    """
    Converts a Word document (.docx) stored in Azure Blob Storage to markdown
    and saves the markdown to the same container with a .md extension.
    
    Args:
        blob_name: The name of the blob to convert.
        
    Returns:
        A dictionary containing information about the conversion process, including status and result location.
    """
    if not blob_service_client:
        return {"error": True, "message": "Azure Blob Service client not initialized."}
    
    # Check if file exists and is a Word document
    file_lower = blob_name.lower()
    is_docx = file_lower.endswith('.docx')
    is_doc = file_lower.endswith('.doc')
    
    if not (is_docx or is_doc):
        return {"error": True, "message": f"File {blob_name} is not a Word document (.doc or .docx)."}
    
    # Set initial status
    start_time = datetime.now()
    conversion_status_tracker[blob_name] = {
        "status": "processing",
        "start_time": start_time.isoformat(),
        "progress": 0,
        "message": "Started Word document to markdown conversion"
    }
    
    try:
        # Get the container client
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
        
        # Download the Word document from blob storage
        conversion_status_tracker[blob_name]["progress"] = 10
        conversion_status_tracker[blob_name]["message"] = "Downloading Word document from blob storage"
        
        blob_client = container_client.get_blob_client(blob_name)
        blob_properties = blob_client.get_blob_properties()
        metadata = blob_properties.metadata
        
        # Download blob content
        blob_data = blob_client.download_blob()
        docx_content = blob_data.readall()
        
        # Save document temporarily (thread-safe)
        suffix = ".docx" if is_docx else ".doc"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(docx_content)
            temp_docx_path = temp_file.name
        
        conversion_status_tracker[blob_name]["progress"] = 30
        conversion_status_tracker[blob_name]["message"] = "Converting Word document to markdown"
        
        # Process the document based on its format
        file_lower = blob_name.lower()
        if file_lower.endswith('.docx'):
            # Use docx2txt for .docx files
            md_text = docx2txt.process(temp_docx_path)
        elif file_lower.endswith('.doc'):
            # For .doc files, use our specialized doc_extractor
            conversion_status_tracker[blob_name]["message"] = "Using specialized extractor for .doc file"
            md_text = extract_text_from_doc(temp_docx_path)
        else:
            raise ValueError(f"Unsupported file format: {blob_name}")
        
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
        if os.path.exists(temp_docx_path):
            os.remove(temp_docx_path)
        
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
            "message": "Word document converted to markdown successfully",
            "markdown_file": markdown_blob_name,
            "json_file": json_blob_name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds()
        }
        
    except Exception as e:
        end_time = datetime.now()
        error_message = f"Error converting Word document to markdown: {str(e)}"
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
    test_file_path = r"path/to/test.docx"  # Change this to a valid DOCX path
    if os.path.exists(test_file_path):
        # For local testing
        print(f"Local testing with file: {test_file_path}")
        # Upload the test file to blob storage
        with open(test_file_path, "rb") as f:
            container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
            blob_client = container_client.get_blob_client(os.path.basename(test_file_path))
            blob_client.upload_blob(f, overwrite=True)
        
        # Convert the file
        result = convert_docx_to_markdown(os.path.basename(test_file_path))
        print(f"Conversion result: {result}")
    else:
        print(f"Test file not found: {test_file_path}")