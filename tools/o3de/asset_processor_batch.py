#!/usr/bin/env python3
"""Fixture-backed and integration-gated Asset Processor Batch proof harness."""

from __future__ import annotations

import argparse
import json
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
SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine.asset-processor-batch-report.schema.json"
DEFAULT_CORPUS = REPO_ROOT / "examples" / "golden-corpus"
APB_TOOL_NAMES = ("AssetProcessorBatch.exe", "AssetProcessorBatch")


def load_corpus_reports(corpus: Path | str) -> List[Tuple[str, Dict[str, Any]]]:
    corpus_path = _resolve_path(corpus)
    reports: List[Tuple[str, Dict[str, Any]]] = []
    for path in sorted(corpus_path.glob("*/asset_processor_batch.fixture.json")):
        reports.append((path.parent.name, load_json(path)))
    return reports


def validate_asset_processor_batch_report(report: Mapping[str, Any], *, strict: bool = True) -> ValidationResult:
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
            publish_tier=str(report.get("publish_tier", "package")),
            physics_enabled=bool(report.get("physics_enabled", False)),
            materialized=bool(report.get("materialized", False)),
            collider_waiver=bool(report.get("collider_waiver", False)),
            material_waiver=bool(report.get("material_waiver", False)),
            external_motion_required=bool(report.get("motion_required", False)),
            cache_heuristic_used=cache_heuristic_used,
        )
    )

    pending_assets = report.get("pending_assets", [])
    if isinstance(pending_assets, list) and pending_assets:
        message = "Asset Processor Batch report includes pending assets."
        if strict:
            result.add_error("MXN_ASSET_PRODUCTS_PENDING", message)
        else:
            result.add_warning("MXN_ASSET_PRODUCTS_PENDING", message)

    expected = {str(product_type).strip() for product_type in report.get("expected_products", []) if str(product_type).strip()}
    present = {product.product_type for product in products if product.status == "ready"}
    for product_type in sorted(expected - present):
        if product_type in report.get("missing_products", []):
            result.add_error("MXN_ASSET_PRODUCT_MISSING", f"Asset Processor Batch proof is missing expected product: {product_type}")

    if lane in {"release_rigged", "external_rig_import"}:
        for product in products:
            if _uses_cache_heuristic(product):
                continue
            if product.status == "ready" and (not product.source_uuid or not product.produced_by_source_uuid):
                result.add_error(
                    "MXN_PROVENANCE_INCOMPLETE",
                    f"Release product {product.product_type} lacks source UUID product identity.",
                )

    if lane in {"release_rigged", "external_rig_import"} and cache_heuristic_used:
        if "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" not in result.error_codes:
            result.add_error(
                "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN",
                "Release Asset Processor Batch proof cannot rely on cache-heuristic products.",
            )
    result.details["cache_heuristic_used"] = cache_heuristic_used
    return result


def run_asset_processor_batch_corpus(
    corpus: Path | str = DEFAULT_CORPUS,
    *,
    mode: str = "fixture",
    enable_asset_processor_batch: bool = False,
    strict_integration: bool = False,
    platform: str = "pc",
    env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    if enable_asset_processor_batch or asset_processor_batch_gate_enabled(env) or mode == "local_asset_processor_batch":
        return _unavailable_integration_report(
            strict_integration=strict_integration,
            platform=platform,
            env=env,
        )
    return _fixture_corpus_report(_resolve_path(corpus), platform=platform)


def _fixture_corpus_report(corpus: Path, *, platform: str) -> Dict[str, Any]:
    schema = load_json(SCHEMA_PATH)
    cases: List[Dict[str, Any]] = []
    all_errors: List[str] = []
    all_warnings: List[str] = []
    for case_id, report in load_corpus_reports(corpus):
        schema_result = schema_validate(report, schema)
        validation = validate_asset_processor_batch_report(report, strict=True)
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
        "report_type": "asset_processor_batch_golden_corpus_summary_v1",
        "report_id": "asset-processor-batch-golden-corpus-summary",
        "mode": "fixture",
        "status": status,
        "integration_enabled": False,
        "strict_integration": False,
        "live_asset_processor_batch_execution": False,
        "platform": platform,
        "cases": cases,
        "errors": _unique(all_errors),
        "warnings": _unique(all_warnings),
        "evidence_refs": [
            {
                "id": "golden-corpus",
                "kind": "asset_processor_batch_fixture_corpus",
                "path": _repo_relative(corpus),
            }
        ],
    }


