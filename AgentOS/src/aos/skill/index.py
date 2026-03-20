from __future__ import annotations

from pathlib import Path

import yaml

from aos.model.runtime import SkillManifest


def _parse_skill_file(skill_file: Path) -> SkillManifest:
    raw_text = skill_file.read_text()
    frontmatter: dict[str, object] = {}
    body = raw_text

    if raw_text.startswith("---\n"):
        _, rest = raw_text.split("---\n", 1)
        frontmatter_text, body = rest.split("\n---\n", 1)
        frontmatter = yaml.safe_load(frontmatter_text) or {}

    metadata = frontmatter.get("metadata") if isinstance(frontmatter.get("metadata"), dict) else {}
    plugin = metadata.get("aos-plugin") if isinstance(metadata, dict) else None
    raw_capabilities = metadata.get("aos-capabilities") if isinstance(metadata, dict) else None
    capabilities_declared = raw_capabilities is not None
    capabilities: list[str] = []
    if isinstance(raw_capabilities, list):
        capabilities = [item for item in raw_capabilities if isinstance(item, str)]
    plugin_path: Path | None = None
    if isinstance(plugin, str):
        resolved = (skill_file.parent / plugin).resolve()
        if resolved.is_relative_to(skill_file.parent.resolve()):
            plugin_path = resolved

    return SkillManifest(
        name=str(frontmatter.get("name") or skill_file.parent.name),
        description=str(frontmatter.get("description") or skill_file.parent.name),
        plugin=plugin if isinstance(plugin, str) else None,
        capabilities=capabilities,
        capabilities_declared=capabilities_declared,
        skill_path=skill_file,
        plugin_path=plugin_path,
        skill_text=body.strip(),
    )


def build_skill_index(skill_root: str | Path) -> dict[str, SkillManifest]:
    root = Path(skill_root)
    manifests: dict[str, SkillManifest] = {}
    for skill_file in sorted(root.glob("**/SKILL.md")):
        manifest = _parse_skill_file(skill_file)
        manifests[manifest.name] = manifest
    return manifests


def ensure_builtin_aos_skill(
    skill_root: str | Path, manifests: dict[str, SkillManifest]
) -> dict[str, SkillManifest]:
    if "aos" in manifests:
        return manifests
    root = Path(skill_root)
    synthetic_path = root / "__builtin__" / "aos" / "SKILL.md"
    manifests["aos"] = SkillManifest(
        name="aos",
        description="built-in control skill",
        capabilities=[],
        capabilities_declared=False,
        skill_path=synthetic_path,
        plugin=None,
        plugin_path=None,
        skill_text="# AOS\n\nUse AOSCP to inspect and control the kernel.",
    )
    return manifests


__all__ = ["build_skill_index", "ensure_builtin_aos_skill"]
