#!/usr/bin/env python3
"""Fixture-backed and integration-gated O3DE Editor Python smoke bridge."""

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
from tools.o3de import runtime_harness as runtime_harness_tool
from tools.validation.results import ValidationResult
from tools.validation.schema_utils import load_json, schema_validate


MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"
MXN_PATH_UNSAFE = "MXN_PATH_UNSAFE"
MXN_EDITOR_SMOKE_STALLED = "MXN_EDITOR_SMOKE_STALLED"
MXN_EDITOR_PROCESS_EXIT_NONZERO = "MXN_EDITOR_PROCESS_EXIT_NONZERO"
MXN_RUNTIME_SMOKE_FAIL = "MXN_RUNTIME_SMOKE_FAIL"
SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine.editor-smoke-report.schema.json"
DEFAULT_CORPUS = REPO_ROOT / "examples" / "editor-smoke"
DEFAULT_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"
DEFAULT_GOLDEN_PROJECT_FIXTURE = REPO_ROOT / "examples" / "o3de-golden-project" / "maxine-golden-project.fixture.json"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "o3de-integration" / "editor-smoke"
DEFAULT_APB_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "o3de-integration" / "apb"
DEFAULT_EDITOR_TIMEOUT_SECONDS = 900
EDITOR_TOOL_NAMES = ("Editor.exe", "O3DEEditor.exe", "Editor", "O3DEEditor")
EDITOR_SCRIPT = REPO_ROOT / "tools" / "o3de" / "editor_python" / "maxine_package_prefab_smoke.py"
DIAGNOSTIC_EDITOR_SCRIPTS = {
    "hello": REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_hello_smoke.py",
    "product-evidence": REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_product_evidence_smoke.py",
    "temp-level": REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_temp_level_smoke.py",
    "entity-minimal": REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_entity_minimal_smoke.py",
    "component-binding": REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_component_binding_smoke.py",
    "actor-binding": REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_actor_binding_smoke.py",
    "actor-asset-assignment": REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_actor_asset_assignment_smoke.py",
    "prefab-binding": REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_prefab_binding_smoke.py",
    "prefab-instantiation": REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_prefab_instantiation_smoke.py",
    "procprefab-product-instantiation": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_procprefab_product_instantiation_smoke.py",
    "procprefab-content-assertions": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_procprefab_content_assertions_smoke.py",
    "procprefab-character-component-assertions": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_procprefab_character_component_assertions_smoke.py",
    "runtime-spawnable-proof-surface": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_runtime_spawnable_proof_surface_smoke.py",
    "full": EDITOR_SCRIPT,
}
DIAGNOSTIC_MODES = tuple(DIAGNOSTIC_EDITOR_SCRIPTS)
DIRECT_PROCPREFAB_TYPED_NONVERIFIED_STATUSES = {
    "procprefab_product_not_editor_instantiable_with_current_binding",
    "procprefab_product_requires_runtime_spawnable_path",
    "blocked_by_unpinned_signature",
    "blocked_by_unsafe_argument_semantics",
    "blocked_by_unsupported_product_asset_type",
    "blocked_by_editor_binding_limitation",
    "blocked_by_missing_binding",
    "unsupported_by_engine_binding",
}
LIVE_EDITOR_GATE_ENV_VARS = (
    "MAXINE_ENABLE_O3DE_INTEGRATION",
    "MAXINE_ENABLE_O3DE_EDITOR_SMOKE",
    "MAXINE_ALLOW_LIVE_O3DE_COMMANDS",
    "MAXINE_ALLOW_LIVE_EDITOR_COMMANDS",
)


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
    if str(report.get("mode", "")) == "local_editor_python":
        if str(report.get("status", "")) == "pass" and report.get("live_editor_execution") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Local Editor Python smoke cannot pass unless live_editor_execution is true.",
            )
        if str(report.get("status", "")) == "pass" and report.get("no_fake_success") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Local Editor Python smoke pass must explicitly preserve no_fake_success=true.",
            )
        if report.get("live_publication") is True:
            result.add_error(MXN_PATH_UNSAFE, "Editor smoke must not enable live publication.")
        if report.get("release_packaging") is True:
            result.add_error(MXN_PATH_UNSAFE, "Editor smoke must not enable release packaging.")
        if report.get("production_level_mutation") is True:
            result.add_error(MXN_PATH_UNSAFE, "Editor smoke must not mutate production levels.")
        temp_path = str(report.get("temp_level_path_redacted", "")).replace("\\", "/")
        if temp_path and not temp_path.startswith("Levels/_maxine_smoke/"):
            result.add_error(MXN_PATH_UNSAFE, "Editor smoke temp level path must stay under Levels/_maxine_smoke.")
        diagnostic_mode = str(report.get("diagnostic_mode", "")).strip()
        targeted_binding_fields = {
            "component-binding": "component_binding_checks",
            "actor-binding": "actor_binding_checks",
            "actor-asset-assignment": "actor_binding_checks",
            "prefab-binding": "prefab_binding_checks",
            "prefab-instantiation": "prefab_binding_checks",
            "procprefab-product-instantiation": "prefab_binding_checks",
            "procprefab-content-assertions": "prefab_binding_checks",
            "procprefab-character-component-assertions": "prefab_binding_checks",
            "runtime-spawnable-proof-surface": "prefab_binding_checks",
        }
        target_field = targeted_binding_fields.get(diagnostic_mode)
        if str(report.get("status", "")) == "pass" and target_field:
            target_checks = report.get(target_field, {})
            target_status = str(target_checks.get("status", "")).strip() if isinstance(target_checks, Mapping) else ""
            if target_status != "pass":
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"{diagnostic_mode} cannot report pass unless {target_field} reports pass.",
                )
        if str(report.get("status", "")) == "pass" and diagnostic_mode in {"actor-asset-assignment", "full"}:
            actor_checks = report.get("actor_binding_checks", {})
            assignment = actor_checks.get("actor_asset_assignment", {}) if isinstance(actor_checks, Mapping) else {}
            readback = assignment.get("readback", {}) if isinstance(assignment, Mapping) else {}
            if (
                not isinstance(assignment, Mapping)
                or assignment.get("status") != "pass"
                or not isinstance(readback, Mapping)
                or readback.get("status") != "pass"
                or readback.get("matched_approved_product") is not True
            ):
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    "Actor asset assignment cannot report pass without verified approved-product readback.",
                )
        if str(report.get("status", "")) == "pass" and diagnostic_mode in {"prefab-instantiation", "full"}:
            prefab_checks = report.get("prefab_binding_checks", {})
            instantiation = prefab_checks.get("instantiation", {}) if isinstance(prefab_checks, Mapping) else {}
            template_load = prefab_checks.get("template_load", {}) if isinstance(prefab_checks, Mapping) else {}
            instantiation_pass = (
                isinstance(instantiation, Mapping)
                and instantiation.get("status") == "pass"
                and int(instantiation.get("created_entity_count", 0) or 0) > 0
            )
            template_load_pass = (
                isinstance(template_load, Mapping)
                and template_load.get("status") == "template_load_pass"
                and str(template_load.get("template_id", "")).strip()
            )
            if not instantiation_pass and not template_load_pass:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    "Prefab instantiation cannot report pass without created-instance or verified template-load evidence.",
                )
        if str(report.get("status", "")) == "pass" and diagnostic_mode in {
            "procprefab-product-instantiation",
            "procprefab-content-assertions",
            "procprefab-character-component-assertions",
            "runtime-spawnable-proof-surface",
            "full",
        }:
            _validate_direct_procprefab_product_semantics(report, result)
            if diagnostic_mode in {"runtime-spawnable-proof-surface", "full"}:
                _validate_runtime_spawnable_proof_surface(report, result)
            if diagnostic_mode == "full" and isinstance(report.get("runtime_harness"), Mapping):
                result.merge(runtime_harness_tool.validate_runtime_harness_report(report["runtime_harness"], strict=strict))
        for smoke_field, check_field in (
            ("actor_smoke", "actor_binding_checks"),
            ("prefab_smoke", "prefab_binding_checks"),
        ):
            smoke = report.get(smoke_field, {})
            checks = report.get(check_field, {})
            smoke_status = str(smoke.get("status", "")).strip() if isinstance(smoke, Mapping) else ""
            check_status = str(checks.get("status", "")).strip() if isinstance(checks, Mapping) else ""
            if smoke_status == "pass" and check_status != "pass":
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"{smoke_field} cannot report pass without matching {check_field} pass evidence.",
                )
            if smoke_status == "unavailable" and "not attempted until" in str(smoke.get("reason", "")).lower():
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"{smoke_field} must report a typed binding status instead of generic unavailable-by-design.",
                )

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


