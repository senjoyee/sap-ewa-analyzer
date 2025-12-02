"""
Document Conversion Orchestrator Module

This module serves as a unified entry point for converting various document formats 
(PDF, DOCX, DOC) to markdown format. It orchestrates the conversion process by 
delegating to specialized converters based on file type.

Key Functionality:
- Unified document conversion interface for multiple file formats
- Conversion status tracking across multiple file formats
- Delegating to specialized converters (PDF, DOCX)
- Error handling and status reporting

The module maintains a global status tracker to monitor all conversion jobs,
making it easy to check the progress of any document conversion process.
"""

import os
from datetime import datetime

from converters import pdf_markdown_converter
from converters import docx_markdown_converter
from converters.pdf_markdown_converter import convert_pdf_to_markdown
from converters.docx_markdown_converter import convert_docx_to_markdown

# Dictionary to track the status of document conversion jobs across all file types
# This is a global tracker for the unified converter
conversion_status_tracker = {}

def convert_document_to_markdown(blob_name: str) -> dict:
    """
    Converts a document (PDF, DOCX, DOC) stored in Azure Blob Storage to markdown.
    This function serves as a unified entry point for all document types.
    
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
        # Use PDF converter
        result = convert_pdf_to_markdown(blob_name)
    elif blob_name.lower().endswith('.docx'):
        # Use DOCX converter
        result = convert_docx_to_markdown(blob_name)
    elif blob_name.lower().endswith('.doc'):
        # Use DOC converter (Pandoc-based)
        from converters.doc_markdown_converter import convert_doc_to_markdown
        result = convert_doc_to_markdown(blob_name)
    else:
        # Unsupported file type
        result = {
            "error": True,
            "status": "failed",
            "message": f"Unsupported file type: {os.path.splitext(blob_name)[1]}. Supported types: .pdf, .docx, .doc",
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
            
        # Check DOCX converter status
        docx_status = docx_markdown_converter.get_conversion_status(blob_name)
        if docx_status.get("status") != "unknown":
            return docx_status
            
        # No status found in any converter
        return {
            "error": True,
            "message": f"No conversion job found for {blob_name}",
            "status": "unknown"
        }
    
    return conversion_status_tracker[blob_name]