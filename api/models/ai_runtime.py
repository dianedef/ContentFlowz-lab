"""Typed models for AI runtime settings, providers, and error envelopes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

RuntimeMode = Literal["byok", "platform"]
RuntimeProvider = Literal["openrouter", "exa", "firecrawl"]
RuntimeErrorKind = Literal["ai_runtime", "business_conflict", "dependency"]


class AIRuntimeSelection(BaseModel):
    """Persisted runtime mode under robotSettings.aiRuntime."""

    mode: RuntimeMode = "byok"


class AIRuntimeModeAvailability(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: RuntimeMode
    enabled: bool
    reason_code: str | None = Field(default=None, serialization_alias="reasonCode")
    message: str | None = None


class AIRuntimeByokProviderStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    supported: bool = True
    configured: bool = False
    masked_secret: str | None = Field(default=None, serialization_alias="maskedSecret")
    validation_status: str = Field(default="unknown", serialization_alias="validationStatus")
    can_validate: bool = Field(default=False, serialization_alias="canValidate")


class AIRuntimePlatformProviderStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    supported: bool = True
    configured: bool = False
    available: bool = False
    reason_code: str | None = Field(default=None, serialization_alias="reasonCode")


class AIRuntimeProviderStatus(BaseModel):
    provider: RuntimeProvider
    kind: str
    used_by: list[str] = Field(default_factory=list, serialization_alias="usedBy")
    byok: AIRuntimeByokProviderStatus
    platform: AIRuntimePlatformProviderStatus


class AIRuntimeSettingsResponse(BaseModel):
    mode: RuntimeMode
    available_modes: list[AIRuntimeModeAvailability] = Field(
        default_factory=list,
        serialization_alias="availableModes",
    )
    providers: list[AIRuntimeProviderStatus] = Field(default_factory=list)


class AIRuntimeModeUpdateRequest(BaseModel):
    mode: RuntimeMode


class ProviderCredentialStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: RuntimeProvider
    configured: bool = False
    masked_secret: str | None = Field(default=None, serialization_alias="maskedSecret")
    validation_status: str = Field(default="unknown", serialization_alias="validationStatus")
    last_validated_at: datetime | None = Field(
        default=None,
        serialization_alias="lastValidatedAt",
    )
    updated_at: datetime | None = Field(default=None, serialization_alias="updatedAt")


class ProviderCredentialUpsertRequest(BaseModel):
    secret: str = Field(
        ...,
        min_length=8,
        validation_alias=AliasChoices("secret", "apiKey", "api_key"),
        serialization_alias="secret",
    )


class ProviderCredentialDeleteResponse(BaseModel):
    deleted: bool = True
    provider: RuntimeProvider


class AIRuntimeErrorEnvelope(BaseModel):
    code: str
    message: str
    kind: RuntimeErrorKind
    route: str
    retryable: bool
    mode: RuntimeMode | None = None
    provider: RuntimeProvider | None = None
    settings_path: str | None = Field(default=None, serialization_alias="settingsPath")
    details: dict[str, Any] | None = None

