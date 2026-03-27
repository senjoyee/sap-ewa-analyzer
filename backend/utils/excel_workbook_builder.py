"""7-tab Excel workbook builder for the V2 agentic pipeline.

Produces: Executive Summary + 6 domain tabs (Security, Database, Performance,
Basis, Business, Lifecycle). Each domain tab has 4 sections: Findings,
Parameters, Deep Thinker Supplements, and Abstentions.
"""
from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from agent.specialist_agents import DomainResult
from agent.deep_thinker_agent import SupplementalFinding

logger = logging.getLogger(__name__)

# SAP-inspired color palette (shared with excel_utils.py)
COLORS = {
    "sap_gold": "F0AB00",
    "sap_dark": "333333",
    "header_bg": "E5E5E5",
    "white": "FFFFFF",
    "light_gray": "F9F9F9",
    "border": "CCCCCC",
    "red": "CC0000",
    "yellow": "E07000",
    "implicit": "6868AC",
    "green": "008000",
    "section_bg": "D6DCE4",
}

DOMAIN_DISPLAY_NAMES: dict[str, str] = {
    "security": "Security",
    "database": "Database",
    "performance": "Performance",
    "basis": "Basis",
    "business": "Business",
    "lifecycle": "Lifecycle",
}

DOMAIN_TAB_ORDER = ["security", "database", "performance", "basis", "business", "lifecycle"]

# Shared styling helpers
_HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="333333")
_HEADER_FILL = PatternFill(start_color="E5E5E5", end_color="E5E5E5", fill_type="solid")
_HEADER_BORDER = Border(
    bottom=Side(style="medium", color="333333"),
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
)
_DATA_BORDER = Border(
    bottom=Side(style="thin", color="CCCCCC"),
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
)
_WRAP_ALIGNMENT = Alignment(horizontal="left", vertical="top", wrap_text=True)


def build_workbook(
    domain_results: list[DomainResult],
    supplemental_findings: list[SupplementalFinding],
    system_metadata: dict[str, str] | None = None,
) -> bytes:
    """Build a 7-tab Excel workbook from pipeline outputs.

    Returns xlsx bytes ready for blob storage.
    """
    wb = Workbook()
    metadata = system_metadata or {}

    # Index results by domain
    results_by_domain: dict[str, DomainResult] = {}
    for dr in domain_results:
        results_by_domain[dr.domain] = dr

    # Index supplemental findings by domain
    supplements_by_domain: dict[str, list[dict[str, Any]]] = {d: [] for d in DOMAIN_TAB_ORDER}
    for sf in supplemental_findings:
        d = sf.domain if isinstance(sf, SupplementalFinding) else sf.get("domain", "")
        sd = sf.to_dict() if isinstance(sf, SupplementalFinding) else sf
        if d in supplements_by_domain:
            supplements_by_domain[d].append(sd)

    # Tab 1: Executive Summary
    ws_exec = wb.active
    _write_executive_summary(ws_exec, results_by_domain, supplemental_findings, metadata)

    # Tabs 2-7: Domain tabs
    for domain in DOMAIN_TAB_ORDER:
        ws = wb.create_sheet(title=DOMAIN_DISPLAY_NAMES[domain])
        dr = results_by_domain.get(domain, DomainResult(domain=domain))
        sups = supplements_by_domain.get(domain, [])
        _write_domain_tab(ws, dr, sups, domain)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Executive Summary Tab
# ---------------------------------------------------------------------------

