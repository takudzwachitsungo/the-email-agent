import asyncio
import logging

from email_agent.trigger.base import Handler

log = logging.getLogger(__name__)


class PollTrigger:
    """Polls Gmail for unread message IDs and dispatches each to the handler."""

    def __init__(self, *, gmail, interval: int) -> None:
        self.gmail = gmail
        self.interval = interval
        self._stop = asyncio.Event()

    async def poll_once(self, handler: Handler) -> None:
        ids = await self.gmail.fetch_unread_ids()
        for mid in ids:
            await handler(mid)

    async def run(self, handler: Handler) -> None:
        log.info("poll trigger started (interval=%ss)", self.interval)
        while not self._stop.is_set():
            try:
                await self.poll_once(handler)
            except Exception:
                log.exception("poll iteration failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()
