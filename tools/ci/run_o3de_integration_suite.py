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
DEFAULT_EDITOR_SMOKE_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"


def run_integration_suite(
    *,
    mode: str = "dry_run",
    dry_run: bool = False,
    enable_o3de_integration: bool = False,
    apb_only: bool = False,
    include_editor_smoke: bool = False,
    editor_smoke_only: bool = False,
    strict_integration: bool = False,
    allow_live_o3de_commands: bool = False,
    golden_project_fixture: Path | str = DEFAULT_GOLDEN_PROJECT_FIXTURE,
    editor_smoke_manifest: Path | str = DEFAULT_EDITOR_SMOKE_MANIFEST,
    env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    env_map = dict(env if env is not None else os.environ)
    if enable_o3de_integration:
        env_map["MAXINE_ENABLE_O3DE_INTEGRATION"] = "1"
        env_map["MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"] = "1"
        if include_editor_smoke or editor_smoke_only or not apb_only:
            env_map["MAXINE_ENABLE_O3DE_EDITOR_SMOKE"] = "1"
    if allow_live_o3de_commands:
        env_map["MAXINE_ALLOW_LIVE_O3DE_COMMANDS"] = "1"

    selected_mode = "dry_run" if dry_run else mode
    golden_fixture = Path(golden_project_fixture)
    golden_fixture = golden_fixture if golden_fixture.is_absolute() else REPO_ROOT / golden_fixture
    editor_manifest = Path(editor_smoke_manifest)
    editor_manifest = editor_manifest if editor_manifest.is_absolute() else REPO_ROOT / editor_manifest
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
        commands.extend(_run_fixture_commands(_fixture_env(env_map)))
        if any(command["return_code"] != 0 for command in commands):
            status = "fail"
    elif selected_mode == "integration":
        if editor_smoke_only:
            commands.extend(
                _run_editor_smoke_live_commands(
                    env_map,
                    strict_integration=strict_integration,
                    golden_project_fixture=golden_fixture,
                    editor_smoke_manifest=editor_manifest,
                )
            )
            if any(command["return_code"] != 0 for command in commands):
                status = "fail"
                errors.extend(_collect_command_error_codes(commands))
            elif any(command.get("reported_skipped") for command in commands):
                status = "skipped"
                warnings.extend([MXN_VALIDATION_TOOL_UNAVAILABLE])
            else:
                status = "pass"
        elif apb_only:
            commands.extend(
                _run_apb_only_commands(
                    env_map,
                    strict_integration=strict_integration,
                    golden_project_fixture=golden_fixture,
                )
            )
            if any(command["return_code"] != 0 for command in commands):
                status = "fail"
                errors.extend(_collect_command_error_codes(commands))
            elif any(command.get("reported_skipped") for command in commands):
                status = "skipped"
                warnings.extend([MXN_VALIDATION_TOOL_UNAVAILABLE])
            else:
                status = "pass"
        elif include_editor_smoke:
            commands.extend(
                _run_apb_only_commands(
                    env_map,
                    strict_integration=strict_integration,
                    golden_project_fixture=golden_fixture,
                )
            )
            if not any(command["return_code"] != 0 for command in commands):
                commands.extend(
                    _run_editor_smoke_live_commands(
                        env_map,
                        strict_integration=strict_integration,
                        golden_project_fixture=golden_fixture,
                        editor_smoke_manifest=editor_manifest,
                    )
                )
            if any(command["return_code"] != 0 for command in commands):
                status = "fail"
                errors.extend(_collect_command_error_codes(commands))
            elif any(command.get("reported_skipped") for command in commands):
                status = "skipped"
                warnings.extend([MXN_VALIDATION_TOOL_UNAVAILABLE])
            else:
                status = "pass"
        elif readiness["status"] == "fail":
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
        "apb_only": apb_only,
        "include_editor_smoke": include_editor_smoke,
        "editor_smoke_only": editor_smoke_only,
        "live_commands_allowed": str(env_map.get("MAXINE_ALLOW_LIVE_O3DE_COMMANDS", "")).strip() == "1",
        "live_o3de_execution": False,
        "live_asset_processor_batch_execution": _command_output_has(commands, "live_asset_processor_batch_execution: true"),
        "live_editor_execution": _command_output_has(commands, "live_editor_execution: true"),
        "live_runtime_execution": _command_output_has(commands, "live_runtime_execution: true"),
        "golden_project_fixture_ref": _repo_relative(golden_fixture),
        "editor_smoke_manifest_ref": _repo_relative(editor_manifest),
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
        _run_command(
            "runtime_harness fixture",
            [
                sys.executable,
                "tools/o3de/runtime_harness.py",
                "--manifest",
                "examples/manifests/release_rigged.pass.example.json",
                "--mode",
                "fixture",
            ],
            env,
        ),
    ]


def _fixture_env(env: Mapping[str, str]) -> Dict[str, str]:
    fixture_env = dict(env)
    for key in (
        "MAXINE_ENABLE_O3DE_INTEGRATION",
        "MAXINE_ENABLE_ASSET_PROCESSOR_BATCH",
        "MAXINE_ENABLE_O3DE_EDITOR_SMOKE",
        "MAXINE_ALLOW_LIVE_O3DE_COMMANDS",
        "MAXINE_ALLOW_LIVE_EDITOR_COMMANDS",
        "MAXINE_ENABLE_O3DE_RUNTIME_HARNESS",
        "MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS",
        "MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE",
        "MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION",
        "MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD",
        "MAXINE_ALLOW_LIVE_PUBLICATION",
        "MAXINE_ENABLE_RELEASE_PACKAGING",
    ):
        fixture_env.pop(key, None)
    return fixture_env


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


