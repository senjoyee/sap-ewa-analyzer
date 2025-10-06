"""
Utility functions for converting a validated EWA summary JSON
(schema v1.1, god_level_ewa_analysis) into human-friendly Markdown.
"""
from typing import Dict, Any, List
import re
from datetime import datetime

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
        # Sanitize cell values: replace newlines with <br> so lists inside cells don't break the table
        sanitized_cells = []
        for x in row:
            cell = "N/A" if x is None else str(x)
            cell = cell.replace("\n", "<br>")
            sanitized_cells.append(cell)
        md.append(f"| {' | '.join(sanitized_cells)} |")
    return md


def _parse_date_any(s: str) -> datetime | None:
    """Best-effort parse for a variety of common date formats. Returns None if unparseable."""
    if not s or not isinstance(s, str):
        return None
    s_clean = s.strip()
    # Try explicit formats first
    patterns = [
        "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%y", "%d-%m-%y", "%Y%m%d",
    ]
    for p in patterns:
        try:
            dt = datetime.strptime(s_clean, p)
            # Accept only reasonable years to avoid malformed tokens like "0405-05-04"
            if 2000 <= dt.year <= 2100:
                return dt
        except Exception:
            pass
    # Extract a date-like token and try again (e.g., from strings like "28.04.2025 / 04.05.2025")
    m = re.search(r"\b(\d{1,4}[./-]\d{1,2}[./-]\d{2,4})\b", s_clean)
    if m:
        token = m.group(1)
        for p in patterns:
            try:
                dt = datetime.strptime(token, p)
                if 2000 <= dt.year <= 2100:
                    return dt
            except Exception:
                pass
    return None


