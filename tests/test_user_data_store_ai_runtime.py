from unittest.mock import AsyncMock

import pytest

from api.services.user_data_store import UserDataStore


@pytest.mark.asyncio
async def test_get_effective_ai_runtime_mode_defaults_to_byok_when_missing(monkeypatch):
    store = UserDataStore()
    monkeypatch.setattr(
        store,
        "get_user_settings",
        AsyncMock(return_value={"robotSettings": {}}),
    )

    mode = await store.get_effective_ai_runtime_mode("user-1")
    assert mode == "byok"


@pytest.mark.asyncio
async def test_get_effective_ai_runtime_mode_reads_persisted_value(monkeypatch):
    store = UserDataStore()
    monkeypatch.setattr(
        store,
        "get_user_settings",
        AsyncMock(return_value={"robotSettings": {"aiRuntime": {"mode": "platform"}}}),
    )

    mode = await store.get_effective_ai_runtime_mode("user-1")
    assert mode == "platform"


@pytest.mark.asyncio
async def test_set_ai_runtime_mode_persists_nested_robot_settings(monkeypatch):
    store = UserDataStore()
    update = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(store, "update_user_settings", update)

    await store.set_ai_runtime_mode("user-1", "platform")

    update.assert_awaited_once_with(
        "user-1",
        {"robotSettings": {"aiRuntime": {"mode": "platform"}}},
    )


@pytest.mark.asyncio
async def test_set_ai_runtime_mode_rejects_unknown_value():
    store = UserDataStore()
    with pytest.raises(ValueError):
        await store.set_ai_runtime_mode("user-1", "enterprise")
