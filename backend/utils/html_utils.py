"""
Utility functions for converting a validated EWA summary JSON
directly to HTML for PDF export and other uses.

This bypasses the Markdown intermediate step for cleaner output.
"""
from typing import Dict, Any, List
import re
import html
from datetime import datetime

__all__ = ["json_to_html", "get_pdf_css"]


# ────────────────────────────────────────────────────────────────────────────────
# CSS Styles
# ────────────────────────────────────────────────────────────────────────────────

def get_pdf_css() -> str:
    """Return the CSS styles for PDF export."""
    return """
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=72:wght@300;400;600;700&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        
        /* Reset and base styles */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: '72', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.5;
            color: #333333;
            background: #ffffff;
            font-size: 11pt;
        }
        
        /* Typography hierarchy */
        h1 {
            font-size: 24pt;
            font-weight: 700;
            color: #F0AB00; /* SAP Gold */
            margin: 30px 0 20px 0;
            padding-bottom: 0;
            border-bottom: none;
            page-break-after: avoid;
        }
        
        h2 {
            font-size: 18pt;
            font-weight: 700;
            color: #F0AB00; /* SAP Gold */
            margin: 25px 0 15px 0;
            padding: 0;
            border-left: none;
            padding-left: 0;
            page-break-after: avoid;
            break-after: avoid-page;
            background: transparent;
        }
        
        h3 {
            font-size: 14pt;
            font-weight: 700;
            color: #333333;
            margin: 20px 0 10px 0;
            page-break-after: avoid;
        }
        
        /* Paragraphs and lists */
        p {
            margin-bottom: 12px;
            text-align: left;
        }
        
        ul, ol {
            margin: 10px 0 15px 30px;
        }
        
        li {
            margin-bottom: 6px;
        }
        
        /* Enhanced tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 10pt;
            border: 1px solid #cccccc;
        }
        
        th {
            background: #E5E5E5;
            color: #333333;
            font-weight: 700;
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid #999999;
        }
        
        td {
            padding: 8px 10px;
            border-bottom: 1px solid #eeeeee;
            vertical-align: top;
        }
        
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        /* Risk/Status badges */
        .risk-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-weight: 700;
            font-size: 10pt;
            text-transform: uppercase;
        }
        
        .risk-critical { background: #cc0000; color: white; }
        .risk-high { background: #e07000; color: white; }
        .risk-medium { background: #F0AB00; color: black; }
        .risk-low { background: #008000; color: white; }
        
        .status-good { color: #008000; font-weight: 700; }
        .status-fair { color: #e07000; font-weight: 700; }
        .status-poor { color: #cc0000; font-weight: 700; }
        
        /* Horizontal rules */
        hr {
            border: none;
            height: 1px;
            background: #F0AB00;
            margin: 30px 0;
        }
        
        /* Card-based layout for findings */
        .findings-cards-container {
            display: block;
            margin: 8px 0 20px 0;
        }
        
        .finding-card {
            background: #ffffff;
            border: 1px solid #e0e0e0;
            border-left: 4px solid #F0AB00;
            margin-bottom: 20px;
            page-break-inside: auto;
            break-inside: auto;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        .card-header {
            background: #f9f9f9;
            padding: 10px 15px;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .card-header-left {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .issue-id {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: #333;
        }
        
        .area-badge {
            background: #333333;
            color: #F0AB00;
            padding: 2px 10px;
            font-size: 9pt;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        .severity-badge {
            padding: 2px 10px;
            font-weight: 700;
            font-size: 9pt;
            text-transform: uppercase;
        }
        
        .severity-critical { background: #cc0000; color: white; }
        .severity-high { background: #e07000; color: white; }
        .severity-medium { background: #F0AB00; color: black; }
        .severity-low { background: #008000; color: white; }
        
        .card-body { padding: 15px; }
        
        /* Severity group styling */
        .severity-group {
            margin-bottom: 25px;
            border-radius: 6px;
            overflow: hidden;
            border: 1px solid #e0e0e0;
        }
        
        .severity-group-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 15px;
            background: #f5f5f5;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .severity-group-title {
            font-weight: 700;
            font-size: 12pt;
            color: #333;
        }
        
        .severity-group-content {
            padding: 15px;
            background: #fafafa;
        }
        
        .severity-group-critical {
            border-left: 4px solid #cc0000;
        }
        
        .severity-group-critical .severity-group-header {
            background: linear-gradient(90deg, rgba(204,0,0,0.1) 0%, #f5f5f5 100%);
        }
        
        .severity-group-high {
            border-left: 4px solid #e07000;
        }
        
        .severity-group-high .severity-group-header {
            background: linear-gradient(90deg, rgba(224,112,0,0.1) 0%, #f5f5f5 100%);
        }
        
        .severity-group-medium {
            border-left: 4px solid #F0AB00;
        }
        
        .severity-group-medium .severity-group-header {
            background: linear-gradient(90deg, rgba(240,171,0,0.1) 0%, #f5f5f5 100%);
        }
        
        .severity-group-low {
            border-left: 4px solid #008000;
        }
        
        .severity-group-low .severity-group-header {
            background: linear-gradient(90deg, rgba(0,128,0,0.1) 0%, #f5f5f5 100%);
        }
        
        .severity-group .finding-card {
            margin-bottom: 15px;
            border-left-width: 3px;
        }
        
        .severity-group .finding-card:last-child {
            margin-bottom: 0;
        }
        
        .card-field {
            margin-bottom: 12px;
        }
        
        .card-field:last-child {
            margin-bottom: 0;
        }
        
        .field-label {
            font-weight: 700;
            color: #666666;
            font-size: 9pt;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        
        .field-value {
            color: #333333;
            font-size: 10pt;
            line-height: 1.5;
        }
        
        .field-value ul {
            margin: 5px 0 0 0;
            padding-left: 20px;
        }
        
        .field-value li {
            margin-bottom: 4px;
        }
        
        /* Cover page */
        .cover-page {
            page-break-after: always;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            align-items: center;
            min-height: 90vh;
            width: 100%;
        }
        
        .cover-block {
            background-color: #F0AB00;
            width: 100%;
            padding: 60px 40px;
            margin-bottom: 60px;
            color: #ffffff;
        }
        
        .cover-title {
            font-size: 36pt;
            font-weight: 700;
            margin: 0;
            line-height: 1.2;
        }
        
        .cover-subtitle {
            font-size: 18pt;
            font-weight: 400;
            margin-top: 20px;
            color: #ffffff;
        }
        
        @page {
            margin: 20mm 15mm;
            @top-center {
                content: "EarlyWatch Alert Deep Dive";
                font-size: 9pt;
                color: #666666;
            }
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666666;
            }
        }
        
        @page:first {
            margin: 0;
            @top-center { content: none; }
            @bottom-center { content: none; }
        }
    """


