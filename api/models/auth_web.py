"""Models for web auth handoff and Clerk webhook flows."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WebHandoffResponse(BaseModel):
    """Opaque handoff returned after validating a Clerk web session."""

    handoff_token: str
    expires_at: datetime


class WebExchangeRequest(BaseModel):
    """Request payload used by the Flutter web app to consume a handoff."""

    handoff_token: str


class WebExchangeResponse(BaseModel):
    """Session payload returned to the Flutter web app after exchange."""

    bearer_token: str
    user_id: str
    email: str | None = None

