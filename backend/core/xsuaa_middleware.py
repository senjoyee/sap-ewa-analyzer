"""
XSUAA JWT Validation Middleware for FastAPI

This module provides JWT token validation for SAP BTP XSUAA authentication.
When deployed to Cloud Foundry, incoming requests will have JWT tokens from
the App Router that need to be validated.

Usage:
    from core.xsuaa_middleware import XSUAAMiddleware, get_current_user
    
    app.add_middleware(XSUAAMiddleware)
    
    @app.get("/protected")
    async def protected_route(user: dict = Depends(get_current_user)):
        return {"user": user["email"]}
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import PyJWKClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.btp_config import get_xsuaa_credentials, is_running_on_cf


# Security scheme for OpenAPI docs
security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_xsuaa_config() -> dict[str, Any]:
    """
    Get XSUAA configuration from service binding.
    Cached for performance.
    """
    if not is_running_on_cf():
        return {}
    
    creds = get_xsuaa_credentials()
    return {
        "clientid": creds.get("clientid"),
        "clientsecret": creds.get("clientsecret"),
        "url": creds.get("url"),
        "uaadomain": creds.get("uaadomain"),
        "verificationkey": creds.get("verificationkey"),
        "xsappname": creds.get("xsappname"),
    }


def get_jwks_client() -> Optional[PyJWKClient]:
    """
    Create JWKS client for fetching public keys.
    Returns None if not running on Cloud Foundry.
    """
    config = get_xsuaa_config()
    if not config.get("url"):
        return None
    
    # XSUAA JWKS endpoint
    jwks_url = f"{config['url']}/token_keys"
    return PyJWKClient(jwks_url)


def validate_jwt_token(token: str) -> dict[str, Any]:
    """
    Validate a JWT token from XSUAA.
    
    Args:
        token: JWT token string (without "Bearer " prefix)
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid
    """
    config = get_xsuaa_config()
    
    if not config.get("url"):
        # Not running on CF, skip validation
        return {"sub": "local-dev", "email": "dev@local", "scope": []}
    
    try:
        # First, try using the verification key from service binding
        if config.get("verificationkey"):
            payload = jwt.decode(
                token,
                config["verificationkey"],
                algorithms=["RS256"],
                audience=config.get("clientid"),
                options={"verify_aud": bool(config.get("clientid"))},
            )
            return payload
        
        # Fallback: fetch key from JWKS endpoint
        jwks_client = get_jwks_client()
        if jwks_client:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=config.get("clientid"),
                options={"verify_aud": bool(config.get("clientid"))},
            )
            return payload
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to validate token - no verification key available",
        )
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )


def check_scope(token_payload: dict[str, Any], required_scope: str) -> bool:
    """
    Check if the token has the required scope.
    
    Args:
        token_payload: Decoded JWT payload
        required_scope: Scope to check (e.g., "read", "write", "admin")
        
    Returns:
        True if scope is present, False otherwise
    """
    scopes = token_payload.get("scope", [])
    xsappname = get_xsuaa_config().get("xsappname", "")
    
    # Check for fully qualified scope (xsappname.scope)
    full_scope = f"{xsappname}.{required_scope}"
    return full_scope in scopes or required_scope in scopes


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict[str, Any]:
    """
    Dependency to get the current authenticated user.
    
    Usage:
        @app.get("/me")
        async def get_me(user: dict = Depends(get_current_user)):
            return user
    """
    # Check if running on Cloud Foundry
    if not is_running_on_cf():
        # Local development - return mock user
        return {
            "sub": "local-dev",
            "email": "dev@localhost",
            "name": "Local Developer",
            "scope": ["read", "write", "admin"],
        }
    
    # Get token from Authorization header
    if not credentials:
        # Try getting from request state (set by middleware)
        user = getattr(request.state, "user", None)
        if user:
            return user
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validate token
    token = credentials.credentials
    payload = validate_jwt_token(token)
    
    return {
        "sub": payload.get("sub"),
        "email": payload.get("email", payload.get("user_name")),
        "name": payload.get("given_name", payload.get("user_name")),
        "scope": payload.get("scope", []),
        "client_id": payload.get("client_id"),
        "zone_id": payload.get("zid"),
    }


def require_scope(scope: str):
    """
    Dependency factory to require a specific scope.
    
    Usage:
        @app.post("/upload")
        async def upload(
            user: dict = Depends(get_current_user),
            _: None = Depends(require_scope("write"))
        ):
            ...
    """
    async def check(user: dict = Depends(get_current_user)):
        if not check_scope({"scope": user.get("scope", [])}, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scope '{scope}' not present",
            )
    return check


class XSUAAMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JWT tokens on all requests.
    
    Adds the validated user to request.state.user for downstream use.
    
    Skips validation for:
    - Health check endpoints
    - OpenAPI documentation
    - Local development (when not on Cloud Foundry)
    """
    
    # Paths that don't require authentication
    EXEMPT_PATHS = {
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # Skip if not running on Cloud Foundry
        if not is_running_on_cf():
            request.state.user = {
                "sub": "local-dev",
                "email": "dev@localhost",
                "name": "Local Developer",
                "scope": ["read", "write", "admin"],
            }
            return await call_next(request)
        
        # Get Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Validate token
        token = auth_header[7:]  # Remove "Bearer " prefix
        try:
            payload = validate_jwt_token(token)
            request.state.user = {
                "sub": payload.get("sub"),
                "email": payload.get("email", payload.get("user_name")),
                "name": payload.get("given_name", payload.get("user_name")),
                "scope": payload.get("scope", []),
            }
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers or {},
            )
        
        return await call_next(request)
