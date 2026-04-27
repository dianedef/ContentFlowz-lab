import importlib.util
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies.auth import CurrentUser, require_current_user


libsql_stub = types.ModuleType("libsql")
libsql_stub.connect = lambda *args, **kwargs: None
sys.modules.setdefault("libsql", libsql_stub)


_MODULE_PATH = Path(__file__).resolve().parents[2] / "api" / "routers" / "feedback.py"
_SPEC = importlib.util.spec_from_file_location("feedback_router_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
feedback_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(feedback_module)
feedback_router = feedback_module.router


def _build_client(*, authenticated: bool = False, email: str = "user@example.com") -> TestClient:
    app = FastAPI()
    app.include_router(feedback_router)
    if authenticated:
        app.dependency_overrides[require_current_user] = lambda: CurrentUser(
            user_id="user_123",
            email=email,
            bearer_token="test-token",
        )
    return TestClient(app)


def test_create_text_feedback_allows_anonymous_submission():
    client = _build_client()
    created_at = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)

    with patch.object(
        feedback_module.feedback_store,
        "create_entry",
        AsyncMock(
            return_value={
                "id": "fb_text_1",
                "type": "text",
                "message": "Besoin d'une version mobile plus claire",
                "audioStorageId": None,
                "durationMs": None,
                "platform": "web",
                "locale": "fr-FR",
                "userId": None,
                "userEmail": None,
                "status": "new",
                "createdAt": created_at,
            }
        ),
    ) as create_entry:
        response = client.post(
            "/api/feedback/text",
            json={
                "message": "  Besoin d'une version mobile plus claire  ",
                "platform": "Web",
                "locale": "fr-FR",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] == "fb_text_1"
    assert payload["type"] == "text"
    assert payload["message"] == "Besoin d'une version mobile plus claire"
    assert payload["userId"] is None
    assert payload["userEmail"] is None
    assert payload["status"] == "new"
    assert payload["createdAt"].startswith("2026-04-19T12:00:00")

    create_entry.assert_awaited_once_with(
        entry_type="text",
        message="Besoin d'une version mobile plus claire",
        platform="web",
        locale="fr-FR",
        user_id=None,
        user_email=None,
    )


def test_get_audio_upload_url_returns_backend_proxy():
    client = _build_client()

    with (
        patch.object(
            feedback_module.feedback_storage_service,
            "generate_storage_id",
            return_value="feedback/audio/2026/04/19/test.wav",
        ) as generate_storage_id,
        patch.object(
            feedback_module.feedback_storage_service,
            "create_upload_token",
            return_value="upload-token",
        ) as create_upload_token,
    ):
        response = client.post(
            "/api/feedback/audio/upload-url",
            json={
                "mimeType": "audio/wav",
                "fileName": "test.wav",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "uploadUrl": "http://testserver/api/feedback/audio/upload/upload-token",
        "storageId": "feedback/audio/2026/04/19/test.wav",
        "method": "PUT",
        "headers": {"Content-Type": "audio/wav"},
    }

    generate_storage_id.assert_called_once_with("test.wav", "audio/wav")
    create_upload_token.assert_called_once_with(
        "feedback/audio/2026/04/19/test.wav",
        "audio/wav",
        max_bytes=None,
    )


def test_get_audio_upload_url_forwards_requested_size_limit():
    client = _build_client()

    with (
        patch.object(
            feedback_module.feedback_storage_service,
            "generate_storage_id",
            return_value="feedback/audio/2026/04/19/test.wav",
        ),
        patch.object(
            feedback_module.feedback_storage_service,
            "create_upload_token",
            return_value="upload-token",
        ) as create_upload_token,
    ):
        response = client.post(
            "/api/feedback/audio/upload-url",
            json={
                "mimeType": "audio/wav",
                "fileName": "test.wav",
                "fileSizeBytes": 1234,
            },
        )

    assert response.status_code == 200
    create_upload_token.assert_called_once_with(
        "feedback/audio/2026/04/19/test.wav",
        "audio/wav",
        max_bytes=1234,
    )


def test_upload_audio_feedback_rejects_payload_over_signed_limit():
    client = _build_client()

    with (
        patch.object(
            feedback_module.feedback_storage_service,
            "verify_token",
            return_value={
                "storageId": "feedback/audio/2026/04/19/test.wav",
                "mimeType": "audio/wav",
                "maxBytes": 4,
            },
        ),
        patch.object(
            feedback_module.feedback_storage_service,
            "upload_bytes",
            AsyncMock(),
        ) as upload_bytes,
    ):
        response = client.put(
            "/api/feedback/audio/upload/signed-token",
            content=b"12345",
            headers={"Content-Type": "audio/wav"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Feedback upload exceeds maximum allowed size."
    upload_bytes.assert_not_awaited()


def test_feedback_admin_requires_auth():
    client = _build_client(authenticated=False)

    response = client.get("/api/feedback/admin")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


def test_feedback_admin_capability_requires_auth():
    client = _build_client(authenticated=False)

    response = client.get("/api/feedback/admin/capability")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


def test_feedback_admin_capability_returns_false_for_non_allowlisted_user():
    client = _build_client(authenticated=True, email="member@example.com")

    with patch.dict(
        feedback_module.os.environ,
        {"FEEDBACK_ADMIN_EMAILS": "admin@example.com"},
        clear=False,
    ):
        response = client.get("/api/feedback/admin/capability")

    assert response.status_code == 200
    assert response.json() == {"isAdmin": False}


def test_feedback_admin_capability_returns_true_for_allowlisted_user():
    client = _build_client(authenticated=True, email="admin@example.com")

    with patch.dict(
        feedback_module.os.environ,
        {"FEEDBACK_ADMIN_EMAILS": "admin@example.com"},
        clear=False,
    ):
        response = client.get("/api/feedback/admin/capability")

    assert response.status_code == 200
    assert response.json() == {"isAdmin": True}


def test_feedback_admin_rejects_authenticated_user_outside_allowlist():
    client = _build_client(authenticated=True, email="member@example.com")

    with patch.dict(
        feedback_module.os.environ,
        {"FEEDBACK_ADMIN_EMAILS": "admin@example.com"},
        clear=False,
    ):
        response = client.get("/api/feedback/admin")

    assert response.status_code == 403
    assert response.json()["detail"] == "Feedback admin access denied"


def test_feedback_admin_lists_entries_for_allowlisted_user():
    client = _build_client(authenticated=True, email="admin@example.com")
    created_at = datetime(2026, 4, 19, 13, 0, tzinfo=timezone.utc)

    with (
        patch.dict(
            feedback_module.os.environ,
            {"FEEDBACK_ADMIN_EMAILS": "admin@example.com"},
            clear=False,
        ),
        patch.object(
            feedback_module.feedback_store,
            "list_entries",
            AsyncMock(
                return_value=[
                    {
                        "id": "fb_audio_1",
                        "type": "audio",
                        "message": None,
                        "audioStorageId": "feedback/audio/2026/04/19/test.wav",
                        "durationMs": 4200,
                        "platform": "web",
                        "locale": "fr-FR",
                        "userId": "user_123",
                        "userEmail": "admin@example.com",
                        "status": "new",
                        "createdAt": created_at,
                    }
                ]
            ),
        ) as list_entries,
        patch.object(
            feedback_module.feedback_storage_service,
            "create_playback_token",
            return_value="playback-token",
        ) as create_playback_token,
    ):
        response = client.get("/api/feedback/admin?status=new&type=audio")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == [
        {
            "id": "fb_audio_1",
            "type": "audio",
            "message": None,
            "audioStorageId": "feedback/audio/2026/04/19/test.wav",
            "audioUrl": "http://testserver/api/feedback/audio/play/playback-token",
            "durationMs": 4200,
            "platform": "web",
            "locale": "fr-FR",
            "userId": "user_123",
            "userEmail": "admin@example.com",
            "status": "new",
            "createdAt": "2026-04-19T13:00:00Z",
        }
    ]

    list_entries.assert_awaited_once_with(status="new", entry_type="audio")
    create_playback_token.assert_called_once_with(
        "feedback/audio/2026/04/19/test.wav"
    )


def test_mark_feedback_reviewed_uses_admin_identity():
    client = _build_client(authenticated=True, email="admin@example.com")
    reviewed_at = datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)

    with (
        patch.dict(
            feedback_module.os.environ,
            {"FEEDBACK_ADMIN_EMAILS": "admin@example.com"},
            clear=False,
        ),
        patch.object(
            feedback_module.feedback_store,
            "mark_reviewed",
            AsyncMock(
                return_value={
                    "id": "fb_text_1",
                    "status": "reviewed",
                    "reviewedAt": reviewed_at,
                }
            ),
        ) as mark_reviewed,
    ):
        response = client.post("/api/feedback/admin/fb_text_1/review")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "id": "fb_text_1",
        "status": "reviewed",
        "reviewedAt": "2026-04-19T13:30:00Z",
    }

    mark_reviewed.assert_awaited_once_with(
        entry_id="fb_text_1",
        reviewer_user_id="user_123",
        reviewer_email="admin@example.com",
    )
