#!/usr/bin/env python3
"""Verify Phase 1 operational baseline inventory and safety markers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


EXPECTED_LADDER_HEADINGS = [
    "## 1. Manifest-first Adapter",
    "## 2. Product Contract Resolver",
    "## 3. Filesystem Probe",
    "## 4. AP Metadata Discovery",
    "## 5. AP Database Schema Inspection",
    "## 6. AP Row Mapping",
    "## 7. Source Identity Matching",
    "## 8. Product Candidate Matching",
    "## 9. Product File Validation",
    "## 10. Resolver Readiness Gate",
    "## 11. Authoritative Dry-Run Plan",
    "## 12. AP Job-state Proof",
    "## 13. AP Platform Proof",
    "## 14. AP Product Freshness Proof",
    "## 15. AP Product Identity Proof",
    "## 16. Updated Authoritative Planner Full Proof Stack",
    "## 17. Authoritative Write Protocol Proposal",
    "## 18. Operator Approval Validation",
    "## 19. Approved-write Pre-write Report",
    "## 20. Final Execution Gate Policy",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_exists(root: Path, rel_paths: List[str], bucket: str, failures: List[str]) -> None:
    for rel in rel_paths:
        if not (root / rel).exists():
            failures.append(f"{bucket} missing: {rel}")


def check_absent(root: Path, rel_paths: List[str], failures: List[str]) -> None:
    for rel in rel_paths:
        if (root / rel).exists():
            failures.append(f"required absent file exists: {rel}")


def check_contains(path: Path, needle: str, failures: List[str]) -> None:
    if not path.exists():
        failures.append(f"missing file for text check: {path.as_posix()}")
        return
    content = path.read_text(encoding="utf-8-sig")
    if needle not in content:
        failures.append(f"required text missing in {path.as_posix()}: {needle}")


def main() -> int:
    root = repo_root()
    inventory_path = root / "docs" / "audits" / "phase1_operational_baseline_inventory.json"

    failures: List[str] = []
    if not inventory_path.exists():
        print(f"FAIL: inventory file missing: {inventory_path}")
        return 2

    try:
        inventory = load_json(inventory_path)
    except Exception as exc:
        print(f"FAIL: unable to parse inventory JSON: {exc}")
        return 2

    required_docs = inventory.get("required_docs", [])
    required_schemas = inventory.get("required_schemas", [])
    required_scripts = inventory.get("required_scripts", [])
    required_examples = inventory.get("required_examples", [])
    required_absent_files = inventory.get("required_absent_files", [])
    stages = inventory.get("stages", [])

    if not isinstance(stages, list) or len(stages) != 20:
        failures.append("inventory.stages must contain exactly 20 entries")

    check_exists(root, required_docs, "doc", failures)
    check_exists(root, required_schemas, "schema", failures)
    check_exists(root, required_scripts, "script", failures)
    check_exists(root, required_examples, "example", failures)
    check_absent(root, required_absent_files, failures)

    check_contains(root / "README.md", "M.A.X.I.N.E. Resolver Ladder", failures)
    check_contains(root / "CODEX-HANDOFF.md", "Post-Consolidation Next Milestone", failures)
    check_contains(
        root / "docs" / "o3de-integration" / "AUTHORITATIVE-EXECUTION-GATE-POLICY.md",
        "This command is **not implemented yet**",
        failures,
    )

    ladder_path = root / "docs" / "roadmap" / "RESOLVER-LADDER-INDEX.md"
    if not ladder_path.exists():
        failures.append("missing file for ladder heading checks: docs/roadmap/RESOLVER-LADDER-INDEX.md")
    else:
        ladder_content = ladder_path.read_text(encoding="utf-8-sig")
        for heading in EXPECTED_LADDER_HEADINGS:
            if heading not in ladder_content:
                failures.append(f"missing ladder stage heading: {heading}")

    if failures:
        print("FAIL: Phase 1 baseline verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: Phase 1 baseline verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
