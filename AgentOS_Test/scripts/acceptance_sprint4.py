from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _prepare_import_path() -> None:
    src = _repo_root() / "src"
    sys.path.insert(0, str(src))


def run(runtime_root: Path) -> dict[str, Any]:
    _prepare_import_path()
    from agentos.control_plane import ControlPlane  # pyright: ignore[reportMissingImports]

    if runtime_root.exists():
        shutil.rmtree(runtime_root)

    cp1 = ControlPlane(runtime_root=runtime_root)
    cp1.call("aos.init", {})
    agent = cp1.call("agent.create", {"displayName": "acceptance-agent"})["data"]
    session = cp1.call(
        "session.create",
        {"agentId": agent["agentId"], "title": "acceptance"},
    )["data"]

    history = cp1.call("session.history.list", {"sessionId": session["sessionId"]})["data"]["items"]
    skill_load_count = sum(
        1
        for item in history
        if any(part.get("type") == "data-skill-load" for part in item.get("parts", []))
    )

    cp1.call(
        "session.append",
        {
            "sessionId": session["sessionId"],
            "role": "user",
            "text": "bash: env | grep AOS_SESSION_ID",
        },
    )
    turn1 = cp1.call("session.run_turn", {"sessionId": session["sessionId"]})["data"]

    cp2 = ControlPlane(runtime_root=runtime_root)
    rebuild = cp2.call("session.context.rebuild", {"sessionId": session["sessionId"]})["data"]
    cp2.call(
        "session.append",
        {
            "sessionId": session["sessionId"],
            "role": "user",
            "text": "hello-after-restart",
        },
    )
    turn2 = cp2.call("session.run_turn", {"sessionId": session["sessionId"]})["data"]

    result = {
        "sessionId": session["sessionId"],
        "skillLoadCount": skill_load_count,
        "turn1": turn1,
        "contextRevisionAfterRebuild": rebuild["contextRevision"],
        "turn2": turn2,
        "checks": {
            "skillLoadCountIs3": skill_load_count == 3,
            "turn1IncludesSessionEnv": "AOS_SESSION_ID=" in str(turn1.get("finalText", "")),
            "turn2ContinuesAfterRestart": turn2.get("finalText") == "ACK: hello-after-restart",
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint-4 acceptance runner")
    parser.add_argument(
        "--runtime-root",
        default="runtime_acceptance",
        help="Runtime directory for acceptance execution",
    )
    args = parser.parse_args()

    result = run(Path(args.runtime_root))
    checks = cast(dict[str, Any], result["checks"])
    ok = all(bool(v) for v in checks.values())
    output = {"ok": ok, "result": result}
    print(json.dumps(output, ensure_ascii=True, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
