from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aos.hook.permissions import HOOK_SPECS, OwnerType, ensure_hook_allowed

HookCallback = Callable[[dict[str, Any], dict[str, Any]], Awaitable[None] | None]


@dataclass
class RegisteredHook:
    instance_id: str
    owner_type: OwnerType
    owner_id: str | None
    callback: HookCallback


class HookEngine:
    def __init__(self) -> None:
        self._registry: dict[str, list[RegisteredHook]] = {name: [] for name in HOOK_SPECS}

    def register(
        self,
        instance_id: str,
        owner_type: OwnerType,
        owner_id: str | None,
        hooks: dict[str, HookCallback],
    ) -> list[str]:
        registered: list[str] = []
        for hook_name, callback in hooks.items():
            ensure_hook_allowed(owner_type, hook_name)
            self._registry.setdefault(hook_name, []).append(
                RegisteredHook(
                    instance_id=instance_id,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    callback=callback,
                )
            )
            registered.append(hook_name)
        return registered

    def unregister_instance(self, instance_id: str) -> None:
        for hook_name, hooks in self._registry.items():
            self._registry[hook_name] = [hook for hook in hooks if hook.instance_id != instance_id]

    async def dispatch(
        self,
        hook_name: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        *,
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        hooks = self._visible_hooks(hook_name, agent_id=agent_id, session_id=session_id)
        spec = HOOK_SPECS[hook_name]
        ordered = sorted(hooks, key=lambda hook: self._order_key(hook.owner_type, spec.direction))

        for hook in ordered:
            result = hook.callback(dict(input_data), output_data)
            if inspect.isawaitable(result):
                await result
        return output_data

    def _visible_hooks(
        self,
        hook_name: str,
        *,
        agent_id: str | None,
        session_id: str | None,
    ) -> list[RegisteredHook]:
        visible: list[RegisteredHook] = []
        for hook in self._registry.get(hook_name, []):
            if hook.owner_type == "system":
                visible.append(hook)
            elif hook.owner_type == "agent" and hook.owner_id == agent_id:
                visible.append(hook)
            elif hook.owner_type == "session" and hook.owner_id == session_id:
                visible.append(hook)
        return visible

    @staticmethod
    def _order_key(owner_type: OwnerType, direction: str) -> int:
        forward = {"system": 0, "agent": 1, "session": 2}
        reverse = {"session": 0, "agent": 1, "system": 2}
        return (forward if direction == "forward" else reverse)[owner_type]


__all__ = ["HookEngine"]
