from api.services.ai_entitlement_service import AIEntitlementService


def test_platform_mode_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AI_PLATFORM_MODE_ENABLED", raising=False)
    monkeypatch.delenv("AI_PLATFORM_MODE_ALLOWED_USER_IDS", raising=False)

    svc = AIEntitlementService()
    assert svc.is_platform_mode_globally_enabled() is False
    assert svc.is_platform_entitled("user-1") is False


def test_entitlement_requires_global_flag_and_allowlisted_user(monkeypatch):
    monkeypatch.setenv("AI_PLATFORM_MODE_ENABLED", "true")
    monkeypatch.setenv("AI_PLATFORM_MODE_ALLOWED_USER_IDS", " user-1 , user-2 ")

    svc = AIEntitlementService()
    assert svc.allowed_user_ids() == {"user-1", "user-2"}
    assert svc.is_platform_entitled("user-1") is True
    assert svc.is_platform_entitled("user-3") is False


def test_platform_availability_reason_when_user_not_entitled(monkeypatch):
    monkeypatch.setenv("AI_PLATFORM_MODE_ENABLED", "false")
    monkeypatch.setenv("AI_PLATFORM_MODE_ALLOWED_USER_IDS", "user-1")

    svc = AIEntitlementService()
    enabled, code, message = svc.platform_availability_reason("user-1")
    assert enabled is False
    assert code == "platform_not_entitled"
    assert message is not None
