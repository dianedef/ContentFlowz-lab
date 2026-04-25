"""Platform-mode entitlement service (env-backed, request-time)."""

from __future__ import annotations

import os


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AIEntitlementService:
    """Decide if a user can access platform-paid AI runtime mode."""

    def is_platform_mode_globally_enabled(self) -> bool:
        return _is_truthy(os.getenv("AI_PLATFORM_MODE_ENABLED"))

    def allowed_user_ids(self) -> set[str]:
        raw = os.getenv("AI_PLATFORM_MODE_ALLOWED_USER_IDS", "")
        return {item.strip() for item in raw.split(",") if item.strip()}

    def is_platform_entitled(self, user_id: str) -> bool:
        if not self.is_platform_mode_globally_enabled():
            return False
        return user_id in self.allowed_user_ids()

    def platform_availability_reason(self, user_id: str) -> tuple[bool, str | None, str | None]:
        if self.is_platform_entitled(user_id):
            return True, None, None
        return (
            False,
            "platform_not_entitled",
            "Platform-paid mode is not enabled for this account.",
        )


ai_entitlement_service = AIEntitlementService()

