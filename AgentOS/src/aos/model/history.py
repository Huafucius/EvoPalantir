from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field

from aos.model.common import AOSModel, OwnerType


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class TextPart(AOSModel):
    id: str = Field(default_factory=lambda: _id("part"))
    type: Literal["text"] = "text"
    text: str


class ToolBashInput(AOSModel):
    command: str
    cwd: str | None = None
    timeout_ms: int | None = None


class ToolBashOutput(AOSModel):
    visible_result: str | None = None
    content_id: str | None = None
    size_chars: int | None = None
    line_count: int | None = None
    preview: str | None = None


class ToolBashPart(AOSModel):
    id: str = Field(default_factory=lambda: _id("part"))
    type: Literal["tool-bash"] = "tool-bash"
    tool_call_id: str
    state: Literal["input-streaming", "input-available", "output-available", "output-error"]
    input: ToolBashInput
    output: ToolBashOutput | None = None
    error_text: str | None = None


class SkillLoadData(AOSModel):
    cause: Literal["default", "explicit", "reinject"]
    owner_type: OwnerType
    owner_id: str | None = None
    name: str
    skill_text: str


class SkillLoadPart(AOSModel):
    id: str = Field(default_factory=lambda: _id("part"))
    type: Literal["data-skill-load"] = "data-skill-load"
    data: SkillLoadData


class CompactionData(AOSModel):
    auto: bool
    overflow: bool | None = None
    from_seq: int
    to_seq: int


class CompactionMarkerPart(AOSModel):
    id: str = Field(default_factory=lambda: _id("part"))
    type: Literal["data-compaction"] = "data-compaction"
    data: CompactionData


class InterruptData(AOSModel):
    reason: str
    payload: dict[str, Any] | None = None


class InterruptPart(AOSModel):
    id: str = Field(default_factory=lambda: _id("part"))
    type: Literal["data-interrupt"] = "data-interrupt"
    data: InterruptData


class BootstrapData(AOSModel):
    phase: Literal["begin", "done"]
    reason: str | None = None
    planned_names: list[str] | None = None


class BootstrapPart(AOSModel):
    id: str = Field(default_factory=lambda: _id("part"))
    type: Literal["data-bootstrap"] = "data-bootstrap"
    transient: bool | None = None
    data: BootstrapData


HistoryPart = (
    TextPart | ToolBashPart | SkillLoadPart | CompactionMarkerPart | InterruptPart | BootstrapPart
)


class SessionHistoryMetadata(AOSModel):
    seq: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    origin: Literal["human", "assistant", "aos"]
    parent_id: str | None = None
    summary: bool | None = None
    finish: str | None = None
    error: dict[str, Any] | None = None


class SessionHistoryMessage(AOSModel):
    id: str = Field(default_factory=lambda: _id("msg"))
    role: Literal["system", "user", "assistant"]
    parts: list[HistoryPart]
    metadata: SessionHistoryMetadata

    @classmethod
    def user_text(cls, seq: int, text: str) -> SessionHistoryMessage:
        return cls(
            role="user",
            parts=[TextPart(text=text)],
            metadata=SessionHistoryMetadata(seq=seq, origin="human"),
        )

    @classmethod
    def assistant_text(cls, seq: int, text: str) -> SessionHistoryMessage:
        return cls(
            role="assistant",
            parts=[TextPart(text=text)],
            metadata=SessionHistoryMetadata(seq=seq, origin="assistant"),
        )

    @classmethod
    def tool_bash_result(
        cls,
        seq: int,
        *,
        tool_call_id: str,
        command: str,
        cwd: str | None,
        timeout_ms: int | None,
        visible_result: str | None,
        error_text: str | None = None,
        content_id: str | None = None,
        size_chars: int | None = None,
        line_count: int | None = None,
        preview: str | None = None,
    ) -> SessionHistoryMessage:
        state = "output-error" if error_text is not None else "output-available"
        output = None
        if error_text is None:
            output = ToolBashOutput(
                visible_result=visible_result,
                content_id=content_id,
                size_chars=size_chars,
                line_count=line_count,
                preview=preview,
            )
        return cls(
            role="assistant",
            parts=[
                ToolBashPart(
                    tool_call_id=tool_call_id,
                    state=state,
                    input=ToolBashInput(command=command, cwd=cwd, timeout_ms=timeout_ms),
                    output=output,
                    error_text=error_text,
                )
            ],
            metadata=SessionHistoryMetadata(seq=seq, origin="assistant"),
        )

    @classmethod
    def skill_load(
        cls,
        seq: int,
        *,
        cause: Literal["default", "explicit", "reinject"],
        owner_type: OwnerType,
        owner_id: str | None,
        name: str,
        skill_text: str,
    ) -> SessionHistoryMessage:
        return cls(
            role="user",
            parts=[
                SkillLoadPart(
                    data=SkillLoadData(
                        cause=cause,
                        owner_type=owner_type,
                        owner_id=owner_id,
                        name=name,
                        skill_text=skill_text,
                    )
                )
            ],
            metadata=SessionHistoryMetadata(seq=seq, origin="aos"),
        )

    @classmethod
    def compaction_marker(
        cls,
        seq: int,
        *,
        from_seq: int,
        to_seq: int,
        auto: bool = False,
        overflow: bool | None = None,
    ) -> SessionHistoryMessage:
        return cls(
            role="user",
            parts=[
                CompactionMarkerPart(
                    data=CompactionData(
                        auto=auto, overflow=overflow, from_seq=from_seq, to_seq=to_seq
                    )
                )
            ],
            metadata=SessionHistoryMetadata(seq=seq, origin="aos"),
        )

    @classmethod
    def compaction_summary(cls, seq: int, *, text: str, parent_id: str) -> SessionHistoryMessage:
        return cls(
            role="assistant",
            parts=[TextPart(text=text)],
            metadata=SessionHistoryMetadata(
                seq=seq,
                origin="aos",
                parent_id=parent_id,
                summary=True,
                finish="completed",
            ),
        )

    @classmethod
    def bootstrap_marker(
        cls,
        seq: int,
        *,
        phase: Literal["begin", "done"],
        planned_names: list[str] | None = None,
    ) -> SessionHistoryMessage:
        return cls(
            role="user",
            parts=[BootstrapPart(data=BootstrapData(phase=phase, planned_names=planned_names))],
            metadata=SessionHistoryMetadata(seq=seq, origin="aos"),
        )

    @classmethod
    def interrupt(
        cls, seq: int, *, reason: str, payload: dict[str, Any] | None = None
    ) -> SessionHistoryMessage:
        return cls(
            role="user",
            parts=[InterruptPart(data=InterruptData(reason=reason, payload=payload))],
            metadata=SessionHistoryMetadata(seq=seq, origin="aos"),
        )


__all__ = [
    "BootstrapPart",
    "CompactionMarkerPart",
    "HistoryPart",
    "InterruptPart",
    "SessionHistoryMessage",
    "SessionHistoryMetadata",
    "SkillLoadPart",
    "TextPart",
    "ToolBashInput",
    "ToolBashOutput",
    "ToolBashPart",
]
