#!/usr/bin/env python3
"""Fixture-backed and integration-gated Asset Processor Batch proof harness."""

from __future__ import annotations

import argparse
import json
import os
import platform as platform_module
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.o3de.product_matrix_resolver import validate_expected_products
from tools.o3de.product_resolver import ProductRecord
from tools.o3de.golden_project_fixture import DEFAULT_FIXTURE as DEFAULT_GOLDEN_PROJECT_FIXTURE
from tools.o3de.golden_project_fixture import run_golden_project_fixture
from tools.validation.results import ValidationResult
from tools.validation.schema_utils import load_json, schema_validate


MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"
MXN_PATH_UNSAFE = "MXN_PATH_UNSAFE"
SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine.asset-processor-batch-report.schema.json"
DEFAULT_CORPUS = REPO_ROOT / "examples" / "golden-corpus"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "o3de-integration" / "apb"
APB_TOOL_NAMES = ("AssetProcessorBatch.exe", "AssetProcessorBatch")
LIVE_GATE_ENV_VARS = (
    "MAXINE_ENABLE_O3DE_INTEGRATION",
    "MAXINE_ENABLE_ASSET_PROCESSOR_BATCH",
    "MAXINE_ALLOW_LIVE_O3DE_COMMANDS",
)


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
    check_local_readiness: bool = False,
    golden_project_fixture: Path | str = DEFAULT_GOLDEN_PROJECT_FIXTURE,
    platform: str = "pc",
    env: Mapping[str, str] | None = None,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    integration_requested = (
        check_local_readiness
        or enable_asset_processor_batch
        or asset_processor_batch_gate_enabled(env)
        or mode == "local_asset_processor_batch"
    )
    live_requested = enable_asset_processor_batch or mode == "local_asset_processor_batch"
    if integration_requested:
        return _integration_or_live_report(
            _resolve_path(corpus),
            strict_integration=strict_integration,
            check_local_readiness=check_local_readiness,
            live_requested=live_requested,
            golden_project_fixture=_resolve_path(golden_project_fixture),
            platform=platform,
            env=env,
            command_runner=command_runner or subprocess.run,
            artifact_root=_resolve_path(artifact_root),
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


def _integration_or_live_report(
    corpus: Path,
    *,
    strict_integration: bool,
    check_local_readiness: bool,
    live_requested: bool,
    golden_project_fixture: Path,
    platform: str,
    env: Mapping[str, str],
    command_runner: Callable[..., subprocess.CompletedProcess[str]],
    artifact_root: Path,
) -> Dict[str, Any]:
    fixture_report = run_golden_project_fixture(golden_project_fixture)
    if fixture_report["status"] == "fail":
        return _invalid_integration_report(
            platform=platform,
            golden_project_fixture=golden_project_fixture,
            errors=list(fixture_report.get("errors", [])),
            warnings=list(fixture_report.get("warnings", [])),
            messages=list(fixture_report.get("messages", [])),
        )

    detection = detect_asset_processor_batch_environment(env, golden_project_fixture=golden_project_fixture)
    if detection.get("project_identity_error"):
        return _invalid_integration_report(
            platform=platform,
            golden_project_fixture=golden_project_fixture,
            errors=[MXN_PATH_UNSAFE],
            warnings=[],
            messages=[str(detection["project_identity_error"])],
        )
    missing = _missing_live_prerequisites(env, detection, live_requested=live_requested or check_local_readiness)
    if check_local_readiness and not missing:
        return _local_readiness_report(
            strict_integration=strict_integration,
            platform=platform,
            detection=detection,
            golden_project_fixture=golden_project_fixture,
        )
    if check_local_readiness or missing:
        return _unavailable_integration_report(
            strict_integration=strict_integration,
            platform=platform,
            env=env,
            detection=detection,
            golden_project_fixture=golden_project_fixture,
            missing=missing,
        )
    return _execute_live_apb(
        corpus=corpus,
        detection=detection,
        strict_integration=strict_integration,
        golden_project_fixture=golden_project_fixture,
        platform=platform,
        env=env,
        command_runner=command_runner,
        artifact_root=artifact_root,
    )


def _local_readiness_report(
    *,
    strict_integration: bool,
    platform: str,
    detection: Mapping[str, Any],
    golden_project_fixture: Path,
) -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "report_type": "asset_processor_batch_golden_corpus_summary_v1",
        "report_id": "asset-processor-batch-local-readiness",
        "mode": "local_asset_processor_batch",
        "status": "pass",
        "integration_enabled": True,
        "integration_executed": False,
        "strict_integration": strict_integration,
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "live_publication": False,
        "o3de_engine_root_present": bool(detection["engine_root"]),
        "o3de_project_path_present": bool(detection["project_path"]),
        "asset_processor_batch_executable": detection["asset_processor_batch_executable"],
        "command_preview": detection["command_preview"],
        "exit_code": None,
        "stdout_log_ref": "",
        "stderr_log_ref": "",
        "asset_processor_log_ref": "",
        "golden_project_fixture_ref": _repo_relative(golden_project_fixture),
        "runner_context": _runner_context(),
        "command": {
            "argv": detection["command_preview"],
            "working_directory": detection["project_path"],
            "exit_code": None,
        },
        "logs": {
            "stdout_log_ref": "",
            "stderr_log_ref": "",
            "asset_processor_log_ref": "",
        },
        "safety": _apb_safety_payload(),
        "platform": platform,
        "cases": [],
        "errors": [],
        "warnings": [],
        "messages": list(detection["messages"]),
        "evidence_refs": [
            {
                "id": "local-apb-readiness",
                "kind": "local_readiness",
                "source": "detect_asset_processor_batch_environment",
            },
            {
                "id": "golden-project-fixture",
                "kind": "o3de_golden_project_fixture",
                "path": _repo_relative(golden_project_fixture),
            },
        ],
    }


