from types import SimpleNamespace

import pytest

from aos.control.plane import AOSRuntime
from aos.model.history import SessionHistoryMessage


@pytest.mark.asyncio
async def test_runtime_session_loop_handles_bash_then_final_answer(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    aos_skill_dir = skill_root / "aos"
    aos_skill_dir.mkdir(parents=True)
    (aos_skill_dir / "SKILL.md").write_text(
        "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
    )

    runtime = await AOSRuntime.open(
        database_path=tmp_path / "agentos.db",
        skill_root=skill_root,
        default_model="gpt-4o-mini",
    )
    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Loop")

    await runtime.call(
        "session.append",
        sessionId=session["sessionId"],
        message=SessionHistoryMessage.user_text(seq=4, text="Say hi").model_dump(
            mode="json", by_alias=True
        ),
    )

    responses = iter(
        [
            SimpleNamespace(
                text=None,
                tool_calls=[
                    SimpleNamespace(
                        id="call-1",
                        function=SimpleNamespace(name="bash", arguments={"command": "printf hi"}),
                    )
                ],
                finish_reason="tool_calls",
                usage={"total_tokens": 1},
            ),
            SimpleNamespace(
                text="done", tool_calls=[], finish_reason="stop", usage={"total_tokens": 1}
            ),
        ]
    )

    async def fake_provider(messages):
        return next(responses)

    await runtime.run_session(session["sessionId"], provider=fake_provider)

    history = await runtime.call("session.history.list", sessionId=session["sessionId"])
    dumped = history["items"]
    assert any(part["type"] == "tool-bash" for item in dumped for part in item["parts"])
    assert any(
        part["type"] == "text" and part["text"] == "done"
        for item in dumped
        for part in item["parts"]
    )
