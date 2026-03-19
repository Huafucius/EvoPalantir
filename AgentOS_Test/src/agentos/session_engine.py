from __future__ import annotations

from typing import Any

from agentos.bash_executor import BashExecutor
from agentos.hook_runtime import HookRuntime, ToolArgs
from agentos.models import SCHEMA_VERSION, make_text_message, new_id, now_rfc3339
from agentos.react_unit import ReActResult, ReActUnit
from agentos.store import Store


class SessionEngine:
    def __init__(self, store: Store, hooks: HookRuntime):
        self.store = store
        self.hooks = hooks
        self.react = ReActUnit()
        self.bash = BashExecutor()

    def run_turn(self, session: dict[str, Any], max_steps: int = 4) -> dict[str, Any]:
        if max_steps <= 0:
            max_steps = 1

        agent_id = str(session["agentId"])
        session_id = str(session["sessionId"])
        history_path = self.store.session_history_path(agent_id, session_id)

        steps = 0
        while steps < max_steps:
            steps += 1
            self._log_phase(session, "computing")
            history = self.store.read_jsonl(history_path)
            if not history:
                final_text = "No session history."
                self._append_assistant_text(session, final_text)
                self._log_phase(session, "idle")
                return {"status": "completed", "steps": steps, "finalText": final_text}

            result = self.react.step(history)
            if result.kind == "final":
                final_text = result.text or ""
                self._append_assistant_text(session, final_text)
                self._log_phase(session, "idle")
                return {"status": "completed", "steps": steps, "finalText": final_text}

            self._log_phase(session, "tooling")
            self._run_tool_call(session, result)

        self._log_phase(session, "idle")
        return {"status": "max_steps_reached", "steps": steps}

    def _run_tool_call(self, session: dict[str, Any], result: ReActResult) -> None:
        agent_id = str(session["agentId"])
        session_id = str(session["sessionId"])
        assert result.toolCall is not None
        call = result.toolCall
        tool_call_id = new_id("tool")

        args = ToolArgs(
            command=call.command,
            cwd=call.cwd,
            timeoutMs=call.timeoutMs or 120000,
        )
        args = self.hooks.apply_tool_before(session, args)
        env = self.hooks.apply_tool_env(session, args)

        bash_result = self.bash.execute(
            command=args.command,
            cwd=args.cwd,
            timeout_ms=args.timeoutMs,
            env=env,
        )

        visible = bash_result.visibleResult or ""
        if bash_result.state == "output-available":
            visible = self.hooks.apply_tool_after(session, bash_result.rawResult, visible)

        part: dict[str, Any] = {
            "id": new_id("part"),
            "type": "tool-bash",
            "toolCallId": tool_call_id,
            "state": bash_result.state,
            "input": {
                "command": args.command,
                "cwd": args.cwd,
                "timeoutMs": args.timeoutMs,
            },
        }
        if bash_result.state == "output-available":
            part["output"] = {"visibleResult": visible}
        else:
            part["errorText"] = bash_result.errorText or "Bash execution failed"

        msg = {
            "id": new_id("msg"),
            "role": "assistant",
            "parts": [part],
            "metadata": {
                "createdAt": now_rfc3339(),
                "origin": "assistant",
            },
        }
        self.store.append_jsonl(self.store.session_history_path(agent_id, session_id), msg)
        self.store.append_jsonl(
            self.store.runtime_log_path(),
            {
                "id": new_id("rl"),
                "time": now_rfc3339(),
                "level": "info",
                "op": "tool.execute",
                "ownerType": "session",
                "ownerId": session_id,
                "agentId": agent_id,
                "sessionId": session_id,
                "refs": {"historyMessageId": msg["id"], "historyPartId": part["id"]},
                "data": {"toolCallId": tool_call_id, "rawResult": bash_result.rawResult},
                "schemaVersion": SCHEMA_VERSION,
            },
        )

    def _append_assistant_text(self, session: dict[str, Any], text: str) -> None:
        agent_id = str(session["agentId"])
        session_id = str(session["sessionId"])
        msg = make_text_message(role="assistant", text=text, origin="assistant")
        self.store.append_jsonl(self.store.session_history_path(agent_id, session_id), msg)

    def _log_phase(self, session: dict[str, Any], phase: str) -> None:
        self.hooks.append_runtime_log(
            op="session.phase",
            owner_type="session",
            owner_id=str(session["sessionId"]),
            agent_id=str(session["agentId"]),
            session_id=str(session["sessionId"]),
            data={"phase": phase},
        )