def _run_apb_only_commands(
    env: Mapping[str, str],
    *,
    strict_integration: bool,
    golden_project_fixture: Path,
) -> List[Dict[str, Any]]:
    strict_args = ["--strict-integration"] if strict_integration else []
    return [
        _run_command(
            "golden_project_fixture readiness",
            [
                sys.executable,
                "tools/o3de/golden_project_fixture.py",
                "--fixture",
                _repo_relative(golden_project_fixture),
            ],
            env,
        ),
        _run_command(
            "asset_processor_batch apb_only",
            [
                sys.executable,
                "tools/o3de/asset_processor_batch.py",
                "--corpus",
                "examples/golden-corpus",
                "--enable-asset-processor-batch",
                "--golden-project-fixture",
                _repo_relative(golden_project_fixture),
                *strict_args,
            ],
            env,
        ),
    ]


def _run_editor_smoke_readiness_commands(
    env: Mapping[str, str],
    *,
    strict_integration: bool,
    golden_project_fixture: Path,
    editor_smoke_manifest: Path,
) -> List[Dict[str, Any]]:
    strict_args = ["--strict"] if strict_integration else []
    return [
        _run_command(
            "editor_smoke readiness",
            [
                sys.executable,
                "tools/o3de/editor_smoke.py",
                "--manifest",
                _repo_relative(editor_smoke_manifest),
                "--check-local-readiness",
                "--golden-project-fixture",
                _repo_relative(golden_project_fixture),
                *strict_args,
            ],
            env,
        )
    ]


def _run_editor_smoke_live_commands(
    env: Mapping[str, str],
    *,
    strict_integration: bool,
    golden_project_fixture: Path,
    editor_smoke_manifest: Path,
) -> List[Dict[str, Any]]:
    strict_args = ["--strict-integration"] if strict_integration else []
    return [
        _run_command(
            "editor_smoke live",
            [
                sys.executable,
                "tools/o3de/editor_smoke.py",
                "--manifest",
                _repo_relative(editor_smoke_manifest),
                "--enable-editor-smoke",
                "--golden-project-fixture",
                _repo_relative(golden_project_fixture),
                *strict_args,
            ],
            env,
        )
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


def _collect_command_error_codes(commands: List[Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    for command in commands:
        combined = f"{command.get('stdout', '')}\n{command.get('stderr', '')}"
        if MXN_VALIDATION_TOOL_UNAVAILABLE in combined:
            errors.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
    return _unique(errors)


def _command_output_has(commands: List[Dict[str, Any]], needle: str) -> bool:
    needle = needle.lower()
    return any(needle in str(command.get("stdout", "")).lower() for command in commands)


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
    parser.add_argument("--apb-only", action="store_true", help="Run only the APB integration path; do not run Editor smoke.")
    parser.add_argument("--include-editor-smoke", action="store_true", help="Run APB baseline followed by gated live Editor smoke.")
    parser.add_argument("--editor-smoke-only", action="store_true", help="Run only gated Editor smoke readiness.")
    parser.add_argument("--strict-integration", action="store_true", help="Fail when local O3DE tooling is unavailable.")
    parser.add_argument("--allow-live-o3de-commands", action="store_true", help="Set the hard live-command gate for future private runs.")
    parser.add_argument("--golden-project-fixture", default=str(DEFAULT_GOLDEN_PROJECT_FIXTURE), help="Golden project fixture contract path.")
    parser.add_argument("--editor-smoke-manifest", default=str(DEFAULT_EDITOR_SMOKE_MANIFEST), help="Editor smoke manifest path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def print_text_report(report: Mapping[str, Any]) -> None:
    print(f"O3DE integration suite: {report['status']}")
    print(f"mode: {report['mode']}")
    print(f"strict_integration: {str(report['strict_integration']).lower()}")
    print(f"apb_only: {str(report.get('apb_only', False)).lower()}")
    print(f"include_editor_smoke: {str(report.get('include_editor_smoke', False)).lower()}")
    print(f"editor_smoke_only: {str(report.get('editor_smoke_only', False)).lower()}")
    print(f"live_commands_allowed: {str(report['live_commands_allowed']).lower()}")
    print(f"live_o3de_execution: {str(report['live_o3de_execution']).lower()}")
    print(f"live_asset_processor_batch_execution: {str(report.get('live_asset_processor_batch_execution', False)).lower()}")
    print(f"live_editor_execution: {str(report.get('live_editor_execution', False)).lower()}")
    print(f"live_runtime_execution: {str(report.get('live_runtime_execution', False)).lower()}")
    print(f"golden_project_fixture_ref: {report.get('golden_project_fixture_ref', '')}")
    print(f"editor_smoke_manifest_ref: {report.get('editor_smoke_manifest_ref', '')}")
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
        apb_only=args.apb_only,
        include_editor_smoke=args.include_editor_smoke,
        editor_smoke_only=args.editor_smoke_only,
        strict_integration=args.strict_integration,
        allow_live_o3de_commands=args.allow_live_o3de_commands,
        golden_project_fixture=args.golden_project_fixture,
        editor_smoke_manifest=args.editor_smoke_manifest,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report)
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
