from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentos.models import SCHEMA_VERSION, new_id, now_rfc3339
from agentos.store import Store

_ORDER = {"system": 0, "agent": 1, "session": 2}


@dataclass(slots=True)
class ToolArgs:
    command: str
    cwd: str | None
    timeoutMs: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "cwd": self.cwd,
            "timeoutMs": self.timeoutMs,
        }


class HookRuntime:
    def __init__(self, store: Store):
        self.store = store

    def ensure_plugin_started(
        self,
        *,
        skill_name: str,
        owner_type: str,
        owner_id: str,
    ) -> dict[str, Any]:
        plugins = self._read_plugins()
        instance_id = f"{owner_type}-{owner_id}-{skill_name}"
        existing = next((it for it in plugins if it.get("instanceId") == instance_id), None)
        if existing is not None:
            return existing

        hooks = self._hooks_for_skill(skill_name)
        plugin = {
            "instanceId": instance_id,
            "skillName": skill_name,
            "ownerType": owner_type,
            "ownerId": owner_id,
            "state": "running",
            "startedAt": now_rfc3339(),
            "hooks": hooks,
        }
        plugins.append(plugin)
        self._write_plugins(plugins)
        return plugin

    def apply_tool_before(self, session: dict[str, Any], args: ToolArgs) -> ToolArgs:
        active = self._active_plugins_for_session(session)
        ordered = sorted(active, key=lambda it: _ORDER.get(str(it.get("ownerType")), 99))
        current = args
        for plugin in ordered:
            if "tool.before" not in self._plugin_hooks(plugin):
                continue
            current = self._run_tool_before(plugin, current)
        return current

    def apply_tool_env(self, session: dict[str, Any], args: ToolArgs) -> dict[str, str]:
        active = self._active_plugins_for_session(session)
        ordered = sorted(active, key=lambda it: _ORDER.get(str(it.get("ownerType")), 99))
        merged: dict[str, str] = {}
        for plugin in ordered:
            if "tool.env" not in self._plugin_hooks(plugin):
                continue
            env_part = self._run_tool_env(plugin, session, args)
            merged.update(env_part)
        return merged

    def apply_tool_after(
        self,
        session: dict[str, Any],
        raw_result: dict[str, Any],
        visible_result: str,
    ) -> str:
        active = self._active_plugins_for_session(session)
        ordered = sorted(
            active, key=lambda it: _ORDER.get(str(it.get("ownerType")), 99), reverse=True
        )
        current = visible_result
        for plugin in ordered:
            if "tool.after" not in self._plugin_hooks(plugin):
                continue
            current = self._run_tool_after(plugin, raw_result, current)
        return current

    def _run_tool_before(self, plugin: dict[str, Any], args: ToolArgs) -> ToolArgs:
        if plugin.get("skillName") != "bash-safe":
            return args
        cmd = args.command.strip()
        blocked_tokens = ["rm -rf /", "shutdown", "reboot", "mkfs"]
        if any(token in cmd for token in blocked_tokens):
            cmd = "printf 'blocked by bash-safe: denied command\n'"
        timeout_ms = max(1, min(args.timeoutMs, 120000))
        return ToolArgs(command=cmd, cwd=args.cwd, timeoutMs=timeout_ms)

    def _run_tool_env(
        self,
        plugin: dict[str, Any],
        session: dict[str, Any],
        _args: ToolArgs,
    ) -> dict[str, str]:
        if plugin.get("skillName") != "bash-safe":
            return {}
        return {
            "AOS_AGENT_ID": str(session["agentId"]),
            "AOS_SESSION_ID": str(session["sessionId"]),
        }

    def _run_tool_after(
        self, plugin: dict[str, Any], raw_result: dict[str, Any], visible_result: str
    ) -> str:
        if plugin.get("skillName") != "bash-safe":
            return visible_result
        text = visible_result.strip()
        if not text:
            stdout = str(raw_result.get("stdout") or "").strip()
            stderr = str(raw_result.get("stderr") or "").strip()
            text = stdout or stderr or "(empty output)"
        return text[:4000]

    def _active_plugins_for_session(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        agent_id = str(session["agentId"])
        session_id = str(session["sessionId"])
        items = self._read_plugins()
        active: list[dict[str, Any]] = []
        for item in items:
            if item.get("state") != "running":
                continue
            owner_type = item.get("ownerType")
            owner_id = str(item.get("ownerId"))
            if owner_type == "system":
                active.append(item)
            elif owner_type == "agent" and owner_id == agent_id:
                active.append(item)
            elif owner_type == "session" and owner_id == session_id:
                active.append(item)
        return active

    def _hooks_for_skill(self, skill_name: str) -> list[str]:
        if skill_name == "bash-safe":
            return ["tool.before", "tool.env", "tool.after"]
        return []

    @staticmethod
    def _plugin_hooks(plugin: dict[str, Any]) -> list[str]:
        hooks = plugin.get("hooks", [])
        if not isinstance(hooks, list):
            return []
        return [str(it) for it in hooks]

    def _plugins_path(self):
        return self.store.runtime_root / "plugins.json"

    def _read_plugins(self) -> list[dict[str, Any]]:
        path = self._plugins_path()
        if not path.exists():
            return []
        data = self.store.read_json(path)
        return list(data.get("items", []))

    def _write_plugins(self, items: list[dict[str, Any]]) -> None:
        self.store.write_json(self._plugins_path(), {"items": items})

    def append_runtime_log(
        self,
        *,
        op: str,
        owner_type: str,
        owner_id: str,
        data: dict[str, Any],
        agent_id: str | None = None,
        session_id: str | None = None,
        refs: dict[str, Any] | None = None,
    ) -> None:
        self.store.append_jsonl(
            self.store.runtime_log_path(),
            {
                "id": new_id("rl"),
                "time": now_rfc3339(),
                "level": "info",
                "op": op,
                "ownerType": owner_type,
                "ownerId": owner_id,
                "agentId": agent_id,
                "sessionId": session_id,
                "refs": refs or {},
                "data": data,
                "schemaVersion": SCHEMA_VERSION,
            },
        )
