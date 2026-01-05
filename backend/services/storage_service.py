"""Storage service to encapsulate blob access logic."""

from __future__ import annotations

from azure.core.exceptions import ResourceNotFoundError

from core.azure_clients import AZURE_STORAGE_CONTAINER_NAME, blob_service_client


class StorageService:
    """Provide high-level helpers for accessing stored files."""

    def get_text_content(self, filename: str) -> str:
        """Download a blob as UTF-8 text from the main container."""
        if not blob_service_client:
            raise RuntimeError("Azure Blob Service client not initialized")

        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME,
            blob=filename,
        )

        try:
            data = blob_client.download_blob().readall()
        except ResourceNotFoundError:
            raise FileNotFoundError(f"File {filename} not found in storage") from None

        return data.decode("utf-8")

    def get_bytes(self, filename: str) -> bytes:
        """Download a blob as raw bytes from the main container."""
        if not blob_service_client:
            raise RuntimeError("Azure Blob Service client not initialized")

        blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME,
            blob=filename,
        )

        try:
            return blob_client.download_blob().readall()
        except ResourceNotFoundError:
            raise FileNotFoundError(f"File {filename} not found in storage") from None