def _validate_direct_procprefab_product_semantics(report: Mapping[str, Any], result: ValidationResult) -> None:
    prefab_checks = report.get("prefab_binding_checks", {})
    semantics = report.get("direct_procprefab_product_semantics")
    if not isinstance(semantics, Mapping) and isinstance(prefab_checks, Mapping):
        semantics = prefab_checks.get("direct_procprefab_product_semantics")
    if not isinstance(semantics, Mapping):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab diagnostics cannot pass without direct_procprefab_product_semantics evidence.",
        )
        return

    product_evidence = semantics.get("procprefab_product_evidence", {})
    if not isinstance(product_evidence, Mapping) or product_evidence.get("status") != "pass":
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab diagnostics require APB-backed procprefab product evidence.",
        )

    source_baseline = semantics.get("source_prefab_baseline_result")
    if not isinstance(source_baseline, Mapping):
        source_baseline = report.get("source_prefab_baseline_result")
    if not isinstance(source_baseline, Mapping) and isinstance(prefab_checks, Mapping):
        source_baseline = prefab_checks.get("source_prefab_baseline_result")
    if not isinstance(source_baseline, Mapping) or source_baseline.get("status") != "pass":
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab diagnostics must preserve the proven source-prefab baseline pass.",
        )

    claimed = semantics.get("direct_product_instantiation_claimed") is True
    verified = semantics.get("direct_product_instantiation_verified") is True
    supported = semantics.get("direct_product_instantiation_supported") is True
    direct_instantiation = semantics.get("procprefab_direct_product_instantiation_result", {})
    if claimed and not verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab instantiation cannot be claimed without direct_product_instantiation_verified=true.",
        )
    if verified and (not claimed or not supported):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Verified direct procprefab instantiation must also be explicitly claimed and supported.",
        )
    if verified:
        created_count = 0
        if isinstance(direct_instantiation, Mapping):
            try:
                created_count = int(direct_instantiation.get("created_entity_count", 0) or 0)
            except (TypeError, ValueError):
                created_count = 0
        if (
            not isinstance(direct_instantiation, Mapping)
            or direct_instantiation.get("status") != "pass"
            or created_count <= 0
            or not str(semantics.get("procprefab_selected_call", "")).strip()
        ):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Verified direct procprefab instantiation requires selected-call and created-entity evidence.",
            )
        _validate_direct_procprefab_content_assertions(report, semantics, prefab_checks, result)
        _validate_procprefab_character_assertions(report, semantics, prefab_checks, result)
    else:
        direct_status = ""
        if isinstance(direct_instantiation, Mapping):
            direct_status = str(direct_instantiation.get("status", "")).strip()
        semantic_status = str(semantics.get("status", "")).strip()
        observed_status = direct_status or semantic_status
        reason = str(
            semantics.get("unsupported_reason")
            or semantics.get("blocked_reason")
            or (direct_instantiation.get("reason", "") if isinstance(direct_instantiation, Mapping) else "")
        ).strip()
        if observed_status not in DIRECT_PROCPREFAB_TYPED_NONVERIFIED_STATUSES or not reason:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Unverified direct procprefab product behavior must report a precise typed unsupported or blocked reason.",
            )


def _validate_procprefab_character_assertions(
    report: Mapping[str, Any],
    semantics: Mapping[str, Any],
    prefab_checks: Any,
    result: ValidationResult,
) -> None:
    character = semantics.get("procprefab_character_assertions")
    if not isinstance(character, Mapping):
        character = report.get("procprefab_character_assertions")
    if not isinstance(character, Mapping) and isinstance(prefab_checks, Mapping):
        character = prefab_checks.get("procprefab_character_assertions")
    if not isinstance(character, Mapping):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Verified direct procprefab instantiation cannot pass without procprefab_character_assertions evidence.",
        )
        return

    status = str(character.get("status", "")).strip()
    assertion_status = str(character.get("character_assertion_status", "")).strip()
    required_status = str(character.get("required_character_assertions_status", "")).strip()
    required_failures = character.get("required_character_assertions_failed", [])
    assertion_failures = character.get("character_assertion_failures", [])
    allowed_statuses = {"pass", "informational_only", "unavailable_with_verified_reason"}
    if status not in allowed_statuses or assertion_status not in allowed_statuses:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Character-specific procprefab assertions require a typed pass/informational/unavailable status.",
        )
    if (
        required_status != "pass"
        or (isinstance(required_failures, list) and required_failures)
        or (isinstance(assertion_failures, list) and assertion_failures)
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Character-specific procprefab assertions cannot pass with failed required assertions.",
        )

    inventory_status = str(character.get("character_component_inventory_status", "")).strip()
    if inventory_status not in {"pass", "informational_only", "unavailable_with_verified_reason"}:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Character-specific procprefab assertions require component inventory with a typed status.",
        )

    required_passed = character.get("required_character_assertions_passed", [])
    if isinstance(required_passed, list) and "Transform" in required_passed:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Transform-only evidence cannot be counted as a character-specific required assertion pass.",
        )

    for field, label in (
        ("editor_log_character_error_scan", "character log error"),
        ("editor_log_missing_actor_signal", "missing actor"),
        ("editor_log_missing_mesh_signal", "missing mesh"),
        ("editor_log_missing_material_signal", "missing material"),
        ("editor_log_missing_animation_signal", "missing animation"),
    ):
        scan = character.get(field, {})
        scan_status = str(scan.get("status", "")).strip() if isinstance(scan, Mapping) else ""
        if scan_status != "pass":
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"Character-specific procprefab assertions require {label} scan status=pass.",
            )


def _validate_runtime_spawnable_proof_surface(report: Mapping[str, Any], result: ValidationResult) -> None:
    prefab_checks = report.get("prefab_binding_checks", {})
    semantics = report.get("direct_procprefab_product_semantics")
    if not isinstance(semantics, Mapping) and isinstance(prefab_checks, Mapping):
        semantics = prefab_checks.get("direct_procprefab_product_semantics")

    proof = report.get("runtime_spawnable_proof")
    if not isinstance(proof, Mapping) and isinstance(semantics, Mapping):
        proof = semantics.get("runtime_spawnable_proof")
    if not isinstance(proof, Mapping) and isinstance(prefab_checks, Mapping):
        proof = prefab_checks.get("runtime_spawnable_proof")
    if not isinstance(proof, Mapping):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime/spawnable proof surface diagnostics require runtime_spawnable_proof evidence.",
        )
        return

    if proof.get("fake_success") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime/spawnable proof surface cannot set fake_success=true.")
    if proof.get("cache_heuristic_used") is True:
        result.add_error(
            "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN",
            "Runtime/spawnable proof surface cannot use cache heuristic release proof.",
        )
    if proof.get("live_publication") is True or proof.get("release_packaging") is True:
        result.add_error(MXN_PATH_UNSAFE, "Runtime/spawnable proof surface must not publish or package.")
    if proof.get("production_level_mutation") is True:
        result.add_error(MXN_PATH_UNSAFE, "Runtime/spawnable proof surface must not mutate production levels.")

    status = str(proof.get("status") or proof.get("runtime_spawnable_proof_status") or "").strip()
    allowed_statuses = {
        "pass",
        "unavailable_with_verified_reason",
        "informational_only",
        "blocked_by_missing_runtime_executable",
        "blocked_by_missing_runtime_readiness",
        "blocked_by_unpinned_runtime_surface",
        "blocked_by_unsafe_runtime_execution",
        "blocked_by_release_packaging_required",
        "blocked_by_publication_required",
        "unsupported_by_current_project_build",
        "runtime_spawnable_character_proof_unavailable",
        "runtime_spawnable_proof_requires_dedicated_runtime_harness",
        "product_dependency_proof_pass",
        "product_dependency_proof_unavailable",
    }
    if status not in allowed_statuses:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime/spawnable proof surface requires a precise typed status.",
        )

    surface = proof.get("runtime_spawnable_surface_discovery", {})
    surface_status = str(surface.get("status", "")).strip() if isinstance(surface, Mapping) else ""
    if surface_status not in {"runtime_surface_discovery_pass", "unavailable_with_verified_reason", "unsupported_by_current_project_build"}:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime/spawnable proof surface requires explicit surface discovery status.",
        )

    dependency = proof.get("product_dependency_proof", {})
    dependency_status = str(dependency.get("status", "")).strip() if isinstance(dependency, Mapping) else ""
    if dependency_status != str(proof.get("product_dependency_proof_status", dependency_status)).strip():
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime/spawnable product dependency proof status must be recorded consistently.",
        )
    if dependency_status not in {"product_dependency_proof_pass", "product_dependency_proof_unavailable", "informational_only"}:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime/spawnable proof surface requires typed product dependency proof status.",
        )

    attempted = proof.get("runtime_spawnable_execution_attempted") is True
    verified = proof.get("runtime_spawnable_execution_verified") is True
    execution_result = proof.get("runtime_spawnable_execution_result", {})
    execution_status = str(execution_result.get("status", "")).strip() if isinstance(execution_result, Mapping) else ""
    if verified and not attempted:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime/spawnable execution cannot be verified unless runtime execution was actually attempted.",
        )
    if verified and execution_status != "pass":
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime/spawnable execution verified=true requires runtime execution result status=pass.",
        )
    if attempted and not verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Attempted runtime/spawnable execution cannot pass unless it is verified.",
        )
    if not attempted and execution_status != "runtime_execution_not_attempted":
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unattempted runtime/spawnable execution must be recorded as runtime_execution_not_attempted.",
        )
    if not attempted and not str(proof.get("runtime_spawnable_blocked_reason", "")).strip():
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unattempted runtime/spawnable execution requires a typed blocked reason.",
        )

    required_failures = proof.get("required_runtime_spawnable_assertions_failed", [])
    assertion_failures = proof.get("runtime_spawnable_assertion_failures", [])
    if (isinstance(required_failures, list) and required_failures) or (
        isinstance(assertion_failures, list) and assertion_failures
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime/spawnable proof surface cannot pass with failed required runtime assertions.",
        )

    for field, label in (
        ("runtime_spawnable_missing_asset_signals", "runtime missing asset"),
        ("runtime_spawnable_missing_character_signals", "runtime missing character"),
    ):
        scan = proof.get(field, {})
        scan_status = str(scan.get("status", "")).strip() if isinstance(scan, Mapping) else ""
        if scan_status not in {"pass", "unavailable_with_verified_reason", "runtime_execution_not_attempted"}:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"Runtime/spawnable proof surface requires {label} signal scan to be pass or explicitly unavailable.",
            )