def _unavailable_integration_report(*, strict_integration: bool, platform: str, env: Mapping[str, str]) -> Dict[str, Any]:
    detection = detect_asset_processor_batch_environment(env)
    status = "fail" if strict_integration else "skipped"
    errors = [MXN_VALIDATION_TOOL_UNAVAILABLE] if strict_integration else []
    warnings = [] if strict_integration else [MXN_VALIDATION_TOOL_UNAVAILABLE]
    return {
        "schema_version": "1.0.0",
        "report_type": "asset_processor_batch_golden_corpus_summary_v1",
        "report_id": "asset-processor-batch-local-integration",
        "mode": "unavailable",
        "status": status,
        "integration_enabled": True,
        "strict_integration": strict_integration,
        "live_asset_processor_batch_execution": False,
        "o3de_engine_root_present": bool(detection["engine_root"]),
        "o3de_project_path_present": bool(detection["project_path"]),
        "asset_processor_batch_executable": detection["asset_processor_batch_executable"],
        "command_preview": detection["command_preview"],
        "exit_code": None,
        "stdout_log_ref": "",
        "stderr_log_ref": "",
        "asset_processor_log_ref": "",
        "platform": platform,
        "cases": [],
        "errors": errors,
        "warnings": warnings,
        "messages": detection["messages"],
        "evidence_refs": [
            {
                "id": "local-apb-integration-gate",
                "kind": "integration_check",
                "source": "detect_asset_processor_batch_environment",
            }
        ],
    }


def detect_asset_processor_batch_environment(env: Mapping[str, str] | None = None) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    engine_root = str(env.get("O3DE_ENGINE_ROOT", "")).strip()
    project_path = str(env.get("O3DE_PROJECT_PATH", "")).strip()
    executable = str(env.get("ASSET_PROCESSOR_BATCH", "")).strip() or _find_apb_on_path(env)
    messages: List[str] = []
    if not engine_root:
        messages.append("O3DE_ENGINE_ROOT is not set.")
    if not project_path:
        messages.append("O3DE_PROJECT_PATH is not set.")
    if not executable:
        messages.append("AssetProcessorBatch executable was not found.")
    if executable and engine_root and project_path:
        messages.append("AssetProcessorBatch tooling was detected, but this proof slice does not execute it automatically.")
    command_preview = [executable, "--project-path", project_path, "--platform", "pc"] if executable and project_path else []
    return {
        "engine_root": engine_root,
        "project_path": project_path,
        "asset_processor_batch_executable": executable,
        "command_preview": command_preview,
        "messages": messages,
    }


def _product_records(report: Mapping[str, Any]) -> List[ProductRecord]:
    source_uuid = ""
    source_assets = report.get("source_assets", [])
    if isinstance(source_assets, list) and source_assets and isinstance(source_assets[0], Mapping):
        source_uuid = str(source_assets[0].get("source_uuid", "")).strip()
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
        product.produced_by_source_uuid is False and evidence_source not in {"fixture", "local_asset_processor_batch", "local_o3de", "asset_system"}
    )


def asset_processor_batch_gate_enabled(env: Mapping[str, str]) -> bool:
    return str(env.get("MAXINE_ENABLE_ASSET_PROCESSOR_BATCH", "")).strip() == "1" or str(
        env.get("MAXINE_ENABLE_O3DE_INTEGRATION", "")
    ).strip() == "1"


def _find_apb_on_path(env: Mapping[str, str]) -> str:
    for raw_entry in str(env.get("PATH", "")).split(os.pathsep):
        if not raw_entry.strip():
            continue
        directory = Path(raw_entry)
        for tool_name in APB_TOOL_NAMES:
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
    parser = argparse.ArgumentParser(description="Validate the MAXINE Asset Processor Batch golden corpus proof.")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Golden corpus root.")
    parser.add_argument("--mode", choices=["fixture", "local_asset_processor_batch"], default="fixture")
    parser.add_argument("--platform", default="pc")
    parser.add_argument("--enable-asset-processor-batch", action="store_true", help="Opt into local APB integration detection.")
    parser.add_argument("--strict-integration", action="store_true", help="Fail if local APB tooling is unavailable.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_asset_processor_batch_corpus(
        args.corpus,
        mode=args.mode,
        enable_asset_processor_batch=args.enable_asset_processor_batch,
        strict_integration=args.strict_integration,
        platform=args.platform,
    )
    print(f"Asset Processor Batch golden corpus: {result['status']}")
    print(f"mode: {result['mode']}")
    print(f"live_asset_processor_batch_execution: {str(result['live_asset_processor_batch_execution']).lower()}")
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
