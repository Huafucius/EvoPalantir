from types import SimpleNamespace

import pytest

from aos.compute.react_unit import ReActUnit


@pytest.mark.asyncio
async def test_react_unit_normalizes_text_response() -> None:
    async def fake_call(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="done", tool_calls=None))],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    unit = ReActUnit(model="gpt-4o-mini", provider_call=fake_call)

    result = await unit.complete(messages=[{"role": "user", "content": "hello"}])

    assert result.text == "done"
    assert result.tool_calls == []
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_react_unit_normalizes_bash_tool_calls() -> None:
    async def fake_call(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call-1",
                                function=SimpleNamespace(
                                    name="bash",
                                    arguments='{"command":"pwd","cwd":"/tmp"}',
                                ),
                            )
                        ],
                    )
                )
            ],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    unit = ReActUnit(model="gpt-4o-mini", provider_call=fake_call)

    result = await unit.complete(messages=[{"role": "user", "content": "hello"}])

    assert result.text is None
    assert result.tool_calls[0].function.name == "bash"
    assert result.tool_calls[0].function.arguments["command"] == "pwd"
