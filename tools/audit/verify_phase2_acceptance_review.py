#!/usr/bin/env python3
"""Verify the Phase 2 acceptance review package and safety assertions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures, sanitize_required_absent


REQUIRED_DOC_TEXT = [
    "Phase 2 Acceptance Review",
    "Do you accept the Phase 2 design-only package",
    "does not authorize production writes",
    "Invoke-MaxineSandboxResolverWrite.ps1 is absent",
    "Invoke-MaxineSandboxRollback.ps1 is absent",
    "Invoke-MaxineAuthoritativeResolverWrite.ps1 is absent",
]

REQUIRED_SAFETY = {
    "design_only": True,
    "write_capable_code_allowed": False,
    "sandbox_write_allowed": False,
    "rollback_execution_allowed": False,
    "authoritative_write_allowed": False,
    "product_resolution_allowed": False,
    "asset_id_claims_allowed": False,
}

REQUIRED_VERIFIER_RUNS = [
    "tools/audit/verify_phase1_baseline.py",
    "tools/audit/verify_phase2_design_only.py",
    "tools/audit/verify_phase2_rollback_design.py",
    "tools/audit/verify_phase2_sandbox_fixture_design.py",
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


def run_script(root: Path, rel_script: str) -> subprocess.CompletedProcess[str]:
    script_path = root / rel_script
    return subprocess.run([sys.executable, str(script_path)], cwd=str(root), capture_output=True, text=True)


def main() -> int:
    root = repo_root()
    package_path = root / "docs" / "reviews" / "phase2_acceptance_review_package.json"
    review_doc = root / "docs" / "reviews" / "PHASE-2-ACCEPTANCE-REVIEW.md"
    failures: List[str] = []

    if not package_path.exists():
        print(f"FAIL: missing acceptance package JSON: {package_path}")
        return 2

    try:
        package = load_json(package_path)
    except Exception as exc:
        print(f"FAIL: unable to parse acceptance package JSON: {exc}")
        return 2

    if not review_doc.exists():
        failures.append("required review doc missing: docs/reviews/PHASE-2-ACCEPTANCE-REVIEW.md")

    check_exists(root, package.get("phase2_artifacts", []), "phase2 artifact", failures)
    check_exists(root, package.get("required_verifiers", []), "required verifier", failures)
    check_absent(root, package.get("required_absent_files", []), failures)

    safety = package.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("package safety must be an object")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                failures.append(f"safety.{key} must be {str(expected).lower()}")

    if review_doc.exists():
        doc_text = review_doc.read_text(encoding="utf-8-sig")
        for needle in REQUIRED_DOC_TEXT:
            if needle not in doc_text:
                failures.append(f"review doc missing required text: {needle}")

    for rel_script in REQUIRED_VERIFIER_RUNS:
        script_path = root / rel_script
        if not script_path.exists():
            failures.append(f"required verifier to execute is missing: {rel_script}")
            continue

        result = run_script(root, rel_script)
        if result.returncode != 0:
            output = (result.stdout + "\n" + result.stderr).strip()
            failures.append(f"verifier failed: {rel_script}\n{output}")

    failures.extend(collect_sandbox_writer_invariant_failures(root))

    if failures:
        print("FAIL: Phase 2 acceptance review verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: Phase 2 acceptance review verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
