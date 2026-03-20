import sqlite3

import pytest

from aos.store.sqlite import SQLiteStore


@pytest.mark.asyncio
async def test_initialize_creates_foundation_tables(tmp_path) -> None:
    database_path = tmp_path / "agentos.db"

    store = SQLiteStore(database_path)
    await store.initialize()

    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    finally:
        connection.close()

    assert [row[0] for row in rows] == [
        "agent_control_blocks",
        "aos_control_blocks",
        "content_blobs",
        "managed_resources",
        "runtime_log",
        "session_control_blocks",
        "session_history",
    ]


@pytest.mark.asyncio
async def test_content_store_round_trip_and_materialize(tmp_path) -> None:
    database_path = tmp_path / "agentos.db"
    runtime_dir = tmp_path / "runtime"

    store = SQLiteStore(database_path)
    await store.initialize()

    content_id = await store.put_content(
        session_id="session-1",
        content="line 1\nline 2\n",
    )

    assert content_id
    assert await store.get_content(content_id) == "line 1\nline 2\n"

    materialized = await store.materialize_content(content_id, runtime_dir=runtime_dir)

    assert materialized == runtime_dir / "blobs" / content_id
    assert materialized.read_text() == "line 1\nline 2\n"
