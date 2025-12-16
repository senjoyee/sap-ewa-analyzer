"""
Centralized Azure client initialization.

This module provides a single source of truth for Azure Blob Storage client
and configuration. All other modules should import from here instead of
initializing their own clients.
"""

from __future__ import annotations

import os
from typing import Optional

from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from azure.data.tables import UpdateMode
from dotenv import load_dotenv

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

# Table storage configuration (used for batch tracking)
AZURE_BATCH_TABLE_NAME: str = os.getenv("AZURE_BATCH_TABLE_NAME", "ewa_batches")

# Initialize the shared clients
blob_service_client: Optional[BlobServiceClient] = None
table_service_client: Optional[TableServiceClient] = None
try:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
except Exception as e:
    print(f"[WARN] Unable to initialize BlobServiceClient: {e}")
    blob_service_client = None

try:
    table_service_client = TableServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    # Ensure table exists
    try:
        table_service_client.create_table_if_not_exists(AZURE_BATCH_TABLE_NAME)
    except Exception:
        # Table may already exist or creation may race; ignore
        pass
except Exception as e:
    print(f"[WARN] Unable to initialize TableServiceClient: {e}")
    table_service_client = None


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


def get_table_client(table_name: Optional[str] = None):
    """Get a table client for the configured batch tracking table."""
    if not table_service_client:
        raise RuntimeError("Azure Table Service client not initialized")
    name = table_name or AZURE_BATCH_TABLE_NAME
    return table_service_client.get_table_client(name)
