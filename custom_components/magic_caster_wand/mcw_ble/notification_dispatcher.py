"""Route queued BLE notifications to their protocol handlers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import AsyncExitStack
from typing import Any

from bleak import BleakClient
from blesession import Notifications, NotificationTimeout, SessionDropped

_LOGGER = logging.getLogger(__name__)


class NotificationDispatcher:
    """Subscribe once per characteristic and dispatch queued frames serially."""

    def __init__(self, client: BleakClient, handlers: dict[str, Callable[[Any, bytearray], None]]) -> None:
        self._client = client
        self._handlers = handlers
        self._stack: AsyncExitStack | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._lifecycle_lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Open notification queues and start one consumer for each characteristic."""
        async with self._lifecycle_lock:
            if self._stack is not None:
                return

            stack = AsyncExitStack()
            await stack.__aenter__()
            tasks: list[asyncio.Task[None]] = []
            try:
                for characteristic, handler in self._handlers.items():
                    notifications = await stack.enter_async_context(
                        Notifications(self._client, characteristic, recover=True)
                    )
                    tasks.append(asyncio.create_task(self._consume(notifications, handler)))
            except BaseException:
                for task in tasks:
                    task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                await stack.aclose()
                raise

            self._stack = stack
            self._tasks = tasks

    async def stop(self) -> None:
        """Stop consumers and release every notification subscription."""
        async with self._lifecycle_lock:
            tasks, self._tasks = self._tasks, []
            for task in tasks:
                task.cancel()
            try:
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                stack, self._stack = self._stack, None
                if stack is not None:
                    await stack.aclose()

    async def _consume(self, notifications: Notifications, handler: Callable[[Any, bytearray], None]) -> None:
        """Deliver each queued frame until the link drops or the task is cancelled."""
        while True:
            try:
                data = await notifications.next(3600, step="notification dispatch")
            except NotificationTimeout:
                continue
            except SessionDropped:
                if self._cleanup_task is None or self._cleanup_task.done():
                    self._cleanup_task = asyncio.create_task(self.stop())
                    self._cleanup_task.add_done_callback(self._on_cleanup_done)
                return

            try:
                handler(None, bytearray(data))
            except Exception:
                _LOGGER.exception("Error dispatching BLE notification")

    def _on_cleanup_done(self, task: asyncio.Task[None]) -> None:
        if self._cleanup_task is task:
            self._cleanup_task = None
        if not task.cancelled() and task.exception() is not None:
            _LOGGER.error("Failed to clean up BLE notification subscriptions: %s", task.exception())
