#!/usr/bin/env python3
"""Verify a planning-only sandbox execution hold artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_HOLD_FIELDS = [
    "schema_version",
    "hold_id",
    "hold_status",
    "hold_reason",
    "held_at_utc",
    "held_by",
    "blocked_commands",
    "safety",
]
REQUIRED_BLOCKED_COMMANDS = [
    "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1",
    "scripts/powershell/Invoke-MaxineSandboxRollback.ps1",
    "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1",
]
REQUIRED_SAFETY = {
    "execution_hold_active": True,
    "implementation_available": False,
    "sandbox_write_allowed": False,
    "rollback_execution_allowed": False,
    "authoritative_write_allowed": False,
    "production_paths_allowed": False,
    "product_resolution_allowed": False,
    "asset_id_claims_allowed": False,
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify planning-only sandbox execution hold JSON.")
    parser.add_argument("--hold", required=True, help="Path to sandbox execution hold JSON")
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_input_path(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (root / path).resolve()
    return path


def main() -> int:
    args = parse_args()
    root = repo_root()

    hold_path = resolve_input_path(root, args.hold)
    if not hold_path.exists():
        print(f"FAIL: missing execution hold JSON: {hold_path}")
        return 2

    try:
        hold = load_json(hold_path)
    except Exception as exc:
        print(f"FAIL: unable to parse execution hold JSON: {exc}")
        return 2

    failures: List[str] = []

    for field in REQUIRED_HOLD_FIELDS:
        if field not in hold:
            failures.append(f"missing required hold field: {field}")

    if hold.get("hold_status") != "hold_active":
        failures.append("hold_status must be hold_active for this phase")

    blocked_commands = hold.get("blocked_commands")
    if not isinstance(blocked_commands, list):
        failures.append("blocked_commands must be an array")
        blocked_commands = []

    for required_command in REQUIRED_BLOCKED_COMMANDS:
        if required_command not in blocked_commands:
            failures.append(f"blocked_commands missing required value: {required_command}")

    for required_command in REQUIRED_BLOCKED_COMMANDS:
        if (root / required_command).exists():
            failures.append(f"blocked command file must be absent: {required_command}")

    safety = hold.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("safety must be an object")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                failures.append(f"safety.{key} must be {str(expected).lower()}")

    if failures:
        print("FAIL: sandbox execution hold verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox execution hold verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
