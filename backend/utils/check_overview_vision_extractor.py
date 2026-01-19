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


def _normalize_subtopic(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return re.sub(r"[^a-z0-9\s]+", "", normalized)


def _extract_json_from_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return cleaned[start : end + 1]


def _extract_text_from_response_output(output_items) -> str:
    if not output_items:
        return ""
    chunks: List[str] = []
    for item in output_items:
        if isinstance(item, dict):
            content = item.get("content") or []
        else:
            content = getattr(item, "content", None) or []
        if isinstance(content, str):
            chunks.append(content)
            continue
        for part in content:
            if isinstance(part, dict):
                part_type = part.get("type")
                text_value = part.get("text")
            else:
                part_type = getattr(part, "type", None)
                text_value = getattr(part, "text", None)
            if isinstance(text_value, dict):
                text_value = text_value.get("value") or text_value.get("text")
            if part_type in {"output_text", "text"} and text_value:
                chunks.append(text_value)
    return "\n".join(chunks)

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

VISION_PROMPT = """You are an expert technical analyst. 
Your goal is to extract specific findings from the "Check Overview" table by validating text against visual markers.

### 1. THE STRATEGY: "VERIFY LEFT"
Instead of looking for icons first, you must scan the **Text Description Column** (Column 4) and validate each entry.

**Step 1: Identify Text Blocks**
- Scan down the right-most column (Column 4). Identify every distinct block of text.

**Step 2: The "Look Left" Test (CRITICAL)**
- For each text block, look at the cell **immediately to its left** (Column 3).
- **IS THERE A RATING ICON IN COLUMN 3?** (Checkmark, Square, Triangle, Circle).
    - **YES:** This is a valid finding. Extract the Text, the Icon Color, and the Main Topic (from Col 2).
    - **NO:** This is a **SECTION HEADER** or a continuation line. **IGNORE IT COMPLETELY.**

### 2. SPECIFIC CONSTRAINTS
- **Headers are NOT Findings:** Text like "Workload Distribution SHP" or "Management of SHP" usually appears in Col 4 but has **NO icon** in Col 3 (the icon is far left in Col 1). You must **SKIP** these.
- **Strict Association:** Never associate a text block with an icon that sits *above* or *below* it. The icon must be on the **same horizontal row** to the left.
- **Topic Inheritance:** Once you find a valid row, if the Topic Name (Col 2) is blank, use the last seen Topic Name from above.

### 3. OUTPUT FORMAT
Return a JSON list. Each object must contain:
- `Topic`: The Topic Name (Col 2).
- `Subtopic_Rating`: The color of the icon in Col 3 (red, yellow, green).
- `Subtopic`: The Text from Col 4.

**Processing Logic:**
1. Find Text.
2. Look Left -> Icon?
3. If Icon exists -> Output Row.
4. If No Icon -> Skip.
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


def render_pages_to_images(pdf_bytes: bytes, page_numbers: List[int], dpi: int = 300) -> List[Tuple[int, bytes]]:
    """
    Render specific PDF pages as PNG images.
    
    Args:
        pdf_bytes: PDF file content as bytes
        page_numbers: List of 0-indexed page numbers to render
        dpi: Resolution for rendering (default 300 for higher fidelity)
        
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


def _get_total_pages(pdf_bytes: bytes) -> int:
    try:
        pdf_stream = io.BytesIO(pdf_bytes)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        total_pages = len(doc)
        doc.close()
        return total_pages
    except Exception as e:
        logger.exception("Error counting PDF pages: %s", e)
        return 0


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
    
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "extract_check_overview",
            "schema": CHECK_OVERVIEW_SCHEMA,
            "strict": True,
        },
    }
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
        try:
            response = await asyncio.to_thread(
                lambda: client.responses.create(
                    model=model,
                    input=[{"role": "user", "content": content}],
                    response_format=response_format,
                    reasoning={"effort": "none"},
                    max_output_tokens=8192,
                )
            )
        except TypeError:
            response = await asyncio.to_thread(
                lambda: client.responses.create(
                    model=model,
                    input=[{"role": "user", "content": content}],
                    text=text_format,
                    reasoning={"effort": "none"},
                    max_output_tokens=8192,
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
            if hasattr(parsed, "model_dump"):
                return parsed.model_dump()
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                return parsed[0]
            if isinstance(parsed, list) and len(parsed) == 1 and hasattr(parsed[0], "model_dump"):
                return parsed[0].model_dump()
        
        # Fallback to output_text
        text = getattr(response, "output_text", None)
        if not text:
            text = _extract_text_from_response_output(getattr(response, "output", None))
        if text:
            logger.debug("Vision API raw output_text: %s", text)
            try:
                return json.loads(text)
            except json.JSONDecodeError as json_err:
                logger.warning("Failed to parse vision output_text as JSON: %s", json_err)
                logger.debug("Vision API output_text snippet: %s", text[:500])
                candidate = _extract_json_from_text(text)
                if candidate:
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError as candidate_err:
                        logger.warning("Failed to parse extracted JSON content: %s", candidate_err)
        else:
            logger.debug("Vision API response output (no text extracted): %s", repr(getattr(response, "output", None))[:1000])
        
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
    
    # Step 1: Always render the first 5 pages (assume Check Overview spans at least 2 pages)
    total_pages = _get_total_pages(pdf_bytes)
    if total_pages <= 0:
        return {"rows": [], "extraction_notes": "Unable to determine PDF page count"}

    pages_to_render = list(range(min(5, total_pages)))
    logger.info(
        "Rendering first %d pages as images for Check Overview extraction: %s",
        len(pages_to_render),
        [p + 1 for p in pages_to_render],
    )
    images = render_pages_to_images(pdf_bytes, pages_to_render)
    
    if not images:
        return {"rows": [], "extraction_notes": "Failed to render PDF pages as images"}
    
    # Step 3: Call vision API
    logger.info("Calling vision API with %d images...", len(images))
    result = await call_vision_api(client, model, images)

    cleaned_rows = []
    for row in result.get("rows", []):
        subtopic = row.get("Subtopic")
        if isinstance(subtopic, str):
            row["Subtopic"] = re.sub(r"\s*\*+$", "", subtopic).strip()

        topic = row.get("Topic")
        if isinstance(topic, str) and isinstance(row.get("Subtopic"), str):
            if topic.strip().lower() == row["Subtopic"].strip().lower():
                continue

        cleaned_rows.append(row)

    result["rows"] = cleaned_rows
    logger.info("Extracted %d Check Overview rows via vision", len(result.get("rows", [])))

    return result
