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
        "managed_resources",
        "runtime_log",
        "session_control_blocks",
        "session_history",
    ]
