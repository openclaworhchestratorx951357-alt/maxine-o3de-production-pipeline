#!/usr/bin/env python3
"""Build a read-only approved-write dry-run pre-write report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


PRE_WRITE_STATUSES = {"pre_write_ready", "pre_write_blocked", "pre_write_incomplete"}


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
    parser = argparse.ArgumentParser(description="Build pre-write report from proposal and approval validation.")
    parser.add_argument("--proposal", required=True, help="Path to write proposal JSON")
    parser.add_argument("--approval-validation", required=True, help="Path to approval validation report JSON")
    parser.add_argument("--output", required=True, help="Path to output pre-write report JSON")
    return parser.parse_args()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def as_list_of_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = safe_text(item).strip()
        if text:
            out.append(text)
    return out


def check_item(check_id: str, passed: bool, message: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": check_id,
        "passed": bool(passed),
        "message": message,
    }
    if details is not None:
        payload["details"] = details
    return payload


def extract_approved_write_fields(
    proposal: Dict[str, Any],
    approval_validation: Dict[str, Any],
) -> List[str]:
    checks = approval_validation.get("checks", [])
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict):
                continue
            if safe_text(check.get("id")).strip() != "approved_write_fields_subset":
                continue
            details = check.get("details", {})
            if not isinstance(details, dict):
                continue
            fields = as_list_of_strings(details.get("approved_write_fields"))
            if fields:
                return fields

    proposed_fields = proposal.get("proposed_write_fields", {})
    if isinstance(proposed_fields, dict):
        return [safe_text(key).strip() for key in proposed_fields.keys() if safe_text(key).strip()]
    return []


def safety_non_executing(proposal: Dict[str, Any], approval_validation: Dict[str, Any]) -> bool:
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

    proposal_safety = proposal.get("safety", {})
    if not isinstance(proposal_safety, dict):
        proposal_safety = {}
    approval_safety = approval_validation.get("safety", {})
    if not isinstance(approval_safety, dict):
        approval_safety = {}

    for key, expected_value in expected.items():
        if proposal_safety.get(key) is not expected_value:
            return False
        if approval_safety.get(key) is not expected_value:
            return False
    return True


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    proposal_path = resolve_path(repo_root, args.proposal)
    approval_validation_path = resolve_path(repo_root, args.approval_validation)
    output_path = resolve_path(repo_root, args.output)

    if not proposal_path.exists():
        print(f"FAIL: proposal file not found: {proposal_path}")
        return 2
    if not approval_validation_path.exists():
        print(f"FAIL: approval validation file not found: {approval_validation_path}")
        return 2

    try:
        proposal = load_json(proposal_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    try:
        approval_validation = load_json(approval_validation_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    proposal_status = safe_text(proposal.get("status")).strip()
    proposal_id = safe_text(proposal.get("proposal_id")).strip() or "unknown-proposal"
    approval_validation_status = safe_text(approval_validation.get("status")).strip()
    approval_validation_id = safe_text(approval_validation.get("validation_id")).strip() or "unknown-validation"

    approved_write_fields = extract_approved_write_fields(proposal, approval_validation)

    proposal_approval_required = proposal_status == "approval_required"
    approval_validation_valid = approval_validation_status == "approval_valid"
    safety_ok = safety_non_executing(proposal, approval_validation)
    write_fields_declared = len(approved_write_fields) > 0

    final_checks = [
        check_item(
            "proposal_approval_required",
            proposal_approval_required,
            "Proposal status must be approval_required for pre-write readiness.",
            {"proposal_status": proposal_status},
        ),
        check_item(
            "approval_validation_valid",
            approval_validation_valid,
            "Approval validation status must be approval_valid for pre-write readiness.",
            {"approval_validation_status": approval_validation_status},
        ),
        check_item(
            "safety_non_executing",
            safety_ok,
            "Proposal and approval validation safety blocks must remain non-executing.",
        ),
        check_item(
            "write_fields_declared",
            write_fields_declared,
            "Approved write fields must be declared.",
            {"approved_write_fields": approved_write_fields},
        ),
    ]

    blocked_reasons: List[str] = []

    if proposal_status == "blocked":
        blocked_reasons.append("proposal_status_blocked")
    if approval_validation_status == "proposal_not_approvable":
        blocked_reasons.append("approval_validation_proposal_not_approvable")

    if not proposal_approval_required:
        blocked_reasons.append("proposal_not_approval_required")
    if not approval_validation_valid:
        blocked_reasons.append("approval_validation_not_valid")
    if not safety_ok:
        blocked_reasons.append("safety_non_executing_failed")
    if not write_fields_declared:
        blocked_reasons.append("approved_write_fields_missing")

    if proposal_status == "approval_required" and approval_validation_status == "approval_valid":
        status = "pre_write_ready"
    elif proposal_status == "blocked" or approval_validation_status == "proposal_not_approvable":
        status = "pre_write_blocked"
    else:
        status = "pre_write_incomplete"

    if status not in PRE_WRITE_STATUSES:
        status = "pre_write_incomplete"

    report = {
        "schema_version": "1.0.0",
        "report_id": f"pre-write-report-{proposal_id}-{approval_validation_id}",
        "status": status,
        "proposal_id": proposal_id,
        "approval_validation_id": approval_validation_id,
        "approved_write_fields": approved_write_fields,
        "blocked_reasons": blocked_reasons,
        "final_checks": final_checks,
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

    try:
        write_json(output_path, report)
    except Exception as exc:
        print(f"FAIL: unable to write pre-write report: {exc}")
        return 2

    print(
        "PASS: pre-write report created. "
        f"status={status} proposal_status={proposal_status} "
        f"approval_validation_status={approval_validation_status} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
