#!/usr/bin/env python3
"""Run safe local production-readiness validators without O3DE or network access."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(label: str, args: List[str]) -> int:
    print(f"== {label} ==")
    proc = subprocess.run(args, cwd=str(REPO_ROOT), text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip())
    print(f"{label}: exit {proc.returncode}")
    return proc.returncode


def main() -> int:
    commands = [
        ("manifest examples", [sys.executable, "tools/validation/validate_manifests.py", "--strict", "--allow-warn"]),
        ("product matrix", [sys.executable, "tools/validation/validate_product_matrix.py"]),
        ("QC reports", [sys.executable, "tools/validation/validate_qc_reports.py"]),
        (
            "release QC fixture",
            [
                sys.executable,
                "tools/qc/run_qc.py",
                "--manifest",
                "examples/manifests/release_rigged.pass.example.json",
                "--strict",
                "--allow-warn",
            ],
        ),
    ]
    codes = [_run(label, args) for label, args in commands]
    print("Integration checks skipped: O3DE Editor, Asset Processor Batch, Blender, Mixamo/Adobe, and network services.")
    return 0 if all(code == 0 for code in codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
