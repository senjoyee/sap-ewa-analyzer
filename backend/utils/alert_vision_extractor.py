"""
Alert Vision Extractor

Extracts alert information from EWA PDF pages using vision capabilities.
Specifically targets "Alerts Decisive for Red Report" and "Alert Overview" sections
to identify alert headlines and their severity based on visual icon colors (Red/Yellow).
"""

import io
import json
import re
import base64
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Schema for structured output
ALERT_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "alerts": {
            "type": "array",
            "description": "List of all alerts found in the image",
            "items": {
                "type": "object",
                "properties": {
                    "headline": {
                        "type": "string",
                        "description": "The exact alert text/headline as shown in the document"
                    },
                    "icon_color": {
                        "type": "string",
                        "enum": ["red", "yellow", "green", "unknown"],
                        "description": "Color of the icon/indicator next to the alert"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"],
                        "description": "Severity based on icon: red->critical/high, yellow->medium, green->low"
                    },
                    "section": {
                        "type": "string",
                        "enum": ["decisive_for_red", "alert_overview", "other"],
                        "description": "Which section this alert was found in"
                    }
                },
                "required": ["headline", "icon_color", "severity", "section"],
                "additionalProperties": False
            }
        },
        "extraction_notes": {
            "type": "string",
            "description": "Any notes about the extraction quality or issues"
        }
    },
    "required": ["alerts", "extraction_notes"],
    "additionalProperties": False
}

VISION_PROMPT = """You are an expert at analyzing SAP EarlyWatch Alert (EWA) report pages.

Analyze this image from an EWA report and extract ALL alerts visible in the "Alerts Decisive for Red Report" and "Alert Overview" sections.

For each alert, identify:
1. **headline**: The exact text of the alert
2. **icon_color**: The color of the icon/indicator (red flash/exclamation = "red", yellow exclamation = "yellow", green = "green")
3. **severity**: Map icon colors as follows:
   - Red icons (especially in "Decisive for Red" section) -> "critical" 
   - Red icons in "Alert Overview" -> "high"
   - Yellow icons -> "medium"
   - Green icons -> "low"
4. **section**: Which section contains the alert ("decisive_for_red" or "alert_overview")

Important:
- Extract EVERY alert visible, do not skip any
- Pay close attention to the icon colors - this is crucial for severity classification
- If you cannot determine the icon color clearly, mark as "unknown" with severity "medium"
"""


def find_alert_pages(pdf_bytes: bytes) -> List[int]:
    """
    Find page numbers containing "Alert Overview" or "Alerts Decisive" sections.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        List of 0-indexed page numbers containing alert sections
    """
    alert_pages = []
    
    try:
        pdf_stream = io.BytesIO(pdf_bytes)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        
        # Keywords to search for
        keywords = [
            "alerts decisive for red report",
            "alert overview",
            "alerts overview",
            "decisive for red",
        ]
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().lower()
            
            for keyword in keywords:
                if keyword in text:
                    if page_num not in alert_pages:
                        alert_pages.append(page_num)
                        logger.info("Found alert content on page %d (keyword: '%s')", page_num + 1, keyword)
                    break
        
        doc.close()
        
        # If no pages found via keywords, try first 5 pages as fallback
        if not alert_pages:
            logger.warning("No alert sections found via keywords, checking first 5 pages")
            alert_pages = list(range(min(5, len(doc))))
        
        return alert_pages
        
    except Exception as e:
        logger.exception("Error finding alert pages: %s", e)
        return []


def render_pages_to_images(pdf_bytes: bytes, page_numbers: List[int], dpi: int = 150) -> List[Tuple[int, bytes]]:
    """
    Render specific PDF pages as PNG images.
    
    Args:
        pdf_bytes: PDF file content as bytes
        page_numbers: List of 0-indexed page numbers to render
        dpi: Resolution for rendering (default 150 for good quality/size balance)
        
    Returns:
        List of tuples (page_number, png_bytes)
    """
    images = []
    
    try:
        pdf_stream = io.BytesIO(pdf_bytes)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        
        zoom = dpi / 72  # Default PDF DPI is 72
        mat = fitz.Matrix(zoom, zoom)
        
        for page_num in page_numbers:
            if page_num < len(doc):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=mat)
                png_bytes = pix.tobytes("png")
                images.append((page_num, png_bytes))
                logger.info("Rendered page %d as PNG (%d bytes)", page_num + 1, len(png_bytes))
        
        doc.close()
        
    except Exception as e:
        logger.exception("Error rendering pages to images: %s", e)
    
    return images


