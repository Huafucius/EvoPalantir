from __future__ import annotations

import asyncio
import importlib.util
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from aos.compute.react_unit import BASH_TOOL_SPEC, ReActUnit
from aos.event.bus import RuntimeEventBus
from aos.hook.engine import HookEngine
from aos.model.context import HistoryRef, SessionContext, materialize_session_context
from aos.model.control_block import (
    AgentControlBlock,
    AOSControlBlock,
    SessionControlBlock,
    SkillDefaultRule,
)
from aos.model.history import SessionHistoryMessage, TextPart
from aos.model.runtime import ManagedResource, PluginInstance, RuntimeEvent, RuntimeLogEntry
from aos.sdk.aos_sdk import AosSDK
from aos.sdk.plugin_context import PluginContext
from aos.skill.defaults import resolve_default_skill_names
from aos.skill.index import build_skill_index, ensure_builtin_aos_skill
from aos.store.sqlite import SQLiteStore
from aos.tool.executor import BashToolExecutor


@dataclass
class RuntimeState:
    contexts: dict[str, SessionContext] = field(default_factory=dict)
    folded_refs: dict[str, set[str]] = field(default_factory=dict)
    catalogs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    plugins: dict[str, PluginInstance] = field(default_factory=dict)
    plugin_hooks: dict[str, list[str]] = field(default_factory=dict)
    resources: dict[str, ManagedResource] = field(default_factory=dict)
    resource_processes: dict[str, Any] = field(default_factory=dict)


