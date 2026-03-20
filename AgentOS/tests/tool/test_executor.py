import pytest

from aos.hook.admission import AdmissionHookEngine
from aos.hook.transform import TransformHookEngine
from aos.tool.executor import BashToolExecutor


@pytest.mark.asyncio
async def test_executor_returns_raw_and_visible_results() -> None:
    executor = BashToolExecutor(AdmissionHookEngine(), TransformHookEngine())

    result = await executor.execute(
        tool_call_id="call-1",
        args={"command": 'python -c "print(1 + 1)"'},
        owner_ids={"agent_id": "agent-1", "session_id": "session-1"},
    )

    assert result["rawResult"]["stdout"].strip() == "2"
    assert result["visibleResult"].strip() == "2"


@pytest.mark.asyncio
async def test_executor_allows_tool_after_hook_to_rewrite_visible_result() -> None:
    transform_hooks = TransformHookEngine()

    async def rewrite_visible_result(input_data: dict, output_data: dict) -> None:
        output_data["result"] = "REWRITTEN"

    transform_hooks.register(
        "session-1", "session", "session-1", {"tool.after": rewrite_visible_result}
    )
    executor = BashToolExecutor(AdmissionHookEngine(), transform_hooks)

    result = await executor.execute(
        tool_call_id="call-1",
        args={"command": "printf hello"},
        owner_ids={"agent_id": "agent-1", "session_id": "session-1"},
    )

    assert result["visibleResult"] == "REWRITTEN"
