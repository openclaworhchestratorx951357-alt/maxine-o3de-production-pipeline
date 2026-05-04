#!/usr/bin/env python3
"""Verify Phase 2 design-only sandbox write prototype artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures, sanitize_required_absent


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


def check_contains(path: Path, needle: str, failures: List[str]) -> None:
    if not path.exists():
        failures.append(f"missing file for text check: {path.as_posix()}")
        return
    content = path.read_text(encoding="utf-8-sig")
    if needle not in content:
        failures.append(f"required text missing in {path.as_posix()}: {needle}")


def main() -> int:
    root = repo_root()
    inventory_path = root / "docs" / "audits" / "phase2_sandbox_write_design_inventory.json"
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
    required_previous = inventory.get("required_previous_baseline_docs", [])
    required_absent = inventory.get("required_absent_files", [])

    check_exists(root, required_docs, "required doc", failures)
    check_exists(root, required_previous, "required previous baseline doc", failures)
    check_absent(root, required_absent, failures)

    phase2_design_doc = root / "docs" / "roadmap" / "PHASE-2-SANDBOX-WRITE-PROTOTYPE-DESIGN.md"
    phase2_contract_doc = root / "docs" / "contracts" / "SANDBOX-WRITE-PROTOTYPE-CONTRACT.md"

    combined_text = ""
    if phase2_design_doc.exists():
        combined_text += phase2_design_doc.read_text(encoding="utf-8-sig").lower() + "\n"
    if phase2_contract_doc.exists():
        combined_text += phase2_contract_doc.read_text(encoding="utf-8-sig").lower() + "\n"

    for needle in ["design-only", "not implemented", "sandbox-only", "rollback", "no products are resolved"]:
        if needle not in combined_text:
            failures.append(f"required design language missing: {needle}")

    check_contains(root / "README.md", "authoritative writes remain unimplemented", failures)

    failures.extend(collect_sandbox_writer_invariant_failures(root))

    if failures:
        print("FAIL: Phase 2 design-only verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: Phase 2 design-only verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
