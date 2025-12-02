"""Core shared modules for the EWA Analyzer backend."""

from core.azure_clients import (
    blob_service_client,
    AZURE_STORAGE_CONNECTION_STRING,
    AZURE_STORAGE_CONTAINER_NAME,
)

__all__ = [
    "blob_service_client",
    "AZURE_STORAGE_CONNECTION_STRING",
    "AZURE_STORAGE_CONTAINER_NAME",
]
