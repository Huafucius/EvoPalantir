import pytest

from aos.control.plane import AOSRuntime
from aos.model.runtime import RuntimeLogEntry


def _write_basic_skills(skill_root) -> None:
    aos_skill_dir = skill_root / "aos"
    aos_skill_dir.mkdir(parents=True)
    (aos_skill_dir / "SKILL.md").write_text(
        "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
    )


@pytest.mark.asyncio
async def test_queries_do_not_write_runtime_log(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)

    await runtime.call("skill.list")

    entries = await runtime.store.list_runtime_log(RuntimeLogEntry)
    assert entries == []


@pytest.mark.asyncio
async def test_commands_do_write_runtime_log(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)

    await runtime.call("agent.create", display_name="Ada")

    entries = await runtime.store.list_runtime_log(RuntimeLogEntry)
    assert [entry.op for entry in entries] == ["agent.create"]


@pytest.mark.asyncio
async def test_catalog_preview_query_bypasses_admission_hooks(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)
    called = False

    async def deny_preview(input_data: dict, output_data: dict) -> None:
        nonlocal called
        called = True
        raise RuntimeError("should not run")

    runtime.admission_hooks.register(
        "system-1", "system", None, {"skill.discovery.before": deny_preview}
    )

    preview = await runtime.call("skill.catalog.preview", ownerType="system")

    assert {item["name"] for item in preview} == {"aos"}
    assert called is False


@pytest.mark.asyncio
async def test_catalog_refresh_command_runs_discovery_admission_hook(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)

    async def narrow_catalog(input_data: dict, output_data: dict) -> None:
        output_data["query"] = {"names": ["aos"]}

    runtime.admission_hooks.register(
        "system-1", "system", None, {"skill.discovery.before": narrow_catalog}
    )

    refreshed = await runtime.call("skill.catalog.refresh", ownerType="system")

    assert {item["name"] for item in refreshed} == {"aos"}
