import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos.control.plane import AOSRuntime


def _write_basic_skills(skill_root) -> None:
    aos_skill_dir = skill_root / "aos"
    aos_skill_dir.mkdir(parents=True)
    (aos_skill_dir / "SKILL.md").write_text(
        "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
    )


@pytest.mark.asyncio
async def test_session_dispatch_returns_dispatch_id_immediately(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)

    async def fake_provider(messages):
        await asyncio.sleep(0.05)
        return SimpleNamespace(
            text="done", tool_calls=[], finish_reason="stop", usage={"total_tokens": 1}
        )

    runtime.provider_call = fake_provider

    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Dispatch")

    result = await runtime.call(
        "session.dispatch",
        sessionId=session["sessionId"],
        message={"role": "user", "content": "hello"},
    )

    assert result["dispatchId"]

    current = await runtime.call("session.get", sessionId=session["sessionId"])
    assert current["phase"] == "dispatched"

    await runtime.wait_for_dispatch(result["dispatchId"])

    current = await runtime.call("session.get", sessionId=session["sessionId"])
    assert current["phase"] == "idle"


@pytest.mark.asyncio
async def test_session_dispatch_rejects_when_lease_is_active(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)
    blocker = asyncio.Event()

    async def fake_provider(messages):
        await blocker.wait()
        return SimpleNamespace(
            text="done", tool_calls=[], finish_reason="stop", usage={"total_tokens": 1}
        )

    runtime.provider_call = fake_provider

    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Dispatch")

    first = await runtime.call(
        "session.dispatch",
        sessionId=session["sessionId"],
        message={"role": "user", "content": "hello"},
    )

    with pytest.raises(ValueError, match="session.busy"):
        await runtime.call(
            "session.dispatch",
            sessionId=session["sessionId"],
            message={"role": "user", "content": "again"},
        )

    blocker.set()
    await runtime.wait_for_dispatch(first["dispatchId"])


@pytest.mark.asyncio
async def test_compact_and_archive_reject_when_dispatch_lease_is_active(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)
    blocker = asyncio.Event()

    async def fake_provider(messages):
        await blocker.wait()
        return SimpleNamespace(
            text="done", tool_calls=[], finish_reason="stop", usage={"total_tokens": 1}
        )

    runtime.provider_call = fake_provider

    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Dispatch")

    dispatch = await runtime.call(
        "session.dispatch",
        sessionId=session["sessionId"],
        message={"role": "user", "content": "hello"},
    )

    with pytest.raises(ValueError, match="session.busy"):
        await runtime.call("session.compact", sessionId=session["sessionId"])

    with pytest.raises(ValueError, match="session.busy"):
        await runtime.call("session.context.compact", sessionId=session["sessionId"])

    with pytest.raises(ValueError, match="session.busy"):
        await runtime.call("session.archive", sessionId=session["sessionId"])

    blocker.set()
    await runtime.wait_for_dispatch(dispatch["dispatchId"])


@pytest.mark.asyncio
async def test_expired_dispatch_lease_is_reconciled_before_archive_and_compact(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)

    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Dispatch")

    stored = await runtime._require_session(session["sessionId"])
    stored.phase = "dispatched"
    stored.lease_id = "dispatch-stale"
    stored.lease_holder = "node-1"
    stored.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    stored.revision += 1
    await runtime.store.save_session_control_block(stored.session_id, stored.agent_id, stored)

    compacted = await runtime.call("session.compact", sessionId=session["sessionId"])
    archived = await runtime.call("session.archive", sessionId=session["sessionId"])

    assert compacted["revision"] >= 1
    assert archived["revision"] >= compacted["revision"]
