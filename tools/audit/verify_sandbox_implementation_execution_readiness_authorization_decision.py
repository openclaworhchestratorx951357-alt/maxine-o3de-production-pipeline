#!/usr/bin/env python3
"""Verify sandbox implementation execution-readiness authorization decision artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures, sanitize_required_absent


ALLOWED_DECISION_STATUS = {
    "execution_authorization_review_hold",
    "execution_authorization_review_rejected",
    "execution_authorization_review_pending_decision_preparation_only",
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
    "decision: execution_authorization_review_pending_decision_preparation_only",
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

    decision_doc = (
        root
        / "docs/reviews/SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-AUTHORIZATION-DECISION.md"
    )
    decision_json = (
        root / "docs/reviews/sandbox_implementation_execution_readiness_authorization_decision.json"
    )
    review_package = (
        root
        / "docs/reviews/sandbox_implementation_execution_readiness_authorization_review_package.json"
    )
    review_doc = (
        root / "docs/reviews/SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-AUTHORIZATION-REVIEW.md"
    )

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
            "decision_status must be one of: execution_authorization_review_hold, execution_authorization_review_rejected, execution_authorization_review_pending_decision_preparation_only"
        )

    accepted = status == "execution_authorization_review_pending_decision_preparation_only"
    if accepted:
        if decision.get("execution_hold_transition_approved") is not True:
            failures.append(
                "execution_hold_transition_approved must be true when decision_status is execution_authorization_review_pending_decision_preparation_only"
            )
        if decision.get("execution_authorization_decision_preparation_allowed") is not True:
            failures.append(
                "execution_authorization_decision_preparation_allowed must be true when decision_status is execution_authorization_review_pending_decision_preparation_only"
            )
    else:
        if decision.get("execution_hold_transition_approved") is not False:
            failures.append(
                "execution_hold_transition_approved must be false for hold/rejected statuses"
            )
        if decision.get("execution_authorization_decision_preparation_allowed") is not False:
            failures.append(
                "execution_authorization_decision_preparation_allowed must be false for hold/rejected statuses"
            )

    if decision.get("execution_hold_current_status") != "hold_active":
        failures.append("execution_hold_current_status must be hold_active")
    if decision.get("execution_hold_next_status") != "hold_active":
        failures.append("execution_hold_next_status must be hold_active in this phase")
    if decision.get("execution_hold_must_remain_active") is not True:
        failures.append("execution_hold_must_remain_active must be true")

    for key, expected in REQUIRED_ALWAYS_FALSE.items():
        if decision.get(key) is not expected:
            failures.append(f"{key} must be {str(expected).lower()}")

    absent_files = decision.get("required_absent_files", [])
    if not isinstance(absent_files, list):
        failures.append("required_absent_files must be an array")
        absent_files = []
    for rel in sanitize_required_absent(absent_files):
        if not isinstance(rel, str) or not rel:
            failures.append("required_absent_files entries must be non-empty strings")
            continue
        if (root / rel).exists():
            failures.append(f"forbidden file exists: {rel}")

    if (
        decision.get("review_package")
        != "docs/reviews/sandbox_implementation_execution_readiness_authorization_review_package.json"
    ):
        failures.append(
            "review_package must reference docs/reviews/sandbox_implementation_execution_readiness_authorization_review_package.json"
        )

    if (
        decision.get("review_document")
        != "docs/reviews/SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-AUTHORIZATION-REVIEW.md"
    ):
        failures.append(
            "review_document must reference docs/reviews/SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-AUTHORIZATION-REVIEW.md"
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
    if review_pkg.get("default_decision_status") != "execution_authorization_review_hold":
        failures.append(
            "authorization review package default_decision_status must be execution_authorization_review_hold"
        )

    prior_decision = (
        root
        / "docs/reviews/sandbox_implementation_execution_readiness_follow_on_decision.json"
    )
    if prior_decision.exists():
        try:
            prev = load_json(prior_decision)
            if (
                prev.get("decision_status")
                != "execution_readiness_review_pending_accepted_for_decision_preparation_only"
            ):
                failures.append(
                    "prior follow-on decision status must be execution_readiness_review_pending_accepted_for_decision_preparation_only"
                )
        except Exception as exc:
            failures.append(f"unable to parse prior follow-on decision: {exc}")
    else:
        failures.append(
            "required prior follow-on decision missing: docs/reviews/sandbox_implementation_execution_readiness_follow_on_decision.json"
        )

    doc_text = decision_doc.read_text(encoding="utf-8-sig").lower()
    for needle in REQUIRED_DOC_NEEDLES:
        if needle not in doc_text:
            failures.append(f"required decision language missing: {needle}")

    failures.extend(collect_sandbox_writer_invariant_failures(root))

    if failures:
        print(
            "FAIL: sandbox implementation execution-readiness authorization decision verification failed."
        )
        for item in failures:
            print(f" - {item}")
        return 1

    print(
        "PASS: sandbox implementation execution-readiness authorization decision verification passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
