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
    if not blob_service_client:
        return markdown_text
    
    try:
        # Derive the JSON blob name from the markdown blob name
        # Pattern: filename_AI.md -> filename_AI.json
        base_name = os.path.splitext(blob_name)[0]
        json_blob_name = f"{base_name}.json"
        
        # Try to download the JSON file
        json_blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, blob=json_blob_name
        )
        
        if json_blob_client.exists():
            json_bytes = json_blob_client.download_blob().readall()
            json_data = json.loads(json_bytes.decode("utf-8", errors="replace"))
            
            # Regenerate markdown with pdf_export=True
            print(f"[PDF Export] Regenerating markdown from JSON: {json_blob_name}")
            return json_to_markdown(json_data, pdf_export=True)
        else:
            print(f"[PDF Export] JSON not found ({json_blob_name}), using original markdown")
            return markdown_text
            
    except Exception as e:
        print(f"[PDF Export] Error loading JSON for PDF optimization: {e}")
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

        area_text = html.escape(area_text_raw.strip()) if area_text_raw else 'General'
        severity_lower = severity_text_raw.lower().strip().strip('"\' >') if severity_text_raw else ''
        if severity_lower not in {'critical', 'high', 'medium', 'low'}:
            severity_lower = 'medium'
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
    
    # Convert markdown to HTML with enhanced features
    html_body = markdown(
        markdown_text,
        extras=[
            "tables", "fenced-code-blocks", "header-ids", "toc", 
            "strike", "task_list", "break-on-newline"
        ]
    )
    
    # Convert findings table to cards for better PDF layout
    html_body = _convert_findings_table_to_cards(html_body)
    
    # Enhanced CSS styling for professional appearance
    enhanced_css = """
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        
        /* Reset and base styles */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #2c3e50;
            background: #ffffff;
            font-size: 11pt;
        }
        
        /* Typography hierarchy */
        h1 {
            font-size: 24pt;
            font-weight: 700;
            color: #1a202c;
            margin: 30px 0 20px 0;
            padding-bottom: 10px;
            border-bottom: 3px solid #4299e1;
            page-break-after: avoid;
        }
        
        h2 {
            font-size: 18pt;
            font-weight: 600;
            color: #2d3748;
            margin: 25px 0 15px 0;
            padding: 10px 0;
            border-left: 4px solid #4299e1;
            padding-left: 15px;
            page-break-after: avoid;
            background: #f7fafc;
        }
        
        h3 {
            font-size: 14pt;
            font-weight: 600;
            color: #4a5568;
            margin: 20px 0 10px 0;
            page-break-after: avoid;
        }
        
        h4 {
            font-size: 12pt;
            font-weight: 500;
            color: #718096;
            margin: 15px 0 8px 0;
            page-break-after: avoid;
        }
        
        /* Paragraphs and lists */
        p {
            margin-bottom: 12px;
            text-align: justify;
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
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border-radius: 8px;
            overflow: hidden;
        }
        
        th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
            padding: 12px 8px;
            text-align: left;
            border-bottom: 2px solid #4c51bf;
        }
        
        td {
            padding: 10px 8px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
        }
        
        tr:nth-child(even) {
            background-color: #f8fafc;
        }
        
        tr:hover {
            background-color: #edf2f7;
        }
        
        /* Risk level styling */
        .risk-critical {
            background: linear-gradient(135deg, #fed7d7, #feb2b2);
            color: #742a2a;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 9pt;
        }
        
        .risk-high {
            background: linear-gradient(135deg, #feebc8, #fbd38d);
            color: #7b341e;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 9pt;
        }
        
        .risk-medium {
            background: linear-gradient(135deg, #fefcbf, #faf089);
            color: #744210;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 9pt;
        }
        
        .risk-low {
            background: linear-gradient(135deg, #c6f6d5, #9ae6b4);
            color: #22543d;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 9pt;
        }
        
        /* Status indicators */
        .status-good {
            color: #38a169;
            font-weight: 600;
        }
        
        .status-fair {
            color: #d69e2e;
            font-weight: 600;
        }
        
        .status-poor {
            color: #e53e3e;
            font-weight: 600;
        }
        
        /* Code blocks */
        pre {
            background: #2d3748;
            color: #e2e8f0;
            padding: 15px;
            border-radius: 6px;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 9pt;
            overflow-x: auto;
            margin: 15px 0;
            border-left: 4px solid #4299e1;
        }
        
        code {
            background: #edf2f7;
            color: #2d3748;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 9pt;
        }
        
        /* Blockquotes */
        blockquote {
            border-left: 4px solid #4299e1;
            margin: 20px 0;
            padding: 15px 20px;
            background: #f7fafc;
            font-style: italic;
            color: #4a5568;
        }
        
        /* Horizontal rules */
        hr {
            border: none;
            height: 2px;
            background: linear-gradient(90deg, #4299e1, #667eea, #764ba2);
            margin: 30px 0;
            border-radius: 1px;
        }
        
        /* Page breaks */
        .page-break {
            page-break-before: always;
        }
        
        .avoid-break {
            page-break-inside: avoid;
        }
        
        /* Headers with icons */
        .section-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .section-icon {
            font-size: 1.2em;
            margin-right: 10px;
        }
        
        /* Summary boxes */
        .summary-box {
            background: linear-gradient(135deg, #f7fafc, #edf2f7);
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .critical-alert {
            background: linear-gradient(135deg, #fed7d7, #feb2b2);
            border: 1px solid #fc8181;
            border-left: 5px solid #e53e3e;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
        }
        
        .warning-alert {
            background: linear-gradient(135deg, #fef5e7, #fed7aa);
            border: 1px solid #f6ad55;
            border-left: 5px solid #ed8936;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
        }
        
        .info-alert {
            background: linear-gradient(135deg, #e6fffa, #b2f5ea);
            border: 1px solid #81e6d9;
            border-left: 5px solid #38b2ac;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
        }
        
        /* Card-based layout for findings */
        .findings-cards-container {
            display: block;
            margin: 20px 0;
        }
        
        .finding-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-bottom: 20px;
            page-break-inside: avoid;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            overflow: hidden;
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
            page-break-inside: avoid;
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
    
    return enhanced_css, html_body


def _post_process_html(
    html_content: str,
    *,
    skip_page_break_sections: set[str] | None = None,
    apply_risk_highlights: bool = True,
) -> str:
    """Apply additional HTML enhancements and optional risk level styling."""
    
    skip_page_break_sections = skip_page_break_sections or set()

    # Add page breaks before major table sections (unless skipped)
    for section_name in ['Positive Findings', 'Key Findings', 'Recommendations', 'Parameters']:
        if section_name in skip_page_break_sections:
            continue
        pattern = fr'(<h\d[^>]*>)({section_name})(</h\d>)'
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
        markdown_text = _get_pdf_optimized_markdown(blob_name, markdown_text)

        # Get enhanced CSS and HTML
        enhanced_css, body_html = _enhanced_markdown_to_html(markdown_text)
        
        # Post-process HTML for additional styling (skip extra page break and risk replacements for cards)
        body_html = _post_process_html(
            body_html,
            skip_page_break_sections={"Key Findings & Recommendations"},
            apply_risk_highlights=False,
        )

        # Build complete HTML document with professional structure
        orientation = " landscape" if landscape else ""
        
        full_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>EWA Analysis Report</title>
            <style>
                {enhanced_css}
                
                /* Print-specific styles */
                @page {{
                    size: {page_size}{orientation};
                    margin: 20mm 15mm;
                    @top-center {{
                        content: "EarlyWatch Alert Deep Dive";
                        font-size: 10pt;
                        color: #4a5568;
                        border-bottom: 1px solid #e2e8f0;
                        padding-bottom: 5px;
                    }}
                    @bottom-center {{
                        content: "Page " counter(page) " of " counter(pages);
                        font-size: 9pt;
                        color: #718096;
                        border-top: 1px solid #e2e8f0;
                        padding-top: 5px;
                    }}
                    @top-right {{
                        content: "Generated: " string(date);
                        font-size: 9pt;
                        color: #718096;
                    }}
                }}
                
                /* First page special styling */
                h1:first-of-type {{
                    margin-top: 0;
                    font-size: 28pt;
                    text-align: center;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    border-bottom: 3px solid #667eea;
                    padding-bottom: 15px;
                }}
            </style>
        </head>
        <body>
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
            skip_page_break_sections={"Key Findings & Recommendations"},
            apply_risk_highlights=False,
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
                margin: 20px 0;
            }
            
            .finding-card {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-bottom: 20px;
                page-break-inside: avoid;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                overflow: hidden;
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
                page-break-inside: avoid;
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