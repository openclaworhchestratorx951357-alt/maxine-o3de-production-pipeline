#!/usr/bin/env python3
"""Verify sandbox execution intent/hold contract artifacts (planning-only)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List


REQUIRED_DOCS = [
    "docs/roadmap/SANDBOX-EXECUTION-INTENT-HOLD-DESIGN.md",
    "docs/contracts/SANDBOX-EXECUTION-INTENT-HOLD-CONTRACT.md",
]
REQUIRED_SCHEMAS = [
    "schemas/maxine_sandbox_execution_intent.schema.json",
    "schemas/maxine_sandbox_execution_hold.schema.json",
]
REQUIRED_EXAMPLES = [
    "examples/manifests/example-sandbox-execution-intent.json",
    "examples/manifests/example-sandbox-execution-hold.json",
    "examples/jobs/example-sandbox-execution-intent-hold-job.json",
]
REQUIRED_DEPENDENCIES = [
    "examples/manifests/example-sandbox-write-final-preflight-report.json",
]
REQUIRED_ABSENT_COMMANDS = [
    "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1",
    "scripts/powershell/Invoke-MaxineSandboxRollback.ps1",
    "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1",
]
REQUIRED_DOC_NEEDLES = [
    "sandbox writes are not implemented",
    "rollback execution is not implemented",
    "this command validates execution intent and hold status only",
    "does not execute sandbox writes",
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
    check_exists(root, REQUIRED_SCHEMAS, "required schema", failures)
    check_exists(root, REQUIRED_EXAMPLES, "required example artifact", failures)
    check_exists(root, REQUIRED_DEPENDENCIES, "required dependency artifact", failures)
    check_absent(root, REQUIRED_ABSENT_COMMANDS, failures)

    verify_preflight = root / "tools" / "audit" / "verify_sandbox_write_final_preflight_report.py"
    verify_intent = root / "tools" / "audit" / "verify_sandbox_execution_intent.py"
    verify_hold = root / "tools" / "audit" / "verify_sandbox_execution_hold.py"

    if not verify_preflight.exists():
        failures.append("required verifier missing: tools/audit/verify_sandbox_write_final_preflight_report.py")
    if not verify_intent.exists():
        failures.append("required verifier missing: tools/audit/verify_sandbox_execution_intent.py")
    if not verify_hold.exists():
        failures.append("required verifier missing: tools/audit/verify_sandbox_execution_hold.py")

    if verify_preflight.exists():
        run_check(
            root,
            [
                sys.executable,
                str(verify_preflight),
                "--report",
                "examples/manifests/example-sandbox-write-final-preflight-report.json",
            ],
            "sandbox write final preflight report verifier",
            failures,
        )

    if verify_intent.exists():
        run_check(
            root,
            [
                sys.executable,
                str(verify_intent),
                "--intent",
                "examples/manifests/example-sandbox-execution-intent.json",
                "--final-preflight-report",
                "examples/manifests/example-sandbox-write-final-preflight-report.json",
            ],
            "sandbox execution intent verifier",
            failures,
        )

    if verify_hold.exists():
        run_check(
            root,
            [
                sys.executable,
                str(verify_hold),
                "--hold",
                "examples/manifests/example-sandbox-execution-hold.json",
            ],
            "sandbox execution hold verifier",
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
        print("FAIL: sandbox execution intent/hold contract verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox execution intent/hold contract verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
