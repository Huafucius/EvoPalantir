from __future__ import annotations

from typing import Any


class AosSDK:
    def __init__(self, runtime, allowed_capabilities: set[str] | None = None) -> None:
        self._runtime = runtime
        self._allowed_capabilities = allowed_capabilities

    async def call(self, op: str, **kwargs: Any) -> Any:
        self._ensure_allowed(op)
        return await self._runtime.call(op, **kwargs)

    def _ensure_allowed(self, op: str) -> None:
        if self._allowed_capabilities is None:
            return
        required = self._required_capability(op)
        if required is None:
            return
        if required not in self._allowed_capabilities:
            raise PermissionError(f"capability {required} is required for {op}")

    @staticmethod
    def _required_capability(op: str) -> str | None:
        if op in {
            "session.list",
            "session.get",
            "session.history.list",
            "session.history.get",
            "session.context.get",
            "session.context.rebuild",
        }:
            return "session.read"
        if op in {"agent.list", "agent.get"}:
            return "agent.read"
        if op in {
            "session.create",
            "session.dispatch",
            "session.append",
            "session.interrupt",
            "session.compact",
            "session.archive",
            "session.context.fold",
            "session.context.unfold",
            "session.context.compact",
        }:
            return "session.write"
        if op.startswith("resource."):
            return "resource.manage"
        if op.startswith("tool."):
            return "tool.execute"
        return None


__all__ = ["AosSDK"]
