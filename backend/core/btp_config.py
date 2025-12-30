"""
SAP BTP Cloud Foundry Configuration Helper

This module provides utilities for reading configuration from SAP BTP
Cloud Foundry environment, including VCAP_SERVICES for bound services
and VCAP_APPLICATION for application metadata.

When running on Cloud Foundry:
- Services are bound via VCAP_SERVICES (JSON in environment variable)
- Application metadata is in VCAP_APPLICATION
- Port is assigned via PORT environment variable

When running locally:
- Falls back to .env file configuration
- Use cf local-env for testing with CF bindings locally

Usage:
    from core.btp_config import get_config, is_running_on_cf
    
    config = get_config()
    azure_conn_str = config.azure_storage_connection_string
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from dotenv import load_dotenv


def is_running_on_cf() -> bool:
    """Check if running on Cloud Foundry (SAP BTP)."""
    return bool(os.getenv("VCAP_SERVICES") or os.getenv("VCAP_APPLICATION"))


def get_vcap_services() -> dict[str, Any]:
    """Parse VCAP_SERVICES environment variable."""
    vcap_str = os.getenv("VCAP_SERVICES", "{}")
    try:
        return json.loads(vcap_str)
    except json.JSONDecodeError:
        return {}


def get_vcap_application() -> dict[str, Any]:
    """Parse VCAP_APPLICATION environment variable."""
    vcap_str = os.getenv("VCAP_APPLICATION", "{}")
    try:
        return json.loads(vcap_str)
    except json.JSONDecodeError:
        return {}


def get_user_provided_service(service_name: str) -> dict[str, Any]:
    """
    Get credentials from a user-provided service.
    
    User-provided services are created with:
    cf cups <service-name> -p '{"key": "value"}'
    
    Args:
        service_name: Name of the user-provided service
        
    Returns:
        Dictionary of credentials, or empty dict if not found
    """
    vcap = get_vcap_services()
    user_provided = vcap.get("user-provided", [])
    
    for service in user_provided:
        if service.get("name") == service_name:
            return service.get("credentials", {})
    
    return {}


def get_xsuaa_credentials() -> dict[str, Any]:
    """
    Get XSUAA service credentials for JWT validation.
    
    Returns credentials including:
    - clientid: OAuth2 client ID
    - clientsecret: OAuth2 client secret
    - url: XSUAA URL for token validation
    - verificationkey: Public key for JWT verification
    """
    vcap = get_vcap_services()
    xsuaa_services = vcap.get("xsuaa", [])
    
    if xsuaa_services:
        return xsuaa_services[0].get("credentials", {})
    
    return {}


def get_destination_service_credentials() -> dict[str, Any]:
    """
    Get Destination Service credentials.
    
    Used to fetch destination configurations at runtime.
    """
    vcap = get_vcap_services()
    dest_services = vcap.get("destination", [])
    
    if dest_services:
        return dest_services[0].get("credentials", {})
    
    return {}


@dataclass
class BTPConfig:
    """
    Configuration container for SAP BTP deployment.
    
    Automatically reads from:
    1. VCAP_SERVICES (Cloud Foundry service bindings)
    2. User-provided services (Azure credentials)
    3. Environment variables (fallback for local dev)
    4. .env file (local development)
    """
    
    # Azure Blob Storage
    azure_storage_connection_string: Optional[str] = None
    azure_storage_container_name: Optional[str] = None
    
    # Azure OpenAI
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_summary_model: Optional[str] = None
    azure_openai_fast_model: Optional[str] = None
    
    # Azure Anthropic (AI Foundry)
    azure_anthropic_endpoint: Optional[str] = None
    azure_anthropic_api_key: Optional[str] = None
    anthropic_summary_model: str = "claude-sonnet-4-5"
    
    # Provider selection
    provider: str = "openai"
    
    # XSUAA (populated from service binding)
    xsuaa_credentials: dict[str, Any] = field(default_factory=dict)
    
    # Application metadata
    app_name: str = "ewa-analyzer"
    space_name: str = "dev"
    org_name: str = ""
    
    # Runtime
    port: int = 8001
    is_cloud_foundry: bool = False
    
    def __post_init__(self):
        """Validate required configuration."""
        if not self.azure_storage_connection_string:
            raise ValueError(
                "AZURE_STORAGE_CONNECTION_STRING is required. "
                "Set it in .env (local) or user-provided service (BTP)."
            )
        if not self.azure_storage_container_name:
            raise ValueError(
                "AZURE_STORAGE_CONTAINER_NAME is required. "
                "Set it in .env (local) or user-provided service (BTP)."
            )


def get_config() -> BTPConfig:
    """
    Load configuration from appropriate source.
    
    On Cloud Foundry:
    - Reads Azure credentials from user-provided service
    - Reads XSUAA credentials from service binding
    - Port from PORT environment variable
    
    Locally:
    - Reads from .env file
    - Uses default port 8001
    
    Returns:
        BTPConfig instance with all configuration loaded
    """
    # Load .env for local development
    load_dotenv()
    
    is_cf = is_running_on_cf()
    
    if is_cf:
        # Running on Cloud Foundry - read from VCAP_SERVICES
        azure_creds = get_user_provided_service("ewa-analyzer-azure-credentials")
        xsuaa_creds = get_xsuaa_credentials()
        vcap_app = get_vcap_application()
        
        return BTPConfig(
            # Azure Blob Storage
            azure_storage_connection_string=azure_creds.get(
                "AZURE_STORAGE_CONNECTION_STRING",
                os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            ),
            azure_storage_container_name=azure_creds.get(
                "AZURE_STORAGE_CONTAINER_NAME",
                os.getenv("AZURE_STORAGE_CONTAINER_NAME")
            ),
            
            # Azure OpenAI
            azure_openai_api_key=azure_creds.get(
                "AZURE_OPENAI_API_KEY",
                os.getenv("AZURE_OPENAI_API_KEY")
            ),
            azure_openai_endpoint=azure_creds.get(
                "AZURE_OPENAI_ENDPOINT",
                os.getenv("AZURE_OPENAI_ENDPOINT")
            ),
            azure_openai_api_version=azure_creds.get(
                "AZURE_OPENAI_API_VERSION",
                os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
            ),
            azure_openai_summary_model=azure_creds.get(
                "AZURE_OPENAI_SUMMARY_MODEL",
                os.getenv("AZURE_OPENAI_SUMMARY_MODEL")
            ),
            azure_openai_fast_model=azure_creds.get(
                "AZURE_OPENAI_FAST_MODEL",
                os.getenv("AZURE_OPENAI_FAST_MODEL")
            ),
            
            # Azure Anthropic
            azure_anthropic_endpoint=azure_creds.get(
                "AZURE_ANTHROPIC_ENDPOINT",
                os.getenv("AZURE_ANTHROPIC_ENDPOINT")
            ),
            azure_anthropic_api_key=azure_creds.get(
                "AZURE_ANTHROPIC_API_KEY",
                os.getenv("AZURE_ANTHROPIC_API_KEY")
            ),
            anthropic_summary_model=azure_creds.get(
                "ANTHROPIC_SUMMARY_MODEL",
                os.getenv("ANTHROPIC_SUMMARY_MODEL", "claude-sonnet-4-5")
            ),
            
            # Provider
            provider=os.getenv("PROVIDER", "openai"),
            
            # XSUAA
            xsuaa_credentials=xsuaa_creds,
            
            # Application metadata
            app_name=vcap_app.get("application_name", "ewa-analyzer"),
            space_name=vcap_app.get("space_name", "dev"),
            org_name=vcap_app.get("organization_name", ""),
            
            # Runtime
            port=int(os.getenv("PORT", "8001")),
            is_cloud_foundry=True,
        )
    else:
        # Local development - read from .env
        return BTPConfig(
            # Azure Blob Storage
            azure_storage_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            azure_storage_container_name=os.getenv("AZURE_STORAGE_CONTAINER_NAME"),
            
            # Azure OpenAI
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            azure_openai_summary_model=os.getenv("AZURE_OPENAI_SUMMARY_MODEL"),
            azure_openai_fast_model=os.getenv("AZURE_OPENAI_FAST_MODEL"),
            
            # Azure Anthropic
            azure_anthropic_endpoint=os.getenv("AZURE_ANTHROPIC_ENDPOINT"),
            azure_anthropic_api_key=os.getenv("AZURE_ANTHROPIC_API_KEY"),
            anthropic_summary_model=os.getenv("ANTHROPIC_SUMMARY_MODEL", "claude-sonnet-4-5"),
            
            # Provider
            provider=os.getenv("PROVIDER", "openai"),
            
            # Runtime
            port=int(os.getenv("PORT", "8001")),
            is_cloud_foundry=False,
        )


# Singleton instance for easy import
_config: Optional[BTPConfig] = None


def init_config() -> BTPConfig:
    """Initialize and return the global configuration."""
    global _config
    if _config is None:
        _config = get_config()
    return _config
