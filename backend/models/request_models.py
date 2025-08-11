"""Common Pydantic models shared across routers.

This centralises simple request/response payload models so we avoid
re-defining them in multiple router modules and keep the codebase DRY.
"""

from pydantic import BaseModel


class BlobNameRequest(BaseModel):
    """Simple request body that only requires a blob name."""

    blob_name: str


class ProcessAnalyzeRequest(BaseModel):
    """Request body for combined process+analyze."""

    blob_name: str
