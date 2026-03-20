from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast

from aos.hook.permissions import OwnerType, ensure_runtime_event_allowed
from aos.model.runtime import RuntimeEvent

EventHandler = Callable[[RuntimeEvent], Awaitable[None] | None]


@dataclass
class Subscription:
    instance_id: str | None
    owner_type: str
    owner_id: str | None
    event_type: str | None
    handler: EventHandler


class RuntimeEventBus:
    def __init__(self) -> None:
        self._subscriptions: list[Subscription] = []
        self._tasks: set[asyncio.Task[None]] = set()

    def subscribe(
        self,
        owner_type: str,
        owner_id: str | None,
        event_type: str | EventHandler,
        handler: EventHandler | None = None,
        *,
        instance_id: str | None = None,
    ) -> None:
        if handler is None:
            actual_event_type = None
            actual_handler = cast(EventHandler, event_type)
        else:
            actual_event_type = str(event_type)
            ensure_runtime_event_allowed(cast(OwnerType, owner_type), actual_event_type)
            actual_handler = handler
        self._subscriptions.append(
            Subscription(
                instance_id=instance_id,
                owner_type=owner_type,
                owner_id=owner_id,
                event_type=actual_event_type,
                handler=actual_handler,
            )
        )

    def unsubscribe_instance(self, instance_id: str) -> None:
        self._subscriptions = [
            subscription
            for subscription in self._subscriptions
            if subscription.instance_id != instance_id
        ]

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
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            return

    @staticmethod
    def _matches(subscription: Subscription, event: RuntimeEvent) -> bool:
        if subscription.event_type is not None and subscription.event_type != event.type:
            return False
        if subscription.owner_type == "system":
            return True
        if subscription.owner_type == "agent":
            return event.agent_id == subscription.owner_id
        return event.session_id == subscription.owner_id


__all__ = ["RuntimeEventBus"]
