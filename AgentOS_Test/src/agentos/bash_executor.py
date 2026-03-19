from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from os import environ
from typing import Any


@dataclass(slots=True)
class BashResult:
    state: str
    visibleResult: str | None
    errorText: str | None
    rawResult: dict[str, Any]


class BashExecutor:
    def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout_ms: int | None = None,
        env: dict[str, str] | None = None,
    ) -> BashResult:
        timeout_s = (timeout_ms or 120000) / 1000
        started = time.time()
        try:
            completed = subprocess.run(
                ["bash", "-lc", command],
                cwd=cwd,
                env={**environ, **(env or {})},
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            elapsed_ms = int((time.time() - started) * 1000)
            raw = {
                "command": command,
                "cwd": cwd,
                "timeoutMs": timeout_ms or 120000,
                "exitCode": None,
                "stdout": e.stdout or "",
                "stderr": e.stderr or "",
                "durationMs": elapsed_ms,
                "timedOut": True,
            }
            return BashResult(
                state="output-error",
                visibleResult=None,
                errorText=f"Command timed out after {timeout_ms or 120000}ms",
                rawResult=raw,
            )

        elapsed_ms = int((time.time() - started) * 1000)
        raw = {
            "command": command,
            "cwd": cwd,
            "timeoutMs": timeout_ms or 120000,
            "exitCode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "durationMs": elapsed_ms,
            "timedOut": False,
        }
        if completed.returncode == 0:
            return BashResult(
                state="output-available",
                visibleResult=self._build_visible_result(completed.stdout, completed.stderr),
                errorText=None,
                rawResult=raw,
            )

        error_text = completed.stderr.strip() or f"Bash exit code {completed.returncode}"
        return BashResult(
            state="output-error",
            visibleResult=None,
            errorText=error_text,
            rawResult=raw,
        )

    @staticmethod
    def _build_visible_result(stdout: str, stderr: str) -> str:
        out = stdout.strip()
        err = stderr.strip()
        if out and err:
            return f"{out}\n{err}"
        if out:
            return out
        if err:
            return err
        return "(empty output)"
