from datetime import datetime

import pytest
from pydantic import ValidationError

from aos.model.control_block import AOSControlBlock, SessionControlBlock, SkillDefaultRule


def test_aos_control_block_uses_schema_aliases() -> None:
    timestamp = datetime.fromisoformat("2026-03-19T10:00:00+00:00")

    control_block = AOSControlBlock(
        schema_version="aos/v0.9",
        name="local",
        skill_root="/tmp/skills",
        revision=1,
        created_at=timestamp,
        updated_at=timestamp,
        auto_fold_threshold=16384,
    )

    assert control_block.model_dump(mode="json", by_alias=True) == {
        "schemaVersion": "aos/v0.9",
        "name": "local",
        "skillRoot": "/tmp/skills",
        "revision": 1,
        "createdAt": "2026-03-19T10:00:00Z",
        "updatedAt": "2026-03-19T10:00:00Z",
        "defaultSkills": [],
        "permissions": None,
        "autoFoldThreshold": 16384,
    }


def test_skill_default_rule_requires_load_or_start() -> None:
    with pytest.raises(ValidationError):
        SkillDefaultRule(name="memory")


def test_archived_session_requires_archived_at() -> None:
    timestamp = datetime.fromisoformat("2026-03-19T10:00:00+00:00")

    with pytest.raises(ValidationError):
        SessionControlBlock(
            schema_version="aos/v0.9",
            session_id="session-1",
            agent_id="agent-1",
            status="archived",
            phase="idle",
            revision=1,
            created_by="human",
            created_at=timestamp,
            updated_at=timestamp,
        )


def test_dispatched_session_requires_lease_fields() -> None:
    timestamp = datetime.fromisoformat("2026-03-19T10:00:00+00:00")

    with pytest.raises(ValidationError):
        SessionControlBlock(
            schema_version="aos/v0.9",
            session_id="session-1",
            agent_id="agent-1",
            status="ready",
            phase="dispatched",
            revision=1,
            created_by="human",
            created_at=timestamp,
            updated_at=timestamp,
        )


def test_idle_session_must_not_keep_lease_fields() -> None:
    timestamp = datetime.fromisoformat("2026-03-19T10:00:00+00:00")

    with pytest.raises(ValidationError):
        SessionControlBlock(
            schema_version="aos/v0.9",
            session_id="session-1",
            agent_id="agent-1",
            status="ready",
            phase="idle",
            lease_id="lease-1",
            lease_holder="node-1",
            lease_expires_at=timestamp,
            revision=1,
            created_by="human",
            created_at=timestamp,
            updated_at=timestamp,
        )


def test_dispatched_session_uses_lease_aliases() -> None:
    timestamp = datetime.fromisoformat("2026-03-19T10:00:00+00:00")

    control_block = SessionControlBlock(
        schema_version="aos/v0.9",
        session_id="session-1",
        agent_id="agent-1",
        status="ready",
        phase="dispatched",
        lease_id="lease-1",
        lease_holder="node-1",
        lease_expires_at=timestamp,
        revision=1,
        created_by="human",
        created_at=timestamp,
        updated_at=timestamp,
        auto_fold_threshold=8192,
    )

    dumped = control_block.model_dump(mode="json", by_alias=True)

    assert dumped["schemaVersion"] == "aos/v0.9"
    assert dumped["phase"] == "dispatched"
    assert dumped["leaseId"] == "lease-1"
    assert dumped["leaseHolder"] == "node-1"
    assert dumped["leaseExpiresAt"] == "2026-03-19T10:00:00Z"
    assert dumped["autoFoldThreshold"] == 8192
