#!/usr/bin/env python3
"""Create a read-only authoritative write protocol proposal from a dry-run plan."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


VALID_PLAN_STATUSES = {"dry_run_ready", "dry_run_incomplete", "dry_run_blocked"}
VALID_PROPOSAL_STATUSES = {"proposal_only", "approval_required", "blocked"}
REQUIRED_APPROVAL_FIELDS = [
    "approval_id",
    "approved_by",
    "approved_at_utc",
    "approval_reason",
    "approved_plan_id",
    "approval_scope",
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
    parser = argparse.ArgumentParser(description="Propose a future authoritative resolver write protocol.")
    parser.add_argument("--plan", required=True, help="Path to authoritative dry-run plan JSON")
    parser.add_argument("--output", required=True, help="Path to output write protocol proposal JSON")
    return parser.parse_args()


def as_list_of_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def minimal_validate_input_plan(plan: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for field in ("plan_id", "status"):
        if field not in plan:
            errors.append(f"Input plan missing required field: {field}")
    status = str(plan.get("status", "")).strip()
    if status not in VALID_PLAN_STATUSES:
        errors.append(f"Input plan status is invalid: {status!r}")
    return errors


def minimal_validate_proposal(proposal: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required_top = [
        "schema_version",
        "proposal_id",
        "status",
        "source_plan_id",
        "proposed_write_fields",
        "required_approval",
        "forbidden_until_approved",
        "safety",
    ]
    for field in required_top:
        if field not in proposal:
            errors.append(f"Proposal missing required field: {field}")

    status = str(proposal.get("status", "")).strip()
    if status not in VALID_PROPOSAL_STATUSES:
        errors.append(f"Proposal status is invalid: {status!r}")

    required_approval = proposal.get("required_approval")
    if not isinstance(required_approval, dict):
        errors.append("required_approval must be an object")
    else:
        required_fields = as_list_of_strings(required_approval.get("required_fields"))
        for field in REQUIRED_APPROVAL_FIELDS:
            if field not in required_fields:
                errors.append(f"required_approval.required_fields missing: {field}")

    safety = proposal.get("safety")
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

    plan_path = resolve_path(repo_root, args.plan)
    output_path = resolve_path(repo_root, args.output)

    if not plan_path.exists():
        print(f"FAIL: plan file not found: {plan_path}")
        return 2

    try:
        plan = load_json(plan_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    input_errors = minimal_validate_input_plan(plan)
    if input_errors:
        print("FAIL: input plan validation failed.")
        for error in input_errors:
            print(f"  - {error}")
        return 2

    plan_id = str(plan.get("plan_id", "")).strip()
    plan_status = str(plan.get("status", "")).strip()
    plan_missing_proofs = as_list_of_strings(plan.get("missing_proofs"))

    proposal_status = "approval_required" if plan_status == "dry_run_ready" else "blocked"

    proposal = {
        "schema_version": "1.0.0",
        "proposal_id": f"authoritative-write-proposal-{plan_id}",
        "status": proposal_status,
        "source_plan_id": plan_id,
        "source_plan_status": plan_status,
        "source_plan_missing_proofs": plan_missing_proofs,
        "proposed_write_fields": {
            "manifest.o3de.products.resolved": {
                "description": "Final authoritative resolution flag.",
                "type": "boolean",
                "proposed_value": True,
                "write_now": False,
            },
            "manifest.o3de.products.resolution_mode": {
                "description": "Authoritative resolution mode identifier.",
                "type": "string",
                "example_value": "authoritative",
                "write_now": False,
            },
            "manifest.o3de.products.resolved_at_utc": {
                "description": "Timestamp when authoritative resolution is written.",
                "type": "string",
                "format": "date-time",
                "write_now": False,
            },
            "manifest.o3de.products.source_identity": {
                "description": "Source identity evidence summary used for authoritative write.",
                "type": "object",
                "write_now": False,
            },
            "manifest.o3de.products.resolved_products[]": {
                "description": "Resolved product records with platform/type/proof links.",
                "type": "array",
                "write_now": False,
            },
            "manifest.o3de.products.proof_refs": {
                "description": "Proof artifacts used for write decision.",
                "type": "array",
                "write_now": False,
            },
            "manifest.o3de.products.operator_approval": {
                "description": "Validated operator approval artifact.",
                "type": "object",
                "write_now": False,
            },
        },
        "required_approval": {
            "required_fields": REQUIRED_APPROVAL_FIELDS,
        },
        "forbidden_until_approved": [
            "resolved true",
            "Asset IDs",
            "prefab publication",
            "entity spawn",
            "product promotion",
        ],
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

    proposal_errors = minimal_validate_proposal(proposal)
    if proposal_errors:
        print("FAIL: proposal validation failed.")
        for error in proposal_errors:
            print(f"  - {error}")
        return 2

    try:
        write_json(output_path, proposal)
    except Exception as exc:
        print(f"FAIL: unable to write proposal output: {exc}")
        return 2

    print(
        "PASS: authoritative write protocol proposal created. "
        f"status={proposal_status} source_plan_status={plan_status} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
