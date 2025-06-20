"""Utility functions for converting EWA summary JSON into Markdown for human-friendly viewing."""
from typing import Dict, Any, List

__all__ = ["json_to_markdown"]

def _format_table(headers: List[str], rows: List[List[str]]) -> List[str]:
    """Helper to format a Markdown table."""
    md = []
    md.append(f"| {' | '.join(headers)} |")
    md.append(f"|{'|'.join(['---'] * len(headers))}|")
    for row in rows:
        # Ensure all items in a row are strings and handle None gracefully
        md.append(f"| {' | '.join(str(x) if x is not None else 'N/A' for x in row)} |")
    return md

def _array_to_markdown_table(array: List[Dict[str, Any]], section_name: str = None) -> List[str]:
    md = []
    if section_name:
        md.append(f"## {section_name}")
    if not array:
        md.append(f"No {section_name.lower() if section_name else 'data'} provided.")
        return md
    # Collect all unique keys from all items for header
    all_keys = set()
    for item in array:
        all_keys.update(item.keys())
    headers = [str(k) for k in all_keys]
    rows = []
    for item in array:
        row = []
        for k in headers:
            v = item.get(k, 'N/A')
            # Format dicts for display
            if isinstance(v, dict):
                # Special formatting for estimatedEffort or similar objects
                if set(v.keys()) == {'analysis', 'implementation'}:
                    v = f"Analysis: {v.get('analysis', 'N/A')}, Implementation: {v.get('implementation', 'N/A')}"
                else:
                    v = ', '.join(f"{k}: {val}" for k, val in v.items()) if v else 'N/A'
            elif isinstance(v, list):
                v = ', '.join(str(x) for x in v) if v else 'N/A'
            row.append(str(v))
        rows.append(row)
    md.extend(_format_table(headers, rows))
    md.append("")
    return md

def json_to_markdown(data: Dict[str, Any]) -> str:
    """Converts the validated EWA summary JSON (v2.0) to a Markdown string."""
    md = []
    meta = data.get('system_metadata', {})
    md.append(f"# EWA Analysis for {meta.get('system_id', 'N/A')} ({meta.get('report_date', 'N/A')})")
    md.append(f"**Analysis Period:** {meta.get('analysis_period', 'N/A')}")
    md.append(f"**Overall Risk Assessment:** `{data.get('overall_risk', 'N/A')}`")
    md.append("\n---\n")

    # --- System Health Overview ---
    md.append("## System Health Overview")
    health = data.get('system_health_overview', {})
    if health:
        rows = [[k.capitalize(), v] for k, v in health.items() if v is not None] # Filter out None values
        if rows:
            md.extend(_format_table(["Area", "Status"], rows))
        else:
            md.append("No health overview data provided.")
    else:
        md.append("No health overview provided.")
    md.append("\n---\n")

    # --- Executive Summary ---
    md.append("## Executive Summary")
    md.append(data.get('executive_summary', 'No summary provided.'))
    md.append("\n---\n")

    # --- Positive Findings ---
    md.extend(_array_to_markdown_table(data.get('positive_findings', []), 'Positive Findings'))
    md.append("\n---\n")

    # --- Key Findings ---
    md.append("## Key Findings")
    key_findings = data.get('key_findings', [])
    if key_findings:
        headers = ["Severity", "Area", "Finding", "Technical Impact", "Business Impact"]
        rows = []
        for f_item in key_findings: # Renamed f to f_item to avoid conflict with file open 'f'
            rows.append([
                f_item.get('severity', 'N/A'), 
                f_item.get('area', 'N/A'), 
                f_item.get('finding', 'N/A'), 
                f_item.get('impact', 'N/A'), 
                f_item.get('businessImpact', 'N/A')
            ])
        md.extend(_format_table(headers, rows))
    else:
        md.append("No key findings reported.")
    md.append("\n---\n")

    
    # --- Recommendations ---
    md.extend(_array_to_markdown_table(data.get('recommendations', []), 'Actionable Recommendations'))

    # --- Parameters Table ---
    md.extend(_array_to_markdown_table(data.get('parameters', []), 'Parameters Table'))
    md.append("\n---\n")

    # --- Quick Wins ---
    md.extend(_array_to_markdown_table(data.get('quickWins', []), 'Quick Wins'))

    # --- Trend Analysis ---
    md.append("## Trend Analysis")
    trends = data.get('trend_analysis', {})
    if trends:
        kpi_trends = trends.get('kpi_trends', [])
        if kpi_trends:
            md.append("### KPI Trends")
            headers = ["KPI Name", "Previous Value", "Current Value", "Change (%)"]
            rows = []
            for kpi_item in kpi_trends: # Renamed kpi to kpi_item
                rows.append([
                    kpi_item.get('kpi_name', 'N/A'),
                    kpi_item.get('previous_value', 'N/A'),
                    kpi_item.get('current_value', 'N/A'),
                    str(kpi_item.get('change_percentage', 'N/A')) # Ensure it's a string for table
                ])
            md.extend(_format_table(headers, rows))
            md.append("")
        
        md.append(f"- **Overall Performance Trend:** `{trends.get('performance_trend', 'N/A')}`")
        md.append(f"- **Overall Stability Trend:** `{trends.get('stability_trend', 'N/A')}`")
        md.append(f"- **Trend Summary:** {trends.get('summary', 'N/A')}")
    else:
        md.append("No trend analysis data provided.")
    md.append("\n---\n")

    # --- Capacity Outlook ---
    md.append("## Capacity Outlook")
    capacity = data.get('capacity_outlook', {})
    if capacity:
        md.append(f"- **Database Growth:** {capacity.get('database_growth', 'N/A')}")
        md.append(f"- **CPU Utilization:** {capacity.get('cpu_utilization', 'N/A')}")
        md.append(f"- **Memory Utilization:** {capacity.get('memory_utilization', 'N/A')}")
        md.append(f"- **Capacity Summary:** {capacity.get('summary', 'N/A')}")
    else:
        md.append("No capacity outlook data provided.")
    md.append("\n---\n")

    # --- Parameters Table ---
    md.extend(_array_to_markdown_table(data.get('parameters', []), 'Parameters Table'))
    md.append("\n---\n")

    # --- Benchmarking ---
    md.append("## Benchmarking")
    benchmarking = data.get('benchmarking', {})
    if benchmarking:
        md.append(f"- **Comparison:** {benchmarking.get('comparison', 'N/A')}")
        md.append(f"- **Summary:** {benchmarking.get('summary', 'N/A')}")
    else:
        md.append("No benchmarking data provided.")
    # md.append("\n---\n") # Removed last --- to avoid double separator if it's the last section

    return "\n".join(md)