# ────────────────────────────────────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────────────────────────────────────

def _escape(text: Any) -> str:
    """Escape HTML entities."""
    if text is None:
        return "N/A"
    return html.escape(str(text))


def _escape_with_basic_markdown(text: Any) -> str:
    """Escape text but keep **bold** markers as <strong>."""
    if text is None:
        return ""

    source = str(text)
    result: list[str] = []
    last = 0

    for match in re.finditer(r"\*\*(.*?)\*\*", source, flags=re.DOTALL):
        if match.start() > last:
            result.append(html.escape(source[last:match.start()]))

        bold_content = match.group(1)
        result.append(f"<strong>{html.escape(bold_content)}</strong>")
        last = match.end()

    if last < len(source):
        result.append(html.escape(source[last:]))

    return "".join(result)


def _to_title_case(s: Any) -> str:
    """Convert to title case for display."""
    try:
        text = str(s)
    except Exception:
        return "N/A"
    text = re.sub(r"\s+", " ", text.strip())
    return text.title()


def _parse_date_any(s: str) -> datetime | None:
    """Best-effort parse for various date formats."""
    if not s or not isinstance(s, str):
        return None
    s_clean = s.strip()
    patterns = [
        "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%y", "%d-%m-%y", "%Y%m%d",
    ]
    for p in patterns:
        try:
            dt = datetime.strptime(s_clean, p)
            if 2000 <= dt.year <= 2100:
                return dt
        except Exception:
            pass
    return None


def _format_date_display(dt: datetime) -> str:
    """Format date as '9th November, 2025'."""
    day = dt.day
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} {dt.strftime('%B, %Y')}"


