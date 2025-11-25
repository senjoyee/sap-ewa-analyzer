"""
Enhanced Export Markdown to PDF route with professional styling.
This replaces the existing export_markdown_to_pdf function with improved CSS and HTML structure.
"""

from __future__ import annotations

import os
import re
import json
import html
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Response, Query
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from weasyprint import HTML
from markdown2 import markdown
from utils.markdown_utils import json_to_markdown

load_dotenv()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError("Azure storage env vars not set")

try:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
except Exception as e:
    print(f"Error initializing BlobServiceClient in export_router: {e}")
    blob_service_client = None

router = APIRouter(prefix="/api", tags=["export"])


def _get_pdf_optimized_markdown(blob_name: str, markdown_text: str) -> str:
    """
    Attempt to regenerate markdown from JSON with pdf_export=True.
    If JSON is not found, return the original markdown.
    
    This ensures that JSON card sections are rendered as tables in PDF exports
    and KPI sections are excluded.
    """
    print(f"[PDF Export] _get_pdf_optimized_markdown called with blob_name={blob_name}")
    print(f"[PDF Export] Original markdown length: {len(markdown_text)}")
    
    if not blob_service_client:
        print(f"[PDF Export] No blob service client, returning original markdown")
        return markdown_text
    
    try:
        # Derive the JSON blob name from the markdown blob name
        # Pattern: filename_AI.md -> filename_AI.json
        base_name = os.path.splitext(blob_name)[0]
        json_blob_name = f"{base_name}.json"
        print(f"[PDF Export] Looking for JSON: {json_blob_name}")
        
        # Try to download the JSON file
        json_blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, blob=json_blob_name
        )
        
        if json_blob_client.exists():
            print(f"[PDF Export] JSON file exists, downloading...")
            json_bytes = json_blob_client.download_blob().readall()
            json_data = json.loads(json_bytes.decode("utf-8", errors="replace"))
            print(f"[PDF Export] JSON loaded successfully, keys: {list(json_data.keys())}")
            
            # Regenerate markdown with pdf_export=True
            print(f"[PDF Export] Regenerating markdown from JSON with pdf_export=True")
            regenerated = json_to_markdown(json_data, pdf_export=True)
            print(f"[PDF Export] Regenerated markdown length: {len(regenerated)}")
            return regenerated
        else:
            print(f"[PDF Export] JSON not found ({json_blob_name}), using original markdown")
            return markdown_text
            
    except Exception as e:
        print(f"[PDF Export] Error loading JSON for PDF optimization: {e}")
        import traceback
        traceback.print_exc()
        return markdown_text


