#!/usr/bin/env python3
"""Diagnose gated O3DE Editor smoke readiness without running Editor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.o3de.editor_smoke import (  # noqa: E402
    DEFAULT_GOLDEN_PROJECT_FIXTURE,
    build_editor_smoke_readiness_report,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local Editor smoke readiness without running Editor.")
    parser.add_argument("--engine-root", help="O3DE engine root.")
    parser.add_argument("--project", help="Controlled MAXINE_GoldenCorpus project path.")
    parser.add_argument("--editor-executable", help="Project/engine-paired Editor executable path.")
    parser.add_argument(
        "--golden-project-fixture",
        default=str(DEFAULT_GOLDEN_PROJECT_FIXTURE),
        help="Golden project fixture contract path.",
    )
    parser.add_argument("--strict", action="store_true", help="Fail when readiness is unavailable.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def _print_text_report(report: Mapping[str, Any]) -> None:
    print(f"Editor smoke readiness: {report['status']}")
    print(f"live_editor_execution_allowed: {str(report.get('live_editor_execution_allowed', False)).lower()}")
    print(f"live_publication_allowed: {str(report.get('live_publication_allowed', False)).lower()}")
    print(f"release_packaging_allowed: {str(report.get('release_packaging_allowed', False)).lower()}")
    editor = report.get("editor_executable", {})
    if editor:
        print(f"editor_executable: {editor.get('path', '')}")
        print(f"editor_executable_provenance: {editor.get('provenance', '')}")
    print(f"editor_python_bindings_enabled: {str(report.get('editor_python_bindings_enabled', False)).lower()}")
    print(f"editor_python_bindings_available: {str(report.get('editor_python_bindings_available', False)).lower()}")
    for code in report.get("errors", []):
        print(f"  error: {code}")
    for code in report.get("warnings", []):
        print(f"  warning: {code}")
    for message in report.get("messages", []):
        print(f"  - {message}")


def main() -> int:
    args = _parse_args()
    report = build_editor_smoke_readiness_report(
        engine_root=args.engine_root,
        project=args.project,
        editor_executable=args.editor_executable,
        golden_project_fixture=args.golden_project_fixture,
        strict=args.strict,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_text_report(report)
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
