
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from markdown2 import markdown

def _enhanced_markdown_to_html(markdown_text: str):
    """Convert markdown to HTML with enhanced styling and structure."""
    
    # Convert markdown to HTML with enhanced features
    html_body = markdown(
        markdown_text,
        extras=[
            "tables", "fenced-code-blocks", "header-ids", "toc", 
            "strike", "task_list", "break-on-newline"
        ]
    )
    
    # Enhanced CSS styling for professional appearance
    enhanced_css = """
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=72:wght@300;400;600;700&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        
        body { color: #333; }
    """
    
    return enhanced_css, html_body

from utils.markdown_utils import json_to_markdown

if __name__ == "__main__":
    sample_data = {
        "System Metadata": {
            "System ID": "TEST",
            "Report Date": "24.11.2025"
        },
        "Executive Summary": "This is a summary.",
        "Key Findings": [
            {
                "Issue ID": "001",
                "Area": "Security",
                "Severity": "High",
                "Finding": "Issue found"
            }
        ]
    }
    
    print("Testing json_to_markdown...")
    md = json_to_markdown(sample_data, pdf_export=True)
    print(f"Markdown Length: {len(md)}")
    print("Markdown Content:")
    print(md)
    
    print("\nTesting _enhanced_markdown_to_html...")
    css, html = _enhanced_markdown_to_html(md)
    print(f"CSS Length: {len(css)}")
    print(f"HTML Length: {len(html)}")
    print("HTML Content:")
    print(html)
