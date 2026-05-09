#!/usr/bin/env python3
"""Compose fixture and gated O3DE integration checks for private runners."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ci.o3de_runner_readiness import MXN_VALIDATION_TOOL_UNAVAILABLE, build_readiness_report


DEFAULT_GOLDEN_PROJECT_FIXTURE = REPO_ROOT / "examples" / "o3de-golden-project" / "maxine-golden-project.fixture.json"


def run_integration_suite(
    *,
    mode: str = "dry_run",
    dry_run: bool = False,
    enable_o3de_integration: bool = False,
    strict_integration: bool = False,
    allow_live_o3de_commands: bool = False,
    golden_project_fixture: Path | str = DEFAULT_GOLDEN_PROJECT_FIXTURE,
    env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    env_map = dict(env if env is not None else os.environ)
    if enable_o3de_integration:
        env_map["MAXINE_ENABLE_O3DE_INTEGRATION"] = "1"
        env_map["MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"] = "1"
        env_map["MAXINE_ENABLE_O3DE_EDITOR_SMOKE"] = "1"
    if allow_live_o3de_commands:
        env_map["MAXINE_ALLOW_LIVE_O3DE_COMMANDS"] = "1"

    selected_mode = "dry_run" if dry_run else mode
    golden_fixture = Path(golden_project_fixture)
    golden_fixture = golden_fixture if golden_fixture.is_absolute() else REPO_ROOT / golden_fixture
    readiness = build_readiness_report(
        env=env_map,
        strict=strict_integration if selected_mode == "integration" else False,
        golden_project_fixture=golden_fixture,
    )
    commands: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []
    status = "pass"

    if selected_mode == "dry_run":
        status = readiness["status"]
        warnings.extend(readiness.get("warnings", []))
        errors.extend(readiness.get("errors", []))
    elif selected_mode == "fixture":
        commands.extend(_run_fixture_commands(env_map))
        if any(command["return_code"] != 0 for command in commands):
            status = "fail"
    elif selected_mode == "integration":
        if readiness["status"] == "fail":
            status = "fail"
            errors.extend(readiness.get("errors", []))
        else:
            commands.extend(_run_integration_commands(env_map, strict_integration=strict_integration))
            if any(command["return_code"] != 0 for command in commands):
                status = "fail"
            elif readiness["status"] == "skipped":
                status = "skipped"
                warnings.extend(readiness.get("warnings", []))
            else:
                status = "pass"
    else:
        status = "fail"
        errors.append("MXN_SCHEMA_VALIDATION_FAIL")

    return {
        "schema_version": "1.0.0",
        "report_type": "maxine_o3de_integration_suite",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": selected_mode,
        "status": status,
        "strict_integration": strict_integration,
        "live_commands_allowed": str(env_map.get("MAXINE_ALLOW_LIVE_O3DE_COMMANDS", "")).strip() == "1",
        "live_o3de_execution": False,
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "golden_project_fixture_ref": _repo_relative(golden_fixture),
        "readiness": readiness,
        "commands": commands,
        "errors": _unique(errors),
        "warnings": _unique(warnings),
    }


def _run_fixture_commands(env: Mapping[str, str]) -> List[Dict[str, Any]]:
    return [
        _run_command(
            "golden_project_fixture fixture",
            [sys.executable, "tools/o3de/golden_project_fixture.py", "--fixtures", "examples/o3de-golden-project"],
            env,
        ),
        _run_command("validate_all fixture", [sys.executable, "tools/validation/validate_all.py"], env),
        _run_command(
            "asset_processor_batch fixture",
            [sys.executable, "tools/o3de/asset_processor_batch.py", "--corpus", "examples/golden-corpus", "--mode", "fixture"],
            env,
        ),
        _run_command(
            "editor_smoke fixture",
            [
                sys.executable,
                "tools/o3de/editor_smoke.py",
                "--manifest",
                "examples/manifests/release_rigged.pass.example.json",
                "--mode",
                "fixture",
            ],
            env,
        ),
    ]


def _run_integration_commands(env: Mapping[str, str], *, strict_integration: bool) -> List[Dict[str, Any]]:
    strict_args = ["--strict-integration"] if strict_integration else []
    return [
        _run_command(
            "validate_all integration",
            [
                sys.executable,
                "tools/validation/validate_all.py",
                "--enable-o3de-integration",
                "--enable-asset-processor-batch",
                "--enable-editor-smoke",
                *strict_args,
            ],
            env,
        ),
        _run_command(
            "asset_processor_batch integration",
            [
                sys.executable,
                "tools/o3de/asset_processor_batch.py",
                "--corpus",
                "examples/golden-corpus",
                "--enable-asset-processor-batch",
                *strict_args,
            ],
            env,
        ),
        _run_command(
            "editor_smoke integration",
            [
                sys.executable,
                "tools/o3de/editor_smoke.py",
                "--manifest",
                "examples/manifests/release_rigged.pass.example.json",
                "--enable-editor-smoke",
                *strict_args,
            ],
            env,
        ),
    ]


def _run_command(label: str, args: List[str], env: Mapping[str, str]) -> Dict[str, Any]:
    proc = subprocess.run(args, cwd=str(REPO_ROOT), text=True, capture_output=True, env=dict(env))
    return {
        "label": label,
        "args": args,
        "return_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "reported_skipped": "skipped" in proc.stdout.lower(),
    }


def _unique(values: List[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fixture or gated private O3DE integration checks.")
    parser.add_argument("--dry-run", action="store_true", help="Only report runner readiness; do not run suite commands.")
    parser.add_argument("--mode", choices=["dry_run", "fixture", "integration"], default="dry_run")
    parser.add_argument("--enable-o3de-integration", action="store_true", help="Opt into local O3DE/APB/Editor adapter checks.")
    parser.add_argument("--strict-integration", action="store_true", help="Fail when local O3DE tooling is unavailable.")
    parser.add_argument("--allow-live-o3de-commands", action="store_true", help="Set the hard live-command gate for future private runs.")
    parser.add_argument("--golden-project-fixture", default=str(DEFAULT_GOLDEN_PROJECT_FIXTURE), help="Golden project fixture contract path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def print_text_report(report: Mapping[str, Any]) -> None:
    print(f"O3DE integration suite: {report['status']}")
    print(f"mode: {report['mode']}")
    print(f"strict_integration: {str(report['strict_integration']).lower()}")
    print(f"live_commands_allowed: {str(report['live_commands_allowed']).lower()}")
    print(f"live_o3de_execution: {str(report['live_o3de_execution']).lower()}")
    print(f"golden_project_fixture_ref: {report.get('golden_project_fixture_ref', '')}")
    for code in report.get("errors", []):
        print(f"  error: {code}")
    for code in report.get("warnings", []):
        print(f"  warning: {code}")
    for command in report.get("commands", []):
        print(f"  {command['label']}: exit {command['return_code']}")
        if command.get("reported_skipped"):
            print("    reported skipped/unavailable")


def main() -> int:
    args = _parse_args()
    mode = "integration" if args.enable_o3de_integration else args.mode
    report = run_integration_suite(
        mode=mode,
        dry_run=args.dry_run,
        enable_o3de_integration=args.enable_o3de_integration,
        strict_integration=args.strict_integration,
        allow_live_o3de_commands=args.allow_live_o3de_commands,
        golden_project_fixture=args.golden_project_fixture,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report)
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
