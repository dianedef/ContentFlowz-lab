import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies.auth import CurrentUser, require_current_user


libsql_stub = types.ModuleType("libsql")
libsql_stub.connect = lambda *args, **kwargs: None
sys.modules.setdefault("libsql", libsql_stub)


_MODULE_PATH = Path(__file__).resolve().parents[2] / "api" / "routers" / "integrations.py"
_SPEC = importlib.util.spec_from_file_location("integrations_router_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
integrations_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(integrations_module)
integrations_router = integrations_module.router

_MISSING_KEY_ERROR = "USER_SECRETS_MASTER_KEY is required for GitHub integration operations."


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(integrations_router)
    app.dependency_overrides[require_current_user] = lambda: CurrentUser(
        user_id="user_123",
        email="user@example.com",
        bearer_token="test-token",
    )
    return TestClient(app)


def test_github_status_returns_503_when_store_requires_master_key():
    client = _build_client()

    with patch.object(
        integrations_module.user_data_store,
        "get_github_integration",
        AsyncMock(side_effect=RuntimeError(_MISSING_KEY_ERROR)),
    ):
        response = client.get("/api/integrations/github/status")

    assert response.status_code == 503
    assert response.json()["detail"] == _MISSING_KEY_ERROR


def test_github_connect_returns_503_when_store_requires_master_key():
    client = _build_client()

    with (
        patch.dict(
            integrations_module.os.environ,
            {"GITHUB_CLIENT_ID": "test-client-id"},
            clear=False,
        ),
        patch.object(
            integrations_module.user_data_store,
            "create_github_oauth_state",
            AsyncMock(side_effect=RuntimeError(_MISSING_KEY_ERROR)),
        ),
    ):
        response = client.get("/api/integrations/github/connect")

    assert response.status_code == 503
    assert response.json()["detail"] == _MISSING_KEY_ERROR


def test_github_repos_returns_503_when_store_requires_master_key():
    client = _build_client()

    with patch.object(
        integrations_module.user_data_store,
        "get_github_integration",
        AsyncMock(side_effect=RuntimeError(_MISSING_KEY_ERROR)),
    ):
        response = client.get("/api/integrations/github/repos")

    assert response.status_code == 503
    assert response.json()["detail"] == _MISSING_KEY_ERROR


def test_github_callback_returns_503_when_store_requires_master_key():
    client = _build_client()

    with patch.object(
        integrations_module.user_data_store,
        "consume_github_oauth_state",
        AsyncMock(side_effect=RuntimeError(_MISSING_KEY_ERROR)),
    ):
        response = client.get("/api/integrations/github/callback?code=test-code&state=test-state")

    assert response.status_code == 503
    assert response.json()["detail"] == _MISSING_KEY_ERROR
