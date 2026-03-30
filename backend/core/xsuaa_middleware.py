"""
XSUAA Middleware for FastAPI.

This middleware handles JWT validation for requests coming from the SAP BTP App Router.
It verifies the token signature against the XSUAA service binding.
"""

import os
import logging
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import jwt
from jwt.algorithms import RSAAlgorithm
import requests
from core.btp_config import get_xsuaa_credentials, is_running_on_cf

logger = logging.getLogger(__name__)

# Paths that bypass authentication (health/discovery only)
_PUBLIC_PATHS = frozenset(["/", "/health", "/api/ping", "/docs", "/openapi.json", "/redoc"])


class XSUAAMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.xsuaa_creds = get_xsuaa_credentials()
        self.public_keys: dict = {}
        self._cache_keys()

    def _uaa_url(self) -> str | None:
        """Return the UAA base URL from XSUAA credentials."""
        if not self.xsuaa_creds:
            return None
        url = self.xsuaa_creds.get("url")
        return url.rstrip("/") if url else None

    def _allowed_issuers(self) -> tuple[str, ...]:
        """Return accepted issuer values used by XSUAA tokens."""
        uaa_url = self._uaa_url()
        if not uaa_url:
            return tuple()
        return (
            uaa_url,
            f"{uaa_url}/oauth/token",
        )

    def _cache_keys(self) -> None:
        """Fetch and cache XSUAA RSA public keys from the token_keys endpoint."""
        uaa_url = self._uaa_url()
        if not uaa_url:
            logger.warning("No UAA URL in XSUAA credentials; JWT signature verification will fail.")
            return
        try:
            resp = requests.get(f"{uaa_url}/token_keys", timeout=10)
            resp.raise_for_status()
            for key_info in resp.json().get("keys", []):
                kid = key_info.get("kid")
                if kid:
                    self.public_keys[kid] = RSAAlgorithm.from_jwk(key_info)
            logger.info("Cached %d XSUAA public key(s)", len(self.public_keys))
        except Exception as exc:
            logger.error("Failed to fetch XSUAA public keys: %s", exc)

    async def dispatch(self, request: Request, call_next):
        # Skip validation when not on Cloud Foundry (local development)
        if not is_running_on_cf():
            return await call_next(request)

        # Allow health and discovery paths without a token
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._unauthorized("Missing Authorization header")

        token = auth_header.split(" ", 1)[1]

        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            public_key = self.public_keys.get(kid)
            if public_key is None:
                # Key may have been rotated — attempt one refresh
                self._cache_keys()
                public_key = self.public_keys.get(kid)

            if public_key is None:
                logger.warning("JWT kid '%s' not found in cached XSUAA keys", kid)
                return self._unauthorized("Unrecognised token key")

            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"verify_exp": True},
                issuer=self._allowed_issuers(),
            )

            # Enforce required scope
            xsappname = (self.xsuaa_creds or {}).get("xsappname")
            required_scope = f"{xsappname}.viewer" if xsappname else None
            user_scopes = claims.get("scope", [])
            if required_scope and required_scope not in user_scopes:
                logger.warning(
                    "Token missing required scope '%s'; present: %s",
                    required_scope,
                    user_scopes,
                )
                return self._forbidden("Insufficient scope")

            request.state.user = {
                "id": claims.get("user_id"),
                "email": claims.get("email"),
                "scopes": user_scopes,
            }

        except jwt.ExpiredSignatureError:
            return self._unauthorized("Token has expired")
        except jwt.InvalidTokenError as exc:
            logger.warning("JWT validation failed: %s", exc)
            return self._unauthorized("Invalid token")

        return await call_next(request)

    @staticmethod
    def _unauthorized(detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @staticmethod
    def _forbidden(detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": detail},
        )
