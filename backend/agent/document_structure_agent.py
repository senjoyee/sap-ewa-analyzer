"""
DocumentStructureAgent - Extracts chapter/section outline from SAP EWA PDF reports.

This agent analyzes the document structure to identify all chapters and major sections,
ensuring comprehensive coverage during the subsequent analysis phase.
"""
from __future__ import annotations

import os
import json
import base64
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None  # type: ignore


class DocumentStructureAgent:
    """
    Extracts the table of contents / chapter structure from an EWA PDF.
    
    Returns a list of chapter names and page ranges to ensure comprehensive analysis coverage.
    Uses multi-page image sampling to capture the full document structure.
    """

    def __init__(self, client: Optional[AzureOpenAI] = None, model: Optional[str] = None, zoom: float = 3.0):
        """
        Initialize the DocumentStructureAgent.
        
        Args:
            client: Azure OpenAI client (created if not provided)
            model: Model to use (defaults to IMAGE_MODEL or gpt-5)
            zoom: Image zoom factor for page rendering (lower for ToC extraction to save tokens)
        """
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")

        self.client = client or AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self.model = model or os.getenv("IMAGE_MODEL", "gpt-5")
        self.zoom = zoom

    # ────────────────────────────────────────────────────────────────────────────
    # PDF rendering helpers
    # ────────────────────────────────────────────────────────────────────────────
    def _find_toc_pages(self, pdf_bytes: bytes) -> List[int]:
        """
        Find pages that likely contain the table of contents.
        
        Looks for keywords like 'Contents', 'Table of Contents', or early pages
        with chapter listings.
        """
        if fitz is None:
            return [0, 1]  # Default to first two pages
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            toc_pages = []
            # Search first 10 pages for ToC indicators
            search_limit = min(10, doc.page_count)
            
            toc_keywords = [
                "contents",
                "table of contents",
                "overview",
                "chapter",
                "section",
            ]
            
            for i in range(search_limit):
                page = doc.load_page(i)
                text = (page.get_text("text") or "").lower()
                
                # Score page based on ToC indicators
                score = sum(1 for kw in toc_keywords if kw in text)
                
                # Also check for numbered sections (1., 2., 3., etc.)
                numbered_sections = len([line for line in text.split('\n') 
                                       if line.strip() and line.strip()[0].isdigit()])
                
                if score >= 2 or numbered_sections >= 5:
                    toc_pages.append(i)
            
            # If no ToC found, sample strategic pages
            if not toc_pages:
                # Sample: cover, page 2-3, and a mid-document page
                mid_page = min(doc.page_count // 2, 20)
                toc_pages = [0, 1, 2, mid_page]
            
            # Limit to first 4 pages to manage token costs
            return toc_pages[:4]
        finally:
            doc.close()

    def _render_pages_png(self, pdf_bytes: bytes, page_indexes: List[int]) -> List[bytes]:
        """Render multiple pages to PNG bytes for vision analysis."""
        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) is not installed. Install 'pymupdf' to enable structure extraction.")
        
        images: List[bytes] = []
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            pc = doc.page_count
            for idx in page_indexes:
                if idx < 0 or idx >= pc:
                    continue
                page = doc.load_page(idx)
                mat = fitz.Matrix(self.zoom, self.zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                images.append(pix.tobytes("png"))
            return images
        finally:
            doc.close()

    # ────────────────────────────────────────────────────────────────────────────
    # Schema and prompt
    # ────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_function_schema() -> Dict[str, Any]:
        """Define the JSON schema for chapter structure extraction."""
        return {
            "type": "object",
            "properties": {
                "chapters": {
                    "type": "array",
                    "description": "List of all major chapters/sections found in the document",
                    "items": {
                        "type": "object",
                        "properties": {
                            "chapter_number": {
                                "type": "string",
                                "description": "Chapter number or identifier (e.g., '1', '2.1', 'A')"
                            },
                            "chapter_name": {
                                "type": "string",
                                "description": "Full chapter title"
                            },
                            "page_range": {
                                "type": "string",
                                "description": "Page range if visible (e.g., '5-12', 'Page 8')"
                            },
                            "subsections": {
                                "type": "array",
                                "description": "List of subsection names if visible",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["chapter_name"],
                        "additionalProperties": False
                    }
                },
                "document_type": {
                    "type": "string",
                    "description": "Type of document detected (e.g., 'SAP EarlyWatch Alert', 'Technical Report')"
                },
                "total_pages": {
                    "type": "integer",
                    "description": "Total number of pages if visible"
                }
            },
            "required": ["chapters"],
            "additionalProperties": False
        }

    @staticmethod
    def _build_instruction_prompt() -> str:
        """Create the instruction prompt for chapter extraction."""
        return """You are analyzing a technical document (likely an SAP EarlyWatch Alert report).

Your task: Extract the complete document structure - all chapters, major sections, and subsections.

Instructions:
1. Look for the Table of Contents, chapter headings, and section structure
2. Extract ALL major chapters/sections you can identify
3. Include chapter numbers, full titles, and page ranges when visible
4. List subsections under each major chapter when available
5. Common EWA chapters include: System Overview, Performance Analysis, Security, Configuration, Database, Capacity Planning, etc.

Be comprehensive - capture EVERY distinct chapter or major section you see."""

    # ────────────────────────────────────────────────────────────────────────────
    # API call
    # ────────────────────────────────────────────────────────────────────────────
    def _call_responses_images(self, page_pngs: List[bytes]) -> Dict[str, Any]:
        """Call Azure OpenAI Responses API with page images to extract structure."""
        tools = [
            {
                "type": "function",
                "name": "extract_document_structure",
                "description": "Extract the complete chapter/section structure from the document",
                "parameters": self._build_function_schema(),
            }
        ]
        instruction = self._build_instruction_prompt()

        content_items: List[Dict[str, Any]] = [
            {"type": "input_text", "text": instruction},
        ]
        
        # Add all page images
        for i, png in enumerate(page_pngs):
            b64 = base64.b64encode(png).decode("ascii")
            data_url = f"data:image/png;base64,{b64}"
            content_items.append({
                "type": "input_image", 
                "image_url": data_url
            })

        response = self.client.responses.create(
            model=self.model,
            tools=tools,
            tool_choice={"type": "function", "name": "extract_document_structure"},
            input=[{"role": "user", "content": content_items}],
            max_output_tokens=4096,
            reasoning={"effort": "low"},
        )

        # Log token usage
        try:
            usage = getattr(response, "usage", None)
            if usage:
                in_tok = getattr(usage, "input_tokens", None)
                out_tok = getattr(usage, "output_tokens", None)
                print(f"[DocumentStructureAgent] Token usage: input={in_tok}, output={out_tok}")
        except Exception:
            pass

        # Parse function call arguments
        args_str = None
        for item in getattr(response, "output", []) or []:
            try:
                item_type = getattr(item, "type", None)
                item_name = getattr(item, "name", None)
                item_args = getattr(item, "arguments", None)
                
                # Handle dict-based response
                if item_type is None and isinstance(item, dict):
                    item_type = item.get("type")
                    item_name = item.get("name")
                    item_args = item.get("arguments")
            except Exception:
                continue
                
            if item_type == "function_call" and item_name == "extract_document_structure":
                args_str = item_args
                if args_str:
                    break

        # Fallback to output_text if no function call found
        if not args_str:
            text = getattr(response, "output_text", None)
            if text:
                args_str = text

        if not args_str:
            raise RuntimeError("No structure extraction result returned from API")

        # Parse JSON
        if isinstance(args_str, dict):
            return args_str
        if not isinstance(args_str, str):
            raise ValueError("Function call arguments are not a string or dict")
        
        try:
            return json.loads(args_str)
        except Exception:
            # Try extracting JSON from markdown code blocks
            start = args_str.find("{")
            end = args_str.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = args_str[start : end + 1]
                return json.loads(candidate)
            raise

    # ────────────────────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────────────────────
    def extract_structure_from_pdf_bytes(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Extract document structure (chapters/sections) from PDF bytes.
        
        Args:
            pdf_bytes: Raw PDF file bytes
            
        Returns:
            Dict containing:
                - chapters: List of chapter objects with names, numbers, page ranges
                - document_type: Detected document type
                - total_pages: Total page count
        """
        if not pdf_bytes:
            return {"chapters": [], "document_type": "unknown", "total_pages": 0}
        
        # Find and render ToC pages
        toc_pages = self._find_toc_pages(pdf_bytes)
        print(f"[DocumentStructureAgent] Analyzing pages {toc_pages} for structure extraction")
        
        page_pngs = self._render_pages_png(pdf_bytes, toc_pages)
        if not page_pngs:
            # Fallback to first page
            page_pngs = self._render_pages_png(pdf_bytes, [0])
        
        result = self._call_responses_images(page_pngs)
        
        # Log extracted chapters for visibility
        chapters = result.get("chapters", [])
        print(f"[DocumentStructureAgent] Extracted {len(chapters)} chapters:")
        for ch in chapters:
            ch_name = ch.get("chapter_name", "Unknown")
            ch_num = ch.get("chapter_number", "")
            print(f"  - {ch_num} {ch_name}")
        
        return result
