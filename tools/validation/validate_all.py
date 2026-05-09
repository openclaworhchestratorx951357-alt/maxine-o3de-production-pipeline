#!/usr/bin/env python3
"""Run safe local production-readiness validators without O3DE or network access."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.o3de.product_resolver import integration_gate_enabled, resolve_manifest_products
from tools.o3de.asset_processor_batch import asset_processor_batch_gate_enabled
from tools.o3de.editor_smoke import editor_smoke_gate_enabled
from tools.validation.schema_utils import load_json

RELEASE_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"


def _run(label: str, args: List[str]) -> int:
    print(f"== {label} ==")
    proc = subprocess.run(args, cwd=str(REPO_ROOT), text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip())
    print(f"{label}: exit {proc.returncode}")
    return proc.returncode


def _run_integration_check(*, enable_o3de_integration: bool, strict_integration: bool) -> int:
    if not enable_o3de_integration:
        print("local O3DE integration: skipped (not enabled; fixture resolver remains the default)")
        return 0
    result = resolve_manifest_products(
        load_json(RELEASE_MANIFEST),
        enable_o3de_integration=True,
        strict=True,
        strict_integration=strict_integration,
    )
    print(f"local O3DE integration: {result.status}")
    for code in result.errors:
        print(f"  error: {code}")
    for code in result.warnings:
        print(f"  warning: {code}")
    for message in result.messages:
        print(f"  - {message}")
    return 1 if result.status == "fail" else 0


def _run_asset_processor_batch_integration_check(*, enable_asset_processor_batch: bool, strict_integration: bool) -> int:
    if not enable_asset_processor_batch:
        print("Asset Processor Batch local integration: skipped (not enabled; fixture corpus remains the default)")
        return 0
    return _run(
        "Asset Processor Batch local integration",
        [
            sys.executable,
            "tools/o3de/asset_processor_batch.py",
            "--corpus",
            "examples/golden-corpus",
            "--enable-asset-processor-batch",
            *(["--strict-integration"] if strict_integration else []),
        ],
    )


def _run_editor_smoke_integration_check(*, enable_editor_smoke: bool, strict_integration: bool) -> int:
    if not enable_editor_smoke:
        print("Editor smoke local integration: skipped (not enabled; fixture bridge remains the default)")
        return 0
    return _run(
        "Editor smoke local integration",
        [
            sys.executable,
            "tools/o3de/editor_smoke.py",
            "--manifest",
            "examples/manifests/release_rigged.pass.example.json",
            "--enable-editor-smoke",
            *(["--strict-integration"] if strict_integration else []),
        ],
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run safe local production-readiness validators.")
    parser.add_argument("--enable-o3de-integration", action="store_true", help="Opt into local O3DE adapter detection.")
    parser.add_argument("--enable-asset-processor-batch", action="store_true", help="Opt into local Asset Processor Batch detection.")
    parser.add_argument("--enable-editor-smoke", action="store_true", help="Opt into local O3DE Editor smoke detection.")
    parser.add_argument("--strict-integration", action="store_true", help="Fail when local O3DE tooling is unavailable.")
    parsed = parser.parse_args()

    commands = [
        ("manifest examples", [sys.executable, "tools/validation/validate_manifests.py", "--strict", "--allow-warn"]),
        ("product matrix", [sys.executable, "tools/validation/validate_product_matrix.py"]),
        ("QC reports", [sys.executable, "tools/validation/validate_qc_reports.py"]),
        (
            "Asset Processor Batch golden corpus",
            [
                sys.executable,
                "tools/o3de/asset_processor_batch.py",
                "--corpus",
                "examples/golden-corpus",
                "--mode",
                "fixture",
            ],
        ),
        (
            "Editor smoke fixture bridge",
            [
                sys.executable,
                "tools/o3de/editor_smoke.py",
                "--manifest",
                "examples/manifests/release_rigged.pass.example.json",
                "--mode",
                "fixture",
            ],
        ),
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
    codes = [_run(label, command_args) for label, command_args in commands]
    enable_integration = parsed.enable_o3de_integration or integration_gate_enabled()
    codes.append(
        _run_integration_check(
            enable_o3de_integration=enable_integration,
            strict_integration=parsed.strict_integration,
        )
    )
    enable_apb = parsed.enable_asset_processor_batch or asset_processor_batch_gate_enabled(os.environ)
    codes.append(
        _run_asset_processor_batch_integration_check(
            enable_asset_processor_batch=enable_apb,
            strict_integration=parsed.strict_integration,
        )
    )
    enable_editor = parsed.enable_editor_smoke or editor_smoke_gate_enabled(os.environ)
    codes.append(
        _run_editor_smoke_integration_check(
            enable_editor_smoke=enable_editor,
            strict_integration=parsed.strict_integration,
        )
    )
    print("Integration checks skipped unless explicitly enabled: O3DE Editor, Asset Processor Batch, Blender, Mixamo/Adobe, and network services.")
    return 0 if all(code == 0 for code in codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
