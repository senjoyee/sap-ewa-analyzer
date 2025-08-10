"""
PDF KPI Extraction Test Script (Azure OpenAI Responses API)

Purpose:
- Upload a source EWA PDF to the Files API
- Ask the model to extract the Performance Indicators table EXACTLY as shown in the PDF,
  preserving units (%, ms, GB, etc.) and the trend ARROW SYMBOLS (e.g., →, ↗, ↘)
- Return results via a forced function call in structured JSON for easy verification

Usage:
  python backend/dev_tests/pdf_kpi_extraction_test.py --pdf path/to/report.pdf \
         [--model gpt-4.1] [--pretty] [--dump response.json]

Environment variables required:
  AZURE_OPENAI_ENDPOINT
  AZURE_OPENAI_API_KEY
  AZURE_OPENAI_API_VERSION
Optional:
  AZURE_OPENAI_SUMMARY_MODEL (default if --model not supplied)

Notes:
- This is a dev/test utility. It does not change production code or orchestration.
- It uses the Azure OpenAI Responses API with a function-calling schema tailored for KPIs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional
import base64
import io

from dotenv import load_dotenv
from openai import AzureOpenAI

# Optional dependency for page rendering
try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional
    fitz = None  # type: ignore

# Optional dependency for image composition
try:
    from PIL import Image, ImageOps, ImageFilter
except Exception:  # pragma: no cover - optional
    Image = None  # type: ignore
    ImageOps = None  # type: ignore
    ImageFilter = None  # type: ignore


def build_function_schema() -> Dict[str, Any]:
    """Return JSON Schema for the function call that extracts KPIs.

    The schema captures each row of the table with:
      - area: string
      - indicator: string
      - value: string (preserve unit & formatting exactly as in PDF)
      - trend: { symbol: string, name: enum }
    """
    return {
        "type": "object",
        "properties": {
            "kpis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string", "description": "Area column as shown (e.g., 'System Performance')"},
                        "indicator": {"type": "string", "description": "Indicator label exactly as shown"},
                        "value": {"type": "string", "description": "Value text exactly as shown, keep units and punctuation (e.g., '629 ms', '100 %', '3076.19 GB')"},
                        "trend": {
                            "type": "object",
                            "properties": {
                                "symbol": {
                                    "type": "string",
                                    "description": "Arrow glyph transcribed to the closest match from the legend. Use only: → (right/flat), ↗ (up-right), ↘ (down-right), ↑ (up), ↓ (down), ↔ (flat/bidirectional), or 'unknown'. Never return '-'.",
                                    "enum": ["→", "↗", "↘", "↑", "↓", "↔", "unknown"]
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Normalized name for the arrow direction.",
                                    "enum": [
                                        "right", "up", "down", "flat", "up-right", "down-right", "up-left", "down-left", "unknown"
                                    ]
                                },
                            },
                            "required": ["symbol"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["area", "indicator", "value", "trend"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["kpis"],
        "additionalProperties": False,
    }


def build_instruction_prompt() -> str:
    """Return the test prompt with precise extraction instructions."""
    return (
        "You are testing KPI extraction fidelity from an SAP EWA PDF.\n"
        "Extract the 'Performance Indicators' table exactly as it appears.\n"
        "Rules:\n"
        "- Use ONLY the information in the PDF. Do NOT infer or re-calculate.\n"
        "- Preserve the original formatting of 'value' including units (%, ms, GB, etc.) and punctuation.\n"
        "- For the 'trend', return the exact ARROW CHARACTER as 'trend.symbol' and also a normalized 'trend.name'\n"
        "  chosen from: right, up, down, flat, up-right, down-right, up-left, down-left, unknown.\n"
        "- Legend for trend.symbol (choose one): → (right/flat), ↗ (up-right), ↘ (down-right), ↑ (up), ↓ (down), ↔ (flat/bidirectional). If the PDF shows a different arrow graphic, choose the closest from the legend.\n"
        "- Never output '-' for trend.symbol; use one of the legend glyphs above or 'unknown'.\n"
        "- You may receive zoomed crops of the Trend column in addition to full-page images. Base the arrow direction on these crops when available.\n"
        "- Do NOT default all trends to '→'. For each row, inspect the glyph carefully; if uncertain, return 'unknown'.\n"
        "- Keep the original row order from the table.\n"
        "- If an entry is missing in the PDF, omit it. Do NOT invent rows.\n"
        "Return ONLY a function call to extract_kpis_from_pdf with the final JSON arguments."
    )


def build_instruction_prompt_single_image() -> str:
    """Instruction for single high-res page image input.

    We only send one full-page image. Ask the model to extract the table and return a function call
    with the structured JSON (kpis: [{area, indicator, value, trend{symbol,name}}]).
    """
    return (
        "You are given ONE high-resolution image of the 'Performance Indicators' page from an SAP EWA report.\n"
        "Task: Extract the entire table into JSON with rows in order, preserving exact 'value' formatting (units, punctuation).\n"
    )


def responses_extract_kpis_from_pdf(
    client: AzureOpenAI,
    model: str,
    pdf_path: str,
    image_bytes_list: Optional[List[bytes]] = None,
    row_crop_note: Optional[str] = None,
    include_pdf_file: bool = True,
    prior_kpis: Optional[List[Dict[str, Any]]] = None,
    trend_update_only: bool = False,
) -> Dict[str, Any]:
    """Upload the PDF to Files API and call Responses API to extract KPIs via function call.

    If image_bytes_list is provided, include those images as additional inputs to help the model
    visually read arrow glyphs when the PDF stores them as vector graphics.
    """
    # Upload PDF to Files API if requested
    file_id: Optional[str] = None
    if include_pdf_file:
        with open(pdf_path, "rb") as f:
            uploaded = client.files.create(file=f, purpose="assistants")
        file_id = uploaded.id

    tools = [
        {
            "type": "function",
            "name": "extract_kpis_from_pdf",
            "description": "Extract the Performance Indicators table exactly as shown in the PDF, preserving units and arrow symbols.",
            "parameters": build_function_schema(),
        }
    ]

    # If we're sending only a single page image (no PDF file and no prior_kpis), use the single-image instruction
    instruction = (
        build_instruction_prompt_single_image()
        if (not include_pdf_file and image_bytes_list and len(image_bytes_list) == 1 and not prior_kpis and not trend_update_only)
        else build_instruction_prompt()
    )

    # Compose input list: optional PDF file + instruction + optional images
    content_items: List[Dict[str, Any]] = []
    if file_id:
        content_items.append({"type": "input_file", "file_id": file_id})
    content_items.append({"type": "input_text", "text": instruction})
    # When updating trends only, provide prior KPI rows to keep textual context minimal
    if trend_update_only and prior_kpis:
        try:
            prior_json = json.dumps(prior_kpis, ensure_ascii=False)
        except Exception:
            prior_json = str(prior_kpis)
        content_items.append({
            "type": "input_text",
            "text": (
                "You already extracted the KPI rows (area, indicator, value). Do NOT change area, indicator, or value. "
                "Only determine and fill trend.symbol and trend.name for each row based on the provided row-strip image. "
                "Maintain the exact order and length of the list. Use this JSON as the base rows to update:\n" + prior_json
            ),
        })
    if row_crop_note:
        content_items.append({"type": "input_text", "text": row_crop_note})
    if image_bytes_list:
        # Limit to 10 images max; convert to string data URLs per Azure Responses API
        for idx, img_bytes in enumerate(image_bytes_list[:10]):
            b64 = base64.b64encode(img_bytes).decode("ascii")
            data_url = f"data:image/png;base64,{b64}"
            content_items.append({"type": "input_image", "image_url": data_url})

    response = client.responses.create(
        model=model,
        tools=tools,
        tool_choice={"type": "function", "name": "extract_kpis_from_pdf"},
        input=[{"role": "user", "content": content_items}],
        max_output_tokens=4096,
        reasoning={"effort": "low"},
    )

    # Print token usage if available
    try:
        usage = getattr(response, "usage", None)
        if usage:
            # Usage may have fields like input_tokens, output_tokens, total_tokens
            print("Token usage:")
            try:
                print(json.dumps(usage, default=lambda o: getattr(o, "__dict__", str(o)), indent=2))
            except Exception:
                print(str(usage))
    except Exception:
        pass

    # Extract function_call arguments (handle SDK objects or dicts)
    args_str = None
    for item in getattr(response, "output", []) or []:
        try:
            # Prefer attribute access (SDK objects)
            item_type = getattr(item, "type", None)
            item_name = getattr(item, "name", None)
            item_args = getattr(item, "arguments", None)
            if item_type is None and isinstance(item, dict):
                # Fallback for dicts
                item_type = item.get("type")
                item_name = item.get("name")
                item_args = item.get("arguments")
        except Exception:
            item_type = None
            item_name = None
            item_args = None
        if item_type == "function_call" and item_name == "extract_kpis_from_pdf":
            args_str = item_args
            if args_str:
                break

    if not args_str:
        # Fallback to output_text if present
        text = getattr(response, "output_text", None)
        if text:
            args_str = text

    if not args_str:
        # As a last resort dump and raise
        try:
            debug_dump = response.model_dump_json(indent=2)
        except Exception:
            debug_dump = str(response)
        raise RuntimeError(f"No function_call arguments returned. Raw response: {debug_dump}")

    # Parse JSON (be tolerant of code fences)
    if isinstance(args_str, dict):
        return args_str
    if not isinstance(args_str, str):
        raise ValueError("Function call arguments are not a string or dict")

    try:
        return json.loads(args_str)
    except Exception:
        start = args_str.find("{")
        end = args_str.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = args_str[start : end + 1]
            return json.loads(candidate)
        raise


def _find_kpi_pages(pdf_path: str) -> List[int]:
    """Heuristically find pages containing the KPI table by simple text search.

    Returns 0-based page indices. If PyMuPDF is unavailable, return empty.
    """
    if fitz is None:
        return []
    doc = fitz.open(pdf_path)
    matched: List[int] = []
    try:
        needles = [
            "Performance Indicators",
            "Area",
            "Indicators",
            "Value",
            "Trend",
        ]
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            hits = sum(1 for n in needles if n.lower() in text.lower())
            if hits >= 2:  # require at least two markers
                matched.append(i)
    finally:
        doc.close()
    return matched


def _render_pages_to_png_bytes(pdf_path: str, pages: List[int], zoom: float = 4.0) -> List[bytes]:
    """Render given 0-based page indices to PNG bytes via PyMuPDF. Empty if PyMuPDF missing."""
    if fitz is None or not pages:
        return []
    out: List[bytes] = []
    doc = fitz.open(pdf_path)
    try:
        mat = fitz.Matrix(zoom, zoom)
        for i in pages:
            if i < 0 or i >= doc.page_count:
                continue
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out.append(pix.tobytes("png"))
    finally:
        doc.close()
    return out


def _combine_images_vertically(img_bytes_list: List[bytes], pad: int = 4, bg=(255, 255, 255)) -> Optional[bytes]:
    """Combine a list of PNG images (bytes) into a single vertical strip. Returns PNG bytes or None if PIL missing."""
    if not img_bytes_list or Image is None:
        return None
    images: List[Image.Image] = []
    for b in img_bytes_list:
        try:
            images.append(Image.open(io.BytesIO(b)).convert("RGB"))
        except Exception:
            continue
    if not images:
        return None
    widths = [im.width for im in images]
    max_w = max(widths)
    total_h = sum(im.height for im in images) + pad * (len(images) - 1)
    canvas = Image.new("RGB", (max_w, total_h), color=bg)
    y = 0
    for idx, im in enumerate(images):
        x = (max_w - im.width) // 2
        canvas.paste(im, (x, y))
        y += im.height
        if idx < len(images) - 1:
            y += pad
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def _preprocess_image_bytes(b: bytes) -> bytes:
    """Grayscale + autocontrast + sharpen + light threshold; returns PNG bytes. If PIL missing, returns original."""
    if Image is None or ImageOps is None or ImageFilter is None:
        return b
    try:
        im = Image.open(io.BytesIO(b)).convert("L")  # grayscale
        im = ImageOps.autocontrast(im)
        im = im.filter(ImageFilter.SHARPEN)
        # Light threshold to accentuate arrows; keep details
        im = im.point(lambda p: 255 if p > 200 else 0, mode='1')  # binary
        im = im.convert("RGB")
        out = io.BytesIO()
        im.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return b


def _render_trend_row_crops_by_text(
    pdf_path: str,
    page_index: int,
    indicators: List[str],
    zoom: float = 6.0,
) -> List[bytes]:
    """Render row-aligned Trend crops by locating each KPI's indicator text on the page.

    For each indicator, we find its text rect, build a vertical slice in the Trend column band
    spanning to the next indicator's y-position (or to the bottom margin for the last row).
    """
    if fitz is None or not indicators:
        return []
    doc = fitz.open(pdf_path)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            return []
        page = doc.load_page(page_index)
        # Trend column band
        trend_rects = page.search_for("Trend") or []
        if not trend_rects:
            return []
        hdr = sorted(trend_rects, key=lambda r: (r.y0, r.x0))[0]
        page_rect = page.rect
        pad_x = 10
        top_margin = 6
        bottom_margin = 36
        left = max(hdr.x0 - pad_x, page_rect.x0)
        right = min(hdr.x1 + pad_x, page_rect.x1)
        top = min(hdr.y1 + top_margin, page_rect.y1)
        bottom = max(top + 20, page_rect.y1 - bottom_margin)
        band_height = max(1.0, bottom - top)
        slice_h = band_height / float(len(indicators))
        mat = fitz.Matrix(zoom, zoom)
        out: List[bytes] = []
        for i in range(len(indicators)):
            y0 = top + i * slice_h
            y1 = top + (i + 1) * slice_h
            clip = fitz.Rect(left, y0, right, y1)
            pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
            out.append(pix.tobytes("png"))
    finally:
        doc.close()
    return out


def _find_performance_page_index(pdf_path: str) -> int:
    """Return a single 0-based page index for the 'Performance Indicators' page.

    Uses `_find_kpi_pages()` and falls back to 0 if nothing matches.
    """
    pages = _find_kpi_pages(pdf_path)
    if pages:
        return pages[0]
    return 0


def _render_single_page_png(pdf_path: str, page_index: int, zoom: float = 4.0) -> bytes:
    """Render one PDF page to PNG bytes using PyMuPDF.

    Raises RuntimeError if rendering fails or PyMuPDF is unavailable.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed. Install 'pymupdf' to enable page rendering.")
    if page_index < 0:
        page_index = 0
    pages = _render_pages_to_png_bytes(pdf_path, [page_index], zoom=zoom)
    if not pages:
        raise RuntimeError(f"Failed to render page index {page_index} from {pdf_path}")
    return pages[0]


