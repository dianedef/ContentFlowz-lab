"""Models for authenticated user data endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from api.models.ai_runtime import AIRuntimeSelection


class SafeApiKeys(BaseModel):
    """Masked API keys returned to clients."""

    exa: str | None = None
    firecrawl: str | None = None
    serper: str | None = None
    openrouter: str | None = None
    bunnyStorage: str | None = None
    bunnyCdn: str | None = None
    bunnyCdnHostname: str | None = None
    consensus: str | None = None
    tavily: str | None = None
    groq: str | None = None


class DashboardLayout(BaseModel):
    defaultTab: str | None = None
    collapsedSections: list[str] = Field(default_factory=list)
    refreshInterval: int | None = None


class ContentFrequencyConfig(BaseModel):
    """How many content pieces the user wants generated per time period."""

    blog_posts_per_month: int = Field(default=0, ge=0, le=30)
    newsletters_per_week: int = Field(default=0, ge=0, le=7)
    shorts_per_day: int = Field(default=0, ge=0, le=10)
    social_posts_per_day: int = Field(default=0, ge=0, le=20)


class RobotSettings(BaseModel):
    autoRun: bool | None = None
    schedules: dict[str, str] = Field(default_factory=dict)
    notifications: dict[str, bool] = Field(default_factory=dict)
    contentFrequency: ContentFrequencyConfig | None = None
    ideaPoolEnabled: bool | None = None
    aiRuntime: AIRuntimeSelection | None = None


class UserSettingsResponse(BaseModel):
    id: str
    userId: str
    theme: str
    language: str | None = None
    emailNotifications: bool
    webhookUrl: str | None = None
    apiKeys: SafeApiKeys | None = None
    defaultProjectId: str | None = None
    dashboardLayout: DashboardLayout | None = None
    robotSettings: RobotSettings | None = None
    createdAt: datetime
    updatedAt: datetime


class UserSettingsUpdateRequest(BaseModel):
    theme: str | None = None
    language: str | None = None
    emailNotifications: bool | None = None
    webhookUrl: str | None = None
    defaultProjectId: str | None = None
    dashboardLayout: dict[str, Any] | None = None
    robotSettings: dict[str, Any] | None = None


class OpenRouterCredentialStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: Literal["openrouter"] = "openrouter"
    configured: bool = False
    masked_secret: str | None = Field(default=None, serialization_alias="maskedSecret")
    validation_status: str = Field(default="unknown", serialization_alias="validationStatus")
    last_validated_at: datetime | None = Field(
        default=None,
        serialization_alias="lastValidatedAt",
    )
    updated_at: datetime | None = Field(default=None, serialization_alias="updatedAt")


class OpenRouterCredentialUpsertRequest(BaseModel):
    api_key: str = Field(
        ...,
        min_length=8,
        validation_alias=AliasChoices("apiKey", "api_key"),
        serialization_alias="apiKey",
    )


class OpenRouterCredentialValidateResponse(BaseModel):
    provider: Literal["openrouter"] = "openrouter"
    valid: bool
    validation_status: str = Field(serialization_alias="validationStatus")
    message: str | None = None


class CreatorProfileResponse(BaseModel):
    id: str
    userId: str
    projectId: str | None = None
    displayName: str | None = None
    voice: dict[str, Any] | None = None
    positioning: dict[str, Any] | None = None
    values: list[str] = Field(default_factory=list)
    currentChapterId: str | None = None
    createdAt: datetime
    updatedAt: datetime


class CreatorProfileUpdateRequest(BaseModel):
    projectId: str | None = None
    displayName: str | None = None
    voice: dict[str, Any] | None = None
    positioning: dict[str, Any] | None = None
    values: list[str] | None = None
    currentChapterId: str | None = None


class PersonaResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    userId: str
    project_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("projectId", "project_id"),
        serialization_alias="projectId",
    )
    name: str
    avatar: str | None = None
    demographics: dict[str, Any] | None = None
    pain_points: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("painPoints", "pain_points"),
        serialization_alias="painPoints",
    )
    goals: list[str] = Field(default_factory=list)
    language: dict[str, Any] | None = None
    content_preferences: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("contentPreferences", "content_preferences"),
        serialization_alias="contentPreferences",
    )
    confidence: int = 50
    created_at: datetime = Field(
        validation_alias=AliasChoices("createdAt", "created_at"),
        serialization_alias="createdAt",
    )
    updated_at: datetime = Field(
        validation_alias=AliasChoices("updatedAt", "updated_at"),
        serialization_alias="updatedAt",
    )

    def to_canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=False)


class PersonaCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("projectId", "project_id"),
        serialization_alias="projectId",
    )
    name: str
    avatar: str | None = None
    demographics: dict[str, Any] | None = None
    pain_points: list[str] | None = Field(
        default=None,
        validation_alias=AliasChoices("painPoints", "pain_points"),
        serialization_alias="painPoints",
    )
    goals: list[str] | None = None
    language: dict[str, Any] | None = None
    content_preferences: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("contentPreferences", "content_preferences"),
        serialization_alias="contentPreferences",
    )
    confidence: int | None = None

    def to_canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=False, exclude_unset=True)


class PersonaUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    avatar: str | None = None
    demographics: dict[str, Any] | None = None
    pain_points: list[str] | None = Field(
        default=None,
        validation_alias=AliasChoices("painPoints", "pain_points"),
        serialization_alias="painPoints",
    )
    goals: list[str] | None = None
    language: dict[str, Any] | None = None
    content_preferences: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("contentPreferences", "content_preferences"),
        serialization_alias="contentPreferences",
    )
    confidence: int | None = None

    def to_canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=False, exclude_unset=True)
