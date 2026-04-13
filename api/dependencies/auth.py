"""Authentication dependencies for protected API routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from api.auth.clerk import (
    ClerkAuthenticationError,
    ClerkConfigurationError,
    validate_clerk_token,
)


class CurrentUser(BaseModel):
    """Normalized authenticated user context."""

    user_id: str
    email: str | None = None
    bearer_token: str


bearer_scheme = HTTPBearer(auto_error=False)


def require_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Require a valid Clerk bearer token and return the current user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        claims = validate_clerk_token(credentials.credentials)
    except ClerkConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ClerkAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return CurrentUser(
        user_id=claims.user_id,
        email=claims.email,
        bearer_token=credentials.credentials,
    )
