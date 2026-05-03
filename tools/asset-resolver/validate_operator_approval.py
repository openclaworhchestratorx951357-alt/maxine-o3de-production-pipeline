#!/usr/bin/env python3
"""Validate read-only operator approval artifacts against write proposal requirements."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


VALIDATION_STATUSES = {
    "approval_valid",
    "approval_invalid",
    "approval_expired",
    "proposal_not_approvable",
}
EXPECTED_APPROVAL_FIELDS = [
    "approval_id",
    "proposal_id",
    "approved_by",
    "approved_at_utc",
    "approval_reason",
    "approved_plan_id",
    "approval_scope",
    "approved_write_fields",
    "expires_at_utc",
]


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
    parser = argparse.ArgumentParser(description="Validate operator approval artifact against write proposal.")
    parser.add_argument("--proposal", required=True, help="Path to write protocol proposal JSON")
    parser.add_argument("--approval", required=True, help="Path to operator approval JSON")
    parser.add_argument("--output", required=True, help="Path to output validation report JSON")
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


def parse_timestamp(raw: Any) -> dt.datetime | None:
    text = safe_text(raw).strip()
    if not text:
        return None
    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    else:
        parsed = parsed.astimezone(dt.timezone.utc)
    return parsed


def check_item(check_id: str, passed: bool, message: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": check_id,
        "passed": bool(passed),
        "message": message,
    }
    if details is not None:
        payload["details"] = details
    return payload


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    proposal_path = resolve_path(repo_root, args.proposal)
    approval_path = resolve_path(repo_root, args.approval)
    output_path = resolve_path(repo_root, args.output)

    if not proposal_path.exists():
        print(f"FAIL: proposal file not found: {proposal_path}")
        return 2
    if not approval_path.exists():
        print(f"FAIL: approval file not found: {approval_path}")
        return 2

    try:
        proposal = load_json(proposal_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    try:
        approval = load_json(approval_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    checks: List[Dict[str, Any]] = []
    blockers: List[str] = []

    proposal_status = safe_text(proposal.get("status")).strip()
    proposal_id = safe_text(proposal.get("proposal_id")).strip()
    source_plan_id = safe_text(proposal.get("source_plan_id")).strip()
    approval_id = safe_text(approval.get("approval_id")).strip()

    is_approvable = proposal_status == "approval_required"
    checks.append(
        check_item(
            "proposal_status_approvable",
            is_approvable,
            "Proposal status must be approval_required.",
            {"proposal_status": proposal_status},
        )
    )
    if not is_approvable:
        blockers.append("proposal_not_approvable")

    missing_fields: List[str] = []
    for field in EXPECTED_APPROVAL_FIELDS:
        if field not in approval:
            missing_fields.append(field)
            continue
        if field == "approved_write_fields":
            if not isinstance(approval.get(field), list):
                missing_fields.append(field)
            elif len(as_list_of_strings(approval.get(field))) == 0:
                missing_fields.append(field)
        else:
            if not safe_text(approval.get(field)).strip():
                missing_fields.append(field)

    required_fields_ok = len(missing_fields) == 0
    checks.append(
        check_item(
            "approval_required_fields",
            required_fields_ok,
            "Approval artifact must include all required non-empty fields.",
            {"missing_or_invalid_fields": missing_fields},
        )
    )
    if not required_fields_ok:
        blockers.append("missing_required_approval_fields")

    proposal_id_match = safe_text(approval.get("proposal_id")).strip() == proposal_id and proposal_id != ""
    checks.append(
        check_item(
            "approval_proposal_id_match",
            proposal_id_match,
            "Approval proposal_id must match proposal.proposal_id.",
            {
                "proposal_id": proposal_id,
                "approval_proposal_id": safe_text(approval.get("proposal_id")).strip(),
            },
        )
    )
    if not proposal_id_match:
        blockers.append("proposal_id_mismatch")

    approved_plan_id_match = safe_text(approval.get("approved_plan_id")).strip() == source_plan_id and source_plan_id != ""
    checks.append(
        check_item(
            "approval_plan_id_match",
            approved_plan_id_match,
            "Approval approved_plan_id must match proposal.source_plan_id.",
            {
                "source_plan_id": source_plan_id,
                "approved_plan_id": safe_text(approval.get("approved_plan_id")).strip(),
            },
        )
    )
    if not approved_plan_id_match:
        blockers.append("approved_plan_id_mismatch")

    approval_scope = safe_text(approval.get("approval_scope")).strip()
    scope_ok = approval_scope != ""
    checks.append(
        check_item(
            "approval_scope_non_empty",
            scope_ok,
            "Approval scope must be non-empty.",
            {"approval_scope": approval_scope},
        )
    )
    if not scope_ok:
        blockers.append("approval_scope_missing")

    proposed_fields = set((proposal.get("proposed_write_fields") or {}).keys()) if isinstance(proposal.get("proposed_write_fields"), dict) else set()
    approved_fields = as_list_of_strings(approval.get("approved_write_fields"))
    unknown_approved_fields = sorted([field for field in approved_fields if field not in proposed_fields])
    write_fields_ok = len(approved_fields) > 0 and len(unknown_approved_fields) == 0
    checks.append(
        check_item(
            "approved_write_fields_subset",
            write_fields_ok,
            "approved_write_fields must reference only proposal proposed_write_fields keys.",
            {
                "approved_write_fields": approved_fields,
                "unknown_approved_fields": unknown_approved_fields,
            },
        )
    )
    if not write_fields_ok:
        blockers.append("approved_write_fields_invalid")

    expires_at = parse_timestamp(approval.get("expires_at_utc"))
    now_utc = dt.datetime.now(dt.timezone.utc)
    not_expired = expires_at is not None and expires_at > now_utc
    checks.append(
        check_item(
            "approval_not_expired",
            not_expired,
            "Approval expires_at_utc must be in the future.",
            {
                "expires_at_utc": safe_text(approval.get("expires_at_utc")),
                "now_utc": now_utc.isoformat(),
            },
        )
    )
    if not not_expired:
        blockers.append("approval_expired")

    safety = approval.get("safety", {})
    if not isinstance(safety, dict):
        safety = {}
    expected_safety = {
        "read_only": True,
        "executes_writes": False,
        "marks_products_resolved": False,
        "claims_asset_ids": False,
        "runs_o3de_editor": False,
        "runs_asset_processor": False,
        "spawns_entities": False,
        "publishes_prefabs": False,
    }
    safety_mismatches: List[str] = []
    for key, expected in expected_safety.items():
        if safety.get(key) is not expected:
            safety_mismatches.append(f"{key}={safe_text(safety.get(key))}")

    safety_ok = len(safety_mismatches) == 0
    checks.append(
        check_item(
            "approval_safety_non_executing",
            safety_ok,
            "Approval safety flags must remain read-only and non-executing.",
            {"mismatches": safety_mismatches},
        )
    )
    if not safety_ok:
        blockers.append("approval_safety_violation")

    if not is_approvable:
        status = "proposal_not_approvable"
    elif not not_expired:
        status = "approval_expired"
    elif any(b for b in blockers if b != "approval_expired"):
        status = "approval_invalid"
    else:
        status = "approval_valid"

    if status not in VALIDATION_STATUSES:
        status = "approval_invalid"

    report = {
        "schema_version": "1.0.0",
        "validation_id": f"approval-validation-{proposal_id or 'unknown-proposal'}-{approval_id or 'unknown-approval'}",
        "status": status,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "checks": checks,
        "blockers": blockers,
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
        print(f"FAIL: unable to write validation report: {exc}")
        return 2

    print(
        "PASS: operator approval validation report created. "
        f"status={status} blocker_count={len(blockers)} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