class AOSRuntime:
    def __init__(self, store: SQLiteStore, skill_root: Path, default_model: str) -> None:
        self.store = store
        self.skill_root = skill_root
        self.default_model = default_model
        self.hooks = HookEngine()
        self.events = RuntimeEventBus()
        self.state = RuntimeState()
        self.skill_index = ensure_builtin_aos_skill(skill_root, build_skill_index(skill_root))
        self.aos_cb: AOSControlBlock | None = None

    @classmethod
    async def open(
        cls,
        *,
        database_path: str | Path,
        skill_root: str | Path,
        default_model: str = "gpt-4o-mini",
    ) -> AOSRuntime:
        store = SQLiteStore(database_path)
        await store.initialize()
        runtime = cls(store=store, skill_root=Path(skill_root), default_model=default_model)
        await runtime._ensure_aos_control_block()
        await runtime._reconcile_default_starts("system", None)
        await runtime.hooks.dispatch(
            "aos.started",
            {
                "cause": "open",
                "timestamp": datetime.now(UTC).isoformat(),
                "catalogSize": len(runtime.skill_index),
            },
            {},
        )
        return runtime

    async def call(self, op: str, **kwargs: Any) -> Any:
        args = {self._to_snake(key): value for key, value in kwargs.items()}
        handler = getattr(self, f"_op_{op.replace('.', '_')}", None)
        if handler is None:
            raise ValueError(f"unsupported op: {op}")
        result = await handler(**args)
        await self._log(
            op,
            owner_type=self._infer_owner_type(op, args),
            owner_id=self._infer_owner_id(args),
            agent_id=args.get("agent_id"),
            session_id=args.get("session_id"),
        )
        return result

    async def _op_skill_list(self) -> list[dict[str, Any]]:
        return [self._catalog_item(manifest) for manifest in self.skill_index.values()]

    async def _op_skill_show(self, name: str) -> dict[str, Any]:
        return self.skill_index[name].model_dump(mode="json", by_alias=True)

    async def _op_skill_load(
        self,
        name: str,
        session_id: str,
        cause: Literal["default", "explicit", "reinject"] = "explicit",
    ) -> dict[str, Any]:
        session_cb = await self._require_session(session_id)
        manifest = self.skill_index[name]
        await self._append_skill_load(
            session_cb,
            name=name,
            skill_text=manifest.skill_text,
            cause=cause,
        )
        return {"name": name, "skillText": manifest.skill_text}

    async def _op_skill_start(
        self,
        skill_name: str,
        owner_type: Literal["system", "agent", "session"],
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        manifest = self.skill_index[skill_name]
        instance_id = f"{owner_type}:{owner_id or 'system'}:{skill_name}"
        await self.hooks.dispatch(
            "skill.start.before",
            {"skillName": skill_name, "ownerType": owner_type, "ownerId": owner_id},
            {},
            agent_id=owner_id if owner_type == "agent" else None,
            session_id=owner_id if owner_type == "session" else None,
        )
        plugin = PluginInstance(
            instance_id=instance_id,
            skill_name=skill_name,
            owner_type=owner_type,
            owner_id=owner_id,
            state="running",
        )
        hooks: dict[str, Any] = {}
        if manifest.plugin_path is not None and manifest.plugin_path.exists():
            module = self._load_module(manifest.plugin_path)
            plugin_factory = getattr(module, "plugin", None)
            if plugin_factory is not None:
                agent_id = None
                session_id = None
                if owner_type == "agent":
                    agent_id = owner_id
                if owner_type == "session":
                    assert owner_id is not None
                    session_id = owner_id
                    session = await self._require_session(owner_id)
                    agent_id = session.agent_id
                plugin_context = PluginContext(
                    owner_type=owner_type,
                    owner_id=owner_id,
                    skill_name=skill_name,
                    agent_id=agent_id,
                    session_id=session_id,
                    aos=AosSDK(self),
                )
                result = plugin_factory(plugin_context)
                hooks = await result if hasattr(result, "__await__") else result
                if hooks:
                    registered = self.hooks.register(instance_id, owner_type, owner_id, hooks)
                    plugin.hooks = registered
                    self.state.plugin_hooks[instance_id] = registered
        self.state.plugins[instance_id] = plugin
        await self.hooks.dispatch(
            "skill.start.after",
            {"instanceId": instance_id, "skillName": skill_name},
            {},
            agent_id=plugin.owner_id if plugin.owner_type == "agent" else None,
            session_id=plugin.owner_id if plugin.owner_type == "session" else None,
        )
        return plugin.model_dump(mode="json", by_alias=True)

    async def _op_skill_stop(self, instance_id: str) -> dict[str, Any]:
        plugin = self.state.plugins[instance_id]
        await self.hooks.dispatch(
            "skill.stop.before",
            {"instanceId": instance_id},
            {},
            agent_id=plugin.owner_id if plugin.owner_type == "agent" else None,
            session_id=plugin.owner_id if plugin.owner_type == "session" else None,
        )
        self.hooks.unregister_instance(instance_id)
        plugin.state = "stopped"
        await self.hooks.dispatch(
            "skill.stop.after",
            {"instanceId": instance_id},
            {},
            agent_id=plugin.owner_id if plugin.owner_type == "agent" else None,
            session_id=plugin.owner_id if plugin.owner_type == "session" else None,
        )
        return {"instanceId": instance_id}

    async def _op_skill_default_list(
        self, owner_type: str, owner_id: str | None = None
    ) -> list[dict[str, Any]]:
        control_block = await self._get_owner_control_block(owner_type, owner_id)
        return [
            rule.model_dump(mode="json", by_alias=True) for rule in control_block.default_skills
        ]

    async def _op_skill_default_set(
        self, owner_type: str, owner_id: str | None = None, entry: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if entry is None:
            raise ValueError("entry is required")
        control_block = await self._get_owner_control_block(owner_type, owner_id)
        rule = SkillDefaultRule.model_validate(entry)
        rules = [
            existing for existing in control_block.default_skills if existing.name != rule.name
        ]
        rules.append(rule)
        control_block.default_skills = rules
        await self._save_owner_control_block(owner_type, control_block)
        await self._reconcile_default_starts(owner_type, owner_id)
        return {"revision": control_block.revision}

    async def _op_skill_default_unset(
        self, owner_type: str, owner_id: str | None = None, name: str | None = None
    ) -> dict[str, Any]:
        if name is None:
            raise ValueError("name is required")
        control_block = await self._get_owner_control_block(owner_type, owner_id)
        control_block.default_skills = [
            rule for rule in control_block.default_skills if rule.name != name
        ]
        await self._save_owner_control_block(owner_type, control_block)
        await self._reconcile_default_starts(owner_type, owner_id)
        return {"revision": control_block.revision}

    async def _op_skill_catalog_refresh(
        self, owner_type: str, owner_id: str | None = None, query: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        await self.hooks.dispatch(
            "skill.index.refresh.before", {"skillRoot": str(self.skill_root)}, {}
        )
        self.skill_index = ensure_builtin_aos_skill(
            self.skill_root, build_skill_index(self.skill_root)
        )
        await self.hooks.dispatch(
            "skill.index.refresh.after", {"indexedCount": len(self.skill_index)}, {}
        )
        catalog = await self._op_skill_catalog_preview(
            owner_type=owner_type, owner_id=owner_id, query=query
        )
        cache_key = f"{owner_type}:{owner_id or 'system'}"
        self.state.catalogs[cache_key] = catalog
        return catalog

    async def _op_skill_catalog_preview(
        self,
        owner_type: str,
        owner_id: str | None = None,
        query: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        discovery_output = await self.hooks.dispatch(
            "skill.discovery.before",
            {"ownerType": owner_type, "ownerId": owner_id, "query": query or {}},
            {"query": query or {}},
            agent_id=owner_id if owner_type == "agent" else None,
            session_id=owner_id if owner_type == "session" else None,
        )
        manifests = list(self.skill_index.values())
        effective_query = discovery_output["query"]
        if effective_query and effective_query.get("names"):
            allowed = set(effective_query["names"])
            manifests = [manifest for manifest in manifests if manifest.name in allowed]
        items = [self._catalog_item(manifest) for manifest in manifests]
        items = items[:limit] if limit is not None else items
        await self.hooks.dispatch(
            "skill.discovery.after",
            {"ownerType": owner_type, "ownerId": owner_id, "catalog": items},
            {},
            agent_id=owner_id if owner_type == "agent" else None,
            session_id=owner_id if owner_type == "session" else None,
        )
        return items

    async def _op_agent_list(self) -> list[dict[str, Any]]:
        agents = await self.store.list_agent_control_blocks(AgentControlBlock)
        return [agent.model_dump(mode="json", by_alias=True) for agent in agents]

    async def _op_agent_create(self, display_name: str | None = None) -> dict[str, Any]:
        now = datetime.now(UTC)
        agent = AgentControlBlock(
            agent_id=self._new_id("agent"),
            status="active",
            display_name=display_name,
            revision=1,
            created_by="human",
            created_at=now,
            updated_at=now,
        )
        await self.store.save_agent_control_block(agent.agent_id, agent)
        await self._reconcile_default_starts("agent", agent.agent_id)
        await self._log(
            "agent.create", owner_type="agent", owner_id=agent.agent_id, agent_id=agent.agent_id
        )
        await self.events.publish(
            RuntimeEvent(
                type="agent.started",
                owner_type="agent",
                agent_id=agent.agent_id,
                payload={"cause": "create"},
            )
        )
        await self.hooks.dispatch(
            "agent.started",
            {"agentId": agent.agent_id, "cause": "create", "timestamp": now.isoformat()},
            {},
            agent_id=agent.agent_id,
        )
        return agent.model_dump(mode="json", by_alias=True)

    async def _op_agent_get(self, agent_id: str) -> dict[str, Any]:
        return (await self._require_agent(agent_id)).model_dump(mode="json", by_alias=True)

    async def _op_agent_update(self, agent_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        agent = await self._require_agent(agent_id)
        mutable_fields = {"display_name", "default_skills", "permissions"}
        updates = {self._to_snake(key): value for key, value in fields.items()}
        unknown = set(updates) - mutable_fields
        if unknown:
            raise ValueError(f"immutable or unknown agent fields: {sorted(unknown)}")

        payload = agent.model_dump(mode="json", by_alias=False)
        payload.update(updates)
        payload["revision"] = agent.revision + 1
        payload["updated_at"] = datetime.now(UTC)
        validated = AgentControlBlock.model_validate(payload)
        await self.store.save_agent_control_block(validated.agent_id, validated)
        await self._log("agent.update", owner_type="agent", owner_id=agent_id, agent_id=agent_id)
        return {"revision": validated.revision}

    async def _op_agent_archive(self, agent_id: str) -> dict[str, Any]:
        agent = await self._require_agent(agent_id)
        agent.status = "archived"
        agent.archived_at = datetime.now(UTC)
        agent.revision += 1
        agent.updated_at = datetime.now(UTC)
        await self.store.save_agent_control_block(agent.agent_id, agent)
        await self._stop_owned_plugins("agent", agent_id)
        await self._stop_owned_resources("agent", agent_id)
        await self._log("agent.archive", owner_type="agent", owner_id=agent_id, agent_id=agent_id)
        await self.events.publish(
            RuntimeEvent(type="agent.archived", owner_type="agent", agent_id=agent_id)
        )
        await self.hooks.dispatch(
            "agent.archived",
            {"agentId": agent_id, "timestamp": agent.archived_at.isoformat()},
            {},
            agent_id=agent_id,
        )
        return {"revision": agent.revision}

    async def _op_session_list(
        self, agent_id: str | None = None, cursor: int | None = None, limit: int = 100
    ) -> dict[str, Any]:
        sessions = await self.store.list_session_control_blocks(
            SessionControlBlock, agent_id=agent_id
        )
        if cursor is not None:
            sessions = sessions[cursor : cursor + limit]
        else:
            sessions = sessions[:limit]
        next_cursor = None if len(sessions) < limit else (cursor or 0) + len(sessions)
        return {
            "items": [item.model_dump(mode="json", by_alias=True) for item in sessions],
            "nextCursor": next_cursor,
        }

    async def _op_session_create(self, agent_id: str, title: str | None = None) -> dict[str, Any]:
        await self._require_agent(agent_id)
        now = datetime.now(UTC)
        session = SessionControlBlock(
            session_id=self._new_id("session"),
            agent_id=agent_id,
            status="initializing",
            title=title,
            revision=1,
            created_by="human",
            created_at=now,
            updated_at=now,
        )
        await self.store.save_session_control_block(session.session_id, session.agent_id, session)
        await self._reconcile_default_starts("session", session.session_id)
        await self._bootstrap_session(session)
        stored = await self._require_session(session.session_id)
        return stored.model_dump(mode="json", by_alias=True)

    async def _op_session_get(self, session_id: str) -> dict[str, Any]:
        return (await self._require_session(session_id)).model_dump(mode="json", by_alias=True)

    async def _op_session_append(self, session_id: str, message: dict[str, Any]) -> dict[str, Any]:
        session = await self._require_session(session_id)
        history_message = SessionHistoryMessage.model_validate(message)
        history_message.metadata.seq = await self._next_seq(session_id)
        await self._append_history_message(session, history_message)
        return {"revision": session.revision}

    async def _op_session_interrupt(
        self, session_id: str, reason: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        session = await self._require_session(session_id)
        seq = await self._next_seq(session_id)
        await self._append_history_message(
            session, SessionHistoryMessage.interrupt(seq, reason=reason, payload=payload)
        )
        await self.events.publish(
            RuntimeEvent(
                type="session.interrupted",
                owner_type="session",
                agent_id=session.agent_id,
                session_id=session.session_id,
                payload={"reason": reason},
            )
        )
        await self.hooks.dispatch(
            "session.interrupted",
            {"reason": reason},
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        return {"revision": session.revision}

    async def _op_session_compact(self, session_id: str) -> dict[str, Any]:
        await self._compact_session(session_id)
        session = await self._require_session(session_id)
        return {"revision": session.revision}

    async def _op_session_archive(self, session_id: str) -> dict[str, Any]:
        session = await self._require_session(session_id)
        session.status = "archived"
        session.archived_at = datetime.now(UTC)
        session.updated_at = datetime.now(UTC)
        session.revision += 1
        await self.store.save_session_control_block(session.session_id, session.agent_id, session)
        self.state.contexts.pop(session_id, None)
        self.state.folded_refs.pop(session_id, None)
        await self._stop_owned_plugins("session", session_id)
        await self._stop_owned_resources("session", session_id)
        await self.events.publish(
            RuntimeEvent(
                type="session.archived",
                owner_type="session",
                agent_id=session.agent_id,
                session_id=session.session_id,
            )
        )
        await self.hooks.dispatch(
            "session.archived",
            {
                "agentId": session.agent_id,
                "sessionId": session.session_id,
                "timestamp": session.archived_at.isoformat(),
            },
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        return {"revision": session.revision}

    async def _op_session_history_list(
        self, session_id: str, cursor: int | None = None, limit: int = 100
    ) -> dict[str, Any]:
        items = await self.store.list_session_history(
            session_id, SessionHistoryMessage, cursor=cursor, limit=limit
        )
        next_cursor = None if len(items) < limit else items[-1].metadata.seq
        return {
            "items": [item.model_dump(mode="json", by_alias=True) for item in items],
            "nextCursor": next_cursor,
        }

    async def _op_session_history_get(self, session_id: str, message_id: str) -> dict[str, Any]:
        message = await self.store.get_session_history_message(
            session_id, message_id, SessionHistoryMessage
        )
        if message is None:
            raise KeyError(message_id)
        return message.model_dump(mode="json", by_alias=True)

    async def _op_session_context_get(self, session_id: str) -> dict[str, Any]:
        context = await self._get_or_rebuild_context(session_id)
        return {
            "sessionId": context.session_id,
            "contextRevision": context.context_revision,
            "messageCount": len(context.messages),
            "foldedRefCount": len(self.state.folded_refs.get(session_id, set())),
        }

    async def _op_session_context_fold(
        self, session_id: str, ref: dict[str, Any]
    ) -> dict[str, Any]:
        history_ref = HistoryRef.model_validate(ref)
        key = (
            history_ref.history_message_id
            if history_ref.history_part_id is None
            else f"{history_ref.history_message_id}:{history_ref.history_part_id}"
        )
        self.state.folded_refs.setdefault(session_id, set()).add(key)
        context = await self._rebuild_context(session_id)
        return {"contextRevision": context.context_revision}

    async def _op_session_context_unfold(
        self, session_id: str, ref: dict[str, Any]
    ) -> dict[str, Any]:
        history_ref = HistoryRef.model_validate(ref)
        key = (
            history_ref.history_message_id
            if history_ref.history_part_id is None
            else f"{history_ref.history_message_id}:{history_ref.history_part_id}"
        )
        self.state.folded_refs.setdefault(session_id, set()).discard(key)
        context = await self._rebuild_context(session_id)
        return {"contextRevision": context.context_revision}

    async def _op_session_context_compact(
        self, session_id: str, auto: bool = False
    ) -> dict[str, Any]:
        await self._compact_session(session_id, auto=auto)
        session = await self._require_session(session_id)
        return {"revision": session.revision}

    async def _op_session_context_rebuild(self, session_id: str) -> dict[str, Any]:
        context = await self._rebuild_context(session_id)
        return {"contextRevision": context.context_revision}

    async def _op_plugin_list(
        self, owner_type: str | None = None, owner_id: str | None = None
    ) -> list[dict[str, Any]]:
        plugins = list(self.state.plugins.values())
        if owner_type is not None:
            plugins = [plugin for plugin in plugins if plugin.owner_type == owner_type]
        if owner_id is not None:
            plugins = [plugin for plugin in plugins if plugin.owner_id == owner_id]
        return [plugin.model_dump(mode="json", by_alias=True) for plugin in plugins]

    async def _op_plugin_get(self, instance_id: str) -> dict[str, Any]:
        return self.state.plugins[instance_id].model_dump(mode="json", by_alias=True)

    async def _op_resource_list(
        self, owner_type: str | None = None, owner_id: str | None = None
    ) -> list[dict[str, Any]]:
        resources = await self.store.list_resources(owner_type=owner_type, owner_id=owner_id)
        return [resource.model_dump(mode="json", by_alias=True) for resource in resources]

    async def _op_resource_start(
        self, owner_type: str, owner_id: str | None = None, spec: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        await self._validate_owner_exists(owner_type, owner_id)
        resource_id = self._new_id("resource")
        resource = ManagedResource(
            resource_id=resource_id,
            kind=(spec or {}).get("kind", "worker"),
            owner_type=cast(Literal["system", "agent", "session"], owner_type),
            owner_id=owner_id,
            owner_instance_id=(spec or {}).get("ownerInstanceId"),
            state="running",
        )
        command = (spec or {}).get("command") or (spec or {}).get("entry")
        try:
            if command:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=(spec or {}).get("cwd"),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self.state.resource_processes[resource_id] = process
                resource.pid = process.pid
            self.state.resources[resource_id] = resource
            await self.store.save_resource(resource)
            await self.hooks.dispatch(
                "resource.started",
                {"resourceId": resource_id, "kind": resource.kind, "endpoints": resource.endpoints},
                {},
                agent_id=(await self._resource_agent_id(owner_type, owner_id)),
                session_id=owner_id if owner_type == "session" else None,
            )
            return resource.model_dump(mode="json", by_alias=True)
        except Exception:
            process = self.state.resource_processes.pop(resource_id, None)
            if process is not None and process.returncode is None:
                process.terminate()
                await process.wait()
            self.state.resources.pop(resource_id, None)
            raise

    async def _op_resource_get(self, resource_id: str) -> dict[str, Any]:
        resource = self.state.resources.get(resource_id)
        if resource is None:
            resource = await self.store.get_resource(resource_id)
        if resource is None:
            raise KeyError(resource_id)
        return resource.model_dump(mode="json", by_alias=True)

    async def _op_resource_stop(self, resource_id: str) -> dict[str, Any]:
        resource = self.state.resources.get(resource_id)
        if resource is None:
            resource = await self.store.get_resource(resource_id)
        if resource is None:
            raise KeyError(resource_id)
        await self.hooks.dispatch(
            "resource.stopping",
            {"resourceId": resource.resource_id, "kind": resource.kind},
            {},
            agent_id=(await self._resource_agent_id(resource.owner_type, resource.owner_id)),
            session_id=resource.owner_id if resource.owner_type == "session" else None,
        )
        process = self.state.resource_processes.pop(resource_id, None)
        if process is not None and process.returncode is None:
            process.terminate()
            await process.wait()
        elif resource.pid is not None:
            resource.state = "error"
            resource.last_error = "resource handle is stale; manual cleanup required"
            self.state.resources[resource_id] = resource
            await self.store.save_resource(resource)
            return {"resourceId": resource_id}
        resource.state = "stopped"
        self.state.resources[resource_id] = resource
        await self.store.save_resource(resource)
        return {"resourceId": resource_id}

    async def run_session(self, session_id: str, *, provider=None, max_turns: int = 8) -> None:
        session = await self._require_session(session_id)
        executor = BashToolExecutor(self.hooks)
        unit = ReActUnit(model=self.default_model, provider_call=provider)

        for _ in range(max_turns):
            if await self._session_has_interrupt(session_id):
                return
            context = await self._get_or_rebuild_context(session_id)
            system_output = await self.hooks.dispatch(
                "session.system.transform",
                {"agentId": session.agent_id, "sessionId": session.session_id},
                {"system": None},
                agent_id=session.agent_id,
                session_id=session.session_id,
            )
            messages = [message.wire for message in context.messages]
            if system_output.get("system"):
                messages = [{"role": "system", "content": system_output["system"]}, *messages]
            messages_output = await self.hooks.dispatch(
                "session.messages.transform",
                {
                    "agentId": session.agent_id,
                    "sessionId": session.session_id,
                    "messages": messages,
                },
                {"messages": messages},
                agent_id=session.agent_id,
                session_id=session.session_id,
            )
            params_output = await self.hooks.dispatch(
                "compute.params.transform",
                {
                    "agentId": session.agent_id,
                    "sessionId": session.session_id,
                    "params": {"model": self.default_model},
                },
                {"params": {"model": self.default_model}},
                agent_id=session.agent_id,
                session_id=session.session_id,
            )
            await self.hooks.dispatch(
                "compute.before",
                {
                    "agentId": session.agent_id,
                    "sessionId": session.session_id,
                    "lastSeq": await self.store.get_max_session_seq(session_id),
                },
                {},
                agent_id=session.agent_id,
                session_id=session.session_id,
            )
            unit = ReActUnit(model=params_output["params"]["model"], provider_call=provider)
            result = await unit.complete(
                messages=messages_output["messages"], tools=[BASH_TOOL_SPEC]
            )
            if result.tool_calls:
                for tool_call in result.tool_calls:
                    execution = await executor.execute(
                        tool_call_id=tool_call.id,
                        args=tool_call.function.arguments,
                        owner_ids={"agent_id": session.agent_id, "session_id": session.session_id},
                    )
                    await self._append_history_message(
                        session,
                        SessionHistoryMessage.tool_bash_result(
                            await self._next_seq(session_id),
                            tool_call_id=tool_call.id,
                            command=execution["args"]["command"],
                            cwd=execution["args"]["cwd"],
                            timeout_ms=execution["args"]["timeoutMs"],
                            visible_result=execution["visibleResult"],
                            error_text=None
                            if execution["rawResult"]["exitCode"] == 0
                            else execution["rawResult"]["stderr"],
                        ),
                    )
                    await self._log(
                        "tool.execute",
                        owner_type="session",
                        owner_id=session.session_id,
                        agent_id=session.agent_id,
                        session_id=session.session_id,
                        data=execution["rawResult"],
                    )
                continue
            if result.text is not None:
                await self._append_history_message(
                    session,
                    SessionHistoryMessage.assistant_text(
                        await self._next_seq(session_id), result.text
                    ),
                )
            await self.hooks.dispatch(
                "compute.after",
                {
                    "agentId": session.agent_id,
                    "sessionId": session.session_id,
                    "appendedMessageCount": 1,
                },
                {},
                agent_id=session.agent_id,
                session_id=session.session_id,
            )
            return
        raise RuntimeError("session loop exceeded max_turns without reaching a terminal state")

    async def _ensure_aos_control_block(self) -> None:
        existing = await self.store.get_aos_control_block(AOSControlBlock)
        if existing is not None:
            self.aos_cb = existing
            return
        now = datetime.now(UTC)
        self.aos_cb = AOSControlBlock(
            schema_version="aos/v0.81",
            name="local",
            skill_root=str(self.skill_root),
            revision=1,
            created_at=now,
            updated_at=now,
        )
        await self.store.save_aos_control_block(self.aos_cb.name, self.aos_cb)

    async def _bootstrap_session(self, session: SessionControlBlock) -> None:
        agent = await self._require_agent(session.agent_id)
        await self.hooks.dispatch(
            "skill.default.resolve.before",
            {"ownerType": "session", "ownerId": session.session_id, "plannedNames": []},
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        names = resolve_default_skill_names(self._require_aos_cb(), agent, session, mode="load")
        await self.hooks.dispatch(
            "skill.default.resolve.after",
            {"ownerType": "session", "ownerId": session.session_id, "resolvedNames": names},
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        await self.hooks.dispatch(
            "session.bootstrap.before",
            {"agentId": session.agent_id, "sessionId": session.session_id, "plannedNames": names},
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )

        await self._append_history_message(
            session,
            SessionHistoryMessage.bootstrap_marker(1, phase="begin", planned_names=names),
        )

        for name in names:
            manifest = self.skill_index.get(name)
            if manifest is None:
                continue
            await self._append_skill_load(
                session,
                name=name,
                skill_text=manifest.skill_text,
                cause="default",
            )

        seq = await self._next_seq(session.session_id)
        await self._append_history_message(
            session, SessionHistoryMessage.bootstrap_marker(seq, phase="done", planned_names=names)
        )
        await self._rebuild_context(session.session_id)
        session.status = "ready"
        session.updated_at = datetime.now(UTC)
        session.revision += 1
        await self.store.save_session_control_block(session.session_id, session.agent_id, session)
        await self.hooks.dispatch(
            "session.bootstrap.after",
            {"agentId": session.agent_id, "sessionId": session.session_id, "injectedNames": names},
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        await self.events.publish(
            RuntimeEvent(
                type="session.started",
                owner_type="session",
                agent_id=session.agent_id,
                session_id=session.session_id,
                payload={"cause": "bootstrap"},
            )
        )
        await self.hooks.dispatch(
            "session.started",
            {
                "agentId": session.agent_id,
                "sessionId": session.session_id,
                "cause": "bootstrap",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )

    async def _append_history_message(
        self, session: SessionControlBlock, message: SessionHistoryMessage
    ) -> None:
        hook_output = await self.hooks.dispatch(
            "session.message.beforeWrite",
            {
                "agentId": session.agent_id,
                "sessionId": session.session_id,
                "message": message.model_dump(mode="json", by_alias=True),
            },
            {"message": message.model_dump(mode="json", by_alias=True)},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        message = SessionHistoryMessage.model_validate(hook_output["message"])
        await self.store.append_session_history(session.session_id, message)
        session.revision += 1
        session.updated_at = datetime.now(UTC)
        await self.store.save_session_control_block(session.session_id, session.agent_id, session)
        await self._rebuild_context(session.session_id)

    async def _compact_session(self, session_id: str, auto: bool = False) -> None:
        session = await self._require_session(session_id)
        history = await self.store.list_full_session_history(session_id, SessionHistoryMessage)
        if not history:
            return
        from_seq = history[0].metadata.seq
        to_seq = history[-1].metadata.seq
        await self.hooks.dispatch(
            "session.compaction.before",
            {
                "agentId": session.agent_id,
                "sessionId": session.session_id,
                "fromSeq": from_seq,
                "toSeq": to_seq,
            },
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        await self.hooks.dispatch(
            "session.compaction.transform",
            {
                "agentId": session.agent_id,
                "sessionId": session.session_id,
                "fromSeq": from_seq,
                "toSeq": to_seq,
            },
            {"contextParts": [], "summaryHint": None},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        marker = SessionHistoryMessage.compaction_marker(
            await self._next_seq(session_id),
            from_seq=from_seq,
            to_seq=to_seq,
            auto=auto,
        )
        await self._append_history_message(session, marker)
        summary_text = (
            "\n".join(
                part.text
                for message in history
                for part in message.parts
                if isinstance(part, TextPart) and part.text
            )
            or "No prior work."
        )
        await self._append_history_message(
            session,
            SessionHistoryMessage.compaction_summary(
                await self._next_seq(session_id),
                text=summary_text,
                parent_id=marker.id,
            ),
        )
        agent = await self._require_agent(session.agent_id)
        await self.hooks.dispatch(
            "session.compaction.after",
            {
                "agentId": session.agent_id,
                "sessionId": session.session_id,
                "compactionSeq": marker.metadata.seq,
            },
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        await self.hooks.dispatch(
            "session.reinject.before",
            {"agentId": session.agent_id, "sessionId": session.session_id, "plannedNames": []},
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        reinjected_names: list[str] = []
        for name in resolve_default_skill_names(
            self._require_aos_cb(), agent, session, mode="load"
        ):
            manifest = self.skill_index.get(name)
            if manifest is None:
                continue
            reinjected_names.append(name)
            await self._append_skill_load(
                session,
                name=name,
                skill_text=manifest.skill_text,
                cause="reinject",
            )
        await self.hooks.dispatch(
            "session.reinject.after",
            {
                "agentId": session.agent_id,
                "sessionId": session.session_id,
                "injectedNames": reinjected_names,
            },
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )

    async def _get_or_rebuild_context(self, session_id: str) -> SessionContext:
        await self._require_session(session_id)
        if session_id not in self.state.contexts:
            return await self._rebuild_context(session_id)
        return self.state.contexts[session_id]

    async def _rebuild_context(self, session_id: str) -> SessionContext:
        await self._require_session(session_id)
        history = await self.store.list_full_session_history(session_id, SessionHistoryMessage)
        current_revision = (
            self.state.contexts[session_id].context_revision + 1
            if session_id in self.state.contexts
            else 1
        )
        context = materialize_session_context(
            session_id,
            history,
            folded_refs=self.state.folded_refs.get(session_id, set()),
            context_revision=current_revision,
        )
        self.state.contexts[session_id] = context
        return context

    async def _next_seq(self, session_id: str) -> int:
        return await self.store.get_max_session_seq(session_id) + 1

    async def _require_agent(self, agent_id: str) -> AgentControlBlock:
        agent = await self.store.get_agent_control_block(agent_id, AgentControlBlock)
        if agent is None:
            raise KeyError(agent_id)
        return agent

    async def _require_session(self, session_id: str) -> SessionControlBlock:
        session = await self.store.get_session_control_block(session_id, SessionControlBlock)
        if session is None:
            raise KeyError(session_id)
        return session

    async def _get_owner_control_block(
        self, owner_type: str, owner_id: str | None
    ) -> AOSControlBlock | AgentControlBlock | SessionControlBlock:
        if owner_type == "system":
            return self._require_aos_cb()
        if owner_type == "agent":
            if owner_id is None:
                raise ValueError("owner_id is required for agent defaults")
            return await self._require_agent(owner_id)
        if owner_id is None:
            raise ValueError("owner_id is required for session defaults")
        return await self._require_session(owner_id)

    async def _save_owner_control_block(
        self,
        owner_type: str,
        control_block: AOSControlBlock | AgentControlBlock | SessionControlBlock,
    ) -> None:
        control_block.revision += 1
        control_block.updated_at = datetime.now(UTC)
        if owner_type == "system" and isinstance(control_block, AOSControlBlock):
            self.aos_cb = control_block
            await self.store.save_aos_control_block(control_block.name, control_block)
            return
        if owner_type == "agent" and isinstance(control_block, AgentControlBlock):
            await self.store.save_agent_control_block(control_block.agent_id, control_block)
            return
        if isinstance(control_block, SessionControlBlock):
            await self.store.save_session_control_block(
                control_block.session_id,
                control_block.agent_id,
                control_block,
            )
            return
        raise TypeError(f"invalid control block for owner_type={owner_type}")

    async def _stop_owned_plugins(self, owner_type: str, owner_id: str) -> None:
        for instance_id, plugin in list(self.state.plugins.items()):
            if plugin.owner_type == owner_type and plugin.owner_id == owner_id:
                self.hooks.unregister_instance(instance_id)
                plugin.state = "stopped"

    async def _stop_owned_resources(self, owner_type: str, owner_id: str) -> None:
        resources = await self.store.list_resources(owner_type=owner_type, owner_id=owner_id)
        for resource in resources:
            await self._op_resource_stop(resource.resource_id)

    async def _log(
        self,
        op: str,
        *,
        owner_type: str,
        owner_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        await self.store.append_runtime_log(
            RuntimeLogEntry(
                id=self._new_id("log"),
                op=op,
                owner_type=cast(Literal["system", "agent", "session"], owner_type),
                owner_id=owner_id,
                agent_id=agent_id,
                session_id=session_id,
                data=data,
            )
        )

    def _require_aos_cb(self) -> AOSControlBlock:
        if self.aos_cb is None:
            raise RuntimeError("AOS control block has not been initialized")
        return self.aos_cb

    def _infer_owner_type(
        self, op: str, args: dict[str, Any]
    ) -> Literal["system", "agent", "session"]:
        if args.get("owner_type") in {"system", "agent", "session"}:
            return cast(Literal["system", "agent", "session"], args["owner_type"])
        if args.get("session_id"):
            return "session"
        if args.get("agent_id"):
            return "agent"
        if op.startswith("agent."):
            return "agent"
        return "system"

    def _infer_owner_id(self, args: dict[str, Any]) -> str | None:
        return args.get("owner_id") or args.get("session_id") or args.get("agent_id")

    async def _resource_agent_id(self, owner_type: str, owner_id: str | None) -> str | None:
        if owner_type == "agent":
            return owner_id
        if owner_type == "session" and owner_id is not None:
            return (await self._require_session(owner_id)).agent_id
        return None

    async def _validate_owner_exists(self, owner_type: str, owner_id: str | None) -> None:
        if owner_type == "system":
            return
        if owner_type == "agent":
            if owner_id is None:
                raise ValueError("owner_id is required for agent resources")
            await self._require_agent(owner_id)
            return
        if owner_id is None:
            raise ValueError("owner_id is required for session resources")
        await self._require_session(owner_id)

    async def _append_skill_load(
        self,
        session: SessionControlBlock,
        *,
        name: str,
        skill_text: str,
        cause: Literal["default", "explicit", "reinject"],
    ) -> None:
        await self.hooks.dispatch(
            "skill.load.before",
            {"name": name, "sessionId": session.session_id},
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )
        message = SessionHistoryMessage.skill_load(
            await self._next_seq(session.session_id),
            cause=cause,
            owner_type="session",
            owner_id=session.session_id,
            name=name,
            skill_text=skill_text,
        )
        await self._append_history_message(session, message)
        await self.hooks.dispatch(
            "skill.load.after",
            {"name": name, "sessionId": session.session_id, "skillText": skill_text},
            {},
            agent_id=session.agent_id,
            session_id=session.session_id,
        )

    async def _reconcile_default_starts(self, owner_type: str, owner_id: str | None) -> None:
        if owner_type == "system":
            desired = set(
                resolve_default_skill_names(self._require_aos_cb(), None, None, mode="start")
            )
        elif owner_type == "agent":
            assert owner_id is not None
            agent = await self._require_agent(owner_id)
            desired = set(
                resolve_default_skill_names(self._require_aos_cb(), agent, None, mode="start")
            )
        else:
            assert owner_id is not None
            session = await self._require_session(owner_id)
            agent = await self._require_agent(session.agent_id)
            desired = set(
                resolve_default_skill_names(self._require_aos_cb(), agent, session, mode="start")
            )

        existing = {
            plugin.skill_name: plugin.instance_id
            for plugin in self.state.plugins.values()
            if plugin.owner_type == owner_type and plugin.owner_id == owner_id
        }
        for skill_name in desired - set(existing):
            await self._op_skill_start(
                skill_name=skill_name,
                owner_type=cast(Literal["system", "agent", "session"], owner_type),
                owner_id=owner_id,
            )
        for skill_name in set(existing) - desired:
            await self._op_skill_stop(existing[skill_name])

    async def _session_has_interrupt(self, session_id: str) -> bool:
        history = await self.store.list_full_session_history(session_id, SessionHistoryMessage)
        if not history:
            return False
        return any(part.type == "data-interrupt" for part in history[-1].parts)

    @staticmethod
    def _catalog_item(manifest) -> dict[str, Any]:
        return {"name": manifest.name, "description": manifest.description}

    @staticmethod
    def _load_module(path: Path):
        spec = importlib.util.spec_from_file_location(f"aos_plugin_{path.stem}_{uuid4().hex}", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load plugin module: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:12]}"

    @staticmethod
    def _to_snake(value: str) -> str:
        result: list[str] = []
        for character in value:
            if character.isupper():
                result.extend(["_", character.lower()])
            else:
                result.append(character)
        return "".join(result).lstrip("_")


__all__ = ["AOSRuntime"]
