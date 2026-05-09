#!/usr/bin/env python3
"""Fixture-backed and integration-gated O3DE Editor Python smoke bridge."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.o3de.product_matrix_resolver import validate_expected_products
from tools.o3de.product_resolver import ProductRecord
from tools.validation.results import ValidationResult
from tools.validation.schema_utils import load_json, schema_validate


MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"
SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine.editor-smoke-report.schema.json"
DEFAULT_CORPUS = REPO_ROOT / "examples" / "editor-smoke"
DEFAULT_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"
EDITOR_TOOL_NAMES = ("Editor.exe", "O3DEEditor.exe", "Editor", "O3DEEditor")
EDITOR_SCRIPT = REPO_ROOT / "tools" / "o3de" / "editor_python" / "maxine_package_prefab_smoke.py"


def load_fixture_reports(corpus: Path | str) -> List[Tuple[str, Dict[str, Any]]]:
    corpus_path = _resolve_path(corpus)
    reports: List[Tuple[str, Dict[str, Any]]] = []
    for path in sorted(corpus_path.glob("*.report.json")):
        case_id = path.name.replace(".fixture.report.json", "").replace(".fail.report.json", "").replace(".skipped.report.json", "")
        case_id = case_id.replace(".", "_")
        reports.append((case_id, load_json(path)))
    return reports


def validate_editor_smoke_report(report: Mapping[str, Any], *, strict: bool = True) -> ValidationResult:
    if str(report.get("mode", "")).strip() == "unavailable" and str(report.get("status", "")).strip() == "skipped":
        return ValidationResult(status="skipped")

    result = ValidationResult()
    lane = str(report.get("lane", "")).strip()
    products = _product_records(report)
    cache_heuristic_used = bool(report.get("cache_heuristic_used", False)) or any(
        _uses_cache_heuristic(product) for product in products
    )
    result.merge(
        validate_expected_products(
            lane,
            products,
            strict=strict,
            publish_tier="package",
            cache_heuristic_used=cache_heuristic_used,
        )
    )

    if report.get("live_editor_execution") is True and str(report.get("mode", "")) in {"fixture", "unavailable"}:
        result.add_error("MXN_RUNTIME_SMOKE_FAIL", "Fixture/skipped Editor smoke reports cannot claim live Editor execution.")

    if lane in {"release_rigged", "external_rig_import"}:
        if not any(str(report.get(field, "")).strip() for field in ("package_ref", "prefab_ref", "procprefab_ref")):
            result.add_error(
                "MXN_ASSET_PRODUCT_MISSING",
                "Release Editor smoke requires package, prefab, or procprefab reference; spawn-only evidence is insufficient.",
            )
        if not str(report.get("product_resolver_report_ref", "")).strip():
            result.add_error("MXN_PROVENANCE_INCOMPLETE", "Release Editor smoke requires product resolver evidence reference.")
        if not str(report.get("asset_processor_batch_report_ref", "")).strip():
            result.add_error("MXN_PROVENANCE_INCOMPLETE", "Release Editor smoke requires Asset Processor Batch proof reference.")
        if not str(report.get("source_uuid", "")).strip():
            result.add_error("MXN_PROVENANCE_INCOMPLETE", "Release Editor smoke requires source UUID identity.")
        for product in products:
            if _uses_cache_heuristic(product):
                continue
            if product.status == "ready" and (not product.source_uuid or not product.produced_by_source_uuid):
                result.add_error(
                    "MXN_PROVENANCE_INCOMPLETE",
                    f"Release Editor smoke product {product.product_type} lacks source UUID product identity.",
                )
        if cache_heuristic_used and "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" not in result.error_codes:
            result.add_error(
                "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN",
                "Release Editor smoke cannot rely on cache-heuristic package or product evidence.",
            )

    expected = {str(product_type).strip() for product_type in report.get("expected_products", []) if str(product_type).strip()}
    present = {product.product_type for product in products if product.status == "ready"}
    for product_type in sorted(expected - present):
        if product_type in report.get("missing_products", []):
            result.add_error("MXN_ASSET_PRODUCT_MISSING", f"Editor smoke proof is missing expected product: {product_type}")

    missing_components = [str(component).strip() for component in report.get("missing_components", []) if str(component).strip()]
    for component in missing_components:
        result.add_error("MXN_RUNTIME_SMOKE_FAIL", f"Editor smoke fixture is missing expected component: {component}")

    result.details["cache_heuristic_used"] = cache_heuristic_used
    return result


def run_editor_smoke_corpus(
    corpus: Path | str = DEFAULT_CORPUS,
    *,
    mode: str = "fixture",
    manifest: Path | str = DEFAULT_MANIFEST,
    enable_editor_smoke: bool = False,
    strict_integration: bool = False,
    platform: str = "pc",
    env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    if enable_editor_smoke or editor_smoke_gate_enabled(env) or mode == "local_editor_python":
        return _unavailable_integration_report(
            manifest=manifest,
            strict_integration=strict_integration,
            platform=platform,
            env=env,
        )
    return _fixture_corpus_report(_resolve_path(corpus), manifest=manifest, platform=platform)


def _fixture_corpus_report(corpus: Path, *, manifest: Path | str, platform: str) -> Dict[str, Any]:
    schema = load_json(SCHEMA_PATH)
    cases: List[Dict[str, Any]] = []
    all_errors: List[str] = []
    all_warnings: List[str] = []
    for case_id, report in load_fixture_reports(corpus):
        schema_result = schema_validate(report, schema)
        validation = validate_editor_smoke_report(report, strict=True)
        expected_status = str(report.get("status", "")).strip()
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
    return {
        "schema_version": "1.0.0",
        "report_type": "editor_smoke_fixture_bridge_summary_v1",
        "report_id": "editor-smoke-fixture-bridge-summary",
        "mode": "fixture",
        "status": status,
        "integration_enabled": False,
        "strict_integration": False,
        "live_editor_execution": False,
        "platform": platform,
        "manifest_ref": _repo_relative(_resolve_path(manifest)),
        "cases": cases,
        "errors": _unique(all_errors),
        "warnings": _unique(all_warnings),
        "evidence_refs": [
            {
                "id": "editor-smoke-fixture-corpus",
                "kind": "editor_smoke_fixture_corpus",
                "path": _repo_relative(corpus),
            }
        ],
    }


def _unavailable_integration_report(
    *,
    manifest: Path | str,
    strict_integration: bool,
    platform: str,
    env: Mapping[str, str],
) -> Dict[str, Any]:
    detection = detect_editor_smoke_environment(env)
    status = "fail" if strict_integration else "skipped"
    errors = [MXN_VALIDATION_TOOL_UNAVAILABLE] if strict_integration else []
    warnings = [] if strict_integration else [MXN_VALIDATION_TOOL_UNAVAILABLE]
    return {
        "schema_version": "1.0.0",
        "report_type": "editor_smoke_fixture_bridge_summary_v1",
        "report_id": "editor-smoke-local-integration",
        "mode": "unavailable",
        "status": status,
        "integration_enabled": True,
        "strict_integration": strict_integration,
        "live_editor_execution": False,
        "editor_python_bindings_required": True,
        "editor_python_bindings_available": False,
        "o3de_engine_root_present": bool(detection["engine_root"]),
        "o3de_project_path_present": bool(detection["project_path"]),
        "editor_executable": detection["editor_executable"],
        "command_preview": detection["command_preview"],
        "exit_code": None,
        "stdout_log_ref": "",
        "stderr_log_ref": "",
        "editor_log_ref": "",
        "asset_processor_log_ref": "",
        "level_strategy": "unavailable",
        "platform": platform,
        "manifest_ref": _repo_relative(_resolve_path(manifest)),
        "cases": [],
        "errors": errors,
        "warnings": warnings,
        "messages": detection["messages"],
        "evidence_refs": [
            {
                "id": "local-editor-smoke-integration-gate",
                "kind": "integration_check",
                "source": "detect_editor_smoke_environment",
            }
        ],
    }


def detect_editor_smoke_environment(env: Mapping[str, str] | None = None) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    engine_root = str(env.get("O3DE_ENGINE_ROOT", "")).strip()
    project_path = str(env.get("O3DE_PROJECT_PATH", "")).strip()
    executable = str(env.get("O3DE_EDITOR_EXECUTABLE", "")).strip() or _find_editor_on_path(env)
    messages: List[str] = []
    if not engine_root:
        messages.append("O3DE_ENGINE_ROOT is not set.")
    if not project_path:
        messages.append("O3DE_PROJECT_PATH is not set.")
    if not executable:
        messages.append("O3DE Editor executable was not found.")
    messages.append("Editor Python bindings are not probed by default; no live Editor command ran.")
    command_preview = [executable, "--project-path", project_path, "--runpython", _repo_relative(EDITOR_SCRIPT)] if executable and project_path else []
    return {
        "engine_root": engine_root,
        "project_path": project_path,
        "editor_executable": executable,
        "command_preview": command_preview,
        "messages": messages,
    }


def editor_smoke_gate_enabled(env: Mapping[str, str] | None = None) -> bool:
    env = env if env is not None else os.environ
    return str(env.get("MAXINE_ENABLE_O3DE_EDITOR_SMOKE", "")).strip() == "1" or str(
        env.get("MAXINE_ENABLE_O3DE_INTEGRATION", "")
    ).strip() == "1"


def _product_records(report: Mapping[str, Any]) -> List[ProductRecord]:
    source_uuid = str(report.get("source_uuid", "")).strip()
    products: List[ProductRecord] = []
    for product in report.get("produced_products", []) if isinstance(report.get("produced_products", []), list) else []:
        if isinstance(product, Mapping):
            payload = dict(product)
            payload.setdefault("source_uuid", source_uuid)
            payload.setdefault("evidence_source", str(report.get("mode", "fixture")))
            products.append(ProductRecord.from_mapping(payload))
    return products


def _uses_cache_heuristic(product: ProductRecord) -> bool:
    evidence_source = product.evidence_source.strip().lower()
    return evidence_source in {"cache_heuristic", "newest_cache_file", "best_looking_cache_file", "fallback_mesh_selection"} or (
        product.produced_by_source_uuid is False and evidence_source not in {"fixture", "local_editor_python", "local_o3de", "asset_system"}
    )


def _find_editor_on_path(env: Mapping[str, str]) -> str:
    for raw_entry in str(env.get("PATH", "")).split(os.pathsep):
        if not raw_entry.strip():
            continue
        directory = Path(raw_entry)
        for tool_name in EDITOR_TOOL_NAMES:
            candidate = directory / tool_name
            if candidate.exists() and candidate.is_file():
                return str(candidate)
    return ""


def _resolve_path(path: Path | str) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else REPO_ROOT / resolved


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _unique(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the MAXINE Editor Python package/prefab smoke fixture bridge.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Manifest path to use for report context.")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Editor smoke fixture corpus root.")
    parser.add_argument("--mode", choices=["fixture", "local_editor_python"], default="fixture")
    parser.add_argument("--platform", default="pc")
    parser.add_argument("--enable-editor-smoke", action="store_true", help="Opt into local Editor smoke integration detection.")
    parser.add_argument("--strict-integration", action="store_true", help="Fail if local Editor tooling is unavailable.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = _resolve_path(args.manifest)
    if not manifest.exists():
        print(f"Editor smoke fixture bridge: fail")
        print(f"  error: MXN_INPUT_MISSING")
        print(f"  - Manifest not found: {manifest}")
        return 2
    result = run_editor_smoke_corpus(
        args.corpus,
        mode=args.mode,
        manifest=manifest,
        enable_editor_smoke=args.enable_editor_smoke,
        strict_integration=args.strict_integration,
        platform=args.platform,
    )
    print(f"Editor smoke fixture bridge: {result['status']}")
    print(f"mode: {result['mode']}")
    print(f"live_editor_execution: {str(result['live_editor_execution']).lower()}")
    for code in result.get("errors", []):
        print(f"  error: {code}")
    for code in result.get("warnings", []):
        print(f"  warning: {code}")
    for message in result.get("messages", []):
        print(f"  - {message}")
    for case in result.get("cases", []):
        print(f"  {case['case_id']}: expected {case['expected_status']}, observed {case['observed_status']} -> {case['status']}")
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
