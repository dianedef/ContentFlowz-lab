from datetime import datetime
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.modules.setdefault("libsql", types.SimpleNamespace())

_ME_ROUTER_PATH = Path(__file__).resolve().parent.parent / "api" / "routers" / "me.py"
_SPEC = importlib.util.spec_from_file_location("contentflow_lab_me_router", _ME_ROUTER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
me_router = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(me_router)

from api.models.project import Project


@pytest.mark.asyncio
async def test_bootstrap_prefers_default_project_id_from_user_settings(monkeypatch):
    user = SimpleNamespace(user_id="user-1", email="user@example.com")
    projects = [
        Project(
            id="project-1",
            user_id="user-1",
            name="Project 1",
            url="https://github.com/acme/project-1",
            created_at=datetime.now(),
        ),
        Project(
            id="project-2",
            user_id="user-1",
            name="Project 2",
            url="https://github.com/acme/project-2",
            created_at=datetime.now(),
        ),
    ]

    monkeypatch.setattr(
        me_router.project_store,
        "get_by_user",
        AsyncMock(return_value=projects),
    )
    monkeypatch.setattr(
        me_router.user_data_store,
        "get_user_settings",
        AsyncMock(return_value={"defaultProjectId": "project-2"}),
    )

    response = await me_router.get_bootstrap(current_user=user)

    assert response.default_project_id == "project-2"
    assert response.user.default_project_id == "project-2"
    assert response.workspace_status == "ready"


@pytest.mark.asyncio
async def test_bootstrap_falls_back_to_first_project_when_setting_is_invalid(
    monkeypatch,
):
    user = SimpleNamespace(user_id="user-1", email="user@example.com")
    projects = [
        Project(
            id="project-1",
            user_id="user-1",
            name="Project 1",
            url="https://github.com/acme/project-1",
            created_at=datetime.now(),
        ),
    ]

    monkeypatch.setattr(
        me_router.project_store,
        "get_by_user",
        AsyncMock(return_value=projects),
    )
    monkeypatch.setattr(
        me_router.user_data_store,
        "get_user_settings",
        AsyncMock(return_value={"defaultProjectId": "missing-project"}),
    )

    response = await me_router.get_bootstrap(current_user=user)

    assert response.default_project_id == "project-1"
    assert response.user.default_project_id == "project-1"