def _render_trend_row_crops(pdf_path: str, page_index: int, row_count: int, zoom: float = 6.0) -> List[bytes]:
    """Divide the Trend column vertical band into row_count equal slices and render each as a crop.

    This is a heuristic fallback when we cannot reliably detect table ruling lines.
    """
    if fitz is None or row_count <= 0:
        return []
    doc = fitz.open(pdf_path)
    out: List[bytes] = []
    try:
        if page_index < 0 or page_index >= doc.page_count:
            return []
        page = doc.load_page(page_index)
        rects = page.search_for("Trend") or []
        if not rects:
            return []
        hdr = sorted(rects, key=lambda r: (r.y0, r.x0))[0]
        page_rect = page.rect
        pad_x = 10
        top_margin = 6
        bottom_margin = 36
        left = max(hdr.x0 - pad_x, page_rect.x0)
        right = min(hdr.x1 + pad_x, page_rect.x1)
        top = min(hdr.y1 + top_margin, page_rect.y1)
        bottom = max(top + 20, page_rect.y1 - bottom_margin)
        band_height = max(1.0, bottom - top)
        slice_h = band_height / float(row_count)
        mat = fitz.Matrix(zoom, zoom)
        for i in range(row_count):
            y0 = top + i * slice_h
            y1 = top + (i + 1) * slice_h
            clip = fitz.Rect(left, y0, right, y1)
            pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
            out.append(pix.tobytes("png"))
    finally:
        doc.close()
    return out


