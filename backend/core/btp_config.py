"""
BTP Configuration Helper.

Reads configuration from VCAP_SERVICES (Cloud Foundry) or falls back to
environment variables for local development.
"""

from __future__ import annotations

import json
import os
from typing import Optional


def is_running_on_cf() -> bool:
    """Check if running on Cloud Foundry (BTP)."""
    return bool(os.getenv("VCAP_SERVICES") or os.getenv("VCAP_APPLICATION"))


def get_vcap_services() -> dict:
    """Parse VCAP_SERVICES environment variable."""
    vcap_str = os.getenv("VCAP_SERVICES", "{}")
    try:
        return json.loads(vcap_str)
    except json.JSONDecodeError:
        return {}


def get_xsuaa_credentials() -> Optional[dict]:
    """Get XSUAA credentials from VCAP_SERVICES."""
    vcap = get_vcap_services()
    xsuaa_services = vcap.get("xsuaa", [])
    if xsuaa_services:
        return xsuaa_services[0].get("credentials", {})
    return None


def get_azure_config() -> dict:
    """
    Get Azure configuration.
    
    On BTP: Reads from environment variables set in mta.yaml
    Locally: Reads from .env file (via dotenv)
    """
    return {
        "connection_string": os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        "container_name": os.getenv("AZURE_STORAGE_CONTAINER_NAME"),
        "openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "openai_api_key": os.getenv("AZURE_OPENAI_API_KEY"),
        "openai_model": os.getenv("AZURE_OPENAI_SUMMARY_MODEL"),
    }


def validate_azure_config() -> tuple[bool, list[str]]:
    """
    Validate that required Azure configuration is present.
    
    Returns:
        Tuple of (is_valid, list_of_missing_keys)
    """
    config = get_azure_config()
    required = ["connection_string", "container_name"]
    missing = [k for k in required if not config.get(k)]
    return len(missing) == 0, missing
