#!/usr/bin/env python3
"""Verify sandbox write planning contract artifacts (design-only)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures, sanitize_required_absent


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
REQUIRED_DOC_NEEDLES = [
    "sandbox writes are not implemented",
    "rollback execution is not implemented",
    "this command is not implemented",
    "planning only",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_exists(root: Path, rel_paths: List[str], label: str, failures: List[str]) -> None:
    for rel in rel_paths:
        if not (root / rel).exists():
            failures.append(f"{label} missing: {rel}")


def check_absent(root: Path, rel_paths: List[str], failures: List[str]) -> None:
    for rel in sanitize_required_absent(rel_paths):
        if (root / rel).exists():
            failures.append(f"forbidden file exists: {rel}")


def main() -> int:
    root = repo_root()

    plan_path = root / "docs" / "audits" / "sandbox_write_planning_contract_plan.json"
    decision_path = root / "docs" / "reviews" / "phase2_acceptance_decision.json"
    design_doc = root / "docs" / "roadmap" / "SANDBOX-WRITE-PLANNING-CONTRACT-DESIGN.md"
    contract_doc = root / "docs" / "contracts" / "SANDBOX-WRITE-PLANNING-CONTRACT.md"
    example_plan = root / "examples" / "manifests" / "example-sandbox-write-plan.json"
    verifier_script = root / "tools" / "audit" / "verify_sandbox_write_plan.py"

    failures: List[str] = []

    if not plan_path.exists():
        print(f"FAIL: missing plan JSON: {plan_path}")
        return 2

    if not decision_path.exists():
        print(f"FAIL: missing phase2 decision JSON: {decision_path}")
        return 2

    try:
        plan = load_json(plan_path)
    except Exception as exc:
        print(f"FAIL: unable to parse plan JSON: {exc}")
        return 2

    try:
        decision = load_json(decision_path)
    except Exception as exc:
        print(f"FAIL: unable to parse decision JSON: {exc}")
        return 2

    if decision.get("decision_status") != "accepted":
        failures.append("phase2 decision_status must be accepted")

    dependency_artifacts = plan.get("required_dependency_artifacts", [])
    if not isinstance(dependency_artifacts, list):
        failures.append("required_dependency_artifacts must be an array")
    else:
        check_exists(root, dependency_artifacts, "dependency artifact", failures)

    required_absent = plan.get("required_command_absent", [])
    if not isinstance(required_absent, list):
        failures.append("required_command_absent must be an array")
    else:
        check_absent(root, required_absent, failures)

    for required_file in [design_doc, contract_doc, example_plan, verifier_script]:
        if not required_file.exists():
            failures.append(f"missing required file: {required_file.relative_to(root)}")

    if verifier_script.exists() and example_plan.exists():
        result = subprocess.run(
            [sys.executable, str(verifier_script), "--plan", str(example_plan)],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            output = (result.stdout + "\n" + result.stderr).strip()
            failures.append(f"sandbox write plan verifier failed: {output}")

    safety = plan.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("safety must be an object")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                failures.append(f"safety.{key} must be {str(expected).lower()}")

    combined_text = ""
    if design_doc.exists():
        combined_text += design_doc.read_text(encoding="utf-8-sig").lower() + "\n"
    if contract_doc.exists():
        combined_text += contract_doc.read_text(encoding="utf-8-sig").lower() + "\n"

    for needle in REQUIRED_DOC_NEEDLES:
        if needle not in combined_text:
            failures.append(f"required planning language missing: {needle}")

    failures.extend(collect_sandbox_writer_invariant_failures(root))

    if failures:
        print("FAIL: sandbox write planning contract verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox write planning contract verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
