from collections.abc import Awaitable, Callable
from typing import Protocol

Handler = Callable[[str], Awaitable[None]]


class Trigger(Protocol):
    """Produces new message IDs and hands each to `handler`."""

    async def run(self, handler: Handler) -> None: ...
