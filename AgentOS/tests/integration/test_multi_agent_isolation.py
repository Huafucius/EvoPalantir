import pytest

from aos.control.plane import AOSRuntime
from aos.model.history import SessionHistoryMessage


@pytest.mark.asyncio
async def test_multiple_agents_keep_session_state_isolated(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    aos_skill_dir = skill_root / "aos"
    aos_skill_dir.mkdir(parents=True)
    (aos_skill_dir / "SKILL.md").write_text(
        "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
    )

    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)
    agent_one = await runtime.call("agent.create", display_name="Ada")
    agent_two = await runtime.call("agent.create", display_name="Turing")
    session_one = await runtime.call("session.create", agentId=agent_one["agentId"], title="One")
    session_two = await runtime.call("session.create", agentId=agent_two["agentId"], title="Two")

    await runtime.call(
        "session.append",
        sessionId=session_one["sessionId"],
        message=SessionHistoryMessage.user_text(seq=4, text="agent one").model_dump(
            mode="json", by_alias=True
        ),
    )
    await runtime.call(
        "session.append",
        sessionId=session_two["sessionId"],
        message=SessionHistoryMessage.user_text(seq=4, text="agent two").model_dump(
            mode="json", by_alias=True
        ),
    )

    history_one = await runtime.call("session.history.list", sessionId=session_one["sessionId"])
    await runtime.call("session.history.list", sessionId=session_two["sessionId"])
    sessions_for_one = await runtime.call("session.list", agentId=agent_one["agentId"])
    sessions_for_two = await runtime.call("session.list", agentId=agent_two["agentId"])

    assert any(
        part["type"] == "text" and part["text"] == "agent one"
        for item in history_one["items"]
        for part in item["parts"]
    )
    assert all(
        not (part["type"] == "text" and part["text"] == "agent two")
        for item in history_one["items"]
        for part in item["parts"]
    )
    assert sessions_for_one["items"][0]["agentId"] == agent_one["agentId"]
    assert sessions_for_two["items"][0]["agentId"] == agent_two["agentId"]
