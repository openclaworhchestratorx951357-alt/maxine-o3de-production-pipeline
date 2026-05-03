#!/usr/bin/env python3
"""Create a read-only execution gate policy evaluation from a pre-write report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


VALID_POLICY_STATUSES = {"policy_only", "not_executable"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def resolve_path(base: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to parse JSON from {path}: {exc}") from exc


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate final execution gate policy from pre-write report.")
    parser.add_argument("--pre-write-report", required=True, help="Path to pre-write report JSON")
    parser.add_argument("--output", required=True, help="Path to output execution gate policy JSON")
    return parser.parse_args()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def minimal_validate_output(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required = [
        "schema_version",
        "policy_id",
        "status",
        "required_preconditions",
        "manual_command_template",
        "rollback_requirements",
        "forbidden_actions",
        "implementation_available",
        "write_allowed",
        "safety",
    ]
    for field in required:
        if field not in payload:
            errors.append(f"Missing required field: {field}")

    status = safe_text(payload.get("status")).strip()
    if status not in VALID_POLICY_STATUSES:
        errors.append(f"Invalid status: {status!r}")

    if payload.get("implementation_available") is not False:
        errors.append("implementation_available must be false")
    if payload.get("write_allowed") is not False:
        errors.append("write_allowed must be false")

    safety = payload.get("safety", {})
    if not isinstance(safety, dict):
        errors.append("safety must be an object")
    else:
        expected = {
            "read_only": True,
            "executes_writes": False,
            "marks_products_resolved": False,
            "claims_asset_ids": False,
            "runs_o3de_editor": False,
            "runs_asset_processor": False,
            "spawns_entities": False,
            "publishes_prefabs": False,
        }
        for key, expected_value in expected.items():
            if safety.get(key) is not expected_value:
                errors.append(f"safety.{key} must be {str(expected_value).lower()}")

    return errors


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    pre_write_path = resolve_path(repo_root, args.pre_write_report)
    output_path = resolve_path(repo_root, args.output)

    if not pre_write_path.exists():
        print(f"FAIL: pre-write report file not found: {pre_write_path}")
        return 2

    try:
        pre_write_report = load_json(pre_write_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    pre_write_status = safe_text(pre_write_report.get("status")).strip()
    report_id = safe_text(pre_write_report.get("report_id")).strip() or "unknown-pre-write-report"

    status = "policy_only" if pre_write_status == "pre_write_ready" else "not_executable"

    required_preconditions = [
        "dry_run_plan_status_dry_run_ready",
        "write_proposal_status_approval_required",
        "approval_validation_status_approval_valid",
        "pre_write_report_status_pre_write_ready",
        "git_working_tree_clean",
        "protected_branch_policy_expected",
        "rollback_artifact_prepared",
        "explicit_manual_operator_command_required",
    ]

    manual_command_template = (
        "Invoke-MaxineAuthoritativeResolverWrite.ps1 "
        "-ManifestPath <path> "
        "-PreWriteReportPath <path> "
        "-RollbackPlanPath <path> "
        "-OperatorApprovalId <id> "
        "-ConfirmWrite"
    )

    rollback_requirements = {
        "pre_write_snapshot": True,
        "previous_manifest_copy": True,
        "fields_to_revert": True,
        "timestamp": True,
        "operator_identity": True,
        "rollback_command_proposal": True,
    }

    forbidden_actions = [
        "resolved_products_write",
        "asset_id_claims",
        "prefab_publication",
        "entity_spawn",
    ]

    evaluation = {
        "schema_version": "1.0.0",
        "policy_id": f"execution-gate-policy-{report_id}",
        "status": status,
        "pre_write_report_id": report_id,
        "required_preconditions": required_preconditions,
        "manual_command_template": manual_command_template,
        "rollback_requirements": rollback_requirements,
        "forbidden_actions": forbidden_actions,
        "implementation_available": False,
        "write_allowed": False,
        "safety": {
            "read_only": True,
            "executes_writes": False,
            "marks_products_resolved": False,
            "claims_asset_ids": False,
            "runs_o3de_editor": False,
            "runs_asset_processor": False,
            "spawns_entities": False,
            "publishes_prefabs": False,
        },
        "updated_utc": utc_now(),
    }

    output_errors = minimal_validate_output(evaluation)
    if output_errors:
        print("FAIL: generated execution gate policy failed validation.")
        for error in output_errors:
            print(f"  - {error}")
        return 2

    try:
        write_json(output_path, evaluation)
    except Exception as exc:
        print(f"FAIL: unable to write execution gate policy output: {exc}")
        return 2

    print(
        "PASS: execution gate policy evaluated. "
        f"status={status} pre_write_status={pre_write_status} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