def _unavailable_integration_report(
    *,
    strict_integration: bool,
    platform: str,
    env: Mapping[str, str],
    detection: Mapping[str, Any] | None = None,
    golden_project_fixture: Path = DEFAULT_GOLDEN_PROJECT_FIXTURE,
    missing: List[str] | None = None,
) -> Dict[str, Any]:
    detection = detection or detect_asset_processor_batch_environment(env, golden_project_fixture=golden_project_fixture)
    missing = missing if missing is not None else _missing_live_prerequisites(env, detection, live_requested=True)
    status = "fail" if strict_integration else "skipped"
    errors = [MXN_VALIDATION_TOOL_UNAVAILABLE] if strict_integration else []
    warnings = [] if strict_integration else [MXN_VALIDATION_TOOL_UNAVAILABLE]
    messages = list(detection["messages"])
    if missing:
        messages.insert(0, "Live Asset Processor Batch prerequisites are unavailable: " + ", ".join(missing) + ".")
    return {
        "schema_version": "1.0.0",
        "report_type": "asset_processor_batch_golden_corpus_summary_v1",
        "report_id": "asset-processor-batch-local-integration",
        "mode": "unavailable",
        "status": status,
        "integration_enabled": True,
        "integration_executed": False,
        "strict_integration": strict_integration,
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "live_publication": False,
        "o3de_engine_root_present": bool(detection["engine_root"]),
        "o3de_project_path_present": bool(detection["project_path"]),
        "asset_processor_batch_executable": detection["asset_processor_batch_executable"],
        "command_preview": detection["command_preview"],
        "exit_code": None,
        "stdout_log_ref": "",
        "stderr_log_ref": "",
        "asset_processor_log_ref": "",
        "golden_project_fixture_ref": _repo_relative(golden_project_fixture),
        "runner_context": _runner_context(),
        "command": {
            "argv": detection["command_preview"],
            "working_directory": detection["project_path"],
            "exit_code": None,
        },
        "logs": {
            "stdout_log_ref": "",
            "stderr_log_ref": "",
            "asset_processor_log_ref": "",
        },
        "safety": _apb_safety_payload(),
        "platform": platform,
        "cases": [],
        "errors": errors,
        "warnings": warnings,
        "messages": messages,
        "evidence_refs": [
            {
                "id": "local-apb-integration-gate",
                "kind": "integration_check",
                "source": "detect_asset_processor_batch_environment",
            },
            {
                "id": "golden-project-fixture",
                "kind": "o3de_golden_project_fixture",
                "path": _repo_relative(golden_project_fixture),
            }
        ],
    }