def _validate_direct_procprefab_content_assertions(
    report: Mapping[str, Any],
    semantics: Mapping[str, Any],
    prefab_checks: Any,
    result: ValidationResult,
) -> None:
    content = semantics.get("direct_procprefab_content_assertions")
    if not isinstance(content, Mapping):
        content = semantics.get("direct_product_assertions")
    if not isinstance(content, Mapping):
        content = report.get("direct_procprefab_content_assertions")
    if not isinstance(content, Mapping) and isinstance(prefab_checks, Mapping):
        content = prefab_checks.get("direct_procprefab_content_assertions")
    if not isinstance(content, Mapping):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Verified direct procprefab instantiation cannot pass without direct_procprefab_content_assertions evidence.",
        )
        return

    content_status = str(content.get("status", "")).strip()
    required_status = str(
        content.get("required_assertions_status") or content.get("direct_product_assertion_status") or ""
    ).strip()
    required_failures = content.get("required_assertions_failed", [])
    assertion_failures = content.get("assertion_failures", [])
    if (
        content_status != "pass"
        or required_status != "pass"
        or (isinstance(required_failures, list) and required_failures)
        or (isinstance(assertion_failures, list) and assertion_failures)
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab content assertions cannot pass with failed required assertions.",
        )

    container_valid = content.get("created_container_valid") is True
    container_evidence = content.get("container_entity_valid", {})
    if isinstance(container_evidence, Mapping):
        container_valid = container_valid or container_evidence.get("status") == "pass"
    if not container_valid:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab content assertions require valid created container/entity evidence.",
        )

    if content.get("owning_prefab_path_matches_expected") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab content assertions require owning prefab path to match the selected product path.",
        )

    created_count = 0
    try:
        created_count = int(content.get("created_entity_count", 0) or 0)
    except (TypeError, ValueError):
        created_count = 0
    if str(content.get("created_entity_count_status", "")).strip() != "pass" or created_count <= 0:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab content assertions require positive created entity count evidence.",
        )

    component_status = str(content.get("component_inventory_status", "")).strip()
    inventory = content.get("component_inventory", {})
    if not component_status and isinstance(inventory, Mapping):
        component_status = str(inventory.get("status", "")).strip()
    if component_status not in {"pass", "informational_only", "unavailable_with_verified_reason"}:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab content assertions require component inventory evidence with a typed status.",
        )
    if component_status == "fail":
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Direct procprefab content assertions cannot pass with failed component inventory evidence.",
        )

    for field, label in (
        ("missing_asset_log_signals", "missing asset"),
        ("editor_log_error_scan", "Editor log error"),
    ):
        scan = content.get(field, {})
        scan_status = str(scan.get("status", "")).strip() if isinstance(scan, Mapping) else ""
        if scan_status != "pass":
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"Direct procprefab content assertions require {label} scan status=pass.",
            )


def run_editor_smoke_corpus(
    corpus: Path | str = DEFAULT_CORPUS,
    *,
    mode: str = "fixture",
    manifest: Path | str = DEFAULT_MANIFEST,
    enable_editor_smoke: bool = False,
    strict_integration: bool = False,
    platform: str = "pc",
    env: Mapping[str, str] | None = None,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
    golden_project_fixture: Path | str = DEFAULT_GOLDEN_PROJECT_FIXTURE,
    diagnostic_mode: str = "full",
    timeout_seconds: int | None = None,
    progress_log: Path | str | None = None,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    if enable_editor_smoke or editor_smoke_gate_enabled(env) or mode == "local_editor_python":
        readiness = build_editor_smoke_readiness_report(
            env=env,
            manifest=manifest,
            golden_project_fixture=golden_project_fixture,
            strict=strict_integration,
        )
        missing_prerequisites = _missing_live_editor_prerequisites(env, readiness, live_requested=enable_editor_smoke)
        if readiness["status"] != "pass" or missing_prerequisites:
            return _unavailable_integration_report(
                manifest=manifest,
                strict_integration=strict_integration,
                platform=platform,
                env=env,
                readiness=readiness,
                missing_prerequisites=missing_prerequisites,
            )
        return _execute_live_editor_smoke(
            manifest=manifest,
            readiness=readiness,
            strict_integration=strict_integration,
            platform=platform,
            env=env,
            command_runner=command_runner,
            artifact_root=_resolve_path(artifact_root),
            golden_project_fixture=_resolve_path(golden_project_fixture),
            diagnostic_mode=_normalize_diagnostic_mode(diagnostic_mode),
            timeout_seconds=timeout_seconds,
            progress_log=_resolve_path(progress_log) if progress_log else None,
        )
    return _fixture_corpus_report(_resolve_path(corpus), manifest=manifest, platform=platform)


def build_editor_smoke_readiness_report(
    *,
    env: Mapping[str, str] | None = None,
    engine_root: Path | str | None = None,
    project: Path | str | None = None,
    editor_executable: Path | str | None = None,
    manifest: Path | str = DEFAULT_MANIFEST,
    golden_project_fixture: Path | str = DEFAULT_GOLDEN_PROJECT_FIXTURE,
    strict: bool = False,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    engine = _path_from_arg_or_env(engine_root, env, "O3DE_ENGINE_ROOT")
    project_path = _path_from_arg_or_env(project, env, "O3DE_PROJECT_PATH")
    editor_path = _select_editor_executable(editor_executable, engine, env)
    golden_fixture = _resolve_path(golden_project_fixture)

    engine_report = _engine_root_report(engine)
    project_report = _project_path_report(project_path)
    editor_report = _editor_executable_report(editor_path, engine)
    bindings_enabled = "EditorPythonBindings" in project_report.get("gem_names", [])
    bindings_available = _editor_python_bindings_available(engine)
    smoke_script = {
        "path": _repo_relative(EDITOR_SCRIPT),
        "present": EDITOR_SCRIPT.exists(),
    }
    temp_level_policy = _temp_level_policy_report(golden_fixture)
    live_publication_allowed = _enabled(env, "MAXINE_ALLOW_LIVE_PUBLICATION")
    release_packaging_allowed = _enabled(env, "MAXINE_ENABLE_RELEASE_PACKAGING")

    errors: List[str] = []
    warnings: List[str] = []
    problem_messages: List[str] = []
    if not engine_report["exists"]:
        problem_messages.append("O3DE_ENGINE_ROOT is missing or does not exist.")
    if not project_report["exists"]:
        problem_messages.append("O3DE_PROJECT_PATH is missing or does not exist.")
    elif project_report.get("project_name") != "MAXINE_GoldenCorpus":
        problem_messages.append("Project path is not MAXINE_GoldenCorpus.")
    if not editor_report["available"]:
        problem_messages.append("A project/engine-paired Editor executable was not found.")
    if not bindings_enabled:
        problem_messages.append("EditorPythonBindings is not enabled in the controlled project.")
    if not bindings_available:
        problem_messages.append("EditorPythonBindings runtime module was not found in the selected engine profile bin.")
    if not smoke_script["present"]:
        problem_messages.append("Editor Python smoke script is missing.")
    if not temp_level_policy["valid"]:
        problem_messages.append("Temporary smoke-level policy is missing or unsafe.")
    if live_publication_allowed:
        problem_messages.append("MAXINE_ALLOW_LIVE_PUBLICATION must remain disabled for Editor smoke.")
    if release_packaging_allowed:
        problem_messages.append("MAXINE_ENABLE_RELEASE_PACKAGING must remain disabled for Editor smoke.")

    status = "pass"
    if problem_messages:
        status = "fail" if strict else "unavailable"
        target = errors if strict else warnings
        target.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
    if live_publication_allowed or release_packaging_allowed:
        errors.append(MXN_PATH_UNSAFE)
        status = "fail"

    live_editor_allowed = (
        status == "pass"
        and _enabled(env, "MAXINE_ENABLE_O3DE_EDITOR_SMOKE")
        and _enabled(env, "MAXINE_ALLOW_LIVE_O3DE_COMMANDS")
        and _enabled(env, "MAXINE_ALLOW_LIVE_EDITOR_COMMANDS")
        and not live_publication_allowed
        and not release_packaging_allowed
    )

    return {
        "schema_version": "1.0.0",
        "report_type": "maxine_editor_smoke_readiness",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": status,
        "strict": strict,
        "manifest_ref": _repo_relative(_resolve_path(manifest)),
        "engine_root": engine_report,
        "project_path": project_report,
        "editor_executable": editor_report,
        "editor_python_bindings_enabled": bindings_enabled,
        "editor_python_bindings_available": bindings_available,
        "editor_smoke_script": smoke_script,
        "temp_level_policy": temp_level_policy,
        "live_editor_execution_allowed": live_editor_allowed,
        "live_publication_allowed": live_publication_allowed,
        "release_packaging_allowed": release_packaging_allowed,
        "live_editor_execution": False,
        "live_publication": False,
        "release_packaging": False,
        "artifact_roots": {
            "editor_smoke": "artifacts/o3de-integration/editor-smoke",
            "setup": "artifacts/o3de-integration/setup/editor",
        },
        "errors": _unique(errors),
        "warnings": _unique(warnings),
        "messages": problem_messages + _readiness_messages(live_editor_allowed),
        "next_steps": _editor_readiness_next_steps(problem_messages),
    }


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
    readiness: Mapping[str, Any] | None = None,
    missing_prerequisites: List[str] | None = None,
) -> Dict[str, Any]:
    detection = detect_editor_smoke_environment(env)
    status = "fail" if strict_integration else "skipped"
    errors = [MXN_VALIDATION_TOOL_UNAVAILABLE] if strict_integration else []
    warnings = [] if strict_integration else [MXN_VALIDATION_TOOL_UNAVAILABLE]
    missing = list(missing_prerequisites or [])
    messages = list(detection["messages"])
    if missing:
        messages.append("Live Editor smoke prerequisites are unavailable: " + ", ".join(missing) + ".")
    if readiness:
        messages.extend(str(message) for message in readiness.get("messages", []))
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
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "cases": [],
        "errors": errors,
        "warnings": warnings,
        "messages": _unique(messages),
        "evidence_refs": [
            {
                "id": "local-editor-smoke-integration-gate",
                "kind": "integration_check",
                "source": "detect_editor_smoke_environment",
            }
        ],
    }


