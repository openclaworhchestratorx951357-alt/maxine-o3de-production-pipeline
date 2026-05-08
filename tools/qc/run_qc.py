#!/usr/bin/env python3
"""Run modular MAXINE QC gates against a manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.qc.gates import run_qc_gates


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MAXINE production-readiness QC gates.")
    parser.add_argument("--manifest", required=True, help="Manifest JSON path.")
    parser.add_argument("--strict", action="store_true", help="Reserved for strict release mode; gates are strict by default.")
    parser.add_argument("--allow-warn", action="store_true", help="Return zero for warning/pending-manual QC reports.")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = REPO_ROOT / manifest_path
    if not manifest_path.exists():
        print(json.dumps({"status": "fail", "error_codes": ["MXN_INPUT_MISSING"], "messages": [f"Manifest not found: {manifest_path}"]}, indent=2))
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    payload = run_qc_gates(manifest)
    print(json.dumps(payload, indent=2))
    if payload["status"] == "pass":
        return 0
    if payload["status"] in {"warn", "pending_manual"} and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
