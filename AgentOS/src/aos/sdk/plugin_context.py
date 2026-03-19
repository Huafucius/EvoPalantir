from __future__ import annotations

from dataclasses import dataclass

from aos.sdk.aos_sdk import AosSDK


@dataclass
class PluginContext:
    owner_type: str
    owner_id: str | None
    skill_name: str
    agent_id: str | None
    session_id: str | None
    aos: AosSDK


__all__ = ["PluginContext"]
