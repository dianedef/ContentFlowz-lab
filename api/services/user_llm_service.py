"""Runtime resolver for user-scoped LLM credentials (OpenRouter V1)."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from api.services.ai_runtime_service import AIRuntimeServiceError, ai_runtime_service

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
NEWSLETTER_OPENROUTER_MODEL = "anthropic/claude-3.5-sonnet"


class UserLLMCredentialError(RuntimeError):
    """Base error for user-scoped runtime credential failures."""


class OpenRouterCredentialMissingError(UserLLMCredentialError):
    """Raised when the user has not configured an OpenRouter key."""


class OpenRouterCredentialInvalidError(UserLLMCredentialError):
    """Raised when the stored OpenRouter key is explicitly invalid."""


class AIRuntimeResolutionError(UserLLMCredentialError):
    """Raised when centralized runtime resolution fails."""

    def __init__(self, *, status_code: int, detail: dict[str, Any]) -> None:
        super().__init__(detail.get("message") or "AI runtime resolution failed.")
        self.status_code = status_code
        self.detail = detail


class UserLLMService:
    """Resolve user-managed OpenRouter key and build OpenAI-compatible client."""

    async def get_openrouter_key(self, user_id: str, *, route: str = "runtime.openrouter") -> str:
        try:
            resolution = await ai_runtime_service.preflight_providers(
                user_id=user_id,
                route=route,
                required_providers=["openrouter"],
            )
        except AIRuntimeServiceError as exc:
            raise AIRuntimeResolutionError(
                status_code=exc.status_code,
                detail=exc.detail,
            ) from exc
        return resolution.get_required_secret("openrouter")

    async def get_openrouter_client(self, user_id: str, *, route: str = "runtime.openrouter") -> OpenAI:
        key = await self.get_openrouter_key(user_id, route=route)
        return OpenAI(
            api_key=key,
            base_url=OPENROUTER_BASE_URL,
        )

    async def get_crewai_llm(
        self,
        user_id: str,
        *,
        model: str = DEFAULT_OPENROUTER_MODEL,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        route: str = "runtime.openrouter",
    ):
        """Build a request-scoped CrewAI LLM with the user's OpenRouter key."""
        from crewai import LLM

        key = await self.get_openrouter_key(user_id, route=route)
        kwargs = {
            "model": model,
            "base_url": OPENROUTER_BASE_URL,
            "api_key": key,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return LLM(**kwargs)

    async def generate_json(
        self,
        user_id: str,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_OPENROUTER_MODEL,
        route: str = "runtime.openrouter",
    ) -> dict:
        client = await self.get_openrouter_client(user_id, route=route)
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise RuntimeError("OpenRouter returned an empty response.")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenRouter did not return valid JSON.") from exc


user_llm_service = UserLLMService()
