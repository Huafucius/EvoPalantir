import pytest

from aos.skill.index import build_skill_index


def test_build_skill_index_parses_capability_manifest(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    skill_dir = skill_root / "memory"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: memory\n"
        "description: memory management\n"
        "metadata:\n"
        "  aos-plugin: plugin.py\n"
        "  aos-capabilities:\n"
        "    - session.read\n"
        "    - session.write\n"
        "---\n\n"
        "# Memory\n\n"
        "Remember things.\n"
    )

    manifest = build_skill_index(skill_root)["memory"]

    assert manifest.capabilities == ["session.read", "session.write"]


def test_build_skill_index_defaults_capabilities_to_empty_list(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    skill_dir = skill_root / "memory"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: memory\ndescription: memory management\n---\n\n# Memory\n\nRemember things.\n"
    )

    manifest = build_skill_index(skill_root)["memory"]

    assert manifest.capabilities == []


@pytest.mark.asyncio
async def test_plugin_context_sdk_checks_capabilities_before_calling_runtime() -> None:
    from aos.sdk.aos_sdk import AosSDK

    class FakeRuntime:
        def __init__(self) -> None:
            self.calls = []

        async def call(self, op: str, **kwargs):
            self.calls.append((op, kwargs))
            return {"ok": True}

    runtime = FakeRuntime()
    sdk = AosSDK(runtime, allowed_capabilities={"session.read"})

    with pytest.raises(PermissionError):
        await sdk.call("session.append", session_id="s-1", message={})
