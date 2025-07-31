"""
Utility functions for converting a validated EWA summary JSON
(schema v1.1, god_level_ewa_analysis) into human-friendly Markdown.
"""
from typing import Dict, Any, List

__all__ = ["json_to_markdown"]


# ────────────────────────────────────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────────────────────────────────────
def _format_table(headers: List[str], rows: List[List[str]]) -> List[str]:
    """Return a list of Markdown lines that render a table."""
    md: List[str] = []
    md.append(f"| {' | '.join(headers)} |")
    md.append(f"| {'|'.join(['---'] * len(headers))} |")
    for row in rows:
        md.append(f"| {' | '.join(str(x) if x is not None else 'N/A' for x in row)} |")
    return md


def _array_to_markdown_table(
    array: List[Dict[str, Any]], section_name: str | None = None
) -> List[str]:
    """
    Generic helper to turn an array of dicts into a Markdown table.

    • Flattens nested dicts that match {'analysis','implementation'}.
    • If the array is empty, prints an informational line instead.
    """
    md: List[str] = []
    if section_name:
        md.append(f"## {section_name}")

    if not array:
        md.append(f"No {section_name.lower() if section_name else 'data'} provided.")
        return md

    # Render columns in the order they appear in the first JSON object for all sections, including Recommendations.
    if not array:
        md.append(f"No {section_name.lower() if section_name else 'data'} provided.")
        return md

    headers = list(array[0].keys())
    rows: List[List[str]] = []
    for item in array:
        row: List[str] = []
        for k in headers:
            v = item.get(k, "N/A")
            if isinstance(v, dict):
                v = ", ".join(f"{dk}: {dv}" for dk, dv in v.items()) if v else "N/A"
            elif isinstance(v, list):
                v = ", ".join(str(x) for x in v) if v else "N/A"
            row.append(str(v))
        rows.append(row)
    md.extend(_format_table(headers, rows))
    md.append("")
    return md

    rows: List[List[str]] = []
    for item in array:
        row: List[str] = []
        for k in headers:
            v = item.get(k, "N/A")
            if isinstance(v, dict):
                # Special-case estimated_effort
                if set(v.keys()) == {"analysis", "implementation"}:
                    v = (
                        f"Analysis: {v.get('analysis', 'N/A')}, "
                        f"Implementation: {v.get('implementation', 'N/A')}"
                    )
                else:
                    v = ", ".join(f"{dk}: {dv}" for dk, dv in v.items()) if v else "N/A"
            elif isinstance(v, list):
                v = ", ".join(str(x) for x in v) if v else "N/A"
            row.append(str(v))
        rows.append(row)

    md.extend(_format_table(headers, rows))
    md.append("")
    return md


# ────────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────────
def json_to_markdown(data: Dict[str, Any]) -> str:
    """
    Convert an EWA JSON document (validated against schema v1.1)
    into a Markdown report suitable for rendering in the UI.
    """
    md: List[str] = []

    # ── Metadata & Header ───────────────────────────────────────────────────────
    meta = data.get("System Metadata", {})
    md.append(
        f"# EWA Analysis for {meta.get('System ID', 'N/A')} "
        f"({meta.get('Report Date', 'N/A')})"
    )
    md.append(f"**Analysis Period:** {meta.get('Analysis Period', 'N/A')}")
    md.append(f"**Overall Risk Assessment:** `{data.get('Overall Risk', data.get('overall_risk', 'N/A'))}`")
    md.append("\n---\n")

    # ── System Health Overview ────────────────────────────────────────────────
    md.append("## System Health Overview")
    health = data.get("System Health Overview", {})
    if health:
        rows = [
            [k, v] for k, v in health.items() if v is not None
        ]
        if rows:
            md.extend(_format_table(["Area", "Status"], rows))
        else:
            md.append("No health overview data provided.")
    else:
        md.append("No health overview provided.")
    md.append("\n---\n")

    # ── Executive Summary ──────────────────────────────────────────────────────
    md.append("## Executive Summary")
    md.append(data.get("Executive Summary", "No summary provided."))
    md.append("\n---\n")

    # ── Positive Findings ─────────────────────────────────────────────────────
    md.extend(_array_to_markdown_table(data.get("Positive Findings", []), "Positive Findings"))
    md.append("\n---\n")

    # ── Key Findings ──────────────────────────────────────────────────────────
    md.extend(_array_to_markdown_table(data.get("Key Findings", []), "Key Findings"))
    md.append("\n---\n")


    # ── Recommendations ───────────────────────────────────────────────────────
    md.extend(_array_to_markdown_table(data.get("Recommendations", []), "Recommendations"))

    # ── Parameters ────────────────────────────────────────────────────────────
    md.append("## Parameters")
    parameters = data.get("Parameters", [])
    if parameters:
        headers = ["Name", "Area", "Current Value", "Recommended Value", "Description"]
        rows = [[p.get(h, "N/A") for h in headers] for p in parameters]
        md.extend(_format_table(headers, rows))
        md.append("")
    else:
        md.append("No parameters provided.")
        md.append("")
    md.append("\n---\n")


    # ── Key Performance Indicators ────────────────────────────────────────────
    md.append("## Key Performance Indicators")
    # Look for KPIs under correct key from deterministic extraction
    kpis = data.get("key_performance_indicators", data.get("KPIs", []))
    if kpis and isinstance(kpis, list) and len(kpis) > 0:
        # Check if KPIs have structured format with trend information
        if isinstance(kpis[0], dict):
            # Render structured KPIs with trends in table format
            headers = ["KPI", "Current Value", "Trend", "Description"]
            rows = []
            for kpi in kpis:
                name = kpi.get('name', 'N/A')
                current_value = kpi.get('current_value', 'N/A')
                trend_info = kpi.get('trend', {})
                trend_direction = trend_info.get('direction', 'N/A')
                trend_description = trend_info.get('description', 'N/A')
                
                # Format trend direction with emoji
                trend_display = {
                    'up': '↗️ Up',
                    'down': '↘️ Down', 
                    'flat': '➡️ Flat',
                    'none': '➖ None'
                }.get(trend_direction, trend_direction)
                
                rows.append([name, current_value, trend_display, trend_description])
            
            md.extend(_format_table(headers, rows))
        else:
            # Fallback for simple string KPIs
            for kpi in kpis:
                md.append(f"- {kpi}")
    else:
        md.append("No KPIs provided.")
    md.append("\n---\n")

    # ── Capacity Outlook ──────────────────────────────────────────────────────
    md.append("## Capacity Outlook")
    capacity = data.get("Capacity Outlook", {})
    if capacity:
        md.append(f"- **Database Growth:** {capacity.get('Database Growth', 'N/A')}")
        md.append(f"- **CPU Utilization:** {capacity.get('CPU Utilization', 'N/A')}")
        md.append(f"- **Memory Utilization:** {capacity.get('Memory Utilization', 'N/A')}")
        md.append(f"- **Capacity Summary:** {capacity.get('Summary', 'N/A')}")
    else:
        md.append("No capacity outlook data provided.")


    # ── Done ─────────────────────────────────────────────────────────────────
    return "\n".join(md)