from __future__ import annotations

import json
from typing import Any

from pydantic import Field

from aos.model.common import AOSModel
from aos.model.history import (
    BootstrapPart,
    CompactionMarkerPart,
    InterruptPart,
    SessionHistoryMessage,
    SkillLoadPart,
    TextPart,
    ToolBashPart,
)


class HistoryRef(AOSModel):
    history_message_id: str
    history_part_id: str | None = None


class ContextProvenance(AOSModel):
    source_message_id: str
    source_part_id: str | None = None
    kind: str


class ContextMessage(AOSModel):
    wire: dict[str, Any]
    aos: ContextProvenance


class SessionContext(AOSModel):
    session_id: str
    context_revision: int = 1
    messages: list[ContextMessage]
    folded_refs: list[HistoryRef] = Field(default_factory=list)


def _ref_keys(folded_refs: set[str] | set[HistoryRef]) -> set[str]:
    keys: set[str] = set()
    for ref in folded_refs:
        if isinstance(ref, str):
            keys.add(ref)
            continue
        keys.add(ref.history_message_id)
        if ref.history_part_id is not None:
            keys.add(f"{ref.history_message_id}:{ref.history_part_id}")
    return keys


def _find_materialization_start(history: list[SessionHistoryMessage]) -> int:
    completed_summary_parent_ids = {
        message.metadata.parent_id
        for message in history
        if message.metadata.summary
        and message.metadata.finish == "completed"
        and message.metadata.parent_id
    }

    latest_marker_index = 0
    for index, message in enumerate(history):
        if (
            any(isinstance(part, CompactionMarkerPart) for part in message.parts)
            and message.id in completed_summary_parent_ids
        ):
            latest_marker_index = index
    return latest_marker_index


def materialize_session_context(
    session_id: str,
    history: list[SessionHistoryMessage],
    *,
    folded_refs: set[str] | set[HistoryRef],
    context_revision: int = 1,
) -> SessionContext:
    folded = _ref_keys(folded_refs)
    start_index = _find_materialization_start(history)
    messages: list[ContextMessage] = []

    for message in history[start_index:]:
        if message.id in folded:
            continue
        for part in message.parts:
            part_key = f"{message.id}:{part.id}"
            if part_key in folded:
                continue

            if isinstance(part, BootstrapPart):
                continue
            if isinstance(part, TextPart):
                messages.append(
                    ContextMessage(
                        wire={"role": message.role, "content": part.text},
                        aos=ContextProvenance(
                            source_message_id=message.id,
                            source_part_id=part.id,
                            kind="assistant-output"
                            if message.role == "assistant"
                            else "user-input",
                        ),
                    )
                )
                continue
            if isinstance(part, SkillLoadPart):
                messages.append(
                    ContextMessage(
                        wire={
                            "role": "system",
                            "content": f"[[AOS-SKILL {part.data.name}]]\n{part.data.skill_text}",
                        },
                        aos=ContextProvenance(
                            source_message_id=message.id,
                            source_part_id=part.id,
                            kind="skill-load",
                        ),
                    )
                )
                continue
            if isinstance(part, CompactionMarkerPart):
                messages.append(
                    ContextMessage(
                        wire={"role": "user", "content": "What did we do so far?"},
                        aos=ContextProvenance(
                            source_message_id=message.id,
                            source_part_id=part.id,
                            kind="compaction-marker",
                        ),
                    )
                )
                continue
            if isinstance(part, InterruptPart):
                messages.append(
                    ContextMessage(
                        wire={"role": "system", "content": f"[[AOS-INTERRUPT]] {part.data.reason}"},
                        aos=ContextProvenance(
                            source_message_id=message.id,
                            source_part_id=part.id,
                            kind="interrupt",
                        ),
                    )
                )
                continue
            if isinstance(part, ToolBashPart):
                if part.state not in {"output-available", "output-error"}:
                    continue
                tool_call = {
                    "id": part.tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "arguments": json.dumps(
                            {
                                "command": part.input.command,
                                "cwd": part.input.cwd,
                                "timeoutMs": part.input.timeout_ms,
                            }
                        ),
                    },
                }
                messages.append(
                    ContextMessage(
                        wire={"role": "assistant", "tool_calls": [tool_call]},
                        aos=ContextProvenance(
                            source_message_id=message.id,
                            source_part_id=part.id,
                            kind="tool-bash-call",
                        ),
                    )
                )
                result_text = part.error_text or (part.output.visible_result if part.output else "")
                messages.append(
                    ContextMessage(
                        wire={
                            "role": "tool",
                            "content": result_text,
                            "tool_call_id": part.tool_call_id,
                        },
                        aos=ContextProvenance(
                            source_message_id=message.id,
                            source_part_id=part.id,
                            kind="tool-bash-result",
                        ),
                    )
                )

    return SessionContext(
        session_id=session_id, context_revision=context_revision, messages=messages
    )


__all__ = [
    "ContextMessage",
    "ContextProvenance",
    "HistoryRef",
    "SessionContext",
    "materialize_session_context",
]
