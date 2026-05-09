#!/usr/bin/env python3
"""Offline readiness report for a private Windows O3DE integration runner."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"
EDITOR_TOOL_NAMES = ("Editor.exe", "O3DEEditor.exe", "Editor", "O3DEEditor")
APB_TOOL_NAMES = ("AssetProcessorBatch.exe", "AssetProcessorBatch")


def build_readiness_report(*, env: Mapping[str, str] | None = None, strict: bool = False) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    editor = _tool_report(
        explicit=env.get("O3DE_EDITOR_EXECUTABLE", ""),
        names=EDITOR_TOOL_NAMES,
        env=env,
    )
    apb = _tool_report(
        explicit=env.get("ASSET_PROCESSOR_BATCH_EXECUTABLE", "") or env.get("ASSET_PROCESSOR_BATCH", ""),
        names=APB_TOOL_NAMES,
        env=env,
    )
    engine_root = _path_report(env.get("O3DE_ENGINE_ROOT", ""))
    project_path = _path_report(env.get("O3DE_PROJECT_PATH", ""))
    live_commands_allowed = _enabled(env, "MAXINE_ALLOW_LIVE_O3DE_COMMANDS")
    missing = []
    if not engine_root["exists"]:
        missing.append("O3DE_ENGINE_ROOT")
    if not project_path["exists"]:
        missing.append("O3DE_PROJECT_PATH")
    if not editor["available"]:
        missing.append("O3DE Editor executable")
    if not apb["available"]:
        missing.append("AssetProcessorBatch executable")

    status = "pass"
    errors: list[str] = []
    warnings: list[str] = []
    if missing:
        status = "fail" if strict else "skipped"
        target = errors if strict else warnings
        target.append(MXN_VALIDATION_TOOL_UNAVAILABLE)

    report = {
        "schema_version": "1.0.0",
        "report_type": "maxine_o3de_runner_readiness",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": status,
        "strict": strict,
        "live_commands_allowed": live_commands_allowed,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "repository_root": str(REPO_ROOT),
        "env": {
            "O3DE_ENGINE_ROOT": engine_root["path"],
            "O3DE_PROJECT_PATH": project_path["path"],
            "O3DE_EDITOR_EXECUTABLE": str(env.get("O3DE_EDITOR_EXECUTABLE", "")).strip(),
            "ASSET_PROCESSOR_BATCH_EXECUTABLE": str(env.get("ASSET_PROCESSOR_BATCH_EXECUTABLE", env.get("ASSET_PROCESSOR_BATCH", ""))).strip(),
            "MAXINE_ENABLE_O3DE_INTEGRATION": _enabled(env, "MAXINE_ENABLE_O3DE_INTEGRATION"),
            "MAXINE_ENABLE_ASSET_PROCESSOR_BATCH": _enabled(env, "MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"),
            "MAXINE_ENABLE_O3DE_EDITOR_SMOKE": _enabled(env, "MAXINE_ENABLE_O3DE_EDITOR_SMOKE"),
            "MAXINE_ALLOW_LIVE_O3DE_COMMANDS": live_commands_allowed,
        },
        "paths": {
            "engine_root": engine_root,
            "project_path": project_path,
        },
        "tools": {
            "editor": editor,
            "asset_processor_batch": apb,
        },
        "would_run": _would_run(env, live_commands_allowed=live_commands_allowed),
        "errors": errors,
        "warnings": warnings,
        "messages": _messages(missing, live_commands_allowed=live_commands_allowed),
        "next_steps": _next_steps(missing),
    }
    return report


def _tool_report(*, explicit: str, names: Iterable[str], env: Mapping[str, str]) -> Dict[str, Any]:
    explicit = str(explicit).strip()
    path = explicit or _find_on_path(names, env)
    exists = bool(path) and Path(path).exists()
    return {
        "path": path,
        "available": bool(path) and exists,
        "exists": exists,
        "source": "environment" if explicit else "PATH" if path else "unavailable",
    }


def _path_report(raw: str) -> Dict[str, Any]:
    path = str(raw).strip()
    return {
        "path": path,
        "present": bool(path),
        "exists": bool(path) and Path(path).exists(),
    }


def _find_on_path(names: Iterable[str], env: Mapping[str, str]) -> str:
    for raw_entry in str(env.get("PATH", "")).split(os.pathsep):
        if not raw_entry.strip():
            continue
        directory = Path(raw_entry)
        for name in names:
            candidate = directory / name
            if candidate.exists() and candidate.is_file():
                return str(candidate)
    return ""


def _enabled(env: Mapping[str, str], key: str) -> bool:
    return str(env.get(key, "")).strip() == "1"


def _would_run(env: Mapping[str, str], *, live_commands_allowed: bool) -> Dict[str, Any]:
    enable_o3de = _enabled(env, "MAXINE_ENABLE_O3DE_INTEGRATION")
    return {
        "fixture_suite": True,
        "local_o3de_adapter": enable_o3de,
        "asset_processor_batch": enable_o3de or _enabled(env, "MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"),
        "editor_smoke": enable_o3de or _enabled(env, "MAXINE_ENABLE_O3DE_EDITOR_SMOKE"),
        "live_o3de_commands": live_commands_allowed,
    }


def _messages(missing: list[str], *, live_commands_allowed: bool) -> list[str]:
    messages = []
    if missing:
        messages.append("Local O3DE tooling is unavailable: " + ", ".join(missing) + ".")
    if not live_commands_allowed:
        messages.append("MAXINE_ALLOW_LIVE_O3DE_COMMANDS is not enabled; live O3DE commands remain blocked.")
    messages.append("Readiness checks do not register runners, require credentials, contact external services, or publish.")
    return messages


def _next_steps(missing: list[str]) -> list[str]:
    if not missing:
        return ["Run the fixture suite, then opt into non-strict integration checks on the private runner."]
    return [
        "Set O3DE_ENGINE_ROOT and O3DE_PROJECT_PATH on the private runner.",
        "Set O3DE_EDITOR_EXECUTABLE or make Editor available on PATH.",
        "Set ASSET_PROCESSOR_BATCH_EXECUTABLE or make AssetProcessorBatch available on PATH.",
    ]


def print_text_report(report: Mapping[str, Any]) -> None:
    print(f"O3DE runner readiness: {report['status']}")
    print(f"strict: {str(report['strict']).lower()}")
    print(f"live_commands_allowed: {str(report['live_commands_allowed']).lower()}")
    for code in report.get("errors", []):
        print(f"  error: {code}")
    for code in report.get("warnings", []):
        print(f"  warning: {code}")
    for message in report.get("messages", []):
        print(f"  - {message}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check private Windows O3DE runner readiness without executing O3DE.")
    parser.add_argument("--strict", action="store_true", help="Fail if local O3DE tooling is unavailable.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_readiness_report(strict=args.strict)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report)
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
