import importlib.util
import sys
import types
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api.models.persona_draft import PersonaDraftRequest
from api.models.persona_draft import RepoUnderstandingResult
import api.services.repo_understanding_service as repo_understanding_module

_PERSONAS_ROUTER_PATH = Path(__file__).resolve().parent.parent / "api" / "routers" / "personas.py"


def _load_personas_router_module():
    sys.modules.setdefault(
        "api.dependencies.auth",
        types.SimpleNamespace(CurrentUser=object, require_current_user=lambda: None),
    )
    spec = importlib.util.spec_from_file_location("contentflow_lab_personas_router", _PERSONAS_ROUTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_persona_draft_blank_form_queues_job_without_llm_key(monkeypatch):
    personas_router = _load_personas_router_module()
    monkeypatch.setattr(personas_router.job_store, "upsert", AsyncMock())
    monkeypatch.setattr(personas_router.user_llm_service, "get_openrouter_key", AsyncMock())

    def _fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(personas_router.asyncio, "create_task", _fake_create_task)

    response = await personas_router.create_persona_draft(
        request=PersonaDraftRequest(
            repo_source="project_repo",
            project_id="project-1",
            mode="blank_form",
        ),
        current_user=SimpleNamespace(user_id="user-1"),
    )

    assert response.status == "pending"
    personas_router.user_llm_service.get_openrouter_key.assert_not_called()


@pytest.mark.asyncio
async def test_persona_draft_requires_openrouter_key_outside_blank_mode(monkeypatch):
    personas_router = _load_personas_router_module()
    monkeypatch.setattr(
        personas_router.user_llm_service,
        "get_openrouter_key",
        AsyncMock(side_effect=RuntimeError("missing key")),
    )

    with pytest.raises(HTTPException) as exc:
        await personas_router.create_persona_draft(
            request=PersonaDraftRequest(
                repo_source="manual_url",
                manual_url="https://example.com",
                mode="suggest_from_repo",
            ),
            current_user=SimpleNamespace(user_id="user-1"),
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_persona_draft_project_repo_success_stores_completed_result(monkeypatch):
    personas_router = _load_personas_router_module()
    monkeypatch.setattr(
        personas_router.ai_runtime_service,
        "preflight_providers",
        AsyncMock(
            return_value=SimpleNamespace(
                required_provider_secrets={"openrouter": "k"},
            )
        ),
    )
    monkeypatch.setattr(
        personas_router.ai_runtime_service,
        "bind_provider_env",
        lambda _resolution: nullcontext(),
    )
    update_mock = AsyncMock()
    monkeypatch.setattr(personas_router.job_store, "update", update_mock)
    monkeypatch.setattr(
        personas_router.repo_understanding_service,
        "understand",
        AsyncMock(
            return_value=RepoUnderstandingResult(
                project_summary="summary",
                evidence=[{"source": "local_repo", "location": "README.md", "snippet": "saas"}],
                persona_candidates=[
                    {
                        "name": "Founder Persona",
                        "demographics": {"role": "Founder", "industry": "B2B SaaS"},
                        "pain_points": ["No pipeline"],
                        "goals": ["Steady demand"],
                    }
                ],
            )
        ),
    )
    monkeypatch.setattr(personas_router.user_llm_service, "get_openrouter_key", AsyncMock(return_value="k"))
    monkeypatch.setattr(
        personas_router.user_data_store,
        "get_creator_profile",
        AsyncMock(
            return_value={
                "displayName": "Lya",
                "voice": {"tone": "clear"},
                "positioning": {"angle": "practical"},
                "values": ["clarity", "speed"],
            }
        ),
    )
    monkeypatch.setattr(
        personas_router.repo_understanding_service,
        "build_persona_draft",
        lambda understanding, creator_profile=None: {
            "name": "Founder Persona",
            "pain_points": ["No pipeline"],
            "goals": ["Steady demand"],
            "confidence": 72,
        },
    )

    await personas_router._run_persona_draft_job(
        job_id="job-1",
        user_id="user-1",
        request=PersonaDraftRequest(
            repo_source="project_repo",
            project_id="project-1",
            mode="suggest_from_repo",
        ),
    )

    assert update_mock.await_count >= 3
    last_call = update_mock.await_args_list[-1]
    assert last_call.args[0] == "job-1"
    assert last_call.kwargs["status"] == "completed"
    assert last_call.kwargs["result"]["confidence"] == 72


@pytest.mark.asyncio
async def test_persona_draft_job_status_is_owner_scoped(monkeypatch):
    personas_router = _load_personas_router_module()
    monkeypatch.setattr(
        personas_router.job_store,
        "get",
        AsyncMock(
            return_value={
                "job_id": "job-1",
                "job_type": "personas.draft",
                "status": "running",
                "user_id": "owner",
            }
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await personas_router.get_persona_draft_job(
            job_id="job-1",
            current_user=SimpleNamespace(user_id="not-owner"),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_repo_understanding_uses_connected_github_source(monkeypatch):
    monkeypatch.setattr(
        repo_understanding_module.user_data_store,
        "get_github_integration",
        AsyncMock(return_value={"token": "gh-token"}),
    )
    monkeypatch.setattr(
        repo_understanding_module.repo_understanding_service,
        "_collect_github_repo",
        AsyncMock(return_value=("repo content", [])),
    )
    monkeypatch.setattr(
        repo_understanding_module.repo_understanding_service,
        "_synthesize_understanding",
        AsyncMock(return_value=RepoUnderstandingResult(project_summary="summary")),
    )

    result = await repo_understanding_module.repo_understanding_service.understand(
        "user-1",
        PersonaDraftRequest(
            repo_source="connected_github",
            repo_url="https://github.com/acme/repo",
        ),
    )

    assert result.project_summary == "summary"


@pytest.mark.asyncio
async def test_repo_understanding_accepts_public_github_manual_url(monkeypatch):
    monkeypatch.setattr(
        repo_understanding_module.repo_understanding_service,
        "_collect_github_repo",
        AsyncMock(return_value=("repo content", [])),
    )
    monkeypatch.setattr(
        repo_understanding_module.repo_understanding_service,
        "_synthesize_understanding",
        AsyncMock(return_value=RepoUnderstandingResult(project_summary="summary")),
    )

    result = await repo_understanding_module.repo_understanding_service.understand(
        "user-1",
        PersonaDraftRequest(
            repo_source="manual_url",
            repo_url="https://github.com/acme/repo",
            mode="suggest_from_repo",
        ),
    )

    assert result.project_summary == "summary"


@pytest.mark.asyncio
async def test_repo_understanding_uses_firecrawl_for_non_github_manual_url(monkeypatch):
    monkeypatch.setattr(
        repo_understanding_module.repo_understanding_service,
        "_collect_public_site",
        AsyncMock(return_value=("site content", [])),
    )
    monkeypatch.setattr(
        repo_understanding_module.repo_understanding_service,
        "_synthesize_understanding",
        AsyncMock(return_value=RepoUnderstandingResult(project_summary="summary")),
    )

    result = await repo_understanding_module.repo_understanding_service.understand(
        "user-1",
        PersonaDraftRequest(
            repo_source="manual_url",
            manual_url="https://example.com",
            mode="suggest_from_repo",
        ),
    )

    assert result.project_summary == "summary"
