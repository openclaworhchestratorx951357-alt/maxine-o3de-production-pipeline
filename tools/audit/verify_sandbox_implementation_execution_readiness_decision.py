#!/usr/bin/env python3
"""Verify sandbox implementation execution-readiness decision artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_DECISION_STATUS = {
    "execution_readiness_hold",
    "execution_readiness_rejected",
    "execution_readiness_review_pending",
}

REQUIRED_ALWAYS_FALSE = {
    "sandbox_write_implementation_allowed": False,
    "rollback_execution_implementation_allowed": False,
    "authoritative_write_allowed": False,
    "production_project_mutation_allowed": False,
    "o3de_editor_allowed": False,
    "asset_processor_allowed": False,
    "product_resolution_allowed": False,
    "asset_id_claims_allowed": False,
}

REQUIRED_DOC_NEEDLES = [
    "decision: execution_readiness_review_pending",
    "execution hold remains active",
    "sandbox write command remains absent",
    "rollback execution command remains absent",
    "authoritative write command remains absent",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    root = repo_root()
    failures: List[str] = []

    decision_doc = root / "docs/reviews/SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-DECISION.md"
    decision_json = root / "docs/reviews/sandbox_implementation_execution_readiness_decision.json"
    review_package = root / "docs/reviews/sandbox_implementation_execution_readiness_review_package.json"
    review_doc = root / "docs/reviews/SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-REVIEW.md"

    if not decision_doc.exists():
        print(f"FAIL: missing decision doc: {decision_doc}")
        return 2
    if not decision_json.exists():
        print(f"FAIL: missing decision JSON: {decision_json}")
        return 2
    if not review_package.exists():
        print(f"FAIL: missing review package JSON: {review_package}")
        return 2
    if not review_doc.exists():
        print(f"FAIL: missing review doc: {review_doc}")
        return 2

    try:
        decision = load_json(decision_json)
    except Exception as exc:
        print(f"FAIL: unable to parse decision JSON: {exc}")
        return 2

    status = decision.get("decision_status")
    if status not in ALLOWED_DECISION_STATUS:
        failures.append(
            "decision_status must be one of: execution_readiness_hold, execution_readiness_rejected, execution_readiness_review_pending"
        )

    if status == "execution_readiness_review_pending":
        if decision.get("execution_hold_transition_approved") is not True:
            failures.append(
                "execution_hold_transition_approved must be true when decision_status is execution_readiness_review_pending"
            )
        if decision.get("implementation_branch_execution_review_allowed") is not True:
            failures.append(
                "implementation_branch_execution_review_allowed must be true when decision_status is execution_readiness_review_pending"
            )
    else:
        if decision.get("execution_hold_transition_approved") is not False:
            failures.append(
                "execution_hold_transition_approved must be false for hold/rejected statuses"
            )
        if decision.get("implementation_branch_execution_review_allowed") is not False:
            failures.append(
                "implementation_branch_execution_review_allowed must be false for hold/rejected statuses"
            )

    if decision.get("execution_hold_current_status") != "hold_active":
        failures.append("execution_hold_current_status must be hold_active")
    if decision.get("execution_hold_next_status") != "hold_active":
        failures.append("execution_hold_next_status must be hold_active in this phase")

    for key, expected in REQUIRED_ALWAYS_FALSE.items():
        if decision.get(key) is not expected:
            failures.append(f"{key} must be {str(expected).lower()}")

    absent_files = decision.get("required_absent_files", [])
    if not isinstance(absent_files, list):
        failures.append("required_absent_files must be an array")
        absent_files = []
    for rel in absent_files:
        if not isinstance(rel, str) or not rel:
            failures.append("required_absent_files entries must be non-empty strings")
            continue
        if (root / rel).exists():
            failures.append(f"forbidden file exists: {rel}")

    if (
        decision.get("review_package")
        != "docs/reviews/sandbox_implementation_execution_readiness_review_package.json"
    ):
        failures.append(
            "review_package must reference docs/reviews/sandbox_implementation_execution_readiness_review_package.json"
        )

    if (
        decision.get("review_document")
        != "docs/reviews/SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-REVIEW.md"
    ):
        failures.append(
            "review_document must reference docs/reviews/SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-REVIEW.md"
        )

    hold_example = root / "examples/manifests/example-sandbox-execution-hold.json"
    if hold_example.exists():
        try:
            hold = load_json(hold_example)
            if hold.get("hold_status") != "hold_active":
                failures.append("execution hold example hold_status must be hold_active")
        except Exception as exc:
            failures.append(f"unable to parse execution hold example: {exc}")
    else:
        failures.append(
            "required hold example missing: examples/manifests/example-sandbox-execution-hold.json"
        )

    review_pkg = load_json(review_package)
    if review_pkg.get("default_decision_status") != "execution_readiness_hold":
        failures.append("execution-readiness review package default_decision_status must be execution_readiness_hold")

    review_decision = root / "docs/reviews/sandbox_implementation_decision.json"
    if review_decision.exists():
        try:
            impl_decision = load_json(review_decision)
            if impl_decision.get("execution_hold_status") != "hold_active":
                failures.append("implementation decision execution_hold_status must be hold_active")
        except Exception as exc:
            failures.append(f"unable to parse implementation decision record: {exc}")
    else:
        failures.append("required implementation decision record missing: docs/reviews/sandbox_implementation_decision.json")

    doc_text = decision_doc.read_text(encoding="utf-8-sig").lower()
    for needle in REQUIRED_DOC_NEEDLES:
        if needle not in doc_text:
            failures.append(f"required decision language missing: {needle}")

    if failures:
        print("FAIL: sandbox implementation execution-readiness decision verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox implementation execution-readiness decision verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
