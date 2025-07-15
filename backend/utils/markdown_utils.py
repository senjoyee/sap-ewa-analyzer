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
    md.append(f"|{'|'.join(['---'] * len(headers))}|")
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

    # Custom header order and wording for Recommendations
    if section_name == "Recommendations":
        headers = [
            "action",
            "estimated_effort",
            "linked_issue_id",
            "preventative_action",
            "priority",
            "recommendation_id",
            "responsible_area",
            "validation_step",
        ]
        header_labels = [
            "Action",
            "Estimated Effort",
            "Linked Issue ID",
            "Preventative Action",
            "Priority",
            "Recommendation ID",
            "Responsible Area",
            "Validation Step",
        ]
        rows: List[List[str]] = []
        for item in array:
            row = [str(item.get(h, "N/A")) for h in headers]
            rows.append(row)
        md.extend(_format_table(header_labels, rows))
        md.append("")
        return md

    # Default: Build deterministic header order
    headers = sorted({k for item in array for k in item.keys()})
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
    meta = data.get("system_metadata", {})
    md.append(
        f"# EWA Analysis for {meta.get('system_id', 'N/A')} "
        f"({meta.get('report_date', 'N/A')})"
    )
    md.append(f"**Analysis Period:** {meta.get('analysis_period', 'N/A')}")
    md.append(f"**Overall Risk Assessment:** `{data.get('overall_risk', 'N/A')}`")
    md.append("\n---\n")

    # ── System Health Overview ────────────────────────────────────────────────
    md.append("## System Health Overview")
    health = data.get("system_health_overview", {})
    if health:
        rows = [
            [k.replace("_", " ").title(), v] for k, v in health.items() if v is not None
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
    md.append(data.get("executive_summary", "No summary provided."))
    md.append("\n---\n")

    # ── Positive Findings ─────────────────────────────────────────────────────
    md.extend(_array_to_markdown_table(data.get("positive_findings", []), "Positive Findings"))
    md.append("\n---\n")

    # ── Key Findings ──────────────────────────────────────────────────────────
    md.append("## Key Findings")
    key_findings = data.get("key_findings", [])
    if key_findings:
        headers = ["id", "area", "finding", "impact", "business_impact", "severity"]
        rows = [[kf.get(h, "N/A") for h in headers] for kf in key_findings]
        md.extend(
            _format_table(
                [h.replace("_", " ").title() for h in headers],
                rows,
            )
        )
    else:
        md.append("No key findings reported.")
    md.append("\n---\n")

    # ── Recommendations ───────────────────────────────────────────────────────
    md.extend(_array_to_markdown_table(data.get("recommendations", []), "Recommendations"))

    # ── Parameters ────────────────────────────────────────────────────────────
    md.append("## Parameters")
    parameters = data.get("parameters", [])
    if parameters:
        headers = ["name", "area", "current_value", "recommended_value", "description"]
        rows = [[p.get(h, "N/A") for h in headers] for p in parameters]
        md.extend(_format_table([h.replace("_", " ").title() for h in headers], rows))
        md.append("")
    else:
        md.append("No parameters provided.")
        md.append("")
    md.append("\n---\n")


    # ── Key Performance Indicators ────────────────────────────────────────────
    md.append("## Key Performance Indicators")
    kpis = data.get("kpis", [])
    if kpis:
        for kpi in kpis:
            md.append(f"- {kpi}")
    else:
        md.append("No KPIs provided.")
    md.append("\n---\n")

    # ── Capacity Outlook ──────────────────────────────────────────────────────
    md.append("## Capacity Outlook")
    capacity = data.get("capacity_outlook", {})
    if capacity:
        md.append(f"- **Database Growth:** {capacity.get('database_growth', 'N/A')}")
        md.append(f"- **CPU Utilization:** {capacity.get('cpu_utilization', 'N/A')}")
        md.append(f"- **Memory Utilization:** {capacity.get('memory_utilization', 'N/A')}")
        md.append(f"- **Capacity Summary:** {capacity.get('summary', 'N/A')}")
    else:
        md.append("No capacity outlook data provided.")


    # ── Done ─────────────────────────────────────────────────────────────────
    return "\n".join(md)