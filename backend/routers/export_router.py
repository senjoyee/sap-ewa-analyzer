"""Export Markdown to PDF route extracted from ewa_main.py."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Response, Query
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from weasyprint import HTML

load_dotenv()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError("Azure storage env vars not set")

try:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
except Exception as e:
    print(f"Error initializing BlobServiceClient in export_router: {e}")
    blob_service_client = None

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export-pdf")
async def export_markdown_to_pdf(
    blob_name: str,
    landscape: bool = Query(True, description="Render PDF in landscape orientation (default: true)"),
    page_size: str = Query("A4", description="Page size for PDF (e.g., A4, A3, Letter). Default: A4"),
):
    """Convert a Markdown blob stored in Azure Blob Storage to a PDF using WeasyPrint."""
    if not blob_service_client:
        raise HTTPException(status_code=500, detail="Azure Blob Service client not initialized")

    try:
        # Validate extension
        if not blob_name.lower().endswith(".md"):
            raise HTTPException(status_code=400, detail="blob_name must point to a .md file")

        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, blob=blob_name
        )
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail=f"File {blob_name} not found")

        markdown_bytes = blob_client.download_blob().readall()
        markdown_text = markdown_bytes.decode("utf-8", errors="replace")

        # Very basic markdown -> HTML conversion (could use markdown2 but avoid extra dep)
        from markdown2 import markdown
        # Enable GitHub-style tables and fenced code blocks for proper rendering
        body_html = markdown(markdown_text, extras=["tables", "fenced-code-blocks"])

        # Base CSS styles; table-layout fixed to prevent overflow
        styles = """
            body { font-family: Arial, Helvetica, sans-serif; }
            table { border-collapse: collapse; width: 100%; font-size: 9pt; table-layout: fixed; word-wrap: break-word; }
            th, td { border: 1px solid #ddd; padding: 6px; text-align: left; }
            th { background-color: #f2f2f2; }
        """
        # Build @page rule dynamically based on params
        orientation = " landscape" if landscape else ""
        styles = f"@page {{ size: {page_size}{orientation}; margin: 15mm; }}\n" + styles
        full_html = f"<html><head><meta charset='utf-8'><style>{styles}</style></head><body>{body_html}</body></html>"

        pdf_bytes = HTML(string=full_html, base_url=".").write_pdf()
        pdf_filename = os.path.splitext(blob_name)[0] + ".pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=\"{pdf_filename}\""},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting markdown to PDF: {str(e)}")
