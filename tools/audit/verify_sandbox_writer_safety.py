#!/usr/bin/env python3
"""Verify sandbox writer skeleton safety boundaries."""

from __future__ import annotations

from pathlib import Path

from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures


REQUIRED_FILES = [
    "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1",
    "scripts/powershell/Invoke-MaxineSandboxRollback.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReceiptInspect.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReviewPacketBuild.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReviewPacketInspect.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReviewDecisionRecord.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReviewDecisionInspect.ps1",
    "scripts/powershell/Invoke-MaxineSandboxWorkflowRun.ps1",
    "scripts/powershell/Invoke-MaxineSandboxWorkflowInspect.ps1",
    "schemas/maxine_sandbox_resolver_write_plan.schema.json",
    "schemas/maxine_sandbox_write_receipt.schema.json",
    "schemas/maxine_sandbox_receipt_index.schema.json",
    "schemas/maxine_sandbox_review_packet.schema.json",
    "schemas/maxine_sandbox_review_decision.schema.json",
    "schemas/maxine_sandbox_workflow_run.schema.json",
    "examples/sandbox/receipts/index.json",
    "examples/sandbox/review-packets/.gitkeep",
    "examples/sandbox/review-decisions/.gitkeep",
    "examples/sandbox/workflow-runs/.gitkeep",
    "examples/sandbox/staging/.gitkeep",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def check_exists(root: Path, rel_paths: list[str], failures: list[str]) -> None:
    for rel in rel_paths:
        if not (root / rel).exists():
            failures.append(f"missing required file: {rel}")


def main() -> int:
    root = repo_root()
    failures: list[str] = []

    check_exists(root, REQUIRED_FILES, failures)
    failures.extend(collect_sandbox_writer_invariant_failures(root))

    if failures:
        print("FAIL: sandbox writer safety verification failed.")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("PASS: sandbox writer admitted-only safety verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
