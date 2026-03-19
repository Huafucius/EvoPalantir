import pytest

from aos.control.plane import AOSRuntime


@pytest.mark.asyncio
async def test_plugin_start_registers_hooks_with_context(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    aos_skill_dir = skill_root / "aos"
    aos_skill_dir.mkdir(parents=True)
    (aos_skill_dir / "SKILL.md").write_text(
        "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
    )

    plugin_skill_dir = skill_root / "injector"
    plugin_skill_dir.mkdir(parents=True)
    (plugin_skill_dir / "plugin.py").write_text(
        "async def plugin(ctx):\n"
        "    async def inject(input_data, output_data):\n"
        '        output_data["messages"].append(\n'
        '            {"role": "system", "content": f"plugin:{ctx.skill_name}:{ctx.session_id}"}\n'
        "        )\n"
        '    return {"session.messages.transform": inject}\n'
    )
    (plugin_skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: injector\n"
        "description: inject a system message\n"
        "metadata:\n"
        "  aos-plugin: plugin.py\n"
        "---\n\n"
        "# Injector\n\n"
        "Inject messages.\n"
    )

    runtime = await AOSRuntime.open(
        database_path=tmp_path / "agentos.db",
        skill_root=skill_root,
    )
    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Plugin")

    plugin = await runtime.call(
        "skill.start",
        skillName="injector",
        ownerType="session",
        ownerId=session["sessionId"],
    )
    output = await runtime.hooks.dispatch(
        "session.messages.transform",
        {"agentId": agent["agentId"], "sessionId": session["sessionId"], "messages": []},
        {"messages": []},
        agent_id=agent["agentId"],
        session_id=session["sessionId"],
    )

    assert plugin["hooks"] == ["session.messages.transform"]
    assert output["messages"] == [
        {"role": "system", "content": f"plugin:injector:{session['sessionId']}"}
    ]
