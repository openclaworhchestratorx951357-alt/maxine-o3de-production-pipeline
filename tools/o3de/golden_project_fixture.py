#!/usr/bin/env python3
"""Fixture-backed O3DE golden project contract validator."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ci.o3de_runner_readiness import MXN_VALIDATION_TOOL_UNAVAILABLE, build_readiness_report
from tools.validation.results import ValidationResult
from tools.validation.schema_utils import load_json, schema_validate


SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine.o3de-golden-project-fixture.schema.json"
FIXTURE_DIR = REPO_ROOT / "examples" / "o3de-golden-project"
DEFAULT_FIXTURE = FIXTURE_DIR / "maxine-golden-project.fixture.json"

MXN_PATH_UNSAFE = "MXN_PATH_UNSAFE"
MXN_ASSET_PRODUCT_MISSING = "MXN_ASSET_PRODUCT_MISSING"
MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN = "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN"
MXN_PROVENANCE_INCOMPLETE = "MXN_PROVENANCE_INCOMPLETE"
MXN_UNDO_PLAN_MISSING = "MXN_UNDO_PLAN_MISSING"


def load_fixture_files(path: Path | str = FIXTURE_DIR) -> List[Tuple[str, Dict[str, Any]]]:
    fixture_root = _resolve_path(path)
    files = sorted(fixture_root.glob("*.json")) if fixture_root.is_dir() else [fixture_root]
    return [(_case_id(fixture_file), load_json(fixture_file)) for fixture_file in files]


def validate_golden_project_fixture(payload: Mapping[str, Any], *, strict: bool = True) -> ValidationResult:
    if str(payload.get("mode", "")).strip() == "unavailable" and str(payload.get("status", "")).strip() == "skipped":
        return ValidationResult(status="skipped")

    result = ValidationResult()
    _validate_project_roots(payload, result)
    _validate_temp_level_policy(payload, result)
    _validate_release_proof(payload, result, strict=strict)
    _validate_live_flags(payload, result)
    return result


def run_golden_project_fixture(
    fixture: Path | str = DEFAULT_FIXTURE,
    *,
    check_local_readiness: bool = False,
    strict: bool = False,
    env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    path = _resolve_path(fixture)
    if check_local_readiness:
        return _run_local_readiness(path, strict=strict, env=env)
    if path.is_dir():
        return _run_fixture_directory(path)
    return _run_fixture_file(path)


def _run_fixture_directory(path: Path) -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    all_errors: List[str] = []
    all_warnings: List[str] = []
    schema = load_json(SCHEMA_PATH)
    for case_id, payload in load_fixture_files(path):
        schema_result = schema_validate(payload, schema)
        validation = validate_golden_project_fixture(payload, strict=True)
        expected_status = str(payload.get("status", "")).strip()
        observed_status = validation.status
        case_passed = schema_result.status == "pass" and observed_status == expected_status
        errors = _unique(schema_result.error_codes + validation.error_codes)
        warnings = _unique(schema_result.warning_codes + validation.warning_codes)
        if not case_passed:
            all_errors.extend(errors)
            all_warnings.extend(warnings)
        cases.append(
            {
                "case_id": case_id,
                "expected_status": expected_status,
                "observed_status": observed_status,
                "status": "pass" if case_passed else "fail",
                "errors": errors,
                "warnings": warnings,
                "messages": schema_result.messages + validation.messages,
            }
        )
    status = "pass" if cases and all(case["status"] == "pass" for case in cases) else "fail"
    return _summary_payload(
        mode="fixture",
        status=status,
        cases=cases,
        errors=_unique(all_errors),
        warnings=_unique(all_warnings),
        evidence_refs=[{"id": "o3de-golden-project-fixtures", "kind": "fixture_directory", "path": _repo_relative(path)}],
    )


def _run_fixture_file(path: Path) -> Dict[str, Any]:
    schema = load_json(SCHEMA_PATH)
    payload = load_json(path)
    schema_result = schema_validate(payload, schema)
    validation = validate_golden_project_fixture(payload, strict=True)
    errors = _unique(schema_result.error_codes + validation.error_codes)
    warnings = _unique(schema_result.warning_codes + validation.warning_codes)
    status = "fail" if schema_result.status == "fail" else validation.status
    return _summary_payload(
        mode=str(payload.get("mode", "fixture")),
        status=status,
        cases=[],
        errors=errors,
        warnings=warnings,
        messages=schema_result.messages + validation.messages,
        evidence_refs=[{"id": str(payload.get("fixture_id", path.stem)), "kind": "fixture_file", "path": _repo_relative(path)}],
        fixture_id=str(payload.get("fixture_id", "")),
    )


def _run_local_readiness(path: Path, *, strict: bool, env: Mapping[str, str] | None) -> Dict[str, Any]:
    fixture_report = _run_fixture_file(path)
    if fixture_report["status"] == "fail":
        return fixture_report
    readiness = build_readiness_report(env=env, strict=strict, golden_project_fixture=path)
    status = readiness["status"]
    mode = "local_readiness" if status == "pass" else "unavailable"
    return _summary_payload(
        mode=mode,
        status=status,
        cases=[],
        errors=list(readiness.get("errors", [])),
        warnings=list(readiness.get("warnings", [])),
        messages=list(readiness.get("messages", [])),
        integration_enabled=True,
        strict_local_readiness=strict,
        readiness=readiness,
        evidence_refs=[
            {"id": "o3de-golden-project-readiness", "kind": "local_readiness", "path": _repo_relative(path)}
        ],
    )


def _summary_payload(
    *,
    mode: str,
    status: str,
    cases: List[Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
    messages: List[str] | None = None,
    evidence_refs: List[Dict[str, Any]] | None = None,
    **extra: Any,
) -> Dict[str, Any]:
    payload = {
        "schema_version": "1.0.0",
        "report_type": "maxine_o3de_golden_project_fixture_summary",
        "report_id": "o3de-golden-project-fixture-summary",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": mode,
        "status": status,
        "integration_enabled": False,
        "live_o3de_execution": False,
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "cases": cases,
        "errors": errors,
        "warnings": warnings,
        "messages": messages or [],
        "evidence_refs": evidence_refs or [],
    }
    payload.update(extra)
    return payload


def _validate_project_roots(payload: Mapping[str, Any], result: ValidationResult) -> None:
    project = _mapping(payload.get("project"))
    allowed_roots = _string_list(project.get("allowed_project_relative_roots"))
    forbidden_roots = _string_list(project.get("forbidden_roots"))
    if not allowed_roots:
        result.add_error(MXN_PATH_UNSAFE, "Golden project fixture must define allowed project-relative roots.")
    for root in allowed_roots + forbidden_roots:
        _require_safe_path(root, "project root policy", result)

    paths_to_check: List[Tuple[str, str]] = []
    for section_name in ("source_layout", "expected_artifact_paths"):
        section = _mapping(payload.get(section_name))
        for key, value in section.items():
            if isinstance(value, str):
                paths_to_check.append((f"{section_name}.{key}", value))
    temp_policy = _mapping(payload.get("temp_level_policy"))
    if isinstance(temp_policy.get("level_root"), str):
        paths_to_check.append(("temp_level_policy.level_root", str(temp_policy["level_root"])))

    for label, value in paths_to_check:
        normalized = _normalize_project_path(value)
        if not _require_safe_path(value, label, result):
            continue
        if _matches_forbidden_root(normalized, forbidden_roots):
            result.add_error(MXN_PATH_UNSAFE, f"{label} uses forbidden project root: {value}")
        if allowed_roots and not _matches_allowed_root(normalized, allowed_roots):
            result.add_error(MXN_PATH_UNSAFE, f"{label} is outside allowed project roots: {value}")


def _validate_temp_level_policy(payload: Mapping[str, Any], result: ValidationResult) -> None:
    policy = _mapping(payload.get("temp_level_policy"))
    level_root = _normalize_project_path(str(policy.get("level_root", "")))
    if not policy.get("enabled"):
        result.add_error(MXN_PATH_UNSAFE, "Temp level policy must be enabled for fixture/private runner smoke prep.")
    if not policy.get("never_use_production_levels"):
        result.add_error(MXN_PATH_UNSAFE, "Temp level policy must forbid production levels by default.")
    if policy.get("allow_existing_level_readonly") is True:
        result.add_error(MXN_PATH_UNSAFE, "Fixture bridge must not use existing levels by default.")
    if not level_root.startswith("Levels/_maxine_smoke"):
        result.add_error(MXN_PATH_UNSAFE, "Temp level root must stay under Levels/_maxine_smoke.")
    if not str(policy.get("cleanup_policy", "")).strip():
        result.add_error(MXN_UNDO_PLAN_MISSING, "Temp level policy must declare dry-run cleanup/undo expectations.")
    if not str(policy.get("naming_prefix", "")).strip().startswith("maxine_smoke_"):
        result.add_error(MXN_PATH_UNSAFE, "Temp level naming prefix must use maxine_smoke_.")


def _validate_release_proof(payload: Mapping[str, Any], result: ValidationResult, *, strict: bool) -> None:
    evidence_by_lane = _mapping(_mapping(payload.get("evidence_expectations")).get("by_lane"))
    product_by_lane = _mapping(_mapping(payload.get("product_expectations")).get("by_lane"))
    for lane in ("release_rigged", "external_rig_import"):
        evidence = _mapping(evidence_by_lane.get(lane))
        products = _mapping(product_by_lane.get(lane))
        if not evidence and lane == "external_rig_import":
            continue
        if products.get("cache_heuristic_used") or evidence.get("cache_heuristic_used"):
            result.add_error(
                MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN,
                f"{lane} golden project proof cannot rely on cache-heuristic products or package refs.",
            )
        if not any(str(evidence.get(field, "")).strip() for field in ("package_ref", "prefab_ref", "procprefab_ref")):
            result.add_error(MXN_ASSET_PRODUCT_MISSING, f"{lane} must define package, prefab, or procprefab reference.")
        required_refs = ("product_resolver_report_ref", "asset_processor_batch_report_ref", "editor_smoke_report_ref")
        missing_refs = [field for field in required_refs if not str(evidence.get(field, "")).strip()]
        if strict and missing_refs:
            result.add_error(MXN_PROVENANCE_INCOMPLETE, f"{lane} is missing evidence refs: {', '.join(missing_refs)}.")
        if not str(evidence.get("undo_plan_ref", "")).strip() and not _mapping(payload.get("temp_level_policy")).get("cleanup_policy"):
            result.add_error(MXN_UNDO_PLAN_MISSING, f"{lane} must include undo/cleanup evidence.")


def _validate_live_flags(payload: Mapping[str, Any], result: ValidationResult) -> None:
    mode = str(payload.get("mode", "")).strip()
    if mode in {"fixture", "unavailable"}:
        for key in ("live_o3de_execution", "live_asset_processor_batch_execution", "live_editor_execution"):
            if payload.get(key) is True:
                result.add_error("MXN_RUNTIME_SMOKE_FAIL", f"{key} cannot be true in {mode} mode.")


def _require_safe_path(value: str, label: str, result: ValidationResult) -> bool:
    normalized = _normalize_project_path(value)
    if not normalized:
        result.add_error(MXN_PATH_UNSAFE, f"{label} path is empty.")
        return False
    if re.match(r"^[A-Za-z]:", value.strip()) or value.startswith(("/", "\\")):
        result.add_error(MXN_PATH_UNSAFE, f"{label} must be project-relative, not absolute: {value}")
        return False
    if ".." in PurePosixPath(normalized).parts:
        result.add_error(MXN_PATH_UNSAFE, f"{label} must not use parent traversal: {value}")
        return False
    return True


def _matches_allowed_root(path: str, roots: Iterable[str]) -> bool:
    return any(path == _normalize_project_path(root) or path.startswith(_normalize_project_path(root).rstrip("/") + "/") for root in roots)


def _matches_forbidden_root(path: str, roots: Iterable[str]) -> bool:
    return any(path == _normalize_project_path(root) or path.startswith(_normalize_project_path(root).rstrip("/") + "/") for root in roots)


def _normalize_project_path(value: str) -> str:
    return str(value).strip().replace("\\", "/").strip("/")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> List[str]:
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _resolve_path(path: Path | str) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else REPO_ROOT / resolved


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _case_id(path: Path) -> str:
    return path.name.removesuffix(".fixture.json").removesuffix(".fail.json").removesuffix(".skipped.json")


def _unique(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the MAXINE O3DE golden project fixture contract.")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE), help="Golden project fixture file.")
    parser.add_argument("--fixtures", help="Golden project fixture directory.")
    parser.add_argument("--check-local-readiness", action="store_true", help="Inspect local O3DE project/tool readiness without mutation.")
    parser.add_argument("--strict", action="store_true", help="Fail when local O3DE project/tooling is unavailable.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def print_text_report(report: Mapping[str, Any]) -> None:
    print(f"Golden project fixture: {report['status']}")
    print(f"mode: {report['mode']}")
    print(f"live_o3de_execution: {str(report['live_o3de_execution']).lower()}")
    print(f"live_asset_processor_batch_execution: {str(report['live_asset_processor_batch_execution']).lower()}")
    print(f"live_editor_execution: {str(report['live_editor_execution']).lower()}")
    for code in report.get("errors", []):
        print(f"  error: {code}")
    for code in report.get("warnings", []):
        print(f"  warning: {code}")
    for message in report.get("messages", []):
        print(f"  - {message}")
    for case in report.get("cases", []):
        print(f"  {case['case_id']}: expected {case['expected_status']}, observed {case['observed_status']} -> {case['status']}")


def main() -> int:
    args = _parse_args()
    target = args.fixtures if args.fixtures else args.fixture
    result = run_golden_project_fixture(
        target,
        check_local_readiness=args.check_local_readiness,
        strict=args.strict,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_text_report(result)
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