def _missing_live_editor_prerequisites(
    env: Mapping[str, str],
    readiness: Mapping[str, Any],
    *,
    live_requested: bool,
) -> List[str]:
    missing: List[str] = []
    if not live_requested:
        missing.append("--enable-editor-smoke")
    for key in LIVE_EDITOR_GATE_ENV_VARS:
        if str(env.get(key, "")).strip() != "1":
            missing.append(key)
    if not readiness.get("engine_root", {}).get("exists"):
        missing.append("O3DE_ENGINE_ROOT")
    if not readiness.get("project_path", {}).get("exists"):
        missing.append("O3DE_PROJECT_PATH")
    if not readiness.get("editor_executable", {}).get("available"):
        missing.append("O3DE_EDITOR_EXECUTABLE")
    if not readiness.get("editor_python_bindings_enabled"):
        missing.append("EditorPythonBindings_enabled")
    if not readiness.get("editor_python_bindings_available"):
        missing.append("EditorPythonBindings_available")
    if not readiness.get("temp_level_policy", {}).get("valid"):
        missing.append("temp_level_policy")
    if readiness.get("live_publication_allowed"):
        missing.append("MAXINE_ALLOW_LIVE_PUBLICATION_must_be_0")
    if readiness.get("release_packaging_allowed"):
        missing.append("MAXINE_ENABLE_RELEASE_PACKAGING_must_be_0")
    return _unique(missing)


