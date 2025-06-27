"""Document conversion status routes extracted from ewa_main.py.

Endpoints:
- POST /api/analyze            -> convert_document_to_markdown
- GET  /api/analysis-status/{blob_name} -> get_conversion_status

No functional changes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from models import BlobNameRequest

from converters.document_converter import convert_document_to_markdown, get_conversion_status

router = APIRouter(prefix="/api", tags=["conversion"])




@router.post("/analyze")
async def analyze_document(request: BlobNameRequest):
    """Process a document using Azure Document Intelligence."""
    try:
        result = convert_document_to_markdown(request.blob_name)
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting document: {str(e)}")


@router.get("/analysis-status/{blob_name}")
async def get_document_analysis_status(blob_name: str):
    """Get the status of a document conversion job."""
    try:
        status = get_conversion_status(blob_name)
        if status.get("error"):
            raise HTTPException(status_code=404, detail=status.get("message"))
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting conversion status: {str(e)}")
