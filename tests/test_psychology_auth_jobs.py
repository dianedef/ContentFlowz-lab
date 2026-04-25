from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks
from fastapi import HTTPException

from api.routers import psychology as psychology_router
from api.services.user_llm_service import OpenRouterCredentialMissingError


@pytest.mark.asyncio
async def test_synthesis_status_is_restricted_to_job_owner(monkeypatch):
    monkeypatch.setattr(
        psychology_router.job_store,
        "get",
        AsyncMock(
            return_value={
                "job_id": "job-1",
                "job_type": "psychology.synthesize_narrative",
                "status": "running",
                "user_id": "user-a",
            }
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await psychology_router.get_synthesis_status(
            task_id="job-1",
            current_user=SimpleNamespace(user_id="user-b"),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_synthesis_status_returns_owned_job(monkeypatch):
    monkeypatch.setattr(
        psychology_router.job_store,
        "get",
        AsyncMock(
            return_value={
                "job_id": "job-1",
                "job_type": "psychology.synthesize_narrative",
                "status": "completed",
                "user_id": "user-a",
                "result": {"ok": True},
            }
        ),
    )

    response = await psychology_router.get_synthesis_status(
        task_id="job-1",
        current_user=SimpleNamespace(user_id="user-a"),
    )

    assert response["status"] == "completed"
    assert response["result"] == {"ok": True}


@pytest.mark.asyncio
async def test_generate_angles_submission_persists_user_scoped_job(monkeypatch):
    upsert = AsyncMock()
    monkeypatch.setattr(psychology_router.job_store, "upsert", upsert)
    monkeypatch.setattr(
        psychology_router.user_llm_service,
        "get_openrouter_key",
        AsyncMock(return_value="sk-or-v1-user"),
    )

    response = await psychology_router.generate_angles(
        request=SimpleNamespace(
            creator_voice={},
            creator_positioning={},
            narrative_summary=None,
            persona_data=SimpleNamespace(to_canonical_dict=lambda: {"name": "P"}),
            content_type=None,
            count=1,
            seo_signals=None,
            trending_signals=None,
        ),
        background_tasks=BackgroundTasks(),
        current_user=SimpleNamespace(user_id="user-1"),
    )

    assert response["status"] == "running"
    upsert.assert_awaited_once()
    assert upsert.await_args.kwargs["job_type"] == "psychology.generate_angles"
    assert upsert.await_args.kwargs["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_synthesize_narrative_requires_user_openrouter_key_even_with_env(
    monkeypatch,
):
    upsert = AsyncMock()
    monkeypatch.setattr(psychology_router.job_store, "upsert", upsert)
    monkeypatch.setattr(
        psychology_router.user_llm_service,
        "get_openrouter_key",
        AsyncMock(
            side_effect=OpenRouterCredentialMissingError("missing OpenRouter key")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await psychology_router.synthesize_narrative(
            request=SimpleNamespace(
                profile_id="default",
                entries=[],
                entry_ids=[],
                current_voice=None,
                current_positioning=None,
                chapter_title=None,
            ),
            background_tasks=BackgroundTasks(),
            current_user=SimpleNamespace(user_id="user-1"),
        )

    assert exc.value.status_code == 409
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_pipeline_requires_user_openrouter_key_before_record_creation(
    monkeypatch,
):
    upsert = AsyncMock()
    monkeypatch.setattr(psychology_router.job_store, "upsert", upsert)
    monkeypatch.setattr(
        psychology_router.user_llm_service,
        "get_openrouter_key",
        AsyncMock(
            side_effect=OpenRouterCredentialMissingError("missing OpenRouter key")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await psychology_router.dispatch_pipeline(
            request=SimpleNamespace(
                target_format="article",
                angle_data={"title": "AI angle"},
                creator_voice=None,
                seo_keyword=None,
                project_id="project-1",
            ),
            background_tasks=BackgroundTasks(),
            current_user=SimpleNamespace(user_id="user-1"),
        )

    assert exc.value.status_code == 409
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_status_is_restricted_to_job_owner(monkeypatch):
    monkeypatch.setattr(
        psychology_router.job_store,
        "get",
        AsyncMock(
            return_value={
                "job_id": "job-2",
                "job_type": "psychology.dispatch_pipeline",
                "status": "running",
                "user_id": "user-a",
            }
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await psychology_router.get_pipeline_status(
            task_id="job-2",
            current_user=SimpleNamespace(user_id="user-b"),
        )

    assert exc.value.status_code == 404
