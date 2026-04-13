"""Site -> app auth handoff and Clerk webhook endpoints."""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from api.dependencies.auth import CurrentUser, require_current_user
from api.models.auth_web import (
    WebExchangeRequest,
    WebExchangeResponse,
    WebHandoffResponse,
)
from api.services.user_data_store import user_data_store
from api.services.web_auth_handoff_store import (
    WebAuthHandoffError,
    web_auth_handoff_store,
)

try:
    from svix.webhooks import Webhook, WebhookVerificationError
except Exception:  # pragma: no cover - dependency resolution is runtime-specific
    Webhook = None
    WebhookVerificationError = Exception


router = APIRouter(prefix="/api/auth/web", tags=["Web Auth"])
webhook_router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

logger = logging.getLogger("api.auth_web")


@router.post(
    "/handoff",
    response_model=WebHandoffResponse,
    summary="Create a short-lived auth handoff for Flutter web",
)
async def create_web_handoff(
    current_user: CurrentUser = Depends(require_current_user),
) -> WebHandoffResponse:
    handoff = await web_auth_handoff_store.create(
        bearer_token=current_user.bearer_token,
        user_id=current_user.user_id,
        email=current_user.email,
    )
    return WebHandoffResponse(
        handoff_token=handoff.token,
        expires_at=handoff.expires_at,
    )


@router.post(
    "/exchange",
    response_model=WebExchangeResponse,
    summary="Consume a handoff token and return an app session",
)
async def exchange_web_handoff(
    payload: WebExchangeRequest,
) -> WebExchangeResponse:
    try:
        handoff = await web_auth_handoff_store.consume(payload.handoff_token)
    except WebAuthHandoffError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return WebExchangeResponse(
        bearer_token=handoff.bearer_token,
        user_id=handoff.user_id,
        email=handoff.email,
    )


@webhook_router.post(
    "/clerk",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive signed Clerk webhooks",
)
async def receive_clerk_webhook(
    request: Request,
    svix_id: str | None = Header(default=None, alias="svix-id"),
    svix_timestamp: str | None = Header(default=None, alias="svix-timestamp"),
    svix_signature: str | None = Header(default=None, alias="svix-signature"),
) -> dict[str, bool]:
    secret = (os.getenv("CLERK_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CLERK_WEBHOOK_SECRET is not configured.",
        )
    if Webhook is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="svix dependency is not installed.",
        )

    payload = await request.body()
    headers = {
        "svix-id": svix_id or "",
        "svix-timestamp": svix_timestamp or "",
        "svix-signature": svix_signature or "",
    }

    try:
        event = Webhook(secret).verify(payload, headers)
    except WebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Clerk webhook signature.",
        ) from exc

    event_type = str(event.get("type") or "")
    data = event.get("data") or {}
    user_id = str(data.get("id") or "").strip()
    email = None
    email_addresses = data.get("email_addresses")
    if isinstance(email_addresses, list) and email_addresses:
        first = email_addresses[0]
        if isinstance(first, dict):
            email = first.get("email_address")

    logger.info(
        "Received Clerk webhook %s for user %s",
        event_type,
        user_id or "<missing>",
    )

    if user_id and user_data_store.db_client and event_type in {
        "user.created",
        "user.updated",
    }:
        settings = await user_data_store.get_user_settings(user_id)
        logger.info(
            "Provisioned settings row %s for Clerk user %s (%s)",
            settings["id"],
            user_id,
            email or "no-email",
        )
    elif user_id and event_type == "user.deleted":
        logger.info(
            "Received Clerk deletion for user %s; no destructive product cleanup is performed automatically.",
            user_id,
        )
    else:
        logger.debug("Clerk webhook payload: %s", json.loads(payload.decode("utf-8")))

    return {"ok": True}
