"""
Document Conversion Orchestrator Module (PDF-only)

This module is the single entry point for converting PDF files to markdown.
Legacy DOC/DOCX support has been removed; non-PDF inputs will return an error.
"""

import os
from datetime import datetime

from converters import pdf_markdown_converter
from converters.pdf_markdown_converter import convert_pdf_to_markdown

# Dictionary to track the status of document conversion jobs across all file types
# This is a global tracker for the unified converter
conversion_status_tracker = {}

def convert_document_to_markdown(blob_name: str) -> dict:
    """
    Converts a PDF stored in Azure Blob Storage to markdown.
    This function now only supports PDF input.
    
    Args:
        blob_name: The name of the blob to convert.
        
    Returns:
        A dictionary containing information about the conversion process.
    """
    # Set initial status
    start_time = datetime.now()
    conversion_status_tracker[blob_name] = {
        "status": "processing",
        "start_time": start_time.isoformat(),
        "progress": 0,
        "message": "Starting document conversion"
    }
    
    # Determine file type and use appropriate converter
    if blob_name.lower().endswith('.pdf'):
        result = convert_pdf_to_markdown(blob_name)
    else:
        # Unsupported file type
        result = {
            "error": True,
            "status": "failed",
            "message": f"Unsupported file type: {os.path.splitext(blob_name)[1]}. Supported types: .pdf",
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat()
        }
    
    # Update the global status tracker with the result
    conversion_status_tracker[blob_name] = {
        **conversion_status_tracker.get(blob_name, {}),
        **result
    }
    
    return result

def get_conversion_status(blob_name: str) -> dict:
    """
    Gets the current status of a document conversion job.
    
    Args:
        blob_name: The name of the blob being converted.
        
    Returns:
        A dictionary containing the current status information.
    """
    if blob_name not in conversion_status_tracker:
        # Check PDF converter status
        pdf_status = pdf_markdown_converter.get_conversion_status(blob_name)
        if pdf_status.get("status") != "unknown":
            return pdf_status

        # No status found
        return {
            "error": True,
            "message": f"No conversion job found for {blob_name}",
            "status": "unknown"
        }

    return conversion_status_tracker[blob_name]