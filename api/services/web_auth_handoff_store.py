"""Ephemeral store for site -> app web auth handoffs."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


class WebAuthHandoffError(RuntimeError):
    """Raised when a web auth handoff cannot be created or consumed."""


@dataclass(slots=True)
class WebAuthHandoff:
    token: str
    bearer_token: str
    user_id: str
    email: str | None
    expires_at: datetime
    used_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None


class WebAuthHandoffStore:
    """Short-lived in-memory handoff storage."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()
        self._items: dict[str, WebAuthHandoff] = {}

    async def create(
        self,
        *,
        bearer_token: str,
        user_id: str,
        email: str | None,
    ) -> WebAuthHandoff:
        async with self._lock:
            self._prune_locked()
            token = secrets.token_urlsafe(32)
            handoff = WebAuthHandoff(
                token=token,
                bearer_token=bearer_token,
                user_id=user_id,
                email=email,
                expires_at=datetime.now(UTC) + self._ttl,
            )
            self._items[token] = handoff
            return handoff

    async def consume(self, token: str) -> WebAuthHandoff:
        async with self._lock:
            self._prune_locked()
            handoff = self._items.get(token)
            if handoff is None:
                raise WebAuthHandoffError("Unknown handoff token.")
            if handoff.is_expired:
                self._items.pop(token, None)
                raise WebAuthHandoffError("Handoff token expired.")
            if handoff.is_used:
                raise WebAuthHandoffError("Handoff token already consumed.")
            handoff.used_at = datetime.now(UTC)
            self._items.pop(token, None)
            return handoff

    def _prune_locked(self) -> None:
        expired = [
            token
            for token, handoff in self._items.items()
            if handoff.is_expired or handoff.is_used
        ]
        for token in expired:
            self._items.pop(token, None)


web_auth_handoff_store = WebAuthHandoffStore()

