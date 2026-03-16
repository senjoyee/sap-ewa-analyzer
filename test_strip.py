import sys
import os
import json

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from backend.workflow_orchestrator import EWAWorkflowOrchestrator
from backend.utils.markdown_utils import json_to_markdown

def test_strip():
    orch = EWAWorkflowOrchestrator.__new__(EWAWorkflowOrchestrator) # bypass init
    
    # Sample data with markdown
    sample_data = {
        "Executive Summary": "This is a **summary** with *italics*.",
        "System Health Overview": {
            "Status": "The status is **OK**."
        },
        "Positive Findings": [
            {
                "Finding": "Everything is **good**."
            }
        ],
        "Key Findings": [
            {
                "Finding": "Found an *issue*."
            }
        ]
    }
    
    print("Testing _strip_markdown_wrappers_recursive...")
    stripped = orch._strip_markdown_wrappers_recursive(sample_data)
    print("Stripped:", json.dumps(stripped, indent=2))
    
    print("\nTesting json_to_markdown...")
    try:
        md = json_to_markdown(sample_data)
        print("Markdown length:", len(md))
    except Exception as e:
        print("json_to_markdown failed on original:", e)
        
    try:
        md = json_to_markdown(stripped)
        print("Markdown length (stripped):", len(md))
    except Exception as e:
        print("json_to_markdown failed on stripped:", e)

    # Test with list
    print("\nTesting with list...")
    sample_list = ["**bold**", {"nested": "*italics*"}]
    stripped_list = orch._strip_markdown_wrappers_recursive(sample_list)
    print("Stripped list:", stripped_list)

    # Test with Error Sentinel
    print("\nTesting with Error Sentinel...")
    error_sentinel = {
        "_parse_error": "Failed to parse JSON from response",
        "raw_arguments": "This is a **raw** argument."
    }
    stripped_error = orch._strip_markdown_wrappers_recursive(error_sentinel)
    print("Stripped error:", stripped_error)
    
if __name__ == "__main__":
    # Mocking EWAWorkflowOrchestrator.__init__ dependencies or avoiding them
    test_strip()
