from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from aos.model.common import (
    AgentStatus,
    AOSModel,
    CreatedBy,
    DefaultSkillAction,
    SessionPhase,
    SessionStatus,
)


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
    schema_version: Literal["aos/v0.9"]
    name: str
    skill_root: str
    revision: int
    created_at: datetime
    updated_at: datetime
    default_skills: list[SkillDefaultRule] = Field(default_factory=list)
    permissions: dict[str, Any] | None = None
    auto_fold_threshold: int | None = None


class AgentControlBlock(AOSModel):
    schema_version: Literal["aos/v0.9"] = "aos/v0.9"
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
    auto_fold_threshold: int | None = None

    @model_validator(mode="after")
    def validate_archive_state(self) -> "AgentControlBlock":
        if self.status == "archived" and self.archived_at is None:
            raise ValueError("archived agents must define archived_at")
        if self.status != "archived" and self.archived_at is not None:
            raise ValueError("active agents must not define archived_at")
        return self


class SessionControlBlock(AOSModel):
    schema_version: Literal["aos/v0.9"] = "aos/v0.9"
    session_id: str
    agent_id: str
    status: SessionStatus
    phase: SessionPhase
    lease_id: str | None = None
    lease_holder: str | None = None
    lease_expires_at: datetime | None = None
    title: str | None = None
    revision: int
    created_by: CreatedBy
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    default_skills: list[SkillDefaultRule] = Field(default_factory=list)
    permissions: dict[str, Any] | None = None
    auto_fold_threshold: int | None = None

    @model_validator(mode="after")
    def validate_archive_state(self) -> "SessionControlBlock":
        if self.status == "archived" and self.archived_at is None:
            raise ValueError("archived sessions must define archived_at")
        if self.status != "archived" and self.archived_at is not None:
            raise ValueError("active sessions must not define archived_at")
        lease_fields = [self.lease_id, self.lease_holder, self.lease_expires_at]
        has_any_lease = any(value is not None for value in lease_fields)
        has_all_lease = all(value is not None for value in lease_fields)
        if self.phase == "dispatched" and not has_all_lease:
            raise ValueError("dispatched sessions must define full lease fields")
        if self.phase != "dispatched" and has_any_lease:
            raise ValueError("non-dispatched sessions must not define lease fields")
        return self


__all__ = [
    "AOSControlBlock",
    "AgentControlBlock",
    "SessionControlBlock",
    "SkillDefaultRule",
]
