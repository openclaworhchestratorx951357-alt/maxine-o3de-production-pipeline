#!/usr/bin/env python3
"""APB dry-run checklist for a private Windows O3DE runner.

This checklist never executes Asset Processor Batch or Editor. It verifies the
repo-side setup contract and reports local tool/path readiness for a future APB
run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ci.o3de_runner_readiness import MXN_VALIDATION_TOOL_UNAVAILABLE, build_readiness_report
from tools.o3de.golden_project_fixture import DEFAULT_FIXTURE as DEFAULT_GOLDEN_PROJECT_FIXTURE
from tools.o3de.golden_project_fixture import run_golden_project_fixture


ENV_TEMPLATE = REPO_ROOT / "examples" / "private-runner" / "o3de-runner.env.example"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "o3de-private-windows-integration.yml"
DEFAULT_GOLDEN_CORPUS = REPO_ROOT / "examples" / "golden-corpus"
MXN_PROVENANCE_INCOMPLETE = "MXN_PROVENANCE_INCOMPLETE"


def build_dry_run_checklist_report(
    *,
    env: Mapping[str, str] | None = None,
    strict: bool = False,
    env_template: Path | str = ENV_TEMPLATE,
    golden_project_fixture: Path | str = DEFAULT_GOLDEN_PROJECT_FIXTURE,
    golden_corpus: Path | str = DEFAULT_GOLDEN_CORPUS,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    env_template_path = _resolve_path(env_template)
    fixture_path = _resolve_path(golden_project_fixture)
    corpus_path = _resolve_path(golden_corpus)

    readiness = build_readiness_report(env=env, strict=strict, golden_project_fixture=fixture_path)
    golden_fixture = run_golden_project_fixture(fixture_path)

    checks = {
        "repo_validation": _documented_check("Run python tools/validation/validate_all.py before live APB."),
        "env_template_present": _file_check(env_template_path, "Private runner env template exists."),
        "env_template_safe": _env_template_safety_check(env_template_path),
        "runner_readiness": _readiness_check(readiness, strict=strict),
        "golden_project_fixture": _summary_check(golden_fixture, "Golden project fixture contract validates."),
        "apb_readiness": _apb_readiness_check(readiness, strict=strict),
        "fixture_suite": _documented_check("Run python tools/ci/run_o3de_integration_suite.py --mode fixture."),
        "workflow_manual_only": _workflow_manual_only_check(WORKFLOW),
        "workflow_private_runner_labels": _workflow_private_labels_check(WORKFLOW),
        "editor_gates_disabled": _editor_gates_disabled_check(env),
        "publication_blocked": _publication_blocked_check(WORKFLOW),
    }

    errors: list[str] = []
    warnings: list[str] = []
    for check in checks.values():
        errors.extend(check.get("errors", []))
        warnings.extend(check.get("warnings", []))

    status = "fail" if errors else "skipped" if warnings else "pass"
    report = {
        "schema_version": "1.0.0",
        "report_type": "maxine_private_runner_apb_dry_run_checklist",
        "generated_at": _utc_now(),
        "status": status,
        "strict": strict,
        "live_commands_allowed": str(env.get("MAXINE_ALLOW_LIVE_O3DE_COMMANDS", "")).strip() == "1",
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "live_publication": False,
        "env_template_ref": _repo_relative(env_template_path),
        "golden_project_fixture_ref": _repo_relative(fixture_path),
        "golden_corpus_ref": _repo_relative(corpus_path),
        "checks": checks,
        "errors": _unique(errors),
        "warnings": _unique(warnings),
        "messages": _messages(status=status, strict=strict),
        "next_steps": _next_steps(status=status, strict=strict),
    }
    return report


def _file_check(path: Path, message: str) -> Dict[str, Any]:
    if path.exists():
        return {"status": "pass", "path": _repo_relative(path), "messages": [message], "errors": [], "warnings": []}
    return {
        "status": "fail",
        "path": _repo_relative(path),
        "messages": [f"Missing required file: {_repo_relative(path)}"],
        "errors": [MXN_PROVENANCE_INCOMPLETE],
        "warnings": [],
    }


def _env_template_safety_check(path: Path) -> Dict[str, Any]:
    file_check = _file_check(path, "Private runner env template exists.")
    if file_check["status"] == "fail":
        return file_check
    assignments = _env_assignments(path)
    errors: list[str] = []
    messages: list[str] = []
    for key, value in assignments.items():
        lowered_key = key.lower()
        lowered_value = value.lower()
        if any(marker in lowered_key for marker in ("token", "password", "secret", "credential", "api_key")):
            errors.append(MXN_PROVENANCE_INCOMPLETE)
            messages.append(f"Unsafe secret-like env key in template: {key}")
        if any(marker in lowered_value for marker in ("ghp_", "gho_", "<token>")):
            errors.append(MXN_PROVENANCE_INCOMPLETE)
            messages.append(f"Unsafe secret-like env value in template: {key}")
    expected = {
        "MAXINE_ENABLE_O3DE_EDITOR_SMOKE": "0",
        "MAXINE_ALLOW_LIVE_O3DE_COMMANDS": "0",
        "MAXINE_GOLDEN_PROJECT_FIXTURE": "examples/o3de-golden-project/maxine-golden-project.fixture.json",
        "MAXINE_GOLDEN_CORPUS": "examples/golden-corpus",
    }
    for key, expected_value in expected.items():
        if assignments.get(key) != expected_value:
            errors.append(MXN_PROVENANCE_INCOMPLETE)
            messages.append(f"{key} must default to {expected_value}.")
    return {
        "status": "fail" if errors else "pass",
        "path": _repo_relative(path),
        "messages": messages or ["Env template contains no secret assignments and keeps live/Editor gates safe by default."],
        "errors": _unique(errors),
        "warnings": [],
    }


def _readiness_check(readiness: Mapping[str, Any], *, strict: bool) -> Dict[str, Any]:
    status = str(readiness.get("status", "fail"))
    return {
        "status": status,
        "messages": list(readiness.get("messages", [])),
        "errors": list(readiness.get("errors", [])),
        "warnings": [] if strict else list(readiness.get("warnings", [])),
    }


def _summary_check(summary: Mapping[str, Any], message: str) -> Dict[str, Any]:
    status = str(summary.get("status", "fail"))
    return {
        "status": status,
        "messages": [message] + list(summary.get("messages", [])),
        "errors": list(summary.get("errors", [])),
        "warnings": list(summary.get("warnings", [])),
    }


def _apb_readiness_check(readiness: Mapping[str, Any], *, strict: bool) -> Dict[str, Any]:
    apb = readiness.get("tools", {}).get("asset_processor_batch", {}) if isinstance(readiness.get("tools"), Mapping) else {}
    if apb.get("available"):
        return {
            "status": "pass",
            "messages": ["AssetProcessorBatch executable is detected; dry-run still does not execute it."],
            "errors": [],
            "warnings": [],
        }
    payload = {
        "status": "fail" if strict else "skipped",
        "messages": ["AssetProcessorBatch executable is unavailable; dry-run does not execute APB."],
        "errors": [MXN_VALIDATION_TOOL_UNAVAILABLE] if strict else [],
        "warnings": [] if strict else [MXN_VALIDATION_TOOL_UNAVAILABLE],
    }
    return payload


def _workflow_manual_only_check(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    errors: list[str] = []
    if "workflow_dispatch:" not in text:
        errors.append(MXN_PROVENANCE_INCOMPLETE)
    if "\npush:" in text or "pull_request:" in text:
        errors.append(MXN_PROVENANCE_INCOMPLETE)
    if "I_UNDERSTAND_THIS_REQUIRES_A_PRIVATE_SELF_HOSTED_WINDOWS_RUNNER" not in text:
        errors.append(MXN_PROVENANCE_INCOMPLETE)
    return {
        "status": "fail" if errors else "pass",
        "messages": ["Workflow is manual-only and has the private runner confirmation guard."],
        "errors": _unique(errors),
        "warnings": [],
    }


def _workflow_private_labels_check(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    ok = "runs-on: [self-hosted, Windows, X64, o3de, maxine-private]" in text
    return {
        "status": "pass" if ok else "fail",
        "messages": ["Workflow targets private self-hosted Windows O3DE labels."],
        "errors": [] if ok else [MXN_PROVENANCE_INCOMPLETE],
        "warnings": [],
    }


def _editor_gates_disabled_check(env: Mapping[str, str]) -> Dict[str, Any]:
    enabled = str(env.get("MAXINE_ENABLE_O3DE_EDITOR_SMOKE", "")).strip() == "1"
    return {
        "status": "fail" if enabled else "pass",
        "messages": ["Editor smoke gate is disabled for APB-only dry-run."],
        "errors": [MXN_PROVENANCE_INCOMPLETE] if enabled else [],
        "warnings": [],
    }


def _publication_blocked_check(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig").lower() if path.exists() else ""
    forbidden = "publish" in text or "release packaging" in text
    return {
        "status": "fail" if forbidden else "pass",
        "messages": ["Workflow contains no publication step."],
        "errors": [MXN_PROVENANCE_INCOMPLETE] if forbidden else [],
        "warnings": [],
    }


def _documented_check(message: str) -> Dict[str, Any]:
    return {"status": "documented", "messages": [message], "errors": [], "warnings": []}


def _env_assignments(path: Path) -> Dict[str, str]:
    assignments: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        assignments[key.strip()] = value.strip()
    return assignments


def _messages(*, status: str, strict: bool) -> list[str]:
    if status == "pass":
        return ["Dry-run checklist is ready for the first APB-only live runbook handoff; no live APB ran."]
    if status == "fail" and strict:
        return ["Strict dry-run checklist failed because required private runner O3DE/APB readiness is unavailable."]
    if status == "fail":
        return ["Dry-run checklist found a repo-side safety/configuration problem."]
    return ["Dry-run checklist skipped unavailable O3DE/APB readiness; no live APB, Editor, or publication ran."]


def _next_steps(*, status: str, strict: bool) -> list[str]:
    if status == "pass":
        return [
            "Run the fixture suite on the private runner.",
            "Review artifacts for secrets before any future APB live run.",
            "Keep Editor smoke disabled until the Editor live smoke slice.",
        ]
    return [
        "Fill in O3DE_ENGINE_ROOT, O3DE_PROJECT_PATH, and ASSET_PROCESSOR_BATCH_EXECUTABLE on the private runner.",
        "Run python tools/ci/o3de_runner_readiness.py --json.",
        "Run python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --check-local-readiness.",
    ]


def _resolve_path(path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def print_text_report(report: Mapping[str, Any]) -> None:
    print(f"Private runner APB dry-run checklist: {report['status']}")
    print(f"strict: {str(report['strict']).lower()}")
    print(f"live_commands_allowed: {str(report['live_commands_allowed']).lower()}")
    print(f"live_asset_processor_batch_execution: {str(report['live_asset_processor_batch_execution']).lower()}")
    print(f"live_editor_execution: {str(report['live_editor_execution']).lower()}")
    print(f"live_publication: {str(report['live_publication']).lower()}")
    print(f"env_template_ref: {report['env_template_ref']}")
    print(f"golden_project_fixture_ref: {report['golden_project_fixture_ref']}")
    for name, check in report.get("checks", {}).items():
        print(f"  {name}: {check.get('status')}")
    for code in report.get("errors", []):
        print(f"  error: {code}")
    for code in report.get("warnings", []):
        print(f"  warning: {code}")
    for message in report.get("messages", []):
        print(f"  - {message}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check private runner APB dry-run readiness without executing APB.")
    parser.add_argument("--strict", action="store_true", help="Fail if local O3DE/APB readiness is unavailable.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    parser.add_argument("--env-template", default=str(ENV_TEMPLATE), help="Private runner env template path.")
    parser.add_argument("--golden-project-fixture", default=str(DEFAULT_GOLDEN_PROJECT_FIXTURE), help="Golden project fixture path.")
    parser.add_argument("--golden-corpus", default=str(DEFAULT_GOLDEN_CORPUS), help="Golden corpus path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_dry_run_checklist_report(
        strict=args.strict,
        env_template=args.env_template,
        golden_project_fixture=args.golden_project_fixture,
        golden_corpus=args.golden_corpus,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report)
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
