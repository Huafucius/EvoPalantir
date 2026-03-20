import pytest

from aos.hook.permissions import HookPermissionError


@pytest.mark.asyncio
async def test_admission_hooks_run_in_system_agent_session_order() -> None:
    from aos.hook.admission import AdmissionHookEngine

    engine = AdmissionHookEngine()
    order: list[str] = []

    async def system_hook(input_data: dict, output_data: dict) -> None:
        order.append("system")

    async def agent_hook(input_data: dict, output_data: dict) -> None:
        order.append("agent")

    async def session_hook(input_data: dict, output_data: dict) -> None:
        order.append("session")

    engine.register("system-1", "system", None, {"session.dispatch.before": system_hook})
    engine.register("agent-1", "agent", "agent-1", {"session.dispatch.before": agent_hook})
    engine.register("session-1", "session", "session-1", {"session.dispatch.before": session_hook})

    await engine.dispatch(
        "session.dispatch.before",
        {"agentId": "agent-1", "sessionId": "session-1", "userMessage": "hello"},
        {},
        agent_id="agent-1",
        session_id="session-1",
    )

    assert order == ["system", "agent", "session"]


@pytest.mark.asyncio
async def test_admission_hooks_can_reject_operation() -> None:
    from aos.hook.admission import AdmissionHookEngine

    engine = AdmissionHookEngine()

    async def deny(input_data: dict, output_data: dict) -> None:
        raise RuntimeError("denied")

    engine.register("system-1", "system", None, {"tool.before": deny})

    with pytest.raises(RuntimeError, match="denied"):
        await engine.dispatch(
            "tool.before", {"toolCallId": "tc-1", "args": {}}, {}, session_id="s-1"
        )


def test_admission_registry_rejects_non_admission_hook_names() -> None:
    from aos.hook.admission import AdmissionHookEngine

    engine = AdmissionHookEngine()

    async def invalid(input_data: dict, output_data: dict) -> None:
        return None

    with pytest.raises(HookPermissionError):
        engine.register("system-1", "system", None, {"session.messages.transform": invalid})