def _invalid_integration_report(
    *,
    platform: str,
    golden_project_fixture: Path,
    errors: List[str],
    warnings: List[str],
    messages: List[str],
) -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "report_type": "asset_processor_batch_golden_corpus_summary_v1",
        "report_id": "asset-processor-batch-invalid-integration",
        "mode": "invalid",
        "status": "fail",
        "integration_enabled": True,
        "integration_executed": False,
        "strict_integration": True,
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "live_publication": False,
        "golden_project_fixture_ref": _repo_relative(golden_project_fixture),
        "platform": platform,
        "cases": [],
        "errors": _unique(errors),
        "warnings": _unique(warnings),
        "messages": messages,
        "safety": _apb_safety_payload(),
        "evidence_refs": [
            {
                "id": "golden-project-fixture",
                "kind": "o3de_golden_project_fixture",
                "path": _repo_relative(golden_project_fixture),
            }
        ],
    }


def _execute_live_apb(
    *,
    corpus: Path,
    detection: Mapping[str, Any],
    strict_integration: bool,
    golden_project_fixture: Path,
    platform: str,
    env: Mapping[str, str],
    command_runner: Callable[..., subprocess.CompletedProcess[str]],
    artifact_root: Path,
) -> Dict[str, Any]:
    started_at = _utc_now()
    start_time = time.monotonic()
    run_id = "apb-live-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = artifact_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    report_path = output_dir / "asset_processor_batch_live_report.json"
    argv = list(detection["command_preview"])
    proc = command_runner(
        argv,
        cwd=str(detection["project_path"]),
        text=True,
        capture_output=True,
        env=dict(env),
    )
    finished_at = _utc_now()
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")
    duration_seconds = round(time.monotonic() - start_time, 3)
    status = "pass" if proc.returncode == 0 else "fail"
    errors = [] if proc.returncode == 0 else ["MXN_VALIDATION_TOOL_UNAVAILABLE"]
    messages = [] if proc.returncode == 0 else [f"Asset Processor Batch exited with code {proc.returncode}."]
    report = {
        "schema_version": "1.0.0",
        "report_type": "asset_processor_batch_golden_corpus_summary_v1",
        "report_id": run_id,
        "mode": "local_asset_processor_batch",
        "status": status,
        "integration_enabled": True,
        "integration_executed": True,
        "strict_integration": strict_integration,
        "live_asset_processor_batch_execution": True,
        "live_editor_execution": False,
        "live_publication": False,
        "runner_context": _runner_context(),
        "golden_project_fixture_ref": _repo_relative(golden_project_fixture),
        "command": {
            "argv": _redacted_argv(argv),
            "working_directory": detection["project_path"],
            "exit_code": proc.returncode,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
        },
        "command_preview": _redacted_argv(argv),
        "exit_code": proc.returncode,
        "stdout_log_ref": _repo_relative(stdout_path),
        "stderr_log_ref": _repo_relative(stderr_path),
        "asset_processor_log_ref": "",
        "apb_report_ref": _repo_relative(report_path),
        "logs": {
            "stdout_log_ref": _repo_relative(stdout_path),
            "stderr_log_ref": _repo_relative(stderr_path),
            "asset_processor_log_ref": "",
        },
        "platform": platform,
        "source_assets": [],
        "expected_products": _expected_products_from_corpus(corpus),
        "produced_products": [],
        "pending_assets": [],
        "missing_products": [],
        "cache_heuristic_used": False,
        "cases": [],
        "errors": errors,
        "warnings": [],
        "messages": messages,
        "safety": _apb_safety_payload(),
        "evidence_refs": [
            {
                "id": "golden-project-fixture",
                "kind": "o3de_golden_project_fixture",
                "path": _repo_relative(golden_project_fixture),
            },
            {
                "id": "apb-live-report",
                "kind": "asset_processor_batch_live_report",
                "path": _repo_relative(report_path),
            },
        ],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def detect_asset_processor_batch_environment(
    env: Mapping[str, str] | None = None,
    *,
    golden_project_fixture: Path | str | None = None,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    engine_root = str(env.get("O3DE_ENGINE_ROOT", "")).strip()
    project_path = str(env.get("O3DE_PROJECT_PATH", "")).strip()
    executable = (
        str(env.get("ASSET_PROCESSOR_BATCH_EXECUTABLE", "")).strip()
        or str(env.get("ASSET_PROCESSOR_BATCH", "")).strip()
        or _find_apb_on_path(env)
    )
    engine_root_exists = bool(engine_root) and Path(engine_root).exists()
    project_path_exists = bool(project_path) and Path(project_path).exists()
    executable_exists = bool(executable) and Path(executable).exists()
    executable_name_valid = _is_asset_processor_batch_executable(executable)
    executable_available = executable_exists and executable_name_valid
    expected_project_name = _expected_project_name(golden_project_fixture)
    project_name = _read_project_name(project_path) if project_path_exists else ""
    project_identity_error = ""
    messages: List[str] = []
    if not engine_root_exists:
        messages.append("O3DE_ENGINE_ROOT is not set or does not exist.")
    if not project_path_exists:
        messages.append("O3DE_PROJECT_PATH is not set or does not exist.")
    if not executable_exists:
        messages.append("AssetProcessorBatch executable was not found or does not exist.")
    elif not executable_name_valid:
        messages.append("ASSET_PROCESSOR_BATCH_EXECUTABLE must point to AssetProcessorBatch.exe, not another O3DE tool.")
    if project_path_exists and expected_project_name:
        if not project_name:
            project_identity_error = "O3DE_PROJECT_PATH does not contain a readable project.json project_name."
        elif project_name != expected_project_name:
            project_identity_error = (
                f"O3DE_PROJECT_PATH project_name '{project_name}' does not match golden fixture project_name "
                f"'{expected_project_name}'."
            )
        if project_identity_error:
            messages.append(project_identity_error)
    if executable_available and engine_root_exists and project_path_exists:
        messages.append("AssetProcessorBatch tooling was detected; live execution still requires every explicit APB gate.")
    command_preview = [executable, "--project-path", project_path, "--platform", "pc"] if executable and project_path else []
    return {
        "engine_root": engine_root,
        "engine_root_exists": engine_root_exists,
        "project_path": project_path,
        "project_path_exists": project_path_exists,
        "project_name": project_name,
        "project_name_expected": expected_project_name,
        "project_identity_error": project_identity_error,
        "asset_processor_batch_executable": executable,
        "asset_processor_batch_executable_exists": executable_exists,
        "asset_processor_batch_executable_name_valid": executable_name_valid,
        "asset_processor_batch_executable_available": executable_available,
        "command_preview": command_preview,
        "messages": messages,
    }


def _missing_live_prerequisites(env: Mapping[str, str], detection: Mapping[str, Any], *, live_requested: bool) -> List[str]:
    missing: List[str] = []
    if not live_requested:
        missing.append("--enable-asset-processor-batch")
    for key in LIVE_GATE_ENV_VARS:
        if str(env.get(key, "")).strip() != "1":
            missing.append(key)
    if not detection.get("engine_root_exists"):
        missing.append("O3DE_ENGINE_ROOT")
    if not detection.get("project_path_exists"):
        missing.append("O3DE_PROJECT_PATH")
    if not detection.get("asset_processor_batch_executable_available"):
        missing.append("ASSET_PROCESSOR_BATCH_EXECUTABLE")
    return _unique(missing)


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


def _expected_products_from_corpus(corpus: Path) -> List[str]:
    expected: List[str] = []
    for _, report in load_corpus_reports(corpus):
        for product_type in report.get("expected_products", []) if isinstance(report.get("expected_products", []), list) else []:
            product_type = str(product_type).strip()
            if product_type and product_type not in expected:
                expected.append(product_type)
    return expected


def _uses_cache_heuristic(product: ProductRecord) -> bool:
    evidence_source = product.evidence_source.strip().lower()
    return evidence_source in {"cache_heuristic", "newest_cache_file", "best_looking_cache_file", "fallback_mesh_selection"} or (
        product.produced_by_source_uuid is False and evidence_source not in {"fixture", "local_asset_processor_batch", "local_o3de", "asset_system"}
    )


def asset_processor_batch_gate_enabled(env: Mapping[str, str]) -> bool:
    return str(env.get("MAXINE_ENABLE_ASSET_PROCESSOR_BATCH", "")).strip() == "1" or str(
        env.get("MAXINE_ENABLE_O3DE_INTEGRATION", "")
    ).strip() == "1"


def _runner_context() -> Dict[str, Any]:
    runner_labels = [label.strip() for label in str(os.environ.get("RUNNER_LABELS", "")).split(",") if label.strip()]
    return {
        "os": platform_module.platform(),
        "runner_name": os.environ.get("RUNNER_NAME", ""),
        "self_hosted_expected": True,
        "private_runner_labels": runner_labels,
    }


def _apb_safety_payload() -> Dict[str, Any]:
    return {
        "live_editor_execution": False,
        "live_publication": False,
        "project_mutation_policy": "AssetProcessorBatch-only cache/product processing for the validated golden project; no Editor, publication, or production-level mutation.",
        "cleanup_policy": "No cache deletion or source-asset deletion; generated command logs stay under artifacts/o3de-integration/apb.",
    }


def _expected_project_name(golden_project_fixture: Path | str | None) -> str:
    if not golden_project_fixture:
        return ""
    path = _resolve_path(golden_project_fixture)
    if not path.exists():
        return ""
    try:
        payload = load_json(path)
    except Exception:
        return ""
    project = payload.get("project", {})
    return str(project.get("project_name", "")).strip() if isinstance(project, Mapping) else ""


def _read_project_name(project_path: str) -> str:
    if not project_path:
        return ""
    project_json = Path(project_path) / "project.json"
    if not project_json.exists():
        return ""
    try:
        payload = json.loads(project_json.read_text(encoding="utf-8-sig"))
    except Exception:
        return ""
    return str(payload.get("project_name", "")).strip() if isinstance(payload, Mapping) else ""


def _redacted_argv(argv: Sequence[str]) -> List[str]:
    redacted: List[str] = []
    for value in argv:
        text = str(value)
        if any(marker in text.lower() for marker in ("token=", "password=", "secret=", "key=")):
            redacted.append("<redacted>")
        else:
            redacted.append(text)
    return redacted


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _is_asset_processor_batch_executable(executable: str) -> bool:
    if not executable:
        return False
    return Path(executable).name.lower() in {name.lower() for name in APB_TOOL_NAMES}


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
    parser.add_argument("--check-local-readiness", action="store_true", help="Check APB project/tool readiness without executing APB.")
    parser.add_argument("--golden-project-fixture", default=str(DEFAULT_GOLDEN_PROJECT_FIXTURE), help="Golden project fixture contract path.")
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
        check_local_readiness=args.check_local_readiness,
        golden_project_fixture=args.golden_project_fixture,
        platform=args.platform,
    )
    print(f"Asset Processor Batch golden corpus: {result['status']}")
    print(f"mode: {result['mode']}")
    print(f"live_asset_processor_batch_execution: {str(result['live_asset_processor_batch_execution']).lower()}")
    if "live_editor_execution" in result:
        print(f"live_editor_execution: {str(result['live_editor_execution']).lower()}")
    if "live_publication" in result:
        print(f"live_publication: {str(result['live_publication']).lower()}")
    if result.get("golden_project_fixture_ref"):
        print(f"golden_project_fixture_ref: {result['golden_project_fixture_ref']}")
    if result.get("apb_report_ref"):
        print(f"apb_report_ref: {result['apb_report_ref']}")
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
