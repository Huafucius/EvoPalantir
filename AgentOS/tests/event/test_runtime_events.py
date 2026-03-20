from datetime import UTC, datetime

import pytest

from aos.model.runtime import RuntimeEvent


@pytest.mark.asyncio
async def test_runtime_events_are_filtered_by_event_type_and_scope() -> None:
    from aos.event.bus import RuntimeEventBus

    bus = RuntimeEventBus()
    deliveries: list[str] = []

    async def system_handler(event: RuntimeEvent) -> None:
        deliveries.append(f"system:{event.type}")

    async def session_handler(event: RuntimeEvent) -> None:
        deliveries.append(f"session:{event.type}")

    bus.subscribe("system", None, "session.dispatch.after", system_handler)
    bus.subscribe("session", "session-1", "session.dispatch.after", session_handler)

    await bus.publish(
        RuntimeEvent(
            type="session.dispatch.after",
            owner_type="session",
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
            session_id="session-1",
            payload={"dispatchId": "dispatch-1"},
        )
    )
    await bus.drain()

    assert deliveries == ["system:session.dispatch.after", "session:session.dispatch.after"]


@pytest.mark.asyncio
async def test_runtime_events_do_not_deliver_unsubscribed_types() -> None:
    from aos.event.bus import RuntimeEventBus

    bus = RuntimeEventBus()
    deliveries: list[str] = []

    async def handler(event: RuntimeEvent) -> None:
        deliveries.append(event.type)

    bus.subscribe("system", None, "compute.after", handler)

    await bus.publish(
        RuntimeEvent(
            type="session.started",
            owner_type="session",
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
            session_id="session-1",
            payload={},
        )
    )
    await bus.drain()

    assert deliveries == []
