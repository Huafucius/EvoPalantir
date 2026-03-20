from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OwnerType = Literal["system", "agent", "session"]
DispatchDirection = Literal["forward", "reverse"]


@dataclass(frozen=True)
class HookSpec:
    allowed_owners: tuple[OwnerType, ...]
    direction: DispatchDirection


@dataclass(frozen=True)
class EventSpec:
    allowed_owners: tuple[OwnerType, ...]


class HookPermissionError(ValueError):
    pass


def _hook(allowed_owners: tuple[OwnerType, ...], direction: DispatchDirection) -> HookSpec:
    return HookSpec(allowed_owners=allowed_owners, direction=direction)


def _event(allowed_owners: tuple[OwnerType, ...]) -> EventSpec:
    return EventSpec(allowed_owners=allowed_owners)


ADMISSION_HOOK_SPECS: dict[str, HookSpec] = {
    "skill.index.refresh.before": _hook(("system",), "forward"),
    "skill.discovery.before": _hook(("system", "agent", "session"), "forward"),
    "skill.default.resolve.before": _hook(("system", "agent", "session"), "forward"),
    "skill.load.before": _hook(("system", "agent", "session"), "forward"),
    "skill.start.before": _hook(("system", "agent", "session"), "forward"),
    "skill.stop.before": _hook(("system", "agent", "session"), "forward"),
    "session.dispatch.before": _hook(("system", "agent", "session"), "forward"),
    "session.bootstrap.before": _hook(("system", "agent", "session"), "forward"),
    "session.reinject.before": _hook(("system", "agent", "session"), "forward"),
    "session.message.beforeWrite": _hook(("system", "agent", "session"), "forward"),
    "session.compaction.before": _hook(("system", "agent", "session"), "forward"),
    "compute.before": _hook(("system", "agent", "session"), "forward"),
    "tool.before": _hook(("system", "agent", "session"), "forward"),
}


TRANSFORM_HOOK_SPECS: dict[str, HookSpec] = {
    "session.system.transform": _hook(("system", "agent", "session"), "forward"),
    "session.messages.transform": _hook(("system", "agent", "session"), "forward"),
    "compute.params.transform": _hook(("system", "agent", "session"), "forward"),
    "tool.env": _hook(("system", "agent", "session"), "forward"),
    "tool.after": _hook(("system", "agent", "session"), "forward"),
    "session.compaction.transform": _hook(("system", "agent", "session"), "forward"),
}


RUNTIME_EVENT_SPECS: dict[str, EventSpec] = {
    "aos.started": _event(("system",)),
    "aos.stopping": _event(("system",)),
    "skill.index.refresh.after": _event(("system",)),
    "skill.discovery.after": _event(("system", "agent", "session")),
    "skill.default.resolve.after": _event(("system", "agent", "session")),
    "skill.load.after": _event(("system", "agent", "session")),
    "skill.start.after": _event(("system", "agent", "session")),
    "skill.stop.after": _event(("system", "agent", "session")),
    "agent.started": _event(("system", "agent")),
    "agent.archived": _event(("system", "agent")),
    "session.started": _event(("system", "agent", "session")),
    "session.archived": _event(("system", "agent", "session")),
    "session.dispatch.after": _event(("system", "agent", "session")),
    "session.bootstrap.after": _event(("system", "agent", "session")),
    "session.reinject.after": _event(("system", "agent", "session")),
    "session.compaction.after": _event(("system", "agent", "session")),
    "session.error": _event(("system", "agent", "session")),
    "session.interrupted": _event(("system", "agent", "session")),
    "compute.after": _event(("system", "agent", "session")),
    "resource.started": _event(("system", "agent", "session")),
    "resource.stopping": _event(("system", "agent", "session")),
    "resource.error": _event(("system", "agent", "session")),
}


# Compatibility union for legacy code paths still using the old HookEngine.
HOOK_SPECS: dict[str, HookSpec] = {
    **ADMISSION_HOOK_SPECS,
    **TRANSFORM_HOOK_SPECS,
    "aos.started": _hook(("system",), "reverse"),
    "aos.stopping": _hook(("system",), "reverse"),
    "skill.index.refresh.after": _hook(("system",), "reverse"),
    "skill.discovery.after": _hook(("system", "agent", "session"), "reverse"),
    "skill.default.resolve.after": _hook(("system", "agent", "session"), "reverse"),
    "skill.load.after": _hook(("system", "agent", "session"), "reverse"),
    "skill.start.after": _hook(("system", "agent", "session"), "reverse"),
    "skill.stop.after": _hook(("system", "agent", "session"), "reverse"),
    "agent.started": _hook(("system", "agent"), "reverse"),
    "agent.archived": _hook(("system", "agent"), "reverse"),
    "session.started": _hook(("system", "agent", "session"), "reverse"),
    "session.archived": _hook(("system", "agent", "session"), "reverse"),
    "session.bootstrap.after": _hook(("system", "agent", "session"), "reverse"),
    "session.reinject.after": _hook(("system", "agent", "session"), "reverse"),
    "session.compaction.after": _hook(("system", "agent", "session"), "reverse"),
    "session.error": _hook(("system", "agent", "session"), "reverse"),
    "session.interrupted": _hook(("system", "agent", "session"), "reverse"),
    "compute.after": _hook(("system", "agent", "session"), "reverse"),
    "resource.started": _hook(("system", "agent", "session"), "reverse"),
    "resource.stopping": _hook(("system", "agent", "session"), "reverse"),
    "resource.error": _hook(("system", "agent", "session"), "reverse"),
}


def ensure_hook_allowed(owner_type: OwnerType, hook_name: str) -> None:
    spec = HOOK_SPECS.get(hook_name)
    if spec is None:
        raise HookPermissionError(f"unknown hook: {hook_name}")
    if owner_type not in spec.allowed_owners:
        raise HookPermissionError(f"{owner_type} cannot register {hook_name}")


def ensure_admission_hook_allowed(owner_type: OwnerType, hook_name: str) -> None:
    spec = ADMISSION_HOOK_SPECS.get(hook_name)
    if spec is None:
        raise HookPermissionError(f"unknown admission hook: {hook_name}")
    if owner_type not in spec.allowed_owners:
        raise HookPermissionError(f"{owner_type} cannot register {hook_name}")


def ensure_transform_hook_allowed(owner_type: OwnerType, hook_name: str) -> None:
    spec = TRANSFORM_HOOK_SPECS.get(hook_name)
    if spec is None:
        raise HookPermissionError(f"unknown transform hook: {hook_name}")
    if owner_type not in spec.allowed_owners:
        raise HookPermissionError(f"{owner_type} cannot register {hook_name}")


def ensure_runtime_event_allowed(owner_type: OwnerType, event_name: str) -> None:
    spec = RUNTIME_EVENT_SPECS.get(event_name)
    if spec is None:
        raise HookPermissionError(f"unknown runtime event: {event_name}")
    if owner_type not in spec.allowed_owners:
        raise HookPermissionError(f"{owner_type} cannot subscribe to {event_name}")


__all__ = [
    "ADMISSION_HOOK_SPECS",
    "TRANSFORM_HOOK_SPECS",
    "RUNTIME_EVENT_SPECS",
    "HOOK_SPECS",
    "HookPermissionError",
    "HookSpec",
    "EventSpec",
    "OwnerType",
    "ensure_hook_allowed",
    "ensure_admission_hook_allowed",
    "ensure_transform_hook_allowed",
    "ensure_runtime_event_allowed",
]