def _normalize_report_date(meta: Dict[str, Any]) -> str:
    """Get a clean report date string."""
    report_date_raw = meta.get("Report Date", meta.get("report_date"))
    dt = _parse_date_any(report_date_raw) if report_date_raw else None
    if dt:
        return _format_date_display(dt)
    
    # Fallback: try analysis period
    ap = meta.get("Analysis Period", meta.get("analysis_period"))
    if isinstance(ap, str):
        tokens = re.findall(r"\b(\d{1,4}[./-]\d{1,2}[./-]\d{2,4})\b", ap)
        for token in reversed(tokens):
            dt2 = _parse_date_any(token)
            if dt2:
                return _format_date_display(dt2)
    
    return report_date_raw if report_date_raw else "N/A"


def _text_to_bullet_html(text: str) -> str:
    """Convert newline-delimited or bullet text to HTML list."""
    if not text:
        return ""
    
    text = text.replace("\r", "").strip()
    bullet_lines = []
    
    # Primary: newline-separated
    if "\n" in text:
        bullet_lines = [ln.strip().lstrip("-•–— ") for ln in text.split("\n") if ln.strip()]
    
    if not bullet_lines:
        # Secondary: inline bullets
        parts = re.split(r"(?:^|[\n;])\s*[\-–—•]\s+", text)
        items = [p.strip() for p in parts[1:] if p.strip()]
        if items:
            preamble = parts[0].strip()
            result = _escape(preamble) + " " if preamble else ""
            result += "<ul>" + "".join(f"<li>{_escape(it)}</li>" for it in items) + "</ul>"
            return result
    
    if bullet_lines:
        return "<ul>" + "".join(f"<li>{_escape(it)}</li>" for it in bullet_lines) + "</ul>"
    
    return _escape(text)


def _render_table(headers: List[str], rows: List[List[str]]) -> str:
    """Render an HTML table."""
    html_parts = ['<table>']
    html_parts.append('<thead><tr>')
    for h in headers:
        html_parts.append(f'<th>{_escape(h)}</th>')
    html_parts.append('</tr></thead>')
    html_parts.append('<tbody>')
    for row in rows:
        html_parts.append('<tr>')
        for cell in row:
            html_parts.append(f'<td>{cell}</td>')  # Cell may contain HTML
        html_parts.append('</tr>')
    html_parts.append('</tbody></table>')
    return ''.join(html_parts)


def _get_severity_class(severity: str) -> str:
    """Get CSS class for severity level."""
    s = str(severity).lower().strip()
    if s == "critical":
        return "severity-critical"
    elif s == "high":
        return "severity-high"
    elif s == "medium":
        return "severity-medium"
    return "severity-low"


