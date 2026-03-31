"""
Export routes for EWA artifacts.

PDF generation has been removed. Only Excel export is supported.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Response

from core.azure_clients import AZURE_STORAGE_CONTAINER_NAME, blob_service_client
from services.storage_service import StorageService
from utils.excel_utils import json_to_excel
from utils.parameter_extractor import extract_parameters_from_markdown

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["export"])
storage_service = StorageService()


def _sanitize_filename_component(value: str) -> str:
    """Sanitize a string for safe filename usage."""
    import re

    cleaned = re.sub(r"[^\w\-]+", "_", value or "").strip("_")
    return cleaned or "unknown"


@router.get("/export-excel")
async def export_json_to_excel(blob_name: str):
    """Export EWA analysis to Excel directly from JSON, with optional parameter recommendations."""
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized")

    try:
        incoming_base, incoming_ext = os.path.splitext(blob_name)
        if blob_name.lower().endswith("_workbook.xlsx"):
            workbook_blob_name = blob_name
        elif blob_name.lower().endswith("_workbook_payload.json"):
            workbook_blob_name = f"{incoming_base[:-17]}_workbook.xlsx"
        elif incoming_ext.lower() in {".md", ".pdf", ".json"}:
            workbook_blob_name = f"{incoming_base}_workbook.xlsx"
        else:
            workbook_blob_name = f"{blob_name}_workbook.xlsx"

        try:
            workbook_bytes = storage_service.get_bytes(workbook_blob_name)
            return Response(
                content=workbook_bytes,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f'attachment; filename="{os.path.basename(workbook_blob_name)}"',
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                },
            )
        except FileNotFoundError:
            logger.info(
                "[Excel Export] Agentic workbook not found (%s), falling back to JSON export",
                workbook_blob_name,
            )

        try:
            json_text = storage_service.get_text_content(blob_name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"JSON file {blob_name} not found") from None

        try:
            json_data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(exc)}") from None

        base_name = os.path.splitext(blob_name)[0]
        original_base = base_name[:-3] if base_name.endswith("_AI") else base_name

        # Fetch customer_name from original source metadata if available.
        customer_name = ""
        try:
            original_pdf_name = f"{original_base}.pdf"
            original_md_name = f"{original_base}.md"

            original_blob_client = blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME, blob=original_pdf_name
            )
            if original_blob_client.exists():
                blob_props = original_blob_client.get_blob_properties()
                if blob_props.metadata:
                    customer_name = blob_props.metadata.get("customer_name", "")
                    logger.info("[Excel Export] Customer name from source metadata: %s", customer_name)

            if not customer_name:
                original_md_client = blob_service_client.get_blob_client(
                    container=AZURE_STORAGE_CONTAINER_NAME, blob=original_md_name
                )
                if original_md_client.exists():
                    blob_props = original_md_client.get_blob_properties()
                    if blob_props.metadata:
                        customer_name = blob_props.metadata.get("customer_name", "")
                        logger.info("[Excel Export] Customer name from source metadata: %s", customer_name)
        except Exception as meta_exc:
            logger.warning("[Excel Export] Error fetching customer metadata: %s", meta_exc)

        parameters: List[Dict[str, Any]] = []
        params_blob_name = f"{original_base}_parameters.json"

        try:
            params_text = storage_service.get_text_content(params_blob_name)
            params_json = json.loads(params_text)
            parameters = params_json.get("parameters", [])
            logger.info("[Excel Export] Loaded %s parameters from %s", len(parameters), params_blob_name)
        except FileNotFoundError:
            logger.info(
                "[Excel Export] Parameters file not found (%s), attempting markdown extraction",
                params_blob_name,
            )
            try:
                md_candidates = [f"{original_base}.md", f"{original_base}_AI.md"]
                md_text = None
                for candidate in md_candidates:
                    try:
                        md_text = storage_service.get_text_content(candidate)
                        break
                    except FileNotFoundError:
                        continue
                if md_text is None:
                    raise FileNotFoundError("No markdown source found for parameter extraction")
                parameters = extract_parameters_from_markdown(md_text)
                logger.info("[Excel Export] Extracted %s parameters from markdown", len(parameters))
            except FileNotFoundError:
                logger.warning(
                    "[Excel Export] Markdown file not found (tried %s); continuing without parameters",
                    md_candidates,
                )
            except Exception as md_exc:
                logger.warning("[Excel Export] Parameter extraction from markdown failed: %s", md_exc)
        except Exception as params_exc:
            logger.warning("[Excel Export] Error loading parameters JSON: %s", params_exc)

        excel_bytes = json_to_excel(json_data, customer_name=customer_name, parameters=parameters)

        safe_customer = _sanitize_filename_component(customer_name) if customer_name else "Customer"
        excel_filename = f"{original_base}_{safe_customer}.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{excel_filename}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error exporting JSON to Excel: {str(exc)}")
