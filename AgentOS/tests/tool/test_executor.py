import pytest

from aos.hook.engine import HookEngine
from aos.tool.executor import BashToolExecutor


@pytest.mark.asyncio
async def test_executor_returns_raw_and_visible_results() -> None:
    executor = BashToolExecutor(HookEngine())

    result = await executor.execute(
        tool_call_id="call-1",
        args={"command": 'python -c "print(1 + 1)"'},
        owner_ids={"agent_id": "agent-1", "session_id": "session-1"},
    )

    assert result["rawResult"]["stdout"].strip() == "2"
    assert result["visibleResult"].strip() == "2"


@pytest.mark.asyncio
async def test_executor_allows_tool_after_hook_to_rewrite_visible_result() -> None:
    engine = HookEngine()

    async def rewrite_visible_result(input_data: dict, output_data: dict) -> None:
        output_data["result"] = "REWRITTEN"

    engine.register("session-1", "session", "session-1", {"tool.after": rewrite_visible_result})
    executor = BashToolExecutor(engine)

    result = await executor.execute(
        tool_call_id="call-1",
        args={"command": "printf hello"},
        owner_ids={"agent_id": "agent-1", "session_id": "session-1"},
    )

    assert result["visibleResult"] == "REWRITTEN"
