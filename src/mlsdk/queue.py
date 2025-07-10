"""Simple asynchronous queue worker for processing items in a queue."""

import asyncio
from typing import Callable, Awaitable, Any


class AsyncQueueWorker:
    """A simple asynchronous queue worker that processes items in a queue."""

    def __init__(self, callback: Callable[[Any], Awaitable[None]]):
        """Initialize the AsyncQueueWorker."""
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._callback = callback
        self._worker_task = asyncio.create_task(self._worker())
        self._flush_event = asyncio.Event()
        self._flush_event.set()  # Initially set, since queue is empty

    async def _worker(self):
        while True:
            item = await self._queue.get()
            self._flush_event.clear()
            try:
                await self._callback(item)
            finally:
                self._queue.task_done()
                if self._queue.empty():
                    self._flush_event.set()

    def enqueue(self, item: Any):
        """Enqueue an item to be processed by the worker."""
        self._queue.put_nowait(item)
        self._flush_event.clear()

    async def flush(self, final: bool = False):
        """Wait for all queued items to be processed."""
        await self._queue.join()
        await self._flush_event.wait()
        if final:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