async def call_vision_api(
    client,
    model: str,
    images: List[Tuple[int, bytes]],
) -> Dict[str, Any]:
    """
    Call the vision API with rendered page images.
    
    Args:
        client: Azure OpenAI client instance
        model: Model deployment name (should support vision, e.g., gpt-4o, gpt-4.1)
        images: List of (page_number, png_bytes) tuples
        
    Returns:
        Structured alert extraction result
    """
    if not images:
        return {"alerts": [], "extraction_notes": "No images provided"}
    
    # Build message content with images
    content = [{"type": "input_text", "text": VISION_PROMPT}]
    
    for page_num, png_bytes in images:
        # Encode image as base64 data URL
        b64_image = base64.b64encode(png_bytes).decode("utf-8")
        content.append({
            "type": "input_image",
            "image_url": f"data:image/png;base64,{b64_image}",
        })
        content.append({
            "type": "input_text",
            "text": f"[Page {page_num + 1}]"
        })
    
    # Prepare structured output format
    text_format = {
        "format": {
            "type": "json_schema",
            "name": "extract_alerts",
            "schema": ALERT_EXTRACTION_SCHEMA,
            "strict": True,
        }
    }
    
    try:
        # Call API using responses endpoint
        response = await asyncio.to_thread(
            lambda: client.responses.create(
                model=model,
                input=[{"role": "user", "content": content}],
                text=text_format,
                max_output_tokens=4096,
            )
        )
        
        # Log token usage
        try:
            usage = getattr(response, "usage", None)
            if usage:
                in_tok = getattr(usage, "input_tokens", None)
                out_tok = getattr(usage, "output_tokens", None)
                logger.info("Vision API token usage: input=%s, output=%s", in_tok, out_tok)
        except Exception:
            pass
        
        # Extract structured output
        parsed = getattr(response, "output_parsed", None)
        if parsed is not None:
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                return parsed[0]
        
        # Fallback to output_text
        text = getattr(response, "output_text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        
        return {"alerts": [], "extraction_notes": "Failed to parse vision API response"}
        
    except Exception as e:
        logger.exception("Vision API call failed: %s", e)
        return {"alerts": [], "extraction_notes": f"Vision API error: {str(e)}"}


async def extract_alerts_with_vision(
    pdf_bytes: bytes,
    client=None,
    model: str = None,
) -> Dict[str, Any]:
    """
    Main entry point: Extract alerts from PDF using vision.
    
    Args:
        pdf_bytes: PDF file content as bytes
        client: Optional Azure OpenAI client (will create one if not provided)
        model: Optional model name (defaults to gpt-4.1 which supports vision)
        
    Returns:
        Dictionary with 'alerts' list and 'extraction_notes'
    """
    import os
    from openai import AzureOpenAI
    
    # Default model for vision
    if model is None:
        model = os.getenv("AZURE_OPENAI_SUMMARY_MODEL", "gpt-4.1")
    
    # Create client if not provided
    if client is None:
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        
        if not endpoint or not api_key or not api_version:
            return {"alerts": [], "extraction_notes": "Azure OpenAI configuration missing"}
        
        client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
        )
    
    # Step 1: Find pages with alert content
    logger.info("Searching for alert pages in PDF...")
    alert_pages = find_alert_pages(pdf_bytes)
    
    if not alert_pages:
        return {"alerts": [], "extraction_notes": "No alert sections found in PDF"}
    
    logger.info("Found %d pages with alert content: %s", len(alert_pages), [p + 1 for p in alert_pages])
    
    # Step 2: Render pages as images (limit to first 3 pages to control costs)
    pages_to_render = alert_pages[:3]
    logger.info("Rendering %d pages as images...", len(pages_to_render))
    images = render_pages_to_images(pdf_bytes, pages_to_render)
    
    if not images:
        return {"alerts": [], "extraction_notes": "Failed to render PDF pages as images"}
    
    # Step 3: Call vision API
    logger.info("Calling vision API with %d images...", len(images))
    result = await call_vision_api(client, model, images)
    
    # Post-process: deduplicate alerts by headline
    seen = set()
    unique_alerts = []
    for alert in result.get("alerts", []):
        headline = alert.get("headline", "").strip()
        if headline and headline not in seen:
            seen.add(headline)
            unique_alerts.append(alert)
    
    result["alerts"] = unique_alerts
    logger.info("Extracted %d unique alerts via vision", len(unique_alerts))
    
    return result
