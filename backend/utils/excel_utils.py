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
from openpyxl.worksheet.datavalidation import DataValidation


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
    data_style.font = Font(name="Calibri", size=11)
    data_style.border = Border(
        bottom=Side(style="thin", color=COLORS["border"]),
        left=Side(style="thin", color=COLORS["border"]),
        right=Side(style="thin", color=COLORS["border"]),
    )
    data_style.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    styles["data"] = data_style
    
    # Label style (for key-value pairs)
    label_style = NamedStyle(name="label_style")
    label_style.font = Font(name="Calibri", size=11, bold=True, color=COLORS["sap_dark"])
    label_style.alignment = Alignment(horizontal="left", vertical="top")
    styles["label"] = label_style
    
    # Value style
    value_style = NamedStyle(name="value_style")
    value_style.font = Font(name="Calibri", size=11)
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
    # Deduplicate configuration entry
    health_areas = ["Performance", "Security", "Stability", "Configuration"]
    
    for area in health_areas:
        status = health.get(area, health.get(area.lower()))
        if status:
            ws[f"A{row}"] = area.title()
            ws[f"A{row}"].font = styles["label"].font
            ws[f"B{row}"] = str(status).upper()
            ws[f"B{row}"].font = Font(name="Calibri", size=11, bold=True, color=COLORS["white"])
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
    
    summary_groups = _group_positive_findings(findings)
    current_row = 3

    if summary_groups:
        ws[f"A{current_row}"] = "Summary by Area"
        ws[f"A{current_row}"].font = Font(name="Calibri", size=12, bold=True, color=COLORS["sap_dark"])
        ws.merge_cells(f"A{current_row}:B{current_row}")
        current_row += 1

        for area, descriptions in summary_groups:
            summary_text = "\n".join(f"- {desc}" for desc in descriptions)
            cell_a = ws.cell(row=current_row, column=1, value=area)
            cell_b = ws.cell(row=current_row, column=2, value=summary_text)

            cell_a.font = styles["label"].font
            _apply_data_style(cell_b, styles)
            cell_b.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            current_row += 1
    else:
        ws[f"A{current_row}"] = "No positive findings recorded."
        ws[f"A{current_row}"].font = styles["value"].font
        ws.merge_cells(f"A{current_row}:B{current_row}")
    
    # Column widths
    ws.column_dimensions["A"].width = 25
    ws.column_dimensions["B"].width = 80


def _group_positive_findings(findings: List[Dict[str, Any]]) -> List[tuple[str, List[str]]]:
    """Group positive findings by area while preserving order."""
    groups: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for item in findings:
        area_raw = item.get("Area", item.get("area", "")) or "General"
        area = str(area_raw).strip() or "General"
        key = area.lower()
        if key not in groups:
            groups[key] = {"label": area, "items": [], "seen": set()}
            order.append(key)

        desc_raw = item.get("Description", item.get("description", "")) or ""
        desc = str(desc_raw).strip()
        if desc:
            normalized = re.sub(r"\s+", " ", desc).strip().lower()
            if normalized and normalized not in groups[key]["seen"]:
                groups[key]["items"].append(desc)
                groups[key]["seen"].add(normalized)

    return [(groups[k]["label"], groups[k]["items"]) for k in order]