def _render_trend_column_crops(pdf_path: str, pages: List[int], zoom: float = 4.0) -> List[bytes]:
    """Render zoomed crops around the 'Trend' column header down to the bottom margin.

    Heuristic: locate the first 'Trend' text rect on the page and crop a narrow vertical
    strip spanning from slightly above that rect to near the bottom of the page.
    """
    if fitz is None or not pages:
        return []
    out: List[bytes] = []
    doc = fitz.open(pdf_path)
    try:
        mat = fitz.Matrix(zoom, zoom)
        for i in pages:
            if i < 0 or i >= doc.page_count:
                continue
            page = doc.load_page(i)
            rects = page.search_for("Trend") or []
            if not rects:
                continue
            hdr = sorted(rects, key=lambda r: (r.y0, r.x0))[0]
            page_rect = page.rect
            pad_x = 10
            pad_top = 10
            bottom_margin = 36
            left = max(hdr.x0 - pad_x, page_rect.x0)
            right = min(hdr.x1 + pad_x, page_rect.x1)
            top = max(hdr.y0 - pad_top, page_rect.y0)
            bottom = max(top + 20, page_rect.y1 - bottom_margin)
            clip = fitz.Rect(left, top, right, bottom)
            pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
            out.append(pix.tobytes("png"))
    finally:
        doc.close()
    return out


