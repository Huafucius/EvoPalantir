from types import SimpleNamespace

import pytest

from aos.control.plane import AOSRuntime
from aos.model.context import materialize_session_context
from aos.model.history import SessionHistoryMessage


def test_materialize_projects_folded_tool_output_as_placeholder() -> None:
    message = SessionHistoryMessage.tool_bash_result(
        seq=1,
        tool_call_id="call-1",
        command="printf hi",
        cwd=None,
        timeout_ms=None,
        visible_result=None,
        content_id="blob-1",
        size_chars=120,
        line_count=4,
        preview="line 1\nline 2",
    )
    part = message.parts[0]

    context = materialize_session_context(
        "session-1",
        [message],
        folded_refs={f"{message.id}:{part.id}"},
        materialized_paths={"blob-1": "/tmp/runtime/blobs/blob-1"},
    )

    assert context.messages[0].aos.kind == "tool-bash-call"
    assert context.messages[1].aos.kind == "tool-bash-folded"
    assert "[[AOS-FOLDED]]" in context.messages[1].wire["content"]
    assert "file: /tmp/runtime/blobs/blob-1" in context.messages[1].wire["content"]
    assert "size: 120 chars, 4 lines" in context.messages[1].wire["content"]


def test_materialize_unfolded_tool_output_loads_content_from_content_map() -> None:
    message = SessionHistoryMessage.tool_bash_result(
        seq=1,
        tool_call_id="call-1",
        command="printf hi",
        cwd=None,
        timeout_ms=None,
        visible_result=None,
        content_id="blob-1",
        size_chars=120,
        line_count=4,
        preview="line 1\nline 2",
    )

    context = materialize_session_context(
        "session-1",
        [message],
        folded_refs=set(),
        content_map={"blob-1": "full content from store"},
    )

    assert context.messages[1].aos.kind == "tool-bash-result"
    assert context.messages[1].wire["content"] == "full content from store"


def test_materialize_projects_fully_folded_message_as_placeholder() -> None:
    message = SessionHistoryMessage.user_text(seq=1, text="hello")

    context = materialize_session_context(
        "session-1",
        [message],
        folded_refs={message.id},
    )

    assert context.messages[0].aos.kind == "message-folded"
    assert "[[AOS-FOLDED]]" in context.messages[0].wire["content"]
    assert (
        f"unfold: aos session context unfold --ref {message.id}"
        in context.messages[0].wire["content"]
    )


def _write_basic_skills(skill_root) -> None:
    aos_skill_dir = skill_root / "aos"
    aos_skill_dir.mkdir(parents=True)
    (aos_skill_dir / "SKILL.md").write_text(
        "---\nname: aos\ndescription: built-in control skill\n---\n\n# AOS\n\nUse AOSCP.\n"
    )


@pytest.mark.asyncio
async def test_dispatch_auto_folds_large_tool_output_and_unfold_restores_it(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)
    responses = iter(
        [
            SimpleNamespace(
                text=None,
                tool_calls=[
                    SimpleNamespace(
                        id="call-1",
                        function=SimpleNamespace(
                            name="bash",
                            arguments={"command": "python - <<'PY'\nprint('x' * 20000)\nPY"},
                        ),
                    )
                ],
                finish_reason="tool_calls",
                usage={"total_tokens": 1},
            ),
            SimpleNamespace(
                text="done", tool_calls=[], finish_reason="stop", usage={"total_tokens": 1}
            ),
        ]
    )

    async def fake_provider(messages):
        return next(responses)

    runtime.provider_call = fake_provider

    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Fold")

    dispatch = await runtime.call(
        "session.dispatch",
        sessionId=session["sessionId"],
        message={"role": "user", "content": "run a long command"},
    )
    await runtime.wait_for_dispatch(dispatch["dispatchId"])

    context = await runtime.call("session.context.get", sessionId=session["sessionId"])
    history = await runtime.call("session.history.list", sessionId=session["sessionId"])
    tool_message = next(
        item
        for item in history["items"]
        if any(part["type"] == "tool-bash" for part in item["parts"])
    )
    tool_part = next(part for part in tool_message["parts"] if part["type"] == "tool-bash")

    assert context["foldedRefCount"] == 1
    assert tool_part["output"]["contentId"]
    assert tool_part["output"]["visibleResult"] is None

    unfolded = await runtime.call(
        "session.context.unfold",
        sessionId=session["sessionId"],
        ref={"historyMessageId": tool_message["id"], "historyPartId": tool_part["id"]},
    )
    context_after_unfold = await runtime.call("session.context.get", sessionId=session["sessionId"])

    assert unfolded["contextRevision"] > context["contextRevision"]
    assert context_after_unfold["foldedRefCount"] == 0


@pytest.mark.asyncio
async def test_rebuild_restores_auto_fold_from_content_id_history(tmp_path) -> None:
    skill_root = tmp_path / "skills"
    _write_basic_skills(skill_root)
    runtime = await AOSRuntime.open(database_path=tmp_path / "agentos.db", skill_root=skill_root)
    responses = iter(
        [
            SimpleNamespace(
                text=None,
                tool_calls=[
                    SimpleNamespace(
                        id="call-1",
                        function=SimpleNamespace(
                            name="bash",
                            arguments={"command": "python - <<'PY'\nprint('x' * 20000)\nPY"},
                        ),
                    )
                ],
                finish_reason="tool_calls",
                usage={"total_tokens": 1},
            ),
            SimpleNamespace(
                text="done", tool_calls=[], finish_reason="stop", usage={"total_tokens": 1}
            ),
        ]
    )

    async def fake_provider(messages):
        return next(responses)

    runtime.provider_call = fake_provider

    agent = await runtime.call("agent.create", display_name="Ada")
    session = await runtime.call("session.create", agentId=agent["agentId"], title="Fold")

    dispatch = await runtime.call(
        "session.dispatch",
        sessionId=session["sessionId"],
        message={"role": "user", "content": "run a long command"},
    )
    await runtime.wait_for_dispatch(dispatch["dispatchId"])

    runtime.state.folded_refs[session["sessionId"]] = set()
    rebuilt = await runtime.call("session.context.rebuild", sessionId=session["sessionId"])
    context = await runtime.call("session.context.get", sessionId=session["sessionId"])

    assert rebuilt["contextRevision"] == context["contextRevision"]
    assert context["foldedRefCount"] == 1
