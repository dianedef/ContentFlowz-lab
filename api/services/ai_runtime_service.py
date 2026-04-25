"""Centralized AI runtime resolver for BYOK/platform modes."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from api.models.ai_runtime import (
    AIRuntimeByokProviderStatus,
    AIRuntimeErrorEnvelope,
    AIRuntimeModeAvailability,
    AIRuntimePlatformProviderStatus,
    AIRuntimeProviderStatus,
    AIRuntimeSettingsResponse,
    ProviderCredentialStatus,
    RuntimeMode,
    RuntimeProvider,
)
from api.services.ai_entitlement_service import ai_entitlement_service
from api.services.runtime_provider_context import runtime_provider_scope
from api.services.user_data_store import user_data_store
from api.services.user_key_store import user_key_store

SUPPORTED_PROVIDERS: tuple[RuntimeProvider, ...] = ("openrouter", "exa", "firecrawl")
OPERATOR_ENV_BY_PROVIDER: dict[RuntimeProvider, str] = {
    "openrouter": "OPENROUTER_API_KEY",
    "exa": "EXA_API_KEY",
    "firecrawl": "FIRECRAWL_API_KEY",
}
PROVIDER_KINDS: dict[RuntimeProvider, str] = {
    "openrouter": "llm",
    "exa": "search",
    "firecrawl": "crawler",
}
PROVIDER_USED_BY: dict[RuntimeProvider, list[str]] = {
    "openrouter": [
        "personas.draft",
        "psychology.synthesize_narrative",
        "psychology.refine_persona",
        "psychology.generate_angles",
        "psychology.dispatch_pipeline.article",
        "psychology.dispatch_pipeline.newsletter",
        "psychology.dispatch_pipeline.short",
        "psychology.dispatch_pipeline.social_post",
        "newsletter.generate",
        "research.competitor_analysis",
    ],
    "exa": [
        "psychology.dispatch_pipeline.article",
        "psychology.dispatch_pipeline.newsletter",
        "newsletter.generate",
        "research.competitor_analysis",
    ],
    "firecrawl": [
        "personas.draft",
        "psychology.dispatch_pipeline.article",
        "research.competitor_analysis",
    ],
}
OPENROUTER_VALIDATE_CAPABLE = {"openrouter"}


class AIRuntimeServiceError(RuntimeError):
    """Structured runtime resolver error for router translation."""

    def __init__(self, *, status_code: int, detail: dict[str, Any]) -> None:
        super().__init__(detail.get("message") or "AI runtime resolution failed.")
        self.status_code = status_code
        self.detail = detail


@dataclass
class RuntimeResolution:
    mode: RuntimeMode
    route: str
    required_provider_secrets: dict[RuntimeProvider, str] = field(default_factory=dict)
    optional_provider_secrets: dict[RuntimeProvider, str] = field(default_factory=dict)

    def has_optional_provider(self, provider: RuntimeProvider) -> bool:
        return provider in self.optional_provider_secrets

    def get_required_secret(self, provider: RuntimeProvider) -> str:
        return self.required_provider_secrets[provider]


class AIRuntimeService:
    """Resolve active runtime mode and provider credentials per request."""

    def _error(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        route: str,
        retryable: bool,
        mode: RuntimeMode | None = None,
        provider: RuntimeProvider | None = None,
        settings_path: str | None = None,
        kind: str = "ai_runtime",
        details: dict[str, Any] | None = None,
    ) -> AIRuntimeServiceError:
        envelope = AIRuntimeErrorEnvelope(
            code=code,
            message=message,
            kind=kind,  # type: ignore[arg-type]
            route=route,
            retryable=retryable,
            mode=mode,
            provider=provider,
            settings_path=settings_path,
            details=details,
        )
        return AIRuntimeServiceError(
            status_code=status_code,
            detail=envelope.model_dump(by_alias=True),
        )

    def _validate_provider(self, provider: str, route: str) -> RuntimeProvider:
        if provider not in SUPPORTED_PROVIDERS:
            raise self._error(
                status_code=400,
                code="ai_runtime_provider_not_supported",
                message=f"Provider '{provider}' is not supported.",
                route=route,
                retryable=False,
                provider=None,
                settings_path="/settings?section=ai-runtime",
            )
        return provider  # type: ignore[return-value]

    def _operator_secret(self, provider: RuntimeProvider) -> str | None:
        env_name = OPERATOR_ENV_BY_PROVIDER[provider]
        value = os.getenv(env_name)
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    async def get_effective_mode(self, user_id: str) -> RuntimeMode:
        try:
            mode = await user_data_store.get_effective_ai_runtime_mode(user_id)
        except RuntimeError:
            return "byok"
        if mode not in {"byok", "platform"}:
            return "byok"
        return mode  # type: ignore[return-value]

    async def resolve_mode(self, user_id: str, *, route: str) -> RuntimeMode:
        mode = await self.get_effective_mode(user_id)
        if mode == "platform" and not ai_entitlement_service.is_platform_entitled(user_id):
            raise self._error(
                status_code=403,
                code="ai_runtime_platform_not_entitled",
                message="Platform-paid mode is not enabled for this account.",
                route=route,
                retryable=False,
                mode=mode,
                settings_path="/settings?section=ai-runtime",
            )
        return mode

    async def _resolve_provider_secret(
        self,
        *,
        user_id: str,
        route: str,
        mode: RuntimeMode,
        provider: RuntimeProvider,
        required: bool,
    ) -> str | None:
        if mode == "platform":
            secret = self._operator_secret(provider)
            if secret:
                return secret
            if required:
                raise self._error(
                    status_code=503,
                    code="ai_runtime_operator_provider_missing",
                    message=f"{provider} is not configured on the operator runtime.",
                    route=route,
                    retryable=False,
                    mode=mode,
                    provider=provider,
                )
            return None

        try:
            status = await user_key_store.get_credential_status(user_id, provider=provider)
        except RuntimeError:
            status = None
        if not status:
            if required:
                raise self._error(
                    status_code=409,
                    code="ai_runtime_user_credential_missing",
                    message=f"{provider} is required in BYOK mode for this action.",
                    route=route,
                    retryable=False,
                    mode=mode,
                    provider=provider,
                    settings_path="/settings?section=ai-runtime",
                )
            return None

        if status.get("validation_status") == "invalid":
            if required:
                raise self._error(
                    status_code=409,
                    code="ai_runtime_user_credential_invalid",
                    message=f"{provider} credential is marked invalid.",
                    route=route,
                    retryable=False,
                    mode=mode,
                    provider=provider,
                    settings_path="/settings?section=ai-runtime",
                )
            return None

        try:
            secret = await user_key_store.get_secret(user_id, provider=provider)
        except RuntimeError:
            secret = None
        if secret:
            return secret
        if required:
            raise self._error(
                status_code=409,
                code="ai_runtime_user_credential_missing",
                message=f"{provider} is required in BYOK mode for this action.",
                route=route,
                retryable=False,
                mode=mode,
                provider=provider,
                settings_path="/settings?section=ai-runtime",
            )
        return None

    async def preflight_providers(
        self,
        *,
        user_id: str,
        route: str,
        required_providers: list[str],
        optional_providers: list[str] | None = None,
    ) -> RuntimeResolution:
        mode = await self.resolve_mode(user_id, route=route)
        required: list[RuntimeProvider] = [
            self._validate_provider(provider, route)
            for provider in required_providers
        ]
        optional: list[RuntimeProvider] = [
            self._validate_provider(provider, route)
            for provider in (optional_providers or [])
        ]

        resolution = RuntimeResolution(mode=mode, route=route)

        for provider in required:
            secret = await self._resolve_provider_secret(
                user_id=user_id,
                route=route,
                mode=mode,
                provider=provider,
                required=True,
            )
            if not secret:
                raise self._error(
                    status_code=503,
                    code="ai_runtime_operator_provider_unavailable",
                    message=f"{provider} is unavailable.",
                    route=route,
                    retryable=True,
                    mode=mode,
                    provider=provider,
                )
            resolution.required_provider_secrets[provider] = secret

        for provider in optional:
            try:
                secret = await self._resolve_provider_secret(
                    user_id=user_id,
                    route=route,
                    mode=mode,
                    provider=provider,
                    required=False,
                )
            except AIRuntimeServiceError as exc:
                if exc.detail.get("code") == "ai_runtime_provider_not_supported":
                    raise
                secret = None
            if secret:
                resolution.optional_provider_secrets[provider] = secret

        return resolution

    def bind_provider_env(self, resolution: RuntimeResolution):
        """Bind resolved providers to request-scoped context (no global env mutation)."""
        secrets = dict(resolution.optional_provider_secrets)
        secrets.update(resolution.required_provider_secrets)
        return runtime_provider_scope(
            route=resolution.route,
            mode=resolution.mode,
            provider_secrets=secrets,
        )

    async def get_runtime_settings(self, user_id: str) -> AIRuntimeSettingsResponse:
        selected_mode = await self.get_effective_mode(user_id)
        platform_enabled, reason_code, message = ai_entitlement_service.platform_availability_reason(user_id)

        available_modes = [
            AIRuntimeModeAvailability(mode="byok", enabled=True, reason_code=None, message=None),
            AIRuntimeModeAvailability(
                mode="platform",
                enabled=platform_enabled,
                reason_code=reason_code,
                message=message,
            ),
        ]

        providers: list[AIRuntimeProviderStatus] = []
        for provider in SUPPORTED_PROVIDERS:
            try:
                status = await user_key_store.get_credential_status(user_id, provider=provider)
            except RuntimeError:
                status = None
            byok_branch = AIRuntimeByokProviderStatus(
                supported=True,
                configured=bool(status),
                masked_secret=(status or {}).get("masked_secret"),
                validation_status=(status or {}).get("validation_status") or "unknown",
                can_validate=provider in OPENROUTER_VALIDATE_CAPABLE,
            )
            platform_configured = bool(self._operator_secret(provider))
            providers.append(
                AIRuntimeProviderStatus(
                    provider=provider,
                    kind=PROVIDER_KINDS[provider],
                    used_by=PROVIDER_USED_BY[provider],
                    byok=byok_branch,
                    platform=AIRuntimePlatformProviderStatus(
                        supported=True,
                        configured=platform_configured,
                        available=(platform_enabled and platform_configured),
                        reason_code=(
                            None
                            if platform_enabled and platform_configured
                            else (
                                "platform_not_entitled"
                                if not platform_enabled
                                else "operator_provider_missing"
                            )
                        ),
                    ),
                )
            )

        return AIRuntimeSettingsResponse(
            mode=selected_mode,
            available_modes=available_modes,
            providers=providers,
        )

    async def set_runtime_mode(
        self,
        *,
        user_id: str,
        mode: RuntimeMode,
    ) -> AIRuntimeSettingsResponse:
        if mode == "platform" and not ai_entitlement_service.is_platform_entitled(user_id):
            raise self._error(
                status_code=403,
                code="ai_runtime_platform_not_entitled",
                message="Platform-paid mode is not enabled for this account.",
                route="settings.ai_runtime.put",
                retryable=False,
                mode="platform",
                settings_path="/settings?section=ai-runtime",
            )

        await user_data_store.set_ai_runtime_mode(user_id, mode)
        return await self.get_runtime_settings(user_id)

    async def get_provider_status(
        self,
        *,
        user_id: str,
        provider: str,
    ) -> ProviderCredentialStatus:
        provider_name = self._validate_provider(provider, "settings.integrations.get")
        try:
            status = await user_key_store.get_credential_status(user_id, provider=provider_name)
        except RuntimeError:
            status = None
        if not status:
            return ProviderCredentialStatus(provider=provider_name, configured=False)
        return ProviderCredentialStatus(
            provider=provider_name,
            configured=True,
            masked_secret=status.get("masked_secret"),
            validation_status=status.get("validation_status") or "unknown",
            last_validated_at=status.get("last_validated_at"),
            updated_at=status.get("updated_at"),
        )

    async def upsert_provider_secret(
        self,
        *,
        user_id: str,
        provider: str,
        secret: str,
    ) -> ProviderCredentialStatus:
        provider_name = self._validate_provider(provider, "settings.integrations.put")
        persisted = await user_key_store.upsert_secret(
            user_id,
            provider=provider_name,
            secret=secret,
            validation_status="unknown",
            last_validated_at=None,
        )
        if isinstance(persisted, dict):
            return ProviderCredentialStatus(
                provider=provider_name,
                configured=bool(persisted.get("configured", True)),
                masked_secret=(
                    persisted.get("masked_secret")
                    or persisted.get("maskedSecret")
                ),
                validation_status=(
                    persisted.get("validation_status")
                    or persisted.get("validationStatus")
                    or "unknown"
                ),
                last_validated_at=(
                    persisted.get("last_validated_at")
                    or persisted.get("lastValidatedAt")
                ),
                updated_at=(
                    persisted.get("updated_at")
                    or persisted.get("updatedAt")
                ),
            )
        return await self.get_provider_status(user_id=user_id, provider=provider_name)

    async def delete_provider_secret(
        self,
        *,
        user_id: str,
        provider: str,
    ) -> dict[str, Any]:
        provider_name = self._validate_provider(provider, "settings.integrations.delete")
        try:
            await user_key_store.delete_credential(user_id, provider=provider_name)
        except RuntimeError:
            # Idempotent delete for unconfigured storage environments.
            pass
        return {"deleted": True, "provider": provider_name}


ai_runtime_service = AIRuntimeService()
