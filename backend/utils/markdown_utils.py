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
            if isinstance(v, dict):
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
        rows = [[k.capitalize(), v] for k, v in health.items() if v is not None]
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
        headers = ["Area", "Finding", "Impact", "Business Impact", "Severity"]
        rows = []
        for f_item in key_findings:
            rows.append([
                f_item.get('Area', 'N/A'),
                f_item.get('Finding', 'N/A'),
                f_item.get('Impact', 'N/A'),
                f_item.get('Business Impact', 'N/A'),
                f_item.get('Severity', 'N/A')
            ])
        md.extend(_format_table(headers, rows))
    else:
        md.append("No key findings reported.")
    md.append("\n---\n")

    # --- Recommendations ---
    md.extend(_array_to_markdown_table(data.get('recommendations', []), 'Recommendations'))

    # --- Parameters Table (custom columns) ---
    parameters = data.get('parameters', [])
    md.append("## Parameters")
    if parameters:
        headers = [
            "Name",
            "Area",
            "Current Value",
            "Recommended Value",
            "Description"
        ]
        rows = []
        for p in parameters:
            rows.append([
                p.get('Name', 'N/A'),
                p.get('Area', 'N/A'),
                p.get('Current Value', 'N/A'),
                p.get('Recommended Value', 'N/A'),
                p.get('Description', 'N/A')
            ])
        md.extend(_format_table(headers, rows))
        md.append("")
    else:
        md.append("No parameters provided.")
        md.append("")
    md.append("\n---\n")

    # --- Quick Wins ---
    md.extend(_array_to_markdown_table(data.get('quickWins', []), 'Quick Wins'))

    # --- Trend Analysis ---
    md.append("## Trend Analysis")
    trends = data.get('Trend Analysis', {}) or data.get('trend_analysis', {})
    if trends:
        kpi_trends = trends.get('KPI Trends', [])
        if kpi_trends:
            md.append("### KPI Trends")
            headers = ["KPI Name", "Previous Value", "Current Value", "Change Percentage"]
            rows = []
            for kpi_item in kpi_trends:
                rows.append([
                    kpi_item.get('KPI Name', 'N/A'),
                    kpi_item.get('Previous Value', 'N/A'),
                    kpi_item.get('Current Value', 'N/A'),
                    str(kpi_item.get('Change Percentage', 'N/A'))
                ])
            md.extend(_format_table(headers, rows))
            md.append("")
        md.append(f"- **Overall Performance Trend:** `{trends.get('Performance Trend', 'N/A')}`")
        md.append(f"- **Overall Stability Trend:** `{trends.get('Stability Trend', 'N/A')}`")
        md.append(f"- **Trend Summary:** {trends.get('Summary', 'N/A')}")
    else:
        md.append("No trend analysis data provided.")
    md.append("\n---\n")

    # --- Capacity Outlook ---
    md.append("## Capacity Outlook")
    capacity = data.get('Capacity Outlook', {})
    if capacity:
        md.append(f"- **Database Growth:** {capacity.get('Database Growth', 'N/A')}")
        md.append(f"- **CPU Utilization:** {capacity.get('CPU Utilization', 'N/A')}")
        md.append(f"- **Memory Utilization:** {capacity.get('Memory Utilization', 'N/A')}")
        md.append(f"- **Capacity Summary:** {capacity.get('Summary', 'N/A')}")
    else:
        md.append("No capacity outlook data provided.")
    md.append("\n---\n")

    # --- Benchmarking ---
    md.append("## Benchmarking")
    benchmarking = data.get('Benchmarking', {})
    if benchmarking:
        md.append(f"- **Comparison:** {benchmarking.get('Comparison', 'N/A')}")
        md.append(f"- **Summary:** {benchmarking.get('Summary', 'N/A')}")
    else:
        md.append("No benchmarking data provided.")

    return "\n".join(md)
