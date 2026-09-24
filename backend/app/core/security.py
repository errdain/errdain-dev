from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from backend.app.core.config import get_settings
from backend.app.core.rate_limit import enforce_rate_limit


@dataclass(frozen=True)
class AuthPrincipal:
    subject: str
    email: str
    tenant_id: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _unauthorized(message: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": message, "code": "UNAUTHORIZED"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _claims_principal(claims: dict[str, Any]) -> AuthPrincipal:
    metadata = claims.get("app_metadata") if isinstance(claims.get("app_metadata"), dict) else {}
    subject = str(claims.get("sub") or "")
    email = str(claims.get("email") or metadata.get("email") or "")
    tenant_id = str(metadata.get("tenant_id") or claims.get("tenant_id") or subject)
    role = str(metadata.get("app_role") or claims.get("app_role") or "user").lower()
    if not subject or not email or not tenant_id or role not in {"user", "admin"}:
        raise _unauthorized("Token is missing required identity claims")
    return AuthPrincipal(subject=subject, email=email.lower(), tenant_id=tenant_id, role=role)


def _decode_bearer(token: str) -> AuthPrincipal:
    settings = get_settings()
    decode_args: dict[str, Any] = {
        "algorithms": ["RS256", "ES256", "HS256"],
        "audience": settings.auth_jwt_audience,
        "options": {"require": ["exp", "sub"]},
    }
    if settings.auth_jwt_issuer:
        decode_args["issuer"] = settings.auth_jwt_issuer
    try:
        if settings.auth_jwks_url:
            key = PyJWKClient(settings.auth_jwks_url).get_signing_key_from_jwt(token).key
            decode_args["algorithms"] = ["RS256", "ES256"]
        elif settings.auth_jwt_secret:
            key = settings.auth_jwt_secret
            decode_args["algorithms"] = ["HS256"]
        else:
            raise _unauthorized("Server authentication is not configured")
        return _claims_principal(jwt.decode(token, key=key, **decode_args))
    except HTTPException:
        raise
    except (InvalidTokenError, ValueError) as exc:
        raise _unauthorized("Invalid or expired access token") from exc


def _local_principal() -> AuthPrincipal:
    settings = get_settings()
    return AuthPrincipal(
        subject="local-developer",
        email=settings.local_auth_email.lower(),
        tenant_id=settings.local_auth_tenant_id,
        role=settings.local_auth_role.lower(),
    )


def require_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthPrincipal:
    settings = get_settings()
    enforce_rate_limit(request, token=authorization or x_api_key)

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise _unauthorized("Authorization must use a Bearer token")
        return _decode_bearer(token)

    # Transitional API-key compatibility exists only outside production.
    if settings.app_env.lower() != "production" and settings.api_key:
        if x_api_key != settings.api_key:
            raise _unauthorized("Invalid or missing API key")
        return _local_principal()

    if (
        settings.app_env.lower() != "production"
        and settings.auth_mode.lower() == "local"
        and settings.allow_local_auth
    ):
        return _local_principal()
    raise _unauthorized()


def require_admin(principal: AuthPrincipal = Depends(require_user)) -> AuthPrincipal:
    if not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Administrator role required", "code": "FORBIDDEN"},
        )
    return principal


# Existing protected routes retain this dependency name while moving from a
# shared credential to authenticated user identity.
require_api_key = require_user
