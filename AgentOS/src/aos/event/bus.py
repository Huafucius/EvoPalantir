from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aos.model.runtime import RuntimeEvent

EventHandler = Callable[[RuntimeEvent], Awaitable[None] | None]


@dataclass
class Subscription:
    owner_type: str
    owner_id: str | None
    handler: EventHandler


class RuntimeEventBus:
    def __init__(self) -> None:
        self._subscriptions: list[Subscription] = []
        self._tasks: set[asyncio.Task[None]] = set()

    def subscribe(self, owner_type: str, owner_id: str | None, handler: EventHandler) -> None:
        self._subscriptions.append(
            Subscription(owner_type=owner_type, owner_id=owner_id, handler=handler)
        )

    async def publish(self, event: RuntimeEvent) -> None:
        for subscription in self._subscriptions:
            if not self._matches(subscription, event):
                continue
            task = asyncio.create_task(self._invoke(subscription.handler, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        if not self._tasks:
            return
        await asyncio.gather(*list(self._tasks))

    async def _invoke(self, handler: EventHandler, event: RuntimeEvent) -> None:
        result = handler(event)
        if asyncio.iscoroutine(result):
            await result

    @staticmethod
    def _matches(subscription: Subscription, event: RuntimeEvent) -> bool:
        if subscription.owner_type == "system":
            return True
        if subscription.owner_type == "agent":
            return event.agent_id == subscription.owner_id
        return event.session_id == subscription.owner_id


__all__ = ["RuntimeEventBus"]
