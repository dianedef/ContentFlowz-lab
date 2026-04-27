"""Models for feedback submission and admin review endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class FeedbackEntryType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"


class FeedbackEntryStatus(str, Enum):
    NEW = "new"
    REVIEWED = "reviewed"


class FeedbackTextCreateRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    platform: str = Field(..., min_length=1, max_length=32)
    locale: str = Field(..., min_length=1, max_length=32)
    userEmail: str | None = Field(default=None, max_length=320)

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Message must not be empty")
        return trimmed


class FeedbackAudioUploadUrlRequest(BaseModel):
    mimeType: str = Field(..., min_length=1, max_length=128)
    fileName: str = Field(..., min_length=1, max_length=255)
    fileSizeBytes: int | None = Field(default=None, gt=0, le=20 * 1024 * 1024)


class FeedbackAudioUploadUrlResponse(BaseModel):
    uploadUrl: str
    storageId: str
    method: str = "PUT"
    headers: dict[str, str] = Field(default_factory=dict)


class FeedbackAudioCreateRequest(BaseModel):
    audioStorageId: str = Field(..., min_length=1, max_length=512)
    durationMs: int = Field(..., gt=0, le=15 * 60 * 1000)
    platform: str = Field(..., min_length=1, max_length=32)
    locale: str = Field(..., min_length=1, max_length=32)
    userEmail: str | None = Field(default=None, max_length=320)


class FeedbackEntryResponse(BaseModel):
    id: str
    type: FeedbackEntryType
    message: str | None = None
    audioStorageId: str | None = None
    audioUrl: str | None = None
    durationMs: int | None = None
    platform: str
    locale: str
    userId: str | None = None
    userEmail: str | None = None
    status: FeedbackEntryStatus
    createdAt: datetime


class FeedbackAdminListResponse(BaseModel):
    items: list[FeedbackEntryResponse] = Field(default_factory=list)


class FeedbackAdminCapabilityResponse(BaseModel):
    isAdmin: bool


class FeedbackReviewResponse(BaseModel):
    ok: bool = True
    id: str
    status: FeedbackEntryStatus = FeedbackEntryStatus.REVIEWED
    reviewedAt: datetime
