#!/usr/bin/env python3
"""Integration-ready O3DE Editor Python package/prefab smoke script.

This script is a template for a future explicitly gated Editor run. It is
checked into the repo so command construction and report fields can be reviewed,
but the default validation path does not execute it.

No live publication is performed here. Future live use must target a temporary
sandbox level, avoid production level mutation, and write a real smoke report
only after Editor Python APIs have actually instantiated and inspected the
package/prefab/procprefab.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def build_unexecuted_template_report(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "report_type": "editor_smoke_fixture_bridge_v1",
        "report_id": "editor-python-package-prefab-smoke-template",
        "generated_at": "integration-runtime-required",
        "mode": "local_editor_python",
        "status": "skipped",
        "integration_enabled": True,
        "strict_integration": False,
        "live_editor_execution": False,
        "editor_python_bindings_required": True,
        "editor_python_bindings_available": False,
        "level_strategy": "temp_sandbox_level",
        "manifest_ref": args.manifest,
        "package_ref": args.package_ref,
        "prefab_ref": args.prefab_ref,
        "procprefab_ref": args.procprefab_ref,
        "errors": [],
        "warnings": ["MXN_VALIDATION_TOOL_UNAVAILABLE"],
        "evidence_refs": [
            {
                "id": "editor-python-template",
                "kind": "integration_ready_script",
                "source": "tools/o3de/editor_python/maxine_package_prefab_smoke.py"
            }
        ]
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Template for future MAXINE O3DE Editor Python prefab smoke.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--package-ref", default="")
    parser.add_argument("--prefab-ref", default="")
    parser.add_argument("--procprefab-ref", default="")
    parser.add_argument("--allow-temp-sandbox-level", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_temp_sandbox_level:
        print("Editor smoke template requires --allow-temp-sandbox-level for future live use.")
        return 2
    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(build_unexecuted_template_report(args), indent=2) + "\n", encoding="utf-8")
    print("Wrote integration-ready Editor smoke template report; no live Editor APIs were invoked by this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
