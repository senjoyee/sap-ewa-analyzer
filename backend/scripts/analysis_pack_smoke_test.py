import json
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, BACKEND_ROOT)

from utils.analysis_pack import build_analysis_pack
from utils.html_utils import json_to_html
from utils.markdown_utils import json_to_markdown


def main() -> int:
    markdown = """# SAP EarlyWatch Alert

## Overview
System ID: ERP
Report Date: 2025-06-09

## Configuration Parameters
| Parameter | Current | Recommended |
| --- | --- | --- |
| abap/heap_area_dia | 1 | 2 |
| rsdb/esm/buffersize_kb | 1024 | 2048 |

## Performance
Average dialog response time is elevated.
"""

    analysis_pack = build_analysis_pack(
        blob_name="ERP_09_Jun_25.pdf",
        markdown_content=markdown,
        metadata={"system_id": "ERP", "report_date": "2025-06-09"},
        check_overview_index={
            "rows": [
                {
                    "Topic": "Performance",
                    "Subtopic Rating": "Red",
                    "Subtopic": "High dialog response time",
                }
            ]
        },
    )

    assert analysis_pack["blob_name"] == "ERP_09_Jun_25.pdf"
    assert len(analysis_pack["sections"]) >= 3
    assert len(analysis_pack["parameter_sections"]) >= 1
    assert "abap/heap_area_dia" in analysis_pack["parameter_focus_markdown"]

    sample_json = {
        "Schema Version": "1.1",
        "System Metadata": {
            "System ID": "ERP",
            "Report Date": "2025-06-09",
            "Analysis Period": "2025-05-01 / 2025-05-31",
        },
        "Chapters Reviewed": ["Overview", "Configuration Parameters", "Performance"],
        "System Health Overview": {
            "Performance": "fair",
            "Security": "good",
            "Stability": "good",
            "configuration": "fair",
        },
        "Executive Summary": "- Performance needs improvement\n- Parameter tuning recommended",
        "Positive Findings": [
            {"Area": "Operations", "Description": "Backups are healthy"}
        ],
        "Key Findings": [
            {
                "Issue ID": "KF-01",
                "Area": "Performance",
                "Finding": "High dialog response time",
                "Impact": "Slow transactions",
                "Business impact": "User productivity degradation",
                "Severity": "high",
                "Source": "Check Overview",
            }
        ],
        "Recommendations": [
            {
                "Recommendation ID": "REC-01",
                "Estimated Effort": {"analysis": "low", "implementation": "medium"},
                "Responsible Area": "SAP Basis Team",
                "Linked issue ID": "KF-01",
                "Action": "- Tune work process memory",
                "Preventative Action": "- Review workload monthly",
            }
        ],
        "Parameter Recommendations": {
            "parameters": [
                {
                    "parameter_name": "abap/heap_area_dia",
                    "area": "Application",
                    "current_value": "1",
                    "recommended_value": "2",
                    "action_status": "Change Required",
                    "priority": "High",
                    "description": "Increase dialog heap area",
                    "source_section": "Configuration Parameters",
                }
            ],
            "extraction_notes": "",
            "summary": {
                "total": 1,
                "by_action_status": {
                    "Change Required": 1,
                    "Verify": 0,
                    "No Action": 0,
                    "Monitor": 0,
                },
                "by_priority": {
                    "High": 1,
                    "Medium": 0,
                    "Low": 0,
                },
                "actionable": 1,
            },
        },
        "Capacity Outlook": {
            "Database Growth": "Stable",
            "CPU Utilization": "Moderate",
            "Memory Utilization": "Moderate",
            "Summary": "Stable",
        },
        "Overall Risk": "medium",
    }

    markdown_output = json_to_markdown(sample_json)
    html_output = json_to_html(sample_json, include_cover_page=False)

    assert "Parameter Recommendations" in markdown_output
    assert "abap/heap_area_dia" in markdown_output
    assert "Parameter Recommendations" in html_output
    assert "abap/heap_area_dia" in html_output

    print(json.dumps({
        "analysis_pack_sections": len(analysis_pack["sections"]),
        "parameter_sections": len(analysis_pack["parameter_sections"]),
        "parameter_candidates": len(analysis_pack.get("parameter_candidates", [])),
        "markdown_render_ok": True,
        "html_render_ok": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
