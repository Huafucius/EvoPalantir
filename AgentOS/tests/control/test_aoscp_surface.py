import pytest

from aos.control.plane import AOSRuntime
from aos.model.control_block import SkillDefaultRule


def _write_basic_skills(skill_root) -> None:
    aos_skill_dir = skill_root / "aos"
    aos_skill_dir.mkdir(parents=True)
    (aos_skill_dir / "SKILL.md").write_text(
        "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
    )

    memory_dir = skill_root / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "SKILL.md").write_text(
        "---\nname: memory\ndescription: memory skill\n---\n\n# Memory\n\nRemember facts.\n"
    )

    plugin_dir = skill_root / "injector"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(
        "async def plugin(ctx):\n"
        "    async def inject(input_data, output_data):\n"
        '        output_data["messages"].append({"role": "system", "content": "plugin-started"})\n'
        '    return {"session.messages.transform": inject}\n'
    )
    (plugin_dir / "SKILL.md").write_text(
        "---\n"
        "name: injector\n"
        "description: plugin skill\n"
        "metadata:\n"
        "  aos-plugin: plugin.py\n"
        "---\n\n"
        "# Injector\n\n"
        "Injects.\n"
    )


@pytest.mark.asyncio
async def test_skill_and_plugin_operations_work_end_to_end(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)

    skills = await runtime.call("skill.list")
    assert {skill["name"] for skill in skills} == {"aos", "injector", "memory"}

    shown = await runtime.call("skill.show", name="injector")
    assert shown["plugin"] == "plugin.py"

    preview = await runtime.call("skill.catalog.preview", ownerType="system")
    refreshed = await runtime.call("skill.catalog.refresh", ownerType="system")
    assert preview == refreshed

    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Skill Ops")
    load_result = await runtime.call("skill.load", name="memory", sessionId=session["sessionId"])
    plugin = await runtime.call(
        "skill.start",
        skillName="injector",
        ownerType="session",
        ownerId=session["sessionId"],
    )
    plugins = await runtime.call("plugin.list", ownerType="session", ownerId=session["sessionId"])
    plugin_details = await runtime.call("plugin.get", instanceId=plugin["instanceId"])

    assert load_result["name"] == "memory"
    assert plugins[0]["instanceId"] == plugin["instanceId"]
    assert plugin_details["hooks"] == ["session.messages.transform"]


@pytest.mark.asyncio
async def test_session_context_defaults_compaction_and_archive_operations(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)

    agent = await runtime.call("agent.create", display_name="Ada")
    updated = await runtime.call(
        "agent.update", agentId=agent["agentId"], fields={"displayName": "Ada Lovelace"}
    )
    default_revision = await runtime.call(
        "skill.default.set",
        ownerType="agent",
        ownerId=agent["agentId"],
        entry=SkillDefaultRule(name="memory", load="enable").model_dump(mode="json", by_alias=True),
    )
    default_list = await runtime.call(
        "skill.default.list", ownerType="agent", ownerId=agent["agentId"]
    )

    session = await runtime.call("session.create", agentId=agent["agentId"], title="Session Ops")
    context_before = await runtime.call("session.context.get", sessionId=session["sessionId"])
    history = await runtime.call("session.history.list", sessionId=session["sessionId"])
    folded = await runtime.call(
        "session.context.fold",
        sessionId=session["sessionId"],
        ref={"historyMessageId": history["items"][1]["id"]},
    )
    context_after_fold = await runtime.call("session.context.get", sessionId=session["sessionId"])
    unfolded = await runtime.call(
        "session.context.unfold",
        sessionId=session["sessionId"],
        ref={"historyMessageId": history["items"][1]["id"]},
    )
    await runtime.call("session.interrupt", sessionId=session["sessionId"], reason="pause")
    compacted = await runtime.call("session.compact", sessionId=session["sessionId"])
    sessions = await runtime.call("session.list", agentId=agent["agentId"])
    archived_session = await runtime.call("session.archive", sessionId=session["sessionId"])
    archived_agent = await runtime.call("agent.archive", agentId=agent["agentId"])

    assert updated["revision"] >= 2
    assert default_revision["revision"] >= 2
    assert [item["name"] for item in default_list] == ["memory"]
    assert context_before["messageCount"] >= 1
    assert folded["contextRevision"] > context_before["contextRevision"]
    assert context_after_fold["foldedRefCount"] == 1
    assert unfolded["contextRevision"] > folded["contextRevision"]
    assert compacted["revision"] > session["revision"]
    assert sessions["items"][0]["sessionId"] == session["sessionId"]
    assert archived_session["revision"] >= compacted["revision"]
    assert archived_agent["revision"] >= 2


@pytest.mark.asyncio
async def test_agent_update_rejects_immutable_fields(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)

    agent = await runtime.call("agent.create", display_name="Ada")

    with pytest.raises(ValueError):
        await runtime.call("agent.update", agentId=agent["agentId"], fields={"agentId": "other"})
