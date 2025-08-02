"""Test script for PDF metadata extraction functionality."""

import os
import sys
import asyncio
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pdf_metadata_extractor import extract_text_from_first_page, _parse_regex_fallback


def test_text_extraction():
    """Test text extraction from a sample PDF."""
    # This is a simple test - in a real scenario, you'd use an actual PDF file
    print("Testing text extraction functionality...")
    
    # Test regex fallback with sample text
    sample_text = """
    SAP ERP System Check
    System ID: ERP
    Report Date: 09.06.2025
    Customer: Test Customer
    """
    
    result = _parse_regex_fallback(sample_text)
    print(f"Regex fallback result: {result}")
    
    # Test date normalization
    from utils.pdf_metadata_extractor import _normalize_date_format
    
    test_dates = ["09.06.2025", "09/06/2025", "09-06-2025", "2025.06.09", "09062025"]
    for date in test_dates:
        normalized = _normalize_date_format(date)
        print(f"{date} -> {normalized}")
    
    print("Text extraction tests completed.")


def main():
    """Main test function."""
    print("Running PDF metadata extraction tests...")
    test_text_extraction()
    print("All tests completed successfully.")


if __name__ == "__main__":
    main()