def _convert_findings_table_to_cards(html_content: str) -> str:
    """Convert the Key Findings & Recommendations table to card layout for better PDF readability."""
    import re
    
    # Find the Key Findings & Recommendations section
    # Look for the h2 header followed by a table
    pattern = r'(<h2[^>]*>Key Findings &amp; Recommendations</h2>)(.*?)(?=<h2|<hr|$)'
    match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    if not match:
        return html_content
    
    section_start = match.start()
    section_end = match.end()
    header_html = match.group(1)
    section_content = match.group(2)

    # Remove any page-break span injected inside the H2 itself
    header_html = re.sub(
        r'(<h2[^>]*>)(?:\s*<span[^>]*class=["\']page-break-before["\'][^>]*>\s*)?(.*?)(?:\s*</span>\s*)?(</h2>)',
        r'\1\2\3',
        header_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    
    # Remove any leading explicit page-break elements that might have slipped in
    section_content = re.sub(
        r'^(\s*(?:<div[^>]*page-break-before[^>]*></div>|<span[^>]*class=["\']page-break-before["\'][^>]*>.*?</span>))*',
        '',
        section_content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    
    # Also strip any immediate <hr> separators that might push content
    section_content = re.sub(r'^\s*<hr\s*/?>', '', section_content, flags=re.IGNORECASE)

    # Extract table data
    table_match = re.search(r'<table>(.*?)</table>', section_content, re.DOTALL)
    if not table_match:
        return html_content
    
    table_html = table_match.group(0)
    
    # Parse table headers
    headers_match = re.search(r'<thead>.*?<tr>(.*?)</tr>.*?</thead>', table_html, re.DOTALL)
    if not headers_match:
        return html_content
    
    headers = re.findall(r'<th[^>]*>(.*?)</th>', headers_match.group(1))
    headers = [re.sub(r'<[^>]+>', '', h).strip() for h in headers]  # Strip HTML tags
    
    # Parse table rows
    tbody_match = re.search(r'<tbody>(.*?)</tbody>', table_html, re.DOTALL)
    if not tbody_match:
        return html_content
    
    rows_html = re.findall(r'<tr>(.*?)</tr>', tbody_match.group(1), re.DOTALL)
    
    # Build card HTML
    cards_html = '<div class="findings-cards-container">'
    
    for row_html in rows_html:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
        if len(cells) != len(headers):
            continue
        
        # Extract key fields for card header
        issue_id = cells[0] if len(cells) > 0 else 'N/A'
        area = cells[1] if len(cells) > 1 else 'N/A'
        severity = cells[2] if len(cells) > 2 else 'N/A'
        
        # Clean area and severity text (strip HTML tags)
        area_text_raw = re.sub(r'<[^>]+>', '', area)
        severity_text_raw = re.sub(r'<[^>]+>', '', severity)

        area_clean = html.unescape(area_text_raw.strip()) if area_text_raw else ''
        area_text = html.escape(area_clean) if area_clean else 'General'

        severity_clean = html.unescape(severity_text_raw.strip()) if severity_text_raw else ''
        severity_match = re.search(r'(critical|high|medium|low)', severity_clean, re.IGNORECASE)
        severity_lower = severity_match.group(1).lower() if severity_match else 'medium'
        severity_display = severity_lower.upper()
        severity_class = f'severity-{severity_lower}'
        
        cards_html += f'''
        <div class="finding-card">
            <div class="card-header">
                <div class="card-header-left">
                    <span class="area-badge">{area_text}</span>
                </div>
                <span class="severity-badge {severity_class}">{severity_display}</span>
            </div>
            <div class="card-body">
        '''
        
        # Add all fields as rows
        for i, (header, cell) in enumerate(zip(headers, cells)):
            if i < 3:  # Skip Issue ID, Area, Severity (already in header)
                continue
            
            cards_html += f'''
                <div class="card-field">
                    <div class="field-label">{header}</div>
                    <div class="field-value">{cell}</div>
                </div>
            '''
        
        cards_html += '''
            </div>
        </div>
        '''
    
    cards_html += '</div>'
    
    # Replace the table with cards
    new_section = header_html + cards_html + section_content[table_match.end():]
    new_html = html_content[:section_start] + new_section + html_content[section_end:]
    
    return new_html


def _enhanced_markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to HTML with enhanced styling and structure."""
    
    # Remove JSON card blocks that are used for UI rendering but not suitable for PDF
    # Pattern: ```json ... ``` blocks that contain card layout definitions
    import re
    markdown_text = re.sub(
        r'```json\s*\n\{[^`]*"layout"\s*:\s*"cards"[^`]*\}\s*\n```',
        '',
        markdown_text,
        flags=re.DOTALL
    )
    
    # Convert markdown to HTML with enhanced features
    html_body = markdown(
        markdown_text,
        extras=[
            "tables", "fenced-code-blocks", "header-ids", "toc", 
            "strike", "task_list", "break-on-newline"
        ]
    )
    
    # Convert findings table to cards for better PDF layout
    # Re-enable card conversion for proper layout
    html_body = _convert_findings_table_to_cards(html_body)
    
    # Enhanced CSS styling for professional appearance
    enhanced_css = """
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
        
        h4 {
            font-size: 12pt;
            font-weight: 600;
            color: #666666;
            margin: 15px 0 8px 0;
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
        
        /* Section page breaks - ensure major tables start on new pages */
        .page-break-before {
            page-break-before: always;
        }
        
        /* Enhanced tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 10pt;
            box-shadow: none;
            border-radius: 0;
            overflow: visible;
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
        
        tr:hover {
            background-color: #f0f0f0;
        }
        
        /* Risk level styling - kept functional but cleaner */
        .risk-critical {
            background: #ffe5e5;
            color: #cc0000;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 2px;
            font-size: 9pt;
        }
        
        .risk-high {
            background: #fff0e0;
            color: #e07000;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 2px;
            font-size: 9pt;
        }
        
        .risk-medium {
            background: #fffae0;
            color: #998a00;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 2px;
            font-size: 9pt;
        }
        
        .risk-low {
            background: #e5ffe5;
            color: #008000;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 2px;
            font-size: 9pt;
        }
        
        /* Status indicators */
        .status-good { color: #008000; font-weight: 700; }
        .status-fair { color: #e07000; font-weight: 700; }
        .status-poor { color: #cc0000; font-weight: 700; }
        
        /* Code blocks */
        pre {
            background: #f5f5f5;
            color: #333333;
            padding: 15px;
            border-radius: 0;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 9pt;
            overflow-x: auto;
            margin: 15px 0;
            border-left: 4px solid #F0AB00; /* SAP Gold */
        }
        
        code {
            background: #f0f0f0;
            color: #333333;
            padding: 2px 4px;
            border-radius: 2px;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 9pt;
        }
        
        /* Blockquotes / Notes */
        blockquote {
            border-left: 4px solid #F0AB00;
            margin: 20px 0;
            padding: 10px 20px;
            background: #fffdf5;
            font-style: normal;
            color: #333333;
        }
        
        /* Horizontal rules */
        hr {
            border: none;
            height: 1px;
            background: #F0AB00;
            margin: 30px 0;
        }
        
        /* Page breaks */
        .page-break { page-break-before: always; }
        .avoid-break { page-break-inside: avoid; }
        
        /* Card-based layout for findings - Updated for SAP Style */
        .findings-cards-container {
            display: block;
            margin: 8px 0 20px 0;
            break-before: avoid-page !important;
            page-break-before: avoid !important;
        }

        h2 + .findings-cards-container {
            break-before: auto !important;
            page-break-before: auto !important;
            margin-top: 6px;
        }
        
        .findings-cards-container .finding-card + .finding-card::before {
            content: "";
            display: block;
            height: 1px;
            background: #cccccc;
            margin: 15px 0;
        }
        
        .finding-card {
            background: #ffffff;
            border: 1px solid #e0e0e0;
            border-left: 4px solid #F0AB00; /* Gold accent */
            border-radius: 0;
            margin-bottom: 20px;
            page-break-inside: auto;
            break-inside: auto;
            break-before: auto !important;
            page-break-before: auto !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            overflow: visible;
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
        
        .area-badge {
            background: #333333;
            color: #F0AB00;
            padding: 2px 10px;
            border-radius: 0;
            font-size: 9pt;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        .severity-badge {
            padding: 2px 10px;
            border-radius: 0;
            font-weight: 700;
            font-size: 9pt;
            text-transform: uppercase;
            display: inline-block;
        }
        
        .severity-critical { background: #cc0000; color: white; }
        .severity-high { background: #e07000; color: white; }
        .severity-medium { background: #F0AB00; color: black; }
        .severity-low { background: #008000; color: white; }
        
        .card-body { padding: 15px; }
        
        .card-field {
            margin-bottom: 12px;
            page-break-inside: auto;
            break-inside: auto;
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
    """
    
    return enhanced_css, html_body


def _post_process_html(
    html_content: str,
    *,
    skip_page_break_sections: set[str] | None = None,
    apply_risk_highlights: bool = True,
    enable_section_page_breaks: bool = True,
) -> str:
    """Apply additional HTML enhancements and optional risk level styling.

    Args:
        html_content: The HTML to post-process
        skip_page_break_sections: Section titles to NOT inject page breaks for
        apply_risk_highlights: Whether to replace bare risk words with styled spans
        enable_section_page_breaks: If False, do not inject any section page breaks
    """
    
    skip_page_break_sections = skip_page_break_sections or set()

    # Add page breaks before major table sections (unless disabled or skipped)
    if enable_section_page_breaks:
        for section_name in ['Positive Findings', 'Key Findings & Recommendations', 'Recommendations', 'Parameters']:
            if section_name in skip_page_break_sections:
                continue
            # Create pattern that handles HTML encoding of ampersands
            encoded_section = section_name.replace('&', '(?:&|&amp;|&amp;amp;)')
            pattern = fr'(<h\d[^>]*>)({encoded_section})(</h\d>)'
            replacement = fr'\1<span class="page-break-before">\2</span>\3'
            html_content = re.sub(pattern, replacement, html_content, flags=re.IGNORECASE)
    
    if apply_risk_highlights:
        # Add risk level classes to severity indicators
        html_content = re.sub(
            r'\b(critical)\b', 
            '<span class="risk-critical">CRITICAL</span>', 
            html_content, 
            flags=re.IGNORECASE
        )
        
        html_content = re.sub(
            r'\b(high)\b', 
            '<span class="risk-high">HIGH</span>', 
            html_content, 
            flags=re.IGNORECASE
        )
        
        html_content = re.sub(
            r'\b(medium)\b', 
            '<span class="risk-medium">MEDIUM</span>', 
            html_content, 
            flags=re.IGNORECASE
        )
        
        html_content = re.sub(
            r'\b(low)\b', 
            '<span class="risk-low">LOW</span>', 
            html_content, 
            flags=re.IGNORECASE
        )
    
    # Add status styling
    html_content = re.sub(
        r'\b(good)\b', 
        '<span class="status-good">GOOD</span>', 
        html_content, 
        flags=re.IGNORECASE
    )
    
    html_content = re.sub(
        r'\b(fair)\b', 
        '<span class="status-fair">FAIR</span>', 
        html_content, 
        flags=re.IGNORECASE
    )
    
    html_content = re.sub(
        r'\b(poor)\b', 
        '<span class="status-poor">POOR</span>', 
        html_content, 
        flags=re.IGNORECASE
    )
    
    return html_content


@router.get("/export-pdf-enhanced")
async def export_markdown_to_pdf_enhanced(
    blob_name: str,
    landscape: bool = Query(True, description="Render PDF in landscape orientation (default: true)"),
    page_size: str = Query("A4", description="Page size for PDF (e.g., A4, A3, Letter). Default: A4"),
    include_header_footer: bool = Query(True, description="Include professional header and footer"),
):
    """Convert a Markdown blob to PDF with enhanced professional styling."""
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized")

    try:
        # Validate extension
        if not blob_name.lower().endswith(".md"):
            raise HTTPException(status_code=400, detail="blob_name must point to a .md file")

        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, blob=blob_name
        )
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail=f"File {blob_name} not found")

        markdown_bytes = blob_client.download_blob().readall()
        markdown_text = markdown_bytes.decode("utf-8", errors="replace")
        
        # Regenerate markdown from JSON for PDF export (converts JSON cards to tables, removes KPIs)
        # Re-enabled to ensure Key Findings are processed correctly
        markdown_text = _get_pdf_optimized_markdown(blob_name, markdown_text)
        print(f"[PDF Export] Regenerated markdown length: {len(markdown_text)}")

        # Get enhanced CSS and HTML
        enhanced_css, body_html = _enhanced_markdown_to_html(markdown_text)
        print(f"[PDF Export] Body HTML length: {len(body_html)}")
        
        # Post-process HTML for additional styling (skip extra page break and risk replacements for cards)
        body_html = _post_process_html(
            body_html,
            skip_page_break_sections={
                "Key Findings & Recommendations",
                "Key Findings &amp; Recommendations",
                "Key Findings &amp;amp; Recommendations",
            },
            apply_risk_highlights=False,
            enable_section_page_breaks=False,
        )

        # Build complete HTML document with professional structure
        orientation = " landscape" if landscape else ""
        
        # Extract metadata for cover page
        import re
        
        # Default values
        sid = "Unknown"
        customer = "Unknown"
        report_date = os.getenv('CURRENT_DATE', 'Today')
        
        # 1. Try to get metadata from blob properties
        try:
            blob_props = blob_client.get_blob_properties()
            if blob_props.metadata:
                # Look for common keys
                customer = blob_props.metadata.get('customer_name', blob_props.metadata.get('Customer', customer))
                sid = blob_props.metadata.get('system_id', blob_props.metadata.get('SystemID', sid))
                # If report date is in metadata, use it
                report_date = blob_props.metadata.get('report_date', report_date)
        except Exception as e:
            print(f"[PDF Export] Error fetching blob metadata: {e}")

        # 2. Fallback: Try to extract from markdown content if still unknown
        if sid == "Unknown":
            # Pattern: # EWA Analysis for <SID> (<DATE>)
            title_match = re.search(r'^# EWA Analysis for\s+(.*?)\s+\((.*?)\)', markdown_text, re.MULTILINE)
            if title_match:
                sid = title_match.group(1).strip()
                if report_date == "Today": # Only override if not set from metadata
                    report_date = title_match.group(2).strip()
            
        # Try to find Customer Name if available in markdown
        if customer == "Unknown":
            customer_match = re.search(r'\*\*Customer:?\*\*\s*(.*)', markdown_text, re.IGNORECASE)
            if customer_match:
                customer = customer_match.group(1).strip()
        
        full_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>EWA Analysis Report</title>
            <style>
                html, body {{
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }}
                {enhanced_css}
                
                /* Print-specific styles */
                @page {{
                    size: {page_size}{orientation};
                    margin: 20mm 15mm;
                    @top-center {{
                        content: "EarlyWatch Alert Deep Dive";
                        font-size: 9pt;
                        color: #666666;
                        border-bottom: 1px solid #cccccc;
                        padding-bottom: 5px;
                    }}
                    @bottom-center {{
                        content: "Page " counter(page) " of " counter(pages);
                        font-size: 9pt;
                        color: #666666;
                        border-top: 1px solid #cccccc;
                        padding-top: 5px;
                    }}
                    @top-right {{
                        content: "Generated: " string(date);
                        font-size: 9pt;
                        color: #666666;
                    }}
                }}
                
                /* Cover Page Styling - SAP Style */
                .cover-page {{
                    page-break-after: always;
                    display: flex;
                    flex-direction: column;
                    justify-content: flex-start; /* Align to top */
                    align-items: center;
                    min-height: 90vh; /* Ensure full height for footer positioning */
                    width: 100%;
                    position: relative;
                }}
                
                .cover-block {{
                    background-color: #F0AB00; /* SAP Gold */
                    width: 100%;
                    padding: 60px 40px;
                    margin-bottom: 60px; /* Increased margin */
                    color: #ffffff;
                }}
                
                .cover-title {{
                    font-size: 36pt;
                    font-weight: 700;
                    margin: 0;
                    line-height: 1.2;
                    text-align: left;
                }}
                
                .cover-subtitle {{
                    font-size: 18pt;
                    font-weight: 400;
                    margin-top: 20px;
                    color: #ffffff;
                    text-align: left;
                }}
                
                .cover-footer {{
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    width: 100%;
                    text-align: left;
                    font-size: 10pt;
                    color: #666666;
                    border-top: 1px solid #F0AB00;
                    padding-top: 10px;
                    margin: 40px; /* Margin around the footer content */
                    box-sizing: border-box; /* Include padding/border in width */
                }}

                /* First page special styling to hide default headers */
                @page:first {{
                    margin: 0;
                    @top-center {{ content: none; }}
                    @bottom-center {{ content: none; }}
                    @top-right {{ content: none; }}
                }}
            </style>
        </head>
        <body>
            <!-- Cover Page -->
            <div class="cover-page">
                <div class="cover-block">
                    <div class="cover-title">EarlyWatch Alert Analysis</div>
                    <div class="cover-subtitle">Deep Dive Report</div>
                </div>
                <div style="padding: 0 40px; width: 100%;">
                    <p style="font-size: 14pt; margin-bottom: 15px;"><strong>SAP System ID:</strong> {sid}</p>
                    <p style="font-size: 14pt; margin-bottom: 15px;"><strong>Customer Name:</strong> {customer}</p>
                    <p style="font-size: 14pt; margin-bottom: 15px;"><strong>Generated On:</strong> {report_date}</p>
                </div>
                <div class="cover-footer">
                    &copy; 2025 SAP SE or an SAP affiliate company. All rights reserved.
                </div>
            </div>

            <div class="report-container">
                {body_html}
            </div>
        </body>
        </html>
        """

        # Generate PDF with enhanced styling
        pdf_bytes = HTML(string=full_html, base_url=".").write_pdf(
            stylesheets=[],
            presentational_hints=True
        )
        
        pdf_filename = os.path.splitext(blob_name)[0] + "_enhanced.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{pdf_filename}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting enhanced markdown to PDF: {str(e)}")


# Keep the original endpoint for backward compatibility
@router.get("/export-pdf")
async def export_markdown_to_pdf(
    blob_name: str,
    landscape: bool = Query(True, description="Render PDF in landscape orientation (default: true)"),
    page_size: str = Query("A4", description="Page size for PDF (e.g., A4, A3, Letter). Default: A4"),
):
    """Original endpoint - kept for backward compatibility."""
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized")

    try:
        if not blob_name.lower().endswith(".md"):
            raise HTTPException(status_code=400, detail="blob_name must point to a .md file")

        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, blob=blob_name
        )
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail=f"File {blob_name} not found")

        markdown_bytes = blob_client.download_blob().readall()
        markdown_text = markdown_bytes.decode("utf-8", errors="replace")
        
        # Regenerate markdown from JSON for PDF export (converts JSON cards to tables, removes KPIs)
        markdown_text = _get_pdf_optimized_markdown(blob_name, markdown_text)

        body_html = markdown(markdown_text, extras=["tables", "fenced-code-blocks"])
        
        # Convert findings table to cards for better PDF layout
        body_html = _convert_findings_table_to_cards(body_html)

        # Post-process HTML for additional styling (skip extra page break and risk replacements for cards)
        body_html = _post_process_html(
            body_html,
            skip_page_break_sections={
                "Key Findings & Recommendations",
                "Key Findings &amp; Recommendations",
                "Key Findings &amp;amp; Recommendations",
            },
            apply_risk_highlights=False,
            enable_section_page_breaks=False,
        )

        # Enhanced CSS styling
        styles = """
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            
            body { 
                font-family: 'Inter', Arial, sans-serif; 
                line-height: 1.6; 
                color: #2c3e50; 
                font-size: 11pt;
                margin: 0;
                padding: 0;
            }
            
            h1 { 
                font-size: 22pt; 
                font-weight: 700; 
                color: #1a202c; 
                margin: 25px 0 15px 0;
                border-bottom: 2px solid #4299e1;
                padding-bottom: 8px;
            }
            
            h2 { 
                font-size: 16pt; 
                font-weight: 600; 
                color: #2d3748; 
                margin: 20px 0 10px 0;
                border-left: 3px solid #4299e1;
                padding-left: 10px;
                background: #f7fafc;
            }
            
            h3 { 
                font-size: 13pt; 
                font-weight: 600; 
                color: #4a5568; 
                margin: 15px 0 8px 0;
            }
            
            table { 
                width: 100%; 
                border-collapse: collapse; 
                margin: 15px 0;
                font-size: 10pt;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }
            
            th { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; 
                font-weight: 600; 
                padding: 10px 8px; 
                text-align: left; 
            }
            
            td { 
                padding: 8px; 
                border-bottom: 1px solid #e2e8f0; 
            }
            
            tr:nth-child(even) {
                background-color: #f8fafc;
            }
            
            /* Card-based layout for findings */
            .findings-cards-container {
                display: block;
                margin: 8px 0 20px 0;
                break-before: avoid-page !important;
                page-break-before: avoid !important;
            }

            /* Ensure first card follows the heading without page break */
            h2 + .findings-cards-container {
                break-before: auto !important;
                page-break-before: auto !important;
                margin-top: 6px;
            }
            
            /* Logical divider between finding cards */
            .findings-cards-container .finding-card + .finding-card::before {
                content: "";
                display: block;
                height: 2px;
                background: linear-gradient(90deg, #e2e8f0, #cbd5e1, #e2e8f0);
                margin: 8px 0 16px 0;
            }
            
            .finding-card {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 0;
                margin-bottom: 20px;
                page-break-inside: auto;
                break-inside: auto;
                break-before: auto !important;
                page-break-before: auto !important;
                box-shadow: none;
                overflow: visible;
            }
            
            .card-header {
                background: linear-gradient(135deg, #f7fafc, #edf2f7);
                padding: 12px 15px;
                border-bottom: 2px solid #e2e8f0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .card-header-left {
                display: flex;
                gap: 10px;
                align-items: center;
            }
            
            .area-badge {
                background: #4299e1;
                color: white;
                padding: 3px 10px;
                border-radius: 4px;
                font-size: 9pt;
                font-weight: 600;
            }
            
            .severity-badge {
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: 700;
                font-size: 9pt;
                text-transform: uppercase;
            }
            
            .severity-critical {
                background: linear-gradient(135deg, #fed7d7, #feb2b2);
                color: #742a2a;
                border: 1px solid #fc8181;
            }
            
            .severity-high {
                background: linear-gradient(135deg, #feebc8, #fbd38d);
                color: #7b341e;
                border: 1px solid #f6ad55;
            }
            
            .severity-medium {
                background: linear-gradient(135deg, #fefcbf, #faf089);
                color: #744210;
                border: 1px solid #ecc94b;
            }
            
            .severity-low {
                background: linear-gradient(135deg, #c6f6d5, #9ae6b4);
                color: #22543d;
                border: 1px solid #68d391;
            }
            
            .card-body {
                padding: 15px;
            }
            
            .card-field {
                margin-bottom: 15px;
                page-break-inside: auto;
                break-inside: auto;
            }
            
            .card-field:last-child {
                margin-bottom: 0;
            }
            
            .field-label {
                font-weight: 600;
                color: #4a5568;
                font-size: 9pt;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 5px;
            }
            
            .field-value {
                color: #2d3748;
                font-size: 10pt;
                line-height: 1.6;
            }
            
            .field-value ul {
                margin: 5px 0 0 0;
                padding-left: 20px;
            }
            
            .field-value li {
                margin-bottom: 4px;
            }
        """
        
        orientation = " landscape" if landscape else ""
        styles = f"@page {{ size: {page_size}{orientation}; margin: 15mm; }}\n" + styles
        full_html = f"<html><head><meta charset='utf-8'><style>{styles}</style></head><body>{body_html}</body></html>"

        pdf_bytes = HTML(string=full_html, base_url=".").write_pdf()
        pdf_filename = os.path.splitext(blob_name)[0] + ".pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting markdown to PDF: {str(e)}")