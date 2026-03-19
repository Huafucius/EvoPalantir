import pytest

from aos.control.plane import AOSRuntime


@pytest.mark.asyncio
async def test_runtime_can_create_agent_and_bootstrap_session(tmp_path) -> None:
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

    agent_result = await runtime.call("agent.create", display_name="Ada")
    session_result = await runtime.call(
        "session.create", agentId=agent_result["agentId"], title="Test"
    )
    history_result = await runtime.call(
        "session.history.list", sessionId=session_result["sessionId"]
    )

    assert agent_result["status"] == "active"
    assert session_result["status"] == "ready"
    assert any(
        part["type"] == "data-skill-load" and part["data"]["name"] == "aos"
        for message in history_result["items"]
        for part in message["parts"]
    )
