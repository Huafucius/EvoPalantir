from typing import Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "aos/v0.81"

AgentStatus = Literal["active", "archived"]
CreatedBy = str
DefaultSkillAction = Literal["enable", "disable"]
OwnerType = Literal["system", "agent", "session"]
SessionStatus = Literal["initializing", "ready", "archived"]


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class AOSModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
    )


__all__ = [
    "AOSModel",
    "AgentStatus",
    "CreatedBy",
    "DefaultSkillAction",
    "OwnerType",
    "SCHEMA_VERSION",
    "SessionStatus",
]
