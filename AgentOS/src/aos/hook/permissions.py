from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OwnerType = Literal["system", "agent", "session"]
DispatchDirection = Literal["forward", "reverse"]


@dataclass(frozen=True)
class HookSpec:
    allowed_owners: tuple[OwnerType, ...]
    direction: DispatchDirection


class HookPermissionError(ValueError):
    pass


def _spec(allowed_owners: tuple[OwnerType, ...], direction: DispatchDirection) -> HookSpec:
    return HookSpec(allowed_owners=allowed_owners, direction=direction)


HOOK_SPECS: dict[str, HookSpec] = {
    "aos.started": _spec(("system",), "reverse"),
    "aos.stopping": _spec(("system",), "reverse"),
    "skill.index.refresh.before": _spec(("system",), "forward"),
    "skill.index.refresh.after": _spec(("system",), "reverse"),
    "skill.discovery.before": _spec(("system", "agent", "session"), "forward"),
    "skill.discovery.after": _spec(("system", "agent", "session"), "reverse"),
    "skill.default.resolve.before": _spec(("system", "agent", "session"), "forward"),
    "skill.default.resolve.after": _spec(("system", "agent", "session"), "reverse"),
    "skill.load.before": _spec(("system", "agent", "session"), "forward"),
    "skill.load.after": _spec(("system", "agent", "session"), "reverse"),
    "skill.start.before": _spec(("system", "agent", "session"), "forward"),
    "skill.start.after": _spec(("system", "agent", "session"), "reverse"),
    "skill.stop.before": _spec(("system", "agent", "session"), "forward"),
    "skill.stop.after": _spec(("system", "agent", "session"), "reverse"),
    "agent.started": _spec(("system", "agent"), "reverse"),
    "agent.archived": _spec(("system", "agent"), "reverse"),
    "session.started": _spec(("system", "agent", "session"), "reverse"),
    "session.archived": _spec(("system", "agent", "session"), "reverse"),
    "session.bootstrap.before": _spec(("system", "agent", "session"), "forward"),
    "session.bootstrap.after": _spec(("system", "agent", "session"), "reverse"),
    "session.reinject.before": _spec(("system", "agent", "session"), "forward"),
    "session.reinject.after": _spec(("system", "agent", "session"), "reverse"),
    "session.message.beforeWrite": _spec(("system", "agent", "session"), "forward"),
    "session.compaction.before": _spec(("system", "agent", "session"), "forward"),
    "session.compaction.after": _spec(("system", "agent", "session"), "reverse"),
    "session.compaction.transform": _spec(("system", "agent", "session"), "forward"),
    "session.system.transform": _spec(("system", "agent", "session"), "forward"),
    "session.messages.transform": _spec(("system", "agent", "session"), "forward"),
    "session.error": _spec(("system", "agent", "session"), "reverse"),
    "session.interrupted": _spec(("system", "agent", "session"), "reverse"),
    "compute.before": _spec(("system", "agent", "session"), "forward"),
    "compute.after": _spec(("system", "agent", "session"), "reverse"),
    "compute.params.transform": _spec(("system", "agent", "session"), "forward"),
    "tool.before": _spec(("system", "agent", "session"), "forward"),
    "tool.after": _spec(("system", "agent", "session"), "reverse"),
    "tool.env": _spec(("system", "agent", "session"), "forward"),
    "resource.started": _spec(("system", "agent", "session"), "reverse"),
    "resource.stopping": _spec(("system", "agent", "session"), "reverse"),
    "resource.error": _spec(("system", "agent", "session"), "reverse"),
}


def ensure_hook_allowed(owner_type: OwnerType, hook_name: str) -> None:
    spec = HOOK_SPECS.get(hook_name)
    if spec is None:
        raise HookPermissionError(f"unknown hook: {hook_name}")
    if owner_type not in spec.allowed_owners:
        raise HookPermissionError(f"{owner_type} cannot register {hook_name}")


__all__ = ["HOOK_SPECS", "HookPermissionError", "HookSpec", "ensure_hook_allowed"]
