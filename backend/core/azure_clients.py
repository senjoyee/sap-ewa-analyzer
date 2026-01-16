"""
Centralized Azure client initialization.

This module provides a single source of truth for Azure Blob Storage client
and configuration. All other modules should import from here instead of
initializing their own clients.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables once
load_dotenv()

# Azure Blob Storage configuration
AZURE_STORAGE_CONNECTION_STRING: Optional[str] = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME: Optional[str] = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

# Validate required environment variables
if not AZURE_STORAGE_CONNECTION_STRING:
    raise ValueError(
        "AZURE_STORAGE_CONNECTION_STRING not found in environment variables. "
        "Please set it in your .env file."
    )
if not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError(
        "AZURE_STORAGE_CONTAINER_NAME not found in environment variables. "
        "Please set it in your .env file."
    )

# Initialize the shared BlobServiceClient
blob_service_client: Optional[BlobServiceClient] = None
try:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
except Exception as e:
    logger.warning("Unable to initialize BlobServiceClient: %s", e)
    blob_service_client = None


def get_blob_client(blob_name: str):
    """Get a blob client for the specified blob name."""
    if not blob_service_client:
        raise RuntimeError("Azure Blob Service client not initialized")
    return blob_service_client.get_blob_client(
        container=AZURE_STORAGE_CONTAINER_NAME,
        blob=blob_name
    )


def get_container_client():
    """Get the container client for the configured container."""
    if not blob_service_client:
        raise RuntimeError("Azure Blob Service client not initialized")
    return blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
