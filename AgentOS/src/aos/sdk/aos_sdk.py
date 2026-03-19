from __future__ import annotations

from typing import Any


class AosSDK:
    def __init__(self, runtime) -> None:
        self._runtime = runtime

    async def call(self, op: str, **kwargs: Any) -> Any:
        return await self._runtime.call(op, **kwargs)


__all__ = ["AosSDK"]
