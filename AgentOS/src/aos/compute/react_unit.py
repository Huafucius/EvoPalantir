from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, cast

from litellm import acompletion

ProviderCall = Callable[..., Awaitable[Any]]

BASH_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Execute a bash command in the current environment.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
                "timeoutMs": {"type": "integer"},
            },
            "required": ["command"],
        },
    },
}


@dataclass
class ReActToolFunction:
    name: str
    arguments: dict[str, Any]


@dataclass
class ReActToolCall:
    id: str
    function: ReActToolFunction


@dataclass
class ComputeResult:
    text: str | None
    tool_calls: list[ReActToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, Any] = field(default_factory=dict)


class ReActUnit:
    def __init__(self, *, model: str, provider_call: ProviderCall | None = None) -> None:
        self.model = model
        self._provider_call = provider_call or acompletion

    async def complete(
        self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> ComputeResult:
        request_tools = [BASH_TOOL_SPEC] if tools is None else tools
        try:
            response = await self._provider_call(
                model=self.model,
                messages=messages,
                tools=request_tools,
            )
        except TypeError:
            provider_call = cast(Any, self._provider_call)
            response = await provider_call(messages)
        return self._normalize_response(response)

    @staticmethod
    def _normalize_response(response: Any) -> ComputeResult:
        if hasattr(response, "text") and hasattr(response, "tool_calls"):
            return ComputeResult(
                text=response.text,
                tool_calls=response.tool_calls,
                finish_reason=getattr(response, "finish_reason", "stop"),
                usage=getattr(response, "usage", {}),
            )

        choice = response.choices[0]
        message = choice.message
        tool_calls = []
        for tool_call in getattr(message, "tool_calls", None) or []:
            arguments = tool_call.function.arguments
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            tool_calls.append(
                ReActToolCall(
                    id=tool_call.id,
                    function=ReActToolFunction(name=tool_call.function.name, arguments=arguments),
                )
            )
        return ComputeResult(
            text=getattr(message, "content", None),
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            usage=getattr(response, "usage", {}),
        )


__all__ = ["BASH_TOOL_SPEC", "ComputeResult", "ReActToolCall", "ReActUnit"]
