from __future__ import annotations

from pathlib import Path
from typing import Any

from agentos.hook_runtime import HookRuntime
from agentos.models import (
    SCHEMA_VERSION,
    SKILL_CATALOG,
    make_agent,
    make_aoscb,
    make_default_skill_rules,
    make_session,
    make_text_message,
    new_id,
    now_rfc3339,
)
from agentos.session_engine import SessionEngine
from agentos.store import Store


class AosError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class ControlPlane:
    def __init__(self, runtime_root: Path):
        self.store = Store(runtime_root=runtime_root)
        self.store.ensure_dirs()
        self.hooks = HookRuntime(store=self.store)
        self.engine = SessionEngine(store=self.store, hooks=self.hooks)

    def call(self, op: str, payload: dict[str, Any]) -> dict[str, Any]:
        handlers: dict[str, Any] = {
            "aos.init": self.aos_init,
            "aos.get": self.aos_get,
            "agent.create": self.agent_create,
            "agent.get": self.agent_get,
            "session.create": self.session_create,
            "session.get": self.session_get,
            "session.append": self.session_append,
            "session.history.list": self.session_history_list,
            "session.context.get": self.session_context_get,
            "session.context.rebuild": self.session_context_rebuild,
            "session.run_turn": self.session_run_turn,
            "skill.list": self.skill_list,
            "skill.load": self.skill_load,
            "skill.start": self.skill_start,
            "plugin.list": self.plugin_list,
        }
        handler = handlers.get(op)
        if handler is None:
            raise AosError("OP_NOT_FOUND", f"Unsupported op: {op}")
        data = handler(payload)
        return {"ok": True, "op": op, "data": data}

    def aos_init(self, payload: dict[str, Any]) -> dict[str, Any]:
        aoscb_path = self.store.aoscb_path()
        if aoscb_path.exists():
            return self.store.read_json(aoscb_path)
        name = str(payload.get("name") or "EvoPalantir-AOS")
        skill_root = str(payload.get("skillRoot") or "skills")
        aoscb = make_aoscb(name=name, skill_root=skill_root)
        self.store.write_json(aoscb_path, aoscb.to_dict())
        self._append_runtime_log(
            "aos.init", owner_type="system", owner_id="system", data={"name": name}
        )
        return aoscb.to_dict()

    def aos_get(self, _payload: dict[str, Any]) -> dict[str, Any]:
        aoscb_path = self.store.aoscb_path()
        if not aoscb_path.exists():
            raise AosError("AOS_NOT_INITIALIZED", "AOS is not initialized. Call aos.init first.")
        return self.store.read_json(aoscb_path)

    def agent_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        display_name = payload.get("displayName")
        if display_name is not None:
            display_name = str(display_name)
        agent = make_agent(display_name=display_name)
        acb_path = self.store.agent_acb_path(agent.agentId)
        self.store.write_json(acb_path, agent.to_dict())
        self._append_runtime_log(
            "agent.create", owner_type="agent", owner_id=agent.agentId, data=agent.to_dict()
        )
        return agent.to_dict()

    def agent_get(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = self._require_str(payload, "agentId")
        acb_path = self.store.agent_acb_path(agent_id)
        if not acb_path.exists():
            raise AosError("AGENT_NOT_FOUND", f"Agent not found: {agent_id}")
        return self.store.read_json(acb_path)

    def session_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = self._require_str(payload, "agentId")
        title = payload.get("title")
        if title is not None:
            title = str(title)
        agent = self.agent_get({"agentId": agent_id})
        if agent["status"] != "active":
            raise AosError("AGENT_NOT_ACTIVE", f"Agent is not active: {agent_id}")
        session = make_session(agent_id=agent_id, title=title)
        session_dir = self.store.session_dir(agent_id, session.sessionId)
        session_dir.mkdir(parents=True, exist_ok=True)
        self.store.write_json(
            self.store.session_scb_path(agent_id, session.sessionId), session.to_dict()
        )
        self.store.write_json(
            self.store.session_context_meta_path(agent_id, session.sessionId),
            {"sessionId": session.sessionId, "contextRevision": 1},
        )
        begin_msg = make_text_message(role="user", text="[[AOS-BOOTSTRAP begin]]", origin="aos")
        self.store.append_jsonl(
            self.store.session_history_path(agent_id, session.sessionId), begin_msg
        )

        for rule in make_default_skill_rules():
            self.store.append_jsonl(
                self.store.session_history_path(agent_id, session.sessionId),
                self._make_skill_load_message(
                    session_id=session.sessionId,
                    name=str(rule["name"]),
                    cause="default",
                ),
            )
            if rule.get("start") == "enable":
                self.hooks.ensure_plugin_started(
                    skill_name=str(rule["name"]),
                    owner_type="session",
                    owner_id=session.sessionId,
                )

        done_msg = make_text_message(role="user", text="[[AOS-BOOTSTRAP done]]", origin="aos")
        self.store.append_jsonl(
            self.store.session_history_path(agent_id, session.sessionId), done_msg
        )
        self._append_runtime_log(
            "session.create",
            owner_type="session",
            owner_id=session.sessionId,
            agent_id=agent_id,
            session_id=session.sessionId,
            data=session.to_dict(),
        )
        return session.to_dict()

    def session_get(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = self._require_str(payload, "sessionId")
        agent_id = self._find_agent_id_by_session(session_id)
        scb_path = self.store.session_scb_path(agent_id, session_id)
        if not scb_path.exists():
            raise AosError("SESSION_NOT_FOUND", f"Session not found: {session_id}")
        return self.store.read_json(scb_path)

    def session_append(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = self._require_str(payload, "sessionId")
        role = self._require_str(payload, "role")
        text = self._require_str(payload, "text")
        if role not in {"user", "assistant", "system"}:
            raise AosError("INVALID_ROLE", f"Unsupported role: {role}")
        session = self.session_get({"sessionId": session_id})
        agent_id = session["agentId"]
        msg = make_text_message(
            role=role, text=text, origin="human" if role == "user" else "assistant"
        )
        history_path = self.store.session_history_path(agent_id, session_id)
        self.store.append_jsonl(history_path, msg)
        self._bump_session_revision(session)
        self._append_runtime_log(
            "session.append",
            owner_type="session",
            owner_id=session_id,
            agent_id=agent_id,
            session_id=session_id,
            data={"messageId": msg["id"]},
        )
        return {"revision": session["revision"], "messageId": msg["id"]}

    def session_history_list(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = self._require_str(payload, "sessionId")
        limit = int(payload.get("limit", 100))
        if limit <= 0:
            raise AosError("INVALID_LIMIT", "limit must be greater than 0")
        session = self.session_get({"sessionId": session_id})
        history = self.store.read_jsonl(
            self.store.session_history_path(session["agentId"], session_id)
        )
        return {"items": history[:limit], "nextCursor": None}

    def session_context_get(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = self._require_str(payload, "sessionId")
        session = self.session_get({"sessionId": session_id})
        meta_path = self.store.session_context_meta_path(session["agentId"], session_id)
        if meta_path.exists():
            meta = self.store.read_json(meta_path)
        else:
            meta = {"sessionId": session_id, "contextRevision": 0}
        history = self.store.read_jsonl(
            self.store.session_history_path(session["agentId"], session_id)
        )
        return {
            "sessionId": session_id,
            "contextRevision": int(meta.get("contextRevision", 0)),
            "messageCount": len(history),
            "foldedRefCount": 0,
        }

    def session_context_rebuild(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = self._require_str(payload, "sessionId")
        session = self.session_get({"sessionId": session_id})
        meta_path = self.store.session_context_meta_path(session["agentId"], session_id)
        if meta_path.exists():
            meta = self.store.read_json(meta_path)
        else:
            meta = {"sessionId": session_id, "contextRevision": 0}
        meta["contextRevision"] = int(meta.get("contextRevision", 0)) + 1
        self.store.write_json(meta_path, meta)
        self._append_runtime_log(
            "session.context.rebuild",
            owner_type="session",
            owner_id=session_id,
            agent_id=session["agentId"],
            session_id=session_id,
            data={"contextRevision": meta["contextRevision"]},
        )
        return {"contextRevision": meta["contextRevision"]}

    def session_run_turn(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = self._require_str(payload, "sessionId")
        max_steps = int(payload.get("maxSteps", 4))
        session = self.session_get({"sessionId": session_id})
        run_result = self.engine.run_turn(session=session, max_steps=max_steps)
        updated_session = self.session_get({"sessionId": session_id})
        self._bump_session_revision(updated_session)
        self._append_runtime_log(
            "session.run_turn",
            owner_type="session",
            owner_id=session_id,
            agent_id=updated_session["agentId"],
            session_id=session_id,
            data=run_result,
        )
        return run_result

    def skill_list(self, _payload: dict[str, Any]) -> dict[str, Any]:
        return {"items": SKILL_CATALOG}

    def skill_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = self._require_str(payload, "sessionId")
        name = self._require_str(payload, "name")
        session = self.session_get({"sessionId": session_id})
        msg = self._make_skill_load_message(session_id=session_id, name=name, cause="explicit")
        self.store.append_jsonl(
            self.store.session_history_path(session["agentId"], session_id), msg
        )
        self._bump_session_revision(session)
        self._append_runtime_log(
            "skill.load",
            owner_type="session",
            owner_id=session_id,
            agent_id=session["agentId"],
            session_id=session_id,
            data={"name": name},
        )
        return {"name": name, "skillText": msg["parts"][0]["data"]["skillText"]}

    def skill_start(self, payload: dict[str, Any]) -> dict[str, Any]:
        owner_type = self._require_str(payload, "ownerType")
        owner_id = str(payload.get("ownerId") or "system")
        skill_name = self._require_str(payload, "skillName")
        if owner_type not in {"system", "agent", "session"}:
            raise AosError("INVALID_OWNER_TYPE", f"Unsupported ownerType: {owner_type}")
        skill = next((it for it in SKILL_CATALOG if it["name"] == skill_name), None)
        if skill is None:
            raise AosError("SKILL_NOT_FOUND", f"Skill not found: {skill_name}")
        plugin = self.hooks.ensure_plugin_started(
            skill_name=skill_name,
            owner_type=owner_type,
            owner_id=owner_id,
        )
        self._append_runtime_log(
            "skill.start",
            owner_type=owner_type,
            owner_id=owner_id,
            data={"instanceId": plugin["instanceId"], "skillName": skill_name},
        )
        return {
            "instanceId": plugin["instanceId"],
            "skillName": skill_name,
            "ownerType": owner_type,
            "ownerId": owner_id,
        }

    def plugin_list(self, payload: dict[str, Any]) -> dict[str, Any]:
        owner_type = payload.get("ownerType")
        owner_id = payload.get("ownerId")
        plugins_path = self.store.runtime_root / "plugins.json"
        if not plugins_path.exists():
            return {"items": []}
        items = list(self.store.read_json(plugins_path).get("items", []))
        if owner_type is not None:
            items = [x for x in items if x.get("ownerType") == owner_type]
        if owner_id is not None:
            items = [x for x in items if x.get("ownerId") == owner_id]
        return {"items": items}

    def _find_agent_id_by_session(self, session_id: str) -> str:
        for agent_id in self.store.list_agents():
            scb_path = self.store.session_scb_path(agent_id, session_id)
            if scb_path.exists():
                return agent_id
        raise AosError("SESSION_NOT_FOUND", f"Session not found: {session_id}")

    def _append_runtime_log(
        self,
        op: str,
        owner_type: str,
        owner_id: str,
        data: dict[str, Any],
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        entry = {
            "id": new_id("rl"),
            "time": now_rfc3339(),
            "level": "info",
            "op": op,
            "ownerType": owner_type,
            "ownerId": owner_id,
            "agentId": agent_id,
            "sessionId": session_id,
            "refs": {},
            "data": data,
            "schemaVersion": SCHEMA_VERSION,
        }
        self.store.append_jsonl(self.store.runtime_log_path(), entry)

    def _make_skill_load_message(self, session_id: str, name: str, cause: str) -> dict[str, Any]:
        skill = next((item for item in SKILL_CATALOG if item["name"] == name), None)
        if skill is None:
            raise AosError("SKILL_NOT_FOUND", f"Skill not found: {name}")
        return {
            "id": new_id("msg"),
            "role": "user",
            "parts": [
                {
                    "id": new_id("part"),
                    "type": "data-skill-load",
                    "data": {
                        "cause": cause,
                        "ownerType": "session",
                        "ownerId": session_id,
                        "name": name,
                        "skillText": f"[[SKILL:{name}]] {skill['description']}",
                    },
                }
            ],
            "metadata": {
                "createdAt": now_rfc3339(),
                "origin": "aos",
            },
        }

    def _bump_session_revision(self, session: dict[str, Any]) -> None:
        session["revision"] = int(session["revision"]) + 1
        session["updatedAt"] = now_rfc3339()
        self.store.write_json(
            self.store.session_scb_path(session["agentId"], session["sessionId"]), session
        )

    @staticmethod
    def _require_str(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if value is None or str(value).strip() == "":
            raise AosError("INVALID_INPUT", f"Missing required field: {key}")
        return str(value)


def error_response(op: str, err: AosError) -> dict[str, Any]:
    return {
        "ok": False,
        "op": op,
        "error": {
            "code": err.code,
            "message": err.message,
            "details": err.details,
        },
    }
