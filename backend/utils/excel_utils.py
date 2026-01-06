"""
Excel export utilities for EWA analysis data.
Generates professionally formatted Excel workbooks from EWA JSON.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Border, Side, Alignment, NamedStyle
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


# SAP-inspired color palette
COLORS = {
    "sap_gold": "F0AB00",
    "sap_dark": "333333",
    "header_bg": "E5E5E5",
    "white": "FFFFFF",
    "light_gray": "F9F9F9",
    "border": "CCCCCC",
    "critical": "CC0000",
    "high": "E07000",
    "medium": "F0AB00",
    "low": "008000",
    "good": "008000",
    "fair": "E07000",
    "poor": "CC0000",
}


def _create_styles() -> Dict[str, NamedStyle]:
    """Create reusable named styles for the workbook."""
    styles = {}
    
    # Title style (for sheet titles)
    title_style = NamedStyle(name="title_style")
    title_style.font = Font(name="Calibri", size=16, bold=True, color=COLORS["sap_dark"])
    title_style.alignment = Alignment(horizontal="left", vertical="center")
    styles["title"] = title_style
    
    # Header style (for table headers)
    header_style = NamedStyle(name="header_style")
    header_style.font = Font(name="Calibri", size=11, bold=True, color=COLORS["sap_dark"])
    header_style.fill = PatternFill(start_color=COLORS["header_bg"], end_color=COLORS["header_bg"], fill_type="solid")
    header_style.border = Border(
        bottom=Side(style="medium", color=COLORS["sap_dark"]),
        left=Side(style="thin", color=COLORS["border"]),
        right=Side(style="thin", color=COLORS["border"]),
    )
    header_style.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    styles["header"] = header_style
    
    # Data cell style
    data_style = NamedStyle(name="data_style")
    data_style.font = Font(name="Calibri", size=10)
    data_style.border = Border(
        bottom=Side(style="thin", color=COLORS["border"]),
        left=Side(style="thin", color=COLORS["border"]),
        right=Side(style="thin", color=COLORS["border"]),
    )
    data_style.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    styles["data"] = data_style
    
    # Label style (for key-value pairs)
    label_style = NamedStyle(name="label_style")
    label_style.font = Font(name="Calibri", size=10, bold=True, color=COLORS["sap_dark"])
    label_style.alignment = Alignment(horizontal="left", vertical="top")
    styles["label"] = label_style
    
    # Value style
    value_style = NamedStyle(name="value_style")
    value_style.font = Font(name="Calibri", size=10)
    value_style.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    styles["value"] = value_style
    
    return styles


def _apply_header_style(cell, styles: Dict[str, NamedStyle]):
    """Apply header styling to a cell."""
    style = styles["header"]
    cell.font = style.font
    cell.fill = style.fill
    cell.border = style.border
    cell.alignment = style.alignment


def _apply_data_style(cell, styles: Dict[str, NamedStyle], alt_row: bool = False):
    """Apply data cell styling."""
    style = styles["data"]
    cell.font = style.font
    cell.border = style.border
    cell.alignment = style.alignment
    if alt_row:
        cell.fill = PatternFill(start_color=COLORS["light_gray"], end_color=COLORS["light_gray"], fill_type="solid")


def _get_severity_fill(severity: str) -> PatternFill:
    """Get fill color based on severity level."""
    severity_lower = severity.lower() if severity else ""
    color = COLORS.get(severity_lower, COLORS["medium"])
    return PatternFill(start_color=color, end_color=color, fill_type="solid")


def _get_status_fill(status: str) -> PatternFill:
    """Get fill color based on status (good/fair/poor)."""
    status_lower = status.lower() if status else ""
    color = COLORS.get(status_lower, COLORS["sap_gold"])
    return PatternFill(start_color=color, end_color=color, fill_type="solid")


def _auto_fit_columns(ws: Worksheet, min_width: int = 12, max_width: int = 60):
    """Auto-fit column widths based on content."""
    for column_cells in ws.columns:
        max_length = 0
        column = column_cells[0].column_letter
        for cell in column_cells:
            try:
                cell_value = str(cell.value) if cell.value else ""
                # Account for line breaks
                lines = cell_value.split("\n")
                max_line_length = max(len(line) for line in lines) if lines else 0
                max_length = max(max_length, max_line_length)
            except:
                pass
        adjusted_width = min(max(max_length + 2, min_width), max_width)
        ws.column_dimensions[column].width = adjusted_width


def _write_summary_sheet(ws: Worksheet, data: Dict[str, Any], styles: Dict[str, NamedStyle], customer_name: str = ""):
    """Write the Summary sheet with metadata and executive summary."""
    ws.title = "Summary"
    
    # Title
    ws["A1"] = "EWA Analysis Summary"
    ws["A1"].font = Font(name="Calibri", size=20, bold=True, color=COLORS["sap_gold"])
    ws.merge_cells("A1:D1")
    ws.row_dimensions[1].height = 30
    
    # System Metadata section
    ws["A3"] = "System Information"
    ws["A3"].font = Font(name="Calibri", size=14, bold=True, color=COLORS["sap_dark"])
    ws.merge_cells("A3:D3")
    
    meta = data.get("System Metadata", data.get("system_metadata", {})) or {}
    row = 4
    
    # Add customer name if provided
    if customer_name:
        ws[f"A{row}"] = "Customer"
        ws[f"A{row}"].font = styles["label"].font
        ws[f"B{row}"] = customer_name
        ws[f"B{row}"].font = styles["value"].font
        row += 1
    
    meta_fields = [
        ("System ID", meta.get("System ID", meta.get("system_id", "N/A"))),
        ("Report Date", meta.get("Report Date", meta.get("report_date", "N/A"))),
        ("Analysis Period", meta.get("Analysis Period", meta.get("analysis_period", "N/A"))),
    ]
    
    for label, value in meta_fields:
        ws[f"A{row}"] = label
        ws[f"A{row}"].font = styles["label"].font
        ws[f"B{row}"] = str(value)
        ws[f"B{row}"].font = styles["value"].font
        row += 1
    
    # Overall Risk
    row += 1
    ws[f"A{row}"] = "Overall Risk"
    ws[f"A{row}"].font = styles["label"].font
    overall_risk = data.get("Overall Risk", data.get("overall_risk", "N/A"))
    ws[f"B{row}"] = str(overall_risk).upper()
    ws[f"B{row}"].font = Font(name="Calibri", size=11, bold=True, color=COLORS["white"])
    ws[f"B{row}"].fill = _get_severity_fill(str(overall_risk))
    ws[f"B{row}"].alignment = Alignment(horizontal="center", vertical="center")
    row += 2
    
    # System Health Overview
    ws[f"A{row}"] = "System Health Overview"
    ws[f"A{row}"].font = Font(name="Calibri", size=14, bold=True, color=COLORS["sap_dark"])
    ws.merge_cells(f"A{row}:D{row}")
    row += 1
    
    health = data.get("System Health Overview", data.get("system_health_overview", {})) or {}
    health_areas = ["Performance", "Security", "Stability", "configuration", "Configuration"]
    
    for area in health_areas:
        status = health.get(area, health.get(area.lower()))
        if status:
            ws[f"A{row}"] = area.title()
            ws[f"A{row}"].font = styles["label"].font
            ws[f"B{row}"] = str(status).upper()
            ws[f"B{row}"].font = Font(name="Calibri", size=10, bold=True, color=COLORS["white"])
            ws[f"B{row}"].fill = _get_status_fill(str(status))
            ws[f"B{row}"].alignment = Alignment(horizontal="center", vertical="center")
            row += 1
    
    row += 1
    
    # Executive Summary
    ws[f"A{row}"] = "Executive Summary"
    ws[f"A{row}"].font = Font(name="Calibri", size=14, bold=True, color=COLORS["sap_dark"])
    ws.merge_cells(f"A{row}:D{row}")
    row += 1
    
    exec_summary = data.get("Executive Summary", data.get("executive_summary", ""))
    if exec_summary:
        ws[f"A{row}"] = exec_summary
        ws[f"A{row}"].font = styles["value"].font
        ws[f"A{row}"].alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        ws.merge_cells(f"A{row}:D{row}")
        ws.row_dimensions[row].height = max(60, len(exec_summary) // 3)
    
    # Set column widths
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 20


def _write_positive_findings_sheet(ws: Worksheet, data: Dict[str, Any], styles: Dict[str, NamedStyle]):
    """Write the Positive Findings sheet."""
    ws.title = "Positive Findings"
    
    findings = data.get("Positive Findings", data.get("positive_findings", [])) or []
    
    # Title
    ws["A1"] = "Positive Findings"
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=COLORS["sap_gold"])
    ws.merge_cells("A1:B1")
    ws.row_dimensions[1].height = 25
    
    if not findings:
        ws["A3"] = "No positive findings recorded."
        return
    
    # Headers
    headers = ["Area", "Description"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=header)
        _apply_header_style(cell, styles)
    
    # Data rows
    for row_idx, finding in enumerate(findings, 4):
        area = finding.get("Area", finding.get("area", ""))
        desc = finding.get("Description", finding.get("description", ""))
        
        cell_a = ws.cell(row=row_idx, column=1, value=area)
        cell_b = ws.cell(row=row_idx, column=2, value=desc)
        
        alt_row = (row_idx - 4) % 2 == 1
        _apply_data_style(cell_a, styles, alt_row)
        _apply_data_style(cell_b, styles, alt_row)
    
    # Column widths
    ws.column_dimensions["A"].width = 25
    ws.column_dimensions["B"].width = 80


def _write_key_findings_sheet(ws: Worksheet, data: Dict[str, Any], styles: Dict[str, NamedStyle]):
    """Write the Key Findings sheet."""
    ws.title = "Key Findings"
    
    findings = data.get("Key Findings", data.get("key_findings", [])) or []
    
    # Title
    ws["A1"] = "Key Findings"
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=COLORS["sap_gold"])
    ws.merge_cells("A1:G1")
    ws.row_dimensions[1].height = 25
    
    if not findings:
        ws["A3"] = "No key findings recorded."
        return
    
    # Headers
    headers = ["Issue ID", "Area", "Severity", "Finding", "Impact", "Business Impact", "Source"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=header)
        _apply_header_style(cell, styles)
    
    # Data rows
    for row_idx, finding in enumerate(findings, 4):
        values = [
            finding.get("Issue ID", finding.get("issue_id", "")),
            finding.get("Area", finding.get("area", "")),
            finding.get("Severity", finding.get("severity", "")),
            finding.get("Finding", finding.get("finding", "")),
            finding.get("Impact", finding.get("impact", "")),
            finding.get("Business impact", finding.get("business_impact", "")),
            finding.get("Source", finding.get("source", "")),
        ]
        
        alt_row = (row_idx - 4) % 2 == 1
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=str(value) if value else "")
            _apply_data_style(cell, styles, alt_row)
            
            # Apply severity coloring
            if col == 3 and value:  # Severity column
                cell.font = Font(name="Calibri", size=10, bold=True, color=COLORS["white"])
                cell.fill = _get_severity_fill(str(value))
                cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Set row height for wrapped text
        ws.row_dimensions[row_idx].height = 60
    
    # Column widths
    widths = [10, 20, 12, 50, 40, 40, 30]
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = width


def _write_recommendations_sheet(ws: Worksheet, data: Dict[str, Any], styles: Dict[str, NamedStyle]):
    """Write the Recommendations sheet."""
    ws.title = "Recommendations"
    
    recs = data.get("Recommendations", data.get("recommendations", [])) or []
    
    # Title
    ws["A1"] = "Recommendations"
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=COLORS["sap_gold"])
    ws.merge_cells("A1:G1")
    ws.row_dimensions[1].height = 25
    
    if not recs:
        ws["A3"] = "No recommendations recorded."
        return
    
    # Headers
    headers = [
        "Rec ID", "Linked Issue", "Responsible Area", 
        "Effort (Analysis)", "Effort (Impl)", "Action", "Preventative Action"
    ]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=header)
        _apply_header_style(cell, styles)
    
    # Data rows
    for row_idx, rec in enumerate(recs, 4):
        effort = rec.get("Estimated Effort", rec.get("estimated_effort", {})) or {}
        if isinstance(effort, str):
            effort_analysis = effort
            effort_impl = ""
        else:
            effort_analysis = effort.get("analysis", "")
            effort_impl = effort.get("implementation", "")
        
        values = [
            rec.get("Recommendation ID", rec.get("recommendation_id", "")),
            rec.get("Linked issue ID", rec.get("linked_issue_id", "")),
            rec.get("Responsible Area", rec.get("responsible_area", "")),
            effort_analysis,
            effort_impl,
            rec.get("Action", rec.get("action", "")),
            rec.get("Preventative Action", rec.get("preventative_action", "")),
        ]
        
        alt_row = (row_idx - 4) % 2 == 1
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=str(value) if value else "")
            _apply_data_style(cell, styles, alt_row)
        
        # Set row height for wrapped text
        ws.row_dimensions[row_idx].height = 80
    
    # Column widths
    widths = [10, 12, 25, 15, 15, 50, 50]
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = width


def _write_capacity_sheet(ws: Worksheet, data: Dict[str, Any], styles: Dict[str, NamedStyle]):
    """Write the Capacity Outlook sheet."""
    ws.title = "Capacity Outlook"
    
    capacity = data.get("Capacity Outlook", data.get("capacity_outlook", {})) or {}
    
    # Title
    ws["A1"] = "Capacity Outlook"
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=COLORS["sap_gold"])
    ws.merge_cells("A1:B1")
    ws.row_dimensions[1].height = 25
    
    if not capacity:
        ws["A3"] = "No capacity data available."
        return
    
    # Key-value pairs
    fields = [
        ("Database Growth", capacity.get("Database Growth", capacity.get("database_growth", "N/A"))),
        ("CPU Utilization", capacity.get("CPU Utilization", capacity.get("cpu_utilization", "N/A"))),
        ("Memory Utilization", capacity.get("Memory Utilization", capacity.get("memory_utilization", "N/A"))),
    ]
    
    row = 3
    for label, value in fields:
        ws[f"A{row}"] = label
        ws[f"A{row}"].font = styles["label"].font
        ws[f"B{row}"] = str(value) if value else "N/A"
        ws[f"B{row}"].font = styles["value"].font
        ws[f"B{row}"].alignment = Alignment(wrap_text=True)
        row += 1
    
    # Summary
    row += 1
    ws[f"A{row}"] = "Summary"
    ws[f"A{row}"].font = Font(name="Calibri", size=12, bold=True, color=COLORS["sap_dark"])
    row += 1
    
    summary = capacity.get("Summary", capacity.get("summary", ""))
    if summary:
        ws[f"A{row}"] = summary
        ws[f"A{row}"].font = styles["value"].font
        ws[f"A{row}"].alignment = Alignment(wrap_text=True)
        ws.merge_cells(f"A{row}:B{row}")
        ws.row_dimensions[row].height = max(40, len(summary) // 2)
    
    # Column widths
    ws.column_dimensions["A"].width = 25
    ws.column_dimensions["B"].width = 80


def _write_chapters_sheet(ws: Worksheet, data: Dict[str, Any], styles: Dict[str, NamedStyle]):
    """Write the Chapters Reviewed sheet."""
    ws.title = "Chapters Reviewed"
    
    chapters = data.get("Chapters Reviewed", data.get("chapters_reviewed", [])) or []
    
    # Title
    ws["A1"] = "Chapters Reviewed"
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=COLORS["sap_gold"])
    ws.row_dimensions[1].height = 25
    
    if not chapters:
        ws["A3"] = "No chapters information available."
        return
    
    # List chapters
    for row_idx, chapter in enumerate(chapters, 3):
        cell = ws.cell(row=row_idx, column=1, value=f"• {chapter}")
        cell.font = styles["value"].font
    
    ws.column_dimensions["A"].width = 60


def json_to_excel(
    json_data: Dict[str, Any],
    customer_name: str = "",
) -> bytes:
    """
    Convert EWA analysis JSON to a formatted Excel workbook.
    
    Args:
        json_data: The EWA analysis JSON data
        customer_name: Optional customer name for the report
        
    Returns:
        Excel file as bytes
    """
    wb = Workbook()
    styles = _create_styles()
    
    # Register styles with workbook
    for style in styles.values():
        try:
            wb.add_named_style(style)
        except ValueError:
            pass  # Style already exists
    
    # Create sheets
    # Remove default sheet and create our own
    default_sheet = wb.active
    
    # 1. Summary sheet
    ws_summary = wb.create_sheet("Summary")
    _write_summary_sheet(ws_summary, json_data, styles, customer_name)
    
    # 2. Positive Findings
    ws_positive = wb.create_sheet("Positive Findings")
    _write_positive_findings_sheet(ws_positive, json_data, styles)
    
    # 3. Key Findings
    ws_findings = wb.create_sheet("Key Findings")
    _write_key_findings_sheet(ws_findings, json_data, styles)
    
    # 4. Recommendations
    ws_recs = wb.create_sheet("Recommendations")
    _write_recommendations_sheet(ws_recs, json_data, styles)
    
    # 5. Capacity Outlook
    ws_capacity = wb.create_sheet("Capacity Outlook")
    _write_capacity_sheet(ws_capacity, json_data, styles)
    
    # 6. Chapters Reviewed
    ws_chapters = wb.create_sheet("Chapters Reviewed")
    _write_chapters_sheet(ws_chapters, json_data, styles)
    
    # Remove the default sheet
    wb.remove(default_sheet)
    
    # Set Summary as active sheet
    wb.active = wb["Summary"]
    
    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return output.getvalue()
