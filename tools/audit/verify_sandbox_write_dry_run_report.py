#!/usr/bin/env python3
"""Verify a planning-only sandbox write dry-run report artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


DRIVE_PATH_RE = re.compile(r"^[a-zA-Z]:[\\/]")
ALLOWED_STATUS = {"dry_run_ready", "dry_run_blocked", "dry_run_incomplete"}
REQUIRED_FIELDS = [
    "schema_version",
    "dry_run_report_id",
    "sandbox_write_plan_id",
    "sandbox_id",
    "status",
    "checks",
    "blockers",
    "warnings",
    "target_manifest_copy",
    "rollback_artifact",
    "proposed_changes_count",
    "forbidden_changes_count",
    "safety",
    "generated_at_utc",
]
REQUIRED_SAFETY = {
    "dry_run_only": True,
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
    parser = argparse.ArgumentParser(description="Verify planning-only sandbox write dry-run report JSON.")
    parser.add_argument("--report", required=True, help="Path to sandbox write dry-run report JSON")
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_slashes(value: str) -> str:
    return value.replace("\\", "/")


def validate_sandbox_relative_path(root: Path, sandbox_root_rel: str, candidate: str) -> Tuple[bool, str]:
    raw = candidate.strip()
    if not raw:
        return False, "path is empty"

    if raw.startswith("\\\\") or raw.startswith("//"):
        return False, "UNC path rejected"

    if DRIVE_PATH_RE.match(raw):
        return False, "Windows drive path rejected"

    candidate_path = Path(raw)
    if candidate_path.is_absolute():
        return False, "absolute path rejected"

    normalized = normalize_slashes(raw)
    if ".." in candidate_path.parts or "/../" in f"/{normalized}/":
        return False, "parent traversal rejected"

    sandbox_abs = (root / sandbox_root_rel).resolve()
    resolved_abs = (root / candidate_path).resolve()
    if sandbox_abs not in resolved_abs.parents and resolved_abs != sandbox_abs:
        return False, "path is outside sandbox root"

    return True, "path is inside sandbox root"


def main() -> int:
    args = parse_args()
    root = repo_root()

    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = (root / report_path).resolve()

    if not report_path.exists():
        print(f"FAIL: missing sandbox write dry-run report JSON: {report_path}")
        return 2

    try:
        report = load_json(report_path)
    except Exception as exc:
        print(f"FAIL: unable to parse sandbox write dry-run report JSON: {exc}")
        return 2

    failures: List[str] = []

    for field in REQUIRED_FIELDS:
        if field not in report:
            failures.append(f"missing required field: {field}")

    status = report.get("status")
    if status not in ALLOWED_STATUS:
        failures.append("status must be one of: dry_run_ready, dry_run_blocked, dry_run_incomplete")

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

    target_manifest_copy = report.get("target_manifest_copy")
    if not isinstance(target_manifest_copy, str):
        failures.append("target_manifest_copy must be a string")
    else:
        ok, reason = validate_sandbox_relative_path(root, "examples/sandbox", target_manifest_copy)
        if not ok:
            failures.append(f"target_manifest_copy invalid: {reason}")

    for int_field in ["proposed_changes_count", "forbidden_changes_count"]:
        value = report.get(int_field)
        if not isinstance(value, int) or value < 0:
            failures.append(f"{int_field} must be a non-negative integer")

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

    if status == "dry_run_ready":
        if blockers:
            failures.append("dry_run_ready requires blockers to be empty")

        all_checks_passed = True
        for idx, check in enumerate(checks):
            if not isinstance(check, dict):
                all_checks_passed = False
                failures.append(f"checks[{idx}] must be an object")
                continue
            if check.get("passed") is not True:
                all_checks_passed = False

        if not all_checks_passed:
            failures.append("dry_run_ready requires all checks.passed values to be true")

        if "Dry-run ready does not authorize execution." not in warnings:
            failures.append(
                "dry_run_ready requires warning: Dry-run ready does not authorize execution."
            )

    if failures:
        print("FAIL: sandbox write dry-run report verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox write dry-run report verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
