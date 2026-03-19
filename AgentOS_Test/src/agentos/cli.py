from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agentos.control_plane import AosError, ControlPlane, error_response


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="aos", add_help=True)
    parser.add_argument("op", help="AOSCP operation, e.g. agent.create")
    parser.add_argument("--input", default="{}", help="JSON object payload")
    parser.add_argument("--runtime-root", default="runtime", help="Runtime storage root")
    return parser.parse_args(argv)


def _parse_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AosError("INVALID_JSON", f"Invalid --input JSON: {e.msg}") from e
    if not isinstance(payload, dict):
        raise AosError("INVALID_INPUT", "Input payload must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    args = parse_args(argv)
    op = args.op
    try:
        payload = _parse_payload(args.input)
        cp = ControlPlane(runtime_root=Path(args.runtime_root))
        result = cp.call(op=op, payload=payload)
        sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
        return 0
    except AosError as e:
        sys.stdout.write(json.dumps(error_response(op=op, err=e), ensure_ascii=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
