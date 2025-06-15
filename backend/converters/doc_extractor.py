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
        pass # catdoc not available, try next method

    # Method 3: Fallback for macOS - textutil (if others fail)
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ['textutil', '-convert', 'txt', doc_path, '-stdout'],
                check=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
                return result.stdout
        except (subprocess.SubprocessError, FileNotFoundError):
            pass # textutil not available or failed

    # Method 4: Basic binary read as a last resort (less reliable)
    try:
        with open(doc_path, 'rb') as f:
            content_bytes = f.read()
        # Attempt to decode as latin-1, then filter for printable ASCII and common punctuation
        # This is a very basic heuristic and might not work well for all .doc files
        text = content_bytes.decode('latin-1', errors='ignore')
        printable_text = "".join(char for char in text if 31 < ord(char) < 127 or char in '\n\r\t')
        if printable_text.strip(): # Check if any meaningful text was extracted
            return printable_text
    except Exception:
        pass # Final fallback failed

    return "Error: Could not extract text from .doc file using any available method."

# Example usage (for testing this module directly):
if __name__ == "__main__":
    # Create a dummy .doc file for testing (replace with a real .doc file path)
    # This part is tricky as creating a valid .doc programmatically is complex.
    # It's better to use an actual .doc file for testing.
    test_file = "test.doc" 
    # Ensure you have a test.doc file in the same directory or provide an absolute path
    if os.path.exists(test_file):
        print(f"Extracting text from: {test_file}")
        extracted_text = extract_text_from_doc(test_file)
        print("--- Extracted Text ---")
        print(extracted_text)
        print("--- End of Text ---")
    else:
        print(f"Test file '{test_file}' not found. Please create it or provide a valid path.")
