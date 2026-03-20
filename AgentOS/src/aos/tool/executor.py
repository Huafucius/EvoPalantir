from __future__ import annotations

import asyncio
import os
from typing import Any

from aos.hook.admission import AdmissionHookEngine
from aos.hook.transform import TransformHookEngine


class BashToolExecutor:
    def __init__(
        self,
        admission_hooks: AdmissionHookEngine,
        transform_hooks: TransformHookEngine,
    ) -> None:
        self._admission_hooks = admission_hooks
        self._transform_hooks = transform_hooks

    async def execute(
        self,
        *,
        tool_call_id: str,
        args: dict[str, Any],
        owner_ids: dict[str, str | None],
    ) -> dict[str, Any]:
        env_output = await self._transform_hooks.dispatch(
            "tool.env",
            {"toolCallId": tool_call_id, "args": dict(args)},
            {"env": {}},
            agent_id=owner_ids.get("agent_id"),
            session_id=owner_ids.get("session_id"),
        )
        args_output = await self._admission_hooks.dispatch(
            "tool.before",
            {"toolCallId": tool_call_id, "args": dict(args)},
            dict(args),
            agent_id=owner_ids.get("agent_id"),
            session_id=owner_ids.get("session_id"),
        )

        merged_env = os.environ.copy()
        merged_env.update(env_output.get("env", {}))
        command = str(args_output["command"])
        cwd = args_output.get("cwd")
        timeout_ms = args_output.get("timeoutMs") or args_output.get("timeout_ms")
        timeout = None if timeout_ms is None else float(timeout_ms) / 1000.0

        process = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            env=merged_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            stdout = b""
            stderr = b"timeout"

        raw_result = {
            "exitCode": process.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "combined": stdout.decode() + stderr.decode(),
        }
        after_output = await self._transform_hooks.dispatch(
            "tool.after",
            {"toolCallId": tool_call_id, "rawResult": raw_result},
            {"result": raw_result["combined"]},
            agent_id=owner_ids.get("agent_id"),
            session_id=owner_ids.get("session_id"),
        )
        return {
            "args": {
                "command": command,
                "cwd": cwd,
                "timeoutMs": timeout_ms,
            },
            "rawResult": raw_result,
            "visibleResult": after_output["result"],
        }


__all__ = ["BashToolExecutor"]
