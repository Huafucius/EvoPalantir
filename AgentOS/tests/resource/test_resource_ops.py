import pytest

from aos.control.plane import AOSRuntime


@pytest.mark.asyncio
async def test_resource_lifecycle_tracks_running_and_stopped_state(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    aos_skill_dir = skill_root / "aos"
    aos_skill_dir.mkdir(parents=True)
    (aos_skill_dir / "SKILL.md").write_text(
        "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
    )

    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)
    resource = await runtime.call(
        "resource.start",
        ownerType="system",
        spec={"kind": "worker", "command": 'python -c "import time; time.sleep(1)"'},
    )
    listed = await runtime.call("resource.list", ownerType="system")
    details = await runtime.call("resource.get", resourceId=resource["resourceId"])
    stopped = await runtime.call("resource.stop", resourceId=resource["resourceId"])

    assert listed[0]["resourceId"] == resource["resourceId"]
    assert details["state"] == "running"
    assert stopped["resourceId"] == resource["resourceId"]
