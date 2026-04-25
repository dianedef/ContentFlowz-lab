from api.models.ai_runtime import (
    AIRuntimeErrorEnvelope,
    AIRuntimeSettingsResponse,
    AIRuntimeModeAvailability,
    AIRuntimeProviderStatus,
    AIRuntimeByokProviderStatus,
    AIRuntimePlatformProviderStatus,
    ProviderCredentialUpsertRequest,
)


def test_provider_upsert_request_accepts_api_key_alias():
    payload = ProviderCredentialUpsertRequest(apiKey="sk-or-v1-12345678")
    assert payload.secret == "sk-or-v1-12345678"


def test_runtime_settings_serializes_alias_fields():
    response = AIRuntimeSettingsResponse(
        mode="byok",
        available_modes=[
            AIRuntimeModeAvailability(
                mode="platform",
                enabled=False,
                reason_code="platform_not_entitled",
                message="not allowed",
            )
        ],
        providers=[
            AIRuntimeProviderStatus(
                provider="openrouter",
                kind="llm",
                used_by=["newsletter.generate"],
                byok=AIRuntimeByokProviderStatus(
                    configured=True,
                    masked_secret="••••••••abcd",
                    validation_status="valid",
                    can_validate=True,
                ),
                platform=AIRuntimePlatformProviderStatus(
                    configured=True,
                    available=False,
                    reason_code="platform_not_entitled",
                ),
            )
        ],
    )

    payload = response.model_dump(by_alias=True)
    assert "availableModes" in payload
    assert payload["providers"][0]["usedBy"] == ["newsletter.generate"]
    assert payload["providers"][0]["byok"]["maskedSecret"] == "••••••••abcd"


def test_runtime_error_envelope_aliases_settings_path():
    envelope = AIRuntimeErrorEnvelope(
        code="ai_runtime_user_credential_missing",
        message="OpenRouter key missing.",
        kind="ai_runtime",
        route="newsletter.generate",
        retryable=False,
        mode="byok",
        provider="openrouter",
        settings_path="/settings?section=ai-runtime",
    )
    payload = envelope.model_dump(by_alias=True)
    assert payload["settingsPath"] == "/settings?section=ai-runtime"
