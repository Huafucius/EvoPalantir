from __future__ import annotations

from pathlib import Path

from agentos.control_plane import ControlPlane
from agentos.store import Store


def _new_cp(runtime_root: Path) -> ControlPlane:
    return ControlPlane(runtime_root=runtime_root)


def test_recovery_rebuild_and_continue(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    cp1 = _new_cp(runtime)

    cp1.call("aos.init", {})
    agent = cp1.call("agent.create", {"displayName": "recover-agent"})["data"]
    session = cp1.call("session.create", {"agentId": agent["agentId"], "title": "recover"})["data"]

    cp1.call(
        "session.append",
        {
            "sessionId": session["sessionId"],
            "role": "user",
            "text": "bash: echo first-turn",
        },
    )
    turn1 = cp1.call("session.run_turn", {"sessionId": session["sessionId"]})["data"]
    assert turn1["status"] == "completed"
    assert "first-turn" in turn1["finalText"]

    cp2 = _new_cp(runtime)
    rebuilt = cp2.call("session.context.rebuild", {"sessionId": session["sessionId"]})["data"]
    assert int(rebuilt["contextRevision"]) >= 2

    cp2.call(
        "session.append",
        {
            "sessionId": session["sessionId"],
            "role": "user",
            "text": "hello-after-restart",
        },
    )
    turn2 = cp2.call("session.run_turn", {"sessionId": session["sessionId"]})["data"]
    assert turn2["status"] == "completed"
    assert "ACK: hello-after-restart" == turn2["finalText"]


def test_bootstrap_and_tool_split(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    cp = _new_cp(runtime)

    cp.call("aos.init", {})
    agent = cp.call("agent.create", {"displayName": "split-agent"})["data"]
    session = cp.call("session.create", {"agentId": agent["agentId"], "title": "split"})["data"]

    history = cp.call("session.history.list", {"sessionId": session["sessionId"]})["data"]["items"]
    skill_loads = [
        item
        for item in history
        if any(part.get("type") == "data-skill-load" for part in item.get("parts", []))
    ]
    assert len(skill_loads) == 3

    cp.call(
        "session.append",
        {
            "sessionId": session["sessionId"],
            "role": "user",
            "text": "bash: echo split-check",
        },
    )
    cp.call("session.run_turn", {"sessionId": session["sessionId"]})

    history2 = cp.call("session.history.list", {"sessionId": session["sessionId"]})["data"]["items"]
    tool_parts = [
        part
        for item in history2
        for part in item.get("parts", [])
        if part.get("type") == "tool-bash"
    ]
    assert any(part.get("output", {}).get("visibleResult") for part in tool_parts)

    store = Store(runtime)
    logs = store.read_jsonl(store.runtime_log_path())
    tool_exec_logs = [log for log in logs if log.get("op") == "tool.execute"]
    assert tool_exec_logs
    assert "rawResult" in tool_exec_logs[-1].get("data", {})
