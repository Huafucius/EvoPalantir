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


@pytest.mark.asyncio
async def test_archived_agent_and_session_reject_mutating_commands(tmp_path) -> None:
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
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Test")

    await runtime.call("agent.archive", agentId=agent["agentId"])
    await runtime.call("session.archive", sessionId=session["sessionId"])

    with pytest.raises(ValueError, match="agent.archived"):
        await runtime.call("session.create", agentId=agent["agentId"], title="Nope")

    with pytest.raises(ValueError, match="agent.archived"):
        await runtime.call(
            "agent.update", agentId=agent["agentId"], fields={"displayName": "Still Ada"}
        )

    with pytest.raises(ValueError, match="agent.archived"):
        await runtime.call(
            "skill.default.set",
            ownerType="agent",
            ownerId=agent["agentId"],
            entry={"name": "memory", "load": "enable"},
        )

    with pytest.raises(ValueError, match="agent.archived"):
        await runtime.call(
            "resource.start",
            ownerType="agent",
            ownerId=agent["agentId"],
            spec={"kind": "worker"},
        )

    with pytest.raises(ValueError, match="session.archived"):
        await runtime.call(
            "session.append",
            sessionId=session["sessionId"],
            message={
                "role": "user",
                "parts": [{"type": "text", "text": "hello"}],
                "metadata": {"seq": 999, "origin": "human"},
            },
        )

    with pytest.raises(ValueError, match="session.archived"):
        await runtime.run_session(session["sessionId"])
