from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolCall:
    command: str
    cwd: str | None = None
    timeoutMs: int | None = None


@dataclass(slots=True)
class ReActResult:
    kind: str
    text: str | None = None
    toolCall: ToolCall | None = None


class ReActUnit:
    """Minimal ReAct unit for Sprint-2 feasibility.

    Contract:
    - Input: session history messages
    - Output: final text or bash tool_call
    """

    def step(self, history: list[dict[str, Any]]) -> ReActResult:
        last = history[-1] if history else None
        if last is None:
            return ReActResult(kind="final", text="No input yet.")

        tool_part = self._find_tool_bash_part(last)
        if tool_part is not None:
            result = tool_part.get("output", {}).get("visibleResult", "")
            return ReActResult(kind="final", text=f"Bash command completed.\n{result}")

        text = self._find_text(last)
        if text is None:
            return ReActResult(kind="final", text="Unsupported message format.")

        stripped = text.strip()
        if stripped.startswith("bash:"):
            return ReActResult(kind="tool_call", toolCall=ToolCall(command=stripped[5:].strip()))

        return ReActResult(kind="final", text=f"ACK: {stripped}")

    @staticmethod
    def _find_text(message: dict[str, Any]) -> str | None:
        parts = message.get("parts", [])
        if not isinstance(parts, list):
            return None
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                return str(text) if text is not None else None
        return None

    @staticmethod
    def _find_tool_bash_part(message: dict[str, Any]) -> dict[str, Any] | None:
        parts = message.get("parts", [])
        if not isinstance(parts, list):
            return None
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "tool-bash":
                return part
        return None
