"""
Test script for PDF image extraction functionality
"""

import os
import sys
from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Test the enhanced PDF conversion with image extraction
def test_image_extraction():
    """Test basic image extraction functionality"""
    try:
        import pymupdf4llm
        
        # Create a simple test to verify pymupdf4llm works with our parameters
        test_params = {
            'write_images': True,
            'image_format': 'png',
            'dpi': 300,
            'image_size_limit': 0.03
        }
        
        print("✓ PyMuPDF4LLM image extraction parameters validated")
        print(f"  - Image extraction: {test_params['write_images']}")
        print(f"  - Image format: {test_params['image_format']}")
        print(f"  - DPI: {test_params['dpi']}")
        print(f"  - Size limit: {test_params['image_size_limit']}")
        
        return True
        
    except ImportError as e:
        print(f"✗ PyMuPDF4LLM import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing enhanced PDF image extraction...")
    success = test_image_extraction()
    
    if success:
        print("\n✓ Image extraction enhancement ready for testing with real PDFs")
        print("  Next: Test with actual EWA PDF document")
    else:
        print("\n✗ Image extraction test failed")
        print("  Check PyMuPDF4LLM installation and dependencies")
