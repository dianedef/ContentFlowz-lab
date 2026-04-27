"""Feedback submission and admin review endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from api.dependencies.auth import (
    CurrentUser,
    get_optional_current_user,
    require_current_user,
)
from api.models.feedback import (
    FeedbackAdminCapabilityResponse,
    FeedbackAdminListResponse,
    FeedbackAudioCreateRequest,
    FeedbackAudioUploadUrlRequest,
    FeedbackAudioUploadUrlResponse,
    FeedbackEntryResponse,
    FeedbackEntryStatus,
    FeedbackEntryType,
    FeedbackReviewResponse,
    FeedbackTextCreateRequest,
)
from api.services.feedback_storage import (
    FeedbackStorageError,
    feedback_storage_service,
)
from api.services.feedback_store import feedback_store

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


def _normalize_optional_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _normalize_platform(value: str) -> str:
    return value.strip().lower()


def _normalize_locale(value: str) -> str:
    return value.strip()


def _admin_allowlist() -> set[str]:
    raw = os.environ.get("FEEDBACK_ADMIN_EMAILS", "")
    normalized = raw.replace("\n", ",").replace(";", ",")
    return {email.strip().lower() for email in normalized.split(",") if email.strip()}


def _raise_store_error(exc: RuntimeError) -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    ) from exc


def _raise_storage_error(exc: FeedbackStorageError, *, client_error: bool = False) -> None:
    raise HTTPException(
        status_code=(
            status.HTTP_400_BAD_REQUEST
            if client_error
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        detail=str(exc),
    ) from exc


def require_feedback_admin(
    current_user: CurrentUser = Depends(require_current_user),
) -> CurrentUser:
    email = _normalize_optional_email(current_user.email)
    if not email or email not in _admin_allowlist():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Feedback admin access denied",
        )
    return current_user


def _absolute_url(request: Request, path: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}{path}"


def _serialize_entry(
    entry: dict,
    *,
    request: Request | None = None,
) -> FeedbackEntryResponse:
    audio_url = None
    audio_storage_id = entry.get("audioStorageId")
    if request is not None and audio_storage_id:
        token = feedback_storage_service.create_playback_token(audio_storage_id)
        audio_url = _absolute_url(request, f"/api/feedback/audio/play/{token}")
    return FeedbackEntryResponse(
        id=entry["id"],
        type=entry["type"],
        message=entry.get("message"),
        audioStorageId=audio_storage_id,
        audioUrl=audio_url,
        durationMs=entry.get("durationMs"),
        platform=entry["platform"],
        locale=entry["locale"],
        userId=entry.get("userId"),
        userEmail=entry.get("userEmail"),
        status=entry["status"],
        createdAt=entry["createdAt"],
    )


@router.post("/text", response_model=FeedbackEntryResponse, status_code=201)
async def create_text_feedback(
    payload: FeedbackTextCreateRequest,
    current_user: CurrentUser | None = Depends(get_optional_current_user),
) -> FeedbackEntryResponse:
    try:
        entry = await feedback_store.create_entry(
            entry_type=FeedbackEntryType.TEXT.value,
            message=payload.message,
            platform=_normalize_platform(payload.platform),
            locale=_normalize_locale(payload.locale),
            user_id=current_user.user_id if current_user else None,
            user_email=_normalize_optional_email(
                current_user.email if current_user else payload.userEmail
            ),
        )
    except RuntimeError as exc:
        _raise_store_error(exc)
    return _serialize_entry(entry)


@router.post(
    "/audio/upload-url",
    response_model=FeedbackAudioUploadUrlResponse,
)
async def get_audio_upload_url(
    payload: FeedbackAudioUploadUrlRequest,
    request: Request,
    current_user: CurrentUser | None = Depends(get_optional_current_user),
) -> FeedbackAudioUploadUrlResponse:
    del current_user
    try:
        storage_id = feedback_storage_service.generate_storage_id(
            payload.fileName,
            payload.mimeType,
        )
        token = feedback_storage_service.create_upload_token(
            storage_id,
            payload.mimeType.strip().lower(),
            max_bytes=payload.fileSizeBytes,
        )
    except FeedbackStorageError as exc:
        _raise_storage_error(
            exc,
            client_error="Unsupported audio MIME type." in str(exc),
        )

    return FeedbackAudioUploadUrlResponse(
        uploadUrl=_absolute_url(request, f"/api/feedback/audio/upload/{token}"),
        storageId=storage_id,
        method="PUT",
        headers={"Content-Type": payload.mimeType.strip().lower()},
    )


@router.put("/audio/upload/{token}", status_code=204)
async def upload_audio_feedback(
    token: str,
    request: Request,
) -> Response:
    try:
        token_payload = feedback_storage_service.verify_token(
            token,
            expected_action="upload",
        )
        max_bytes_value = token_payload.get("maxBytes")
        max_bytes = int(max_bytes_value) if max_bytes_value is not None else None

        content_length_header = request.headers.get("content-length")
        if max_bytes is not None and content_length_header:
            try:
                content_length = int(content_length_header)
            except ValueError as exc:
                raise FeedbackStorageError("Feedback upload content length is invalid.") from exc
            if content_length > max_bytes:
                raise FeedbackStorageError("Feedback upload exceeds maximum allowed size.")

        mime_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        expected_mime = str(token_payload.get("mimeType", "")).strip().lower()
        if expected_mime and mime_type and mime_type != expected_mime:
            raise FeedbackStorageError("Feedback upload content type mismatch.")
        body = await request.body()
        if max_bytes is not None and len(body) > max_bytes:
            raise FeedbackStorageError("Feedback upload exceeds maximum allowed size.")
        await feedback_storage_service.upload_bytes(
            storage_id=token_payload["storageId"],
            body=body,
            mime_type=expected_mime or mime_type or "audio/wav",
        )
    except FeedbackStorageError as exc:
        _raise_storage_error(
            exc,
            client_error=(
                "token" in str(exc).lower()
                or "payload is empty" in str(exc).lower()
                or "content type mismatch" in str(exc).lower()
                or "maximum allowed size" in str(exc).lower()
                or "content length is invalid" in str(exc).lower()
            ),
        )

    return Response(status_code=204)


@router.post("/audio", response_model=FeedbackEntryResponse, status_code=201)
async def create_audio_feedback(
    payload: FeedbackAudioCreateRequest,
    current_user: CurrentUser | None = Depends(get_optional_current_user),
) -> FeedbackEntryResponse:
    try:
        exists = await feedback_storage_service.object_exists(payload.audioStorageId)
    except FeedbackStorageError as exc:
        _raise_storage_error(exc)

    if not exists:
        raise HTTPException(status_code=404, detail="Feedback audio upload not found")

    try:
        entry = await feedback_store.create_entry(
            entry_type=FeedbackEntryType.AUDIO.value,
            audio_storage_id=payload.audioStorageId,
            duration_ms=payload.durationMs,
            platform=_normalize_platform(payload.platform),
            locale=_normalize_locale(payload.locale),
            user_id=current_user.user_id if current_user else None,
            user_email=_normalize_optional_email(
                current_user.email if current_user else payload.userEmail
            ),
        )
    except RuntimeError as exc:
        _raise_store_error(exc)
    return _serialize_entry(entry)


@router.get("/admin/capability", response_model=FeedbackAdminCapabilityResponse)
async def feedback_admin_capability(
    current_user: CurrentUser = Depends(require_current_user),
) -> FeedbackAdminCapabilityResponse:
    email = _normalize_optional_email(current_user.email)
    return FeedbackAdminCapabilityResponse(
        isAdmin=bool(email and email in _admin_allowlist())
    )


@router.get("/admin", response_model=FeedbackAdminListResponse)
async def list_feedback_admin(
    request: Request,
    status_filter: FeedbackEntryStatus | None = Query(default=None, alias="status"),
    type_filter: FeedbackEntryType | None = Query(default=None, alias="type"),
    current_user: CurrentUser = Depends(require_feedback_admin),
) -> FeedbackAdminListResponse:
    del current_user
    try:
        entries = await feedback_store.list_entries(
            status=status_filter.value if status_filter else None,
            entry_type=type_filter.value if type_filter else None,
        )
    except RuntimeError as exc:
        _raise_store_error(exc)
    return FeedbackAdminListResponse(
        items=[_serialize_entry(entry, request=request) for entry in entries]
    )


@router.post("/admin/{feedback_id}/review", response_model=FeedbackReviewResponse)
async def mark_feedback_reviewed(
    feedback_id: str,
    current_user: CurrentUser = Depends(require_feedback_admin),
) -> FeedbackReviewResponse:
    try:
        entry = await feedback_store.mark_reviewed(
            entry_id=feedback_id,
            reviewer_user_id=current_user.user_id,
            reviewer_email=_normalize_optional_email(current_user.email),
        )
    except RuntimeError as exc:
        _raise_store_error(exc)
    if not entry:
        raise HTTPException(status_code=404, detail="Feedback entry not found")
    return FeedbackReviewResponse(
        id=entry["id"],
        status=entry["status"],
        reviewedAt=entry["reviewedAt"],
    )


@router.get("/audio/play/{token}")
async def stream_feedback_audio(
    token: str,
) -> Response:
    try:
        token_payload = feedback_storage_service.verify_token(
            token,
            expected_action="playback",
        )
        body, content_type = await feedback_storage_service.download_bytes(
            token_payload["storageId"]
        )
    except FeedbackStorageError as exc:
        _raise_storage_error(
            exc,
            client_error="token" in str(exc).lower(),
        )

    return Response(
        content=body,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=60"},
    )
