from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api.models.ai_runtime import (
    AIRuntimeModeAvailability,
    AIRuntimeProviderStatus,
    AIRuntimeByokProviderStatus,
    AIRuntimePlatformProviderStatus,
    AIRuntimeSettingsResponse,
    ProviderCredentialDeleteResponse,
    ProviderCredentialStatus,
)
from api.models.user_data import OpenRouterCredentialUpsertRequest
from api.routers import settings_integrations as router
from api.services.ai_runtime_service import AIRuntimeServiceError


@pytest.mark.asyncio
async def test_get_ai_runtime_returns_runtime_payload(monkeypatch):
    expected = AIRuntimeSettingsResponse(
        mode="byok",
        available_modes=[
            AIRuntimeModeAvailability(mode="byok", enabled=True),
            AIRuntimeModeAvailability(
                mode="platform",
                enabled=False,
                reason_code="platform_not_entitled",
                message="locked",
            ),
        ],
        providers=[
            AIRuntimeProviderStatus(
                provider="openrouter",
                kind="llm",
                used_by=["newsletter.generate"],
                byok=AIRuntimeByokProviderStatus(configured=False),
                platform=AIRuntimePlatformProviderStatus(configured=False, available=False),
            )
        ],
    )
    monkeypatch.setattr(
        router.ai_runtime_service,
        "get_runtime_settings",
        AsyncMock(return_value=expected),
    )

    response = await router.get_ai_runtime(
        current_user=SimpleNamespace(user_id="user-1"),
    )
    assert response.mode == "byok"
    assert response.available_modes[1].reason_code == "platform_not_entitled"


@pytest.mark.asyncio
async def test_put_ai_runtime_translates_runtime_error(monkeypatch):
    monkeypatch.setattr(
        router.ai_runtime_service,
        "set_runtime_mode",
        AsyncMock(
            side_effect=AIRuntimeServiceError(
                status_code=403,
                detail={
                    "code": "ai_runtime_platform_not_entitled",
                    "message": "locked",
                    "kind": "ai_runtime",
                    "route": "settings.ai_runtime.put",
                    "retryable": False,
                },
            )
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await router.put_ai_runtime(
            request=SimpleNamespace(mode="platform"),
            current_user=SimpleNamespace(user_id="user-1"),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "ai_runtime_platform_not_entitled"


@pytest.mark.asyncio
async def test_openrouter_get_wrapper_delegates_to_generic_provider_route(monkeypatch):
    monkeypatch.setattr(
        router,
        "get_provider_credential",
        AsyncMock(
            return_value=ProviderCredentialStatus(
                provider="openrouter",
                configured=True,
                masked_secret="••••••••abcd",
                validation_status="valid",
            )
        ),
    )

    response = await router.get_openrouter_credential(
        current_user=SimpleNamespace(user_id="user-1"),
    )
    assert response.provider == "openrouter"
    assert response.masked_secret == "••••••••abcd"


@pytest.mark.asyncio
async def test_openrouter_put_wrapper_maps_api_key_payload(monkeypatch):
    put_provider = AsyncMock(
        return_value=ProviderCredentialStatus(
            provider="openrouter",
            configured=True,
            masked_secret="••••••••1234",
            validation_status="unknown",
        )
    )
    monkeypatch.setattr(router, "put_provider_credential", put_provider)

    response = await router.put_openrouter_credential(
        request=OpenRouterCredentialUpsertRequest(api_key="sk-or-v1-secret-1234"),
        current_user=SimpleNamespace(user_id="user-1"),
    )

    assert response.configured is True
    assert response.masked_secret == "••••••••1234"
    assert put_provider.await_args.kwargs["provider"] == "openrouter"
    assert put_provider.await_args.kwargs["request"].secret == "sk-or-v1-secret-1234"


@pytest.mark.asyncio
async def test_openrouter_delete_wrapper_returns_legacy_shape(monkeypatch):
    monkeypatch.setattr(
        router,
        "delete_provider_credential",
        AsyncMock(
            return_value=ProviderCredentialDeleteResponse(
                deleted=True,
                provider="openrouter",
            )
        ),
    )

    response = await router.delete_openrouter_credential(
        current_user=SimpleNamespace(user_id="user-1"),
    )
    assert response == {"deleted": True}
