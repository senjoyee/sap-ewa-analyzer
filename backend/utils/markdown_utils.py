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
    md.append("## Positive Findings")
    positive_findings = data.get('positive_findings', [])
    if positive_findings:
        for finding in positive_findings:
            md.append(f"- **{finding.get('area', 'N/A')}:** {finding.get('description', 'N/A')}")
    else:
        md.append("No positive findings reported.")
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

    # --- Critical Issues ---
    md.append("## Critical Issues")
    critical_issues = data.get('critical_issues', [])
    if critical_issues:
        for issue in critical_issues:
            md.append(f"### `[{issue.get('severity', 'N/A')}]` {issue.get('title', 'N/A')} (ID: {issue.get('id', 'N/A')})")
            md.append(f"- **Area:** {issue.get('area', 'N/A')}")
            md.append(f"- **Description:** {issue.get('description', 'N/A')}")
            md.append(f"- **Likely Root Cause:** {issue.get('likely_root_cause', 'N/A')}")
            md.append(f"- **Business Impact:** {issue.get('businessImpact', 'N/A')}")
            notes_list = issue.get('suggested_sap_notes', [])
            notes = ", ".join(notes_list) if notes_list else 'N/A'
            md.append(f"- **Suggested SAP Notes:** {notes}")
            md.append("") # Spacer
    else:
        md.append("No critical issues reported.")
    md.append("\n---\n")
    
    # --- Helper function for formatting recommendations (used for Recommendations and Quick Wins) ---
    def _format_recommendation_details(recommendations_list: List[Dict[str, Any]], title: str) -> List[str]:
        rec_md = []
        rec_md.append(f"## {title}")
        if recommendations_list:
            for r_item in recommendations_list: # Renamed r to r_item
                rec_md.append(f"### `[{r_item.get('priority', 'N/A')}]` {r_item.get('action', 'No action text provided')} (ID: {r_item.get('recommendationId', 'N/A')})")
                effort = r_item.get('estimatedEffort', {})
                effort_analysis = effort.get('analysis', 'N/A')
                effort_impl = effort.get('implementation', 'N/A')
                rec_md.append(f"- **Estimated Effort:** Analysis: `{effort_analysis}`, Implementation: `{effort_impl}`")
                rec_md.append(f"- **Responsible Area:** {r_item.get('responsibleArea', 'N/A')}")
                if r_item.get('linkedIssueId'): # Check if linkedIssueId exists and is not empty
                    rec_md.append(f"- **Linked Critical Issue ID:** {r_item.get('linkedIssueId')}")
                rec_md.append(f"- **Validation Step:** {r_item.get('validationStep', 'N/A')}")
                rec_md.append(f"- **Preventative Action:** {r_item.get('preventativeAction', 'N/A')}")
                rec_md.append("") # Spacer
        else:
            rec_md.append(f"No {title.lower()} provided.")
        rec_md.append("\n---\n")
        return rec_md

    # --- Recommendations ---
    md.extend(_format_recommendation_details(data.get('recommendations', []), "Actionable Recommendations"))

    # --- Quick Wins ---
    md.extend(_format_recommendation_details(data.get('quickWins', []), "Quick Wins"))

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
