"""
Export routes for EWA artifacts.

PDF generation has been removed. Only Excel export is supported.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Response

from core.azure_clients import blob_service_client
from services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["export"])
storage_service = StorageService()


@router.get("/export-excel")
async def export_json_to_excel(blob_name: str):
    """Export an existing workbook artifact."""
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
            logger.info("[Excel Export] Workbook not found: %s", workbook_blob_name)
            raise HTTPException(status_code=404, detail=f"Workbook file {workbook_blob_name} not found") from None
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error exporting workbook %s", blob_name)
        raise HTTPException(status_code=500, detail=f"Error exporting workbook: {str(exc)}")