def _write_findings_and_recommendations_sheet(ws: Worksheet, data: Dict[str, Any], styles: Dict[str, NamedStyle]):
    """Write combined Findings & Recommendations sheet grouped by severity."""
    ws.title = "Findings & Actions"
    
    findings = data.get("Key Findings", data.get("key_findings", [])) or []
    recs = data.get("Recommendations", data.get("recommendations", [])) or []
    
    # Build lookup of recommendations by linked issue ID
    recs_by_issue = {}
    for rec in recs:
        linked_id = rec.get("Linked issue ID", rec.get("linked_issue_id", ""))
        if linked_id:
            if linked_id not in recs_by_issue:
                recs_by_issue[linked_id] = []
            recs_by_issue[linked_id].append(rec)
    
    # Title
    ws["A1"] = "Findings & Recommended Actions"
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=COLORS["sap_gold"])
    ws.merge_cells("A1:I1")
    ws.row_dimensions[1].height = 25
    
    if not findings:
        ws["A3"] = "No key findings recorded."
        return
    
    # Group findings by severity
    severity_order = ["critical", "high", "medium", "low"]
    grouped = {sev: [] for sev in severity_order}
    for finding in findings:
        sev = str(finding.get("Severity", finding.get("severity", "medium"))).lower()
        if sev not in grouped:
            sev = "medium"
        grouped[sev].append(finding)
    
    # Combined headers
    headers = [
        "Issue ID", "Area", "Finding", "Impact", "Business Impact", "Source",
        "Action", "Preventative Action", "Effort"
    ]
    
    current_row = 3
    group_ranges = {}
    
    for severity in severity_order:
        group_findings = grouped[severity]
        if not group_findings:
            continue
        
        # Severity group header row
        ws.cell(row=current_row, column=1, value=f"{severity.upper()} ({len(group_findings)})")
        ws.merge_cells(f"A{current_row}:I{current_row}")
        header_cell = ws[f"A{current_row}"]
        header_cell.font = Font(name="Calibri", size=12, bold=True, color=COLORS["white"])
        header_cell.fill = _get_severity_fill(severity)
        header_cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[current_row].height = 25
        current_row += 1
        
        # Column headers for this group
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col, value=header)
            _apply_header_style(cell, styles)
        current_row += 1
        
        # Data rows for this severity
        data_start_row = current_row
        for idx, finding in enumerate(group_findings):
            issue_id = finding.get("Issue ID", finding.get("issue_id", ""))
            
            # Get linked recommendations
            linked_recs = recs_by_issue.get(issue_id, [])
            if linked_recs:
                rec = linked_recs[0]  # Take first linked recommendation
                effort = rec.get("Estimated Effort", rec.get("estimated_effort", {})) or {}
                if isinstance(effort, str):
                    effort_str = effort
                else:
                    effort_str = f"Analysis: {effort.get('analysis', 'N/A')}, Impl: {effort.get('implementation', 'N/A')}"
                action = rec.get("Action", rec.get("action", ""))
                preventative = rec.get("Preventative Action", rec.get("preventative_action", ""))
            else:
                action = ""
                preventative = ""
                effort_str = ""
            
            values = [
                issue_id,
                finding.get("Area", finding.get("area", "")),
                finding.get("Finding", finding.get("finding", "")),
                finding.get("Impact", finding.get("impact", "")),
                finding.get("Business impact", finding.get("business_impact", "")),
                finding.get("Source", finding.get("source", "")),
                action,
                preventative,
                effort_str,
            ]
            
            alt_row = idx % 2 == 1
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=current_row, column=col, value=str(value) if value else "")
                _apply_data_style(cell, styles, alt_row)
            
            ws.row_dimensions[current_row].height = 70
            current_row += 1
        
        data_end_row = current_row - 1
        group_ranges[severity] = (data_start_row, data_end_row)
        
        # Add blank row between groups
        current_row += 1
    
    # Apply Excel outline grouping - Critical expanded, others collapsed
    ws.sheet_properties.outlinePr.summaryBelow = False
    for severity, (start, end) in group_ranges.items():
        if start <= end:
            ws.row_dimensions.group(start, end, outline_level=1, hidden=(severity != "critical"))
    
    # Column widths
    widths = [10, 18, 40, 30, 30, 25, 40, 40, 20]
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
    
    # List chapters (no bullet prefix)
    for row_idx, chapter in enumerate(chapters, 3):
        cell = ws.cell(row=row_idx, column=1, value=f"{chapter}")
        cell.font = styles["value"].font
    
    ws.column_dimensions["A"].width = 60


