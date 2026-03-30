"""
XSUAA Middleware for FastAPI.

This middleware handles JWT validation for requests coming from the SAP BTP App Router.
It verifies the token signature against the XSUAA service binding.
"""

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
        self.verification_key_pem: str | None = None
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
        """Fetch and cache XSUAA RSA public keys from token_keys and verificationkey."""
        self.public_keys = {}
        self.verification_key_pem = None

        # Fallback key directly from XSUAA credentials (works even if token_keys call fails).
        verification_key = (self.xsuaa_creds or {}).get("verificationkey")
        if verification_key:
            self.verification_key_pem = verification_key.replace("\\n", "\n")

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
            logger.info(
                "Cached %d XSUAA public key(s)%s",
                len(self.public_keys),
                " with verificationkey fallback" if self.verification_key_pem else "",
            )
        except Exception as exc:
            logger.error("Failed to fetch XSUAA public keys: %s", exc)
            if self.verification_key_pem:
                logger.info("Continuing with XSUAA verificationkey fallback")

    def _verification_candidates(self, kid: str | None) -> list:
        """Return candidate keys to try for token verification."""
        candidates: list = []
        if kid and kid in self.public_keys:
            candidates.append(self.public_keys[kid])

        # Try all cached JWKs in case kid mapping differs/rotated.
        for key_id, key in self.public_keys.items():
            if kid and key_id == kid:
                continue
            candidates.append(key)

        # Finally try credentials fallback key if available.
        if self.verification_key_pem:
            candidates.append(self.verification_key_pem)

        return candidates

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

            # Key may have been rotated — refresh once before verifying.
            if not self.public_keys and not self.verification_key_pem:
                self._cache_keys()

            claims = None
            last_error: Exception | None = None
            for candidate_key in self._verification_candidates(kid):
                try:
                    claims = jwt.decode(
                        token,
                        candidate_key,
                        algorithms=["RS256"],
                        options={"verify_exp": True},
                        issuer=self._allowed_issuers(),
                    )
                    break
                except jwt.InvalidTokenError as exc:
                    last_error = exc

            if claims is None:
                logger.warning("Unable to verify JWT with available XSUAA keys (kid=%s)", kid)
                if last_error is not None:
                    raise last_error
                return self._unauthorized("Unrecognised token key")

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
