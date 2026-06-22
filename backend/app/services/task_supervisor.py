"""Small task owner for runtime provider loops."""

import asyncio
from collections.abc import Coroutine
from typing import Any


class TaskSupervisor:
    """Own cancellable runtime tasks and make cleanup deterministic."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    def create(self, awaitable: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task: asyncio.Task[Any] = asyncio.create_task(awaitable)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def cancel_all(self) -> None:
        for task in tuple(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    @property
    def pending_count(self) -> int:
        return sum(1 for task in self._tasks if not task.done())
