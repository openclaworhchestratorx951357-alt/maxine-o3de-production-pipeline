#!/usr/bin/env python3
"""Shared sandbox-writer admitted-only safety invariant helpers."""

from __future__ import annotations

from pathlib import Path
from typing import List


SANDBOX_WRITER_REL = "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1"
SANDBOX_ROLLBACK_REL = "scripts/powershell/Invoke-MaxineSandboxRollback.ps1"
AUTHORITATIVE_REL = "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1"

ADMITTED_SANDBOX_COMMANDS = {
    SANDBOX_WRITER_REL,
    SANDBOX_ROLLBACK_REL,
}

REQUIRED_WRITER_NEEDLES = [
    "sandbox_only",
    "explicit_sandbox_approval",
    "approved_target_under_sandbox",
    "examples/sandbox/staging",
    "parent traversal and is blocked",
]

REQUIRED_ROLLBACK_NEEDLES = [
    "confirmrollback",
    "files_written",
    "sandbox_only",
]

FORBIDDEN_EXECUTION_NEEDLES = [
    "o3de editor",
    "asset processor",
    "o3de.exe",
    "editor.exe",
    "assetprocessorbatch",
    "invoke-maxineauthoritativeresolverwrite.ps1",
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
    authoritative = root / AUTHORITATIVE_REL

    if not writer.exists():
        failures.append(f"sandbox writer command missing: {SANDBOX_WRITER_REL}")
    if not rollback.exists():
        failures.append(f"sandbox rollback command missing: {SANDBOX_ROLLBACK_REL}")
    if authoritative.exists():
        failures.append(f"authoritative command must remain absent: {AUTHORITATIVE_REL}")

    if writer.exists():
        writer_text = _read_text(writer)
        for needle in REQUIRED_WRITER_NEEDLES:
            if needle not in writer_text:
                failures.append(f"sandbox writer missing safety needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in writer_text:
                failures.append(f"sandbox writer contains forbidden execution needle: {needle}")

    if rollback.exists():
        rollback_text = _read_text(rollback)
        for needle in REQUIRED_ROLLBACK_NEEDLES:
            if needle not in rollback_text:
                failures.append(f"sandbox rollback missing safety needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in rollback_text:
                failures.append(f"sandbox rollback contains forbidden execution needle: {needle}")

    return failures
