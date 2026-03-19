from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from aos.model.common import AgentStatus, AOSModel, CreatedBy, DefaultSkillAction, SessionStatus


class SkillDefaultRule(AOSModel):
    name: str
    load: DefaultSkillAction | None = None
    start: DefaultSkillAction | None = None

    @model_validator(mode="after")
    def validate_actions(self) -> "SkillDefaultRule":
        if self.load is None and self.start is None:
            raise ValueError("at least one of load or start must be set")
        return self


class AOSControlBlock(AOSModel):
    schema_version: Literal["aos/v0.81"]
    name: str
    skill_root: str
    revision: int
    created_at: datetime
    updated_at: datetime
    default_skills: list[SkillDefaultRule] = Field(default_factory=list)
    permissions: dict[str, Any] | None = None


class AgentControlBlock(AOSModel):
    agent_id: str
    status: AgentStatus
    display_name: str | None = None
    revision: int
    created_by: CreatedBy
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    default_skills: list[SkillDefaultRule] = Field(default_factory=list)
    permissions: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_archive_state(self) -> "AgentControlBlock":
        if self.status == "archived" and self.archived_at is None:
            raise ValueError("archived agents must define archived_at")
        if self.status != "archived" and self.archived_at is not None:
            raise ValueError("active agents must not define archived_at")
        return self


class SessionControlBlock(AOSModel):
    session_id: str
    agent_id: str
    status: SessionStatus
    title: str | None = None
    revision: int
    created_by: CreatedBy
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    default_skills: list[SkillDefaultRule] = Field(default_factory=list)
    permissions: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_archive_state(self) -> "SessionControlBlock":
        if self.status == "archived" and self.archived_at is None:
            raise ValueError("archived sessions must define archived_at")
        if self.status != "archived" and self.archived_at is not None:
            raise ValueError("active sessions must not define archived_at")
        return self


__all__ = [
    "AOSControlBlock",
    "AgentControlBlock",
    "SessionControlBlock",
    "SkillDefaultRule",
]
