#!/usr/bin/env python3
"""Verify a planning-only sandbox write approval artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_APPROVAL_FIELDS = [
    "schema_version",
    "approval_id",
    "approval_scope",
    "approved_dry_run_report_id",
    "approved_sandbox_write_plan_id",
    "approved_by",
    "approved_at_utc",
    "approval_reason",
    "safety",
]
REQUIRED_SAFETY = {
    "approval_only": True,
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
    parser = argparse.ArgumentParser(description="Verify planning-only sandbox write approval JSON.")
    parser.add_argument("--approval", required=True, help="Path to sandbox write approval JSON")
    parser.add_argument("--dry-run-report", required=True, help="Path to sandbox write dry-run report JSON")
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

    approval_path = resolve_input_path(root, args.approval)
    dry_run_path = resolve_input_path(root, args.dry_run_report)

    if not approval_path.exists():
        print(f"FAIL: missing approval JSON: {approval_path}")
        return 2
    if not dry_run_path.exists():
        print(f"FAIL: missing dry-run report JSON: {dry_run_path}")
        return 2

    try:
        approval = load_json(approval_path)
    except Exception as exc:
        print(f"FAIL: unable to parse approval JSON: {exc}")
        return 2

    try:
        dry_run = load_json(dry_run_path)
    except Exception as exc:
        print(f"FAIL: unable to parse dry-run report JSON: {exc}")
        return 2

    failures: List[str] = []

    for field in REQUIRED_APPROVAL_FIELDS:
        if field not in approval:
            failures.append(f"missing required approval field: {field}")

    if approval.get("approval_scope") != "sandbox_only_planning":
        failures.append("approval_scope must equal sandbox_only_planning")

    if approval.get("approved_dry_run_report_id") != dry_run.get("dry_run_report_id"):
        failures.append("approved_dry_run_report_id must match dry_run_report.dry_run_report_id")

    if approval.get("approved_sandbox_write_plan_id") != dry_run.get("sandbox_write_plan_id"):
        failures.append("approved_sandbox_write_plan_id must match dry_run_report.sandbox_write_plan_id")

    safety = approval.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("safety must be an object")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                failures.append(f"safety.{key} must be {str(expected).lower()}")

    if failures:
        print("FAIL: sandbox write approval verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox write approval verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
