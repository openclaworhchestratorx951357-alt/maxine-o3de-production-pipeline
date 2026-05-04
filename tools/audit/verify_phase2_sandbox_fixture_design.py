#!/usr/bin/env python3
"""Verify Phase 2 sandbox fixture path-safety design package."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures, sanitize_required_absent


ACCEPTED_SAMPLE = "examples/sandbox/manifests/working/example-working.manifest.json"
REJECTED_SAMPLES = [
    "../outside.json",
    "C:\\Temp\\outside.json",
    "examples/sandbox/../outside.json",
    "C:\\Users\\topgu\\OneDrive\\Documents\\O3de_GEMS_Research\\Projects\\MaxineShow\\Project.json",
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


def run_check(root: Path, cmd: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)


def main() -> int:
    root = repo_root()
    inventory_path = root / "docs" / "audits" / "phase2_sandbox_fixture_path_safety_inventory.json"
    failures: List[str] = []

    if not inventory_path.exists():
        print(f"FAIL: missing inventory file: {inventory_path}")
        return 2

    try:
        inventory = load_json(inventory_path)
    except Exception as exc:
        print(f"FAIL: unable to parse inventory JSON: {exc}")
        return 2

    required_docs = inventory.get("required_docs", [])
    required_policy_files = inventory.get("required_policy_files", [])
    required_scripts = inventory.get("required_scripts", [])
    required_dirs = inventory.get("required_fixture_directories", [])
    required_absent = inventory.get("required_absent_files", [])

    check_exists(root, required_docs, "required doc", failures)
    check_exists(root, required_policy_files, "required policy file", failures)
    check_exists(root, required_scripts, "required script", failures)
    check_exists(root, required_dirs, "required fixture directory", failures)
    check_absent(root, required_absent, failures)

    verifier = root / "tools" / "audit" / "verify_sandbox_path_safety.py"
    if not verifier.exists():
        failures.append("missing path-safety verifier script")
    else:
        policy_only = run_check(root, [sys.executable, str(verifier)])
        if policy_only.returncode != 0:
            failures.append(
                "policy-only path-safety verifier failed: "
                + (policy_only.stdout + "\n" + policy_only.stderr).strip()
            )

        accepted = run_check(root, [sys.executable, str(verifier), "--path", ACCEPTED_SAMPLE])
        if accepted.returncode != 0:
            failures.append(
                "accepted sample path should pass but failed: "
                + (accepted.stdout + "\n" + accepted.stderr).strip()
            )

        for sample in REJECTED_SAMPLES:
            rejected = run_check(root, [sys.executable, str(verifier), "--path", sample])
            if rejected.returncode == 0:
                failures.append(f"rejected sample path unexpectedly passed: {sample}")

    design_doc = root / "docs" / "roadmap" / "PHASE-2-SANDBOX-FIXTURE-PATH-SAFETY-DESIGN.md"
    contract_doc = root / "docs" / "contracts" / "SANDBOX-FIXTURE-PATH-SAFETY-CONTRACT.md"

    combined = ""
    if design_doc.exists():
        combined += design_doc.read_text(encoding="utf-8-sig").lower() + "\n"
    if contract_doc.exists():
        combined += contract_doc.read_text(encoding="utf-8-sig").lower() + "\n"

    for needle in ["path-safety", "sandbox root", "no products are resolved", "does not authorize sandbox writes"]:
        if needle not in combined:
            failures.append(f"required path-safety design language missing: {needle}")

    failures.extend(collect_sandbox_writer_invariant_failures(root))

    if failures:
        print("FAIL: Phase 2 sandbox fixture path-safety design verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: Phase 2 sandbox fixture path-safety design verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
