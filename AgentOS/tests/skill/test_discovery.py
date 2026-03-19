from datetime import datetime
from pathlib import Path

from aos.model.control_block import (
    AgentControlBlock,
    AOSControlBlock,
    SessionControlBlock,
    SkillDefaultRule,
)
from aos.skill.defaults import resolve_default_skill_names
from aos.skill.index import build_skill_index


def test_build_skill_index_parses_frontmatter_and_plugin_path(tmp_path: Path) -> None:
    skill_dir = tmp_path / "memory"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    plugin_file = skill_dir / "plugin.py"
    plugin_file.write_text("async def plugin(ctx):\n    return {}\n")
    skill_file.write_text(
        "---\n"
        "name: memory\n"
        "description: Long-term memory\n"
        "metadata:\n"
        "  aos-plugin: plugin.py\n"
        "---\n\n"
        "# Memory\n\n"
        "Remember useful facts.\n"
    )

    index = build_skill_index(tmp_path)

    manifest = index["memory"]
    assert manifest.name == "memory"
    assert manifest.description == "Long-term memory"
    assert manifest.plugin == "plugin.py"
    assert manifest.plugin_path == plugin_file
    assert "Remember useful facts." in manifest.skill_text


def test_default_skill_resolution_overrides_by_scope() -> None:
    timestamp = datetime.fromisoformat("2026-03-19T10:00:00+00:00")

    aos_cb = AOSControlBlock(
        schema_version="aos/v0.81",
        name="local",
        skill_root="/tmp/skills",
        revision=1,
        created_at=timestamp,
        updated_at=timestamp,
        default_skills=[SkillDefaultRule(name="memory", load="enable")],
    )
    agent_cb = AgentControlBlock(
        agent_id="agent-1",
        status="active",
        revision=1,
        created_by="human",
        created_at=timestamp,
        updated_at=timestamp,
        default_skills=[SkillDefaultRule(name="memory", load="disable")],
    )
    session_cb = SessionControlBlock(
        session_id="session-1",
        agent_id="agent-1",
        status="ready",
        revision=1,
        created_by="human",
        created_at=timestamp,
        updated_at=timestamp,
        default_skills=[SkillDefaultRule(name="shell", load="enable")],
    )

    assert resolve_default_skill_names(aos_cb, agent_cb, session_cb, mode="load") == [
        "aos",
        "shell",
    ]
