"""
Check Overview Vision Extractor

Extracts Check Overview table rows from EWA PDF pages using vision capabilities.
Targets the "Check Overview" table to capture Topic, Subtopic Rating, and Subtopic.
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
CHECK_OVERVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "description": "List of Check Overview table rows",
            "items": {
                "type": "object",
                "properties": {
                    "Topic": {
                        "type": "string",
                        "description": "Topic column value (may repeat for multiple subtopics)"
                    },
                    "Subtopic Rating": {
                        "type": "string",
                        "enum": ["red", "yellow", "green", "unknown"],
                        "description": "Icon color in the Subtopic Rating column"
                    },
                    "Subtopic": {
                        "type": "string",
                        "description": "Subtopic column value"
                    }
                },
                "required": ["Topic", "Subtopic Rating", "Subtopic"],
                "additionalProperties": False
            }
        },
        "extraction_notes": {
            "type": "string",
            "description": "Any notes about the extraction quality or issues"
        }
    },
    "required": ["rows", "extraction_notes"],
    "additionalProperties": False
}

VISION_PROMPT = """You are an expert at analyzing SAP EarlyWatch Alert (EWA) report pages.

Analyze this image from an EWA report and extract ALL rows from the "Check Overview" table.

The table has four columns: "Topic Rating", "Topic", "Subtopic Rating", "Subtopic".
Return one JSON object per row with:
1. **Topic**: The Topic column text (repeat the last seen Topic when the cell is blank).
2. **Subtopic Rating**: The icon color in the Subtopic Rating column (red/yellow/green).
3. **Subtopic**: The Subtopic column text.

Important:
- Ignore the "Topic Rating" column entirely.
- Extract EVERY row that has a Subtopic Rating icon; if the Subtopic Rating icon is missing, skip the row.
- Pay close attention to the Subtopic Rating icon colors.
- If you cannot determine the icon color clearly, use "unknown".
"""


def find_check_overview_pages(pdf_bytes: bytes) -> List[int]:
    """
    Find page numbers containing the "Check Overview" table.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        List of 0-indexed page numbers containing Check Overview sections
    """
    check_pages = []
    
    try:
        pdf_stream = io.BytesIO(pdf_bytes)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        
        # Strategy 1: Find "Check Overview" heading
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            if re.search(r'\bcheck\s+overview\b', text, re.IGNORECASE):
                logger.info("Found 'Check Overview' table on page %d", page_num + 1)
                check_pages.append(page_num)
                # Include the next two pages as the table usually continues
                for offset in (1, 2):
                    next_page = page_num + offset
                    if next_page < len(doc):
                        check_pages.append(next_page)
                        logger.info("Including continuation page %d", next_page + 1)
                break  # Found the table, no need to continue
        
        # Strategy 2: If Check Overview not found, fall back to keyword search
        if not check_pages:
            logger.warning("'Check Overview' not found, using keyword fallback")
            keywords = [
                "check overview",
            ]
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text().lower()
                
                for keyword in keywords:
                    if keyword in text:
                        if page_num not in check_pages:
                            check_pages.append(page_num)
                            logger.info("Found Check Overview on page %d (keyword: '%s')", page_num + 1, keyword)
                        break
        
        # Strategy 3: If still no pages found, try first 5 pages as last resort
        if not check_pages:
            logger.warning("No Check Overview found via keywords, checking first 5 pages")
            check_pages = list(range(min(5, len(doc))))
        
        doc.close()
        
        return check_pages
        
    except Exception as e:
        logger.exception("Error finding Check Overview pages: %s", e)
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
        Structured Check Overview extraction result
    """
    if not images:
        return {"rows": [], "extraction_notes": "No images provided"}
    
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
            "name": "extract_check_overview",
            "schema": CHECK_OVERVIEW_SCHEMA,
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
                reasoning={"effort": "high"},
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
        
        return {"rows": [], "extraction_notes": "Failed to parse vision API response"}
        
    except Exception as e:
        logger.exception("Vision API call failed: %s", e)
        return {"rows": [], "extraction_notes": f"Vision API error: {str(e)}"}


async def extract_check_overview_with_vision(
    pdf_bytes: bytes,
    client=None,
    model: str = None,
) -> Dict[str, Any]:
    """
    Main entry point: Extract Check Overview table from PDF using vision.
    
    Args:
        pdf_bytes: PDF file content as bytes
        client: Optional Azure OpenAI client (will create one if not provided)
        model: Optional model name (defaults to gpt-4.1 which supports vision)
        
    Returns:
        Dictionary with 'rows' list and 'extraction_notes'
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
            return {"rows": [], "extraction_notes": "Azure OpenAI configuration missing"}
        
        client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
        )
    
    # Step 1: Find pages with Check Overview content
    logger.info("Searching for Check Overview pages in PDF...")
    check_pages = find_check_overview_pages(pdf_bytes)
    
    if not check_pages:
        return {"rows": [], "extraction_notes": "No Check Overview sections found in PDF"}
    
    logger.info("Found %d pages with Check Overview content: %s", len(check_pages), [p + 1 for p in check_pages])
    
    # Step 2: Render pages as images (limit to first 3 pages to control costs)
    pages_to_render = check_pages[:3]
    logger.info("Rendering %d pages as images...", len(pages_to_render))
    images = render_pages_to_images(pdf_bytes, pages_to_render)
    
    if not images:
        return {"rows": [], "extraction_notes": "Failed to render PDF pages as images"}
    
    # Step 3: Call vision API
    logger.info("Calling vision API with %d images...", len(images))
    result = await call_vision_api(client, model, images)
    
    # Post-process: deduplicate rows by (Topic, Subtopic Rating, Subtopic)
    seen = set()
    unique_rows = []
    for row in result.get("rows", []):
        topic = (row.get("Topic") or "").strip()
        rating = (row.get("Subtopic Rating") or "").strip()
        subtopic = (row.get("Subtopic") or "").strip()
        key = (topic, rating, subtopic)
        if topic and subtopic and key not in seen:
            seen.add(key)
            unique_rows.append(row)
    
    result["rows"] = unique_rows
    logger.info("Extracted %d unique Check Overview rows via vision", len(unique_rows))
    
    return result
