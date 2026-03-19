from datetime import UTC, datetime

import pytest

from aos.hook.engine import HookEngine
from aos.hook.permissions import HookPermissionError


@pytest.mark.asyncio
async def test_transform_hooks_run_in_system_agent_session_order() -> None:
    engine = HookEngine()
    order: list[str] = []

    async def system_hook(input_data: dict, output_data: dict) -> None:
        order.append("system")
        output_data["messages"].append("system")

    async def agent_hook(input_data: dict, output_data: dict) -> None:
        order.append("agent")
        output_data["messages"].append("agent")

    async def session_hook(input_data: dict, output_data: dict) -> None:
        order.append("session")
        output_data["messages"].append("session")

    engine.register("system-1", "system", None, {"session.messages.transform": system_hook})
    engine.register("agent-1", "agent", "agent-1", {"session.messages.transform": agent_hook})
    engine.register(
        "session-1", "session", "session-1", {"session.messages.transform": session_hook}
    )

    output = await engine.dispatch(
        "session.messages.transform",
        {"agentId": "agent-1", "sessionId": "session-1"},
        {"messages": []},
        agent_id="agent-1",
        session_id="session-1",
    )

    assert order == ["system", "agent", "session"]
    assert output == {"messages": ["system", "agent", "session"]}


@pytest.mark.asyncio
async def test_lifecycle_hooks_run_in_session_agent_system_order() -> None:
    engine = HookEngine()
    order: list[str] = []

    async def system_hook(input_data: dict, output_data: dict) -> None:
        order.append("system")

    async def agent_hook(input_data: dict, output_data: dict) -> None:
        order.append("agent")

    async def session_hook(input_data: dict, output_data: dict) -> None:
        order.append("session")

    engine.register("system-1", "system", None, {"session.started": system_hook})
    engine.register("agent-1", "agent", "agent-1", {"session.started": agent_hook})
    engine.register("session-1", "session", "session-1", {"session.started": session_hook})

    await engine.dispatch(
        "session.started",
        {
            "agentId": "agent-1",
            "cause": "test",
            "sessionId": "session-1",
            "timestamp": datetime.now(UTC).isoformat(),
        },
        {},
        agent_id="agent-1",
        session_id="session-1",
    )

    assert order == ["session", "agent", "system"]


def test_register_rejects_out_of_scope_hooks() -> None:
    engine = HookEngine()

    async def invalid_hook(input_data: dict, output_data: dict) -> None:
        return None

    with pytest.raises(HookPermissionError):
        engine.register("session-1", "session", "session-1", {"agent.started": invalid_hook})
