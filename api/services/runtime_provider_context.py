"""Request-scoped provider credential context for tool runtimes."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeProviderContext:
    route: str
    mode: str
    provider_secrets: dict[str, str]


_RUNTIME_PROVIDER_CONTEXT: ContextVar[RuntimeProviderContext | None] = ContextVar(
    "runtime_provider_context",
    default=None,
)


def set_runtime_provider_context(
    *,
    route: str,
    mode: str,
    provider_secrets: dict[str, str],
) -> Token[RuntimeProviderContext | None]:
    """Bind provider secrets for the current async context."""
    context = RuntimeProviderContext(
        route=route,
        mode=mode,
        provider_secrets=dict(provider_secrets),
    )
    return _RUNTIME_PROVIDER_CONTEXT.set(context)


def reset_runtime_provider_context(token: Token[RuntimeProviderContext | None]) -> None:
    """Restore the previous provider scope."""
    _RUNTIME_PROVIDER_CONTEXT.reset(token)


def get_runtime_provider_context() -> RuntimeProviderContext | None:
    """Return active request-scoped provider context, if any."""
    return _RUNTIME_PROVIDER_CONTEXT.get()


def get_runtime_provider_secret(provider: str) -> str | None:
    """Resolve provider secret from request scope."""
    context = get_runtime_provider_context()
    if context is None:
        return None
    value = context.provider_secrets.get(provider)
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@contextmanager
def runtime_provider_scope(*, route: str, mode: str, provider_secrets: dict[str, str]):
    """Temporarily bind provider secrets for downstream tools."""
    token = set_runtime_provider_context(
        route=route,
        mode=mode,
        provider_secrets=provider_secrets,
    )
    try:
        yield
    finally:
        reset_runtime_provider_context(token)
