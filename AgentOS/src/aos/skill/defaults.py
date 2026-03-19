from __future__ import annotations

from collections import OrderedDict

from aos.model.control_block import AgentControlBlock, AOSControlBlock, SessionControlBlock


def resolve_default_skill_names(
    aos_cb: AOSControlBlock,
    agent_cb: AgentControlBlock | None,
    session_cb: SessionControlBlock | None,
    *,
    mode: str,
) -> list[str]:
    resolved: OrderedDict[str, str] = OrderedDict()

    for control_block in (aos_cb, agent_cb, session_cb):
        if control_block is None:
            continue
        for rule in control_block.default_skills:
            action = getattr(rule, mode)
            if action is None:
                continue
            resolved[rule.name] = action

    names = [name for name, action in resolved.items() if action == "enable"]
    if mode == "load":
        return ["aos", *[name for name in names if name != "aos"]]
    return names


__all__ = ["resolve_default_skill_names"]
