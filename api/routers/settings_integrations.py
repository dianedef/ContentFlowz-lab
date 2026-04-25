"""Authenticated runtime mode and provider integration settings endpoints."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies.auth import CurrentUser, require_current_user
from api.models.ai_runtime import (
    AIRuntimeModeUpdateRequest,
    AIRuntimeSettingsResponse,
    ProviderCredentialDeleteResponse,
    ProviderCredentialStatus,
    ProviderCredentialUpsertRequest,
)
from api.models.user_data import (
    OpenRouterCredentialStatus,
    OpenRouterCredentialUpsertRequest,
    OpenRouterCredentialValidateResponse,
)
from api.services.ai_runtime_service import AIRuntimeServiceError, ai_runtime_service
from api.services.user_key_store import user_key_store

router = APIRouter(tags=["Settings Integrations"])

_OPENROUTER_PROVIDER = "openrouter"
_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def _raise_runtime_error(exc: AIRuntimeServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _to_openrouter_status(status: ProviderCredentialStatus) -> OpenRouterCredentialStatus:
    return OpenRouterCredentialStatus(
        provider="openrouter",
        configured=status.configured,
        masked_secret=status.masked_secret,
        validation_status=status.validation_status,
        last_validated_at=status.last_validated_at,
        updated_at=status.updated_at,
    )


@router.get(
    "/api/settings/ai-runtime",
    response_model=AIRuntimeSettingsResponse,
    summary="Get AI runtime settings",
)
async def get_ai_runtime(
    current_user: CurrentUser = Depends(require_current_user),
) -> AIRuntimeSettingsResponse:
    return await ai_runtime_service.get_runtime_settings(current_user.user_id)


@router.put(
    "/api/settings/ai-runtime",
    response_model=AIRuntimeSettingsResponse,
    summary="Update AI runtime mode",
)
async def put_ai_runtime(
    request: AIRuntimeModeUpdateRequest,
    current_user: CurrentUser = Depends(require_current_user),
) -> AIRuntimeSettingsResponse:
    try:
        return await ai_runtime_service.set_runtime_mode(
            user_id=current_user.user_id,
            mode=request.mode,
        )
    except AIRuntimeServiceError as exc:
        _raise_runtime_error(exc)


@router.get(
    "/api/settings/integrations/openrouter",
    response_model=OpenRouterCredentialStatus,
    summary="Get OpenRouter credential status",
)
async def get_openrouter_credential(
    current_user: CurrentUser = Depends(require_current_user),
) -> OpenRouterCredentialStatus:
    """Compatibility wrapper backed by generic provider settings."""
    status = await get_provider_credential(
        provider=_OPENROUTER_PROVIDER,
        current_user=current_user,
    )
    return _to_openrouter_status(status)


@router.put(
    "/api/settings/integrations/openrouter",
    response_model=OpenRouterCredentialStatus,
    summary="Store OpenRouter credential",
)
async def put_openrouter_credential(
    request: OpenRouterCredentialUpsertRequest,
    current_user: CurrentUser = Depends(require_current_user),
) -> OpenRouterCredentialStatus:
    """Compatibility wrapper backed by generic provider settings."""
    status = await put_provider_credential(
        provider=_OPENROUTER_PROVIDER,
        request=ProviderCredentialUpsertRequest(secret=request.api_key),
        current_user=current_user,
    )
    return _to_openrouter_status(status)


@router.delete(
    "/api/settings/integrations/openrouter",
    response_model=dict[str, bool],
    summary="Delete OpenRouter credential",
)
async def delete_openrouter_credential(
    current_user: CurrentUser = Depends(require_current_user),
) -> dict[str, bool]:
    """Compatibility wrapper backed by generic provider settings."""
    payload = await delete_provider_credential(
        provider=_OPENROUTER_PROVIDER,
        current_user=current_user,
    )
    return {"deleted": payload.deleted}


@router.get(
    "/api/settings/integrations/{provider}",
    response_model=ProviderCredentialStatus,
    summary="Get provider credential status",
)
async def get_provider_credential(
    provider: str,
    current_user: CurrentUser = Depends(require_current_user),
) -> ProviderCredentialStatus:
    try:
        return await ai_runtime_service.get_provider_status(
            user_id=current_user.user_id,
            provider=provider,
        )
    except AIRuntimeServiceError as exc:
        _raise_runtime_error(exc)


@router.put(
    "/api/settings/integrations/{provider}",
    response_model=ProviderCredentialStatus,
    summary="Store provider credential",
)
async def put_provider_credential(
    provider: str,
    request: ProviderCredentialUpsertRequest,
    current_user: CurrentUser = Depends(require_current_user),
) -> ProviderCredentialStatus:
    try:
        return await ai_runtime_service.upsert_provider_secret(
            user_id=current_user.user_id,
            provider=provider,
            secret=request.secret,
        )
    except AIRuntimeServiceError as exc:
        _raise_runtime_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete(
    "/api/settings/integrations/{provider}",
    response_model=ProviderCredentialDeleteResponse,
    summary="Delete provider credential",
)
async def delete_provider_credential(
    provider: str,
    current_user: CurrentUser = Depends(require_current_user),
) -> ProviderCredentialDeleteResponse:
    try:
        payload = await ai_runtime_service.delete_provider_secret(
            user_id=current_user.user_id,
            provider=provider,
        )
    except AIRuntimeServiceError as exc:
        _raise_runtime_error(exc)
    return ProviderCredentialDeleteResponse(**payload)


@router.post(
    "/api/settings/integrations/openrouter/validate",
    response_model=OpenRouterCredentialValidateResponse,
    summary="Validate stored OpenRouter credential",
)
async def validate_openrouter_credential(
    current_user: CurrentUser = Depends(require_current_user),
) -> OpenRouterCredentialValidateResponse:
    try:
        api_key = await user_key_store.get_secret(
            current_user.user_id,
            provider=_OPENROUTER_PROVIDER,
        )
    except RuntimeError:
        api_key = None
    if not api_key:
        return OpenRouterCredentialValidateResponse(
            provider="openrouter",
            valid=False,
            validation_status="missing",
            message="No OpenRouter key configured.",
        )

    validation_status = "invalid"
    message = "OpenRouter key is invalid."
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(
                _OPENROUTER_MODELS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if response.status_code < 400:
            validation_status = "valid"
            message = "OpenRouter key is valid."
    except Exception:
        validation_status = "invalid"
        message = "OpenRouter validation request failed."

    try:
        await user_key_store.set_validation_status(
            current_user.user_id,
            provider=_OPENROUTER_PROVIDER,
            validation_status=validation_status,
        )
    except RuntimeError:
        pass
    return OpenRouterCredentialValidateResponse(
        provider="openrouter",
        valid=validation_status == "valid",
        validation_status=validation_status,
        message=message,
    )
