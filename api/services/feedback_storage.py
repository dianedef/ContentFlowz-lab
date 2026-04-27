"""Short-lived signed feedback upload/playback URLs backed by Bunny Storage."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


class FeedbackStorageError(RuntimeError):
    pass


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(f"{raw}{padding}")


def _utc_ts() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


class FeedbackStorageService:
    def __init__(self) -> None:
        self._base_url = "https://storage.bunnycdn.com"

    def _signing_secret(self) -> str:
        secret = os.getenv("FEEDBACK_SIGNING_SECRET") or os.getenv(
            "CLERK_WEBHOOK_SECRET"
        )
        if not secret:
            raise FeedbackStorageError(
                "FEEDBACK_SIGNING_SECRET not configured."
            )
        return secret

    def _storage_key(self) -> str:
        key = os.getenv("BUNNY_STORAGE_API_KEY")
        if not key:
            raise FeedbackStorageError("BUNNY_STORAGE_API_KEY not configured.")
        return key

    def _storage_zone(self) -> str:
        zone = os.getenv("BUNNY_STORAGE_ZONE")
        if not zone:
            raise FeedbackStorageError("BUNNY_STORAGE_ZONE not configured.")
        return zone

    def _storage_region(self) -> str:
        return (os.getenv("BUNNY_STORAGE_REGION") or "de").strip().lower()

    def _upload_ttl_seconds(self) -> int:
        try:
            return int(os.getenv("FEEDBACK_UPLOAD_TTL_SECONDS", "900"))
        except ValueError:
            return 900

    def _max_upload_bytes(self) -> int:
        try:
            value = int(os.getenv("FEEDBACK_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
        except ValueError:
            value = 5 * 1024 * 1024
        return max(1024, value)

    def _playback_ttl_seconds(self) -> int:
        try:
            return int(os.getenv("FEEDBACK_PLAYBACK_TTL_SECONDS", "300"))
        except ValueError:
            return 300

    def _mime_allowlist(self) -> set[str]:
        return {"audio/wav", "audio/x-wav", "audio/wave"}

    def _storage_url(self, storage_id: str) -> str:
        region = self._storage_region()
        if region and region != "de":
            regional_prefix = {"ny", "la", "sg", "syd"}
            if region in regional_prefix:
                return (
                    f"https://{region}.storage.bunnycdn.com/"
                    f"{self._storage_zone()}/{storage_id}"
                )
        return f"{self._base_url}/{self._storage_zone()}/{storage_id}"

    def generate_storage_id(self, file_name: str, mime_type: str) -> str:
        mime = mime_type.strip().lower()
        if mime not in self._mime_allowlist():
            raise FeedbackStorageError("Unsupported audio MIME type.")

        sanitized_name = file_name.rsplit("/", 1)[-1].strip() or "feedback.wav"
        extension = ".wav"
        if "." in sanitized_name:
            extension = f".{sanitized_name.rsplit('.', 1)[-1].lower()}"
        if extension not in {".wav"}:
            extension = ".wav"

        now = datetime.now(tz=timezone.utc)
        random_part = secrets.token_hex(8)
        return (
            f"feedback/audio/{now.year:04d}/{now.month:02d}/{now.day:02d}/"
            f"{random_part}{extension}"
        )

    def issue_token(
        self,
        *,
        action: str,
        storage_id: str,
        ttl_seconds: int,
        mime_type: str | None = None,
        max_bytes: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "action": action,
            "storageId": storage_id,
            "exp": _utc_ts() + ttl_seconds,
        }
        if mime_type:
            payload["mimeType"] = mime_type
        if max_bytes:
            payload["maxBytes"] = int(max_bytes)
        encoded_payload = _b64url_encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signature = hmac.new(
            self._signing_secret().encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return f"{encoded_payload}.{_b64url_encode(signature)}"

    def verify_token(self, token: str, *, expected_action: str) -> dict[str, Any]:
        try:
            payload_part, signature_part = token.split(".", 1)
        except ValueError as exc:
            raise FeedbackStorageError("Malformed feedback token.") from exc

        expected_sig = hmac.new(
            self._signing_secret().encode("utf-8"),
            payload_part.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        provided_sig = _b64url_decode(signature_part)
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise FeedbackStorageError("Invalid feedback token signature.")

        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
        if payload.get("action") != expected_action:
            raise FeedbackStorageError("Feedback token action mismatch.")
        if int(payload.get("exp", 0)) < _utc_ts():
            raise FeedbackStorageError("Feedback token expired.")
        return payload

    def create_upload_token(
        self,
        storage_id: str,
        mime_type: str,
        *,
        max_bytes: int | None = None,
    ) -> str:
        effective_max_bytes = max_bytes if max_bytes is not None else self._max_upload_bytes()
        return self.issue_token(
            action="upload",
            storage_id=storage_id,
            ttl_seconds=self._upload_ttl_seconds(),
            mime_type=mime_type,
            max_bytes=effective_max_bytes,
        )

    def create_playback_token(self, storage_id: str) -> str:
        return self.issue_token(
            action="playback",
            storage_id=storage_id,
            ttl_seconds=self._playback_ttl_seconds(),
        )

    async def upload_bytes(
        self,
        *,
        storage_id: str,
        body: bytes,
        mime_type: str,
    ) -> None:
        if not body:
            raise FeedbackStorageError("Feedback audio payload is empty.")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.put(
                self._storage_url(storage_id),
                content=body,
                headers={
                    "AccessKey": self._storage_key(),
                    "Content-Type": mime_type,
                },
            )
        if response.status_code >= 400:
            raise FeedbackStorageError(
                f"Feedback audio upload failed ({response.status_code})."
            )

    async def object_exists(self, storage_id: str) -> bool:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.head(
                self._storage_url(storage_id),
                headers={"AccessKey": self._storage_key()},
            )
        return response.status_code == 200

    async def download_bytes(self, storage_id: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                self._storage_url(storage_id),
                headers={"AccessKey": self._storage_key()},
            )
        if response.status_code >= 400:
            raise FeedbackStorageError(
                f"Feedback audio download failed ({response.status_code})."
            )
        content_type = response.headers.get("content-type", "audio/wav")
        return response.content, content_type


feedback_storage_service = FeedbackStorageService()
