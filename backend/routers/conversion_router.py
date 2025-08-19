"""Document conversion status routes extracted from ewa_main.py.

Endpoints:
- POST /api/analyze            -> convert_document_to_markdown
- GET  /api/analysis-status/{blob_name} -> get_conversion_status

No functional changes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from models import BlobNameRequest

# Conversion pipeline has been deprecated from the runtime API surface.
# Keep modules in codebase, but do not import or expose them via HTTP.

router = APIRouter(prefix="/api", tags=["conversion"])




@router.post("/analyze")
async def analyze_document(request: BlobNameRequest):
    """Deprecated: PDF-to-Markdown conversion endpoint is disabled."""
    raise HTTPException(status_code=410, detail="This endpoint is disabled. Use PDF-first EWA analysis.")


@router.get("/analysis-status/{blob_name}")
async def get_document_analysis_status(blob_name: str):
    """Deprecated: conversion status endpoint is disabled."""
    raise HTTPException(status_code=410, detail="This endpoint is disabled. Conversion pipeline is no longer exposed.")
