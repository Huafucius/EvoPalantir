from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

SCHEMA_VERSION = "aos/v0.81"


def now_rfc3339() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


@dataclass(slots=True)
class SkillDefaultRule:
    name: str
    load: str | None = None
    start: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AOSCB:
    schemaVersion: str
    name: str
    skillRoot: str
    revision: int
    createdAt: str
    updatedAt: str
    defaultSkills: list[dict[str, Any]] = field(default_factory=list)
    permissions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ACB:
    agentId: str
    status: str
    displayName: str | None
    revision: int
    createdBy: str
    createdAt: str
    updatedAt: str
    archivedAt: str | None = None
    defaultSkills: list[dict[str, Any]] = field(default_factory=list)
    permissions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SCB:
    sessionId: str
    agentId: str
    status: str
    title: str | None
    revision: int
    createdBy: str
    createdAt: str
    updatedAt: str
    archivedAt: str | None = None
    defaultSkills: list[dict[str, Any]] = field(default_factory=list)
    permissions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_default_skill_rules() -> list[dict[str, Any]]:
    return [
        SkillDefaultRule(name="aos", load="enable", start="disable").to_dict(),
        SkillDefaultRule(name="docs-rag", load="enable", start="disable").to_dict(),
        SkillDefaultRule(name="bash-safe", load="enable", start="enable").to_dict(),
    ]


def make_aoscb(name: str, skill_root: str) -> AOSCB:
    now = now_rfc3339()
    return AOSCB(
        schemaVersion=SCHEMA_VERSION,
        name=name,
        skillRoot=skill_root,
        revision=1,
        createdAt=now,
        updatedAt=now,
        defaultSkills=make_default_skill_rules(),
        permissions={},
    )


def make_agent(display_name: str | None, created_by: str = "human") -> ACB:
    now = now_rfc3339()
    return ACB(
        agentId=new_id("agent"),
        status="active",
        displayName=display_name,
        revision=1,
        createdBy=created_by,
        createdAt=now,
        updatedAt=now,
        defaultSkills=[],
        permissions={},
    )


def make_session(agent_id: str, title: str | None, created_by: str = "human") -> SCB:
    now = now_rfc3339()
    return SCB(
        sessionId=new_id("session"),
        agentId=agent_id,
        status="ready",
        title=title,
        revision=1,
        createdBy=created_by,
        createdAt=now,
        updatedAt=now,
        defaultSkills=[],
        permissions={},
    )


def make_text_message(role: str, text: str, origin: str) -> dict[str, Any]:
    return {
        "id": new_id("msg"),
        "role": role,
        "parts": [
            {
                "id": new_id("part"),
                "type": "text",
                "text": text,
            }
        ],
        "metadata": {
            "createdAt": now_rfc3339(),
            "origin": origin,
        },
    }


SKILL_CATALOG: list[dict[str, str]] = [
    {
        "name": "aos",
        "description": "AOS control plane contract, JSON-only and bash invocation rules.",
    },
    {
        "name": "docs-rag",
        "description": "RAG retrieval guide for AgentOS docs and citation behavior.",
    },
    {
        "name": "bash-safe",
        "description": "Bash safety boundary with minimal tool hooks.",
    },
]
