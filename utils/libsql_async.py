"""Async compatibility layer for the maintained `libsql` driver.

The repository previously depended on the deprecated `libsql-client` package.
This module exposes the small async API surface the app uses while relying on
the maintained `libsql` package underneath.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import libsql


@dataclass
class ResultSet:
    rows: list[tuple[Any, ...]]


class Client:
    def __init__(self, url: str, auth_token: str | None = None) -> None:
        self._url = url
        self._auth_token = auth_token or ""
        self._conn = self._connect()
        self._lock: asyncio.Lock | None = None

    def _connect(self) -> libsql.Connection:
        return libsql.connect(
            database=self._url,
            auth_token=self._auth_token,
            _check_same_thread=False,
        )

    def _ensure_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @staticmethod
    def _should_reconnect(exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "stream not found" in message
            or "hrana" in message
            or "websocket" in message
            or "connection" in message
            or "transport" in message
        )

    def _reconnect(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = self._connect()

    async def execute(
        self,
        statement: str,
        args: list[Any] | tuple[Any, ...] | None = None,
    ) -> ResultSet:
        params = list(args) if args is not None else []

        def _run() -> ResultSet:
            cursor = self._conn.execute(statement, params)
            try:
                rows = cursor.fetchall()
            except Exception:
                rows = []
            return ResultSet(rows=rows)

        async with self._ensure_lock():
            for attempt in range(2):
                try:
                    return await asyncio.to_thread(_run)
                except Exception as exc:
                    if attempt == 0 and self._should_reconnect(exc):
                        await asyncio.to_thread(self._reconnect)
                        continue
                    raise

    async def close(self) -> None:
        async with self._ensure_lock():
            await asyncio.to_thread(self._conn.close)


def create_client(*, url: str, auth_token: str | None = None, **_: Any) -> Client:
    return Client(url=url, auth_token=auth_token)