def _normalize_issue_ids(
    findings: List[Dict[str, Any]], recommendations: List[Dict[str, Any]]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Renumber Issue IDs sequentially by severity prefix (C/H/M/L) based on list order,
    and rewrite recommendation links to match the new IDs.
    """
    prefix_map = {"critical": "C", "high": "H", "medium": "M", "low": "L"}
    counters: Dict[str, int] = {}
    id_map: Dict[str, str] = {}

    normalized_findings: List[Dict[str, Any]] = []
    for finding in findings:
        severity = str(finding.get("Severity") or finding.get("severity") or "").lower().strip()
        prefix = prefix_map.get(severity, "C")
        counters[prefix] = counters.get(prefix, 0) + 1
        new_id = f"{prefix}{counters[prefix]:02d}"

        original_id = finding.get("Issue ID") or finding.get("issue_id")
        if original_id:
            id_map[str(original_id)] = new_id

        nf = dict(finding)
        nf["Issue ID"] = new_id
        nf.pop("issue_id", None)
        normalized_findings.append(nf)

    normalized_recs: List[Dict[str, Any]] = []
    for rec in recommendations:
        nr = dict(rec)
        linked_id = rec.get("Linked issue ID") or rec.get("linked_issue_id")
        if linked_id and linked_id in id_map:
            nr["Linked issue ID"] = id_map[linked_id]
        elif linked_id:
            nr["Linked issue ID"] = linked_id
        nr.pop("linked_issue_id", None)
        normalized_recs.append(nr)

    return normalized_findings, normalized_recs


def _get_risk_class(risk: str) -> str:
    """Get CSS class for risk level."""
    r = str(risk).lower().strip()
    if r == "critical":
        return "risk-critical"
    elif r == "high":
        return "risk-high"
    elif r == "medium":
        return "risk-medium"
    return "risk-low"


def _get_status_class(status: str) -> str:
    """Get CSS class for status."""
    s = str(status).lower().strip()
    if s == "good":
        return "status-good"
    elif s == "fair":
        return "status-fair"
    elif s == "poor":
        return "status-poor"
    return ""


# ────────────────────────────────────────────────────────────────────────────────
# Section renderers
# ────────────────────────────────────────────────────────────────────────────────

def _render_cover_page(meta: Dict[str, Any], customer_name: str = "") -> str:
    """Render the PDF cover page.
    
    Args:
        meta: System metadata from JSON
        customer_name: Customer name from blob metadata (takes precedence)
    """
    sid = meta.get("System ID", meta.get("system_id", "Unknown"))
    # Use passed customer_name if provided, otherwise try to get from meta
    customer = customer_name if customer_name else meta.get("Customer", meta.get("customer", "Unknown"))
    report_date = _normalize_report_date(meta)
    
    return f'''
    <div class="cover-page">
        <div class="cover-block">
            <div class="cover-title">EarlyWatch Alert Analysis</div>
            <div class="cover-subtitle">Deep Dive Report</div>
        </div>
        <div style="padding: 0 40px; width: 100%;">
            <p style="font-size: 14pt; margin-bottom: 15px;"><strong>SAP System ID:</strong> {_escape(sid)}</p>
            <p style="font-size: 14pt; margin-bottom: 15px;"><strong>Customer Name:</strong> {_escape(customer)}</p>
            <p style="font-size: 14pt; margin-bottom: 15px;"><strong>Generated On:</strong> {_escape(report_date)}</p>
        </div>
    </div>
    '''


def _render_header(data: Dict[str, Any]) -> str:
    """Render the report header section."""
    meta = data.get("System Metadata", data.get("system_metadata", {}))
    sid = meta.get("System ID", meta.get("system_id", "N/A"))
    report_date = _normalize_report_date(meta)
    analysis_period = meta.get("Analysis Period", meta.get("analysis_period", "N/A"))
    overall_risk = data.get("Overall Risk", data.get("overall_risk", "N/A"))
    risk_class = _get_risk_class(overall_risk)
    
    return f'''
    <h1>EWA Analysis for {_escape(sid)} ({_escape(report_date)})</h1>
    <p><strong>Analysis Period:</strong> {_escape(analysis_period)}</p>
    <p><strong>Overall Risk Assessment:</strong> <span class="risk-badge {risk_class}">{_escape(overall_risk).upper()}</span></p>
    <hr>
    '''


def _render_system_health(data: Dict[str, Any]) -> str:
    """Render System Health Overview section."""
    health = data.get("System Health Overview", data.get("system_health_overview", {}))
    if not health:
        return '<h2>System Health Overview</h2><p>No health overview provided.</p><hr>'
    
    rows = []
    for area, status in health.items():
        if status is None:
            continue
        status_class = _get_status_class(status)
        status_html = f'<span class="{status_class}">{_escape(status).upper()}</span>' if status_class else _escape(status)
        rows.append([_escape(_to_title_case(area)), status_html])
    
    if not rows:
        return '<h2>System Health Overview</h2><p>No health overview data provided.</p><hr>'
    
    table = _render_table(["Area", "Status"], rows)
    return f'<h2>System Health Overview</h2>{table}<hr>'


def _render_executive_summary(data: Dict[str, Any]) -> str:
    """Render Executive Summary section."""
    summary = data.get("Executive Summary", data.get("executive_summary", "No summary provided."))
    
    # Convert newlines to proper HTML
    if isinstance(summary, str):
        # Check if it has bullet points
        if "\n" in summary and any(line.strip().startswith("-") for line in summary.split("\n")):
            summary_html = _text_to_bullet_html(summary)
        else:
            summary_html = _escape_with_basic_markdown(summary).replace("\n", "<br>")
    else:
        summary_html = _escape_with_basic_markdown(str(summary))
    
    return f'<h2>Executive Summary</h2><div>{summary_html}</div><hr>'


def _render_positive_findings(data: Dict[str, Any]) -> str:
    """Render Positive Findings section."""
    findings = data.get("Positive Findings", data.get("positive_findings", []))
    if not findings:
        return '<h2>Positive Findings</h2><p>No positive findings provided.</p><hr>'
    
    # Get headers from first item
    if findings:
        headers = list(findings[0].keys())
        rows = []
        for item in findings:
            row = [_escape(str(item.get(h, "N/A"))) for h in headers]
            rows.append(row)
        table = _render_table(headers, rows)
    else:
        table = "<p>No positive findings provided.</p>"
    
    return f'<h2>Positive Findings</h2>{table}<hr>'


def _render_findings_and_recommendations(data: Dict[str, Any]) -> str:
    """Render Key Findings & Recommendations with severity subheaders."""
    findings_raw = data.get("Key Findings", data.get("key_findings", []))
    recommendations_raw = data.get("Recommendations", data.get("recommendations", []))

    findings, recommendations = _normalize_issue_ids(findings_raw, recommendations_raw)
    
    # Build recommendation lookup by linked issue ID
    rec_map: Dict[str, List[Dict[str, Any]]] = {}
    for rec in recommendations:
        linked_id = rec.get("Linked issue ID") or rec.get("linked_issue_id")
        if linked_id:
            rec_map.setdefault(linked_id, []).append(rec)
    
    # Merge findings with their recommendations
    merged: List[Dict[str, Any]] = []
    for finding in findings:
        issue_id = finding.get("Issue ID") or finding.get("issue_id")
        linked_recs = rec_map.get(issue_id, [])
        
        if linked_recs:
            for rec in linked_recs:
                merged.append({
                    "Issue ID": issue_id,
                    "Area": finding.get("Area") or finding.get("area"),
                    "Severity": finding.get("Severity") or finding.get("severity"),
                    "Source": finding.get("Source") or finding.get("source"),
                    "Finding": finding.get("Finding") or finding.get("finding"),
                    "Impact": finding.get("Impact") or finding.get("impact"),
                    "Business impact": finding.get("Business impact") or finding.get("business_impact"),
                    "Estimated Effort": rec.get("Estimated Effort") or rec.get("estimated_effort"),
                    "Responsible Area": rec.get("Responsible Area") or rec.get("responsible_area"),
                    "Action": rec.get("Action") or rec.get("action"),
                    "Preventative Action": rec.get("Preventative Action") or rec.get("preventative_action"),
                })
        else:
            merged.append({
                "Issue ID": issue_id,
                "Area": finding.get("Area") or finding.get("area"),
                "Severity": finding.get("Severity") or finding.get("severity"),
                "Source": finding.get("Source") or finding.get("source"),
                "Finding": finding.get("Finding") or finding.get("finding"),
                "Impact": finding.get("Impact") or finding.get("impact"),
                "Business impact": finding.get("Business impact") or finding.get("business_impact"),
            })
    
    if not merged:
        return '<h2>Key Findings &amp; Recommendations</h2><p>No findings provided.</p><hr>'
    
    # Group findings by severity
    severity_order = ["critical", "high", "medium", "low"]
    severity_groups: Dict[str, List[Dict[str, Any]]] = {s: [] for s in severity_order}
    severity_labels = {
        "critical": "Critical Issues",
        "high": "High Priority Issues",
        "medium": "Medium Priority Issues",
        "low": "Low Priority Issues",
    }
    
    for item in merged:
        severity = str(item.get("Severity", "low")).lower().strip()
        if severity not in severity_groups:
            severity = "low"
        severity_groups[severity].append(item)
    
    def _format_issue_id_with_severity(issue_id: Any, severity: str) -> str:
        """Prefix issue id with severity initial (C/H/M/L)."""
        prefix_map = {"critical": "C", "high": "H", "medium": "M", "low": "L"}
        sev_key = str(severity or "low").lower()
        prefix = prefix_map.get(sev_key, "L")
        base = str(issue_id or "N/A")
        match = re.search(r"(\d+)", base)
        number_part = match.group(1) if match else base
        return f"{prefix}{number_part}"

    # Render cards by severity with simple headers
    html_parts = ['<h2>Key Findings &amp; Recommendations</h2>']
    
    for severity in severity_order:
        group_items = severity_groups[severity]
        if not group_items:
            continue
        
        severity_class = _get_severity_class(severity)
        count = len(group_items)
        
        # Severity subheader
        html_parts.append(f'''
        <h3 style="margin: 18px 0 10px 0; display: flex; align-items: center; gap: 8px;">
            <span class="severity-badge {severity_class}">{severity.upper()}</span>
            <span>{severity_labels[severity]} ({count})</span>
        </h3>
        ''')
        
        # Render cards within this severity
        for item in group_items:
            issue_id = item.get("Issue ID", "N/A")
            area = item.get("Area", "General")
            display_issue_id = _format_issue_id_with_severity(issue_id, severity)
            
            html_parts.append(f'''
            <div class="finding-card">
                <div class="card-header">
                    <div class="card-header-left">
                        <span class="issue-id">{_escape(display_issue_id)}</span>
                        <span class="area-badge">{_escape(area)}</span>
                    </div>
                </div>
                <div class="card-body">
            ''')
            
            # Render fields (skip Issue ID, Area, Severity - already in header)
            skip_fields = {"Issue ID", "Area", "Severity"}
            bullet_fields = {"finding", "action", "preventative action", "preventive action", "impact", "business impact"}
            
            for key, value in item.items():
                if key in skip_fields or value is None:
                    continue
                
                key_lower = key.lower().strip()
                
                # Handle effort object
                if isinstance(value, dict) and set(value.keys()) == {"analysis", "implementation"}:
                    value_html = f"Analysis: {_escape(value.get('analysis', 'N/A'))}, Implementation: {_escape(value.get('implementation', 'N/A'))}"
                elif key_lower in bullet_fields and isinstance(value, str):
                    value_html = _text_to_bullet_html(value)
                else:
                    value_html = _escape(str(value))
                
                html_parts.append(f'''
                    <div class="card-field">
                        <div class="field-label">{_escape(key)}</div>
                        <div class="field-value">{value_html}</div>
                    </div>
                ''')
            
            html_parts.append('</div></div>')
    
    html_parts.append('<hr>')
    return ''.join(html_parts)


def _render_capacity_outlook(data: Dict[str, Any]) -> str:
    """Render Capacity Outlook section."""
    capacity = data.get("Capacity Outlook", data.get("capacity_outlook", {}))
    if not capacity:
        return '<h2>Capacity Outlook</h2><p>No capacity outlook data provided.</p><hr>'
    
    html_parts = ['<h2>Capacity Outlook</h2><ul>']
    
    fields = [
        ("Database Growth", "Database Growth"),
        ("CPU Utilization", "CPU Utilization"),
        ("Memory Utilization", "Memory Utilization"),
        ("Summary", "Capacity Summary"),
    ]
    
    for key, label in fields:
        value = capacity.get(key, "N/A")
        html_parts.append(f'<li><strong>{label}:</strong> {_escape(value)}</li>')
    
    html_parts.append('</ul><hr>')
    return ''.join(html_parts)


# ────────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────────

def json_to_html(
    data: Dict[str, Any],
    include_cover_page: bool = True,
    include_css: bool = True,
    page_size: str = "A4",
    landscape: bool = True,
    customer_name: str = "",
) -> str:
    """
    Convert an EWA JSON document directly to HTML.
    
    Args:
        data: The EWA JSON data to convert
        include_cover_page: Whether to include the cover page
        include_css: Whether to include CSS styles in the output
        page_size: Page size for PDF (A4, A3, Letter)
        landscape: Whether to use landscape orientation
        customer_name: Customer name from blob metadata
    
    Returns:
        Complete HTML document string
    """
    meta = data.get("System Metadata", data.get("system_metadata", {}))
    
    # Build body content
    body_parts = []
    
    if include_cover_page:
        body_parts.append(_render_cover_page(meta, customer_name=customer_name))
    
    body_parts.append('<div class="report-container">')
    body_parts.append(_render_header(data))
    body_parts.append(_render_system_health(data))
    body_parts.append(_render_executive_summary(data))
    body_parts.append(_render_positive_findings(data))
    body_parts.append(_render_findings_and_recommendations(data))
    body_parts.append(_render_capacity_outlook(data))
    body_parts.append('</div>')
    
    body_html = ''.join(body_parts)
    
    if not include_css:
        return body_html
    
    # Build full HTML document
    css = get_pdf_css()
    orientation = " landscape" if landscape else ""
    page_css = f"@page {{ size: {page_size}{orientation}; }}"
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EWA Analysis Report</title>
    <style>
        {page_css}
        {css}
    </style>
</head>
<body>
    {body_html}
</body>
</html>'''
