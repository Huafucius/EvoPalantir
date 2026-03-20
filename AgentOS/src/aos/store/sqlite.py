from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import aiosqlite
from pydantic import BaseModel

from aos.model.history import SessionHistoryMessage
from aos.model.runtime import ManagedResource, RuntimeLogEntry

ModelT = TypeVar("ModelT", bound=BaseModel)

FOUNDATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS aos_control_blocks (
    name TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_control_blocks (
    agent_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_control_blocks (
    session_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_history (
    session_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    message_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (session_id, seq),
    UNIQUE (session_id, message_id)
);

CREATE TABLE IF NOT EXISTS runtime_log (
    id TEXT PRIMARY KEY,
    time TEXT NOT NULL,
    owner_type TEXT NOT NULL,
    owner_id TEXT,
    agent_id TEXT,
    session_id TEXT,
    op TEXT NOT NULL,
    level TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS managed_resources (
    resource_id TEXT PRIMARY KEY,
    owner_type TEXT NOT NULL,
    owner_id TEXT,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_blobs (
    blob_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    size_chars INTEGER NOT NULL,
    line_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

    @property
    def database_path(self) -> Path:
        return self._database_path

    async def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._database_path) as connection:
            await connection.executescript(FOUNDATION_SCHEMA)
            await connection.commit()

    async def get_aos_control_block(self, model_type: type[ModelT]) -> ModelT | None:
        row = await self._fetchone("SELECT payload FROM aos_control_blocks LIMIT 1")
        return None if row is None else model_type.model_validate_json(row[0])

    async def save_aos_control_block(self, name: str, model: BaseModel) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO aos_control_blocks(name, payload) VALUES (?, ?)",
            (name, self._dump_model(model)),
        )

    async def list_agent_control_blocks(self, model_type: type[ModelT]) -> list[ModelT]:
        rows = await self._fetchall("SELECT payload FROM agent_control_blocks ORDER BY agent_id")
        return [model_type.model_validate_json(row[0]) for row in rows]

    async def get_agent_control_block(
        self, agent_id: str, model_type: type[ModelT]
    ) -> ModelT | None:
        row = await self._fetchone(
            "SELECT payload FROM agent_control_blocks WHERE agent_id = ?", (agent_id,)
        )
        return None if row is None else model_type.model_validate_json(row[0])

    async def save_agent_control_block(self, agent_id: str, model: BaseModel) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO agent_control_blocks(agent_id, payload) VALUES (?, ?)",
            (agent_id, self._dump_model(model)),
        )

    async def list_session_control_blocks(
        self, model_type: type[ModelT], agent_id: str | None = None
    ) -> list[ModelT]:
        if agent_id is None:
            rows = await self._fetchall(
                "SELECT payload FROM session_control_blocks ORDER BY session_id"
            )
        else:
            rows = await self._fetchall(
                "SELECT payload FROM session_control_blocks WHERE agent_id = ? ORDER BY session_id",
                (agent_id,),
            )
        return [model_type.model_validate_json(row[0]) for row in rows]

    async def get_session_control_block(
        self, session_id: str, model_type: type[ModelT]
    ) -> ModelT | None:
        row = await self._fetchone(
            "SELECT payload FROM session_control_blocks WHERE session_id = ?",
            (session_id,),
        )
        return None if row is None else model_type.model_validate_json(row[0])

    async def save_session_control_block(
        self, session_id: str, agent_id: str, model: BaseModel
    ) -> None:
        await self._execute(
            (
                "INSERT OR REPLACE INTO session_control_blocks("
                "session_id, agent_id, payload"
                ") VALUES (?, ?, ?)"
            ),
            (session_id, agent_id, self._dump_model(model)),
        )

    async def append_session_history(self, session_id: str, message: SessionHistoryMessage) -> None:
        await self._execute(
            "INSERT INTO session_history(session_id, seq, message_id, payload) VALUES (?, ?, ?, ?)",
            (session_id, message.metadata.seq, message.id, self._dump_model(message)),
        )

    async def list_session_history(
        self,
        session_id: str,
        model_type: type[ModelT],
        *,
        cursor: int | None = None,
        limit: int = 100,
    ) -> list[ModelT]:
        if cursor is None:
            rows = await self._fetchall(
                "SELECT payload FROM session_history WHERE session_id = ? ORDER BY seq LIMIT ?",
                (session_id, limit),
            )
        else:
            rows = await self._fetchall(
                (
                    "SELECT payload FROM session_history "
                    "WHERE session_id = ? AND seq > ? ORDER BY seq LIMIT ?"
                ),
                (session_id, cursor, limit),
            )
        return [model_type.model_validate_json(row[0]) for row in rows]

    async def list_full_session_history(
        self, session_id: str, model_type: type[ModelT]
    ) -> list[ModelT]:
        rows = await self._fetchall(
            "SELECT payload FROM session_history WHERE session_id = ? ORDER BY seq",
            (session_id,),
        )
        return [model_type.model_validate_json(row[0]) for row in rows]

    async def get_max_session_seq(self, session_id: str) -> int:
        row = await self._fetchone(
            "SELECT MAX(seq) FROM session_history WHERE session_id = ?",
            (session_id,),
        )
        if row is None or row[0] is None:
            return 0
        return int(row[0])

    async def get_session_history_message(
        self,
        session_id: str,
        message_id: str,
        model_type: type[ModelT],
    ) -> ModelT | None:
        row = await self._fetchone(
            "SELECT payload FROM session_history WHERE session_id = ? AND message_id = ?",
            (session_id, message_id),
        )
        return None if row is None else model_type.model_validate_json(row[0])

    async def append_runtime_log(self, entry: RuntimeLogEntry) -> None:
        await self._execute(
            (
                "INSERT INTO runtime_log("
                "id, time, owner_type, owner_id, agent_id, session_id, op, level, payload"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                entry.id,
                entry.time.isoformat(),
                entry.owner_type,
                entry.owner_id,
                entry.agent_id,
                entry.session_id,
                entry.op,
                entry.level,
                self._dump_model(entry),
            ),
        )

    async def list_runtime_log(
        self, model_type: type[ModelT], *, owner_type: str | None = None
    ) -> list[ModelT]:
        if owner_type is None:
            rows = await self._fetchall("SELECT payload FROM runtime_log ORDER BY time")
        else:
            rows = await self._fetchall(
                "SELECT payload FROM runtime_log WHERE owner_type = ? ORDER BY time",
                (owner_type,),
            )
        return [model_type.model_validate_json(row[0]) for row in rows]

    async def save_resource(self, resource: ManagedResource) -> None:
        await self._execute(
            (
                "INSERT OR REPLACE INTO managed_resources("
                "resource_id, owner_type, owner_id, payload"
                ") VALUES (?, ?, ?, ?)"
            ),
            (
                resource.resource_id,
                resource.owner_type,
                resource.owner_id,
                self._dump_model(resource),
            ),
        )

    async def get_resource(self, resource_id: str) -> ManagedResource | None:
        row = await self._fetchone(
            "SELECT payload FROM managed_resources WHERE resource_id = ?",
            (resource_id,),
        )
        return None if row is None else ManagedResource.model_validate_json(row[0])

    async def list_resources(
        self,
        *,
        owner_type: str | None = None,
        owner_id: str | None = None,
    ) -> list[ManagedResource]:
        if owner_type is None:
            rows = await self._fetchall(
                "SELECT payload FROM managed_resources ORDER BY resource_id"
            )
        elif owner_id is None:
            rows = await self._fetchall(
                "SELECT payload FROM managed_resources WHERE owner_type = ? ORDER BY resource_id",
                (owner_type,),
            )
        else:
            rows = await self._fetchall(
                (
                    "SELECT payload FROM managed_resources "
                    "WHERE owner_type = ? AND owner_id = ? ORDER BY resource_id"
                ),
                (owner_type, owner_id),
            )
        return [ManagedResource.model_validate_json(row[0]) for row in rows]

    async def put_content(self, *, session_id: str, content: str) -> str:
        from datetime import UTC, datetime
        from uuid import uuid4

        content_id = f"blob-{uuid4().hex[:12]}"
        await self._execute(
            (
                "INSERT INTO content_blobs("
                "blob_id, session_id, content, size_chars, line_count, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?)"
            ),
            (
                content_id,
                session_id,
                content,
                len(content),
                content.count("\n") + (0 if not content or content.endswith("\n") else 1),
                datetime.now(UTC).isoformat(),
            ),
        )
        return content_id

    async def get_content(self, content_id: str) -> str | None:
        row = await self._fetchone(
            "SELECT content FROM content_blobs WHERE blob_id = ?",
            (content_id,),
        )
        return None if row is None else str(row[0])

    async def materialize_content(self, content_id: str, *, runtime_dir: Path) -> Path:
        content = await self.get_content(content_id)
        if content is None:
            raise KeyError(f"unknown content id: {content_id}")
        blob_dir = runtime_dir / "blobs"
        blob_dir.mkdir(parents=True, exist_ok=True)
        path = blob_dir / content_id
        path.write_text(content)
        return path

    async def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        async with aiosqlite.connect(self._database_path) as connection:
            await connection.execute(sql, params)
            await connection.commit()

    async def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        async with aiosqlite.connect(self._database_path) as connection:
            async with connection.execute(sql, params) as cursor:
                return await cursor.fetchone()

    async def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        async with aiosqlite.connect(self._database_path) as connection:
            async with connection.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
        return list(rows)

    @staticmethod
    def _dump_model(model: BaseModel) -> str:
        return json.dumps(model.model_dump(mode="json", by_alias=True), separators=(",", ":"))


__all__ = ["FOUNDATION_SCHEMA", "SQLiteStore"]
