#!/usr/bin/env python3
"""Verify sandbox implementation-branch kickoff safety package artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_DOC_NEEDLES = [
    "non-executing implementation-branch kickoff checklist",
    "no sandbox write implementation",
    "no rollback execution implementation",
    "no authoritative write implementation",
    "execution hold remains active",
]

REQUIRED_SAFETY_FALSE = {
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

    package_path = (
        root / "docs" / "audits" / "sandbox_implementation_branch_kickoff_safety_package.json"
    )
    package_doc_path = (
        root / "docs" / "audits" / "SANDBOX-IMPLEMENTATION-BRANCH-KICKOFF-SAFETY-PACKAGE.md"
    )

    if not package_path.exists():
        print(f"FAIL: missing kickoff package JSON: {package_path}")
        return 2
    if not package_doc_path.exists():
        print(f"FAIL: missing kickoff package doc: {package_doc_path}")
        return 2

    try:
        package = load_json(package_path)
    except Exception as exc:
        print(f"FAIL: unable to parse kickoff package JSON: {exc}")
        return 2

    if package.get("package_name") != "sandbox-implementation-branch-kickoff-safety-package":
        failures.append("package_name must be sandbox-implementation-branch-kickoff-safety-package")
    if package.get("design_only") is not True:
        failures.append("design_only must be true")
    if package.get("checklist_only") is not True:
        failures.append("checklist_only must be true")
    if package.get("execution_hold_must_remain_active") is not True:
        failures.append("execution_hold_must_remain_active must be true")

    safety = package.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("safety must be an object")
        safety = {}
    for key, expected in REQUIRED_SAFETY_FALSE.items():
        if safety.get(key) is not expected:
            failures.append(f"safety.{key} must be {str(expected).lower()}")

    decision_rel = package.get("decision_record")
    if not isinstance(decision_rel, str) or not decision_rel:
        failures.append("decision_record must be a non-empty string")
        decision_rel = ""
    baseline_rel = package.get("baseline_record")
    if not isinstance(baseline_rel, str) or not baseline_rel:
        failures.append("baseline_record must be a non-empty string")
        baseline_rel = ""

    decision: Dict[str, Any] = {}
    if decision_rel:
        decision_path = root / decision_rel
        if not decision_path.exists():
            failures.append(f"decision record missing: {decision_rel}")
        else:
            try:
                decision = load_json(decision_path)
            except Exception as exc:
                failures.append(f"unable to parse decision record {decision_rel}: {exc}")

    if decision:
        if decision.get("decision_status") != package.get("required_decision_status"):
            failures.append("decision_status does not match required_decision_status")
        if decision.get("execution_hold_status") != package.get("required_execution_hold_status"):
            failures.append("execution_hold_status does not match required_execution_hold_status")
        if decision.get("sandbox_write_implementation_allowed") is not False:
            failures.append("sandbox_write_implementation_allowed must remain false")
        if decision.get("rollback_execution_implementation_allowed") is not False:
            failures.append("rollback_execution_implementation_allowed must remain false")
        if decision.get("authoritative_write_allowed") is not False:
            failures.append("authoritative_write_allowed must remain false")

    if baseline_rel:
        baseline_path = root / baseline_rel
        if not baseline_path.exists():
            failures.append(f"baseline record missing: {baseline_rel}")
        else:
            try:
                baseline = load_json(baseline_path)
                if baseline.get("baseline_name") != "sandbox-implementation-branch-baseline":
                    failures.append("baseline_record baseline_name must be sandbox-implementation-branch-baseline")
            except Exception as exc:
                failures.append(f"unable to parse baseline record {baseline_rel}: {exc}")

    required_artifacts = package.get("required_artifacts", [])
    if not isinstance(required_artifacts, list):
        failures.append("required_artifacts must be an array")
        required_artifacts = []
    for rel in required_artifacts:
        if not isinstance(rel, str) or not rel:
            failures.append("required_artifacts entries must be non-empty strings")
            continue
        if not (root / rel).exists():
            failures.append(f"required artifact missing: {rel}")

    required_absent_files = package.get("required_absent_files", [])
    if not isinstance(required_absent_files, list):
        failures.append("required_absent_files must be an array")
        required_absent_files = []
    for rel in required_absent_files:
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

    doc_text = package_doc_path.read_text(encoding="utf-8-sig").lower()
    for needle in REQUIRED_DOC_NEEDLES:
        if needle not in doc_text:
            failures.append(f"required kickoff language missing: {needle}")

    if failures:
        print("FAIL: sandbox implementation-branch kickoff safety package verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox implementation-branch kickoff safety package verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
