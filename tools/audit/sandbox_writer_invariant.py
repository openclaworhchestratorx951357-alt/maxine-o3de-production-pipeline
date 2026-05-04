#!/usr/bin/env python3
"""Shared sandbox-writer admitted-only safety invariant helpers."""

from __future__ import annotations

from pathlib import Path
from typing import List


SANDBOX_WRITER_REL = "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1"
SANDBOX_ROLLBACK_REL = "scripts/powershell/Invoke-MaxineSandboxRollback.ps1"
SANDBOX_INSPECT_REL = "scripts/powershell/Invoke-MaxineSandboxReceiptInspect.ps1"
AUTHORITATIVE_REL = "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1"
RECEIPT_INDEX_REL = "examples/sandbox/receipts/index.json"
RECEIPT_INDEX_SCHEMA_REL = "schemas/maxine_sandbox_receipt_index.schema.json"

ADMITTED_SANDBOX_COMMANDS = {
    SANDBOX_WRITER_REL,
    SANDBOX_ROLLBACK_REL,
    SANDBOX_INSPECT_REL,
}

REQUIRED_WRITER_NEEDLES = [
    "sandbox_only",
    "explicit_sandbox_approval",
    "approved_target_under_sandbox",
    "examples/sandbox/staging",
    "receipt_index_path",
    "receipts/index.json",
    "parent traversal and is blocked",
]

REQUIRED_ROLLBACK_NEEDLES = [
    "confirmrollback",
    "files_written",
    "sandbox_only",
    "receipt_index_path",
    "rolled_back",
]

REQUIRED_INSPECT_NEEDLES = [
    "receipt_id",
    "status",
    "files_written",
    "sha256_before",
    "sha256_after",
    "rollback_status",
    "blocked_reason",
]

FORBIDDEN_EXECUTION_NEEDLES = [
    "o3de editor",
    "asset processor",
    "o3de.exe",
    "editor.exe",
    "assetprocessorbatch",
    "invoke-maxineauthoritativeresolverwrite.ps1",
]

FORBIDDEN_CAPABILITY_NEEDLES = [
    "product resolution",
    "resolved_products",
    "asset_id",
    "asset ids",
    "spawn entities",
    "publish prefabs",
]

FORBIDDEN_INSPECT_MUTATION_NEEDLES = [
    "remove-item",
    "set-content",
    "add-content",
    "clear-content",
    "writealltext",
    "new-item",
    "out-file",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").lower()


def sanitize_required_absent(paths: List[str]) -> List[str]:
    sanitized: List[str] = []
    for rel in paths:
        if rel in ADMITTED_SANDBOX_COMMANDS:
            continue
        sanitized.append(rel)
    return sanitized


def collect_sandbox_writer_invariant_failures(root: Path) -> List[str]:
    failures: List[str] = []

    writer = root / SANDBOX_WRITER_REL
    rollback = root / SANDBOX_ROLLBACK_REL
    inspect = root / SANDBOX_INSPECT_REL
    authoritative = root / AUTHORITATIVE_REL
    receipt_index = root / RECEIPT_INDEX_REL
    receipt_index_schema = root / RECEIPT_INDEX_SCHEMA_REL

    if not writer.exists():
        failures.append(f"sandbox writer command missing: {SANDBOX_WRITER_REL}")
    if not rollback.exists():
        failures.append(f"sandbox rollback command missing: {SANDBOX_ROLLBACK_REL}")
    if not inspect.exists():
        failures.append(f"sandbox receipt inspect command missing: {SANDBOX_INSPECT_REL}")
    if authoritative.exists():
        failures.append(f"authoritative command must remain absent: {AUTHORITATIVE_REL}")
    if not receipt_index.exists():
        failures.append(f"receipt index missing: {RECEIPT_INDEX_REL}")
    if not receipt_index_schema.exists():
        failures.append(f"receipt index schema missing: {RECEIPT_INDEX_SCHEMA_REL}")

    if writer.exists():
        writer_text = _read_text(writer)
        for needle in REQUIRED_WRITER_NEEDLES:
            if needle not in writer_text:
                failures.append(f"sandbox writer missing safety needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in writer_text:
                failures.append(f"sandbox writer contains forbidden execution needle: {needle}")
        for needle in FORBIDDEN_CAPABILITY_NEEDLES:
            if needle in writer_text:
                failures.append(f"sandbox writer contains forbidden capability needle: {needle}")

    if rollback.exists():
        rollback_text = _read_text(rollback)
        for needle in REQUIRED_ROLLBACK_NEEDLES:
            if needle not in rollback_text:
                failures.append(f"sandbox rollback missing safety needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in rollback_text:
                failures.append(f"sandbox rollback contains forbidden execution needle: {needle}")
        for needle in FORBIDDEN_CAPABILITY_NEEDLES:
            if needle in rollback_text:
                failures.append(f"sandbox rollback contains forbidden capability needle: {needle}")

    if inspect.exists():
        inspect_text = _read_text(inspect)
        for needle in REQUIRED_INSPECT_NEEDLES:
            if needle not in inspect_text:
                failures.append(f"sandbox inspect command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in inspect_text:
                failures.append(f"sandbox inspect command contains forbidden execution needle: {needle}")
        for needle in FORBIDDEN_CAPABILITY_NEEDLES:
            if needle in inspect_text:
                failures.append(f"sandbox inspect command contains forbidden capability needle: {needle}")
        for needle in FORBIDDEN_INSPECT_MUTATION_NEEDLES:
            if needle in inspect_text:
                failures.append(f"sandbox inspect command is not read-only; contains mutation needle: {needle}")

    if receipt_index.exists():
        try:
            raw = receipt_index.read_text(encoding="utf-8-sig")
            import json

            parsed = json.loads(raw)
            if parsed.get("sandbox_root") != "examples/sandbox":
                failures.append("receipt index sandbox_root must be examples/sandbox.")
            if not isinstance(parsed.get("receipts"), list):
                failures.append("receipt index receipts field must be an array.")
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(f"receipt index is not valid JSON: {exc}")

    return failures