def _execute_live_editor_smoke(
    *,
    manifest: Path | str,
    readiness: Mapping[str, Any],
    strict_integration: bool,
    platform: str,
    env: Mapping[str, str],
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
    artifact_root: Path,
    golden_project_fixture: Path,
    diagnostic_mode: str,
    timeout_seconds: int | None,
    progress_log: Path | None,
) -> Dict[str, Any]:
    started_at = _utc_now()
    start_time = time.monotonic()
    run_id = "editor-smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = artifact_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    report_path = output_dir / "editor_smoke_live_report.json"
    template_path = output_dir / "editor_smoke_report.template.json"
    progress_path = progress_log or (output_dir / "progress.jsonl")

    engine_root = Path(str(readiness["engine_root"]["path"]))
    project_path = Path(str(readiness["project_path"]["path"]))
    editor_executable = Path(str(readiness["editor_executable"]["path"]))
    selected_timeout_seconds = timeout_seconds if timeout_seconds is not None else _editor_timeout_seconds(env)
    apb_baseline = _select_apb_baseline_report(env)
    manifest_path = _resolve_path(manifest)
    apb_payload = _load_json_if_present(apb_baseline)
    product_summary = _product_evidence_summary(apb_payload)
    expected_products = _expected_products_from_manifest(manifest_path, product_summary)
    missing_products = [product for product in expected_products if product not in product_summary["produced_products"]]

    if not apb_baseline or not apb_payload or product_summary["status"] != "pass" or missing_products or product_summary["cache_heuristic_used"]:
        messages = []
        if not apb_baseline:
            messages.append("No APB baseline report was found for the Editor smoke.")
        if product_summary["status"] != "pass":
            messages.append("APB baseline report is not pass.")
        if missing_products:
            messages.append("APB baseline is missing expected products: " + ", ".join(missing_products) + ".")
        if product_summary["cache_heuristic_used"]:
            messages.append("APB baseline used cache heuristic evidence.")
        return _unavailable_integration_report(
            manifest=manifest,
            strict_integration=True,
            platform=platform,
            env=env,
            readiness=readiness,
            missing_prerequisites=["APB_BASELINE_PRODUCT_EVIDENCE"],
        ) | {"messages": messages, "product_evidence_summary": product_summary}

    script_path = _editor_script_for_diagnostic_mode(diagnostic_mode)
    temp_level_name = "maxine_smoke_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    temp_level_rel = f"Levels/_maxine_smoke/{temp_level_name}"
    level_name_for_editor = f"_maxine_smoke/{temp_level_name}"
    argv = [
        str(editor_executable),
        "-NullRenderer",
        "-rhi=Null",
        "--skipWelcomeScreenDialog",
        "--autotest_mode",
        "--project-path",
        str(project_path),
        "--runpython",
        str(script_path),
    ]
    _write_progress_marker(
        progress_path,
        phase="wrapper",
        step="process_start",
        status="started",
        started_monotonic=start_time,
        message="Launching gated Editor smoke.",
        temp_level_path=temp_level_rel,
        report_path=report_path,
    )
    template = _live_report_template(
        run_id=run_id,
        manifest=manifest_path,
        readiness=readiness,
        platform=platform,
        strict_integration=strict_integration,
        argv=argv,
        timeout_seconds=selected_timeout_seconds,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        report_path=report_path,
        progress_path=progress_path,
        apb_baseline=apb_baseline,
        product_summary=product_summary,
        expected_products=expected_products,
        temp_level_rel=temp_level_rel,
        started_at=started_at,
        golden_project_fixture=golden_project_fixture,
        diagnostic_mode=diagnostic_mode,
        script_path=script_path,
    )
    template_path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")

    editor_env = dict(env)
    editor_env["O3DE_ENGINE_ROOT"] = str(engine_root)
    editor_env["O3DE_PROJECT_PATH"] = str(project_path)
    editor_env["O3DE_EDITOR_EXECUTABLE"] = str(editor_executable)
    editor_env["MAXINE_EDITOR_PROCESS_LAUNCHED"] = "1"
    editor_env["MAXINE_EDITOR_SMOKE_REPORT_OUT"] = str(report_path)
    editor_env["MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE"] = str(template_path)
    editor_env["MAXINE_EDITOR_SMOKE_PROGRESS_LOG"] = str(progress_path)
    editor_env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] = diagnostic_mode
    editor_env["MAXINE_EDITOR_SMOKE_TEMP_LEVEL_NAME"] = level_name_for_editor
    editor_env["MAXINE_EDITOR_SMOKE_TEMP_LEVEL_PATH"] = str(project_path / temp_level_rel)
    editor_env["MAXINE_EDITOR_SMOKE_ALLOW_TEMP_SANDBOX_LEVEL"] = "1"
    editor_env["MAXINE_ALLOW_LIVE_PUBLICATION"] = "0"
    editor_env["MAXINE_ENABLE_RELEASE_PACKAGING"] = "0"
    editor_env.setdefault("PYTHONIOENCODING", "utf-8")

    proc, timed_out, process_cleanup = _run_live_editor_command(
        argv,
        cwd=str(project_path),
        env=editor_env,
        timeout_seconds=selected_timeout_seconds,
        command_runner=command_runner,
    )
    finished_at = _utc_now()
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")
    duration_seconds = round(time.monotonic() - start_time, 3)
    progress_markers = _load_progress_markers(progress_path)
    last_progress_marker = _last_relevant_progress_marker(progress_markers)
    stall_phase = _classify_stall_phase(last_progress_marker) if timed_out else ""
    if timed_out:
        _write_progress_marker(
            progress_path,
            phase="wrapper",
            step="timeout_reached",
            status="stalled",
            started_monotonic=start_time,
            message=f"Editor smoke exceeded timeout of {selected_timeout_seconds} seconds.",
            error_code=MXN_EDITOR_SMOKE_STALLED,
        )
    _write_progress_marker(
        progress_path,
        phase="wrapper",
        step="final_status",
        status="stalled" if timed_out else "completed",
        started_monotonic=start_time,
        message="Wrapper finalized Editor smoke report.",
        error_code=MXN_EDITOR_SMOKE_STALLED if timed_out else "",
    )

    report = _load_json_if_present(report_path) or dict(template)
    runtime_report_found = report_path.exists()
    errors = list(report.get("errors", [])) if isinstance(report.get("errors", []), list) else []
    warnings = list(report.get("warnings", [])) if isinstance(report.get("warnings", []), list) else []
    messages = list(report.get("messages", [])) if isinstance(report.get("messages", []), list) else []
    if timed_out:
        errors.append(MXN_EDITOR_SMOKE_STALLED)
        messages.append(f"Editor smoke exceeded timeout of {selected_timeout_seconds} seconds and was stopped.")
    elif proc.returncode != 0:
        errors.append(MXN_EDITOR_PROCESS_EXIT_NONZERO)
        messages.append(f"Editor smoke exited with code {proc.returncode}.")
    elif not runtime_report_found:
        errors.append(MXN_RUNTIME_SMOKE_FAIL)
        messages.append("Editor exited without writing a smoke report.")

    report.update(
        {
            "generated_at": finished_at,
            "status": "stalled" if timed_out else "fail" if errors or proc.returncode != 0 else report.get("status", "pass"),
            "diagnostic_mode": diagnostic_mode,
            "live_editor_execution": True,
            "live_asset_processor_batch_execution": False,
            "live_publication": False,
            "release_packaging": False,
            "production_level_mutation": False,
            "exit_code": proc.returncode,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
            "timeout_seconds": selected_timeout_seconds,
            "timed_out": timed_out,
            "timeout_stall": timed_out,
            "process_cleanup": process_cleanup,
            "process_tree_cleanup": process_cleanup,
            "stdout_log_ref": _repo_relative(stdout_path),
            "stderr_log_ref": _repo_relative(stderr_path),
            "editor_log_ref": _find_editor_log_ref(project_path),
            "progress_log_ref": _repo_relative(progress_path),
            "last_progress_marker": last_progress_marker,
            "stall_phase": stall_phase,
            "script_path_redacted": _redact_path(str(script_path)),
            "script_path_mode": "absolute",
            "editor_command_working_directory": _redact_path(str(project_path)),
            "apb_baseline_ref": _repo_relative(apb_baseline),
            "product_evidence_summary": product_summary,
            "command_preview": _redacted_argv(argv),
            "command_argv_redacted": _redacted_argv(argv),
            "errors": _unique(errors),
            "warnings": _unique(warnings),
            "messages": _unique(messages),
        }
    )
    report["evidence_refs"] = _merge_evidence_refs(
        report.get("evidence_refs", []),
        [
            {"id": "editor-smoke-live-report", "kind": "editor_smoke_report", "path": _repo_relative(report_path)},
            {"id": "editor-smoke-progress-log", "kind": "editor_smoke_progress_log", "path": _repo_relative(progress_path)},
            {"id": "apb-baseline", "kind": "asset_processor_batch_report", "path": _repo_relative(apb_baseline)},
        ],
    )

    schema_result = schema_validate(report, load_json(SCHEMA_PATH))
    semantic_result = validate_editor_smoke_report(report, strict=True)
    if schema_result.status == "fail" or semantic_result.status == "fail":
        report["status"] = "fail" if report["status"] != "stalled" else "stalled"
        report["errors"] = _unique(report.get("errors", []) + schema_result.error_codes + semantic_result.error_codes)
        report["messages"] = _unique(report.get("messages", []) + schema_result.messages + semantic_result.messages)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _run_live_editor_command(
    argv: Sequence[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    timeout_seconds: int,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> Tuple[subprocess.CompletedProcess[str], bool, Dict[str, Any]]:
    if command_runner is not None:
        try:
            proc = command_runner(argv=list(argv), cwd=cwd, env=dict(env), timeout_seconds=timeout_seconds)
            return proc, False, {"attempted": False, "method": "", "return_code": None}
        except subprocess.TimeoutExpired as exc:
            return (
                subprocess.CompletedProcess(list(argv), None, stdout=exc.output or "", stderr=exc.stderr or ""),
                True,
                {"attempted": True, "method": "command_runner_timeout", "return_code": None},
            )

    proc = subprocess.Popen(list(argv), cwd=cwd, env=dict(env), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cleanup = {"attempted": False, "method": "", "return_code": None}
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        return subprocess.CompletedProcess(list(argv), proc.returncode, stdout=stdout, stderr=stderr), False, cleanup
    except subprocess.TimeoutExpired:
        cleanup = _terminate_process_tree(proc)
        stdout, stderr = proc.communicate(timeout=10)
        return subprocess.CompletedProcess(list(argv), None, stdout=stdout, stderr=stderr), True, cleanup


def _live_report_template(
    *,
    run_id: str,
    manifest: Path,
    readiness: Mapping[str, Any],
    platform: str,
    strict_integration: bool,
    argv: Sequence[str],
    timeout_seconds: int,
    stdout_path: Path,
    stderr_path: Path,
    report_path: Path,
    progress_path: Path,
    apb_baseline: Path,
    product_summary: Mapping[str, Any],
    expected_products: List[str],
    temp_level_rel: str,
    started_at: str,
    golden_project_fixture: Path,
    diagnostic_mode: str,
    script_path: Path,
) -> Dict[str, Any]:
    manifest_payload = _load_json_if_present(manifest) or {}
    lane = str(manifest_payload.get("job", {}).get("lane", "release_rigged")).strip() or "release_rigged"
    publication = manifest_payload.get("publication", {})
    publication_package = publication.get("package", {}) if isinstance(publication, Mapping) else {}
    source_uuid = _first_source_uuid(product_summary.get("products", []), manifest_payload)
    source_assets = _source_assets_from_manifest(manifest_payload, source_uuid)
    procprefab_ref = _first_product_path(product_summary.get("products", []), "procprefab")
    runtime_harness_payload = _runtime_harness_payload_for_editor_template(
        manifest=manifest,
        readiness=readiness,
        apb_baseline=apb_baseline,
    )
    return {
        "schema_version": "1.0.0",
        "report_type": "editor_smoke_fixture_bridge_v1",
        "report_id": run_id,
        "generated_at": started_at,
        "mode": "local_editor_python",
        "diagnostic_mode": diagnostic_mode,
        "status": "fail",
        "integration_enabled": True,
        "strict_integration": strict_integration,
        "live_editor_execution": True,
        "live_asset_processor_batch_execution": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "editor_python_bindings_required": True,
        "editor_python_bindings_available": bool(readiness.get("editor_python_bindings_available")),
        "o3de_engine_root_present": bool(readiness.get("engine_root", {}).get("exists")),
        "o3de_project_path_present": bool(readiness.get("project_path", {}).get("exists")),
        "editor_executable": str(readiness.get("editor_executable", {}).get("path", "")),
        "editor_executable_provenance": str(readiness.get("editor_executable", {}).get("provenance", "")),
        "engine_root_redacted": _redact_path(str(readiness.get("engine_root", {}).get("path", ""))),
        "project_path_redacted": _redact_path(str(readiness.get("project_path", {}).get("path", ""))),
        "editor_executable_redacted": _redact_path(str(readiness.get("editor_executable", {}).get("path", ""))),
        "command_preview": _redacted_argv(argv),
        "command_argv_redacted": _redacted_argv(argv),
        "exit_code": None,
        "started_at": started_at,
        "finished_at": "",
        "duration_seconds": 0,
        "timeout_seconds": timeout_seconds,
        "timed_out": False,
        "stdout_log_ref": _repo_relative(stdout_path),
        "stderr_log_ref": _repo_relative(stderr_path),
        "progress_log_ref": _repo_relative(progress_path),
        "last_progress_marker": {},
        "stall_phase": "",
        "editor_log_ref": "",
        "asset_processor_log_ref": "",
        "platform": platform,
        "lane": lane,
        "level_strategy": "temp_sandbox_level",
        "temp_level_policy": readiness.get("temp_level_policy", {}),
        "temp_level_path_redacted": temp_level_rel,
        "manifest_ref": _repo_relative(manifest),
        "evidence_bundle_ref": str(manifest_payload.get("evidence", {}).get("bundle_ref", "")),
        "package_ref": str(publication_package.get("package_root", "")) if isinstance(publication_package, Mapping) else "",
        "prefab_ref": str(publication_package.get("prefab_ref", "")) if isinstance(publication_package, Mapping) else "",
        "procprefab_ref": procprefab_ref,
        "source_uuid": source_uuid,
        "product_resolver_report_ref": "apb_baseline.produced_products",
        "asset_processor_batch_report_ref": _repo_relative(apb_baseline),
        "apb_baseline_ref": _repo_relative(apb_baseline),
        "source_assets": source_assets,
        "expected_products": expected_products,
        "produced_products": list(product_summary.get("products", [])),
        "pending_assets": [],
        "missing_products": list(product_summary.get("missing_products", [])),
        "product_evidence_summary": dict(product_summary),
        "entity_expectations": [{"name": "maxine_smoke_entity", "required_components": ["Transform"]}],
        "component_expectations": ["Transform"],
        "instantiated_entities": [],
        "missing_components": [],
        "screenshots": [],
        "cache_heuristic_used": bool(product_summary.get("cache_heuristic_used")),
        "script_path_redacted": _redact_path(str(script_path)),
        "script_path_mode": "absolute",
        "editor_command_working_directory": _redact_path(str(readiness.get("project_path", {}).get("path", ""))),
        "component_type_registry": {},
        "binding_call_surface": {},
        "safe_call_results": [],
        "component_binding_checks": {"status": "not_run"},
        "actor_binding_checks": {"status": "not_run"},
        "prefab_binding_checks": {"status": "not_run"},
        "source_prefab_baseline_result": {"status": "not_run"},
        "direct_procprefab_product_semantics": {"status": "not_run"},
        "direct_procprefab_content_assertions": {"status": "not_run"},
        "procprefab_character_assertions": {"status": "not_run"},
        "runtime_spawnable_proof": {"status": "not_run"},
        "runtime_harness": runtime_harness_payload,
        "property_path_discovery": {},
        "property_list_summary": {},
        "no_fake_success": True,
        "entity_smoke": {"status": "not_run"},
        "prefab_smoke": {"status": "not_run"},
        "actor_smoke": {"status": "not_run"},
        "component_smoke": {"status": "not_run"},
        "errors": [],
        "warnings": [],
        "messages": [],
        "runner_context": _runner_context(),
        "evidence_refs": [
            {"id": "golden-project-fixture", "kind": "o3de_golden_project_fixture", "path": _repo_relative(golden_project_fixture)},
            {"id": "editor-python-smoke-script", "kind": "editor_python_script", "path": _repo_relative(script_path)},
            {"id": "editor-smoke-report-template", "kind": "editor_smoke_report_template", "path": _repo_relative(report_path)},
            {"id": "editor-smoke-progress-log", "kind": "editor_smoke_progress_log", "path": _repo_relative(progress_path)},
        ],
        "next_steps": [],
    }


def _runtime_harness_payload_for_editor_template(
    *,
    manifest: Path,
    readiness: Mapping[str, Any],
    apb_baseline: Path,
) -> Dict[str, Any]:
    try:
        report = runtime_harness_tool.run_runtime_harness(
            manifest=manifest,
            pin_runtime_command=True,
            strict=False,
            engine_root=Path(str(readiness.get("engine_root", {}).get("path", ""))),
            project=Path(str(readiness.get("project_path", {}).get("path", ""))),
            apb_report=apb_baseline,
        )
        payload = report.get("runtime_harness", report)
        return dict(payload) if isinstance(payload, Mapping) else {"runtime_harness_status": "unavailable_with_verified_reason"}
    except Exception as exc:
        return {
            "runtime_harness_status": "unavailable_with_verified_reason",
            "runtime_harness_readiness_status": "unavailable_with_verified_reason",
            "runtime_harness_unavailable_reason": "runtime_harness_readiness_exception",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_harness_proof_is_character_proof": False,
            "runtime_exit_fixture_status": "not_run",
            "runtime_exit_fixture_available": False,
            "runtime_exit_fixture_execution_verified": False,
            "runtime_exit_fixture_runtime_command_uses_product_load_probe": False,
            "runtime_exit_fixture_is_runtime_character_proof": False,
            "runtime_exit_fixture_character_proof_claimed": False,
            "runtime_exit_fixture_character_proof_verified": False,
            "runtime_character_product_load": {"status": "runtime_character_product_load_not_attempted"},
            "runtime_character_product_load_status": "runtime_character_product_load_not_attempted",
            "runtime_character_product_load_verified": False,
            "runtime_character_product_load_claimed": False,
            "runtime_character_product_load_probe_enabled": False,
            "runtime_character_product_load_probe_shipping_behavior": False,
            "runtime_character_product_load_source_refs": [],
            "runtime_character_product_load_candidate_matrix": [],
            "runtime_character_product_load_candidate_matrix_recorded": False,
            "runtime_character_product_load_products": [],
            "runtime_character_product_load_required_products_complete": False,
            "runtime_character_product_load_all_required_ready": False,
            "runtime_character_product_load_missing_products": [],
            "runtime_character_product_load_timed_out_products": [],
            "runtime_character_product_load_failed_products": [],
            "runtime_character_product_load_markers_observed": False,
            "runtime_character_product_load_selected_product_log_scan": [],
            "runtime_character_product_load_selected_product_missing_error_scan": {
                "status": "runtime_character_product_load_not_attempted",
                "matches": [],
            },
            "runtime_character_product_load_is_instantiation_proof": False,
            "runtime_runtime_character_product_load_is_instantiation_proof": False,
            "runtime_character_product_load_runtime_equivalent_surface_kind": "",
            "runtime_character_spawnable_surface": {"status": "runtime_character_spawnable_surface_not_attempted"},
            "runtime_character_spawnable_surface_status": "runtime_character_spawnable_surface_not_attempted",
            "runtime_character_spawnable_surface_source_validation": "runtime_character_spawnable_surface_not_attempted",
            "runtime_character_spawnable_surface_source_refs": [],
            "runtime_character_spawnable_surface_search_status": "runtime_character_spawnable_surface_not_attempted",
            "runtime_character_spawnable_surface_candidates": [],
            "runtime_character_spawnable_surface_candidate_matrix_recorded": False,
            "runtime_character_spawnable_surface_selected": "",
            "runtime_character_spawnable_surface_found": False,
            "runtime_character_spawnable_surface_claimed": False,
            "runtime_character_spawnable_surface_verified": False,
            "runtime_character_spawnable_surface_generation_required": False,
            "runtime_character_spawnable_surface_generation_completed": False,
            "runtime_character_spawnable_surface_generation_blocker": "",
            "runtime_character_prefab_source": {"status": "runtime_character_prefab_source_not_attempted"},
            "runtime_character_prefab_source_status": "runtime_character_prefab_source_not_attempted",
            "runtime_character_prefab_source_path": "",
            "runtime_character_prefab_source_kind": "",
            "runtime_character_prefab_source_owned_by_repo": False,
            "runtime_character_prefab_source_committed": False,
            "runtime_character_prefab_source_is_defaultlevel": False,
            "runtime_character_prefab_source_is_production_level": False,
            "runtime_character_prefab_source_is_temp": False,
            "runtime_character_prefab_source_is_generic_transform_only": False,
            "runtime_character_prefab_source_is_character_specific": False,
            "runtime_character_prefab_source_is_approved": False,
            "runtime_character_prefab_source_generation_strategy": "",
            "runtime_character_prefab_source_generation_source_validation": "runtime_character_prefab_source_not_attempted",
            "runtime_character_prefab_source_generation_source_refs": [],
            "runtime_character_prefab_source_manifest_refs": [],
            "runtime_character_prefab_source_approved_product_refs": [],
            "runtime_character_prefab_source_apb_expected_product": "",
            "runtime_character_prefab_source_apb_product_found": False,
            "runtime_character_prefab_source_apb_product_path": "",
            "runtime_character_prefab_source_apb_product_asset_id": "",
            "runtime_character_prefab_source_apb_product_asset_type": "",
            "runtime_character_prefab_source_apb_product_builder": "",
            "runtime_character_prefab_source_apb_product_status": "runtime_character_prefab_source_apb_product_not_attempted",
            "runtime_character_prefab_source_generation_completed": False,
            "runtime_character_prefab_source_generation_blocker": "",
            "runtime_character_spawn_instantiation": {"status": "runtime_character_spawn_instantiation_not_attempted"},
            "runtime_character_spawn_instantiation_status": "runtime_character_spawn_instantiation_not_attempted",
            "runtime_character_spawn_instantiation_claimed": False,
            "runtime_character_spawn_instantiation_verified": False,
            "runtime_character_spawn_instantiation_source_validation": "runtime_character_spawn_instantiation_not_attempted",
            "runtime_character_spawn_instantiation_source_refs": [],
            "runtime_character_spawn_instantiation_probe_enabled": False,
            "runtime_character_spawn_instantiation_probe_shipping_behavior": False,
            "runtime_character_spawn_instantiation_candidate_matrix": [],
            "runtime_character_spawn_instantiation_candidate_matrix_recorded": False,
            "runtime_character_spawn_instantiation_api": "",
            "runtime_character_spawn_instantiation_api_argument_shape": {},
            "runtime_character_spawn_instantiation_context_status": "",
            "runtime_character_spawn_instantiation_spawnable_product_path": "",
            "runtime_character_spawn_instantiation_spawnable_catalog_path": "",
            "runtime_character_spawn_instantiation_spawnable_asset_id": "",
            "runtime_character_spawn_instantiation_spawnable_asset_type": "",
            "runtime_character_spawn_instantiation_spawnable_loaded_ready": False,
            "runtime_character_spawn_instantiation_spawn_request_issued": False,
            "runtime_character_spawn_instantiation_spawn_ticket": "",
            "runtime_character_spawn_instantiation_spawn_completion_observed": False,
            "runtime_character_spawn_instantiation_spawn_result": "",
            "runtime_character_spawn_instantiation_spawned_entity_count": 0,
            "runtime_character_spawn_instantiation_spawned_entity_ids": [],
            "runtime_character_spawn_instantiation_spawned_entity_names": [],
            "runtime_character_spawn_instantiation_spawned_entity_component_inventory": [],
            "runtime_character_spawn_instantiation_timeout": False,
            "runtime_character_spawn_instantiation_log_errors": [],
            "runtime_character_spawn_instantiation_cleanup_attempted": False,
            "runtime_character_spawn_instantiation_cleanup_status": "runtime_character_spawn_instantiation_cleanup_not_attempted",
            "runtime_character_spawn_instantiation_is_animation_proof": False,
            "runtime_character_spawn_instantiation_remaining_blocker": "",
            "runtime_character_instantiation_claimed": False,
            "runtime_character_instantiation_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "live_publication": False,
            "release_packaging": False,
            "production_level_mutation": False,
            "fake_success": False,
            "cache_heuristic_used": False,
            "messages": [str(exc)],
        }


def _editor_timeout_seconds(env: Mapping[str, str]) -> int:
    raw = str(env.get("MAXINE_EDITOR_SMOKE_TIMEOUT_SECONDS", "")).strip()
    if not raw:
        return DEFAULT_EDITOR_TIMEOUT_SECONDS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_EDITOR_TIMEOUT_SECONDS


def _normalize_diagnostic_mode(value: str | None) -> str:
    mode = str(value or "full").strip().lower()
    return mode if mode in DIAGNOSTIC_EDITOR_SCRIPTS else "full"


def _editor_script_for_diagnostic_mode(mode: str) -> Path:
    return DIAGNOSTIC_EDITOR_SCRIPTS[_normalize_diagnostic_mode(mode)]


def _write_progress_marker(
    path: Path,
    *,
    phase: str,
    step: str,
    status: str,
    started_monotonic: float,
    message: str = "",
    pid: int | None = None,
    temp_level_path: str = "",
    report_path: Path | None = None,
    error_code: str = "",
) -> None:
    record: Dict[str, Any] = {
        "timestamp": _utc_now(),
        "phase": phase,
        "step": step,
        "status": status,
        "message": message,
        "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
    }
    if pid is not None:
        record["pid"] = pid
    if temp_level_path:
        record["temp_level_path"] = _redact_path(temp_level_path)
    if report_path is not None:
        record["report_path"] = _repo_relative(report_path)
    if error_code:
        record["error_code"] = error_code
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _load_progress_markers(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    markers: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            markers.append(payload)
    return markers


def _last_relevant_progress_marker(markers: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    for marker in reversed(markers):
        if str(marker.get("phase", "")) == "script":
            return dict(marker)
    if markers:
        return dict(markers[-1])
    return {}


def _classify_stall_phase(marker: Mapping[str, Any]) -> str:
    step = str(marker.get("step", "")).strip()
    status = str(marker.get("status", "")).strip()
    if not step:
        return "editor_startup_stall"
    if step in {"process_start", "stdout_opened", "stderr_opened"}:
        return "runpython_not_invoked"
    if step == "python_script_import_started":
        return "script_import_stall"
    if step == "azlmbr_import_started":
        return "azlmbr_import_stall"
    if step == "product_evidence_load_started":
        return "product_evidence_stall"
    if step == "create_level_started":
        return "temp_level_create_stall"
    if step == "open_level_started":
        return "temp_level_open_stall"
    if step == "save_level_started":
        return "temp_level_save_stall"
    if step == "idle_wait_started":
        return "idle_wait_stall"
    if step == "entity_create_started":
        return "entity_create_stall"
    if step == "component_binding_started":
        return "component_binding_stall"
    if step == "actor_binding_started":
        return "actor_binding_stall"
    if step == "actor_asset_assignment_started":
        return "actor_asset_assignment_stall"
    if step == "prefab_binding_started":
        return "prefab_binding_stall"
    if step == "prefab_instantiation_started":
        return "prefab_instantiation_stall"
    if step == "procprefab_product_instantiation_started":
        return "procprefab_product_instantiation_stall"
    if step == "procprefab_content_assertions_started":
        return "procprefab_content_assertions_stall"
    if step == "procprefab_character_assertions_started":
        return "procprefab_character_assertions_stall"
    if step == "runtime_spawnable_proof_started":
        return "runtime_spawnable_proof_stall"
    if step == "report_write_started":
        return "report_write_stall"
    if status in {"started", "running"}:
        return "unknown_editor_stall"
    return "unknown_editor_stall"


def _select_apb_baseline_report(env: Mapping[str, str]) -> Path | None:
    explicit = str(env.get("MAXINE_APB_BASELINE_REPORT", "")).strip()
    if explicit and Path(explicit).exists():
        return Path(explicit)
    reports = sorted(
        DEFAULT_APB_ARTIFACT_ROOT.glob("apb-live-*/asset_processor_batch_live_report.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return reports[0] if reports else None


def _load_json_if_present(path: Path | None) -> Dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _product_evidence_summary(apb_payload: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not apb_payload:
        return {
            "status": "missing",
            "produced_products": [],
            "missing_products": [],
            "pending_products": [],
            "cache_heuristic_used": False,
            "products": [],
        }
    products = [dict(product) for product in apb_payload.get("produced_products", []) if isinstance(product, Mapping)]
    produced = _unique(
        [
            str(product.get("product_type", "")).strip()
            for product in products
            if str(product.get("status", "")).strip() == "ready" and str(product.get("product_type", "")).strip()
        ]
    )
    return {
        "status": str(apb_payload.get("status", "")).strip() or "unknown",
        "produced_products": produced,
        "missing_products": [str(value) for value in apb_payload.get("missing_products", []) if str(value).strip()],
        "pending_products": [str(value) for value in apb_payload.get("pending_products", []) if str(value).strip()],
        "cache_heuristic_used": bool(apb_payload.get("cache_heuristic_used", False)),
        "products": products,
    }


def _expected_products_from_manifest(manifest: Path, product_summary: Mapping[str, Any]) -> List[str]:
    payload = _load_json_if_present(manifest) or {}
    o3de = payload.get("o3de", {})
    expected = (
        [str(product_type).strip() for product_type in o3de.get("expected_product_types", []) if str(product_type).strip()]
        if isinstance(o3de, Mapping)
        else []
    )
    if expected:
        return _unique(expected)
    return _unique([str(product_type) for product_type in product_summary.get("produced_products", [])])


def _source_assets_from_manifest(manifest_payload: Mapping[str, Any], source_uuid: str) -> List[Dict[str, Any]]:
    inputs = manifest_payload.get("inputs", {})
    sources = inputs.get("sources", []) if isinstance(inputs, Mapping) else []
    result: List[Dict[str, Any]] = []
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, Mapping):
            continue
        path = str(source.get("relative_path", "") or source.get("path", "")).strip()
        if path:
            result.append({"path": path, "source_uuid": source_uuid})
    return result


def _first_source_uuid(products: Any, manifest_payload: Mapping[str, Any]) -> str:
    if isinstance(products, list):
        for product in products:
            if isinstance(product, Mapping) and str(product.get("source_uuid", "")).strip():
                return str(product["source_uuid"]).strip()
    o3de = manifest_payload.get("o3de", {})
    return str(o3de.get("source_uuid", "")).strip() if isinstance(o3de, Mapping) else ""


def _first_product_path(products: Any, product_type: str) -> str:
    if not isinstance(products, list):
        return ""
    for product in products:
        if isinstance(product, Mapping) and str(product.get("product_type", "")).strip() == product_type:
            return str(product.get("relative_product_path", "") or product.get("product_path", "")).strip()
    return ""


def _redacted_argv(argv: Sequence[str]) -> List[str]:
    redacted: List[str] = []
    for value in argv:
        text = str(value)
        if any(marker in text.lower() for marker in ("token=", "password=", "secret=", "key=")):
            redacted.append("<redacted>")
        else:
            redacted.append(_redact_path(text))
    return redacted


def _redact_path(value: str) -> str:
    repo = str(REPO_ROOT.resolve()).replace("\\", "/")
    home = str(Path.home()).replace("\\", "/")
    normalized = value.replace("\\", "/")
    if repo and normalized.lower().startswith(repo.lower()):
        return "%REPO_ROOT%" + normalized[len(repo):]
    if home and normalized.lower().startswith(home.lower()):
        return "%USERPROFILE%" + normalized[len(home):]
    return normalized


def _find_editor_log_ref(project_path: Path) -> str:
    candidates = list(project_path.glob("**/Editor.log"))
    if not candidates:
        return ""
    newest = max(candidates, key=lambda path: path.stat().st_mtime)
    return _redact_path(str(newest))


def _merge_evidence_refs(existing: Any, additions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    refs = [dict(ref) for ref in existing if isinstance(ref, Mapping)] if isinstance(existing, list) else []
    seen = {str(ref.get("id", "")) for ref in refs}
    for ref in additions:
        if str(ref.get("id", "")) not in seen:
            refs.append(ref)
            seen.add(str(ref.get("id", "")))
    return refs


def _terminate_process_tree(proc: subprocess.Popen[str]) -> Dict[str, Any]:
    cleanup = {"attempted": True, "method": "kill", "return_code": None}
    if platform_module.system().lower() == "windows":
        taskkill = subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], text=True, capture_output=True)
        cleanup["method"] = "taskkill /T /F"
        cleanup["return_code"] = taskkill.returncode
        if taskkill.returncode == 0:
            return cleanup
    try:
        proc.kill()
        cleanup["return_code"] = 0
    except Exception:
        cleanup["return_code"] = 1
    return cleanup


def _runner_context() -> Dict[str, Any]:
    runner_labels = [label.strip() for label in str(os.environ.get("RUNNER_LABELS", "")).split(",") if label.strip()]
    return {
        "os": platform_module.platform(),
        "runner_name": os.environ.get("RUNNER_NAME", ""),
        "self_hosted_expected": True,
        "private_runner_labels": runner_labels,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _path_from_arg_or_env(value: Path | str | None, env: Mapping[str, str], key: str) -> Path | None:
    raw = str(value if value is not None else env.get(key, "")).strip()
    return Path(raw) if raw else None


def _engine_root_report(path: Path | None) -> Dict[str, Any]:
    exists = bool(path) and path.exists()
    return {
        "path": _display_path(path),
        "exists": exists,
        "engine_json_present": bool(path) and (path / "engine.json").exists(),
        "scripts_present": bool(path) and ((path / "scripts" / "o3de.bat").exists() or (path / "scripts" / "o3de.py").exists()),
    }


def _project_path_report(path: Path | None) -> Dict[str, Any]:
    exists = bool(path) and path.exists()
    project_json = path / "project.json" if path else None
    payload: Dict[str, Any] = {}
    if project_json and project_json.exists():
        try:
            payload = json.loads(project_json.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            payload = {}
    gem_names = [str(gem) for gem in payload.get("gem_names", []) if str(gem).strip()] if isinstance(payload.get("gem_names"), list) else []
    return {
        "path": _display_path(path),
        "exists": exists,
        "project_json_present": bool(project_json and project_json.exists()),
        "project_name": str(payload.get("project_name", "")).strip(),
        "gem_names": gem_names,
    }


def _select_editor_executable(
    explicit: Path | str | None,
    engine_root: Path | None,
    env: Mapping[str, str],
) -> Path | None:
    raw = str(explicit if explicit is not None else env.get("O3DE_EDITOR_EXECUTABLE", "")).strip()
    if raw:
        return Path(raw)
    if engine_root:
        profile_bin = engine_root / "build" / "windows" / "bin" / "profile"
        for name in EDITOR_TOOL_NAMES:
            candidate = profile_bin / name
            if candidate.exists() and candidate.is_file():
                return candidate
    path_candidate = _find_editor_on_path(env)
    return Path(path_candidate) if path_candidate else None


def _editor_executable_report(path: Path | None, engine_root: Path | None) -> Dict[str, Any]:
    exists = bool(path) and path.exists() and path.is_file()
    name_valid = bool(path) and Path(path).name.lower() in {name.lower() for name in EDITOR_TOOL_NAMES}
    provenance = _editor_provenance(path, engine_root) if path else "unavailable"
    return {
        "path": _display_path(path),
        "available": bool(exists and name_valid and provenance in {"engine_profile_bin", "engine_root"}),
        "exists": exists,
        "name_valid": name_valid,
        "provenance": provenance,
    }


def _editor_provenance(path: Path | None, engine_root: Path | None) -> str:
    if not path or not engine_root:
        return "unavailable"
    try:
        resolved_path = path.resolve()
        resolved_engine = engine_root.resolve()
    except OSError:
        return "invalid"
    if not _is_relative_to(resolved_path, resolved_engine):
        return "outside_engine_root"
    profile_bin = resolved_engine / "build" / "windows" / "bin" / "profile"
    if resolved_path.parent == profile_bin:
        return "engine_profile_bin"
    return "engine_root"


def _editor_python_bindings_available(engine_root: Path | None) -> bool:
    if not engine_root:
        return False
    profile_bin = engine_root / "build" / "windows" / "bin" / "profile"
    return any(profile_bin.glob("EditorPythonBindings*.dll")) or any(profile_bin.glob("EditorPythonBindings*.pyd"))


def _temp_level_policy_report(golden_project_fixture: Path) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if golden_project_fixture.exists():
        try:
            payload = json.loads(golden_project_fixture.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            payload = {}
    raw_policy = payload.get("temp_level_policy", {})
    policy = raw_policy if isinstance(raw_policy, dict) else {}
    level_root = str(policy.get("level_root", "")).strip()
    valid = (
        bool(policy.get("enabled"))
        and level_root.replace("\\", "/").startswith("Levels/_maxine_smoke")
        and policy.get("never_use_production_levels") is True
        and policy.get("allow_existing_level_readonly") is False
        and str(policy.get("cleanup_policy", "")).strip()
    )
    return {
        "fixture_ref": _repo_relative(golden_project_fixture),
        "present": golden_project_fixture.exists(),
        "valid": bool(valid),
        "level_root": level_root,
        "naming_prefix": str(policy.get("naming_prefix", "")).strip(),
        "cleanup_policy": str(policy.get("cleanup_policy", "")).strip(),
        "never_use_production_levels": policy.get("never_use_production_levels") is True,
        "allow_existing_level_readonly": policy.get("allow_existing_level_readonly") is True,
    }


def _readiness_messages(live_editor_allowed: bool) -> List[str]:
    if live_editor_allowed:
        return ["Live Editor smoke gates are open, while publication and release packaging remain blocked."]
    return ["Readiness checks do not execute Editor, publish, package, delete Asset Cache, or mutate production levels."]


def _editor_readiness_next_steps(problem_messages: List[str]) -> List[str]:
    if not problem_messages:
        return ["Run the gated Editor smoke command only after the APB clean baseline passes in the same session."]
    steps = []
    if any("Editor executable" in message for message in problem_messages):
        steps.append("Build or set the project/engine-paired Editor executable, then rerun readiness.")
    if any("EditorPythonBindings" in message for message in problem_messages):
        steps.append("Enable/build EditorPythonBindings for the controlled MAXINE_GoldenCorpus project.")
    if any("Temporary smoke-level policy" in message for message in problem_messages):
        steps.append("Repair the golden project fixture temp-level policy before running live Editor.")
    if not steps:
        steps.append("Resolve the reported readiness blockers, then rerun strict readiness.")
    return steps


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _display_path(path: Path | None) -> str:
    return str(path) if path else ""


def editor_smoke_gate_enabled(env: Mapping[str, str] | None = None) -> bool:
    env = env if env is not None else os.environ
    return str(env.get("MAXINE_ENABLE_O3DE_EDITOR_SMOKE", "")).strip() == "1" or str(
        env.get("MAXINE_ENABLE_O3DE_INTEGRATION", "")
    ).strip() == "1"


def _enabled(env: Mapping[str, str], key: str) -> bool:
    return str(env.get(key, "")).strip() == "1"


def _exit_code_for_status(report: Mapping[str, Any]) -> int:
    return 1 if str(report.get("status", "")).strip() in {"fail", "stalled", "unavailable"} else 0


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
    parser.add_argument("--check-local-readiness", action="store_true", help="Inspect local Editor smoke readiness without running Editor.")
    parser.add_argument("--engine-root", help="O3DE engine root for local readiness.")
    parser.add_argument("--project", help="Controlled O3DE project path for local readiness.")
    parser.add_argument("--editor-executable", help="Project/engine-paired Editor executable path.")
    parser.add_argument("--golden-project-fixture", default=str(DEFAULT_GOLDEN_PROJECT_FIXTURE), help="Golden project fixture contract path.")
    parser.add_argument("--diagnostic-mode", choices=DIAGNOSTIC_MODES, default="full", help="Live Editor diagnostic smoke scope.")
    parser.add_argument("--timeout-seconds", type=int, help="Bounded live Editor smoke timeout in seconds.")
    parser.add_argument("--progress-log", help="Optional JSONL progress log path for live Editor smoke diagnostics.")
    parser.add_argument("--apb-report", help="Explicit APB baseline report path for live Editor smoke product evidence.")
    parser.add_argument("--strict", action="store_true", help="Fail if local Editor smoke readiness is unavailable.")
    parser.add_argument("--strict-integration", action="store_true", help="Fail if local Editor tooling is unavailable.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = _resolve_path(args.manifest)
    if args.check_local_readiness:
        report = build_editor_smoke_readiness_report(
            engine_root=args.engine_root,
            project=args.project,
            editor_executable=args.editor_executable,
            golden_project_fixture=args.golden_project_fixture,
            strict=args.strict or args.strict_integration,
        )
        _print_readiness_report(report)
        return 1 if report["status"] == "fail" else 0
    if not manifest.exists():
        print(f"Editor smoke fixture bridge: fail")
        print(f"  error: MXN_INPUT_MISSING")
        print(f"  - Manifest not found: {manifest}")
        return 2
    env_map = dict(os.environ)
    if args.engine_root:
        env_map["O3DE_ENGINE_ROOT"] = args.engine_root
    if args.project:
        env_map["O3DE_PROJECT_PATH"] = args.project
    if args.editor_executable:
        env_map["O3DE_EDITOR_EXECUTABLE"] = args.editor_executable
    if args.apb_report:
        env_map["MAXINE_APB_BASELINE_REPORT"] = args.apb_report
    result = run_editor_smoke_corpus(
        args.corpus,
        mode=args.mode,
        manifest=manifest,
        enable_editor_smoke=args.enable_editor_smoke,
        strict_integration=args.strict_integration,
        platform=args.platform,
        env=env_map,
        golden_project_fixture=args.golden_project_fixture,
        diagnostic_mode=args.diagnostic_mode,
        timeout_seconds=args.timeout_seconds,
        progress_log=args.progress_log,
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
    return _exit_code_for_status(result)


def _print_readiness_report(report: Mapping[str, Any]) -> None:
    print(f"Editor smoke readiness: {report['status']}")
    print(f"live_editor_execution_allowed: {str(report.get('live_editor_execution_allowed', False)).lower()}")
    print(f"live_editor_execution: {str(report.get('live_editor_execution', False)).lower()}")
    print(f"live_publication: {str(report.get('live_publication', False)).lower()}")
    print(f"release_packaging: {str(report.get('release_packaging', False)).lower()}")
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


if __name__ == "__main__":
    raise SystemExit(main())
