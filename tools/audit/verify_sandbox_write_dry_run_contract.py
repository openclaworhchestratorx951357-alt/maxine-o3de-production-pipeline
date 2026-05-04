#!/usr/bin/env python3
"""Verify sandbox write dry-run report contract artifacts (planning-only)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List
from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures, sanitize_required_absent


REQUIRED_DOCS = [
    "docs/roadmap/SANDBOX-WRITE-DRY-RUN-REPORT-DESIGN.md",
    "docs/contracts/SANDBOX-WRITE-DRY-RUN-REPORT-CONTRACT.md",
]
REQUIRED_SCHEMA = "schemas/maxine_sandbox_write_dry_run_report.schema.json"
REQUIRED_EXAMPLE_REPORT = "examples/manifests/example-sandbox-write-dry-run-report.json"
REQUIRED_EXAMPLE_JOB = "examples/jobs/example-sandbox-write-dry-run-report-job.json"
REQUIRED_DEPENDENCIES = [
    "examples/manifests/example-sandbox-write-plan.json",
    "examples/manifests/example-sandbox-rollback-artifact.json",
    "docs/reviews/phase2_acceptance_decision.json",
    "docs/audits/sandbox_rollback_execution_design_plan.json",
    "docs/audits/sandbox_write_planning_contract_plan.json",
]
REQUIRED_ABSENT_COMMANDS = [
    "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1",
    "scripts/powershell/Invoke-MaxineSandboxRollback.ps1",
    "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1",
]
REQUIRED_DOC_NEEDLES = [
    "sandbox writes are not implemented",
    "rollback execution is not implemented",
    "this command validates the dry-run report only",
    "does not execute writes",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def check_exists(root: Path, rel_paths: List[str], label: str, failures: List[str]) -> None:
    for rel in rel_paths:
        if not (root / rel).exists():
            failures.append(f"{label} missing: {rel}")


def check_absent(root: Path, rel_paths: List[str], failures: List[str]) -> None:
    for rel in sanitize_required_absent(rel_paths):
        if (root / rel).exists():
            failures.append(f"forbidden command file exists: {rel}")


def run_check(root: Path, cmd: List[str], label: str, failures: List[str]) -> None:
    result = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    if result.returncode != 0:
        output = (result.stdout + "\n" + result.stderr).strip()
        failures.append(f"{label} failed: {output}")


def main() -> int:
    root = repo_root()
    failures: List[str] = []

    check_exists(root, REQUIRED_DOCS, "required doc", failures)
    check_exists(root, [REQUIRED_SCHEMA], "required schema", failures)
    check_exists(root, [REQUIRED_EXAMPLE_REPORT], "required example report", failures)
    check_exists(root, [REQUIRED_EXAMPLE_JOB], "required example job", failures)
    check_exists(root, REQUIRED_DEPENDENCIES, "required dependency artifact", failures)
    check_absent(root, REQUIRED_ABSENT_COMMANDS, failures)

    verify_plan = root / "tools" / "audit" / "verify_sandbox_write_plan.py"
    verify_report = root / "tools" / "audit" / "verify_sandbox_write_dry_run_report.py"

    if not verify_plan.exists():
        failures.append("required verifier missing: tools/audit/verify_sandbox_write_plan.py")
    if not verify_report.exists():
        failures.append("required verifier missing: tools/audit/verify_sandbox_write_dry_run_report.py")

    if verify_plan.exists():
        run_check(
            root,
            [sys.executable, str(verify_plan), "--plan", "examples/manifests/example-sandbox-write-plan.json"],
            "sandbox write plan verifier",
            failures,
        )

    if verify_report.exists():
        run_check(
            root,
            [
                sys.executable,
                str(verify_report),
                "--report",
                "examples/manifests/example-sandbox-write-dry-run-report.json",
            ],
            "sandbox write dry-run report verifier",
            failures,
        )

    combined_text = ""
    for rel_path in REQUIRED_DOCS:
        doc_path = root / rel_path
        if doc_path.exists():
            combined_text += doc_path.read_text(encoding="utf-8-sig").lower() + "\n"

    for needle in REQUIRED_DOC_NEEDLES:
        if needle not in combined_text:
            failures.append(f"required design language missing: {needle}")

    failures.extend(collect_sandbox_writer_invariant_failures(root))

    if failures:
        print("FAIL: sandbox write dry-run contract verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox write dry-run contract verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
