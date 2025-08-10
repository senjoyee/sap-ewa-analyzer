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


class KPIImageAgent:
    """
    Extracts the 'Performance Indicators' table by sending ONE high-resolution
    page image to the Azure OpenAI Responses API (IMAGE_MODEL, e.g., gpt-5).

    Returns a dict like: {"kpis": [{"area","indicator","value","trend":{"symbol","name"}} ...]}
    """

    def __init__(self, client: Optional[AzureOpenAI] = None, model: Optional[str] = None, zoom: float = 6.0):
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
    # Rendering helpers
    # ────────────────────────────────────────────────────────────────────────────
    def _find_performance_page_index(self, pdf_bytes: bytes) -> int:
        """Heuristically find page index containing 'Performance Indicators'. Fallback to 0."""
        if fitz is None:
            return 0
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            needles = [
                "Performance Indicators",
                "Area",
                "Indicators",
                "Value",
                "Trend",
            ]
            candidates: List[int] = []
            for i, page in enumerate(doc):
                text = page.get_text("text") or ""
                hits = sum(1 for n in needles if n.lower() in text.lower())
                if hits >= 2:
                    candidates.append(i)
            if candidates:
                return candidates[0]
            return 0
        finally:
            doc.close()

    def _render_single_page_png(self, pdf_bytes: bytes, page_index: int) -> bytes:
        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) is not installed. Install 'pymupdf' to enable KPI image extraction.")
        if page_index < 0:
            page_index = 0
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if page_index >= doc.page_count:
                page_index = 0
            page = doc.load_page(page_index)
            mat = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            return pix.tobytes("png")
        finally:
            doc.close()

    # ────────────────────────────────────────────────────────────────────────────
    # Responses API call
    # ────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_function_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "kpis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "area": {"type": "string"},
                            "indicator": {"type": "string"},
                            "value": {"type": "string"},
                            "trend": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string", "enum": ["→", "↗", "↘", "↑", "↓", "↔", "unknown"]},
                                    "name": {"type": "string"},
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

    @staticmethod
    def _build_instruction_prompt_single_image() -> str:
        return (
            "You are given ONE high-resolution image of the 'Performance Indicators' page from an SAP EWA report.\n"
            "Task: Extract the entire table into JSON with rows in order, preserving exact 'value' formatting (units, punctuation).\n"
        )

    def _call_responses_single_image(self, page_png: bytes) -> Dict[str, Any]:
        tools = [
            {
                "type": "function",
                "name": "extract_kpis_from_pdf",
                "description": "Extract the Performance Indicators table exactly as shown in the PDF, preserving units and arrow symbols.",
                "parameters": self._build_function_schema(),
            }
        ]
        instruction = self._build_instruction_prompt_single_image()

        b64 = base64.b64encode(page_png).decode("ascii")
        data_url = f"data:image/png;base64,{b64}"

        content_items: List[Dict[str, Any]] = [
            {"type": "input_text", "text": instruction},
            {"type": "input_image", "image_url": data_url},
        ]

        response = self.client.responses.create(
            model=self.model,
            tools=tools,
            tool_choice={"type": "function", "name": "extract_kpis_from_pdf"},
            input=[{"role": "user", "content": content_items}],
            max_output_tokens=4096,
            reasoning={"effort": "low"},
        )

        # Optional: Log token usage
        try:
            usage = getattr(response, "usage", None)
            if usage:
                try:
                    print("[KPIImageAgent] Token usage:")
                    print(json.dumps(usage, default=lambda o: getattr(o, "__dict__", str(o)), indent=2))
                except Exception:
                    print(str(usage))
        except Exception:
            pass

        # Parse function call args
        args_str = None
        for item in getattr(response, "output", []) or []:
            try:
                item_type = getattr(item, "type", None)
                item_name = getattr(item, "name", None)
                item_args = getattr(item, "arguments", None)
                if item_type is None and isinstance(item, dict):
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
            text = getattr(response, "output_text", None)
            if text:
                args_str = text
        if not args_str:
            try:
                debug_dump = response.model_dump_json(indent=2)
            except Exception:
                debug_dump = str(response)
            raise RuntimeError(f"No function_call arguments returned. Raw response: {debug_dump}")

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

    # ────────────────────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────────────────────
    def extract_kpis_from_pdf_bytes(self, pdf_bytes: bytes) -> Dict[str, Any]:
        if not pdf_bytes:
            return {"kpis": []}
        page_index = self._find_performance_page_index(pdf_bytes)
        page_png = self._render_single_page_png(pdf_bytes, page_index)
        return self._call_responses_single_image(page_png)