def _write_executive_summary(
    ws: Worksheet,
    results_by_domain: dict[str, DomainResult],
    supplemental_findings: list[SupplementalFinding],
    metadata: dict[str, str],
):
    ws.title = "Executive Summary"

    # Title
    ws["A1"] = "EWA Workbook — Executive Summary"
    ws["A1"].font = Font(name="Calibri", size=20, bold=True, color=COLORS["sap_gold"])
    ws.merge_cells("A1:F1")
    ws.row_dimensions[1].height = 30

    # System Metadata
    row = 3
    ws[f"A{row}"] = "System Information"
    ws[f"A{row}"].font = Font(name="Calibri", size=14, bold=True, color=COLORS["sap_dark"])
    ws.merge_cells(f"A{row}:F{row}")
    row += 1

    for label, key in [("System ID", "system_id"), ("Report Date", "report_date"), ("Analysis Period", "analysis_period")]:
        val = metadata.get(key, metadata.get(label, ""))
        if val:
            ws[f"A{row}"] = label
            ws[f"A{row}"].font = Font(name="Calibri", size=11, bold=True, color=COLORS["sap_dark"])
            ws[f"B{row}"] = str(val)
            row += 1
    row += 1

    # Domain RAG Status Matrix
    ws[f"A{row}"] = "Domain Overview"
    ws[f"A{row}"].font = Font(name="Calibri", size=14, bold=True, color=COLORS["sap_dark"])
    ws.merge_cells(f"A{row}:F{row}")
    row += 1

    matrix_headers = ["Domain", "RED Findings", "YELLOW Findings", "Parameters", "Deep Thinker", "Abstentions"]
    for col_idx, header in enumerate(matrix_headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        _apply_header(cell)
    row += 1

    for domain in DOMAIN_TAB_ORDER:
        dr = results_by_domain.get(domain, DomainResult(domain=domain))
        red_count = sum(1 for f in dr.findings if f.get("rag_status") == "red")
        yellow_count = sum(1 for f in dr.findings if f.get("rag_status") == "yellow")
        param_count = len(dr.parameters)
        sup_count = sum(1 for sf in supplemental_findings
                        if (sf.domain if isinstance(sf, SupplementalFinding) else sf.get("domain", "")) == domain)
        abstention_count = len(dr.abstentions)

        values = [DOMAIN_DISPLAY_NAMES.get(domain, domain), red_count, yellow_count, param_count, sup_count, abstention_count]
        for col_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=row, column=col_idx, value=val)
            _apply_data(cell, row)
            # Color the domain name cell based on worst status
            if col_idx == 1:
                cell.font = Font(name="Calibri", size=11, bold=True)
            elif col_idx == 2 and val > 0:
                cell.font = Font(name="Calibri", size=11, bold=True, color=COLORS["red"])
            elif col_idx == 3 and val > 0:
                cell.font = Font(name="Calibri", size=11, bold=True, color=COLORS["yellow"])
        row += 1
    row += 1

    # Top 5 Risks
    ws[f"A{row}"] = "Top Risks"
    ws[f"A{row}"].font = Font(name="Calibri", size=14, bold=True, color=COLORS["sap_dark"])
    ws.merge_cells(f"A{row}:F{row}")
    row += 1

    # Collect all findings across domains, sort by severity
    all_findings: list[tuple[str, dict]] = []
    for domain in DOMAIN_TAB_ORDER:
        dr = results_by_domain.get(domain, DomainResult(domain=domain))
        for f in dr.findings:
            all_findings.append((domain, f))

    # Sort: red first, then yellow
    all_findings.sort(key=lambda x: 0 if x[1].get("rag_status") == "red" else 1)

    risk_headers = ["ID", "Domain", "Title", "RAG", "Impact", "Source Chapter"]
    for col_idx, header in enumerate(risk_headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        _apply_header(cell)
    row += 1

    for domain, finding in all_findings[:5]:
        vals = [
            finding.get("finding_id", ""),
            DOMAIN_DISPLAY_NAMES.get(domain, domain),
            finding.get("title", ""),
            finding.get("rag_status", "").upper(),
            finding.get("impact", ""),
            finding.get("source_chapter", ""),
        ]
        for col_idx, val in enumerate(vals, start=1):
            cell = ws.cell(row=row, column=col_idx, value=val)
            _apply_data(cell, row)
            if col_idx == 4:
                _color_rag(cell, val)
        row += 1

    # Deep Thinker Highlights
    if supplemental_findings:
        row += 1
        ws[f"A{row}"] = "AI Deep Analysis Highlights"
        ws[f"A{row}"].font = Font(name="Calibri", size=14, bold=True, color=COLORS["sap_dark"])
        ws.merge_cells(f"A{row}:F{row}")
        row += 1

        dt_headers = ["ID", "Domain", "Title", "Description", "Rationale", ""]
        for col_idx, header in enumerate(dt_headers, start=1):
            if header:
                cell = ws.cell(row=row, column=col_idx, value=header)
                _apply_header(cell)
        row += 1

        for sf in supplemental_findings[:3]:
            sd = sf.to_dict() if isinstance(sf, SupplementalFinding) else sf
            vals = [
                sd.get("finding_id", ""),
                DOMAIN_DISPLAY_NAMES.get(sd.get("domain", ""), sd.get("domain", "")),
                sd.get("title", ""),
                sd.get("description", ""),
                sd.get("rationale", ""),
            ]
            for col_idx, val in enumerate(vals, start=1):
                cell = ws.cell(row=row, column=col_idx, value=val)
                _apply_data(cell, row)
            row += 1

    _auto_fit(ws)


# ---------------------------------------------------------------------------
# Domain Tab
# ---------------------------------------------------------------------------

def _write_domain_tab(
    ws: Worksheet,
    dr: DomainResult,
    supplements: list[dict[str, Any]],
    domain: str,
):
    display_name = DOMAIN_DISPLAY_NAMES.get(domain, domain)
    row = 1

    # Title
    ws[f"A{row}"] = f"{display_name} — Domain Analysis"
    ws[f"A{row}"].font = Font(name="Calibri", size=18, bold=True, color=COLORS["sap_gold"])
    ws.merge_cells(f"A{row}:F{row}")
    ws.row_dimensions[row].height = 28
    row += 2

    # Section A: Findings
    row = _write_section_header(ws, row, "A — Findings (RED/YELLOW)")
    if dr.findings:
        headers = ["ID", "Source Chapter", "Title", "RAG", "Description", "Impact"]
        row = _write_table_headers(ws, row, headers)
        for finding in dr.findings:
            vals = [
                finding.get("finding_id", ""),
                finding.get("source_chapter", ""),
                finding.get("title", ""),
                finding.get("rag_status", "").upper(),
                finding.get("description", ""),
                finding.get("impact", ""),
            ]
            for col_idx, val in enumerate(vals, start=1):
                cell = ws.cell(row=row, column=col_idx, value=val)
                _apply_data(cell, row)
                if col_idx == 4:
                    _color_rag(cell, val)
            ws.row_dimensions[row].height = 60
            row += 1
    else:
        ws[f"A{row}"] = "No RED or YELLOW findings in this domain."
        ws[f"A{row}"].font = Font(name="Calibri", size=11, italic=True, color="666666")
        row += 1
    row += 1

    # Section B: Parameters
    row = _write_section_header(ws, row, "B — Parameters (RED/YELLOW)")
    if dr.parameters:
        headers = ["Parameter", "Current Value", "Recommended", "RAG", "Action", "Source Chapter"]
        row = _write_table_headers(ws, row, headers)
        for param in dr.parameters:
            vals = [
                param.get("param_name", ""),
                param.get("current_value", ""),
                param.get("recommended_value", ""),
                param.get("rag_status", "").upper(),
                param.get("action", ""),
                param.get("source_chapter", ""),
            ]
            for col_idx, val in enumerate(vals, start=1):
                cell = ws.cell(row=row, column=col_idx, value=val)
                _apply_data(cell, row)
                if col_idx == 4:
                    _color_rag(cell, val)
            row += 1
    else:
        ws[f"A{row}"] = "No flagged parameters in this domain."
        ws[f"A{row}"].font = Font(name="Calibri", size=11, italic=True, color="666666")
        row += 1
    row += 1

    # Section C: Deep Thinker Supplements
    row = _write_section_header(ws, row, "C — AI Deep Analysis (Implicit Risks)")
    if supplements:
        headers = ["ID", "Title", "Description", "Rationale", "", ""]
        row = _write_table_headers(ws, row, headers)
        for sf in supplements:
            vals = [
                sf.get("finding_id", ""),
                sf.get("title", ""),
                sf.get("description", ""),
                sf.get("rationale", ""),
            ]
            for col_idx, val in enumerate(vals, start=1):
                cell = ws.cell(row=row, column=col_idx, value=val)
                _apply_data(cell, row)
                if col_idx == 1:
                    cell.font = Font(name="Calibri", size=11, color=COLORS["implicit"])
            ws.row_dimensions[row].height = 60
            row += 1
    else:
        ws[f"A{row}"] = "No supplemental findings for this domain."
        ws[f"A{row}"].font = Font(name="Calibri", size=11, italic=True, color="666666")
        row += 1
    row += 1

    # Section D: Abstentions
    row = _write_section_header(ws, row, "D — Abstentions (Chapters with No Extracted Data)")
    if dr.abstentions:
        headers = ["Chapter", "Reason", "", "", "", ""]
        row = _write_table_headers(ws, row, headers)
        for ab in dr.abstentions:
            vals = [ab.get("chapter", ""), ab.get("reason", "")]
            for col_idx, val in enumerate(vals, start=1):
                cell = ws.cell(row=row, column=col_idx, value=val)
                _apply_data(cell, row)
            row += 1
    else:
        ws[f"A{row}"] = "All assigned chapters had extractable data."
        ws[f"A{row}"].font = Font(name="Calibri", size=11, italic=True, color="666666")
        row += 1

    _auto_fit(ws)


# ---------------------------------------------------------------------------
# Shared cell formatting helpers
# ---------------------------------------------------------------------------

def _apply_header(cell):
    cell.font = _HEADER_FONT
    cell.fill = _HEADER_FILL
    cell.border = _HEADER_BORDER
    cell.alignment = _WRAP_ALIGNMENT


def _apply_data(cell, row_num: int):
    cell.font = Font(name="Calibri", size=11)
    cell.border = _DATA_BORDER
    cell.alignment = _WRAP_ALIGNMENT
    if row_num % 2 == 0:
        cell.fill = PatternFill(start_color=COLORS["light_gray"], end_color=COLORS["light_gray"], fill_type="solid")


def _color_rag(cell, value: str):
    v = value.strip().upper() if value else ""
    if v == "RED":
        cell.font = Font(name="Calibri", size=11, bold=True, color=COLORS["white"])
        cell.fill = PatternFill(start_color=COLORS["red"], end_color=COLORS["red"], fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="top")
    elif v == "YELLOW":
        cell.font = Font(name="Calibri", size=11, bold=True, color=COLORS["sap_dark"])
        cell.fill = PatternFill(start_color=COLORS["yellow"], end_color=COLORS["yellow"], fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="top")
    elif v == "IMPLICIT":
        cell.font = Font(name="Calibri", size=11, bold=True, color=COLORS["white"])
        cell.fill = PatternFill(start_color=COLORS["implicit"], end_color=COLORS["implicit"], fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="top")


def _write_section_header(ws: Worksheet, row: int, text: str) -> int:
    ws[f"A{row}"] = text
    ws[f"A{row}"].font = Font(name="Calibri", size=13, bold=True, color=COLORS["sap_dark"])
    ws[f"A{row}"].fill = PatternFill(start_color=COLORS["section_bg"], end_color=COLORS["section_bg"], fill_type="solid")
    ws.merge_cells(f"A{row}:F{row}")
    ws.row_dimensions[row].height = 24
    return row + 1


def _write_table_headers(ws: Worksheet, row: int, headers: list[str]) -> int:
    for col_idx, header in enumerate(headers, start=1):
        if header:
            cell = ws.cell(row=row, column=col_idx, value=header)
            _apply_header(cell)
    return row + 1


def _auto_fit(ws: Worksheet, min_width: int = 14, max_width: int = 55):
    for col_idx in range(1, ws.max_column + 1):
        max_length = 0
        col_letter = get_column_letter(col_idx)
        for row_idx in range(1, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            try:
                val = str(cell.value) if cell.value else ""
                lines = val.split("\n")
                max_line = max(len(line) for line in lines) if lines else 0
                max_length = max(max_length, max_line)
            except Exception:
                pass
        adjusted = min(max(max_length + 2, min_width), max_width)
        ws.column_dimensions[col_letter].width = adjusted
