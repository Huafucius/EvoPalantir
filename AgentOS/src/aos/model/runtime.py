from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from aos.model.common import AOSModel, OwnerType


class SkillManifest(AOSModel):
    name: str
    description: str
    plugin: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    capabilities_declared: bool = False
    skill_path: Path
    plugin_path: Path | None = None
    skill_text: str


class SkillCatalogItem(AOSModel):
    name: str
    description: str


class RuntimeEvent(AOSModel):
    type: str
    owner_type: OwnerType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_id: str | None = None
    session_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RuntimeLogEntry(AOSModel):
    id: str
    time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    level: Literal["info", "warn", "error"] = "info"
    op: str
    owner_type: OwnerType
    owner_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    refs: dict[str, Any] | None = None
    data: dict[str, Any] | None = None


class PluginInstance(AOSModel):
    instance_id: str
    skill_name: str
    owner_type: OwnerType
    owner_id: str | None = None
    state: Literal["starting", "running", "stopping", "stopped", "error"] = "starting"
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    hooks: list[str] = Field(default_factory=list)
    admission_hooks: list[str] = Field(default_factory=list)
    transform_hooks: list[str] = Field(default_factory=list)
    event_subscriptions: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    last_error: str | None = None


class ManagedResource(AOSModel):
    resource_id: str
    kind: Literal["app", "service", "worker"]
    owner_type: OwnerType
    owner_id: str | None = None
    owner_instance_id: str | None = None
    pid: int | None = None
    state: Literal["starting", "running", "stopping", "stopped", "error"] = "starting"
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    endpoints: list[str] = Field(default_factory=list)
    last_error: str | None = None


__all__ = [
    "ManagedResource",
    "PluginInstance",
    "RuntimeEvent",
    "RuntimeLogEntry",
    "SkillCatalogItem",
    "SkillManifest",
]
