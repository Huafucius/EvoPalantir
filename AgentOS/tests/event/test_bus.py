from datetime import UTC, datetime

import pytest

from aos.event.bus import RuntimeEventBus
from aos.model.runtime import RuntimeEvent


@pytest.mark.asyncio
async def test_session_events_are_visible_to_session_agent_and_system() -> None:
    bus = RuntimeEventBus()
    deliveries: list[str] = []

    async def system_handler(event: RuntimeEvent) -> None:
        deliveries.append(f"system:{event.type}")

    async def agent_handler(event: RuntimeEvent) -> None:
        deliveries.append(f"agent:{event.type}")

    async def session_handler(event: RuntimeEvent) -> None:
        deliveries.append(f"session:{event.type}")

    bus.subscribe("system", None, system_handler)
    bus.subscribe("agent", "agent-1", agent_handler)
    bus.subscribe("session", "session-1", session_handler)

    await bus.publish(
        RuntimeEvent(
            type="session.started",
            owner_type="session",
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
            session_id="session-1",
            payload={"cause": "test"},
        )
    )
    await bus.drain()

    assert deliveries == [
        "system:session.started",
        "agent:session.started",
        "session:session.started",
    ]
