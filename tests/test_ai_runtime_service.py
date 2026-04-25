import os
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from api.services.ai_runtime_service import (
    AIRuntimeService,
    AIRuntimeServiceError,
    RuntimeResolution,
    user_key_store,
)
from api.services.runtime_provider_context import get_runtime_provider_secret

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _identity_tool_decorator(func=None, *args, **kwargs):
    if callable(func):
        return func
    if func is None or not callable(func):
        def _decorator(inner):
            return inner
        return _decorator


def _load_module(name: str, relative_path: str):
    module_path = _PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_bind_provider_env_uses_request_scope_without_mutating_process_env(monkeypatch):
    svc = AIRuntimeService()
    monkeypatch.setenv("EXA_API_KEY", "process-exa-key")

    resolution = RuntimeResolution(
        mode="byok",
        route="newsletter.generate",
        required_provider_secrets={"exa": "scoped-exa-key"},
        optional_provider_secrets={"firecrawl": "scoped-firecrawl-key"},
    )

    with svc.bind_provider_env(resolution):
        assert get_runtime_provider_secret("exa") == "scoped-exa-key"
        assert get_runtime_provider_secret("firecrawl") == "scoped-firecrawl-key"
        assert os.getenv("EXA_API_KEY") == "process-exa-key"

    assert get_runtime_provider_secret("exa") is None
    assert os.getenv("EXA_API_KEY") == "process-exa-key"


@pytest.mark.asyncio
async def test_preflight_missing_required_byok_provider_raises_runtime_error(monkeypatch):
    svc = AIRuntimeService()
    monkeypatch.setattr(svc, "get_effective_mode", AsyncMock(return_value="byok"))
    monkeypatch.setattr(
        user_key_store,
        "get_credential_status",
        AsyncMock(return_value=None),
    )

    with pytest.raises(AIRuntimeServiceError) as exc:
        await svc.preflight_providers(
            user_id="user-1",
            route="research.competitor_analysis",
            required_providers=["exa"],
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "ai_runtime_user_credential_missing"
    assert exc.value.detail["provider"] == "exa"


@pytest.mark.asyncio
async def test_upsert_provider_secret_uses_persisted_payload_without_extra_lookup(monkeypatch):
    svc = AIRuntimeService()
    upsert = AsyncMock(
        return_value={
            "provider": "openrouter",
            "configured": True,
            "masked_secret": "••••••••abcd",
            "validation_status": "unknown",
            "updated_at": None,
            "last_validated_at": None,
        }
    )
    monkeypatch.setattr(user_key_store, "upsert_secret", upsert)

    status = await svc.upsert_provider_secret(
        user_id="user-1",
        provider="openrouter",
        secret="sk-or-v1-secret-abcd",
    )

    assert status.provider == "openrouter"
    assert status.configured is True
    assert status.masked_secret == "••••••••abcd"
    upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_exa_tool_requires_request_scoped_key(monkeypatch):
    class FakeExa:
        def __init__(self, api_key):
            self.api_key = api_key

    fake_exa = types.ModuleType("exa_py")
    fake_exa.Exa = FakeExa
    fake_crewai = types.ModuleType("crewai")
    fake_crewai_tools = types.ModuleType("crewai.tools")
    fake_crewai_tools.tool = _identity_tool_decorator
    fake_crewai.tools = fake_crewai_tools

    monkeypatch.setitem(sys.modules, "exa_py", fake_exa)
    monkeypatch.setitem(sys.modules, "crewai", fake_crewai)
    monkeypatch.setitem(sys.modules, "crewai.tools", fake_crewai_tools)
    monkeypatch.setenv("EXA_API_KEY", "process-exa-key")

    exa_tools = _load_module(
        "contentflow_test_exa_tools",
        "agents/shared/tools/exa_tools.py",
    )

    svc = AIRuntimeService()
    resolution = RuntimeResolution(
        mode="byok",
        route="research.competitor_analysis",
        required_provider_secrets={"exa": "scoped-exa-key"},
    )
    with svc.bind_provider_env(resolution):
        client = exa_tools._get_client()
        assert client.api_key == "scoped-exa-key"

    with pytest.raises(ValueError, match="Runtime provider secret required for provider 'exa'"):
        exa_tools._get_client()


@pytest.mark.asyncio
async def test_firecrawl_tool_requires_request_scoped_key(monkeypatch):
    class FakeFirecrawlApp:
        def __init__(self, *, api_key):
            self.api_key = api_key

    fake_firecrawl = types.ModuleType("firecrawl")
    fake_firecrawl.FirecrawlApp = FakeFirecrawlApp
    fake_crewai = types.ModuleType("crewai")
    fake_crewai_tools = types.ModuleType("crewai.tools")
    fake_crewai_tools.tool = _identity_tool_decorator
    fake_crewai.tools = fake_crewai_tools

    monkeypatch.setitem(sys.modules, "firecrawl", fake_firecrawl)
    monkeypatch.setitem(sys.modules, "crewai", fake_crewai)
    monkeypatch.setitem(sys.modules, "crewai.tools", fake_crewai_tools)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "process-firecrawl-key")

    firecrawl_tools = _load_module(
        "contentflow_test_firecrawl_tools",
        "agents/shared/tools/firecrawl_tools.py",
    )

    svc = AIRuntimeService()
    resolution = RuntimeResolution(
        mode="byok",
        route="personas.draft",
        required_provider_secrets={"firecrawl": "scoped-firecrawl-key"},
    )
    with svc.bind_provider_env(resolution):
        client = firecrawl_tools._get_client()
        assert client.api_key == "scoped-firecrawl-key"

    with pytest.raises(ValueError, match="Runtime provider secret required for provider 'firecrawl'"):
        firecrawl_tools._get_client()


@pytest.mark.asyncio
async def test_newsletter_content_collector_requires_request_scoped_exa_key(monkeypatch):
    class FakeExa:
        def __init__(self, api_key):
            self.api_key = api_key

    fake_exa = types.ModuleType("exa_py")
    fake_exa.Exa = FakeExa
    fake_crewai = types.ModuleType("crewai")
    fake_crewai_tools = types.ModuleType("crewai.tools")
    fake_crewai_tools.tool = _identity_tool_decorator
    fake_crewai.tools = fake_crewai_tools

    monkeypatch.setitem(sys.modules, "exa_py", fake_exa)
    monkeypatch.setitem(sys.modules, "crewai", fake_crewai)
    monkeypatch.setitem(sys.modules, "crewai.tools", fake_crewai_tools)
    monkeypatch.setenv("EXA_API_KEY", "process-exa-key")

    content_tools = _load_module(
        "contentflow_test_newsletter_content_tools",
        "agents/newsletter/tools/content_tools.py",
    )

    svc = AIRuntimeService()
    resolution = RuntimeResolution(
        mode="byok",
        route="newsletter.generate",
        required_provider_secrets={"exa": "scoped-newsletter-exa"},
    )
    with svc.bind_provider_env(resolution):
        collector = content_tools.ContentCollector()
        assert collector.exa.api_key == "scoped-newsletter-exa"

    with pytest.raises(ValueError, match="Runtime provider secret required for provider 'exa'"):
        content_tools.ContentCollector()
