#!/usr/bin/env python3
"""Verify sandbox implementation execution-readiness authorization review artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures, sanitize_required_absent


REQUIRED_DOC = (
    "docs/reviews/SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-AUTHORIZATION-REVIEW.md"
)
REQUIRED_TEMPLATE = (
    "docs/reviews/sandbox_implementation_execution_readiness_authorization_decision_template.json"
)
REQUIRED_PACKAGE = (
    "docs/reviews/sandbox_implementation_execution_readiness_authorization_review_package.json"
)
REQUIRED_REVIEW_NEEDLES = [
    "beginning execution-authorization decision preparation",
    "decision: execution_authorization_review_hold",
    "does not authorize sandbox write execution",
    "execution hold remains active",
]
REQUIRED_SAFETY = {
    "review_only": True,
    "execution_hold_must_remain_active": True,
    "execution_authorization_decision_preparation_allowed_by_default": False,
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


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_python_verifier(root: Path, rel_path: str, failures: List[str]) -> None:
    verifier_path = root / rel_path
    if not verifier_path.exists():
        failures.append(f"required verifier missing: {rel_path}")
        return
    result = subprocess.run(
        [sys.executable, str(verifier_path)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        failures.append(
            "required verifier failed: "
            f"{rel_path}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def main() -> int:
    root = repo_root()
    failures: List[str] = []

    package_path = root / REQUIRED_PACKAGE
    review_doc_path = root / REQUIRED_DOC
    template_path = root / REQUIRED_TEMPLATE

    if not package_path.exists():
        print(f"FAIL: missing review package JSON: {package_path}")
        return 2

    try:
        package = load_json(package_path)
    except Exception as exc:
        print(f"FAIL: unable to parse review package JSON: {exc}")
        return 2

    if not review_doc_path.exists():
        failures.append(f"required review doc missing: {REQUIRED_DOC}")
    if not template_path.exists():
        failures.append(f"required decision template missing: {REQUIRED_TEMPLATE}")

    if package.get("default_decision_status") != "execution_authorization_review_hold":
        failures.append("default_decision_status must be execution_authorization_review_hold")

    required_stack = package.get("required_stack_artifacts", [])
    if not isinstance(required_stack, list):
        failures.append("required_stack_artifacts must be an array")
        required_stack = []
    for rel in required_stack:
        if not isinstance(rel, str) or not rel:
            failures.append("required_stack_artifacts entries must be non-empty strings")
            continue
        if not (root / rel).exists():
            failures.append(f"required_stack_artifact missing: {rel}")

    required_absent = package.get("required_absent_files", [])
    if not isinstance(required_absent, list):
        failures.append("required_absent_files must be an array")
        required_absent = []
    for rel in sanitize_required_absent(required_absent):
        if not isinstance(rel, str) or not rel:
            failures.append("required_absent_files entries must be non-empty strings")
            continue
        if (root / rel).exists():
            failures.append(f"forbidden file exists: {rel}")

    required_verifiers = package.get("required_verifiers", [])
    if not isinstance(required_verifiers, list):
        failures.append("required_verifiers must be an array")
        required_verifiers = []
    for rel in required_verifiers:
        if not isinstance(rel, str) or not rel:
            failures.append("required_verifiers entries must be non-empty strings")
            continue
        run_python_verifier(root, rel, failures)

    safety = package.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("safety must be an object")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                failures.append(f"safety.{key} must be {str(expected).lower()}")

    follow_on_decision_path = (
        root / "docs/reviews/sandbox_implementation_execution_readiness_follow_on_decision.json"
    )
    if follow_on_decision_path.exists():
        try:
            follow_on_decision = load_json(follow_on_decision_path)
            if (
                follow_on_decision.get("decision_status")
                != "execution_readiness_review_pending_accepted_for_decision_preparation_only"
            ):
                failures.append(
                    "follow-on decision status must be execution_readiness_review_pending_accepted_for_decision_preparation_only"
                )
            if follow_on_decision.get("execution_hold_current_status") != "hold_active":
                failures.append(
                    "follow-on decision execution_hold_current_status must be hold_active"
                )
        except Exception as exc:
            failures.append(f"unable to parse follow-on decision JSON: {exc}")
    else:
        failures.append(
            "required follow-on decision missing: docs/reviews/sandbox_implementation_execution_readiness_follow_on_decision.json"
        )

    hold_example_path = root / "examples/manifests/example-sandbox-execution-hold.json"
    if hold_example_path.exists():
        try:
            hold_example = load_json(hold_example_path)
            if hold_example.get("hold_status") != "hold_active":
                failures.append("execution hold example hold_status must be hold_active")
        except Exception as exc:
            failures.append(f"unable to parse execution hold example JSON: {exc}")
    else:
        failures.append(
            "required hold example missing: examples/manifests/example-sandbox-execution-hold.json"
        )

    if template_path.exists():
        try:
            template = load_json(template_path)
            if template.get("decision_status") != "execution_authorization_review_hold":
                failures.append(
                    "decision template decision_status must be execution_authorization_review_hold"
                )
            if template.get("execution_hold_current_status") != "hold_active":
                failures.append(
                    "decision template execution_hold_current_status must be hold_active"
                )
            if template.get("execution_hold_next_status") != "hold_active":
                failures.append(
                    "decision template execution_hold_next_status must be hold_active"
                )
            if template.get("execution_hold_must_remain_active") is not True:
                failures.append(
                    "decision template execution_hold_must_remain_active must be true"
                )
            if (
                template.get("execution_authorization_decision_preparation_allowed")
                is not False
            ):
                failures.append(
                    "decision template execution_authorization_decision_preparation_allowed must be false"
                )
        except Exception as exc:
            failures.append(f"unable to parse decision template JSON: {exc}")

    if review_doc_path.exists():
        review_text = review_doc_path.read_text(encoding="utf-8-sig").lower()
        for needle in REQUIRED_REVIEW_NEEDLES:
            if needle not in review_text:
                failures.append(f"required review language missing: {needle}")

    failures.extend(collect_sandbox_writer_invariant_failures(root))

    if failures:
        print(
            "FAIL: sandbox implementation execution-readiness authorization review verification failed."
        )
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox implementation execution-readiness authorization review verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
