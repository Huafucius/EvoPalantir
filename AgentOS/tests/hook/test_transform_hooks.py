import pytest

from aos.hook.permissions import HookPermissionError


@pytest.mark.asyncio
async def test_transform_hooks_run_in_system_agent_session_order() -> None:
    from aos.hook.transform import TransformHookEngine

    engine = TransformHookEngine()
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
        {"agentId": "agent-1", "sessionId": "session-1", "messages": []},
        {"messages": []},
        agent_id="agent-1",
        session_id="session-1",
    )

    assert order == ["system", "agent", "session"]
    assert output == {"messages": ["system", "agent", "session"]}


def test_transform_registry_rejects_non_transform_hook_names() -> None:
    from aos.hook.transform import TransformHookEngine

    engine = TransformHookEngine()

    async def invalid(input_data: dict, output_data: dict) -> None:
        return None

    with pytest.raises(HookPermissionError):
        engine.register("session-1", "session", "session-1", {"session.started": invalid})
