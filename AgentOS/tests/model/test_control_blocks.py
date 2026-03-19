from datetime import datetime

import pytest
from pydantic import ValidationError

from aos.model.control_block import AOSControlBlock, SessionControlBlock, SkillDefaultRule


def test_aos_control_block_uses_schema_aliases() -> None:
    timestamp = datetime.fromisoformat("2026-03-19T10:00:00+00:00")

    control_block = AOSControlBlock(
        schema_version="aos/v0.81",
        name="local",
        skill_root="/tmp/skills",
        revision=1,
        created_at=timestamp,
        updated_at=timestamp,
    )

    assert control_block.model_dump(mode="json", by_alias=True) == {
        "schemaVersion": "aos/v0.81",
        "name": "local",
        "skillRoot": "/tmp/skills",
        "revision": 1,
        "createdAt": "2026-03-19T10:00:00Z",
        "updatedAt": "2026-03-19T10:00:00Z",
        "defaultSkills": [],
        "permissions": None,
    }


def test_skill_default_rule_requires_load_or_start() -> None:
    with pytest.raises(ValidationError):
        SkillDefaultRule(name="memory")


def test_archived_session_requires_archived_at() -> None:
    timestamp = datetime.fromisoformat("2026-03-19T10:00:00+00:00")

    with pytest.raises(ValidationError):
        SessionControlBlock(
            session_id="session-1",
            agent_id="agent-1",
            status="archived",
            revision=1,
            created_by="human",
            created_at=timestamp,
            updated_at=timestamp,
        )
