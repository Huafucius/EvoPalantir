from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, runtime_root: Path):
        self.runtime_root = runtime_root

    def ensure_dirs(self) -> None:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self._agents_dir().mkdir(parents=True, exist_ok=True)

    def aoscb_path(self) -> Path:
        return self.runtime_root / "aoscb.json"

    def runtime_log_path(self) -> Path:
        return self.runtime_root / "runtime-log.jsonl"

    def agent_dir(self, agent_id: str) -> Path:
        return self._agents_dir() / agent_id

    def agent_acb_path(self, agent_id: str) -> Path:
        return self.agent_dir(agent_id) / "acb.json"

    def session_dir(self, agent_id: str, session_id: str) -> Path:
        return self.agent_dir(agent_id) / "sessions" / session_id

    def session_scb_path(self, agent_id: str, session_id: str) -> Path:
        return self.session_dir(agent_id, session_id) / "scb.json"

    def session_history_path(self, agent_id: str, session_id: str) -> Path:
        return self.session_dir(agent_id, session_id) / "history.jsonl"

    def session_context_meta_path(self, agent_id: str, session_id: str) -> Path:
        return self.session_dir(agent_id, session_id) / "context-meta.json"

    def write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def append_jsonl(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(data, ensure_ascii=True) + "\n")

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        items: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                items.append(json.loads(stripped))
        return items

    def list_agents(self) -> list[str]:
        base = self._agents_dir()
        if not base.exists():
            return []
        return [p.name for p in base.iterdir() if p.is_dir()]

    def _agents_dir(self) -> Path:
        return self.runtime_root / "agents"