def analyze_with_optional_images(
    client: AzureOpenAI,
    model: str,
    pdf_path: str,
    use_auto_image: bool,
    images_only: bool = False,
) -> Dict[str, Any]:
    # If images_only: perform two-pass images-only. First minimal images to get KPIs, then
    # add a combined row-crops strip aligned to KPI rows to improve arrow classification.
    if use_auto_image and images_only:
        pages = _find_kpi_pages(pdf_path)
        if not pages:
            pages = [0]
        # Minimal images: KPI page + one trend column crop
        base_images = _render_pages_to_png_bytes(pdf_path, pages[:1])
        trend_crops = _render_trend_column_crops(pdf_path, pages[:1])
        images_min = (base_images + trend_crops[:1])[:10]
        if not images_min:
            raise RuntimeError("Images-only mode requested but no KPI-page images could be rendered.")
        first = responses_extract_kpis_from_pdf(
            client, model, pdf_path, image_bytes_list=images_min, row_crop_note=None, include_pdf_file=False
        )
        kpis1 = first.get("kpis") or []
        if not kpis1:
            return first
        # Build row-wise crops using detected indicator texts where possible; fallback to equal slices
        indicators = [str(k.get("indicator", "")) for k in kpis1]
        row_crops = _render_trend_row_crops_by_text(pdf_path, pages[0], indicators)
        if not row_crops:
            row_crops = _render_trend_row_crops(pdf_path, pages[0], len(kpis1))
        # Row-strip only second pass: exclude full-page and trend-crop images to reduce tokens
        images2: List[bytes] = []
        row_crop_note = None
        if row_crops:
            combined = _combine_images_vertically(row_crops)
            if combined is not None:
                images2 = [combined]
                row_crop_note = (
                    "This image is a vertical strip of row-wise Trend crops, top (row #1) to bottom (row #N). "
                    "Map slice i to kpis[i-1]. Use this strip to classify each row's arrow precisely."
                )
            else:
                # Fallback: include individual row crops only (still no full-page image)
                images2 = row_crops[:10]
                if images2:
                    row_crop_note = (
                        f"Included {len(images2)} row-wise Trend crops in order from row #1 downward. "
                        f"Map crop i to kpis[i-1]."
                    )
        images2 = images2[:10]
        second = responses_extract_kpis_from_pdf(
            client,
            model,
            pdf_path,
            image_bytes_list=images2,
            row_crop_note=row_crop_note,
            include_pdf_file=False,
            prior_kpis=kpis1,
            trend_update_only=True,
        )
        return second

    # First run PDF-only. If many trend symbols are unknown and use_auto_image is True,
    # render KPI pages to images and retry including images in the request.
    result = responses_extract_kpis_from_pdf(client, model, pdf_path)
    kpis = result.get("kpis") or []

    def unknown_ratio(rows: List[Dict[str, Any]]) -> float:
        if not rows:
            return 1.0
        unk = 0
        for r in rows:
            t = (r.get("trend") or {}).get("symbol", "unknown")
            if t in ("unknown", "-"):
                unk += 1
        return unk / max(1, len(rows))

    if use_auto_image and unknown_ratio(kpis) >= 0.3:
        print("High unknown trend rate detected; attempting image-assisted retry...")
        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) is not installed. Install 'pymupdf' to enable --auto-image.")
        pages = _find_kpi_pages(pdf_path)
        if not pages:
            # Fallback: try first two pages
            pages = [0, 1] if fitz is not None else []
        base_images = _render_pages_to_png_bytes(pdf_path, pages[:1])  # limit to first KPI page
        # Add one zoomed trend-column crop from the same page
        trend_crops = _render_trend_column_crops(pdf_path, pages[:1])
        images = list(base_images) + trend_crops[:1]
        row_crop_note = None
        # Add row-wise crops aligned to the kpis order using the first KPI page
        if kpis and pages:
            indicators = [str(k.get("indicator", "")) for k in kpis]
            # Prefer text-anchored crops; fallback to equal-slice crops
            row_crops = _render_trend_row_crops_by_text(pdf_path, pages[0], indicators)
            if not row_crops:
                row_crops = _render_trend_row_crops(pdf_path, pages[0], len(kpis))
            if row_crops:
                # Preprocess individual crops (already done in text-anchored path), then combine
                combined = _combine_images_vertically(row_crops)
                if combined is not None:
                    images.append(combined)
                    row_crop_note = (
                        "The last image is a vertical strip of row-wise Trend crops, top (row #1) to bottom (row #N). "
                        "Map slice i to kpis[i-1]. Use this strip to classify each row's arrow precisely."
                    )
                else:
                    # PIL missing: include up to fit limit
                    remain_slots = max(0, 10 - len(images))
                    images.extend(row_crops[:remain_slots])
                    if remain_slots:
                        row_crop_note = (
                            f"Included {min(len(row_crops), remain_slots)} row-wise Trend crops in order from row #1 downward. "
                            f"Map crop i to kpis[i-1]."
                        )
        # Final guard: enforce max 10 images
        images = images[:10]
        if images:
            result = responses_extract_kpis_from_pdf(
                client, model, pdf_path, image_bytes_list=images, row_crop_note=row_crop_note
            )
        else:
            print("Could not render KPI pages; keeping original result.")
    return result


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Jsonify Performance Indicators table from a single high-res page image via Azure OpenAI Responses API")
    parser.add_argument("--pdf", required=True, help="Path to the EWA PDF to analyze")
    parser.add_argument("--model", default="gpt-5", help="Model deployment name (e.g., gpt-5)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--dump", default=None, help="Optional path to write raw JSON output to a file")
    parser.add_argument("--page", type=int, default=None, help="Optional 0-based page index override (otherwise auto-detect)")
    parser.add_argument("--zoom", type=float, default=4.0, help="Rendering zoom factor (4.0 ~ 288 DPI)")
    args = parser.parse_args()

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    if not endpoint or not api_key or not api_version:
        print("Missing Azure OpenAI environment variables: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION", file=sys.stderr)
        return 2

    if not os.path.isfile(args.pdf):
        print(f"PDF not found: {args.pdf}", file=sys.stderr)
        return 2

    client = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)

    # Determine page to render
    try:
        page_index = args.page if args.page is not None else _find_performance_page_index(args.pdf)
        page_png = _render_single_page_png(args.pdf, page_index, zoom=args.zoom)
    except Exception as e:
        print(f"Error rendering page image: {e}", file=sys.stderr)
        return 1

    # Call Responses API with ONLY the single page image; no PDF upload
    try:
        result = responses_extract_kpis_from_pdf(
            client,
            args.model,
            args.pdf,
            image_bytes_list=[page_png],
            row_crop_note=None,
            include_pdf_file=False,
        )
    except Exception as e:
        print(f"Error during extraction: {e}", file=sys.stderr)
        return 1

    if args.dump:
        try:
            with open(args.dump, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"Saved output to {args.dump}")
        except Exception as e:
            print(f"Warning: could not write dump file: {e}")

    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))

    # Quick summary to stdout
    kpis = result.get("kpis", [])
    print(f"\nExtracted {len(kpis)} KPI rows.")
    if kpis[:3]:
        print("Sample rows:")
        for row in kpis[:3]:
            area = row.get("area", "")
            ind = row.get("indicator", "")
            val = row.get("value", "")
            sym = (row.get("trend") or {}).get("symbol", "")
            print(f"- [{area}] {ind} = {val}  Trend: {sym}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
