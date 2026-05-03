#!/usr/bin/env python3
"""Verify the Phase 2 acceptance decision record."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_DOC_TEXT = [
    "Phase 2 Acceptance Decision",
    "no write-capable resolver is implemented",
    "sandbox write command remains absent",
    "rollback execution command remains absent",
    "authoritative write command remains absent",
]

REQUIRED_FALSE_FIELDS = [
    "sandbox_write_implementation_allowed",
    "rollback_execution_allowed",
    "authoritative_write_allowed",
    "product_resolution_allowed",
    "asset_id_claims_allowed",
    "o3de_editor_allowed",
    "asset_processor_allowed",
]


VALID_STATUSES = {"accepted", "rejected", "hold"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_absent(root: Path, rel_paths: List[str], failures: List[str]) -> None:
    for rel in rel_paths:
        if (root / rel).exists():
            failures.append(f"forbidden file exists: {rel}")


def main() -> int:
    root = repo_root()
    decision_path = root / "docs" / "reviews" / "phase2_acceptance_decision.json"
    doc_path = root / "docs" / "reviews" / "PHASE-2-ACCEPTANCE-DECISION.md"

    failures: List[str] = []

    if not decision_path.exists():
        print(f"FAIL: missing decision JSON: {decision_path}")
        return 2

    try:
        decision = load_json(decision_path)
    except Exception as exc:
        print(f"FAIL: unable to parse decision JSON: {exc}")
        return 2

    if not doc_path.exists():
        failures.append("missing decision document: docs/reviews/PHASE-2-ACCEPTANCE-DECISION.md")

    review_package = decision.get("review_package")
    review_document = decision.get("review_document")

    if not isinstance(review_package, str) or not (root / review_package).exists():
        failures.append("review_package is missing or does not exist")

    if not isinstance(review_document, str) or not (root / review_document).exists():
        failures.append("review_document is missing or does not exist")

    status = decision.get("decision_status")
    if status not in VALID_STATUSES:
        failures.append("decision_status must be one of: accepted, rejected, hold")

    required_absent = decision.get("required_absent_files", [])
    if not isinstance(required_absent, list):
        failures.append("required_absent_files must be an array")
    else:
        check_absent(root, required_absent, failures)

    for field in REQUIRED_FALSE_FIELDS:
        if decision.get(field) is not False:
            failures.append(f"{field} must be false")

    if status == "accepted":
        if decision.get("sandbox_write_prototype_planning_allowed") is not True:
            failures.append("sandbox_write_prototype_planning_allowed must be true when accepted")
        if decision.get("accepted_next_step_allowed") is not True:
            failures.append("accepted_next_step_allowed must be true when accepted")
    elif status in {"hold", "rejected"}:
        if decision.get("sandbox_write_prototype_planning_allowed") is not False:
            failures.append("sandbox_write_prototype_planning_allowed must be false when hold/rejected")
        if decision.get("accepted_next_step_allowed") is not False:
            failures.append("accepted_next_step_allowed must be false when hold/rejected")

    if doc_path.exists():
        doc_text = doc_path.read_text(encoding="utf-8-sig")
        for needle in REQUIRED_DOC_TEXT:
            if needle not in doc_text:
                failures.append(f"decision doc missing required text: {needle}")

    if failures:
        print("FAIL: Phase 2 acceptance decision verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: Phase 2 acceptance decision verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
