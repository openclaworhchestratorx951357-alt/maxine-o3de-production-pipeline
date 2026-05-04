#!/usr/bin/env python3
"""Verify a planning-only sandbox write final preflight report artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_STATUS = {"preflight_ready", "preflight_blocked", "preflight_incomplete"}
REQUIRED_FIELDS = [
    "schema_version",
    "preflight_report_id",
    "sandbox_write_plan_id",
    "dry_run_report_id",
    "approval_gate_report_id",
    "sandbox_id",
    "status",
    "checks",
    "blockers",
    "warnings",
    "rollback_artifact",
    "safety",
    "generated_at_utc",
]
REQUIRED_SAFETY = {
    "preflight_only": True,
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
    parser = argparse.ArgumentParser(description="Verify planning-only sandbox write final preflight report JSON.")
    parser.add_argument("--report", required=True, help="Path to sandbox write final preflight report JSON")
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
    report_path = resolve_input_path(root, args.report)

    if not report_path.exists():
        print(f"FAIL: missing final preflight report JSON: {report_path}")
        return 2

    try:
        report = load_json(report_path)
    except Exception as exc:
        print(f"FAIL: unable to parse final preflight report JSON: {exc}")
        return 2

    failures: List[str] = []

    for field in REQUIRED_FIELDS:
        if field not in report:
            failures.append(f"missing required field: {field}")

    status = report.get("status")
    if status not in ALLOWED_STATUS:
        failures.append("status must be one of: preflight_ready, preflight_blocked, preflight_incomplete")

    checks = report.get("checks")
    if not isinstance(checks, list):
        failures.append("checks must be an array")
        checks = []

    blockers = report.get("blockers")
    if not isinstance(blockers, list):
        failures.append("blockers must be an array")
        blockers = []

    warnings = report.get("warnings")
    if not isinstance(warnings, list):
        failures.append("warnings must be an array")
        warnings = []

    rollback_artifact = report.get("rollback_artifact")
    if not isinstance(rollback_artifact, str) or not rollback_artifact.strip():
        failures.append("rollback_artifact must be a non-empty string")

    safety = report.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("safety must be an object")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                failures.append(f"safety.{key} must be {str(expected).lower()}")

        for forbidden_true_field in [
            "sandbox_write_allowed",
            "rollback_execution_allowed",
            "authoritative_write_allowed",
            "product_resolution_allowed",
            "asset_id_claims_allowed",
        ]:
            if safety.get(forbidden_true_field) is True:
                failures.append(f"safety.{forbidden_true_field} must not be true")

    if status == "preflight_ready":
        if blockers:
            failures.append("preflight_ready requires blockers to be empty")

        all_checks_passed = True
        for idx, check in enumerate(checks):
            if not isinstance(check, dict):
                all_checks_passed = False
                failures.append(f"checks[{idx}] must be an object")
                continue
            if check.get("passed") is not True:
                all_checks_passed = False

        if not all_checks_passed:
            failures.append("preflight_ready requires all checks.passed values to be true")

        if "Preflight ready does not authorize execution." not in warnings:
            failures.append("preflight_ready requires warning: Preflight ready does not authorize execution.")

    if failures:
        print("FAIL: sandbox write final preflight report verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox write final preflight report verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
