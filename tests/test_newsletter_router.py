from types import SimpleNamespace
import sys
import types
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from api.routers import newsletter as newsletter_router
from api.services.ai_runtime_service import AIRuntimeServiceError


@pytest.mark.asyncio
async def test_generate_newsletter_async_requires_user_key_even_with_env(monkeypatch):
    upsert = AsyncMock()
    monkeypatch.setattr(newsletter_router.job_store, "upsert", upsert)
    monkeypatch.setattr(
        newsletter_router.ai_runtime_service,
        "preflight_providers",
        AsyncMock(
            side_effect=AIRuntimeServiceError(
                status_code=409,
                detail={
                    "code": "ai_runtime_user_credential_missing",
                    "message": "missing OpenRouter key",
                    "kind": "ai_runtime",
                    "route": "newsletter.generate",
                    "retryable": False,
                },
            )
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await newsletter_router.generate_newsletter_async(
            request=newsletter_router.NewsletterRequest(
                name="Weekly digest",
                topics=["AI"],
                target_audience="Founders",
            ),
            background_tasks=BackgroundTasks(),
            current_user=SimpleNamespace(user_id="user-1"),
        )

    assert exc.value.status_code == 409
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_newsletter_job_status_is_restricted_to_job_owner(monkeypatch):
    monkeypatch.setattr(
        newsletter_router.job_store,
        "get",
        AsyncMock(
            return_value={
                "job_id": "job-1",
                "job_type": "newsletter.generate",
                "status": "completed",
                "user_id": "user-a",
            }
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await newsletter_router.get_job_status(
            job_id="job-1",
            current_user=SimpleNamespace(user_id="user-b"),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_newsletter_check_config_distinguishes_user_key_from_server_tools(
    monkeypatch,
):
    async def fake_preflight(*, user_id, route, required_providers, optional_providers=None):
        if required_providers == ["openrouter"]:
            raise AIRuntimeServiceError(
                status_code=409,
                detail={
                    "code": "ai_runtime_user_credential_missing",
                    "message": "missing",
                    "kind": "ai_runtime",
                    "route": route,
                    "retryable": False,
                },
            )
        return SimpleNamespace(required_provider_secrets={"exa": "k"})

    monkeypatch.setattr(newsletter_router.ai_runtime_service, "preflight_providers", fake_preflight)

    def fake_validate_config(*, openrouter_configured=None, exa_configured=None):
        return {
            "sendgrid_configured": True,
            "composio_configured": True,
            "exa_configured": bool(exa_configured),
            "openrouter_configured": bool(openrouter_configured),
            "imap_configured": True,
        }

    fake_newsletter_pkg = types.ModuleType("agents.newsletter")
    fake_newsletter_pkg.__path__ = []
    fake_config_pkg = types.ModuleType("agents.newsletter.config")
    fake_config_pkg.__path__ = []
    fake_config_module = types.ModuleType(
        "agents.newsletter.config.newsletter_config"
    )
    fake_config_module.validate_config = fake_validate_config
    monkeypatch.setitem(sys.modules, "agents.newsletter", fake_newsletter_pkg)
    monkeypatch.setitem(sys.modules, "agents.newsletter.config", fake_config_pkg)
    monkeypatch.setitem(
        sys.modules,
        "agents.newsletter.config.newsletter_config",
        fake_config_module,
    )

    response = await newsletter_router.check_config(
        current_user=SimpleNamespace(user_id="user-1"),
    )

    assert response["configured"] is False
    assert response["llm_configured"] is False
    assert response["server_ready"] is True
    assert response["checks"]["sendgrid_configured"] is True
    assert response["checks"]["openrouter_configured"] is False
