#!/usr/bin/env python3
"""Verify sandbox write approval-gate contract artifacts (planning-only)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List


REQUIRED_DOCS = [
    "docs/roadmap/SANDBOX-WRITE-APPROVAL-GATE-DESIGN.md",
    "docs/contracts/SANDBOX-WRITE-APPROVAL-GATE-CONTRACT.md",
]
REQUIRED_SCHEMA = "schemas/maxine_sandbox_write_approval_gate_report.schema.json"
REQUIRED_EXAMPLE_APPROVAL = "examples/manifests/example-sandbox-write-approval.json"
REQUIRED_EXAMPLE_REPORT = "examples/manifests/example-sandbox-write-approval-gate-report.json"
REQUIRED_EXAMPLE_JOB = "examples/jobs/example-sandbox-write-approval-gate-job.json"
REQUIRED_DEPENDENCIES = [
    "examples/manifests/example-sandbox-write-dry-run-report.json",
    "examples/manifests/example-sandbox-write-plan.json",
    "docs/reviews/phase2_acceptance_decision.json",
]
REQUIRED_ABSENT_COMMANDS = [
    "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1",
    "scripts/powershell/Invoke-MaxineSandboxRollback.ps1",
    "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1",
]
REQUIRED_DOC_NEEDLES = [
    "sandbox writes are not implemented",
    "rollback execution is not implemented",
    "this command validates approval only",
    "does not execute writes",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def check_exists(root: Path, rel_paths: List[str], label: str, failures: List[str]) -> None:
    for rel in rel_paths:
        if not (root / rel).exists():
            failures.append(f"{label} missing: {rel}")


def check_absent(root: Path, rel_paths: List[str], failures: List[str]) -> None:
    for rel in rel_paths:
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
    check_exists(root, [REQUIRED_EXAMPLE_APPROVAL], "required example approval", failures)
    check_exists(root, [REQUIRED_EXAMPLE_REPORT], "required example approval gate report", failures)
    check_exists(root, [REQUIRED_EXAMPLE_JOB], "required example job", failures)
    check_exists(root, REQUIRED_DEPENDENCIES, "required dependency artifact", failures)
    check_absent(root, REQUIRED_ABSENT_COMMANDS, failures)

    verify_dry_run_report = root / "tools" / "audit" / "verify_sandbox_write_dry_run_report.py"
    verify_approval = root / "tools" / "audit" / "verify_sandbox_write_approval.py"
    verify_gate_report = root / "tools" / "audit" / "verify_sandbox_write_approval_gate_report.py"

    if not verify_dry_run_report.exists():
        failures.append("required verifier missing: tools/audit/verify_sandbox_write_dry_run_report.py")
    if not verify_approval.exists():
        failures.append("required verifier missing: tools/audit/verify_sandbox_write_approval.py")
    if not verify_gate_report.exists():
        failures.append("required verifier missing: tools/audit/verify_sandbox_write_approval_gate_report.py")

    if verify_dry_run_report.exists():
        run_check(
            root,
            [
                sys.executable,
                str(verify_dry_run_report),
                "--report",
                "examples/manifests/example-sandbox-write-dry-run-report.json",
            ],
            "sandbox write dry-run report verifier",
            failures,
        )

    if verify_approval.exists():
        run_check(
            root,
            [
                sys.executable,
                str(verify_approval),
                "--approval",
                "examples/manifests/example-sandbox-write-approval.json",
                "--dry-run-report",
                "examples/manifests/example-sandbox-write-dry-run-report.json",
            ],
            "sandbox write approval verifier",
            failures,
        )

    if verify_gate_report.exists():
        run_check(
            root,
            [
                sys.executable,
                str(verify_gate_report),
                "--report",
                "examples/manifests/example-sandbox-write-approval-gate-report.json",
            ],
            "sandbox write approval-gate report verifier",
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

    if failures:
        print("FAIL: sandbox write approval-gate contract verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox write approval-gate contract verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