def _write_parameters_sheet(ws: Worksheet, parameters: List[Dict[str, Any]], styles: Dict[str, NamedStyle]):
    """Write the Parameter Changes sheet with all recommended parameter modifications."""
    ws.title = "Parameter Changes"
    
    # Title
    ws["A1"] = "Recommended Parameter Changes"
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=COLORS["sap_gold"])
    ws.merge_cells("A1:F1")
    ws.row_dimensions[1].height = 25
    
    if not parameters:
        ws["A3"] = "No parameter recommendations found in the report."
        return
    
    # Group parameters by area
    area_order = [
        "SAP HANA", "Database", "SAP Kernel", "Profile Parameters",
        "Application", "Memory/Buffer", "Operating System", "Network", "General"
    ]
    
    grouped = {}
    for param in parameters:
        area = param.get("area", "General")
        if area not in grouped:
            grouped[area] = []
        grouped[area].append(param)
    
    # Headers
    headers = ["Parameter Name", "Area", "Current Value", "Recommended Value", "Description", "Section"]
    
    current_row = 3
    
    # Write parameters grouped by area
    for area in area_order:
        if area not in grouped:
            continue
        
        area_params = grouped[area]
        
        # Area header row
        ws.cell(row=current_row, column=1, value=f"{area} ({len(area_params)} parameters)")
        ws.merge_cells(f"A{current_row}:F{current_row}")
        area_cell = ws[f"A{current_row}"]
        area_cell.font = Font(name="Calibri", size=12, bold=True, color=COLORS["white"])
        area_cell.fill = PatternFill(start_color=COLORS["sap_dark"], end_color=COLORS["sap_dark"], fill_type="solid")
        area_cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[current_row].height = 22
        current_row += 1
        
        # Column headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col, value=header)
            cell.font = Font(name="Calibri", size=11, bold=True, color=COLORS["sap_dark"])
            cell.fill = PatternFill(start_color=COLORS["header_bg"], end_color=COLORS["header_bg"], fill_type="solid")
            cell.border = Border(
                bottom=Side(style="medium", color=COLORS["sap_dark"]),
                left=Side(style="thin", color=COLORS["border"]),
                right=Side(style="thin", color=COLORS["border"]),
            )
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws.row_dimensions[current_row].height = 20
        current_row += 1
        
        # Data rows
        for idx, param in enumerate(area_params):
            values = [
                param.get("parameter_name", ""),
                param.get("area", ""),
                param.get("current_value", ""),
                param.get("recommended_value", ""),
                param.get("description", ""),
                param.get("section", ""),
            ]
            
            alt_row = idx % 2 == 1
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=current_row, column=col, value=str(value) if value else "")
                cell.font = Font(name="Calibri", size=11)
                cell.border = Border(
                    bottom=Side(style="thin", color=COLORS["border"]),
                    left=Side(style="thin", color=COLORS["border"]),
                    right=Side(style="thin", color=COLORS["border"]),
                )
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                if alt_row:
                    cell.fill = PatternFill(start_color=COLORS["light_gray"], end_color=COLORS["light_gray"], fill_type="solid")
                
                # Highlight recommended value column
                if col == 4 and value:  # Recommended Value column
                    cell.font = Font(name="Calibri", size=11, bold=True, color=COLORS["sap_dark"])
            
            ws.row_dimensions[current_row].height = 35
            current_row += 1
        
        # Blank row between groups
        current_row += 1
    
    # Handle any areas not in the predefined order
    for area, area_params in grouped.items():
        if area in area_order:
            continue
        
        # Area header row
        ws.cell(row=current_row, column=1, value=f"{area} ({len(area_params)} parameters)")
        ws.merge_cells(f"A{current_row}:F{current_row}")
        area_cell = ws[f"A{current_row}"]
        area_cell.font = Font(name="Calibri", size=12, bold=True, color=COLORS["white"])
        area_cell.fill = PatternFill(start_color=COLORS["sap_dark"], end_color=COLORS["sap_dark"], fill_type="solid")
        current_row += 1
        
        # Column headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col, value=header)
            cell.font = Font(name="Calibri", size=11, bold=True)
            cell.fill = PatternFill(start_color=COLORS["header_bg"], end_color=COLORS["header_bg"], fill_type="solid")
        current_row += 1
        
        # Data rows
        for param in area_params:
            values = [
                param.get("parameter_name", ""),
                param.get("area", ""),
                param.get("current_value", ""),
                param.get("recommended_value", ""),
                param.get("description", ""),
                param.get("section", ""),
            ]
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=current_row, column=col, value=str(value) if value else "")
                cell.font = Font(name="Calibri", size=11)
                cell.alignment = Alignment(wrap_text=True)
            current_row += 1
        
        current_row += 1
    
    # Column widths
    widths = [35, 18, 20, 20, 45, 30]
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = width


def json_to_excel(
    json_data: Dict[str, Any],
    customer_name: str = "",
    parameters: Optional[List[Dict[str, Any]]] = None,
) -> bytes:
    """
    Convert EWA analysis JSON to a formatted Excel workbook.
    
    Args:
        json_data: The EWA analysis JSON data
        customer_name: Optional customer name for the report
        parameters: Optional list of parameter recommendations extracted from markdown
        
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
    
    # 3. Findings & Actions (combined Key Findings + Recommendations)
    ws_findings = wb.create_sheet("Findings & Actions")
    _write_findings_and_recommendations_sheet(ws_findings, json_data, styles)
    
    # 4. Parameter Recommendations (if available)
    if parameters:
        ws_params = wb.create_sheet("Parameter Changes")
        _write_parameters_sheet(ws_params, parameters, styles)
    
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
