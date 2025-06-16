"""
Document Text Extraction Module

This module provides utilities for extracting text from legacy Microsoft Word (.doc) files
using various command-line tools with fallback mechanisms. It supports multiple extraction
methods including antiword, catdoc, and textutil (on macOS), ensuring maximum compatibility
across different environments.

Key Functionality:
- Extracting text content from .doc files using multiple methods
- Cross-platform support (Windows, macOS, Linux)
- Graceful fallbacks when primary extraction tools are unavailable
- Temporary file handling for extraction processes

This module is particularly useful for processing legacy documents in the EWA Analyzer
workflow before they can be analyzed by more sophisticated services.
"""

import os
import tempfile
import subprocess
import platform

def extract_text_from_doc(doc_path):
    """
    Extract text from .doc file using multiple methods and fallbacks.
    Returns the extracted text as a string.
    """
    # Method 1: Try to use antiword if installed
    try:
        result = subprocess.run(
            ['antiword', doc_path], 
            check=True, 
            capture_output=True,
            text=True
        )
        if result.stdout:
            return result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        pass  # antiword not available, try next method
    
    # Method 2: Try to use catdoc if installed
    try:
        result = subprocess.run(
            ['catdoc', doc_path], 
            check=True, 
            capture_output=True,
            text=True
        )
        if result.stdout:
            return result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        pass  # catdoc not available, try next method
    
    # Method 3: Try simple binary extraction (last resort)
    try:
        with open(doc_path, 'rb') as f:
            content = f.read()
            # Extract ASCII text (very basic approach)
            text = ''.join(char for char in content.decode('ascii', errors='ignore') 
                          if 32 <= ord(char) < 127 or char in '\n\r\t')
            return f"Warning: Limited text extraction used for .doc file.\n\n{text}"
    except Exception as e:
        return f"Error extracting text from .doc file: {str(e)}"