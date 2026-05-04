#!/usr/bin/env python3
"""Verify sandbox implementation branch baseline and safety constraints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_DOC_NEEDLES = [
    "sandbox writes are not implemented",
    "rollback execution is not implemented",
    "authoritative writes are not implemented",
    "execution hold remains active",
]

BASELINE_FALSE_FIELDS = {
    "implementation_available": False,
    "sandbox_write_implementation_allowed": False,
    "rollback_execution_implementation_allowed": False,
    "authoritative_write_allowed": False,
    "production_paths_allowed": False,
    "product_resolution_allowed": False,
    "asset_id_claims_allowed": False,
    "o3de_editor_allowed": False,
    "asset_processor_allowed": False,
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    root = repo_root()
    failures: List[str] = []

    baseline_path = root / "docs" / "audits" / "sandbox_implementation_branch_baseline.json"
    baseline_doc_path = root / "docs" / "audits" / "SANDBOX-IMPLEMENTATION-BRANCH-BASELINE.md"

    if not baseline_path.exists():
        print(f"FAIL: missing baseline JSON: {baseline_path}")
        return 2

    if not baseline_doc_path.exists():
        print(f"FAIL: missing baseline doc: {baseline_doc_path}")
        return 2

    try:
        baseline = load_json(baseline_path)
    except Exception as exc:
        print(f"FAIL: unable to parse baseline JSON: {exc}")
        return 2

    if baseline.get("baseline_name") != "sandbox-implementation-branch-baseline":
        failures.append("baseline_name must be sandbox-implementation-branch-baseline")
    if baseline.get("baseline_type") != "implementation_branch_safety_baseline":
        failures.append("baseline_type must be implementation_branch_safety_baseline")
    if baseline.get("branch_name") != "codex/sandbox-implementation-branch-baseline":
        failures.append("branch_name must be codex/sandbox-implementation-branch-baseline")
    if baseline.get("base_branch") != "main":
        failures.append("base_branch must be main")

    for key, expected in BASELINE_FALSE_FIELDS.items():
        if baseline.get(key) is not expected:
            failures.append(f"{key} must be {str(expected).lower()}")

    if baseline.get("implementation_branch_created_in_this_baseline") is not True:
        failures.append("implementation_branch_created_in_this_baseline must be true")

    decision_rel = baseline.get("decision_record")
    if not isinstance(decision_rel, str) or not decision_rel:
        failures.append("decision_record must be a non-empty string")
        decision_rel = ""
    decision_path = root / decision_rel if decision_rel else None
    decision: Dict[str, Any] = {}

    if decision_path is None or not decision_path.exists():
        failures.append("decision_record path must exist")
    else:
        try:
            decision = load_json(decision_path)
        except Exception as exc:
            failures.append(f"unable to parse decision_record JSON: {exc}")

    if decision:
        if decision.get("decision_status") != baseline.get("decision_status_required"):
            failures.append("decision_status does not match decision_status_required")
        if decision.get("implementation_branch_creation_allowed") is not baseline.get(
            "implementation_branch_creation_allowed_required"
        ):
            failures.append(
                "implementation_branch_creation_allowed does not match implementation_branch_creation_allowed_required"
            )
        if decision.get("execution_hold_status") != baseline.get("execution_hold_status_required"):
            failures.append("execution_hold_status does not match execution_hold_status_required")
        if decision.get("implementation_branch_created") is not baseline.get(
            "implementation_branch_created_in_decision_record"
        ):
            failures.append(
                "implementation_branch_created does not match implementation_branch_created_in_decision_record"
            )

    required_docs = baseline.get("required_docs", [])
    if not isinstance(required_docs, list):
        failures.append("required_docs must be an array")
        required_docs = []
    for rel in required_docs:
        if not isinstance(rel, str) or not rel:
            failures.append("required_docs entries must be non-empty strings")
            continue
        if not (root / rel).exists():
            failures.append(f"required doc missing: {rel}")

    required_absent_files = baseline.get("required_absent_files", [])
    if not isinstance(required_absent_files, list):
        failures.append("required_absent_files must be an array")
        required_absent_files = []
    for rel in required_absent_files:
        if not isinstance(rel, str) or not rel:
            failures.append("required_absent_files entries must be non-empty strings")
            continue
        if (root / rel).exists():
            failures.append(f"forbidden file exists: {rel}")

    doc_text = baseline_doc_path.read_text(encoding="utf-8-sig").lower()
    for needle in REQUIRED_DOC_NEEDLES:
        if needle not in doc_text:
            failures.append(f"required baseline language missing: {needle}")

    if failures:
        print("FAIL: sandbox implementation branch baseline verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox implementation branch baseline verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
