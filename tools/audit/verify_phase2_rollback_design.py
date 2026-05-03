#!/usr/bin/env python3
"""Verify Phase 2 rollback artifact design package."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_exists(root: Path, rel_paths: List[str], label: str, failures: List[str]) -> None:
    for rel in rel_paths:
        if not (root / rel).exists():
            failures.append(f"{label} missing: {rel}")


def check_absent(root: Path, rel_paths: List[str], failures: List[str]) -> None:
    for rel in rel_paths:
        if (root / rel).exists():
            failures.append(f"forbidden file exists: {rel}")


def check_contains(path: Path, needle: str, failures: List[str]) -> None:
    if not path.exists():
        failures.append(f"missing file for text check: {path.as_posix()}")
        return
    content = path.read_text(encoding="utf-8-sig")
    if needle not in content:
        failures.append(f"required text missing in {path.as_posix()}: {needle}")


def main() -> int:
    root = repo_root()
    inventory_path = root / "docs" / "audits" / "phase2_rollback_artifact_design_inventory.json"
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
    required_schemas = inventory.get("required_schemas", [])
    required_examples = inventory.get("required_examples", [])
    required_scripts = inventory.get("required_scripts", [])
    required_absent = inventory.get("required_absent_files", [])

    check_exists(root, required_docs, "required doc", failures)
    check_exists(root, required_schemas, "required schema", failures)
    check_exists(root, required_examples, "required example", failures)
    check_exists(root, required_scripts, "required script", failures)
    check_absent(root, required_absent, failures)

    rollback_doc = root / "docs" / "roadmap" / "PHASE-2-ROLLBACK-ARTIFACT-DESIGN.md"
    rollback_contract = root / "docs" / "contracts" / "SANDBOX-ROLLBACK-ARTIFACT-CONTRACT.md"

    combined = ""
    if rollback_doc.exists():
        combined += rollback_doc.read_text(encoding="utf-8-sig").lower() + "\n"
    if rollback_contract.exists():
        combined += rollback_contract.read_text(encoding="utf-8-sig").lower() + "\n"

    for needle in ["design", "rollback", "not implemented", "no products are resolved"]:
        if needle not in combined:
            failures.append(f"required rollback design language missing: {needle}")

    artifact_verifier = root / "tools" / "audit" / "verify_sandbox_rollback_artifact.py"
    artifact_path = root / "examples" / "manifests" / "example-sandbox-rollback-artifact.json"
    if artifact_verifier.exists() and artifact_path.exists():
        result = subprocess.run(
            [sys.executable, str(artifact_verifier), "--artifact", str(artifact_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            failures.append(
                "rollback artifact verifier failed on example artifact: "
                + (result.stdout + "\n" + result.stderr).strip()
            )
    else:
        failures.append("unable to run rollback artifact verifier against example artifact")

    if failures:
        print("FAIL: Phase 2 rollback design verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: Phase 2 rollback design verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