def _format_date_ddmmyyyy(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y")


def _to_title_case(s: Any) -> str:
    """Conservatively convert a value to Title Case for display.

    - Non-string values are returned as-is cast to str.
    - Simple word capitalization; extend later for special acronyms if needed.
    """
    try:
        text = str(s)
    except Exception:
        return "N/A"
    # Normalize whitespace then title-case words
    text = re.sub(r"\s+", " ", text.strip())
    return text.title()


def _normalize_report_date(meta: Dict[str, Any]) -> str:
    """Render a clean Report Date. If the direct value is malformed, fall back to the end of Analysis Period."""
    report_date_raw = meta.get("Report Date", meta.get("report_date"))
    dt = _parse_date_any(report_date_raw) if report_date_raw else None
    if dt:
        return _format_date_ddmmyyyy(dt)
    # Fallback: try to derive from analysis period (prefer the last date if two are present)
    ap = meta.get("Analysis Period", meta.get("analysis_period"))
    if isinstance(ap, str):
        # Find all date-like tokens and take the last one
        tokens = re.findall(r"\b(\d{1,4}[./-]\d{1,2}[./-]\d{2,4})\b", ap)
        for token in reversed(tokens):
            dt2 = _parse_date_any(token)
            if dt2:
                return _format_date_ddmmyyyy(dt2)
    # Last resort: return original (or N/A if missing)
    return report_date_raw if report_date_raw else "N/A"


def _array_to_markdown_table(
    array: List[Dict[str, Any]], section_name: str | None = None
) -> List[str]:
    """
    Generic helper to turn an array of dicts into a Markdown table.

    • Flattens nested dicts that match {'analysis','implementation'}.
    • Renders Action/Preventative Action as bullet lists inside table cells.
    • If the array is empty, prints an informational line instead.
    """
    md: List[str] = []
    if section_name:
        md.append(f"## {section_name}")

    if not array:
        md.append(f"No {section_name.lower() if section_name else 'data'} provided.")
        return md

    # Render columns in the order they appear in the first JSON object for all sections, including Recommendations.
    headers = list(array[0].keys())

    # Remove flattened duplicate headers like "Estimated Effort:analysis" when base object exists
    dict_bases = [k for k in headers if isinstance(array[0].get(k), dict)]
    cleaned_headers: List[str] = []
    for h in headers:
        if any(h.startswith(f"{base}:") for base in dict_bases):
            continue
        cleaned_headers.append(h)
    headers = cleaned_headers

    rows: List[List[str]] = []
    for item in array:
        row: List[str] = []
        for k in headers:
            v = item.get(k, "N/A")
            # Render bullet lists for Action/Preventative Action/Impact/Business impact (case-insensitive)
            key_norm = k.strip().lower()
            bullet_fields = {"finding", "action", "preventative action", "preventive action", "impact", "business impact"}
            if isinstance(v, str) and key_norm in bullet_fields:
                text = v.replace("\r", "").strip()
                bullet_lines = []
                # Primary: newline-separated bullets
                if "\n" in text:
                    bullet_lines = [ln.strip().lstrip("-•–— ") for ln in text.split("\n") if ln.strip()]
                if not bullet_lines:
                    # Secondary: regex split on inline bullets using hyphen/en-dash/em-dash or bullet char, optionally after ; or newline
                    parts = re.split(r"(?:^|[\n;])\s*[\-–—•]\s+", text)
                    items = [p.strip() for p in parts[1:] if p.strip()]
                    if items:
                        preamble = parts[0].strip()
                        v = (preamble + " " if preamble else "") + "<ul>" + "".join(f"<li>{it}</li>" for it in items) + "</ul>"
                        row.append(v)
                        continue
                if bullet_lines:
                    v = "<ul>" + "".join(f"<li>{it}</li>" for it in bullet_lines) + "</ul>"
            elif isinstance(v, dict):
                # Special-case effort object
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

    # (removed unreachable duplicate block)


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
    # Support both Title Case and snake_case keys
    meta = data.get("System Metadata", data.get("system_metadata", {}))
    sid = meta.get('System ID', meta.get('system_id', 'N/A'))
    report_date_display = _normalize_report_date(meta)
    md.append(f"# EWA Analysis for {sid} ({report_date_display})")
    md.append(f"**Analysis Period:** {meta.get('Analysis Period', meta.get('analysis_period', 'N/A'))}")
    md.append(f"**Overall Risk Assessment:** `{data.get('Overall Risk', data.get('overall_risk', 'N/A'))}`")
    md.append("\n---\n")

    # ── System Health Overview ────────────────────────────────────────────────
    md.append("## System Health Overview")
    health = data.get("System Health Overview", data.get("system_health_overview", {}))
    if health:
        rows = [
            [_to_title_case(k), v] for k, v in health.items() if v is not None
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
    md.append(data.get("Executive Summary", data.get("executive_summary", "No summary provided.")))
    md.append("\n---\n")

    # ── Positive Findings ─────────────────────────────────────────────────────
    md.append("<div style='page-break-before: always;'></div>")
    md.append("")
    md.extend(_array_to_markdown_table(data.get("Positive Findings", data.get("positive_findings", [])), "Positive Findings"))
    md.append("\n---\n")

    # ── Key Findings ──────────────────────────────────────────────────────────
    md.append("<div style='page-break-before: always;'></div>")
    md.append("")
    md.extend(_array_to_markdown_table(data.get("Key Findings", data.get("key_findings", [])), "Key Findings"))
    md.append("\n---\n")


    # ── Recommendations ───────────────────────────────────────────────────────
    md.append("<div style='page-break-before: always;'></div>")
    md.append("")
    md.extend(_array_to_markdown_table(data.get("Recommendations", data.get("recommendations", [])), "Recommendations"))


    # ── Key Performance Indicators ────────────────────────────────────────────
    md.append("<div style='page-break-before: always;'></div>")
    md.append("")
    md.append("## Key Performance Indicators")
    # Look for KPIs under new image agent schema first, then legacy keys
    kpis = (
        data.get("kpis")
        or data.get("key_performance_indicators")
        or data.get("KPIs")
        or []
    )
    if kpis and isinstance(kpis, list):
        if isinstance(kpis[0], dict):
            sample = kpis[0]
            # New schema (image agent): {area, indicator, value, trend:{symbol,name}}
            is_new_schema = (
                ("indicator" in sample) or ("value" in sample) or (
                    isinstance(sample.get("trend"), dict) and "symbol" in sample.get("trend", {})
                )
            )
            if is_new_schema:
                headers = ["Area", "Indicator", "Value", "Trend"]
                rows: List[List[str]] = []
                for kpi in kpis:
                    area = kpi.get("area", "N/A")
                    indicator = kpi.get("indicator", kpi.get("name", "N/A"))
                    value = kpi.get("value", kpi.get("current_value", "N/A"))
                    t = kpi.get("trend") or {}
                    symbol = t.get("symbol") or ""
                    # Show only the arrow symbol, no text
                    trend_display = symbol if symbol else "N/A"
                    rows.append([area, indicator, value, trend_display])
                md.extend(_format_table(headers, rows))
            else:
                # Legacy deterministic schema
                headers = ["Area", "KPI", "Current Value", "Trend"]
                rows: List[List[str]] = []
                for kpi in kpis:
                    area = kpi.get('area', 'N/A')
                    name = kpi.get('name', 'N/A')
                    current_value = kpi.get('current_value', 'N/A')
                    trend_info = kpi.get('trend', {})
                    trend_direction = trend_info.get('direction', 'N/A')
                    if trend_direction == 'none':
                        trend_display = 'N/A'
                    else:
                        # Arrow-only mapping
                        trend_display = {
                            'up': '↗️',
                            'down': '↘️', 
                            'flat': '➡️'
                        }.get(trend_direction, trend_direction)
                    rows.append([area, name, current_value, trend_display])
                md.extend(_format_table(headers, rows))
        else:
            # Fallback for simple string KPIs
            for kpi in kpis:
                md.append(f"- {kpi}")
    else:
        md.append("No KPIs provided.")
    md.append("\n---\n")

    # ── Capacity Outlook ──────────────────────────────────────────────────────
    md.append("<div style='page-break-before: always;'></div>")
    md.append("")
    md.append("## Capacity Outlook")
    # Handle both key formats: "Capacity Outlook" and "capacity_outlook"
    capacity = data.get("Capacity Outlook", data.get("capacity_outlook", {}))
    if capacity:
        md.append(f"- **Database Growth:** {capacity.get('Database Growth', 'N/A')}")
        md.append(f"- **CPU Utilization:** {capacity.get('CPU Utilization', 'N/A')}")
        md.append(f"- **Memory Utilization:** {capacity.get('Memory Utilization', 'N/A')}")
        md.append(f"- **Capacity Summary:** {capacity.get('Summary', 'N/A')}")
    else:
        md.append("No capacity outlook data provided.")
    # End-of-report separator
    md.append("\n---\n")


    # ── Done ─────────────────────────────────────────────────────────────────
    return "\n".join(md)