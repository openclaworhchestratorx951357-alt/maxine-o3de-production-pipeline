#!/usr/bin/env python3
"""Verify a planning-only sandbox write plan artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


DRIVE_PATH_RE = re.compile(r"^[a-zA-Z]:[\\/]")
REQUIRED_FIELDS = [
    "schema_version",
    "sandbox_write_plan_id",
    "sandbox_id",
    "design_only",
    "target_manifest_copy",
    "pre_write_snapshot",
    "rollback_artifact",
    "operator_approval_ref",
    "execution_gate_ref",
    "proposed_changes",
    "forbidden_changes",
    "safety",
]
REQUIRED_FORBIDDEN_CHANGES = {
    "o3de.products.resolved",
    "o3de.products.asset_id",
    "o3de.products.resolved_products",
}
REQUIRED_SAFETY = {
    "sandbox_only": True,
    "implementation_available": False,
    "sandbox_write_allowed": False,
    "rollback_execution_required": True,
    "rollback_execution_implemented": False,
    "authoritative_write_allowed": False,
    "production_paths_allowed": False,
    "product_resolution_allowed": False,
    "asset_id_claims_allowed": False,
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify planning-only sandbox write plan JSON.")
    parser.add_argument("--plan", required=True, help="Path to sandbox write plan JSON")
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

    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = (root / plan_path).resolve()

    if not plan_path.exists():
        print(f"FAIL: missing sandbox write plan JSON: {plan_path}")
        return 2

    try:
        plan = load_json(plan_path)
    except Exception as exc:
        print(f"FAIL: unable to parse sandbox write plan JSON: {exc}")
        return 2

    failures: List[str] = []

    for field in REQUIRED_FIELDS:
        if field not in plan:
            failures.append(f"missing required field: {field}")

    target_manifest_copy = plan.get("target_manifest_copy")
    if not isinstance(target_manifest_copy, str):
        failures.append("target_manifest_copy must be a string")
    else:
        ok, reason = validate_sandbox_relative_path(root, "examples/sandbox", target_manifest_copy)
        if not ok:
            failures.append(f"target_manifest_copy invalid: {reason}")

    proposed_changes = plan.get("proposed_changes")
    if not isinstance(proposed_changes, list):
        failures.append("proposed_changes must be an array")
        proposed_changes = []

    forbidden_changes = plan.get("forbidden_changes")
    if not isinstance(forbidden_changes, list):
        failures.append("forbidden_changes must be an array")
        forbidden_changes = []
    else:
        missing_forbidden = REQUIRED_FORBIDDEN_CHANGES.difference(set(forbidden_changes))
        for missing in sorted(missing_forbidden):
            failures.append(f"forbidden_changes missing required value: {missing}")

    for idx, change in enumerate(proposed_changes):
        if not isinstance(change, dict):
            failures.append(f"proposed_changes[{idx}] must be an object")
            continue

        field_value = change.get("field")
        if not isinstance(field_value, str) or not field_value.strip():
            failures.append(f"proposed_changes[{idx}].field must be a non-empty string")
            continue

        lowered = field_value.lower()
        if lowered.startswith("o3de.products"):
            failures.append(f"proposed_changes[{idx}].field must not start with o3de.products")

        if "asset_id" in lowered:
            failures.append(
                f"proposed_changes[{idx}].field must not contain asset_id unless listed in forbidden_changes"
            )

    safety = plan.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("safety must be an object")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                failures.append(f"safety.{key} must be {str(expected).lower()}")

    if plan.get("design_only") is not True:
        failures.append("design_only must be true")

    if failures:
        print("FAIL: sandbox write plan verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox write plan verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
