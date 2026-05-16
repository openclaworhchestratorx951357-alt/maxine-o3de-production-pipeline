#!/usr/bin/env python3
"""Fixture-backed and integration-gated O3DE Editor Python smoke bridge."""

from __future__ import annotations

import argparse
import json
import os
import platform as platform_module
import re
import shutil
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
    "approved-animation-component-wiring-generation": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_approved_animation_component_wiring_generation_smoke.py",
    "approved-prefab-save-update-automation-surface": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_approved_prefab_save_update_automation_surface_smoke.py",
    "approved-prefab-save-update-bridge": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_approved_prefab_save_update_bridge_smoke.py",
    "approved-prefab-save-update-bridge-host": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_approved_prefab_save_update_bridge_host_smoke.py",
    "approved-prefab-save-update-route": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_approved_prefab_save_update_route_smoke.py",
    "approved-source-prefab-actor-simple-motion-wiring": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_approved_source_prefab_actor_simple_motion_wiring_smoke.py",
    "approved-source-prefab-propagation-apply-step": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_approved_source_prefab_propagation_apply_step_smoke.py",
    "approved-source-prefab-parent-link-override-apply-route": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_approved_source_prefab_parent_link_override_apply_route_smoke.py",
    "approved-source-prefab-override-path-generation-template-update": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_approved_source_prefab_override_path_generation_template_update_smoke.py",
    "editor-viewport-visual-material-evidence": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_viewport_visual_material_evidence_smoke.py",
    "non-null-editor-render-capture-envelope": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_non_null_render_capture_envelope_smoke.py",
    "non-null-editor-visual-runner-readiness": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_non_null_visual_runner_readiness_smoke.py",
    "non-null-editor-desktop-rhi-readiness": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_non_null_desktop_rhi_readiness_smoke.py",
    "live-non-null-editor-launch": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_live_non_null_launch_smoke.py",
    "editor-screenshot-capture-artifact-readiness": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_screenshot_capture_artifact_readiness_smoke.py",
    "editor-active-viewport-temp-scene-readiness": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_active_viewport_temp_scene_readiness_smoke.py",
    "editor-safe-temp-visual-scene-display-context": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_safe_temp_visual_scene_display_context_smoke.py",
    "editor-nonblocking-viewport-swapchain-readiness": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_nonblocking_viewport_swapchain_readiness_smoke.py",
    "editor-ap-negotiation-viewport-materialization-readiness": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_ap_negotiation_viewport_materialization_readiness_smoke.py",
    "asset-processor-project-build-alignment-repair": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_asset_processor_alignment_repair_smoke.py",
    "operator-run-ap-alignment-remediation-verification": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_operator_ap_alignment_remediation_verification_smoke.py",
    "focused-editor-viewport-activation-default-viewport-materialization": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_focused_viewport_materialization_smoke.py",
    "editor-main-window-activation-materialization-deep-dive": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_main_window_activation_materialization_smoke.py",
    "alternate-editor-window-discovery-visible-shell-materialization": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_alternate_window_shell_materialization_smoke.py",
    "editor-layout-bootstrap-window-lifecycle-deep-dive": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_layout_bootstrap_window_lifecycle_smoke.py",
    "editor-bootstrap-wait-shell-ready-synchronization": REPO_ROOT
    / "tools"
    / "o3de"
    / "editor_python"
    / "editor_bootstrap_wait_shell_ready_smoke.py",
    "full": EDITOR_SCRIPT,
}
DIAGNOSTIC_MODES = tuple(DIAGNOSTIC_EDITOR_SCRIPTS)
SOURCE_ONLY_EDITOR_DIAGNOSTIC_MODES = {
    "non-null-editor-visual-runner-readiness",
    "non-null-editor-desktop-rhi-readiness",
}
NON_NULL_RENDER_CAPTURE_RHIS = {"dx12", "vulkan"}
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

    diagnostic_mode = str(report.get("diagnostic_mode", "")).strip()
    source_only_diagnostic = diagnostic_mode in SOURCE_ONLY_EDITOR_DIAGNOSTIC_MODES
    blocked_live_non_null_launch_diagnostic = (
        diagnostic_mode == "live-non-null-editor-launch"
        and report.get("live_editor_execution") is not True
        and str(report.get("live_non_null_editor_launch_blocker", "")).strip()
    )
    blocked_editor_screenshot_capture_diagnostic = (
        diagnostic_mode == "editor-screenshot-capture-artifact-readiness"
        and report.get("live_editor_execution") is not True
        and str(report.get("editor_screenshot_capture_artifact_readiness_blocker", "")).strip()
    )
    blocked_nonblocking_viewport_swapchain_diagnostic = (
        diagnostic_mode == "editor-nonblocking-viewport-swapchain-readiness"
        and report.get("live_editor_execution") is not True
        and str(report.get("nonblocking_viewport_swapchain_probe_blocker", "")).strip()
    )
    blocked_asset_processor_alignment_diagnostic = (
        diagnostic_mode
        in {
            "asset-processor-project-build-alignment-repair",
            "operator-run-ap-alignment-remediation-verification",
            "focused-editor-viewport-activation-default-viewport-materialization",
        }
        and report.get("live_editor_execution") is not True
        and bool(_asset_processor_alignment_preflight_blocker(report))
    )
    if report.get("live_editor_execution") is True and str(report.get("mode", "")) in {"fixture", "unavailable"}:
        result.add_error("MXN_RUNTIME_SMOKE_FAIL", "Fixture/skipped Editor smoke reports cannot claim live Editor execution.")
    if str(report.get("mode", "")) == "local_editor_python":
        if (
            str(report.get("status", "")) == "pass"
            and report.get("live_editor_execution") is not True
            and not source_only_diagnostic
                and not blocked_live_non_null_launch_diagnostic
                and not blocked_editor_screenshot_capture_diagnostic
                and not blocked_nonblocking_viewport_swapchain_diagnostic
                and not blocked_asset_processor_alignment_diagnostic
            ):
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
        if diagnostic_mode == "approved-animation-component-wiring-generation":
            _validate_approved_runtime_animation_component_wiring_editor_generation(report, result)
        if diagnostic_mode == "approved-prefab-save-update-automation-surface":
            _validate_approved_prefab_save_update_automation_surface(report, result)
        if diagnostic_mode == "approved-prefab-save-update-bridge":
            _validate_approved_prefab_save_update_bridge(report, result)
        if diagnostic_mode == "approved-prefab-save-update-bridge-host":
            _validate_approved_prefab_save_update_bridge_host(report, result)
        if diagnostic_mode == "approved-prefab-save-update-route":
            _validate_approved_prefab_save_update_route(report, result)
        if diagnostic_mode == "approved-source-prefab-actor-simple-motion-wiring":
            _validate_approved_source_prefab_actor_simple_motion_wiring(report, result)
        if diagnostic_mode == "approved-source-prefab-propagation-apply-step":
            _validate_approved_source_prefab_propagation_apply_step(report, result)
        if diagnostic_mode == "approved-source-prefab-parent-link-override-apply-route":
            _validate_approved_source_prefab_parent_link_override_apply_route(report, result)
        if diagnostic_mode == "approved-source-prefab-override-path-generation-template-update":
            _validate_approved_source_prefab_override_path_generation_template_update(report, result)
        if diagnostic_mode == "editor-viewport-visual-material-evidence":
            _validate_editor_viewport_visual_material_evidence(report, result)
        if diagnostic_mode == "non-null-editor-render-capture-envelope":
            _validate_non_null_editor_render_capture_envelope(report, result)
        if diagnostic_mode == "non-null-editor-visual-runner-readiness":
            _validate_non_null_editor_visual_runner_readiness(report, result)
        if diagnostic_mode == "non-null-editor-desktop-rhi-readiness":
            _validate_non_null_editor_desktop_rhi_readiness(report, result)
        if diagnostic_mode == "live-non-null-editor-launch":
            _validate_live_non_null_editor_launch(report, result)
        if diagnostic_mode == "editor-screenshot-capture-artifact-readiness":
            _validate_editor_screenshot_capture_artifact_readiness(report, result)
        if diagnostic_mode == "editor-active-viewport-temp-scene-readiness":
            _validate_editor_active_viewport_temp_scene_readiness(report, result)
        if diagnostic_mode == "editor-safe-temp-visual-scene-display-context":
            _validate_editor_safe_temp_visual_scene_display_context(report, result)
        if diagnostic_mode == "editor-nonblocking-viewport-swapchain-readiness":
            _validate_editor_nonblocking_viewport_swapchain_readiness(report, result)
        if diagnostic_mode == "editor-ap-negotiation-viewport-materialization-readiness":
            _validate_editor_ap_negotiation_viewport_materialization_readiness(report, result)
        if diagnostic_mode == "asset-processor-project-build-alignment-repair":
            _validate_asset_processor_project_build_alignment_repair(report, result)
        if diagnostic_mode == "operator-run-ap-alignment-remediation-verification":
            _validate_operator_ap_alignment_remediation_verification(report, result)
        if diagnostic_mode == "focused-editor-viewport-activation-default-viewport-materialization":
            _validate_focused_editor_viewport_materialization(report, result)
        if diagnostic_mode == "editor-main-window-activation-materialization-deep-dive":
            _validate_editor_main_window_activation_deep_dive(report, result)
        if diagnostic_mode == "alternate-editor-window-discovery-visible-shell-materialization":
            _validate_alternate_editor_window_discovery_visible_shell(report, result)
        if diagnostic_mode == "editor-layout-bootstrap-window-lifecycle-deep-dive":
            _validate_editor_layout_bootstrap_window_lifecycle(report, result)
        if diagnostic_mode == "editor-bootstrap-wait-shell-ready-synchronization":
            _validate_editor_bootstrap_wait_shell_ready_synchronization(report, result)
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


def _validate_approved_runtime_animation_component_wiring_editor_generation(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("approved_runtime_animation_component_wiring_editor_generation_attempted") is True
    completed = report.get("approved_runtime_animation_component_wiring_editor_generation_completed") is True
    verified = report.get("approved_runtime_animation_component_wiring_editor_generation_verified") is True
    blocker = str(report.get("approved_runtime_animation_component_wiring_editor_generation_blocker", "")).strip()

    if str(report.get("status", "")).strip() == "pass" and (not attempted or not completed):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved Editor-generated animation component wiring diagnostic cannot pass without attempted/completed evidence.",
        )
    if report.get("approved_runtime_animation_component_wiring_hand_authored_unknown_json_used") is not False:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved animation component wiring must preserve hand_authored_unknown_json_used=false.",
        )

    if verified:
        required_true = {
            "approved_runtime_animation_component_wiring_source_prefab_modified": "source prefab modification",
            "approved_runtime_animation_component_wiring_editor_generated_update_used": "Editor-generated update",
            "approved_runtime_animation_component_wiring_actor_component_added": "Actor component add",
            "approved_runtime_animation_component_wiring_simple_motion_component_added": "Simple Motion component add",
            "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": "Actor asset assignment",
            "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": "Motion asset assignment",
            "approved_runtime_animation_component_wiring_property_readback_verified": "property readback",
            "approved_runtime_animation_component_wiring_prefab_save_verified": "prefab save",
            "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": "spawnable regeneration/found evidence",
            "runtime_character_animation_component_wiring_claimed": "runtime component wiring claim",
            "runtime_character_animation_component_wiring_verified": "runtime component wiring verification",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved Editor-generated animation component wiring verified=true requires {label}.",
                )
        if blocker:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved Editor-generated animation component wiring verified=true cannot also report a blocker.",
            )
    elif str(report.get("status", "")).strip() == "pass" and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved Editor-generated animation component wiring diagnostic pass without verification requires a typed blocker.",
        )

    if blocker == "blocked_by_editor_generated_prefab_update_save_semantics":
        contradictory_true = {
            "approved_runtime_animation_component_wiring_source_prefab_modified": "source prefab modification",
            "approved_runtime_animation_component_wiring_editor_generated_update_used": "Editor-generated source update",
            "approved_runtime_animation_component_wiring_prefab_save_verified": "prefab save",
            "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": "spawnable regeneration",
        }
        for field, label in contradictory_true.items():
            if report.get(field) is True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Save-semantics blocker cannot report {label} as verified.",
                )

    false_until_playback = (
        "runtime_character_animation_claimed",
        "runtime_character_animation_verified",
        "runtime_character_proof_claimed",
        "runtime_character_proof_verified",
    )
    for field in false_until_playback:
        if report.get(field) is True and report.get("runtime_character_animation_playback_observed") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"{field}=true requires observed runtime animation playback evidence.",
            )


def _validate_approved_prefab_save_update_automation_surface(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("approved_prefab_save_update_automation_surface_diagnostic_attempted") is True
    completed = report.get("approved_prefab_save_update_automation_surface_diagnostic_completed") is True
    found = report.get("approved_prefab_save_update_automation_surface_found") is True
    verified = report.get("approved_prefab_save_update_automation_surface_verified") is True
    blocker = str(report.get("approved_prefab_save_update_automation_surface_blocker", "")).strip()
    source_status = str(report.get("approved_prefab_save_update_source_validation_status", "")).strip()
    source_verified = report.get("approved_prefab_save_update_source_validation_verified") is True

    if str(report.get("status", "")).strip() == "pass" and (not attempted or not completed):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update automation diagnostic cannot pass without attempted/completed evidence.",
        )
    if source_status != "pass" or not source_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update automation diagnostic requires positive source validation.",
        )

    if verified:
        required_true = {
            "approved_prefab_save_update_automation_surface_found": "save/update automation surface found",
            "approved_prefab_save_update_rejected_defaultlevel_path": "defaultlevel path rejection",
            "approved_prefab_save_update_rejected_production_level_path": "production-level path rejection",
            "approved_prefab_save_update_scratch_save_attempted": "scratch save attempt",
            "approved_prefab_save_update_scratch_save_verified": "scratch save verification",
            "approved_prefab_save_update_scratch_cleanup_verified": "scratch cleanup verification",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved prefab save/update automation verified=true requires {label}.",
                )
        if not (
            report.get("approved_prefab_save_update_behavior_context_exposed") is True
            or report.get("approved_prefab_save_update_bridge_verified") is True
        ):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved prefab save/update automation verified=true requires an exposed BehaviorContext route or verified bridge.",
            )
        if blocker:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved prefab save/update automation verified=true cannot also report a blocker.",
            )
    elif str(report.get("status", "")).strip() == "pass" and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update automation diagnostic pass without verification requires a typed blocker.",
        )

    if blocker == "blocked_by_prefab_save_interface_not_available_to_automation":
        if found:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Prefab save interface unavailable blocker cannot also report surface_found=true.",
            )
        contradictory_true = {
            "approved_prefab_save_update_behavior_context_exposed": "BehaviorContext exposure",
            "approved_prefab_save_update_bridge_added": "bridge addition",
            "approved_prefab_save_update_bridge_verified": "bridge verification",
            "approved_prefab_save_update_scratch_save_attempted": "scratch save attempt",
            "approved_prefab_save_update_scratch_save_verified": "scratch save verification",
            "approved_runtime_animation_component_wiring_source_prefab_modified": "approved source prefab modification",
            "approved_runtime_animation_component_wiring_prefab_save_verified": "approved source prefab save",
            "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": "spawnable regeneration/found evidence",
        }
        for field, label in contradictory_true.items():
            if report.get(field) is True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Prefab save interface unavailable blocker cannot report {label}.",
                )

    false_until_runtime_component_proof = (
        "runtime_character_animation_component_wiring_claimed",
        "runtime_character_animation_component_wiring_verified",
        "runtime_character_animation_claimed",
        "runtime_character_animation_verified",
        "runtime_character_proof_claimed",
        "runtime_character_proof_verified",
    )
    for field in false_until_runtime_component_proof:
        if report.get(field) is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"{field}=true is not supported by prefab save/update automation surface evidence alone.",
            )


def _validate_approved_prefab_save_update_bridge(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("approved_prefab_save_update_bridge_diagnostic_attempted") is True
    completed = report.get("approved_prefab_save_update_bridge_diagnostic_completed") is True
    verified = report.get("approved_prefab_save_update_bridge_verified") is True
    blocker = str(report.get("approved_prefab_save_update_bridge_blocker", "")).strip()
    source_status = str(report.get("approved_prefab_save_update_bridge_source_validation_status", "")).strip()
    source_verified = report.get("approved_prefab_save_update_bridge_source_validation_verified") is True

    if str(report.get("status", "")).strip() == "pass" and (not attempted or not completed):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update bridge diagnostic cannot pass without attempted/completed evidence.",
        )
    if source_status != "pass" or not source_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update bridge diagnostic requires positive source validation.",
        )

    if verified:
        required_true = {
            "approved_prefab_save_update_bridge_added": "bridge addition",
            "approved_prefab_save_update_bridge_behavior_context_reflected": "BehaviorContext reflection",
            "approved_prefab_save_update_bridge_callable_from_editor_python": "Editor Python callable bridge",
            "approved_prefab_save_update_rejected_defaultlevel_path": "defaultlevel path rejection",
            "approved_prefab_save_update_rejected_production_level_path": "production-level path rejection",
            "approved_prefab_save_update_rejected_generated_product_path": "generated product path rejection",
            "approved_prefab_save_update_scratch_save_attempted": "scratch save attempt",
            "approved_prefab_save_update_scratch_save_verified": "scratch save verification",
            "approved_prefab_save_update_scratch_reload_or_parse_verified": "scratch reload/parse verification",
            "approved_prefab_save_update_scratch_cleanup_verified": "scratch cleanup verification",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved prefab save/update bridge verified=true requires {label}.",
                )
        if report.get("approved_prefab_save_update_generated_products_committed") is not False:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved prefab save/update bridge verified=true requires generated_products_committed=false.",
            )
        if blocker:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved prefab save/update bridge verified=true cannot also report a blocker.",
            )
    elif str(report.get("status", "")).strip() == "pass" and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update bridge diagnostic pass without verification requires a typed blocker.",
        )

    if blocker == "blocked_by_prefab_save_bridge_requires_editor_gem_registration":
        contradictory_true = {
            "approved_prefab_save_update_bridge_added": "bridge addition",
            "approved_prefab_save_update_bridge_verified": "bridge verification",
            "approved_prefab_save_update_bridge_behavior_context_reflected": "BehaviorContext reflection",
            "approved_prefab_save_update_bridge_callable_from_editor_python": "Editor Python callable bridge",
            "approved_prefab_save_update_scratch_save_attempted": "scratch save attempt",
            "approved_prefab_save_update_scratch_save_verified": "scratch save verification",
            "approved_runtime_animation_component_wiring_source_prefab_modified": "approved source prefab modification",
            "approved_runtime_animation_component_wiring_prefab_save_verified": "approved source prefab save",
            "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": "spawnable regeneration/found evidence",
        }
        for field, label in contradictory_true.items():
            if report.get(field) is True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Editor Gem registration blocker cannot report {label}.",
                )

    false_until_runtime_component_proof = (
        "runtime_character_animation_component_wiring_claimed",
        "runtime_character_animation_component_wiring_verified",
        "runtime_character_animation_claimed",
        "runtime_character_animation_verified",
        "runtime_character_proof_claimed",
        "runtime_character_proof_verified",
    )
    for field in false_until_runtime_component_proof:
        if report.get(field) is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"{field}=true is not supported by prefab save/update bridge evidence alone.",
            )


def _validate_approved_prefab_save_update_bridge_host(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("approved_prefab_save_update_bridge_host_diagnostic_attempted") is True
    completed = report.get("approved_prefab_save_update_bridge_host_diagnostic_completed") is True
    source_status = str(report.get("approved_prefab_save_update_bridge_host_source_validation_status", "")).strip()
    source_verified = report.get("approved_prefab_save_update_bridge_host_source_validation_verified") is True
    blocker = str(report.get("approved_prefab_save_update_bridge_host_blocker", "")).strip()
    host_callable = report.get("approved_prefab_save_update_bridge_host_callable_from_editor_python") is True

    if str(report.get("status", "")).strip() == "pass" and (not attempted or not completed):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update bridge-host diagnostic cannot pass without attempted/completed evidence.",
        )
    if source_status != "pass" or not source_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update bridge-host diagnostic requires positive source validation.",
        )

    if report.get("approved_prefab_save_update_bridge_host_added") is True:
        for field, label in (
            ("approved_prefab_save_update_bridge_host_registered", "bridge-host registration"),
            ("approved_prefab_save_update_bridge_host_target_name", "Editor/Tools target name"),
            ("approved_prefab_save_update_bridge_host_module_name", "Editor module name"),
            (
                "approved_prefab_save_update_bridge_host_aztoolsframework_dependency_present",
                "AzToolsFramework dependency",
            ),
            (
                "approved_prefab_save_update_bridge_host_behavior_context_reflected",
                "BehaviorContext reflection",
            ),
            ("approved_prefab_save_update_bridge_host_runtime_excluded", "runtime exclusion"),
        ):
            value = report.get(field)
            if isinstance(value, str):
                if not value.strip():
                    result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Bridge-host addition requires {label}.")
            elif value is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Bridge-host addition requires {label}.")

    if host_callable:
        required_true = {
            "approved_prefab_save_update_bridge_host_added": "bridge-host source addition",
            "approved_prefab_save_update_bridge_host_registered": "bridge-host registration",
            "approved_prefab_save_update_bridge_host_build_verified": "bridge-host build/load verification",
            "approved_prefab_save_update_bridge_host_aztoolsframework_dependency_present": "AzToolsFramework dependency",
            "approved_prefab_save_update_bridge_host_behavior_context_reflected": "BehaviorContext reflection",
            "approved_prefab_save_update_bridge_host_runtime_excluded": "runtime exclusion",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Bridge-host callable=true requires {label}.",
                )
        if blocker:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Bridge-host callable=true cannot also report a bridge-host blocker.",
            )
    elif str(report.get("status", "")).strip() == "pass" and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update bridge-host diagnostic pass without callability requires a typed blocker.",
        )

    if blocker == "blocked_by_editor_bridge_host_not_loaded_in_editor" and host_callable:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Bridge-host not-loaded blocker cannot report Editor Python callability.",
        )
    if report.get("approved_prefab_save_update_bridge_verified") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Bridge-host diagnostic alone cannot claim prefab save/update bridge verification.",
        )
    if report.get("approved_prefab_save_update_scratch_save_verified") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Bridge-host diagnostic alone cannot claim scratch save/update verification.",
        )
    if report.get("approved_runtime_animation_component_wiring_source_prefab_modified") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Bridge-host diagnostic must not mutate the approved runtime animation source prefab.",
        )

    false_until_runtime_component_proof = (
        "runtime_character_animation_component_wiring_claimed",
        "runtime_character_animation_component_wiring_verified",
        "runtime_character_animation_claimed",
        "runtime_character_animation_verified",
        "runtime_character_proof_claimed",
        "runtime_character_proof_verified",
    )
    for field in false_until_runtime_component_proof:
        if report.get(field) is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"{field}=true is not supported by prefab save/update bridge-host evidence alone.",
            )


def _validate_approved_prefab_save_update_route(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("approved_prefab_save_update_route_diagnostic_attempted") is True
    completed = report.get("approved_prefab_save_update_route_diagnostic_completed") is True
    source_status = str(report.get("approved_prefab_save_update_route_source_validation_status", "")).strip()
    source_verified = report.get("approved_prefab_save_update_route_source_validation_verified") is True
    route_callable = report.get("approved_prefab_save_update_route_callable_from_editor_python") is True
    bridge_verified = report.get("approved_prefab_save_update_bridge_verified") is True
    scratch_saved = report.get("approved_prefab_save_update_scratch_save_verified") is True
    scratch_parsed = report.get("approved_prefab_save_update_scratch_reload_or_parse_verified") is True
    scratch_cleaned = report.get("approved_prefab_save_update_scratch_cleanup_verified") is True
    blocker = str(report.get("approved_prefab_save_update_route_blocker", "")).strip()

    if str(report.get("status", "")).strip() == "pass" and (not attempted or not completed):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update route diagnostic cannot pass without attempted/completed evidence.",
        )
    if source_status != "pass" or not source_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved prefab save/update route diagnostic requires positive repo-owned route source validation.",
        )
    if bridge_verified:
        required_true = {
            "approved_prefab_save_update_route_added": "route source addition",
            "approved_prefab_save_update_route_behavior_context_reflected": "route BehaviorContext reflection",
            "approved_prefab_save_update_route_callable_from_editor_python": "route Editor Python callability",
            "approved_prefab_save_update_bridge_host_callable_from_editor_python": "bridge-host callability",
            "approved_prefab_save_update_scratch_save_attempted": "scratch save attempt",
            "approved_prefab_save_update_scratch_save_verified": "scratch save verification",
            "approved_prefab_save_update_scratch_reload_or_parse_verified": "scratch parse/reload verification",
            "approved_prefab_save_update_scratch_cleanup_verified": "scratch cleanup verification",
            "approved_prefab_save_update_rejected_defaultlevel_path": "defaultlevel rejection",
            "approved_prefab_save_update_rejected_production_level_path": "production-level rejection",
            "approved_prefab_save_update_rejected_generated_product_path": "generated-product rejection",
            "approved_prefab_save_update_rejected_unapproved_absolute_path": "unapproved absolute path rejection",
            "approved_prefab_save_update_rejected_path_traversal": "path traversal rejection",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Prefab save/update bridge verified=true requires {label}.")
        if blocker:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Verified prefab save/update route cannot also report a route blocker.")
        for hash_field in ("approved_prefab_save_update_after_hash",):
            if not str(report.get(hash_field, "")).strip():
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Verified prefab save/update route requires {hash_field}.")
    elif str(report.get("status", "")).strip() == "pass" and route_callable and scratch_saved and scratch_parsed and scratch_cleaned:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Route callability and scratch save evidence require approved_prefab_save_update_bridge_verified=true.",
        )

    if scratch_saved and not scratch_parsed:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Scratch save proof requires prefab JSON parse/reload proof.")
    if scratch_saved and not scratch_cleaned:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Scratch save proof requires cleanup verification.")
    if report.get("approved_runtime_animation_component_wiring_source_prefab_modified") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Route scratch proof must not mutate the approved runtime animation source prefab.",
        )

    false_until_runtime_component_proof = (
        "runtime_character_animation_component_wiring_claimed",
        "runtime_character_animation_component_wiring_verified",
        "runtime_character_animation_claimed",
        "runtime_character_animation_verified",
        "runtime_character_proof_claimed",
        "runtime_character_proof_verified",
    )
    for field in false_until_runtime_component_proof:
        if report.get(field) is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"{field}=true is not supported by prefab save/update route scratch proof alone.",
            )


def _validate_approved_source_prefab_actor_simple_motion_wiring(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("approved_source_prefab_actor_simple_motion_wiring_attempted") is True
    completed = report.get("approved_source_prefab_actor_simple_motion_wiring_completed") is True
    verified = report.get("approved_source_prefab_actor_simple_motion_wiring_verified") is True
    blocker = str(report.get("approved_source_prefab_actor_simple_motion_wiring_blocker", "")).strip()
    source_status = str(
        report.get("approved_source_prefab_actor_simple_motion_wiring_source_validation_status", "")
    ).strip()
    source_verified = report.get("approved_source_prefab_actor_simple_motion_wiring_source_validation_verified") is True

    if str(report.get("status", "")).strip() == "pass" and (not attempted or not completed):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab Actor + Simple Motion wiring diagnostic cannot pass without attempted/completed evidence.",
        )
    if source_status != "pass" or not source_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab Actor + Simple Motion wiring requires positive source validation.",
        )
    if report.get("approved_source_prefab_hand_authored_unknown_json_used") is not False:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab wiring must preserve hand_authored_unknown_json_used=false.",
        )
    if report.get("approved_source_prefab_defaultlevel_mutation") is not False:
        result.add_error(MXN_PATH_UNSAFE, "Approved source-prefab wiring must not mutate defaultlevel content.")
    if report.get("approved_source_prefab_production_level_mutation") is not False:
        result.add_error(MXN_PATH_UNSAFE, "Approved source-prefab wiring must not mutate production-level content.")

    if verified:
        required_true = {
            "approved_source_prefab_modified": "approved source-prefab modification",
            "approved_source_prefab_persisted_wiring_markers_verified": "persisted ActorAsset/MotionAsset prefab markers",
            "approved_source_prefab_save_verified": "approved source-prefab save",
            "approved_source_prefab_actor_component_added": "Actor component add",
            "approved_source_prefab_simple_motion_component_added": "Simple Motion component add",
            "approved_source_prefab_actor_asset_assignment_verified": "Actor asset assignment",
            "approved_source_prefab_motion_asset_assignment_verified": "Motion asset assignment",
            "approved_source_prefab_property_readback_verified": "property readback",
            "approved_runtime_animation_component_wiring_source_prefab_modified": "preserved runtime wiring source-prefab modified flag",
            "approved_runtime_animation_component_wiring_editor_generated_update_used": "Editor-generated update flag",
            "approved_runtime_animation_component_wiring_prefab_save_verified": "runtime wiring prefab save flag",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved source-prefab wiring verified=true requires {label}.",
                )
        if not (
            report.get("approved_source_prefab_entity_changes_committed") is True
            or report.get("approved_source_prefab_component_overrides_applied") is True
        ):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab wiring verified=true requires a source-backed entity change commit or component override apply route.",
            )
        if blocker:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab wiring verified=true cannot also report a blocker.",
            )
        for hash_field in (
            "approved_source_prefab_before_hash",
            "approved_source_prefab_after_hash",
            "approved_source_prefab_project_after_hash",
        ):
            if not str(report.get(hash_field, "")).strip():
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Approved source-prefab wiring requires {hash_field}.")
        if not str(report.get("approved_source_prefab_actor_asset_id", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Approved source-prefab wiring requires Actor asset id evidence.")
        if not str(report.get("approved_source_prefab_motion_asset_id", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Approved source-prefab wiring requires Motion asset id evidence.")
    elif str(report.get("status", "")).strip() == "pass" and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab wiring diagnostic pass without verification requires a typed blocker.",
        )

    false_until_runtime = (
        "runtime_character_animation_component_wiring_claimed",
        "runtime_character_animation_component_wiring_verified",
        "runtime_character_animation_claimed",
        "runtime_character_animation_verified",
        "runtime_character_proof_claimed",
        "runtime_character_proof_verified",
    )
    for field in false_until_runtime:
        if report.get(field) is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"{field}=true must come from APB/runtime diagnostics, not the Editor source-prefab wiring report alone.",
            )


def _validate_approved_source_prefab_propagation_apply_step(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("approved_source_prefab_propagation_apply_step_attempted") is True
    completed = report.get("approved_source_prefab_propagation_apply_step_completed") is True
    verified = report.get("approved_source_prefab_propagation_apply_step_verified") is True
    blocker = str(report.get("approved_source_prefab_propagation_apply_step_blocker", "")).strip()
    source_status = str(
        report.get("approved_source_prefab_propagation_apply_step_source_validation_status", "")
    ).strip()
    source_verified = report.get("approved_source_prefab_propagation_apply_step_source_validation_verified") is True

    if str(report.get("status", "")).strip() == "pass" and (not attempted or not completed):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab propagation/apply diagnostic cannot pass without attempted/completed evidence.",
        )
    if source_status != "pass" or not source_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab propagation/apply diagnostic requires positive repo-owned source validation.",
        )
    if report.get("approved_source_prefab_hand_authored_unknown_json_used") is not False:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab propagation/apply diagnostic must preserve hand_authored_unknown_json_used=false.",
        )
    if report.get("approved_source_prefab_defaultlevel_mutation") is not False:
        result.add_error(MXN_PATH_UNSAFE, "Approved source-prefab propagation/apply diagnostic must not mutate defaultlevel content.")
    if report.get("approved_source_prefab_production_level_mutation") is not False:
        result.add_error(
            MXN_PATH_UNSAFE,
            "Approved source-prefab propagation/apply diagnostic must not mutate production-level content.",
        )

    if verified:
        required_true = {
            "approved_source_prefab_modified": "approved source-prefab modification",
            "approved_source_prefab_template_dom_updated": "source-template DOM update",
            "approved_source_prefab_save_verified": "approved source-prefab save",
            "approved_source_prefab_persisted_actor_asset_marker_verified": "persisted ActorAsset marker",
            "approved_source_prefab_persisted_motion_asset_marker_verified": "persisted MotionAsset marker",
            "approved_source_prefab_persisted_wiring_markers_verified": "persisted wiring marker pair",
            "approved_source_prefab_actor_component_added": "Actor component add",
            "approved_source_prefab_simple_motion_component_added": "Simple Motion component add",
            "approved_source_prefab_actor_asset_assignment_verified": "Actor asset assignment",
            "approved_source_prefab_motion_asset_assignment_verified": "Motion asset assignment",
            "approved_source_prefab_property_readback_verified": "property readback",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved source-prefab propagation/apply verified=true requires {label}.",
                )
        if not (
            report.get("approved_source_prefab_entity_changes_committed") is True
            or report.get("approved_source_prefab_component_overrides_applied") is True
        ):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab propagation/apply verified=true requires a source-backed commit/apply route.",
            )
        if blocker:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab propagation/apply verified=true cannot also report a blocker.",
            )
        for hash_field in ("approved_source_prefab_before_hash", "approved_source_prefab_after_hash"):
            if not str(report.get(hash_field, "")).strip():
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved source-prefab propagation/apply diagnostic requires {hash_field}.",
                )
    elif str(report.get("status", "")).strip() == "pass" and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab propagation/apply diagnostic pass without verification requires a typed blocker.",
        )

    false_until_downstream_runtime = (
        "approved_spawnable_regenerated_or_found",
        "runtime_character_animation_component_wiring_claimed",
        "runtime_character_animation_component_wiring_verified",
        "runtime_character_animation_claimed",
        "runtime_character_animation_verified",
        "runtime_character_proof_claimed",
        "runtime_character_proof_verified",
    )
    for field in false_until_downstream_runtime:
        if report.get(field) is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"{field}=true must come from APB/runtime diagnostics, not source-template propagation/apply source validation alone.",
            )


def _validate_approved_source_prefab_parent_link_override_apply_route(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("approved_source_prefab_parent_link_override_apply_route_attempted") is True
    completed = report.get("approved_source_prefab_parent_link_override_apply_route_completed") is True
    verified = report.get("approved_source_prefab_parent_link_override_apply_route_verified") is True
    blocker = str(report.get("approved_source_prefab_parent_link_override_apply_route_blocker", "")).strip()
    source_status = str(
        report.get("approved_source_prefab_parent_link_override_apply_source_validation_status", "")
    ).strip()
    source_verified = report.get("approved_source_prefab_parent_link_override_apply_source_validation_verified") is True

    if str(report.get("status", "")).strip() == "pass" and (not attempted or not completed):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab parent-link override apply route cannot pass without attempted/completed evidence.",
        )
    if source_status != "pass" or not source_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab parent-link override apply route requires positive repo-owned source validation.",
        )
    if report.get("approved_source_prefab_hand_authored_unknown_json_used") is not False:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab parent-link override apply route must preserve hand_authored_unknown_json_used=false.",
        )
    if report.get("approved_source_prefab_defaultlevel_mutation") is not False:
        result.add_error(MXN_PATH_UNSAFE, "Approved source-prefab parent-link override apply route must not mutate defaultlevel content.")
    if report.get("approved_source_prefab_production_level_mutation") is not False:
        result.add_error(
            MXN_PATH_UNSAFE,
            "Approved source-prefab parent-link override apply route must not mutate production-level content.",
        )

    if verified:
        required_true = {
            "approved_source_prefab_entity_ownership_checked": "approved prefab entity ownership check",
            "approved_source_prefab_entity_ownership_verified": "approved prefab entity ownership verification",
            "approved_source_prefab_entity_owning_prefab_matches_requested_path": "approved prefab entity owning path match",
            "approved_source_prefab_component_ownership_checked": "approved prefab component ownership check",
            "approved_source_prefab_component_ownership_verified": "approved prefab component ownership verification",
            "approved_source_prefab_parent_focus_context_required": "parent focus requirement",
            "approved_source_prefab_parent_focus_context_available": "parent focus availability",
            "approved_source_prefab_parent_focus_context_applied": "parent focus application",
            "approved_source_prefab_parent_focus_context_restored": "parent focus restoration",
            "approved_source_prefab_link_context_required": "link context requirement",
            "approved_source_prefab_link_context_available": "link context availability",
            "approved_source_prefab_component_override_paths_detected": "component override path detection",
            "approved_source_prefab_component_overrides_detected": "component override detection",
            "approved_source_prefab_component_overrides_applied": "component override application",
            "approved_source_prefab_push_overrides_to_prefab_attempted": "PushOverridesToPrefab attempt",
            "approved_source_prefab_push_overrides_to_prefab_verified": "PushOverridesToPrefab verification",
            "approved_source_prefab_template_dom_updated": "source-template DOM update",
            "approved_source_prefab_modified": "approved source-prefab modification",
            "approved_source_prefab_changed_this_run": "fresh source-prefab hash change",
            "approved_source_prefab_marker_presence_verified": "ActorAsset/MotionAsset marker presence",
            "approved_source_prefab_marker_persistence_verified_this_run": "fresh ActorAsset/MotionAsset marker persistence",
            "approved_source_prefab_save_verified": "approved source-prefab save",
            "approved_source_prefab_actor_component_added": "Actor component add",
            "approved_source_prefab_simple_motion_component_added": "Simple Motion component add",
            "approved_source_prefab_actor_asset_assignment_verified": "Actor asset assignment",
            "approved_source_prefab_motion_asset_assignment_verified": "Motion asset assignment",
            "approved_source_prefab_property_readback_verified": "property readback",
            "approved_source_prefab_persisted_actor_asset_marker_verified": "persisted ActorAsset marker",
            "approved_source_prefab_persisted_motion_asset_marker_verified": "persisted MotionAsset marker",
            "approved_source_prefab_persisted_wiring_markers_verified": "persisted wiring marker pair",
            "approved_source_prefab_propagation_apply_step_verified": "propagation/apply step verification",
            "approved_source_prefab_actor_simple_motion_wiring_verified": "Actor + Simple Motion wiring verification",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved source-prefab parent-link override apply verified=true requires {label}.",
                )
        if blocker:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab parent-link override apply verified=true cannot also report a blocker.",
            )
        if str(report.get("approved_source_prefab_marker_persistence_blocker", "")).strip():
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab parent-link override apply verified=true cannot report a marker persistence blocker.",
            )
        before_hash = str(report.get("approved_source_prefab_before_hash", "")).strip()
        after_hash = str(report.get("approved_source_prefab_after_hash", "")).strip()
        if not before_hash or not after_hash or before_hash == after_hash:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab parent-link override apply verified=true requires changed before/after hashes.",
            )
        for asset_field in ("approved_source_prefab_actor_asset_id", "approved_source_prefab_motion_asset_id"):
            if not str(report.get(asset_field, "")).strip():
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved source-prefab parent-link override apply verified=true requires {asset_field}.",
                )
    elif str(report.get("status", "")).strip() == "pass" and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab parent-link override apply route pass without verification requires a typed blocker.",
        )

    false_until_downstream_runtime = (
        "approved_spawnable_regenerated_or_found",
        "runtime_character_animation_component_wiring_claimed",
        "runtime_character_animation_component_wiring_verified",
        "runtime_character_animation_claimed",
        "runtime_character_animation_verified",
        "runtime_character_proof_claimed",
        "runtime_character_proof_verified",
    )
    for field in false_until_downstream_runtime:
        if report.get(field) is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"{field}=true must come from APB/runtime diagnostics, not source-template parent-link override apply alone.",
            )


def _validate_approved_source_prefab_override_path_generation_template_update(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("approved_source_prefab_override_path_generation_template_update_attempted") is True
    completed = report.get("approved_source_prefab_override_path_generation_template_update_completed") is True
    verified = report.get("approved_source_prefab_override_path_generation_template_update_verified") is True
    blocker = str(report.get("approved_source_prefab_override_path_generation_template_update_blocker", "")).strip()
    source_status = str(
        report.get("approved_source_prefab_override_path_generation_template_update_source_validation_status", "")
    ).strip()
    source_verified = (
        report.get("approved_source_prefab_override_path_generation_template_update_source_validation_verified") is True
    )

    if str(report.get("status", "")).strip() == "pass" and (not attempted or not completed):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab override-path/template-update route cannot pass without attempted/completed evidence.",
        )
    if source_status != "pass" or not source_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab override-path/template-update route requires positive repo-owned source validation.",
        )
    if report.get("approved_source_prefab_hand_authored_unknown_json_used") is not False:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab override-path/template-update route must preserve hand_authored_unknown_json_used=false.",
        )
    if report.get("approved_source_prefab_defaultlevel_mutation") is not False:
        result.add_error(
            MXN_PATH_UNSAFE,
            "Approved source-prefab override-path/template-update route must not mutate defaultlevel content.",
        )
    if report.get("approved_source_prefab_production_level_mutation") is not False:
        result.add_error(
            MXN_PATH_UNSAFE,
            "Approved source-prefab override-path/template-update route must not mutate production-level content.",
        )

    if verified:
        required_true = {
            "approved_source_prefab_entity_ownership_checked": "approved prefab entity ownership check",
            "approved_source_prefab_entity_ownership_verified": "approved prefab entity ownership verification",
            "approved_source_prefab_entity_owning_prefab_matches_requested_path": "approved prefab entity owning path match",
            "approved_source_prefab_component_ownership_checked": "approved prefab component ownership check",
            "approved_source_prefab_component_ownership_verified": "approved prefab component ownership verification",
            "approved_source_prefab_template_dom_update_route_used": "source-backed template update route",
            "approved_source_prefab_template_dom_initial_entity_found": "initial source-template entity DOM",
            "approved_source_prefab_serialized_entity_dom_generated": "serialized live entity DOM",
            "approved_source_prefab_entity_patch_generated": "entity patch generation",
            "approved_source_prefab_patch_entity_in_template_attempted": "PatchEntityInTemplate attempt",
            "approved_source_prefab_patch_entity_in_template_verified": "PatchEntityInTemplate verification",
            "approved_source_prefab_push_overrides_to_template_attempted": "template patch attempt",
            "approved_source_prefab_push_overrides_to_template_verified": "template patch verification",
            "approved_source_prefab_template_dom_updated": "source-template DOM update",
            "approved_source_prefab_modified": "approved source-prefab modification",
            "approved_source_prefab_changed_this_run": "fresh source-prefab hash change",
            "approved_source_prefab_marker_presence_verified": "ActorAsset/MotionAsset marker presence",
            "approved_source_prefab_marker_persistence_verified_this_run": "fresh ActorAsset/MotionAsset marker persistence",
            "approved_source_prefab_save_verified": "approved source-prefab save",
            "approved_source_prefab_actor_component_added": "Actor component add",
            "approved_source_prefab_simple_motion_component_added": "Simple Motion component add",
            "approved_source_prefab_actor_asset_assignment_verified": "Actor asset assignment",
            "approved_source_prefab_motion_asset_assignment_verified": "Motion asset assignment",
            "approved_source_prefab_property_readback_verified": "property readback",
            "approved_source_prefab_persisted_actor_asset_marker_verified": "persisted ActorAsset marker",
            "approved_source_prefab_persisted_motion_asset_marker_verified": "persisted MotionAsset marker",
            "approved_source_prefab_persisted_wiring_markers_verified": "persisted wiring marker pair",
            "approved_source_prefab_template_update_route_rejection_probes_attempted": "template-update route rejection probes",
            "approved_source_prefab_template_update_route_rejection_probes_verified": "template-update route rejection probe verification",
            "approved_source_prefab_template_update_route_rejected_defaultlevel_path": "template-update defaultlevel rejection",
            "approved_source_prefab_template_update_route_rejected_production_level_path": "template-update production-level rejection",
            "approved_source_prefab_template_update_route_rejected_generated_product_path": "template-update generated-product rejection",
            "approved_source_prefab_template_update_route_rejected_cache_path": "template-update cache rejection",
            "approved_source_prefab_template_update_route_rejected_unapproved_absolute_path": "template-update unapproved absolute-path rejection",
            "approved_source_prefab_template_update_route_rejected_other_project_path": "template-update other-project rejection",
            "approved_source_prefab_template_update_route_rejected_path_traversal": "template-update traversal rejection",
            "approved_source_prefab_template_update_route_rejected_non_prefab_path": "template-update non-prefab rejection",
            "approved_source_prefab_template_update_route_rejected_wrong_entity_owner": "template-update wrong-entity ownership rejection",
            "approved_source_prefab_propagation_apply_step_verified": "propagation/apply step verification",
            "approved_source_prefab_actor_simple_motion_wiring_verified": "Actor + Simple Motion wiring verification",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved source-prefab override-path/template-update verified=true requires {label}.",
                )
        if int(report.get("approved_source_prefab_entity_patch_operation_count", 0) or 0) <= 0:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab override-path/template-update verified=true requires a non-empty entity patch.",
            )
        if blocker:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab override-path/template-update verified=true cannot also report a blocker.",
            )
        if str(report.get("approved_source_prefab_marker_persistence_blocker", "")).strip():
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab override-path/template-update verified=true cannot report a marker persistence blocker.",
            )
        before_hash = str(report.get("approved_source_prefab_before_hash", "")).strip()
        after_hash = str(report.get("approved_source_prefab_after_hash", "")).strip()
        if not before_hash or not after_hash or before_hash == after_hash:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Approved source-prefab override-path/template-update verified=true requires changed before/after hashes.",
            )
        for asset_field in ("approved_source_prefab_actor_asset_id", "approved_source_prefab_motion_asset_id"):
            if not str(report.get(asset_field, "")).strip():
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Approved source-prefab override-path/template-update verified=true requires {asset_field}.",
                )
    elif str(report.get("status", "")).strip() == "pass" and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Approved source-prefab override-path/template-update route pass without verification requires a typed blocker.",
        )

    false_until_downstream_runtime = (
        "approved_spawnable_regenerated_or_found",
        "runtime_character_animation_component_wiring_claimed",
        "runtime_character_animation_component_wiring_verified",
        "runtime_character_animation_claimed",
        "runtime_character_animation_verified",
        "runtime_character_proof_claimed",
        "runtime_character_proof_verified",
    )
    for field in false_until_downstream_runtime:
        if report.get(field) is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                f"{field}=true must come from APB/runtime diagnostics, not source-template override-path/template update alone.",
            )


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


def _validate_editor_viewport_visual_material_evidence(report: Mapping[str, Any], result: ValidationResult) -> None:
    if report.get("editor_viewport_visual_material_evidence_attempted") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Editor viewport visual/material evidence diagnostic must record attempted=true.",
        )
    if report.get("editor_viewport_visual_material_evidence_completed") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Editor viewport visual/material evidence diagnostic must record completed=true.",
        )
    if report.get("editor_viewport_visual_material_evidence_source_validation_verified") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Editor viewport visual/material evidence diagnostic requires source validation.",
        )
    if report.get("editor_visual_material_defaultlevel_mutation") is True or report.get("defaultlevel_mutation") is True:
        result.add_error(MXN_PATH_UNSAFE, "Editor visual/material evidence must not mutate defaultlevel.")
    if (
        report.get("editor_visual_material_production_level_mutation") is True
        or report.get("production_level_mutation") is True
    ):
        result.add_error(MXN_PATH_UNSAFE, "Editor visual/material evidence must not mutate production levels.")
    if report.get("asset_cache_deleted") is True:
        result.add_error(MXN_PATH_UNSAFE, "Editor visual/material evidence must not delete Asset Cache.")
    if report.get("cache_heuristic_used") is True:
        result.add_error(
            "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN",
            "Editor visual/material evidence must not use cache heuristic proof.",
        )

    gate_verified = report.get("visual_material_gate_verified") is True
    rendered_verified = report.get("visual_material_rendered_evidence_gate_verified") is True
    if report.get("full_runtime_character_visual_material_gate_verified") is True and not gate_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Full runtime character visual/material gate cannot pass without visual_material_gate_verified=true.",
        )
    if report.get("visual_material_gate_claimed") is True and not gate_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "visual_material_gate_claimed=true requires visual_material_gate_verified=true.",
        )
    if report.get("runtime_character_proof_claimed") is True or report.get("runtime_character_proof_verified") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Editor viewport visual/material evidence cannot claim full runtime character proof.",
        )
    if gate_verified:
        required_true_fields = {
            "visual_material_gate_claimed": "visual/material claim",
            "visual_material_product_inventory_gate_verified": "APB/material inventory readiness",
            "visual_material_rendered_evidence_gate_attempted": "rendered evidence attempt",
            "visual_material_rendered_evidence_gate_verified": "rendered visual/material evidence",
            "editor_visual_material_capture_api_found": "source-validated capture API",
            "editor_visual_material_temp_scene_created": "safe temp visual scene",
            "editor_visual_material_character_instantiated": "approved character instantiation/display",
            "editor_visual_material_camera_or_view_framed": "camera or viewport framing",
            "editor_visual_material_capture_requested": "screenshot/frame capture request",
            "editor_visual_material_capture_completed": "screenshot/frame capture completion",
            "editor_visual_material_capture_artifact_exists": "captured artifact existence",
            "editor_visual_material_capture_content_validation_attempted": "capture content validation attempt",
            "editor_visual_material_capture_content_validation_verified": "capture content validation",
            "editor_visual_material_nonblank_validation_verified": "nonblank image validation",
            "editor_visual_material_character_presence_validation_verified": "character-presence validation",
            "editor_visual_material_material_presence_validation_verified": "material-presence validation",
            "editor_visual_material_cleanup_verified": "cleanup verification",
            "editor_visual_material_selected_log_scan_passed": "selected log scan",
        }
        for field, label in required_true_fields.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"visual_material_gate_verified=true requires {label}.",
                )
        try:
            width = int(report.get("editor_visual_material_capture_artifact_width", 0) or 0)
            height = int(report.get("editor_visual_material_capture_artifact_height", 0) or 0)
            size_bytes = int(report.get("editor_visual_material_capture_artifact_size_bytes", 0) or 0)
        except (TypeError, ValueError):
            width = height = size_bytes = 0
        if width <= 0 or height <= 0 or size_bytes <= 0:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "visual_material_gate_verified=true requires captured artifact dimensions and size.",
            )
    elif rendered_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Rendered visual/material evidence cannot be verified while visual_material_gate_verified is false.",
        )
    elif not str(report.get("editor_viewport_visual_material_evidence_blocker", "")).strip():
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unverified Editor visual/material evidence requires a precise typed blocker.",
        )


def _validate_non_null_editor_render_capture_envelope(report: Mapping[str, Any], result: ValidationResult) -> None:
    if report.get("non_null_editor_render_capture_envelope_attempted") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor render/capture envelope diagnostic must record attempted=true.",
        )
    if report.get("non_null_editor_render_capture_envelope_completed") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor render/capture envelope diagnostic must record completed=true.",
        )
    if report.get("non_null_editor_render_capture_envelope_source_validation_verified") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor render/capture envelope diagnostic requires source validation.",
        )
    if report.get("non_null_editor_render_capture_null_renderer_used") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "non_null_editor_render_capture_null_renderer_used must be false for the non-null render/capture envelope.",
        )
    rhi_requested = str(report.get("non_null_editor_render_capture_rhi_requested", "")).strip().lower()
    if not rhi_requested:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor render/capture envelope must record the requested RHI.",
        )
    elif rhi_requested not in NON_NULL_RENDER_CAPTURE_RHIS:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            f"Non-null Editor render/capture envelope requested unsupported RHI '{rhi_requested}'.",
        )
    if report.get("editor_visual_material_defaultlevel_mutation") is True or report.get("defaultlevel_mutation") is True:
        result.add_error(MXN_PATH_UNSAFE, "Non-null Editor render/capture envelope must not mutate defaultlevel.")
    if (
        report.get("editor_visual_material_production_level_mutation") is True
        or report.get("production_level_mutation") is True
    ):
        result.add_error(MXN_PATH_UNSAFE, "Non-null Editor render/capture envelope must not mutate production levels.")
    if report.get("asset_cache_deleted") is True:
        result.add_error(MXN_PATH_UNSAFE, "Non-null Editor render/capture envelope must not delete Asset Cache.")
    if report.get("cache_heuristic_used") is True:
        result.add_error(
            "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN",
            "Non-null Editor render/capture envelope must not use cache heuristic proof.",
        )

    envelope_verified = report.get("non_null_editor_render_capture_envelope_verified") is True
    capture_readiness = report.get("visual_material_capture_readiness_verified") is True
    gate_verified = report.get("visual_material_gate_verified") is True
    rendered_verified = report.get("visual_material_rendered_evidence_gate_verified") is True
    if envelope_verified:
        for field, label in {
            "non_null_editor_render_capture_editor_launched": "Editor launch",
            "non_null_editor_render_capture_editor_exited_cleanly": "clean Editor exit",
            "editor_visual_material_capture_api_available_under_non_null_rhi": "capture API under non-null RHI",
            "editor_visual_material_cleanup_verified": "cleanup",
            "editor_visual_material_selected_log_scan_passed": "selected log scan",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"non_null_editor_render_capture_envelope_verified=true requires {label}.",
                )
    elif not str(report.get("non_null_editor_render_capture_envelope_blocker", "")).strip():
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unverified non-null Editor render/capture envelope requires a precise typed blocker.",
        )

    if capture_readiness:
        for field, label in {
            "editor_visual_material_capture_requested": "capture request",
            "editor_visual_material_capture_completed": "capture completion",
            "editor_visual_material_capture_artifact_exists": "capture artifact existence",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"visual_material_capture_readiness_verified=true requires {label}.",
                )
        try:
            width = int(report.get("editor_visual_material_capture_artifact_width", 0) or 0)
            height = int(report.get("editor_visual_material_capture_artifact_height", 0) or 0)
            size_bytes = int(report.get("editor_visual_material_capture_artifact_size_bytes", 0) or 0)
        except (TypeError, ValueError):
            width = height = size_bytes = 0
        if width <= 0 or height <= 0 or size_bytes <= 0:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "visual_material_capture_readiness_verified=true requires captured artifact dimensions and size.",
            )

    if report.get("full_runtime_character_visual_material_gate_verified") is True and not gate_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Full runtime character visual/material gate cannot pass without visual_material_gate_verified=true.",
        )
    if report.get("visual_material_gate_claimed") is True and not gate_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "visual_material_gate_claimed=true requires visual_material_gate_verified=true.",
        )
    if report.get("runtime_character_proof_claimed") is True or report.get("runtime_character_proof_verified") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor render/capture envelope cannot claim full runtime character proof.",
        )
    if gate_verified:
        for field, label in {
            "visual_material_gate_claimed": "visual/material claim",
            "visual_material_product_inventory_gate_verified": "APB/material inventory readiness",
            "visual_material_rendered_evidence_gate_attempted": "rendered evidence attempt",
            "visual_material_rendered_evidence_gate_verified": "rendered visual/material evidence",
            "editor_visual_material_capture_api_found": "source-validated capture API",
            "editor_visual_material_temp_scene_created": "safe temp visual scene",
            "editor_visual_material_character_instantiated": "approved character instantiation/display",
            "editor_visual_material_camera_or_view_framed": "camera or viewport framing",
            "editor_visual_material_capture_requested": "screenshot/frame capture request",
            "editor_visual_material_capture_completed": "screenshot/frame capture completion",
            "editor_visual_material_capture_artifact_exists": "captured artifact existence",
            "editor_visual_material_capture_content_validation_attempted": "capture content validation attempt",
            "editor_visual_material_capture_content_validation_verified": "capture content validation",
            "editor_visual_material_nonblank_validation_verified": "nonblank image validation",
            "editor_visual_material_character_presence_validation_verified": "character-presence validation",
            "editor_visual_material_material_presence_validation_verified": "material-presence validation",
            "editor_visual_material_cleanup_verified": "cleanup verification",
            "editor_visual_material_selected_log_scan_passed": "selected log scan",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"visual_material_gate_verified=true requires {label}.",
                )
    elif rendered_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Rendered visual/material evidence cannot be verified while visual_material_gate_verified is false.",
        )


def _validate_non_null_editor_visual_runner_readiness(report: Mapping[str, Any], result: ValidationResult) -> None:
    if report.get("non_null_editor_visual_runner_readiness_attempted") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor visual runner readiness diagnostic must record attempted=true.",
        )
    if report.get("non_null_editor_visual_runner_readiness_completed") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor visual runner readiness diagnostic must record completed=true.",
        )
    if report.get("non_null_editor_visual_runner_readiness_source_validation_verified") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor visual runner readiness requires source validation.",
        )
    if report.get("existing_nullrenderer_safe_editor_lane_preserved") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null visual readiness must preserve the existing NullRenderer-safe Editor lane.",
        )
    if report.get("null_renderer_used") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "null_renderer_used must be false for the non-null visual runner readiness envelope.",
        )

    selected_rhi = str(report.get("selected_rhi", "") or report.get("non_null_editor_render_capture_rhi_requested", "")).strip().lower()
    if not selected_rhi:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Non-null visual runner readiness must record selected_rhi.")
    elif selected_rhi not in NON_NULL_RENDER_CAPTURE_RHIS:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Non-null visual runner readiness selected unsupported RHI '{selected_rhi}'.")

    for field, message in (
        ("editor_temp_visual_scene_defaultlevel_mutation", "temp visual scene contract must not mutate defaultlevel."),
        ("editor_temp_visual_scene_production_level_mutation", "temp visual scene contract must not mutate production levels."),
        ("editor_visual_material_defaultlevel_mutation", "Editor visual/material readiness must not mutate defaultlevel."),
        ("editor_visual_material_production_level_mutation", "Editor visual/material readiness must not mutate production levels."),
        ("defaultlevel_mutation", "Editor visual/material readiness must not mutate defaultlevel."),
        ("production_level_mutation", "Editor visual/material readiness must not mutate production levels."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_PATH_UNSAFE, message)
    if report.get("asset_cache_deleted") is True:
        result.add_error(MXN_PATH_UNSAFE, "Non-null visual runner readiness must not delete Asset Cache.")
    if report.get("cache_heuristic_used") is True:
        result.add_error(
            "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN",
            "Non-null visual runner readiness must not use cache heuristic proof.",
        )

    temp_contract_verified = report.get("editor_temp_visual_scene_contract_verified") is True
    temp_root = str(report.get("editor_temp_visual_scene_approved_root", "")).replace("\\", "/").strip()
    if report.get("editor_temp_visual_scene_contract_pinned") is True or temp_contract_verified:
        if report.get("editor_temp_visual_scene_contract_attempted") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "temp visual scene contract cannot be pinned without attempted=true.",
            )
        if not temp_root or not temp_root.startswith("Levels/_maxine_visual_smoke"):
            result.add_error(
                MXN_PATH_UNSAFE,
                "temp visual scene contract requires approved root under Levels/_maxine_visual_smoke.",
            )
        lowered_root = temp_root.lower()
        if "defaultlevel" in lowered_root or "/production" in lowered_root or "production/" in lowered_root:
            result.add_error(
                MXN_PATH_UNSAFE,
                "temp visual scene contract root must not target defaultlevel or production levels.",
            )
        if report.get("editor_temp_visual_scene_cleanup_policy_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "temp visual scene contract requires verified cleanup policy.",
            )
        if report.get("editor_temp_visual_scene_defaultlevel_mutation") is not False:
            result.add_error(
                MXN_PATH_UNSAFE,
                "temp visual scene contract must explicitly record editor_temp_visual_scene_defaultlevel_mutation=false.",
            )
        if report.get("editor_temp_visual_scene_production_level_mutation") is not False:
            result.add_error(
                MXN_PATH_UNSAFE,
                "temp visual scene contract must explicitly record editor_temp_visual_scene_production_level_mutation=false.",
            )
    elif not str(report.get("editor_temp_visual_scene_contract_blocker", "")).strip():
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unverified temp visual scene contract requires a precise typed blocker.",
        )

    artifact_root = str(report.get("editor_visual_material_capture_artifact_root", "")).replace("\\", "/").strip()
    if report.get("editor_visual_material_capture_artifact_policy_verified") is True:
        if artifact_root != "artifacts/o3de-integration/editor-smoke":
            result.add_error(
                MXN_PATH_UNSAFE,
                "capture artifact policy requires artifacts/o3de-integration/editor-smoke root.",
            )
    elif report.get("editor_temp_visual_scene_contract_pinned") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Pinned temp visual scene contract requires a verified capture artifact policy.",
        )

    visible_verified = report.get("visible_desktop_session_verified") is True
    gpu_verified = report.get("gpu_or_driver_readiness_verified") is True
    rhi_verified = report.get("rhi_readiness_verified") is True
    readiness_verified = report.get("non_null_editor_visual_runner_readiness_verified") is True
    launch_attempted = report.get("non_null_editor_launch_attempted") is True
    launch_verified = report.get("non_null_editor_launch_verified") is True
    if readiness_verified:
        for field, label in {
            "visible_desktop_session_verified": "visible desktop/session readiness",
            "gpu_or_driver_readiness_verified": "GPU/driver readiness",
            "rhi_readiness_verified": "RHI readiness",
            "editor_temp_visual_scene_contract_verified": "temp visual scene contract",
            "editor_visual_material_capture_artifact_policy_verified": "capture artifact policy",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"non_null_editor_visual_runner_readiness_verified=true requires {field} ({label}).",
                )
    elif not str(report.get("non_null_editor_visual_runner_readiness_blocker", "")).strip():
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unverified non-null Editor visual runner readiness requires a precise typed blocker.",
        )

    if launch_attempted and not visible_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "non_null_editor_launch_attempted=true requires visible_desktop_session_verified=true.",
        )
    if launch_attempted and not gpu_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "non_null_editor_launch_attempted=true requires gpu_or_driver_readiness_verified=true.",
        )
    if launch_attempted and not rhi_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "non_null_editor_launch_attempted=true requires rhi_readiness_verified=true.",
        )
    if launch_verified:
        if not launch_attempted or report.get("non_null_editor_launch_completed") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "non_null_editor_launch_verified=true requires launch attempted/completed evidence.",
            )
        if report.get("non_null_editor_launch_exit_code") != 0:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "non_null_editor_launch_verified=true requires non_null_editor_launch_exit_code=0.",
            )

    capture_requested = report.get("editor_visual_material_capture_requested") is True
    if capture_requested and not readiness_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "editor_visual_material_capture_requested=true requires non_null_editor_visual_runner_readiness_verified=true.",
        )
    if report.get("visual_material_capture_readiness_verified") is True:
        for field, label in {
            "non_null_editor_visual_runner_readiness_verified": "visual runner readiness",
            "editor_visual_material_capture_requested": "capture request",
            "editor_visual_material_capture_completed": "capture completion",
            "editor_visual_material_capture_artifact_exists": "capture artifact existence",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"visual_material_capture_readiness_verified=true requires {field} ({label}).",
                )

    gate_verified = report.get("visual_material_gate_verified") is True
    rendered_verified = report.get("visual_material_rendered_evidence_gate_verified") is True
    if report.get("visual_material_gate_claimed") is True and not gate_verified:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "visual_material_gate_claimed=true requires visual_material_gate_verified=true.")
    if report.get("full_runtime_character_visual_material_gate_verified") is True and not gate_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "full_runtime_character_visual_material_gate_verified=true requires visual_material_gate_verified=true.",
        )
    if gate_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "visual_material_gate_verified=true is not allowed from readiness/temp-scene contract evidence alone.",
        )
    if rendered_verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "visual_material_rendered_evidence_gate_verified=true is not allowed from readiness/temp-scene contract evidence alone.",
        )
    if report.get("runtime_character_proof_claimed") is True or report.get("runtime_character_proof_verified") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor visual runner readiness cannot claim full runtime character proof.",
        )


def _validate_non_null_editor_desktop_rhi_readiness(report: Mapping[str, Any], result: ValidationResult) -> None:
    _validate_non_null_editor_visual_runner_readiness(report, result)
    if report.get("non_null_editor_desktop_rhi_readiness_attempted") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor desktop/RHI readiness diagnostic must record attempted=true.",
        )
    if report.get("non_null_editor_desktop_rhi_readiness_completed") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor desktop/RHI readiness diagnostic must record completed=true.",
        )
    if report.get("non_null_editor_desktop_rhi_readiness_source_validation_verified") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-null Editor desktop/RHI readiness requires source validation.",
        )
    for field in (
        "visible_desktop_session_check_attempted",
        "gpu_or_driver_readiness_check_attempted",
        "rhi_readiness_check_attempted",
    ):
        if report.get(field) is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Desktop/RHI readiness requires {field}=true.")
    for field in (
        "visible_desktop_session_check_method",
        "gpu_or_driver_readiness_check_method",
        "rhi_readiness_check_method",
        "visible_desktop_session_state",
        "windows_session_type",
    ):
        if not str(report.get(field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Desktop/RHI readiness must record {field}.")
    if not isinstance(report.get("gpu_adapter_summary"), list):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Desktop/RHI readiness must record gpu_adapter_summary as a list.")
    if report.get("rhi_fallback_considered") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Desktop/RHI readiness must record rhi_fallback_considered=true.")

    desktop_rhi_verified = report.get("non_null_editor_desktop_rhi_readiness_verified") is True
    if desktop_rhi_verified:
        for field, label in {
            "visible_desktop_session_verified": "visible desktop/session readiness",
            "gpu_or_driver_readiness_verified": "GPU/driver readiness",
            "rhi_readiness_verified": "selected RHI readiness",
            "editor_temp_visual_scene_contract_verified": "temp visual scene contract",
            "editor_visual_material_capture_artifact_policy_verified": "capture artifact policy",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"non_null_editor_desktop_rhi_readiness_verified=true requires {field} ({label}).",
                )
    elif not str(report.get("non_null_editor_desktop_rhi_readiness_blocker", "")).strip():
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unverified non-null Editor desktop/RHI readiness requires a precise typed blocker.",
        )

    if report.get("editor_visual_material_capture_requested") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Desktop/RHI readiness diagnostic must not request screenshot/frame capture.",
        )
    if report.get("editor_visual_material_capture_completed") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Desktop/RHI readiness diagnostic must not claim screenshot/frame capture completion.",
        )
    if report.get("visual_material_capture_readiness_verified") is True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Desktop/RHI readiness alone cannot verify visual/material capture readiness.",
        )


def _validate_live_non_null_editor_launch(report: Mapping[str, Any], result: ValidationResult) -> None:
    _validate_non_null_editor_desktop_rhi_readiness(report, result)
    source_validated = report.get("live_non_null_editor_launch_source_validation_verified") is True
    launch_attempted = report.get("live_non_null_editor_launch_attempted") is True
    launch_blocker = str(report.get("live_non_null_editor_launch_blocker", "")).strip()
    if not source_validated and launch_attempted:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Live non-null Editor launch must not be attempted when launch source validation is false.",
        )
    if not source_validated and not launch_blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unvalidated live non-null Editor launch source contract requires a precise typed blocker.",
        )
    if report.get("existing_nullrenderer_safe_editor_lane_preserved") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Live non-null Editor launch must preserve the existing NullRenderer-safe Editor lane.",
        )

    selected_rhi = str(
        report.get("live_non_null_editor_launch_selected_rhi", "")
        or report.get("selected_rhi", "")
        or report.get("non_null_editor_render_capture_rhi_requested", "")
    ).strip().lower()
    if not selected_rhi:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Live non-null Editor launch must record the selected RHI.")
    elif selected_rhi not in NON_NULL_RENDER_CAPTURE_RHIS:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Live non-null Editor launch selected unsupported RHI '{selected_rhi}'.")

    command_parts = list(report.get("command_argv_redacted", []) or []) + list(
        report.get("live_non_null_editor_launch_command", []) or []
    )
    command = " ".join(str(part) for part in command_parts)
    if (
        report.get("live_non_null_editor_launch_null_renderer_used") is True
        or "-NullRenderer" in command
        or "-rhi=Null" in command
        or "-rhi=null" in command.lower()
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "live_non_null_editor_launch_null_renderer_used must be false and command must omit NullRenderer/null RHI.",
        )

    for field, message in (
        ("editor_temp_visual_scene_created", "Live non-null launch-only diagnostic must not create a temp visual scene."),
        ("editor_visual_material_temp_scene_created", "Live non-null launch-only diagnostic must not create a visual scene."),
        ("editor_visual_material_capture_requested", "Live non-null launch-only diagnostic must not request screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Live non-null launch-only diagnostic must not claim screenshot/frame capture completion."),
        ("visual_material_capture_readiness_verified", "Live non-null launch-only diagnostic cannot verify capture readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Live non-null launch-only diagnostic must not attempt rendered evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Live non-null launch-only diagnostic cannot verify rendered visual/material evidence."),
        ("visual_material_gate_verified", "Live non-null Editor launch alone cannot verify the visual/material gate."),
        ("full_runtime_character_visual_material_gate_verified", "Live non-null Editor launch alone cannot verify the full visual/material gate."),
        ("runtime_character_proof_claimed", "Live non-null Editor launch cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Live non-null Editor launch cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)

    for field, message in (
        ("editor_temp_visual_scene_defaultlevel_mutation", "Live non-null Editor launch must not mutate defaultlevel."),
        ("editor_temp_visual_scene_production_level_mutation", "Live non-null Editor launch must not mutate production levels."),
        ("editor_visual_material_defaultlevel_mutation", "Live non-null Editor launch must not mutate defaultlevel."),
        ("editor_visual_material_production_level_mutation", "Live non-null Editor launch must not mutate production levels."),
        ("defaultlevel_mutation", "Live non-null Editor launch must not mutate defaultlevel."),
        ("production_level_mutation", "Live non-null Editor launch must not mutate production levels."),
        ("asset_cache_deleted", "Live non-null Editor launch must not delete Asset Cache."),
        ("cache_heuristic_used", "Live non-null Editor launch must not use cache heuristic proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_PATH_UNSAFE, message)

    attempted = launch_attempted
    completed = report.get("live_non_null_editor_launch_completed") is True
    verified = report.get("live_non_null_editor_launch_verified") is True
    if attempted:
        for field, label in {
            "visible_desktop_session_verified": "visible desktop/session readiness",
            "gpu_or_driver_readiness_verified": "GPU/driver readiness",
            "rhi_readiness_verified": "RHI readiness",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"live_non_null_editor_launch_attempted=true requires {field} ({label}).",
                )
        if report.get("live_editor_execution") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "live_non_null_editor_launch_attempted=true requires live_editor_execution=true.",
            )
        if report.get("non_null_editor_launch_attempted") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "live_non_null_editor_launch_attempted=true requires non_null_editor_launch_attempted=true.",
            )
    elif not str(report.get("live_non_null_editor_launch_blocker", "")).strip():
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unattempted live non-null Editor launch requires a precise typed blocker.",
        )

    if verified:
        for field, label in {
            "live_non_null_editor_launch_attempted": "launch attempt",
            "live_non_null_editor_launch_completed": "launch completion",
            "live_non_null_editor_launch_python_wrapper_executed": "Python wrapper execution",
            "live_non_null_editor_launch_selected_log_scan_passed": "selected log scan",
            "non_null_editor_launch_attempted": "non-null launch attempt mirror",
            "non_null_editor_launch_completed": "non-null launch completion mirror",
            "non_null_editor_launch_verified": "non-null launch verification mirror",
        }.items():
            if report.get(field) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"live_non_null_editor_launch_verified=true requires {label}.")
        if report.get("live_non_null_editor_launch_exit_code") != 0 or report.get("non_null_editor_launch_exit_code") != 0:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "live_non_null_editor_launch_verified=true requires zero launch exit codes.",
            )
        if report.get("live_non_null_editor_launch_timeout") is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "live_non_null_editor_launch_verified=true requires timeout=false.",
            )
        if report.get("live_non_null_editor_launch_killed") is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "live_non_null_editor_launch_verified=true requires killed=false.",
            )
        blocking_matches = report.get("live_non_null_editor_launch_selected_log_blocking_matches", [])
        if isinstance(blocking_matches, list) and blocking_matches:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "live_non_null_editor_launch_verified=true requires no selected blocking log matches.",
            )
    elif attempted and completed and not str(report.get("live_non_null_editor_launch_blocker", "")).strip():
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unverified live non-null Editor launch requires a precise typed blocker.",
        )


def _validate_editor_screenshot_capture_artifact_readiness(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    source_validated = report.get("editor_screenshot_capture_artifact_readiness_source_validation_verified") is True
    attempted = report.get("editor_screenshot_capture_artifact_readiness_attempted") is True
    completed = report.get("editor_screenshot_capture_artifact_readiness_completed") is True
    verified = report.get("editor_screenshot_capture_artifact_readiness_verified") is True
    blocker = str(report.get("editor_screenshot_capture_artifact_readiness_blocker", "")).strip()

    if report.get("existing_nullrenderer_safe_editor_lane_preserved") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Editor screenshot capture artifact readiness must preserve the existing NullRenderer-safe Editor lane.",
        )
    if attempted and not source_validated:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Editor screenshot capture artifact readiness must not be attempted when source validation is false.",
        )
    if not source_validated and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unvalidated Editor screenshot capture artifact readiness requires a precise typed blocker.",
        )

    selected_rhi = str(
        report.get("live_non_null_editor_launch_selected_rhi", "")
        or report.get("selected_rhi", "")
        or report.get("non_null_editor_render_capture_rhi_requested", "")
    ).strip().lower()
    if not selected_rhi:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor screenshot capture artifact readiness must record selected RHI.")
    elif selected_rhi not in NON_NULL_RENDER_CAPTURE_RHIS:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            f"Editor screenshot capture artifact readiness selected unsupported RHI '{selected_rhi}'.",
        )

    command_parts = list(report.get("command_argv_redacted", []) or []) + list(
        report.get("live_non_null_editor_launch_command", []) or []
    )
    command = " ".join(str(part) for part in command_parts)
    if (
        report.get("live_non_null_editor_launch_null_renderer_used") is True
        or report.get("non_null_editor_render_capture_null_renderer_used") is True
        or "-NullRenderer" in command
        or "-rhi=Null" in command
        or "-rhi=null" in command.lower()
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Editor screenshot capture artifact readiness command must omit NullRenderer/null RHI.",
        )

    for field, message in (
        ("editor_temp_visual_scene_created", "Screenshot artifact readiness slice must not create a temp visual scene."),
        ("editor_visual_material_temp_scene_created", "Screenshot artifact readiness slice must not create a visual scene."),
        ("visual_material_rendered_evidence_gate_verified", "visual_material_rendered_evidence_gate_verified=true is not allowed from screenshot artifact readiness alone."),
        ("visual_material_gate_claimed", "visual_material_gate_claimed=true is not allowed from screenshot artifact readiness alone."),
        ("visual_material_gate_verified", "visual_material_gate_verified=true is not allowed from screenshot artifact readiness alone."),
        ("full_runtime_character_visual_material_gate_verified", "full_runtime_character_visual_material_gate_verified=true is not allowed from screenshot artifact readiness alone."),
        ("runtime_character_proof_claimed", "Screenshot artifact readiness cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Screenshot artifact readiness cannot verify full runtime character proof."),
        ("editor_visual_material_capture_content_validation_verified", "Screenshot artifact readiness does not verify capture content."),
        ("editor_visual_material_nonblank_validation_verified", "Screenshot artifact readiness does not verify nonblank content unless a later content gate passes."),
        ("editor_visual_material_character_presence_validation_verified", "Screenshot artifact readiness does not verify character presence."),
        ("editor_visual_material_material_presence_validation_verified", "Screenshot artifact readiness does not verify material presence."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)

    for field, message in (
        ("editor_temp_visual_scene_defaultlevel_mutation", "Screenshot artifact readiness must not mutate defaultlevel."),
        ("editor_temp_visual_scene_production_level_mutation", "Screenshot artifact readiness must not mutate production levels."),
        ("editor_visual_material_defaultlevel_mutation", "Screenshot artifact readiness must not mutate defaultlevel."),
        ("editor_visual_material_production_level_mutation", "Screenshot artifact readiness must not mutate production levels."),
        ("defaultlevel_mutation", "Screenshot artifact readiness must not mutate defaultlevel."),
        ("production_level_mutation", "Screenshot artifact readiness must not mutate production levels."),
        ("asset_cache_deleted", "Screenshot artifact readiness must not delete Asset Cache."),
        ("cache_heuristic_used", "Screenshot artifact readiness must not use cache heuristic proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_PATH_UNSAFE, message)

    if attempted:
        for field, label in {
            "visible_desktop_session_verified": "visible desktop/session readiness",
            "gpu_or_driver_readiness_verified": "GPU/driver readiness",
            "rhi_readiness_verified": "RHI readiness",
            "live_non_null_editor_launch_source_validation_verified": "live launch source validation",
            "live_non_null_editor_launch_verified": "live non-null Editor launch verification",
            "live_non_null_editor_launch_python_wrapper_executed": "Editor Python wrapper execution",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"editor_screenshot_capture_artifact_readiness_attempted=true requires {field} ({label}).",
                )
        if report.get("live_editor_execution") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "editor_screenshot_capture_artifact_readiness_attempted=true requires live_editor_execution=true.",
            )
    elif not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unattempted Editor screenshot capture artifact readiness requires a precise typed blocker.",
        )

    capture_readiness = report.get("visual_material_capture_readiness_verified") is True
    if verified or capture_readiness:
        required_true = {
            "editor_screenshot_capture_artifact_readiness_attempted": "capture readiness attempt",
            "editor_screenshot_capture_artifact_readiness_completed": "capture readiness completion",
            "editor_visual_material_capture_api_found": "capture API source",
            "editor_visual_material_capture_api_available_under_non_null_rhi": "capture API availability under non-null RHI",
            "editor_visual_material_capture_requested": "capture request",
            "editor_visual_material_capture_request_accepted": "capture request acceptance",
            "editor_visual_material_capture_completed": "capture completion",
            "editor_visual_material_capture_artifact_exists": "capture artifact existence",
            "editor_visual_material_selected_log_scan_passed": "selected log scan",
        }
        for field, label in required_true.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"editor_screenshot_capture_artifact_readiness_verified=true requires {field} ({label}).",
                )
        if not completed:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "visual_material_capture_readiness_verified=true requires screenshot artifact readiness completion.",
            )
        width = int(report.get("editor_visual_material_capture_artifact_width", 0) or 0)
        height = int(report.get("editor_visual_material_capture_artifact_height", 0) or 0)
        size_bytes = int(report.get("editor_visual_material_capture_artifact_size_bytes", 0) or 0)
        artifact_format = str(report.get("editor_visual_material_capture_artifact_format", "")).strip().lower()
        sha256 = str(report.get("editor_visual_material_capture_artifact_sha256", "")).strip()
        if artifact_format != "png" or width <= 0 or height <= 0 or size_bytes <= 0 or len(sha256) != 64:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Screenshot capture artifact readiness requires png artifact format, positive dimensions/size, and sha256.",
            )
        if blocker:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Verified screenshot capture artifact readiness must not carry a blocker.",
            )
    elif attempted and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unverified screenshot capture artifact readiness requires a precise typed blocker.",
        )


def _validate_editor_active_viewport_temp_scene_readiness(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    _validate_live_non_null_editor_launch(report, result)
    source_validated = report.get("editor_active_viewport_temp_scene_readiness_source_validation_verified") is True
    attempted = report.get("editor_active_viewport_temp_scene_readiness_attempted") is True
    completed = report.get("editor_active_viewport_temp_scene_readiness_completed") is True
    verified = report.get("editor_active_viewport_temp_scene_readiness_verified") is True
    blocker = str(report.get("editor_active_viewport_temp_scene_readiness_blocker", "")).strip()

    if not attempted:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Active viewport/temp scene readiness must record attempted=true.")
    if not completed:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Active viewport/temp scene readiness must record completed=true.")
    if not source_validated and attempted:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Active viewport/temp scene readiness must not proceed when source validation is false.",
        )
    if not source_validated and not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unvalidated active viewport/temp scene readiness requires a precise typed blocker.",
        )

    for field, message in (
        ("editor_visual_material_capture_requested", "Active viewport/temp scene readiness must not request screenshot/frame capture."),
        ("editor_visual_material_capture_request_accepted", "Active viewport/temp scene readiness must not accept screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Active viewport/temp scene readiness must not claim screenshot/frame capture completion."),
        ("visual_material_capture_readiness_verified", "Active viewport/temp scene readiness alone cannot verify screenshot artifact readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Active viewport/temp scene readiness must not attempt rendered evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Active viewport/temp scene readiness cannot verify rendered evidence."),
        ("visual_material_gate_claimed", "Active viewport/temp scene readiness cannot claim visual/material proof."),
        ("visual_material_gate_verified", "Active viewport/temp scene readiness cannot verify visual/material proof."),
        ("full_runtime_character_visual_material_gate_verified", "Active viewport/temp scene readiness cannot verify the full visual/material gate."),
        ("runtime_character_proof_claimed", "Active viewport/temp scene readiness cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Active viewport/temp scene readiness cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)

    for field, message in (
        ("editor_temp_visual_scene_defaultlevel_mutation", "Active viewport/temp scene readiness must not mutate defaultlevel."),
        ("editor_temp_visual_scene_production_level_mutation", "Active viewport/temp scene readiness must not mutate production levels."),
        ("editor_visual_material_defaultlevel_mutation", "Active viewport/temp scene readiness must not mutate defaultlevel."),
        ("editor_visual_material_production_level_mutation", "Active viewport/temp scene readiness must not mutate production levels."),
        ("defaultlevel_mutation", "Active viewport/temp scene readiness must not mutate defaultlevel."),
        ("production_level_mutation", "Active viewport/temp scene readiness must not mutate production levels."),
        ("asset_cache_deleted", "Active viewport/temp scene readiness must not delete Asset Cache."),
        ("cache_heuristic_used", "Active viewport/temp scene readiness must not use cache heuristic proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_PATH_UNSAFE, message)

    temp_root = str(report.get("editor_temp_visual_scene_approved_root", "")).replace("\\", "/").strip()
    temp_path = str(report.get("editor_temp_visual_scene_path", "")).replace("\\", "/").strip()
    if report.get("editor_temp_visual_scene_readiness_verified") is True or report.get("editor_temp_visual_scene_contract_verified") is True:
        if report.get("editor_temp_visual_scene_readiness_attempted") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Verified temp visual scene readiness requires attempted=true.")
        if not temp_root.startswith("Levels/_maxine_visual_smoke"):
            result.add_error(MXN_PATH_UNSAFE, "Temp visual scene readiness requires approved root under Levels/_maxine_visual_smoke.")
        if temp_path and not temp_path.startswith("Levels/_maxine_visual_smoke"):
            result.add_error(MXN_PATH_UNSAFE, "Temp visual scene readiness path must stay under Levels/_maxine_visual_smoke.")
        if report.get("editor_temp_visual_scene_cleanup_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Temp visual scene readiness requires cleanup verification or no-create cleanup policy.")
        if report.get("editor_temp_visual_scene_defaultlevel_mutation") is not False:
            result.add_error(MXN_PATH_UNSAFE, "Temp visual scene readiness must record defaultlevel mutation as false.")
        if report.get("editor_temp_visual_scene_production_level_mutation") is not False:
            result.add_error(MXN_PATH_UNSAFE, "Temp visual scene readiness must record production-level mutation as false.")
    elif not str(report.get("editor_temp_visual_scene_contract_blocker", "")).strip():
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified temp visual scene readiness requires a precise typed blocker.")

    if report.get("editor_active_viewport_readiness_attempted") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Active viewport readiness must record attempted=true.")
    if report.get("editor_active_viewport_readiness_verified") is True:
        for field in ("editor_active_viewport_check_method", "editor_active_viewport_state"):
            if not str(report.get(field, "")).strip():
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Verified active viewport readiness requires {field}.")
        if report.get("editor_active_viewport_render_ready") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Verified active viewport readiness requires render-ready viewport dimensions.")
    elif not str(report.get("editor_active_viewport_blocker", "")).strip():
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified active viewport readiness requires a precise typed blocker.")

    if report.get("editor_frame_capture_target_readiness_attempted") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "FrameCapture target readiness must record attempted=true.")
    if report.get("editor_frame_capture_target_readiness_verified") is True:
        if report.get("editor_active_viewport_window_handle_available") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "FrameCapture target readiness requires a source-validated active/default viewport window handle.",
            )
    elif not str(report.get("editor_frame_capture_target_blocker", "")).strip():
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified FrameCapture target readiness requires a precise typed blocker.")

    capture_target_verified = report.get("editor_visual_material_capture_target_readiness_verified") is True
    if capture_target_verified:
        if not (
            report.get("editor_temp_visual_scene_readiness_verified") is True
            or report.get("editor_frame_capture_target_readiness_verified") is True
        ):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Capture target readiness requires temp visual scene readiness or FrameCapture target readiness.",
            )
    elif verified:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Verified active viewport/temp scene readiness requires capture-target readiness.",
        )

    if verified:
        for field, label in {
            "editor_active_viewport_temp_scene_readiness_source_validation_verified": "source validation",
            "visible_desktop_session_verified": "visible desktop/session readiness",
            "gpu_or_driver_readiness_verified": "GPU/driver readiness",
            "rhi_readiness_verified": "RHI readiness",
            "live_non_null_editor_launch_verified": "live non-null Editor launch",
            "editor_visual_material_capture_target_readiness_verified": "capture-target readiness",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"editor_active_viewport_temp_scene_readiness_verified=true requires {field} ({label}).",
                )
        if blocker:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Verified active viewport/temp scene readiness must not carry a blocker.")
    elif not blocker:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unverified active viewport/temp scene readiness requires a precise typed blocker.",
        )


def _validate_editor_safe_temp_visual_scene_display_context(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("temp_visual_scene_context_exercise_attempted") is True
    completed = report.get("temp_visual_scene_context_exercise_completed") is True
    verified = report.get("temp_visual_scene_context_exercise_verified") is True
    source_validated = report.get("temp_visual_scene_source_validated") is True
    blocker = str(report.get("temp_visual_scene_context_exercise_blocker", "")).strip() or str(
        report.get("temp_visual_scene_blocker", "")
    ).strip()

    for field, label in {
        "live_non_null_editor_launch_attempted": "live non-null Editor launch attempted",
        "live_non_null_editor_launch_completed": "live non-null Editor launch completed",
        "live_non_null_editor_launch_verified": "live non-null Editor launch verified",
        "live_non_null_editor_launch_python_wrapper_executed": "Editor Python wrapper executed",
        "visible_desktop_session_verified": "visible desktop/session readiness",
        "gpu_or_driver_readiness_verified": "GPU/driver readiness",
        "rhi_readiness_verified": "RHI readiness",
    }.items():
        if report.get(field) is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Safe temp visual scene context requires {label}.")
    if report.get("live_non_null_editor_launch_null_renderer_used") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Safe temp visual scene context must omit NullRenderer.")

    if not attempted:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Safe temp visual scene context exercise must record attempted=true.")
    if not completed:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Safe temp visual scene context exercise must record completed=true.")
    if not source_validated and attempted:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Safe temp visual scene context cannot proceed without source validation.")
    if not source_validated and not blocker:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unvalidated safe temp visual scene context requires a typed blocker.")

    for field, message in (
        ("editor_visual_material_capture_requested", "Safe temp visual scene context must not request screenshot/frame capture."),
        ("editor_visual_material_capture_request_accepted", "Safe temp visual scene context must not accept screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Safe temp visual scene context must not claim screenshot/frame capture completion."),
        ("visual_material_capture_readiness_verified", "Safe temp visual scene context cannot verify screenshot artifact readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Safe temp visual scene context must not attempt rendered visual evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Safe temp visual scene context cannot verify rendered visual evidence."),
        ("visual_material_gate_claimed", "Safe temp visual scene context cannot claim visual/material proof."),
        ("visual_material_gate_verified", "Safe temp visual scene context cannot verify visual/material proof."),
        ("runtime_character_proof_claimed", "Safe temp visual scene context cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Safe temp visual scene context cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)

    for field, message in (
        ("defaultlevel_mutation", "Safe temp visual scene context must not mutate defaultlevel."),
        ("production_level_mutation", "Safe temp visual scene context must not mutate production levels."),
        ("editor_temp_visual_scene_defaultlevel_mutation", "Safe temp visual scene context must not mutate defaultlevel."),
        ("editor_temp_visual_scene_production_level_mutation", "Safe temp visual scene context must not mutate production levels."),
        ("editor_visual_material_defaultlevel_mutation", "Safe temp visual scene context must not mutate defaultlevel."),
        ("editor_visual_material_production_level_mutation", "Safe temp visual scene context must not mutate production levels."),
        ("defaultlevel_mutation_detected", "Safe temp visual scene context must not detect defaultlevel mutation."),
        ("production_level_mutation_detected", "Safe temp visual scene context must not detect production-level mutation."),
        ("production_character_asset_mutation_detected", "Safe temp visual scene context must not detect production character asset mutation."),
        ("asset_cache_deleted", "Safe temp visual scene context must not delete Asset Cache."),
        ("cache_heuristic_used", "Safe temp visual scene context must not use cache heuristic proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_PATH_UNSAFE, message)

    temp_path = str(report.get("temp_visual_scene_path", "") or report.get("editor_temp_visual_scene_path", ""))
    normalized_temp_path = temp_path.replace("\\", "/").strip()
    if not normalized_temp_path.startswith("Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context"):
        result.add_error(
            MXN_PATH_UNSAFE,
            "Safe temp visual scene context path must remain under Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context.",
        )
    if "defaultlevel" in normalized_temp_path.lower() or "production" in normalized_temp_path.lower():
        result.add_error(MXN_PATH_UNSAFE, "Safe temp visual scene context path cannot include defaultlevel or production names.")

    if verified:
        for field, label in {
            "temp_visual_scene_source_validated": "source validation",
            "visible_desktop_session_verified": "visible desktop/session readiness",
            "gpu_or_driver_readiness_verified": "GPU/driver readiness",
            "rhi_readiness_verified": "RHI readiness",
            "live_non_null_editor_launch_verified": "live non-null Editor launch",
            "temp_visual_scene_created": "temp scene creation",
            "temp_visual_scene_opened": "temp scene open/display context",
            "temp_visual_scene_saved": "source-validated create-level save",
            "temp_visual_scene_cleanup_attempted": "cleanup attempted",
            "temp_visual_scene_cleanup_completed": "cleanup completed",
            "defaultlevel_mutation_checked": "defaultlevel mutation audit",
            "production_level_mutation_checked": "production-level mutation audit",
            "production_character_asset_mutation_checked": "production character mutation audit",
        }.items():
            if report.get(field) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Verified safe temp visual scene context requires {field} ({label}).")
        if blocker:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Verified safe temp visual scene context must not carry a blocker.")
    elif not blocker:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified safe temp visual scene context requires a precise typed blocker.")

    if report.get("active_viewport_after_temp_context_attempted") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Safe temp visual scene context must record active viewport after-context probe status.")
    if (
        report.get("active_viewport_after_temp_context_verified") is not True
        and not str(report.get("active_viewport_after_temp_context_blocker", "")).strip()
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified active viewport after temp context requires a blocker.")
    if report.get("framecapture_target_after_temp_context_attempted") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Safe temp visual scene context must record FrameCapture target after-context probe status.")
    if (
        report.get("framecapture_target_after_temp_context_verified") is not True
        and not str(report.get("framecapture_target_after_temp_context_blocker", "")).strip()
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified FrameCapture target after temp context requires a blocker.")


def _validate_editor_nonblocking_viewport_swapchain_readiness(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    attempted = report.get("nonblocking_viewport_swapchain_probe_attempted") is True
    verified = report.get("nonblocking_viewport_swapchain_probe_verified") is True
    source_validated = report.get("nonblocking_viewport_swapchain_probe_source_validated") is True
    blocker = str(report.get("nonblocking_viewport_swapchain_probe_blocker", "")).strip()
    strategies = report.get("nonblocking_viewport_swapchain_probe_strategies", [])

    for field, label in {
        "live_non_null_editor_launch_attempted": "live non-null Editor launch attempted",
        "live_non_null_editor_launch_completed": "live non-null Editor launch completed",
        "live_non_null_editor_launch_verified": "live non-null Editor launch verified",
        "live_non_null_editor_launch_python_wrapper_executed": "Editor Python wrapper executed",
        "visible_desktop_session_verified": "visible desktop/session readiness",
        "gpu_or_driver_readiness_verified": "GPU/driver readiness",
        "rhi_readiness_verified": "RHI readiness",
        "temp_visual_scene_context_exercise_verified": "safe temp visual scene context exercise",
        "temp_visual_scene_cleanup_attempted": "temp scene cleanup attempted",
        "temp_visual_scene_cleanup_completed": "temp scene cleanup completed",
        "safe_temp_visual_scene_context_preserved": "safe temp visual scene context preservation",
    }.items():
        if report.get(field) is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Non-blocking viewport/SwapChain readiness requires {label}.")
    if report.get("live_non_null_editor_launch_null_renderer_used") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Non-blocking viewport/SwapChain readiness must omit NullRenderer.")

    if not attempted:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Non-blocking viewport/SwapChain readiness must record attempted=true.")
    if not source_validated and attempted:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Non-blocking viewport/SwapChain readiness cannot proceed without source validation.",
        )
    if not source_validated and not blocker:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unvalidated non-blocking viewport/SwapChain readiness requires a blocker.")

    if not isinstance(strategies, list) or not strategies:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Non-blocking viewport/SwapChain readiness requires strategy evidence.")
    else:
        for strategy in strategies:
            if not isinstance(strategy, Mapping):
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Probe strategy entries must be objects.")
                continue
            if not str(strategy.get("id", "")).strip():
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Probe strategy entries require an id.")
            if strategy.get("screenshot_capture_requested") is True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Probe strategies must not request screenshot/frame capture.")
            if strategy.get("readiness_only") is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Probe strategies must be explicitly readiness-only.")
            if strategy.get("attempted") is True and strategy.get("source_validated") is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Attempted probe strategies require source_validated=true.")
            if strategy.get("verified") is not True and not str(strategy.get("blocker", "")).strip():
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified probe strategies require typed blockers.")

    for field, message in (
        ("editor_visual_material_capture_requested", "Non-blocking viewport/SwapChain readiness must not request screenshot/frame capture."),
        ("editor_visual_material_capture_request_accepted", "Non-blocking viewport/SwapChain readiness must not accept screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Non-blocking viewport/SwapChain readiness must not claim screenshot/frame capture completion."),
        ("visual_material_capture_readiness_verified", "Non-blocking viewport/SwapChain readiness cannot verify screenshot artifact readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Non-blocking viewport/SwapChain readiness must not attempt rendered visual evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Non-blocking viewport/SwapChain readiness cannot verify rendered visual evidence."),
        ("visual_material_gate_claimed", "Non-blocking viewport/SwapChain readiness cannot claim visual/material proof."),
        ("visual_material_gate_verified", "Non-blocking viewport/SwapChain readiness cannot verify visual/material proof."),
        ("runtime_character_proof_claimed", "Non-blocking viewport/SwapChain readiness cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Non-blocking viewport/SwapChain readiness cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)

    for field, message in (
        ("defaultlevel_mutation", "Non-blocking viewport/SwapChain readiness must not mutate defaultlevel."),
        ("production_level_mutation", "Non-blocking viewport/SwapChain readiness must not mutate production levels."),
        ("editor_temp_visual_scene_defaultlevel_mutation", "Non-blocking viewport/SwapChain readiness must not mutate defaultlevel."),
        ("editor_temp_visual_scene_production_level_mutation", "Non-blocking viewport/SwapChain readiness must not mutate production levels."),
        ("defaultlevel_mutation_detected", "Non-blocking viewport/SwapChain readiness must not detect defaultlevel mutation."),
        ("production_level_mutation_detected", "Non-blocking viewport/SwapChain readiness must not detect production-level mutation."),
        ("production_character_asset_mutation_detected", "Non-blocking viewport/SwapChain readiness must not detect production character asset mutation."),
        ("asset_cache_deleted", "Non-blocking viewport/SwapChain readiness must not delete Asset Cache."),
        ("cache_heuristic_used", "Non-blocking viewport/SwapChain readiness must not use cache heuristic proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_PATH_UNSAFE, message)

    temp_path = str(report.get("temp_visual_scene_path", "") or report.get("editor_temp_visual_scene_path", ""))
    normalized_temp_path = temp_path.replace("\\", "/").strip()
    if not normalized_temp_path.startswith("Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context"):
        result.add_error(
            MXN_PATH_UNSAFE,
            "Non-blocking viewport/SwapChain readiness temp path must remain under Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context.",
        )
    if "defaultlevel" in normalized_temp_path.lower() or "production" in normalized_temp_path.lower():
        result.add_error(MXN_PATH_UNSAFE, "Non-blocking viewport/SwapChain readiness temp path cannot include defaultlevel or production names.")

    for field, label in {
        "active_default_viewport_probe_attempted": "active/default viewport probe attempted",
        "active_default_viewport_window_handle_attempted": "window-handle probe attempted",
        "active_default_viewport_window_handle_source_validated": "window-handle source validation",
        "atom_swapchain_readiness_probe_attempted": "Atom SwapChain probe attempted",
        "atom_swapchain_readiness_probe_source_validated": "Atom SwapChain source validation",
        "framecapture_target_readiness_attempted": "FrameCapture target probe attempted",
        "framecapture_target_readiness_source_validated": "FrameCapture target source validation",
    }.items():
        if source_validated and report.get(field) is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Source-validated non-blocking probe requires {field} ({label}).")

    if verified:
        if report.get("active_default_viewport_window_handle_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Verified non-blocking probe requires source-validated window-handle readiness.")
        if report.get("atom_swapchain_readiness_probe_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Verified non-blocking probe requires SwapChain readiness.")
        if report.get("framecapture_target_readiness_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Verified non-blocking probe requires FrameCapture target readiness.")
        if blocker:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Verified non-blocking probe must not carry a blocker.")
    elif not blocker:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified non-blocking viewport/SwapChain readiness requires a precise typed blocker.")


def _asset_processor_alignment_preflight_blocker(report: Mapping[str, Any]) -> str:
    if str(report.get("diagnostic_mode", "")).strip() not in {
        "asset-processor-project-build-alignment-repair",
        "operator-run-ap-alignment-remediation-verification",
    }:
        return ""
    live_ready = (
        report.get("live_non_null_editor_launch_verified") is True
        and report.get("temp_visual_scene_context_exercise_verified") is True
        and report.get("safe_temp_visual_scene_context_preserved") is True
    )
    if live_ready:
        return ""
    for field in (
        "asset_processor_alignment_blocker",
        "editor_asset_processor_negotiation_blocker",
        "live_non_null_editor_launch_blocker",
        "non_null_editor_desktop_rhi_readiness_blocker",
        "temp_visual_scene_context_exercise_blocker",
        "temp_visual_scene_blocker",
    ):
        blocker = str(report.get(field, "")).strip()
        if blocker:
            return blocker
    return ""


def _validate_editor_ap_negotiation_viewport_materialization_readiness(
    report: Mapping[str, Any],
    result: ValidationResult,
    *,
    allow_preflight_blocked: bool = False,
) -> None:
    preflight_blocker = _asset_processor_alignment_preflight_blocker(report) if allow_preflight_blocked else ""
    if not preflight_blocker:
        for field, label in {
            "live_non_null_editor_launch_attempted": "live non-null Editor launch attempted",
            "live_non_null_editor_launch_completed": "live non-null Editor launch completed",
            "live_non_null_editor_launch_verified": "live non-null Editor launch verified",
            "live_non_null_editor_launch_python_wrapper_executed": "Editor Python wrapper executed",
            "visible_desktop_session_verified": "visible desktop/session readiness",
            "gpu_or_driver_readiness_verified": "GPU/driver readiness",
            "rhi_readiness_verified": "RHI readiness",
            "temp_visual_scene_context_exercise_verified": "safe temp visual scene context exercise",
            "temp_visual_scene_cleanup_attempted": "temp scene cleanup attempted",
            "temp_visual_scene_cleanup_completed": "temp scene cleanup completed",
            "safe_temp_visual_scene_context_preserved": "safe temp visual scene context preservation",
        }.items():
            if report.get(field) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Editor/AP negotiation readiness requires {label}.")

    if report.get("editor_asset_processor_negotiation_preflight_attempted") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor/AP negotiation preflight must record attempted=true.")
    if report.get("editor_asset_processor_negotiation_source_validated") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor/AP negotiation preflight requires source validation.")
    if not str(report.get("editor_asset_processor_negotiation_state", "")).strip():
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor/AP negotiation preflight requires a state.")
    if (
        report.get("editor_asset_processor_negotiation_preflight_verified") is not True
        and not str(report.get("editor_asset_processor_negotiation_blocker", "")).strip()
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified Editor/AP negotiation preflight requires a blocker.")

    required_attempt_fields = {
        "editor_asset_processor_modal_detection_attempted": "negotiation-failed modal detection",
        "editor_asset_processor_project_alignment_attempted": "AP/Editor project alignment",
        "editor_asset_processor_build_root_alignment_attempted": "AP/Editor build-root alignment",
        "asset_processor_process_inventory_attempted": "Asset Processor process inventory",
    }
    if not preflight_blocker:
        required_attempt_fields.update(
            {
                "viewport_window_materialization_repair_attempted": "viewport/window materialization readiness",
                "active_default_viewport_after_ap_alignment_attempted": "active/default viewport after AP alignment",
                "framecapture_target_after_ap_alignment_attempted": "FrameCapture target after AP alignment",
                "atom_swapchain_after_ap_alignment_attempted": "Atom SwapChain after AP alignment",
            }
        )
    for field, label in required_attempt_fields.items():
        if report.get(field) is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Editor/AP negotiation readiness requires {label}.")

    post_alignment_blocker_fields = (
        (
            "editor_asset_processor_project_alignment_verified",
            "editor_asset_processor_project_alignment_blocker",
            "project alignment",
        ),
        (
            "editor_asset_processor_build_root_alignment_verified",
            "editor_asset_processor_build_root_alignment_blocker",
            "build-root alignment",
        ),
        (
            "viewport_window_materialization_repair_verified",
            "viewport_window_materialization_blocker",
            "viewport/window materialization",
        ),
        (
            "active_default_viewport_after_ap_alignment_verified",
            "active_default_viewport_after_ap_alignment_blocker",
            "active/default viewport after AP alignment",
        ),
        (
            "framecapture_target_after_ap_alignment_verified",
            "framecapture_target_after_ap_alignment_blocker",
            "FrameCapture target after AP alignment",
        ),
        (
            "atom_swapchain_after_ap_alignment_verified",
            "atom_swapchain_after_ap_alignment_blocker",
            "Atom SwapChain after AP alignment",
        ),
    )
    if preflight_blocker:
        post_alignment_blocker_fields = post_alignment_blocker_fields[:2]
    for field, blocker_field, label in post_alignment_blocker_fields:
        if report.get(field) is not True and not str(report.get(blocker_field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Unverified {label} requires a typed blocker.")

    for inventory_field in ("editor_process_inventory_sanitized", "asset_processor_process_inventory_sanitized"):
        entries = report.get(inventory_field, [])
        if not isinstance(entries, list):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{inventory_field} must be a sanitized list.")
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{inventory_field} entries must be objects.")
                continue
            if "command_line" in entry:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Process inventory must not emit raw command lines.")
            if entry.get("raw_command_line_emitted") is True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Process inventory must mark raw command lines as redacted.")

    for field, message in (
        ("editor_visual_material_capture_requested", "Editor/AP negotiation readiness must not request screenshot/frame capture."),
        ("editor_visual_material_capture_request_accepted", "Editor/AP negotiation readiness must not accept screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Editor/AP negotiation readiness cannot claim screenshot/frame capture completion."),
        ("visual_material_capture_readiness_verified", "Editor/AP negotiation readiness cannot verify screenshot artifact readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Editor/AP negotiation readiness must not attempt rendered visual evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Editor/AP negotiation readiness cannot verify rendered visual evidence."),
        ("visual_material_gate_claimed", "Editor/AP negotiation readiness cannot claim visual/material proof."),
        ("visual_material_gate_verified", "Editor/AP negotiation readiness cannot verify visual/material proof."),
        ("runtime_character_proof_claimed", "Editor/AP negotiation readiness cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Editor/AP negotiation readiness cannot verify full runtime character proof."),
        ("asset_cache_deleted", "Editor/AP negotiation readiness must not delete Asset Cache."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)

    for field, message in (
        ("defaultlevel_mutation", "Editor/AP negotiation readiness must not mutate defaultlevel."),
        ("production_level_mutation", "Editor/AP negotiation readiness must not mutate production levels."),
        ("editor_temp_visual_scene_defaultlevel_mutation", "Editor/AP negotiation readiness must not mutate defaultlevel."),
        ("editor_temp_visual_scene_production_level_mutation", "Editor/AP negotiation readiness must not mutate production levels."),
        ("defaultlevel_mutation_detected", "Editor/AP negotiation readiness must not detect defaultlevel mutation."),
        ("production_level_mutation_detected", "Editor/AP negotiation readiness must not detect production-level mutation."),
        ("production_character_asset_mutation_detected", "Editor/AP negotiation readiness must not mutate production character assets."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)

    temp_path = str(report.get("temp_visual_scene_path", "") or report.get("editor_temp_visual_scene_path", ""))
    normalized_temp_path = temp_path.replace("\\", "/").strip()
    if normalized_temp_path and not normalized_temp_path.startswith(
        "Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context"
    ):
        result.add_error(
            MXN_PATH_UNSAFE,
            "Editor/AP negotiation temp path must remain under Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context.",
        )
    if not preflight_blocker and not normalized_temp_path:
        result.add_error(
            MXN_PATH_UNSAFE,
            "Editor/AP negotiation temp path must remain under Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context.",
        )
    if "defaultlevel" in normalized_temp_path.lower() or "production" in normalized_temp_path.lower():
        result.add_error(MXN_PATH_UNSAFE, "Editor/AP negotiation temp path cannot include defaultlevel or production names.")


def _validate_asset_processor_project_build_alignment_repair(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    _validate_editor_ap_negotiation_viewport_materialization_readiness(
        report,
        result,
        allow_preflight_blocked=True,
    )
    preflight_blocker = _asset_processor_alignment_preflight_blocker(report)
    for field, label in {
        "asset_processor_alignment_repair_attempted": "AP alignment repair/safe-block attempted",
        "asset_processor_alignment_source_validated": "AP alignment source validation",
        "asset_processor_process_inventory_attempted": "AP process inventory",
        "asset_processor_executable_path_alignment_attempted": "AP executable path alignment",
        "asset_processor_project_alignment_attempted": "AP project path alignment",
        "asset_processor_build_root_alignment_attempted": "AP build-root alignment",
        "asset_processor_branch_project_token_alignment_attempted": "AP branch/project token boundary",
    }.items():
        if report.get(field) is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"AP alignment repair diagnostic requires {label}.")
    if not preflight_blocker and report.get("viewport_window_materialization_after_ap_alignment_attempted") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "AP alignment repair diagnostic requires viewport/window materialization after AP alignment.",
        )

    for field in (
        "asset_processor_alignment_state",
        "asset_processor_target_engine_root",
        "asset_processor_target_build_root",
        "asset_processor_target_project_path",
        "asset_processor_target_executable_path",
        "asset_processor_target_project_name",
        "asset_processor_repair_mode",
    ):
        if not str(report.get(field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"AP alignment repair diagnostic requires {field}.")

    if (
        report.get("asset_processor_alignment_repair_verified") is not True
        and not str(report.get("asset_processor_alignment_blocker", "")).strip()
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified AP alignment repair requires a typed blocker.")
    alignment_blocker_fields = (
        (
            "asset_processor_project_alignment_verified",
            "asset_processor_project_alignment_blocker",
            "AP project alignment",
        ),
        (
            "asset_processor_build_root_alignment_verified",
            "asset_processor_build_root_alignment_blocker",
            "AP build-root alignment",
        ),
        (
            "asset_processor_branch_project_token_alignment_verified",
            "asset_processor_branch_project_token_alignment_blocker",
            "AP branch/project token alignment",
        ),
        (
            "viewport_window_materialization_after_ap_alignment_verified",
            "viewport_window_materialization_after_ap_alignment_blocker",
            "viewport/window materialization after AP alignment",
        ),
    )
    if preflight_blocker:
        alignment_blocker_fields = alignment_blocker_fields[:3]
    for field, blocker_field, label in alignment_blocker_fields:
        if report.get(field) is not True and not str(report.get(blocker_field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Unverified {label} requires a typed blocker.")

    if report.get("asset_processor_operator_remediation_available") is True:
        command = str(report.get("asset_processor_operator_remediation_command_sanitized", ""))
        command_lower = command.lower()
        if "--project-path" not in command_lower or "--engine-path" not in command_lower or "assetprocessor.exe" not in command_lower:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "AP alignment operator remediation must include sanitized AssetProcessor.exe, --engine-path, and --project-path.",
            )
    for inventory_field in ("asset_processor_process_inventory_sanitized", "editor_process_inventory_sanitized"):
        entries = report.get(inventory_field, [])
        if not isinstance(entries, list):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{inventory_field} must be a sanitized list.")
            continue
        for entry in entries:
            if isinstance(entry, Mapping) and ("command_line" in entry or entry.get("raw_command_line_emitted") is True):
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "AP alignment process inventory must not emit raw command lines.")

    for field, message in (
        ("asset_cache_deletion_attempted", "AP alignment repair must not delete Asset Cache."),
        ("asset_processor_database_wipe_attempted", "AP alignment repair must not wipe Asset Processor databases."),
        ("asset_cache_deleted", "AP alignment repair must not delete Asset Cache."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)


def _validate_operator_ap_alignment_remediation_verification(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    _validate_asset_processor_project_build_alignment_repair(report, result)
    for field, label in {
        "operator_ap_alignment_remediation_verification_attempted": "operator remediation verification attempt",
        "editor_asset_processor_negotiation_after_operator_remediation_attempted": (
            "Editor/AP negotiation after operator remediation"
        ),
    }.items():
        if report.get(field) is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Operator AP remediation verification requires {label}.")

    state = str(report.get("operator_ap_alignment_remediation_state", "")).strip()
    if not state:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Operator AP remediation verification requires operator_ap_alignment_remediation_state.")
    source_unavailable = (
        report.get("operator_ap_alignment_remediation_source_validated") is False
        or state == "blocked_by_operator_ap_alignment_verification_source_validation_unavailable"
    )
    command = str(report.get("operator_ap_alignment_remediation_command_sanitized", "")).strip()
    command_available = report.get("operator_ap_alignment_remediation_command_available") is True
    if not source_unavailable:
        if not command_available:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Operator AP remediation verification requires operator remediation command availability.")
        if not command:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Operator AP remediation verification requires operator_ap_alignment_remediation_command_sanitized.")
    elif command_available and not command:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Operator AP remediation command availability requires a sanitized command.")

    if (
        report.get("operator_ap_alignment_remediation_verification_verified") is True
        and report.get("asset_processor_alignment_repair_verified") is not True
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Operator AP remediation cannot verify unless AP project/build alignment is verified.",
        )
    if (
        report.get("operator_ap_alignment_remediation_verification_verified") is not True
        and not str(report.get("operator_ap_alignment_remediation_blocker", "")).strip()
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Unverified operator AP remediation requires a typed blocker.",
        )

    if report.get("operator_ap_alignment_remediation_appears_applied") is True and (
        report.get("asset_processor_project_alignment_verified") is not True
        or report.get("asset_processor_build_root_alignment_verified") is not True
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Operator AP remediation cannot appear applied without verified AP project/build alignment.",
        )

    if report.get("operator_ap_alignment_remediation_verification_verified") is not True and not source_unavailable:
        next_steps = report.get("operator_ap_alignment_remediation_next_steps", [])
        if not isinstance(next_steps, list) or not next_steps:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Blocked operator AP remediation verification requires structured next steps.",
            )

    if report.get("asset_processor_launch_if_missing_attempted") is True:
        if report.get("asset_processor_launch_if_missing_allowed") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "AP launch-if-missing cannot be attempted unless explicitly allowed.",
            )
        if report.get("asset_processor_mismatched_process_running") is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "AP launch-if-missing cannot run while a mismatched AP process is present.",
            )

    for field, message in (
        ("asset_cache_deletion_attempted", "Operator AP remediation verification must not delete Asset Cache."),
        ("asset_processor_database_wipe_attempted", "Operator AP remediation verification must not wipe AP databases."),
        ("asset_cache_deleted", "Operator AP remediation verification must not delete Asset Cache."),
        ("editor_visual_material_capture_requested", "Operator AP remediation verification must not request screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Operator AP remediation verification cannot claim screenshot/frame capture completion."),
        ("visual_material_gate_verified", "Operator AP remediation verification cannot verify visual/material proof."),
        ("runtime_character_proof_verified", "Operator AP remediation verification cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)


def _validate_focused_editor_viewport_materialization(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    _validate_operator_ap_alignment_remediation_verification(report, result)
    source_blocked = (
        report.get("focused_viewport_materialization_source_validated") is False
        or str(report.get("focused_viewport_materialization_state", "")).strip()
        == "blocked_by_focused_viewport_materialization_source_validation_unavailable"
    )
    preconditions_verified = (
        report.get("ap_alignment_preserved") is True
        and report.get("editor_asset_processor_negotiation_preserved") is True
        and report.get("operator_ap_alignment_remediation_verification_verified") is True
        and report.get("safe_temp_visual_scene_context_preserved") is True
        and report.get("temp_visual_scene_context_exercise_verified") is True
        and report.get("temp_visual_scene_cleanup_completed") is True
    )
    precondition_blocked = not source_blocked and not preconditions_verified
    if not source_blocked and report.get("focused_viewport_materialization_attempted") is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Focused viewport materialization requires focused viewport materialization attempt.",
        )
    for field, label in {
        "editor_modal_detection_attempted": "bounded modal detection",
        "active_default_viewport_after_materialization_attempted": "active/default viewport after materialization",
        "active_default_viewport_window_handle_after_materialization_attempted": (
            "active/default viewport window-handle after materialization"
        ),
        "atom_swapchain_after_viewport_materialization_attempted": "Atom SwapChain after materialization",
        "framecapture_target_after_viewport_materialization_attempted": (
            "FrameCapture target after materialization"
        ),
    }.items():
        if not source_blocked and not precondition_blocked and report.get(field) is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Focused viewport materialization requires {label}.")

    if not source_blocked and not precondition_blocked:
        for field, label in {
            "focused_viewport_materialization_source_validated": "focused viewport source validation",
            "ap_alignment_preserved": "AP alignment preservation",
            "editor_asset_processor_negotiation_preserved": "Editor/AP negotiation preservation",
            "operator_ap_alignment_remediation_verification_verified": "operator AP remediation verification",
            "safe_temp_visual_scene_context_preserved": "safe temp visual scene preservation",
            "temp_visual_scene_context_exercise_verified": "safe temp visual scene exercise",
            "temp_visual_scene_cleanup_completed": "safe temp visual scene cleanup",
        }.items():
            if report.get(field) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Focused viewport materialization requires {label}.")

    if not str(report.get("focused_viewport_materialization_state", "")).strip():
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Focused viewport materialization requires a state.")
    if (
        report.get("focused_viewport_materialization_verified") is not True
        and not str(report.get("focused_viewport_materialization_blocker", "")).strip()
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified focused viewport materialization requires a typed blocker.")

    readiness_fields = (
        (
            "editor_main_window_discovery_verified",
            "editor_main_window_discovery_blocker",
            "Editor main-window discovery",
        ),
        (
            "editor_main_window_activation_verified",
            "editor_main_window_activation_blocker",
            "Editor main-window activation",
        ),
        (
            "default_viewport_pane_discovery_verified",
            "default_viewport_pane_discovery_blocker",
            "default viewport pane discovery",
        ),
        (
            "default_viewport_pane_activation_verified",
            "default_viewport_pane_activation_blocker",
            "default viewport pane activation",
        ),
        (
            "default_viewport_widget_discovery_verified",
            "default_viewport_widget_discovery_blocker",
            "default viewport widget discovery",
        ),
        (
            "active_default_viewport_after_materialization_verified",
            "active_default_viewport_after_materialization_blocker",
            "active/default viewport after materialization",
        ),
        (
            "active_default_viewport_window_handle_after_materialization_verified",
            "active_default_viewport_window_handle_after_materialization_blocker",
            "active/default viewport window handle after materialization",
        ),
        (
            "atom_swapchain_after_viewport_materialization_verified",
            "atom_swapchain_after_viewport_materialization_blocker",
            "Atom SwapChain after viewport materialization",
        ),
        (
            "framecapture_target_after_viewport_materialization_verified",
            "framecapture_target_after_viewport_materialization_blocker",
            "FrameCapture target after viewport materialization",
        ),
    )
    if source_blocked or precondition_blocked:
        readiness_fields = ()
    for field, blocker_field, label in readiness_fields:
        if report.get(field) is not True and not str(report.get(blocker_field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Unverified {label} requires a typed blocker.")

    if report.get("focused_viewport_materialization_verified") is True:
        for field, label in {
            "editor_main_window_discovery_verified": "main-window discovery",
            "editor_main_window_activation_verified": "main-window activation",
            "default_viewport_widget_discovery_verified": "default viewport widget discovery",
            "default_viewport_pane_activation_verified": "default viewport pane/widget activation",
            "viewport_event_loop_idle_wait_completed": "Qt event-loop idle wait",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Focused viewport materialization verified=true requires {label}.",
                )

    for inventory_field in (
        "editor_main_window_materialization_evidence",
        "default_viewport_materialization_evidence",
        "atom_swapchain_after_viewport_materialization_evidence",
    ):
        evidence = report.get(inventory_field)
        if isinstance(evidence, Mapping):
            serialized_keys = set(evidence.keys())
            if "command_line" in serialized_keys or "environment" in serialized_keys:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Focused viewport evidence must not emit raw command lines or environment dumps.")
            for entry in evidence.get("sanitized_windows", []) or evidence.get("sanitized_widgets", []) or []:
                if isinstance(entry, Mapping) and (
                    entry.get("raw_title_emitted") is True
                    or entry.get("raw_object_name_emitted") is True
                    or "command_line" in entry
                ):
                    result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Focused viewport evidence must keep window/widget data sanitized.")

    for field, message in (
        ("asset_cache_deletion_attempted", "Focused viewport materialization must not delete Asset Cache."),
        ("asset_processor_database_wipe_attempted", "Focused viewport materialization must not wipe AP databases."),
        ("asset_cache_deleted", "Focused viewport materialization must not delete Asset Cache."),
        ("editor_visual_material_capture_requested", "Focused viewport materialization must not request screenshot/frame capture."),
        ("editor_visual_material_capture_request_accepted", "Focused viewport materialization must not accept screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Focused viewport materialization cannot claim screenshot/frame capture completion."),
        ("visual_material_capture_readiness_verified", "Focused viewport materialization cannot verify screenshot artifact readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Focused viewport materialization must not attempt rendered visual evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Focused viewport materialization cannot verify rendered visual evidence."),
        ("visual_material_gate_claimed", "Focused viewport materialization cannot claim visual/material proof."),
        ("visual_material_gate_verified", "Focused viewport materialization cannot verify visual/material proof."),
        ("runtime_character_proof_claimed", "Focused viewport materialization cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Focused viewport materialization cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)


def _validate_editor_main_window_activation_deep_dive(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    _validate_focused_editor_viewport_materialization(report, result)
    source_blocked = (
        report.get("editor_main_window_activation_deep_dive_source_validated") is False
        or str(report.get("editor_main_window_activation_deep_dive_state", "")).strip()
        == "blocked_by_editor_main_window_activation_source_validation_unavailable"
    )
    preconditions_verified = (
        report.get("ap_alignment_preserved") is True
        and report.get("editor_asset_processor_negotiation_preserved") is True
        and report.get("operator_ap_alignment_remediation_verification_verified") is True
        and report.get("safe_temp_visual_scene_context_preserved") is True
        and report.get("temp_visual_scene_context_exercise_verified") is True
        and report.get("temp_visual_scene_cleanup_completed") is True
    )
    precondition_blocked = not source_blocked and not preconditions_verified
    if not source_blocked and report.get("editor_main_window_activation_deep_dive_attempted") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor main-window deep dive requires an attempted diagnostic.")
    if not str(report.get("editor_main_window_activation_deep_dive_state", "")).strip():
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor main-window deep dive requires a state.")
    if (
        report.get("editor_main_window_activation_deep_dive_verified") is not True
        and not str(report.get("editor_main_window_activation_deep_dive_blocker", "")).strip()
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified Editor main-window deep dive requires a typed blocker.")

    if not source_blocked and not precondition_blocked:
        for field, label in {
            "editor_modal_detection_attempted": "bounded modal detection",
            "editor_main_window_candidate_inventory_attempted": "main-window inventory",
            "editor_main_window_candidate_classification_attempted": "main-window candidate classification",
            "alternate_viewport_materialization_path_attempted": "alternate viewport materialization path",
            "active_default_viewport_after_main_window_deep_dive_attempted": (
                "active/default viewport after main-window deep dive"
            ),
            "active_default_viewport_window_handle_after_main_window_deep_dive_attempted": (
                "active/default viewport window handle after main-window deep dive"
            ),
            "atom_swapchain_after_main_window_deep_dive_attempted": (
                "Atom SwapChain after main-window deep dive"
            ),
            "framecapture_target_after_main_window_deep_dive_attempted": (
                "FrameCapture target after main-window deep dive"
            ),
        }.items():
            if report.get(field) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Editor main-window deep dive requires {label}.")

    inventory = report.get("editor_main_window_candidate_inventory_sanitized", [])
    if not source_blocked and not precondition_blocked and not isinstance(inventory, list):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor main-window inventory must be a sanitized list.")
    if isinstance(inventory, list):
        for entry in inventory:
            if not isinstance(entry, Mapping):
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor main-window inventory entries must be sanitized objects.")
                continue
            if (
                entry.get("raw_title_emitted") is True
                or entry.get("raw_object_name_emitted") is True
                or "command_line" in entry
                or "environment" in entry
                or "window_title" in entry
                or "object_name" in entry
            ):
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor main-window inventory must not emit raw window/object/process data.")

    hidden_count = int(report.get("editor_main_window_hidden_candidate_count", 0) or 0)
    minimized_count = int(report.get("editor_main_window_minimized_candidate_count", 0) or 0)
    eligible_count = int(report.get("editor_main_window_activation_eligible_candidate_count", 0) or 0)
    if hidden_count + minimized_count > 0 and eligible_count == 0:
        if report.get("editor_main_window_hidden_candidate_show_allowed") is not False:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Editor main-window deep dive must block hidden/minimized show/raise/activate without a source-validated safe path.",
            )
        if not str(report.get("editor_main_window_hidden_candidate_show_blocker", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Blocked hidden main-window show policy requires a typed blocker.")

    if report.get("editor_main_window_activation_deep_dive_verified") is True:
        for field, label in {
            "editor_main_window_candidate_classification_verified": "main-window candidate classification",
            "editor_main_window_activation_verified": "main-window activation",
            "editor_main_window_materialization_verified": "main-window materialization",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Editor main-window deep dive verified=true requires {label}.",
                )
        if eligible_count <= 0:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Editor main-window deep dive verified=true requires an activation-eligible visible candidate.",
            )

    readiness_fields = (
        (
            "default_viewport_pane_discovery_after_main_window_deep_dive_verified",
            "default_viewport_pane_discovery_after_main_window_deep_dive_blocker",
            "default viewport pane discovery after main-window deep dive",
        ),
        (
            "default_viewport_pane_activation_after_main_window_deep_dive_verified",
            "default_viewport_pane_activation_after_main_window_deep_dive_blocker",
            "default viewport pane activation after main-window deep dive",
        ),
        (
            "default_viewport_widget_discovery_after_main_window_deep_dive_verified",
            "default_viewport_widget_discovery_after_main_window_deep_dive_blocker",
            "default viewport widget discovery after main-window deep dive",
        ),
        (
            "active_default_viewport_after_main_window_deep_dive_verified",
            "active_default_viewport_after_main_window_deep_dive_blocker",
            "active/default viewport after main-window deep dive",
        ),
        (
            "active_default_viewport_window_handle_after_main_window_deep_dive_verified",
            "active_default_viewport_window_handle_after_main_window_deep_dive_blocker",
            "active/default viewport window handle after main-window deep dive",
        ),
        (
            "atom_swapchain_after_main_window_deep_dive_verified",
            "atom_swapchain_after_main_window_deep_dive_blocker",
            "Atom SwapChain after main-window deep dive",
        ),
        (
            "framecapture_target_after_main_window_deep_dive_verified",
            "framecapture_target_after_main_window_deep_dive_blocker",
            "FrameCapture target after main-window deep dive",
        ),
    )
    if source_blocked or precondition_blocked:
        readiness_fields = ()
    for field, blocker_field, label in readiness_fields:
        if report.get(field) is not True and not str(report.get(blocker_field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Unverified {label} requires a typed blocker.")

    for field, message in (
        ("asset_cache_deletion_attempted", "Editor main-window deep dive must not delete Asset Cache."),
        ("asset_processor_database_wipe_attempted", "Editor main-window deep dive must not wipe AP databases."),
        ("asset_cache_deleted", "Editor main-window deep dive must not delete Asset Cache."),
        ("editor_visual_material_capture_requested", "Editor main-window deep dive must not request screenshot/frame capture."),
        ("editor_visual_material_capture_request_accepted", "Editor main-window deep dive must not accept screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Editor main-window deep dive cannot claim screenshot/frame capture completion."),
        ("visual_material_capture_readiness_verified", "Editor main-window deep dive cannot verify screenshot artifact readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Editor main-window deep dive must not attempt rendered visual evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Editor main-window deep dive cannot verify rendered visual evidence."),
        ("visual_material_gate_claimed", "Editor main-window deep dive cannot claim visual/material proof."),
        ("visual_material_gate_verified", "Editor main-window deep dive cannot verify visual/material proof."),
        ("runtime_character_proof_claimed", "Editor main-window deep dive cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Editor main-window deep dive cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)


def _validate_sanitized_window_inventory(
    inventory: Any,
    result: ValidationResult,
    *,
    label: str,
) -> None:
    if not isinstance(inventory, list):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{label} must be a sanitized list.")
        return
    forbidden_keys = {
        "window_title",
        "object_name",
        "command_line",
        "environment",
        "native_handle",
        "handle",
    }
    for entry in inventory:
        if not isinstance(entry, Mapping):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{label} entries must be sanitized objects.")
            continue
        if (
            entry.get("raw_title_emitted") is True
            or entry.get("raw_object_name_emitted") is True
            or entry.get("raw_native_handle_emitted") is True
            or any(key in entry for key in forbidden_keys)
        ):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{label} must not emit raw window/object/process data.")


def _validate_alternate_editor_window_discovery_visible_shell(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    _validate_editor_main_window_activation_deep_dive(report, result)
    source_blocked = (
        report.get("alternate_editor_window_discovery_source_validated") is False
        or str(report.get("alternate_editor_window_discovery_state", "")).strip()
        == "blocked_by_alternate_editor_window_discovery_source_validation_unavailable"
    )
    preconditions_verified = (
        report.get("ap_alignment_preserved") is True
        and report.get("editor_asset_processor_negotiation_preserved") is True
        and report.get("operator_ap_alignment_remediation_verification_verified") is True
        and report.get("safe_temp_visual_scene_context_preserved") is True
        and report.get("temp_visual_scene_context_exercise_verified") is True
        and report.get("temp_visual_scene_cleanup_completed") is True
    )
    precondition_blocked = not source_blocked and not preconditions_verified

    if not source_blocked and report.get("alternate_editor_window_discovery_attempted") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Alternate Editor window discovery requires an attempted diagnostic.")
    if not str(report.get("alternate_editor_window_discovery_state", "")).strip():
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Alternate Editor window discovery requires a state.")
    if (
        report.get("alternate_editor_window_discovery_verified") is not True
        and not str(report.get("alternate_editor_window_discovery_blocker", "")).strip()
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified alternate Editor window discovery requires a typed blocker.")

    if not source_blocked and not precondition_blocked:
        for field, label in {
            "editor_modal_detection_attempted": "bounded modal detection",
            "qt_top_level_widget_inventory_attempted": "sanitized Qt top-level inventory",
            "hidden_editor_shell_candidate_classification_attempted": "hidden Editor shell candidate classification",
            "visible_editor_shell_discovery_attempted": "visible Editor shell discovery",
            "visible_editor_shell_candidate_classification_attempted": "visible Editor shell candidate classification",
            "default_viewport_widget_discovery_after_visible_shell_attempted": (
                "default viewport widget discovery after visible shell"
            ),
            "active_default_viewport_after_visible_shell_attempted": "active/default viewport after visible shell",
            "active_default_viewport_window_handle_after_visible_shell_attempted": (
                "active/default viewport window handle after visible shell"
            ),
            "atom_swapchain_after_visible_shell_attempted": "Atom SwapChain after visible shell",
            "framecapture_target_after_visible_shell_attempted": "FrameCapture target after visible shell",
        }.items():
            if report.get(field) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Alternate Editor window discovery requires {label}.")

    if not source_blocked and not precondition_blocked:
        qt_inventory = report.get("qt_top_level_widget_inventory_sanitized", [])
        _validate_sanitized_window_inventory(
            qt_inventory,
            result,
            label="alternate Editor window inventory",
        )
        _validate_sanitized_window_inventory(
            report.get("native_editor_window_inventory_sanitized", []),
            result,
            label="native window inventory",
        )
        for entry in (qt_inventory if isinstance(qt_inventory, list) else []):
            if (
                isinstance(entry, Mapping)
                and entry.get("materialization_eligible") is True
                and entry.get("editor_shell_identity_source_validated") is not True
            ):
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    "Materialization-eligible visible Editor shell candidates require source-validated Editor-shell identity.",
                )

    hidden_count = int(report.get("qt_hidden_top_level_widget_count", 0) or 0)
    if hidden_count > 0:
        if report.get("hidden_editor_shell_candidate_show_allowed") is not False:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Alternate Editor window discovery must block hidden show/raise/activate without a source-validated visible Editor shell.",
            )
        if not str(report.get("hidden_editor_shell_candidate_show_blocker", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Blocked hidden Editor shell show policy requires a typed blocker.")

    if report.get("visible_editor_shell_discovery_verified") is True:
        if int(report.get("visible_editor_shell_candidate_count", 0) or 0) <= 0:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Visible Editor shell discovery verified=true requires a visible shell candidate count.",
            )
        if report.get("visible_editor_shell_candidate_classification_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Visible Editor shell discovery verified=true requires candidate classification evidence.",
            )
        qt_inventory = report.get("qt_top_level_widget_inventory_sanitized", [])
        has_source_validated_visible_shell = any(
            isinstance(entry, Mapping)
            and entry.get("visible") is True
            and entry.get("likely_editor_shell") is True
            and entry.get("materialization_eligible") is True
            and entry.get("editor_shell_identity_source_validated") is True
            for entry in (qt_inventory if isinstance(qt_inventory, list) else [])
        )
        if not has_source_validated_visible_shell:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Visible Editor shell discovery verified=true requires sanitized source-validated Editor-shell identity evidence.",
            )
    elif not source_blocked and not precondition_blocked:
        if not str(report.get("visible_editor_shell_discovery_blocker", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified visible Editor shell discovery requires a typed blocker.")

    if report.get("visible_editor_shell_materialization_verified") is True:
        for field, label in {
            "visible_editor_shell_discovery_verified": "visible Editor shell discovery",
            "visible_editor_shell_materialization_attempted": "visible Editor shell materialization attempt",
            "visible_editor_shell_materialization_source_validated": "visible Editor shell materialization source validation",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Visible Editor shell materialization verified=true requires {label}.",
                )
    elif not source_blocked and not precondition_blocked:
        if not str(report.get("visible_editor_shell_materialization_blocker", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified visible Editor shell materialization requires a typed blocker.")

    readiness_fields = (
        (
            "default_viewport_pane_discovery_after_visible_shell_verified",
            "default_viewport_pane_discovery_after_visible_shell_blocker",
            "default viewport pane discovery after visible shell",
        ),
        (
            "default_viewport_pane_activation_after_visible_shell_verified",
            "default_viewport_pane_activation_after_visible_shell_blocker",
            "default viewport pane activation after visible shell",
        ),
        (
            "default_viewport_widget_discovery_after_visible_shell_verified",
            "default_viewport_widget_discovery_after_visible_shell_blocker",
            "default viewport widget discovery after visible shell",
        ),
        (
            "active_default_viewport_after_visible_shell_verified",
            "active_default_viewport_after_visible_shell_blocker",
            "active/default viewport after visible shell",
        ),
        (
            "active_default_viewport_window_handle_after_visible_shell_verified",
            "active_default_viewport_window_handle_after_visible_shell_blocker",
            "active/default viewport window handle after visible shell",
        ),
        (
            "atom_swapchain_after_visible_shell_verified",
            "atom_swapchain_after_visible_shell_blocker",
            "Atom SwapChain after visible shell",
        ),
        (
            "framecapture_target_after_visible_shell_verified",
            "framecapture_target_after_visible_shell_blocker",
            "FrameCapture target after visible shell",
        ),
    )
    if source_blocked or precondition_blocked:
        readiness_fields = ()
    for field, blocker_field, label in readiness_fields:
        if report.get(field) is not True and not str(report.get(blocker_field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Unverified {label} requires a typed blocker.")

    for field, message in (
        ("asset_cache_deletion_attempted", "Alternate Editor window discovery must not delete Asset Cache."),
        ("asset_processor_database_wipe_attempted", "Alternate Editor window discovery must not wipe AP databases."),
        ("asset_cache_deleted", "Alternate Editor window discovery must not delete Asset Cache."),
        ("editor_visual_material_capture_requested", "Alternate Editor window discovery must not request screenshot/frame capture."),
        ("editor_visual_material_capture_request_accepted", "Alternate Editor window discovery must not accept screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Alternate Editor window discovery cannot claim screenshot/frame capture completion."),
        ("visual_material_capture_readiness_verified", "Alternate Editor window discovery cannot verify screenshot artifact readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Alternate Editor window discovery must not attempt rendered visual evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Alternate Editor window discovery cannot verify rendered visual evidence."),
        ("visual_material_gate_claimed", "Alternate Editor window discovery cannot claim visual/material proof."),
        ("visual_material_gate_verified", "Alternate Editor window discovery cannot verify visual/material proof."),
        ("runtime_character_proof_claimed", "Alternate Editor window discovery cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Alternate Editor window discovery cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)


def _validate_editor_layout_bootstrap_window_lifecycle(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    _validate_alternate_editor_window_discovery_visible_shell(report, result)
    source_blocked = (
        report.get("editor_layout_bootstrap_lifecycle_source_validated") is False
        or str(report.get("editor_layout_bootstrap_lifecycle_state", "")).strip()
        == "blocked_by_editor_layout_bootstrap_lifecycle_source_validation_unavailable"
    )
    preconditions_verified = (
        report.get("ap_alignment_preserved") is True
        and report.get("editor_asset_processor_negotiation_preserved") is True
        and report.get("operator_ap_alignment_remediation_verification_verified") is True
        and report.get("safe_temp_visual_scene_context_preserved") is True
        and report.get("temp_visual_scene_context_exercise_verified") is True
        and report.get("temp_visual_scene_cleanup_completed") is True
    )
    precondition_blocked = not source_blocked and not preconditions_verified

    if not source_blocked and report.get("editor_layout_bootstrap_lifecycle_deep_dive_attempted") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor layout/bootstrap lifecycle requires an attempted diagnostic.")
    if not str(report.get("editor_layout_bootstrap_lifecycle_state", "")).strip():
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor layout/bootstrap lifecycle requires a state.")
    if (
        report.get("editor_layout_bootstrap_lifecycle_deep_dive_verified") is not True
        and not str(report.get("editor_layout_bootstrap_lifecycle_blocker", "")).strip()
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified Editor layout/bootstrap lifecycle requires a typed blocker.")

    if report.get("editor_layout_mutation_attempted") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor layout/bootstrap lifecycle must not mutate Editor layout.")
    if report.get("editor_user_layout_mutation_attempted") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor layout/bootstrap lifecycle must not mutate Editor layout or user layout settings.")

    launch = report.get("editor_launch_command_classification_sanitized")
    if not isinstance(launch, Mapping):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor layout/bootstrap lifecycle requires sanitized launch command classification.")
    else:
        if (
            launch.get("raw_command_line_emitted") is True
            or launch.get("raw_environment_emitted") is True
            or "command_line" in launch
            or "environment" in launch
        ):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor layout/bootstrap lifecycle must not emit raw command lines or environment dumps.")

    viewpane_evidence = report.get("editor_viewpane_registration_evidence")
    if isinstance(viewpane_evidence, Mapping) and (
        viewpane_evidence.get("raw_pane_names_emitted") is True
        or "pane_names" in viewpane_evidence
        or "raw_pane_names" in viewpane_evidence
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor layout/bootstrap lifecycle must not emit raw view-pane names.")

    if not source_blocked and not precondition_blocked:
        for field, label in {
            "editor_launch_command_classification_attempted": "launch command classification",
            "editor_launch_visual_lane_flags_classified": "visual lane launch flag classification",
            "editor_automation_script_timing_classification_attempted": "automation script timing classification",
            "editor_bootstrap_stage_classification_attempted": "bootstrap stage classification",
            "editor_initialized_wait_attempted": "Editor initialized wait classification",
            "editor_layout_restore_state_attempted": "layout restore state classification",
            "editor_shell_ready_event_wait_attempted": "shell-ready event wait classification",
            "editor_viewpane_registration_attempted": "ViewPane registration classification",
            "default_viewport_viewpane_registration_attempted": "default viewport ViewPane registration classification",
            "default_viewport_pane_open_state_attempted": "default viewport pane open-state classification",
            "visible_editor_shell_after_lifecycle_wait_attempted": "visible Editor shell after lifecycle wait",
            "default_viewport_widget_discovery_after_lifecycle_attempted": "default viewport widget discovery after lifecycle",
            "active_default_viewport_after_lifecycle_attempted": "active/default viewport after lifecycle",
            "active_default_viewport_window_handle_after_lifecycle_attempted": (
                "active/default viewport window handle after lifecycle"
            ),
            "atom_swapchain_after_lifecycle_attempted": "Atom SwapChain after lifecycle",
            "framecapture_target_after_lifecycle_attempted": "FrameCapture target after lifecycle",
        }.items():
            if report.get(field) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Editor layout/bootstrap lifecycle requires {label}.")

    for field, blocker_field, label in (
        (
            "editor_initialized_wait_verified",
            "editor_initialized_wait_blocker",
            "Editor initialized wait",
        ),
        (
            "editor_layout_restore_state_verified",
            "editor_layout_restore_state_blocker",
            "layout restore state",
        ),
        (
            "editor_run_scoped_layout_override_verified",
            "editor_run_scoped_layout_override_blocker",
            "run-scoped layout override",
        ),
        (
            "editor_shell_ready_event_wait_verified",
            "editor_shell_ready_event_wait_blocker",
            "shell-ready event wait",
        ),
        (
            "editor_viewpane_registration_verified",
            "editor_viewpane_registration_blocker",
            "ViewPane registration",
        ),
        (
            "default_viewport_viewpane_registration_verified",
            "default_viewport_viewpane_registration_blocker",
            "default viewport ViewPane registration",
        ),
        (
            "default_viewport_pane_open_state_verified",
            "default_viewport_pane_open_state_blocker",
            "default viewport pane open state",
        ),
        (
            "visible_editor_shell_after_lifecycle_wait_verified",
            "visible_editor_shell_after_lifecycle_wait_blocker",
            "visible Editor shell after lifecycle wait",
        ),
        (
            "visible_editor_shell_lifecycle_materialization_verified",
            "visible_editor_shell_lifecycle_materialization_blocker",
            "visible Editor shell lifecycle materialization",
        ),
    ):
        if source_blocked or precondition_blocked:
            continue
        if report.get(field) is not True and not str(report.get(blocker_field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Unverified {label} requires a typed blocker.")

    hidden_count = int(report.get("qt_hidden_top_level_widget_count", 0) or 0)
    if hidden_count > 0 or str(report.get("hidden_editor_shell_candidate_lifecycle_state", "")).strip():
        if report.get("hidden_editor_shell_candidate_show_allowed") is not False:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Editor layout/bootstrap lifecycle must block hidden show/raise/activate without a source-validated safe lifecycle path.",
            )
        if not str(report.get("hidden_editor_shell_candidate_show_blocker", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Blocked hidden Editor shell lifecycle policy requires a typed blocker.")

    if report.get("editor_layout_bootstrap_lifecycle_deep_dive_verified") is True:
        for field, label in {
            "visible_editor_shell_after_lifecycle_wait_verified": "visible Editor shell after lifecycle wait",
            "visible_editor_shell_lifecycle_materialization_verified": "visible Editor shell materialization",
            "visible_editor_shell_lifecycle_materialization_source_validated": "visible Editor shell materialization source validation",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Editor layout/bootstrap lifecycle verified=true requires {label}.",
                )

    readiness_fields = (
        (
            "default_viewport_pane_discovery_after_lifecycle_verified",
            "default_viewport_pane_discovery_after_lifecycle_blocker",
            "default viewport pane discovery after lifecycle",
        ),
        (
            "default_viewport_pane_activation_after_lifecycle_verified",
            "default_viewport_pane_activation_after_lifecycle_blocker",
            "default viewport pane activation after lifecycle",
        ),
        (
            "default_viewport_widget_discovery_after_lifecycle_verified",
            "default_viewport_widget_discovery_after_lifecycle_blocker",
            "default viewport widget discovery after lifecycle",
        ),
        (
            "active_default_viewport_after_lifecycle_verified",
            "active_default_viewport_after_lifecycle_blocker",
            "active/default viewport after lifecycle",
        ),
        (
            "active_default_viewport_window_handle_after_lifecycle_verified",
            "active_default_viewport_window_handle_after_lifecycle_blocker",
            "active/default viewport window handle after lifecycle",
        ),
        (
            "atom_swapchain_after_lifecycle_verified",
            "atom_swapchain_after_lifecycle_blocker",
            "Atom SwapChain after lifecycle",
        ),
        (
            "framecapture_target_after_lifecycle_verified",
            "framecapture_target_after_lifecycle_blocker",
            "FrameCapture target after lifecycle",
        ),
    )
    if source_blocked or precondition_blocked:
        readiness_fields = ()
    for field, blocker_field, label in readiness_fields:
        if report.get(field) is not True and not str(report.get(blocker_field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Unverified {label} requires a typed blocker.")

    for field, message in (
        ("asset_cache_deletion_attempted", "Editor layout/bootstrap lifecycle must not delete Asset Cache."),
        ("asset_processor_database_wipe_attempted", "Editor layout/bootstrap lifecycle must not wipe AP databases."),
        ("asset_cache_deleted", "Editor layout/bootstrap lifecycle must not delete Asset Cache."),
        ("screenshot_capture_requested", "Editor layout/bootstrap lifecycle must not request screenshot/frame capture."),
        ("screenshot_capture_completed", "Editor layout/bootstrap lifecycle cannot claim screenshot/frame capture completion."),
        ("editor_visual_material_capture_requested", "Editor layout/bootstrap lifecycle must not request screenshot/frame capture."),
        ("editor_visual_material_capture_request_accepted", "Editor layout/bootstrap lifecycle must not accept screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Editor layout/bootstrap lifecycle cannot claim screenshot/frame capture completion."),
        ("rendered_visual_evidence_claimed", "Editor layout/bootstrap lifecycle cannot claim rendered visual evidence."),
        ("rendered_visual_evidence_verified", "Editor layout/bootstrap lifecycle cannot verify rendered visual evidence."),
        ("visual_material_capture_readiness_verified", "Editor layout/bootstrap lifecycle cannot verify screenshot artifact readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Editor layout/bootstrap lifecycle must not attempt rendered visual evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Editor layout/bootstrap lifecycle cannot verify rendered visual evidence."),
        ("visual_material_gate_claimed", "Editor layout/bootstrap lifecycle cannot claim visual/material proof."),
        ("visual_material_gate_verified", "Editor layout/bootstrap lifecycle cannot verify visual/material proof."),
        ("full_runtime_character_proof_claimed", "Editor layout/bootstrap lifecycle cannot claim full runtime character proof."),
        ("full_runtime_character_proof_verified", "Editor layout/bootstrap lifecycle cannot verify full runtime character proof."),
        ("runtime_character_proof_claimed", "Editor layout/bootstrap lifecycle cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Editor layout/bootstrap lifecycle cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)


def _validate_editor_bootstrap_wait_shell_ready_synchronization(
    report: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    _validate_editor_layout_bootstrap_window_lifecycle(report, result)
    source_blocked = (
        report.get("editor_bootstrap_wait_shell_ready_synchronization_source_validated") is False
        or str(report.get("editor_bootstrap_wait_shell_ready_synchronization_state", "")).strip()
        == "blocked_by_editor_bootstrap_wait_shell_ready_source_validation_unavailable"
    )
    preconditions_verified = (
        report.get("ap_alignment_preserved") is True
        and report.get("editor_asset_processor_negotiation_preserved") is True
        and report.get("operator_ap_alignment_remediation_verification_verified") is True
        and report.get("safe_temp_visual_scene_context_preserved") is True
        and report.get("temp_visual_scene_context_exercise_verified") is True
        and report.get("temp_visual_scene_cleanup_completed") is True
    )
    precondition_blocked = not source_blocked and not preconditions_verified

    if not source_blocked and report.get("editor_bootstrap_wait_shell_ready_synchronization_attempted") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor shell-ready synchronization requires an attempted diagnostic.")
    if not str(report.get("editor_bootstrap_wait_shell_ready_synchronization_state", "")).strip():
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor shell-ready synchronization requires a state.")
    if (
        report.get("editor_bootstrap_wait_shell_ready_synchronization_verified") is not True
        and not str(report.get("editor_bootstrap_wait_shell_ready_synchronization_blocker", "")).strip()
    ):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unverified Editor shell-ready synchronization requires a typed blocker.")

    if report.get("editor_layout_mutation_attempted") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor shell-ready synchronization must not mutate Editor layout.")
    if report.get("editor_user_layout_mutation_attempted") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor shell-ready synchronization must not mutate Editor layout or user layout settings.")

    launch = report.get("editor_launch_command_classification_sanitized")
    if not isinstance(launch, Mapping):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor shell-ready synchronization requires sanitized launch command classification.")
    else:
        if (
            launch.get("raw_command_line_emitted") is True
            or launch.get("raw_environment_emitted") is True
            or "command_line" in launch
            or "environment" in launch
        ):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor shell-ready synchronization must not emit raw command lines or environment dumps.")

    if not source_blocked and not precondition_blocked:
        for field, label in {
            "editor_launch_command_classification_attempted": "launch command classification",
            "editor_launch_visual_lane_flags_classified": "visual lane launch flag classification",
            "editor_automation_script_timing_classification_attempted": "automation script timing classification",
            "editor_deferred_diagnostic_strategy_attempted": "deferred diagnostic strategy classification",
            "editor_late_diagnostic_execution_attempted": "late diagnostic execution classification",
            "editor_qtimer_shell_ready_strategy_attempted": "QTimer shell-ready strategy classification",
            "editor_event_loop_posted_callback_attempted": "event-loop posted callback classification",
            "editor_notify_initialized_wait_attempted": "NotifyEditorInitialized wait classification",
            "editor_app_exec_boundary_wait_attempted": "app->exec boundary wait classification",
            "editor_shell_ready_event_wait_attempted": "shell-ready event wait classification",
            "visible_editor_shell_after_shell_ready_attempted": "visible Editor shell after shell-ready",
            "default_viewport_pane_discovery_after_shell_ready_attempted": "default viewport pane discovery after shell-ready",
            "default_viewport_widget_discovery_after_shell_ready_attempted": "default viewport widget discovery after shell-ready",
            "active_default_viewport_after_shell_ready_attempted": "active/default viewport after shell-ready",
            "active_default_viewport_window_handle_after_shell_ready_attempted": (
                "active/default viewport window handle after shell-ready"
            ),
            "atom_swapchain_after_shell_ready_attempted": "Atom SwapChain after shell-ready",
            "framecapture_target_after_shell_ready_attempted": "FrameCapture target after shell-ready",
        }.items():
            if report.get(field) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Editor shell-ready synchronization requires {label}.")

    for field, blocker_field, label in (
        (
            "editor_deferred_diagnostic_strategy_verified",
            "editor_deferred_diagnostic_strategy_blocker",
            "deferred diagnostic strategy",
        ),
        (
            "editor_late_diagnostic_execution_verified",
            "editor_late_diagnostic_execution_blocker",
            "late diagnostic execution",
        ),
        (
            "editor_qtimer_shell_ready_strategy_verified",
            "editor_qtimer_shell_ready_strategy_blocker",
            "QTimer shell-ready strategy",
        ),
        (
            "editor_event_loop_posted_callback_verified",
            "editor_event_loop_posted_callback_blocker",
            "event-loop posted callback",
        ),
        (
            "editor_notify_initialized_wait_verified",
            "editor_notify_initialized_wait_blocker",
            "NotifyEditorInitialized wait",
        ),
        (
            "editor_app_exec_boundary_wait_verified",
            "editor_app_exec_boundary_wait_blocker",
            "app->exec boundary wait",
        ),
        (
            "editor_shell_ready_event_wait_verified",
            "editor_shell_ready_event_wait_blocker",
            "shell-ready event wait",
        ),
        (
            "editor_layout_restore_state_after_shell_ready_verified",
            "editor_layout_restore_state_after_shell_ready_blocker",
            "layout restore after shell-ready",
        ),
        (
            "visible_editor_shell_after_shell_ready_verified",
            "visible_editor_shell_after_shell_ready_blocker",
            "visible Editor shell after shell-ready",
        ),
        (
            "visible_editor_shell_materialization_after_shell_ready_verified",
            "visible_editor_shell_materialization_after_shell_ready_blocker",
            "visible Editor shell materialization after shell-ready",
        ),
    ):
        if source_blocked or precondition_blocked:
            continue
        if report.get(field) is not True and not str(report.get(blocker_field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Unverified {label} requires a typed blocker.")

    if not source_blocked and not precondition_blocked:
        if report.get("default_viewport_viewpane_registration_preserved") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "Editor shell-ready synchronization must preserve default viewport ViewPane registration evidence.",
            )
        if int(report.get("editor_late_diagnostic_timeout_seconds", 0) or 0) < 1:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Editor shell-ready synchronization requires a bounded late diagnostic timeout.")

    if report.get("editor_late_diagnostic_execution_verified") is True:
        for field, label in {
            "editor_bootstrap_wait_shell_ready_synchronization_verified": "shell-ready synchronization verification",
            "editor_bootstrap_wait_shell_ready_synchronization_source_validated": "shell-ready source validation",
            "editor_late_diagnostic_cleanup_completed": "late diagnostic cleanup completion",
        }.items():
            if report.get(field) is not True:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    f"Late diagnostic execution verified=true requires {label}.",
                )
        if not str(report.get("editor_shell_ready_synchronization_point", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Late diagnostic execution requires a typed synchronization point.")

    readiness_fields = (
        (
            "default_viewport_pane_discovery_after_shell_ready_verified",
            "default_viewport_pane_discovery_after_shell_ready_blocker",
            "default viewport pane discovery after shell-ready",
        ),
        (
            "default_viewport_pane_activation_after_shell_ready_verified",
            "default_viewport_pane_activation_after_shell_ready_blocker",
            "default viewport pane activation after shell-ready",
        ),
        (
            "default_viewport_widget_discovery_after_shell_ready_verified",
            "default_viewport_widget_discovery_after_shell_ready_blocker",
            "default viewport widget discovery after shell-ready",
        ),
        (
            "active_default_viewport_after_shell_ready_verified",
            "active_default_viewport_after_shell_ready_blocker",
            "active/default viewport after shell-ready",
        ),
        (
            "active_default_viewport_window_handle_after_shell_ready_verified",
            "active_default_viewport_window_handle_after_shell_ready_blocker",
            "active/default viewport window handle after shell-ready",
        ),
        (
            "atom_swapchain_after_shell_ready_verified",
            "atom_swapchain_after_shell_ready_blocker",
            "Atom SwapChain after shell-ready",
        ),
        (
            "framecapture_target_after_shell_ready_verified",
            "framecapture_target_after_shell_ready_blocker",
            "FrameCapture target after shell-ready",
        ),
    )
    if source_blocked or precondition_blocked:
        readiness_fields = ()
    for field, blocker_field, label in readiness_fields:
        if report.get(field) is not True and not str(report.get(blocker_field, "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Unverified {label} requires a typed blocker.")

    for field, message in (
        ("asset_cache_deletion_attempted", "Editor shell-ready synchronization must not delete Asset Cache."),
        ("asset_processor_database_wipe_attempted", "Editor shell-ready synchronization must not wipe AP databases."),
        ("asset_cache_deleted", "Editor shell-ready synchronization must not delete Asset Cache."),
        ("screenshot_capture_requested", "Editor shell-ready synchronization must not request screenshot/frame capture."),
        ("screenshot_capture_completed", "Editor shell-ready synchronization cannot claim screenshot/frame capture completion."),
        ("editor_visual_material_capture_requested", "Editor shell-ready synchronization must not request screenshot/frame capture."),
        ("editor_visual_material_capture_request_accepted", "Editor shell-ready synchronization must not accept screenshot/frame capture."),
        ("editor_visual_material_capture_completed", "Editor shell-ready synchronization cannot claim screenshot/frame capture completion."),
        ("rendered_visual_evidence_claimed", "Editor shell-ready synchronization cannot claim rendered visual evidence."),
        ("rendered_visual_evidence_verified", "Editor shell-ready synchronization cannot verify rendered visual evidence."),
        ("visual_material_capture_readiness_verified", "Editor shell-ready synchronization cannot verify screenshot artifact readiness."),
        ("visual_material_rendered_evidence_gate_attempted", "Editor shell-ready synchronization must not attempt rendered visual evidence."),
        ("visual_material_rendered_evidence_gate_verified", "Editor shell-ready synchronization cannot verify rendered visual evidence."),
        ("visual_material_gate_claimed", "Editor shell-ready synchronization cannot claim visual/material proof."),
        ("visual_material_gate_verified", "Editor shell-ready synchronization cannot verify visual/material proof."),
        ("full_runtime_character_proof_claimed", "Editor shell-ready synchronization cannot claim full runtime character proof."),
        ("full_runtime_character_proof_verified", "Editor shell-ready synchronization cannot verify full runtime character proof."),
        ("runtime_character_proof_claimed", "Editor shell-ready synchronization cannot claim full runtime character proof."),
        ("runtime_character_proof_verified", "Editor shell-ready synchronization cannot verify full runtime character proof."),
    ):
        if report.get(field) is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, message)


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


def _normalise_process_path(value: str | Path) -> str:
    return str(value).replace("\\", "/").strip().lower()


def _same_process_path(left: str | Path, right: str | Path) -> bool:
    return _normalise_process_path(left) == _normalise_process_path(right)


def _normalise_command_path_token(value: str | Path) -> str:
    normalized = _normalise_process_path(str(value).strip().strip("\"'"))
    while len(normalized) > 3 and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _display_command_path_token(value: str | Path) -> str:
    normalized = str(value).replace("\\", "/").strip().strip("\"'")
    while len(normalized) > 3 and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _process_command_project_path_values(command_line: str) -> List[str]:
    values: List[str] = []
    for match in re.finditer(
        r"(?i)(?:^|\s)--project-path(?:\s+|=)(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))",
        command_line,
    ):
        value = next((group for group in match.groups() if group), "")
        normalized = _normalise_command_path_token(value)
        if normalized:
            values.append(normalized)
    return values


def _process_command_project_path_matches(command_line: str, path: Path) -> bool:
    expected = _normalise_command_path_token(path)
    return bool(expected and expected in _process_command_project_path_values(command_line))


def _process_command_engine_path_values(command_line: str) -> List[str]:
    values: List[str] = []
    for match in re.finditer(
        r"(?i)(?:^|\s)--engine-path(?:\s+|=)(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))",
        command_line,
    ):
        value = next((group for group in match.groups() if group), "")
        normalized = _normalise_command_path_token(value)
        if normalized:
            values.append(normalized)
    return values


def _process_command_engine_path_matches(command_line: str, path: Path) -> bool:
    expected = _normalise_command_path_token(path)
    return bool(expected and expected in _process_command_engine_path_values(command_line))


def _sanitized_process_entry(
    row: Mapping[str, Any],
    *,
    expected_executable: Path,
    expected_project_path: Path,
    expected_editor_executable: Path,
) -> Dict[str, Any]:
    executable_path = str(row.get("executable_path") or row.get("ExecutablePath") or "").strip()
    command_line = str(row.get("command_line") or row.get("CommandLine") or "").strip()
    process_name = str(row.get("name") or row.get("Name") or Path(executable_path).name).strip()
    expected_build_bin = expected_editor_executable.parent
    project_path_values = _process_command_project_path_values(command_line)
    return {
        "process_name": process_name,
        "executable_basename": Path(executable_path).name if executable_path else "",
        "expected_executable": _same_process_path(executable_path, expected_executable) if executable_path else False,
        "same_build_bin_as_editor": _same_process_path(Path(executable_path).parent, expected_build_bin)
        if executable_path
        else False,
        "command_line_project_path_present": bool(project_path_values),
        "command_line_project_path_matches": _process_command_project_path_matches(command_line, expected_project_path),
        "command_line_redacted": True,
        "raw_command_line_emitted": False,
    }


def _classify_editor_asset_processor_process_inventory(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_project_path: Path,
    expected_editor_executable: Path,
    expected_asset_processor_executable: Path,
) -> Dict[str, Any]:
    editor_rows: List[Mapping[str, Any]] = []
    ap_rows: List[Mapping[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or row.get("Name") or "").lower()
        executable_path = str(row.get("executable_path") or row.get("ExecutablePath") or "").lower()
        if "assetprocessor" in name or executable_path.endswith("assetprocessor.exe"):
            ap_rows.append(row)
        elif "editor" in name or executable_path.endswith("editor.exe") or executable_path.endswith("o3deeditor.exe"):
            editor_rows.append(row)

    sanitized_editors = [
        _sanitized_process_entry(
            row,
            expected_executable=expected_editor_executable,
            expected_project_path=expected_project_path,
            expected_editor_executable=expected_editor_executable,
        )
        for row in editor_rows
    ]
    sanitized_ap = [
        _sanitized_process_entry(
            row,
            expected_executable=expected_asset_processor_executable,
            expected_project_path=expected_project_path,
            expected_editor_executable=expected_editor_executable,
        )
        for row in ap_rows
    ]
    ap_running = bool(sanitized_ap)
    ap_expected_exe = any(entry.get("expected_executable") is True for entry in sanitized_ap)
    ap_same_build = any(entry.get("same_build_bin_as_editor") is True for entry in sanitized_ap)
    project_match = any(entry.get("command_line_project_path_matches") is True for entry in sanitized_ap)
    explicit_project_mismatch = any(
        entry.get("command_line_project_path_present") is True
        and entry.get("command_line_project_path_matches") is not True
        for entry in sanitized_ap
    )
    project_alignment_verified = bool(ap_running and project_match)
    build_alignment_verified = bool(ap_running and ap_expected_exe and ap_same_build)
    if not ap_running:
        project_blocker = "blocked_by_asset_processor_not_running"
        build_blocker = "blocked_by_asset_processor_not_running"
    elif explicit_project_mismatch:
        project_blocker = "blocked_by_editor_asset_processor_project_mismatch"
        build_blocker = "" if build_alignment_verified else "blocked_by_editor_asset_processor_build_root_mismatch"
    elif not project_alignment_verified:
        project_blocker = "blocked_by_editor_asset_processor_project_alignment_unverified"
        build_blocker = "" if build_alignment_verified else "blocked_by_editor_asset_processor_build_root_mismatch"
    else:
        project_blocker = ""
        build_blocker = "" if build_alignment_verified else "blocked_by_editor_asset_processor_build_root_mismatch"

    if not ap_running:
        state = "blocked_by_asset_processor_not_running"
        negotiation_blocker = "blocked_by_asset_processor_not_running"
    elif explicit_project_mismatch:
        state = "blocked_by_editor_asset_processor_project_mismatch"
        negotiation_blocker = "blocked_by_editor_asset_processor_project_mismatch"
    elif not build_alignment_verified:
        state = "blocked_by_editor_asset_processor_build_root_mismatch"
        negotiation_blocker = "blocked_by_editor_asset_processor_build_root_mismatch"
    elif project_alignment_verified:
        state = "verified_editor_asset_processor_negotiation_aligned"
        negotiation_blocker = ""
    else:
        state = "blocked_by_editor_asset_processor_project_alignment_unverified"
        negotiation_blocker = "blocked_by_editor_asset_processor_project_alignment_unverified"

    return {
        "editor_process_inventory_attempted": True,
        "editor_process_inventory_sanitized": sanitized_editors,
        "asset_processor_process_inventory_attempted": True,
        "asset_processor_process_inventory_sanitized": sanitized_ap,
        "asset_processor_process_running": ap_running,
        "asset_processor_process_owner_verified": False,
        "editor_asset_processor_project_alignment_attempted": True,
        "editor_asset_processor_project_alignment_verified": project_alignment_verified,
        "editor_asset_processor_project_alignment_blocker": project_blocker,
        "editor_asset_processor_build_root_alignment_attempted": True,
        "editor_asset_processor_build_root_alignment_verified": build_alignment_verified,
        "editor_asset_processor_build_root_alignment_blocker": build_blocker,
        "editor_asset_processor_negotiation_preflight_attempted": True,
        "editor_asset_processor_negotiation_preflight_verified": bool(
            project_alignment_verified and build_alignment_verified
        ),
        "editor_asset_processor_negotiation_state": state,
        "editor_asset_processor_negotiation_blocker": negotiation_blocker,
        "editor_asset_processor_negotiation_repair_attempted": False,
        "editor_asset_processor_negotiation_repair_verified": False,
        "editor_asset_processor_negotiation_repair_blocker": "blocked_by_asset_processor_process_ownership_unverified",
        "asset_processor_restart_attempted": False,
        "asset_processor_restart_completed": False,
        "asset_processor_restart_blocker": "blocked_by_asset_processor_process_ownership_unverified",
        "asset_processor_launch_attempted": False,
        "asset_processor_launch_completed": False,
        "asset_processor_launch_blocker": "not_selected_existing_process_classification_only",
    }


def _asset_processor_operator_remediation_command(
    *,
    target_asset_processor_executable: Path,
    target_engine_root: Path,
    target_project_path: Path,
) -> str:
    return (
        f'"{_display_command_path_token(target_asset_processor_executable)}" --start-hidden '
        f'--engine-path="{_display_command_path_token(target_engine_root)}" '
        f'--project-path="{_display_command_path_token(target_project_path)}"'
    )


def _diagnostic_owned_asset_processor_process_ids(env: Mapping[str, str]) -> set[int]:
    values: List[str] = []
    for key in (
        "MAXINE_ASSET_PROCESSOR_DIAGNOSTIC_OWNED_PIDS",
        "MAXINE_AP_DIAGNOSTIC_OWNED_PROCESS_IDS",
        "MAXINE_AP_DIAGNOSTIC_OWNED_PROCESS_ID",
    ):
        raw = str(env.get(key, "")).strip()
        if raw:
            values.extend(token for token in re.split(r"[,\s;]+", raw) if token)
    process_ids: set[int] = set()
    for value in values:
        try:
            parsed = int(value)
        except ValueError:
            continue
        if parsed > 0:
            process_ids.add(parsed)
    return process_ids


def _classify_asset_processor_project_build_alignment(
    rows: Sequence[Mapping[str, Any]],
    *,
    target_engine_root: Path,
    target_project_path: Path,
    target_editor_executable: Path,
    target_asset_processor_executable: Path,
    source_validated: bool,
) -> Dict[str, Any]:
    process_inventory = _classify_editor_asset_processor_process_inventory(
        rows,
        expected_project_path=target_project_path,
        expected_editor_executable=target_editor_executable,
        expected_asset_processor_executable=target_asset_processor_executable,
    )
    ap_rows: List[Mapping[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or row.get("Name") or "").lower()
        executable_path = str(row.get("executable_path") or row.get("ExecutablePath") or "").lower()
        if "assetprocessor" in name or executable_path.endswith("assetprocessor.exe"):
            ap_rows.append(row)

    sanitized_ap = list(process_inventory.get("asset_processor_process_inventory_sanitized", []))
    ap_running = bool(sanitized_ap)
    process_count = len(sanitized_ap)
    target_process_running = any(entry.get("expected_executable") is True for entry in sanitized_ap)
    mismatched_process_running = bool(
        ap_running
        and any(
            entry.get("expected_executable") is not True
            or entry.get("same_build_bin_as_editor") is not True
            or (
                entry.get("command_line_project_path_present") is True
                and entry.get("command_line_project_path_matches") is not True
            )
            for entry in sanitized_ap
        )
    )
    executable_alignment_verified = bool(target_process_running)
    build_alignment_verified = bool(
        target_process_running and any(entry.get("same_build_bin_as_editor") is True for entry in sanitized_ap)
    )
    project_alignment_verified = bool(
        ap_running and any(entry.get("command_line_project_path_matches") is True for entry in sanitized_ap)
    )
    explicit_project_mismatch = any(
        entry.get("command_line_project_path_present") is True
        and entry.get("command_line_project_path_matches") is not True
        for entry in sanitized_ap
    )
    explicit_engine_mismatch = any(
        _process_command_engine_path_values(str(row.get("command_line") or row.get("CommandLine") or ""))
        and not _process_command_engine_path_matches(
            str(row.get("command_line") or row.get("CommandLine") or ""),
            target_engine_root,
        )
        for row in ap_rows
    )
    owner_verified = any(row.get("owned_by_diagnostic_run") is True for row in ap_rows)
    operator_remediation_command = _asset_processor_operator_remediation_command(
        target_asset_processor_executable=target_asset_processor_executable,
        target_engine_root=target_engine_root,
        target_project_path=target_project_path,
    )

    if not source_validated:
        alignment_verified = False
        state = "blocked_by_asset_processor_alignment_repair_source_validation_unavailable"
        blocker = "blocked_by_asset_processor_alignment_repair_source_validation_unavailable"
        repair_mode = "classify_only"
        remediation_available = False
        remediation_reason = ""
    elif not ap_running:
        alignment_verified = False
        state = "blocked_by_asset_processor_not_running"
        blocker = "blocked_by_asset_processor_not_running"
        repair_mode = "dry_run_operator_repair_command"
        remediation_available = True
        remediation_reason = "No running Asset Processor process was found for the target rig."
    elif project_alignment_verified and build_alignment_verified and executable_alignment_verified:
        alignment_verified = True
        state = "verified_asset_processor_project_build_alignment"
        blocker = ""
        repair_mode = "classify_only"
        remediation_available = False
        remediation_reason = ""
    elif explicit_project_mismatch:
        alignment_verified = False
        state = "blocked_by_asset_processor_project_mismatch"
        blocker = (
            "blocked_by_asset_processor_process_ownership_unverified"
            if not owner_verified
            else "blocked_by_asset_processor_project_mismatch"
        )
        repair_mode = "dry_run_operator_repair_command" if not owner_verified else "controlled_restart_if_owned"
        remediation_available = not owner_verified
        remediation_reason = "Mismatched Asset Processor project path is running and process ownership is not verified."
    elif not build_alignment_verified or explicit_engine_mismatch:
        alignment_verified = False
        state = "blocked_by_asset_processor_build_root_mismatch"
        blocker = (
            "blocked_by_asset_processor_process_ownership_unverified"
            if not owner_verified
            else "blocked_by_asset_processor_build_root_mismatch"
        )
        repair_mode = "dry_run_operator_repair_command" if not owner_verified else "controlled_restart_if_owned"
        remediation_available = not owner_verified
        remediation_reason = "Mismatched Asset Processor build root is running and process ownership is not verified."
    else:
        alignment_verified = False
        state = "blocked_by_asset_processor_project_mismatch"
        blocker = "blocked_by_asset_processor_project_mismatch"
        repair_mode = "dry_run_operator_repair_command"
        remediation_available = True
        remediation_reason = "Asset Processor project/build-root alignment could not be proven."

    executable_blocker = "" if executable_alignment_verified else (
        "blocked_by_asset_processor_not_running" if not ap_running else "blocked_by_asset_processor_build_root_mismatch"
    )
    project_blocker = "" if project_alignment_verified else (
        "blocked_by_asset_processor_not_running"
        if not ap_running
        else "blocked_by_asset_processor_project_mismatch"
    )
    build_blocker = "" if build_alignment_verified and not explicit_engine_mismatch else (
        "blocked_by_asset_processor_not_running"
        if not ap_running
        else "blocked_by_asset_processor_build_root_mismatch"
    )
    owner_blocker = "" if owner_verified else "blocked_by_asset_processor_process_ownership_unverified"
    restart_allowed = bool(owner_verified and not alignment_verified and source_validated)

    payload: Dict[str, Any] = dict(process_inventory)
    payload.update(
        {
            "asset_processor_alignment_repair_attempted": True,
            "asset_processor_alignment_repair_verified": alignment_verified,
            "asset_processor_alignment_source_validated": source_validated,
            "asset_processor_alignment_state": state,
            "asset_processor_alignment_blocker": blocker,
            "asset_processor_target_engine_root": _display_command_path_token(target_engine_root),
            "asset_processor_target_build_root": _display_command_path_token(target_asset_processor_executable.parent),
            "asset_processor_target_project_path": _display_command_path_token(target_project_path),
            "asset_processor_target_executable_path": _display_command_path_token(
                target_asset_processor_executable
            ),
            "asset_processor_target_project_name": target_project_path.name,
            "asset_processor_target_branch_token_available": False,
            "asset_processor_target_branch_token_sanitized": "unavailable_without_runtime_negotiation_query",
            "asset_processor_process_count": process_count,
            "asset_processor_target_process_running": target_process_running,
            "asset_processor_mismatched_process_running": mismatched_process_running,
            "asset_processor_no_process_running": not ap_running,
            "asset_processor_process_owner_verified": owner_verified,
            "asset_processor_process_owner_blocker": owner_blocker,
            "asset_processor_executable_path_alignment_attempted": True,
            "asset_processor_executable_path_alignment_verified": executable_alignment_verified,
            "asset_processor_executable_path_alignment_blocker": executable_blocker,
            "asset_processor_project_alignment_attempted": True,
            "asset_processor_project_alignment_verified": project_alignment_verified,
            "asset_processor_project_alignment_blocker": project_blocker,
            "asset_processor_build_root_alignment_attempted": True,
            "asset_processor_build_root_alignment_verified": bool(build_alignment_verified and not explicit_engine_mismatch),
            "asset_processor_build_root_alignment_blocker": build_blocker,
            "asset_processor_branch_project_token_alignment_attempted": True,
            "asset_processor_branch_project_token_alignment_verified": False,
            "asset_processor_branch_project_token_alignment_blocker": (
                "blocked_by_asset_processor_branch_project_token_alignment_unavailable"
            ),
            "asset_processor_repair_mode": repair_mode,
            "asset_processor_operator_remediation_available": remediation_available,
            "asset_processor_operator_remediation_command_sanitized": (
                operator_remediation_command if remediation_available else ""
            ),
            "asset_processor_operator_remediation_reason": remediation_reason,
            "asset_processor_launch_attempted": False,
            "asset_processor_launch_completed": False,
            "asset_processor_launch_blocker": ""
            if ap_running
            else "blocked_by_asset_processor_launch_requires_explicit_operator_or_owned_harness",
            "asset_processor_launch_if_missing_allowed": False,
            "asset_processor_launch_if_missing_attempted": False,
            "asset_processor_launch_if_missing_completed": False,
            "asset_processor_launch_if_missing_blocker": "not_selected_existing_process_classification_only"
            if ap_running
            else "blocked_by_asset_processor_launch_if_missing_unavailable",
            "asset_processor_restart_attempted": False,
            "asset_processor_restart_completed": False,
            "asset_processor_restart_blocker": ""
            if restart_allowed
            else ("not_selected_alignment_verified" if alignment_verified else owner_blocker),
            "asset_cache_deletion_attempted": False,
            "asset_processor_database_wipe_attempted": False,
            "editor_asset_processor_project_alignment_verified": project_alignment_verified,
            "editor_asset_processor_project_alignment_blocker": ""
            if project_alignment_verified
            else "blocked_by_editor_asset_processor_project_mismatch",
            "editor_asset_processor_build_root_alignment_verified": bool(
                build_alignment_verified and not explicit_engine_mismatch
            ),
            "editor_asset_processor_build_root_alignment_blocker": ""
            if build_alignment_verified and not explicit_engine_mismatch
            else "blocked_by_editor_asset_processor_build_root_mismatch",
            "editor_asset_processor_negotiation_preflight_verified": alignment_verified,
            "editor_asset_processor_negotiation_state": "verified_editor_asset_processor_negotiation_after_alignment"
            if alignment_verified
            else state,
            "editor_asset_processor_negotiation_blocker": ""
            if alignment_verified
            else blocker,
        }
    )
    return payload


def _operator_ap_alignment_remediation_verification_payload(report: Mapping[str, Any]) -> Dict[str, Any]:
    def remediation_command() -> str:
        command_value = str(report.get("asset_processor_operator_remediation_command_sanitized", "")).strip()
        if command_value:
            return command_value
        executable = str(report.get("asset_processor_target_executable_path", "")).strip()
        engine_root = str(report.get("asset_processor_target_engine_root", "")).strip()
        project_path = str(report.get("asset_processor_target_project_path", "")).strip()
        if executable and engine_root and project_path:
            return f'"{executable}" --start-hidden --engine-path="{engine_root}" --project-path="{project_path}"'
        return ""

    alignment_verified = report.get("asset_processor_alignment_repair_verified") is True
    ap_source_validated = report.get("asset_processor_alignment_source_validated") is True
    operator_source_value = report.get("operator_ap_alignment_remediation_source_validated")
    operator_source_validated = operator_source_value is not False
    source_validated = bool(ap_source_validated and operator_source_validated)
    mismatched_running = report.get("asset_processor_mismatched_process_running") is True
    no_process_running = report.get("asset_processor_no_process_running") is True
    owner_verified = report.get("asset_processor_process_owner_verified") is True
    command = remediation_command()
    command_available = bool(command and source_validated)

    if not source_validated:
        verified = False
        state = "blocked_by_operator_ap_alignment_verification_source_validation_unavailable"
        blocker = "blocked_by_operator_ap_alignment_verification_source_validation_unavailable"
        appears_applied = False
        not_applied_reason = "Operator AP remediation verification source validation is unavailable."
    elif alignment_verified:
        verified = True
        state = "verified_operator_ap_alignment_remediation"
        blocker = ""
        appears_applied = True
        not_applied_reason = ""
    elif mismatched_running and not owner_verified:
        verified = False
        state = "blocked_by_operator_ap_remediation_not_applied"
        blocker = "blocked_by_operator_ap_remediation_not_applied"
        appears_applied = False
        not_applied_reason = "A mismatched Asset Processor process is still running and ownership is not verified."
    elif no_process_running:
        verified = False
        state = "blocked_by_asset_processor_not_running"
        blocker = "blocked_by_asset_processor_not_running"
        appears_applied = False
        not_applied_reason = "No Asset Processor process is running for the target rig."
    else:
        verified = False
        state = str(report.get("asset_processor_alignment_state") or "blocked_by_operator_ap_remediation_not_applied")
        blocker = str(report.get("asset_processor_alignment_blocker") or state)
        appears_applied = False
        not_applied_reason = "Asset Processor alignment remains unverified after operator remediation check."

    next_steps: List[str] = []
    if not verified and command_available:
        if mismatched_running:
            next_steps.append("Manually close the mismatched Asset Processor process from the target machine.")
        next_steps.append(command)
        next_steps.append("Rerun the operator-run AP alignment remediation verification diagnostic.")

    negotiation_verified = report.get("editor_asset_processor_negotiation_preflight_verified") is True
    negotiation_state = (
        "verified_editor_asset_processor_negotiation_after_operator_remediation"
        if negotiation_verified and verified
        else state
    )
    negotiation_blocker = "" if negotiation_verified and verified else blocker

    return {
        "operator_ap_alignment_remediation_verification_attempted": True,
        "operator_ap_alignment_remediation_verification_verified": verified,
        "operator_ap_alignment_remediation_state": state,
        "operator_ap_alignment_remediation_blocker": blocker,
        "operator_ap_alignment_remediation_command_available": command_available,
        "operator_ap_alignment_remediation_command_sanitized": command,
        "operator_ap_alignment_remediation_appears_applied": appears_applied,
        "operator_ap_alignment_remediation_not_applied_reason": not_applied_reason,
        "operator_ap_alignment_remediation_next_steps": next_steps,
        "editor_asset_processor_negotiation_after_operator_remediation_attempted": (
            report.get("editor_asset_processor_negotiation_preflight_attempted") is True
        ),
        "editor_asset_processor_negotiation_after_operator_remediation_verified": bool(
            negotiation_verified and verified
        ),
        "editor_asset_processor_negotiation_after_operator_remediation_state": negotiation_state,
        "editor_asset_processor_negotiation_after_operator_remediation_blocker": negotiation_blocker,
        "viewport_window_materialization_after_operator_ap_remediation_attempted": (
            report.get("viewport_window_materialization_after_ap_alignment_attempted") is True
            or report.get("viewport_window_materialization_repair_attempted") is True
        ),
        "viewport_window_materialization_after_operator_ap_remediation_verified": (
            report.get("viewport_window_materialization_after_ap_alignment_verified") is True
            or report.get("viewport_window_materialization_repair_verified") is True
        ),
        "viewport_window_materialization_after_operator_ap_remediation_blocker": str(
            report.get("viewport_window_materialization_after_ap_alignment_blocker")
            or report.get("viewport_window_materialization_blocker", "")
        ),
        "active_default_viewport_after_operator_ap_remediation_attempted": (
            report.get("active_default_viewport_after_ap_alignment_attempted") is True
        ),
        "active_default_viewport_after_operator_ap_remediation_verified": (
            report.get("active_default_viewport_after_ap_alignment_verified") is True
        ),
        "active_default_viewport_after_operator_ap_remediation_blocker": str(
            report.get("active_default_viewport_after_ap_alignment_blocker", "")
        ),
        "framecapture_target_after_operator_ap_remediation_attempted": (
            report.get("framecapture_target_after_ap_alignment_attempted") is True
        ),
        "framecapture_target_after_operator_ap_remediation_verified": (
            report.get("framecapture_target_after_ap_alignment_verified") is True
        ),
        "framecapture_target_after_operator_ap_remediation_blocker": str(
            report.get("framecapture_target_after_ap_alignment_blocker", "")
        ),
        "atom_swapchain_after_operator_ap_remediation_attempted": (
            report.get("atom_swapchain_after_ap_alignment_attempted") is True
        ),
        "atom_swapchain_after_operator_ap_remediation_verified": (
            report.get("atom_swapchain_after_ap_alignment_verified") is True
        ),
        "atom_swapchain_after_operator_ap_remediation_blocker": str(
            report.get("atom_swapchain_after_ap_alignment_blocker", "")
        ),
    }


def _windows_editor_asset_processor_process_rows(
    timeout_seconds: int = 5,
    *,
    diagnostic_owned_process_ids: set[int] | None = None,
) -> List[Dict[str, Any]]:
    if platform_module.system().lower() != "windows":
        return []
    owned_process_ids = set(diagnostic_owned_process_ids or set())
    command = (
        "$ErrorActionPreference='SilentlyContinue'; "
        "$rows = Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -in @('AssetProcessor.exe','Editor.exe','O3DEEditor.exe') } | "
        "Select-Object ProcessId,Name,ExecutablePath,CommandLine; "
        "$rows | ConvertTo-Json -Depth 3"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, Mapping):
        parsed = [parsed]
    rows: List[Dict[str, Any]] = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, Mapping):
                process_id = item.get("ProcessId")
                try:
                    process_id_int = int(process_id)
                except (TypeError, ValueError):
                    process_id_int = 0
                rows.append(
                    {
                        "process_id": process_id,
                        "name": item.get("Name", ""),
                        "executable_path": item.get("ExecutablePath", ""),
                        "command_line": item.get("CommandLine", ""),
                        "owned_by_diagnostic_run": process_id_int in owned_process_ids,
                    }
                )
    return rows


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
        normalized_diagnostic_mode = _normalize_diagnostic_mode(diagnostic_mode)
        if normalized_diagnostic_mode in SOURCE_ONLY_EDITOR_DIAGNOSTIC_MODES:
            return _execute_source_only_editor_visual_runner_readiness(
                manifest=manifest,
                readiness=readiness,
                strict_integration=strict_integration,
                platform=platform,
                env=env,
                artifact_root=_resolve_path(artifact_root),
                golden_project_fixture=_resolve_path(golden_project_fixture),
                diagnostic_mode=normalized_diagnostic_mode,
                timeout_seconds=timeout_seconds,
                progress_log=_resolve_path(progress_log) if progress_log else None,
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
            diagnostic_mode=normalized_diagnostic_mode,
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


def _execute_source_only_editor_visual_runner_readiness(
    *,
    manifest: Path | str,
    readiness: Mapping[str, Any],
    strict_integration: bool,
    platform: str,
    env: Mapping[str, str],
    artifact_root: Path,
    golden_project_fixture: Path,
    diagnostic_mode: str,
    timeout_seconds: int | None,
    progress_log: Path | None,
) -> Dict[str, Any]:
    started_at = _utc_now()
    start_time = time.monotonic()
    if diagnostic_mode == "non-null-editor-desktop-rhi-readiness":
        run_slug = "non-null-editor-desktop-rhi-readiness"
        report_filename = "non_null_editor_desktop_rhi_readiness_report.json"
        evidence_report_id = "non-null-editor-desktop-rhi-readiness-report"
        source_start_message = "Building source-only non-null Editor desktop/RHI readiness diagnostic."
        source_finish_message = "Finalized source-only non-null Editor desktop/RHI readiness diagnostic."
        level_strategy = "source_validated_desktop_rhi_readiness"
        final_message = (
            "Non-null Editor desktop/RHI readiness diagnostic is source-validated; "
            "live non-null launch and screenshot capture were not attempted."
        )
    else:
        run_slug = "non-null-editor-visual-runner-readiness"
        report_filename = "non_null_editor_visual_runner_readiness_report.json"
        evidence_report_id = "non-null-editor-visual-runner-readiness-report"
        source_start_message = "Building source-only non-null Editor visual runner readiness/temp-scene contract."
        source_finish_message = "Finalized source-only non-null Editor visual runner readiness/temp-scene contract."
        level_strategy = "source_validated_visual_runner_contract"
        final_message = (
            "Non-null Editor visual runner readiness/temp-scene contract is source-validated; "
            "live non-null launch and screenshot capture were not attempted."
        )
    run_id = run_slug + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = artifact_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    report_path = output_dir / report_filename
    template_path = output_dir / "editor_smoke_report.template.json"
    progress_path = progress_log or (output_dir / "progress.jsonl")

    engine_root = Path(str(readiness["engine_root"]["path"]))
    project_path = Path(str(readiness["project_path"]["path"]))
    editor_executable = Path(str(readiness["editor_executable"]["path"]))
    selected_timeout_seconds = timeout_seconds if timeout_seconds is not None else _editor_timeout_seconds(env)
    selected_render_capture_rhi = _selected_non_null_render_capture_rhi(env)
    apb_baseline = _select_apb_baseline_report(env)
    manifest_path = _resolve_path(manifest)
    apb_payload = _load_json_if_present(apb_baseline)
    product_summary = _product_evidence_summary(apb_payload)
    expected_products = _expected_products_from_manifest(manifest_path, product_summary)
    missing_products = [product for product in expected_products if product not in product_summary["produced_products"]]

    if not apb_baseline or not apb_payload or product_summary["status"] != "pass" or missing_products or product_summary["cache_heuristic_used"]:
        messages = []
        if not apb_baseline:
            messages.append("No APB baseline report was found for the Editor visual runner readiness contract.")
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
    argv = [
        str(editor_executable),
        f"-rhi={selected_render_capture_rhi}",
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
        step="source_only_contract_start",
        status="started",
        started_monotonic=start_time,
        message=source_start_message,
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
        temp_level_rel="",
        started_at=started_at,
        golden_project_fixture=golden_project_fixture,
        diagnostic_mode=diagnostic_mode,
        script_path=script_path,
    )
    template.update(
        {
            "status": "pass",
            "level_strategy": level_strategy,
            "live_editor_execution": False,
            "live_asset_processor_batch_execution": False,
            "exit_code": None,
            "temp_level_path_redacted": "",
            "non_null_editor_render_capture_rhi_requested": selected_render_capture_rhi,
            "non_null_editor_render_capture_null_renderer_used": False,
            "null_renderer_used": False,
        }
    )
    template_path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")

    previous_env = {key: os.environ.get(key) for key in ("O3DE_ENGINE_ROOT", "O3DE_PROJECT_PATH", "O3DE_EDITOR_EXECUTABLE")}
    os.environ["O3DE_ENGINE_ROOT"] = str(engine_root)
    os.environ["O3DE_PROJECT_PATH"] = str(project_path)
    os.environ["O3DE_EDITOR_EXECUTABLE"] = str(editor_executable)
    try:
        from tools.o3de.editor_python import maxine_package_prefab_smoke as editor_python_smoke

        if diagnostic_mode == "non-null-editor-desktop-rhi-readiness":
            contract_payload = editor_python_smoke._run_non_null_editor_desktop_rhi_readiness_checks(
                template,
                progress_log=progress_path,
            )
        else:
            contract_payload = editor_python_smoke._run_non_null_editor_visual_runner_readiness_checks(
                template,
                progress_log=progress_path,
            )
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    finished_at = _utc_now()
    duration_seconds = round(time.monotonic() - start_time, 3)
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    _write_progress_marker(
        progress_path,
        phase="wrapper",
        step="source_only_contract_final_status",
        status="completed",
        started_monotonic=start_time,
        message=source_finish_message,
        report_path=report_path,
    )
    progress_markers = _load_progress_markers(progress_path)

    report = dict(template)
    report.update(contract_payload)
    report.update(
        {
            "generated_at": finished_at,
            "status": "pass",
            "diagnostic_mode": diagnostic_mode,
            "live_editor_execution": False,
            "live_asset_processor_batch_execution": False,
            "live_publication": False,
            "release_packaging": False,
            "production_level_mutation": False,
            "defaultlevel_mutation": False,
            "exit_code": None,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
            "timeout_seconds": selected_timeout_seconds,
            "timed_out": False,
            "timeout_stall": False,
            "process_cleanup": {"attempted": False, "method": "source_only_no_process", "return_code": None},
            "process_tree_cleanup": {"attempted": False, "method": "source_only_no_process", "return_code": None},
            "stdout_log_ref": _repo_relative(stdout_path),
            "stderr_log_ref": _repo_relative(stderr_path),
            "editor_log_ref": "",
            "progress_log_ref": _repo_relative(progress_path),
            "last_progress_marker": _last_relevant_progress_marker(progress_markers),
            "stall_phase": "",
            "script_path_redacted": _redact_path(str(script_path)),
            "script_path_mode": "absolute",
            "editor_command_working_directory": _redact_path(str(project_path)),
            "apb_baseline_ref": _repo_relative(apb_baseline),
            "product_evidence_summary": product_summary,
            "command_preview": _redacted_argv(argv),
            "command_argv_redacted": _redacted_argv(argv),
            "errors": [],
            "warnings": [],
            "messages": _unique(
                list(contract_payload.get("messages", []))
                + [final_message]
            ),
        }
    )
    report["evidence_refs"] = _merge_evidence_refs(
        report.get("evidence_refs", []),
        [
            {"id": evidence_report_id, "kind": "editor_smoke_report", "path": _repo_relative(report_path)},
            {"id": "editor-smoke-progress-log", "kind": "editor_smoke_progress_log", "path": _repo_relative(progress_path)},
            {"id": "apb-baseline", "kind": "asset_processor_batch_report", "path": _repo_relative(apb_baseline)},
        ],
    )
    preserved_ref = str(report.get("preserved_non_null_editor_render_capture_report_ref", "")).strip()
    if preserved_ref:
        report["evidence_refs"] = _merge_evidence_refs(
            report.get("evidence_refs", []),
            [
                {
                    "id": "preserved-non-null-editor-render-capture-envelope-report",
                    "kind": "editor_smoke_report",
                    "path": preserved_ref,
                }
            ],
        )

    schema_result = schema_validate(report, load_json(SCHEMA_PATH))
    semantic_result = validate_editor_smoke_report(report, strict=True)
    if schema_result.status == "fail" or semantic_result.status == "fail":
        report["status"] = "fail"
        report["errors"] = _unique(schema_result.error_codes + semantic_result.error_codes)
        report["messages"] = _unique(report.get("messages", []) + schema_result.messages + semantic_result.messages)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


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
    safe_temp_scene_leaf = "editor_safe_temp_visual_scene_display_context_" + run_id.removeprefix("editor-smoke-").lower()
    safe_temp_scene_level_name = (
        f"_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context/{safe_temp_scene_leaf}"
    )
    safe_temp_scene_rel = f"Levels/{safe_temp_scene_level_name}"
    safe_temp_scene_abs = project_path / safe_temp_scene_rel
    non_null_render_capture_mode = diagnostic_mode == "non-null-editor-render-capture-envelope"
    live_non_null_editor_launch_mode = diagnostic_mode == "live-non-null-editor-launch"
    screenshot_capture_artifact_readiness_mode = diagnostic_mode == "editor-screenshot-capture-artifact-readiness"
    active_viewport_temp_scene_readiness_mode = diagnostic_mode == "editor-active-viewport-temp-scene-readiness"
    safe_temp_visual_scene_context_mode = diagnostic_mode == "editor-safe-temp-visual-scene-display-context"
    nonblocking_viewport_swapchain_readiness_mode = (
        diagnostic_mode == "editor-nonblocking-viewport-swapchain-readiness"
    )
    ap_negotiation_viewport_materialization_mode = (
        diagnostic_mode == "editor-ap-negotiation-viewport-materialization-readiness"
    )
    asset_processor_alignment_repair_mode = (
        diagnostic_mode == "asset-processor-project-build-alignment-repair"
    )
    operator_ap_alignment_remediation_verification_mode = (
        diagnostic_mode == "operator-run-ap-alignment-remediation-verification"
    )
    focused_viewport_materialization_mode = (
        diagnostic_mode == "focused-editor-viewport-activation-default-viewport-materialization"
    )
    editor_main_window_activation_deep_dive_mode = (
        diagnostic_mode == "editor-main-window-activation-materialization-deep-dive"
    )
    alternate_editor_window_visible_shell_mode = (
        diagnostic_mode == "alternate-editor-window-discovery-visible-shell-materialization"
    )
    editor_layout_bootstrap_window_lifecycle_mode = (
        diagnostic_mode == "editor-layout-bootstrap-window-lifecycle-deep-dive"
    )
    editor_bootstrap_wait_shell_ready_mode = (
        diagnostic_mode == "editor-bootstrap-wait-shell-ready-synchronization"
    )
    asset_processor_alignment_family_mode = (
        asset_processor_alignment_repair_mode
        or operator_ap_alignment_remediation_verification_mode
        or focused_viewport_materialization_mode
        or editor_main_window_activation_deep_dive_mode
        or alternate_editor_window_visible_shell_mode
        or editor_layout_bootstrap_window_lifecycle_mode
        or editor_bootstrap_wait_shell_ready_mode
    )
    safe_temp_scene_exercise_mode = (
        safe_temp_visual_scene_context_mode
        or nonblocking_viewport_swapchain_readiness_mode
        or ap_negotiation_viewport_materialization_mode
        or asset_processor_alignment_family_mode
    )
    nonblocking_probe_family_mode = (
        nonblocking_viewport_swapchain_readiness_mode
        or ap_negotiation_viewport_materialization_mode
        or asset_processor_alignment_family_mode
    )
    selected_render_capture_rhi = _selected_non_null_render_capture_rhi(env)
    non_null_editor_mode = (
        non_null_render_capture_mode
        or live_non_null_editor_launch_mode
        or screenshot_capture_artifact_readiness_mode
        or active_viewport_temp_scene_readiness_mode
        or safe_temp_scene_exercise_mode
    )
    live_non_null_process_mode = (
        live_non_null_editor_launch_mode
        or screenshot_capture_artifact_readiness_mode
        or active_viewport_temp_scene_readiness_mode
        or safe_temp_scene_exercise_mode
    )
    render_args = [f"-rhi={selected_render_capture_rhi}"] if non_null_editor_mode else ["-NullRenderer", "-rhi=Null"]
    argv = [
        str(editor_executable),
        *render_args,
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
    if live_non_null_process_mode:
        previous_env = {
            key: os.environ.get(key)
            for key in (
                "O3DE_ENGINE_ROOT",
                "O3DE_PROJECT_PATH",
                "O3DE_EDITOR_EXECUTABLE",
                "MAXINE_EDITOR_RENDER_CAPTURE_RHI",
                "MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_PATH",
                "MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_ROOT",
                "MAXINE_EDITOR_SAFE_TEMP_VISUAL_SCENE_LEVEL_NAME",
                "MAXINE_EDITOR_SAFE_TEMP_VISUAL_SCENE_LEVEL_PATH",
                "MAXINE_ALLOW_EDITOR_ACTIVE_VIEWPORT_PYTHON_PROBE",
                "MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS",
                "MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR",
                "MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION",
                "MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION",
                "MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE",
                "MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL",
                "MAXINE_ENABLE_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE",
                "MAXINE_ENABLE_EDITOR_BOOTSTRAP_WAIT_SHELL_READY_SYNCHRONIZATION",
            )
        }
        os.environ["O3DE_ENGINE_ROOT"] = str(engine_root)
        os.environ["O3DE_PROJECT_PATH"] = str(project_path)
        os.environ["O3DE_EDITOR_EXECUTABLE"] = str(editor_executable)
        os.environ["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] = selected_render_capture_rhi
        if safe_temp_scene_exercise_mode:
            os.environ["MAXINE_EDITOR_SAFE_TEMP_VISUAL_SCENE_LEVEL_NAME"] = safe_temp_scene_level_name
            os.environ["MAXINE_EDITOR_SAFE_TEMP_VISUAL_SCENE_LEVEL_PATH"] = str(safe_temp_scene_abs)
        if ap_negotiation_viewport_materialization_mode:
            os.environ["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        if asset_processor_alignment_family_mode:
            os.environ["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
            os.environ["MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        if operator_ap_alignment_remediation_verification_mode:
            os.environ["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        if focused_viewport_materialization_mode:
            os.environ["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
            os.environ["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
        if editor_main_window_activation_deep_dive_mode:
            os.environ["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
            os.environ["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
        if alternate_editor_window_visible_shell_mode:
            os.environ["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
            os.environ["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
            os.environ["MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL"] = "1"
        if editor_layout_bootstrap_window_lifecycle_mode:
            os.environ["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
            os.environ["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
            os.environ["MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE"] = "1"
        if editor_bootstrap_wait_shell_ready_mode:
            os.environ["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
            os.environ["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
            os.environ["MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE"] = "1"
            os.environ["MAXINE_ENABLE_EDITOR_BOOTSTRAP_WAIT_SHELL_READY_SYNCHRONIZATION"] = "1"
        if screenshot_capture_artifact_readiness_mode:
            os.environ["MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_ROOT"] = str(output_dir)
            os.environ["MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_PATH"] = str(
                output_dir / "editor_screenshot_capture_artifact_readiness.png"
            )
        try:
            from tools.o3de.editor_python import maxine_package_prefab_smoke as editor_python_smoke

            desktop_payload = editor_python_smoke._run_non_null_editor_desktop_rhi_readiness_checks(
                template,
                progress_log=progress_path,
            )
            template.update(desktop_payload)
            launch_payload = editor_python_smoke._run_live_non_null_editor_launch_checks(
                template,
                progress_log=progress_path,
                launch_attempted=False,
                launch_completed=False,
                launch_exit_code=None,
                timed_out=False,
                killed=False,
                stdout_ref=_repo_relative(stdout_path),
                stderr_ref=_repo_relative(stderr_path),
                log_ref="",
                selected_log_blocking_matches=[],
            )
            template.update(launch_payload)
            if screenshot_capture_artifact_readiness_mode:
                capture_source_validation = editor_python_smoke._editor_screenshot_capture_artifact_readiness_source_validation(
                    engine_root
                )
                capture_source_validated = (
                    capture_source_validation.get("status")
                    == "editor_screenshot_capture_artifact_readiness_source_validation_pass"
                )
                capture_source_blocker = str(
                    capture_source_validation.get("blocker")
                    or "blocked_by_editor_screenshot_capture_requires_additional_source_validation"
                )
                template.update(
                    {
                        "editor_screenshot_capture_artifact_readiness_attempted": False,
                        "editor_screenshot_capture_artifact_readiness_completed": False,
                        "editor_screenshot_capture_artifact_readiness_verified": False,
                        "editor_screenshot_capture_artifact_readiness_blocker": ""
                        if capture_source_validated
                        else capture_source_blocker,
                        "editor_screenshot_capture_artifact_readiness_candidate_matrix": (
                            editor_python_smoke._editor_screenshot_capture_artifact_readiness_candidate_matrix(
                                source_validated=capture_source_validated,
                                selected_rhi=selected_render_capture_rhi,
                                capture_requested=False,
                                capture_verified=False,
                                blocker="" if capture_source_validated else capture_source_blocker,
                            )
                        ),
                        "editor_screenshot_capture_artifact_readiness_selected_strategy": (
                            "bounded_live_editor_screenshot_capture_artifact_readiness"
                        ),
                        "editor_screenshot_capture_artifact_readiness_source_validation_status": (
                            capture_source_validation.get("status", "")
                        ),
                        "editor_screenshot_capture_artifact_readiness_source_validation_verified": capture_source_validated,
                        "editor_screenshot_capture_artifact_readiness_source_validation": capture_source_validation,
                        "editor_screenshot_capture_artifact_readiness_source_files": [
                            str(spec["path"])
                            for spec in editor_python_smoke._editor_screenshot_capture_artifact_readiness_source_specs(
                                engine_root
                            )
                        ],
                    }
                )
            if active_viewport_temp_scene_readiness_mode:
                viewport_source_validation = editor_python_smoke._editor_active_viewport_temp_scene_readiness_source_validation(
                    engine_root
                )
                viewport_source_validated = (
                    viewport_source_validation.get("status")
                    == "editor_active_viewport_temp_scene_readiness_source_validation_pass"
                )
                viewport_source_blocker = str(
                    viewport_source_validation.get("blocker")
                    or "blocked_by_editor_active_viewport_requires_additional_source_validation"
                )
                template.update(
                    {
                        "editor_active_viewport_temp_scene_readiness_attempted": False,
                        "editor_active_viewport_temp_scene_readiness_completed": False,
                        "editor_active_viewport_temp_scene_readiness_verified": False,
                        "editor_active_viewport_temp_scene_readiness_blocker": ""
                        if viewport_source_validated
                        else viewport_source_blocker,
                        "editor_active_viewport_temp_scene_readiness_candidate_matrix": (
                            editor_python_smoke._editor_active_viewport_temp_scene_readiness_candidate_matrix(
                                source_validated=viewport_source_validated,
                                active_viewport_verified=False,
                                frame_capture_target_verified=False,
                                temp_scene_verified=viewport_source_validated,
                                capture_target_verified=viewport_source_validated,
                                blocker="" if viewport_source_validated else viewport_source_blocker,
                            )
                        ),
                        "editor_active_viewport_temp_scene_readiness_selected_strategy": (
                            "source_validated_temp_visual_scene_contract_no_capture"
                            if viewport_source_validated
                            else ""
                        ),
                        "editor_active_viewport_temp_scene_readiness_source_validation_status": (
                            viewport_source_validation.get("status", "")
                        ),
                        "editor_active_viewport_temp_scene_readiness_source_validation_verified": viewport_source_validated,
                        "editor_active_viewport_temp_scene_readiness_source_validation": viewport_source_validation,
                        "editor_active_viewport_temp_scene_readiness_source_files": [
                            str(spec["path"])
                            for spec in editor_python_smoke._editor_active_viewport_temp_scene_readiness_source_specs(
                                engine_root
                            )
                        ],
                    }
                )
            if safe_temp_scene_exercise_mode:
                temp_context_source_validation = (
                    editor_python_smoke._editor_safe_temp_visual_scene_display_context_source_validation(engine_root)
                )
                temp_context_source_validated = (
                    temp_context_source_validation.get("status")
                    == "editor_safe_temp_visual_scene_display_context_source_validation_pass"
                )
                temp_context_source_blocker = str(
                    temp_context_source_validation.get("blocker")
                    or "blocked_by_temp_visual_scene_source_validation_unavailable"
                )
                template.update(
                    {
                        "temp_visual_scene_context_exercise_attempted": False,
                        "temp_visual_scene_context_exercise_completed": False,
                        "temp_visual_scene_context_exercise_verified": False,
                        "temp_visual_scene_context_exercise_blocker": ""
                        if temp_context_source_validated
                        else temp_context_source_blocker,
                        "temp_visual_scene_source_validated": temp_context_source_validated,
                        "temp_visual_scene_source_validation_status": temp_context_source_validation.get("status", ""),
                        "temp_visual_scene_source_validation": temp_context_source_validation,
                        "temp_visual_scene_source_files": [
                            str(spec["path"])
                            for spec in editor_python_smoke._editor_safe_temp_visual_scene_display_context_source_specs(
                                engine_root
                            )
                        ],
                        "temp_visual_scene_path": safe_temp_scene_rel,
                        "temp_visual_scene_cleanup_policy": "post_editor_exit_run_owned_temp_root_cleanup",
                        "editor_temp_visual_scene_approved_root": "Levels/_maxine_visual_smoke",
                    }
                )
            if nonblocking_probe_family_mode:
                nonblocking_source_validation = (
                    editor_python_smoke._editor_nonblocking_viewport_swapchain_readiness_source_validation(engine_root)
                )
                nonblocking_source_validated = (
                    nonblocking_source_validation.get("status")
                    == "editor_nonblocking_viewport_swapchain_readiness_source_validation_pass"
                )
                nonblocking_source_blocker = str(
                    nonblocking_source_validation.get("blocker")
                    or "blocked_by_nonblocking_viewport_or_swapchain_probe_source_validation_unavailable"
                )
                template.update(
                    {
                        "nonblocking_viewport_swapchain_probe_attempted": False,
                        "nonblocking_viewport_swapchain_probe_verified": False,
                        "nonblocking_viewport_swapchain_probe_source_validated": nonblocking_source_validated,
                        "nonblocking_viewport_swapchain_probe_source_validation_status": (
                            nonblocking_source_validation.get("status", "")
                        ),
                        "nonblocking_viewport_swapchain_probe_source_validation": nonblocking_source_validation,
                        "nonblocking_viewport_swapchain_probe_source_files": [
                            str(spec["path"])
                            for spec in editor_python_smoke._editor_nonblocking_viewport_swapchain_readiness_source_specs(
                                engine_root
                            )
                        ],
                        "nonblocking_viewport_swapchain_probe_blocker": ""
                        if nonblocking_source_validated
                        else nonblocking_source_blocker,
                        "nonblocking_viewport_swapchain_probe_strategies": [],
                    }
                )
            if ap_negotiation_viewport_materialization_mode or asset_processor_alignment_family_mode:
                ap_source_validation = (
                    editor_python_smoke._editor_ap_negotiation_viewport_materialization_source_validation(engine_root)
                )
                ap_source_validated = (
                    ap_source_validation.get("status")
                    == "editor_ap_negotiation_viewport_materialization_source_validation_pass"
                )
                ap_source_blocker = str(
                    ap_source_validation.get("blocker")
                    or "blocked_by_editor_asset_processor_negotiation_source_validation_unavailable"
                )
                process_rows = _windows_editor_asset_processor_process_rows(
                    diagnostic_owned_process_ids=_diagnostic_owned_asset_processor_process_ids(env)
                )
                if asset_processor_alignment_family_mode:
                    alignment_source_validation = (
                        editor_python_smoke._asset_processor_project_build_alignment_source_validation(engine_root)
                    )
                    alignment_source_validated = (
                        alignment_source_validation.get("status")
                        == "asset_processor_project_build_alignment_source_validation_pass"
                    )
                    process_inventory = _classify_asset_processor_project_build_alignment(
                        process_rows,
                        target_engine_root=engine_root,
                        target_project_path=project_path,
                        target_editor_executable=editor_executable,
                        target_asset_processor_executable=editor_executable.parent / "AssetProcessor.exe",
                        source_validated=alignment_source_validated,
                    )
                else:
                    alignment_source_validation = {}
                    alignment_source_validated = False
                    process_inventory = _classify_editor_asset_processor_process_inventory(
                        process_rows,
                        expected_project_path=project_path,
                        expected_editor_executable=editor_executable,
                        expected_asset_processor_executable=editor_executable.parent / "AssetProcessor.exe",
                    )
                template.update(process_inventory)
                template.update(
                    {
                        "editor_asset_processor_negotiation_source_validated": ap_source_validated,
                        "editor_asset_processor_negotiation_source_validation_status": (
                            ap_source_validation.get("status", "")
                        ),
                        "editor_asset_processor_negotiation_source_validation": ap_source_validation,
                        "editor_asset_processor_negotiation_source_files": [
                            str(spec["path"])
                            for spec in editor_python_smoke._editor_ap_negotiation_viewport_materialization_source_specs(
                                engine_root
                            )
                        ],
                        "editor_asset_processor_negotiation_preflight_verified": (
                            template.get("editor_asset_processor_negotiation_preflight_verified") is True
                            and ap_source_validated
                        ),
                        "editor_asset_processor_negotiation_blocker": ""
                        if (
                            template.get("editor_asset_processor_negotiation_preflight_verified") is True
                            and ap_source_validated
                        )
                        else str(template.get("editor_asset_processor_negotiation_blocker") or ap_source_blocker),
                        "editor_asset_processor_modal_detection_attempted": False,
                        "editor_asset_processor_negotiation_failed_modal_detected": False,
                        "editor_asset_processor_negotiation_failed_modal_blocker": "",
                        "viewport_window_materialization_repair_attempted": False,
                        "viewport_window_materialization_repair_verified": False,
                        "viewport_window_materialization_state": "",
                        "viewport_window_materialization_blocker": "",
                    }
                )
                if asset_processor_alignment_family_mode:
                    template.update(
                        {
                            "asset_processor_alignment_source_validated": alignment_source_validated,
                            "asset_processor_alignment_source_validation_status": (
                                alignment_source_validation.get("status", "")
                            ),
                            "asset_processor_alignment_source_validation": alignment_source_validation,
                            "asset_processor_alignment_source_files": [
                                str(spec["path"])
                                for spec in editor_python_smoke._asset_processor_project_build_alignment_source_specs(
                                    engine_root
                                )
                            ],
                            "editor_asset_processor_negotiation_preflight_verified": (
                                template.get("editor_asset_processor_negotiation_preflight_verified") is True
                                and ap_source_validated
                                and alignment_source_validated
                            ),
                            "editor_asset_processor_negotiation_blocker": ""
                            if (
                                template.get("editor_asset_processor_negotiation_preflight_verified") is True
                                and ap_source_validated
                                and alignment_source_validated
                            )
                            else str(
                                template.get("editor_asset_processor_negotiation_blocker")
                                or template.get("asset_processor_alignment_blocker")
                                or alignment_source_validation.get("blocker")
                                or ap_source_blocker
                            ),
                        }
                    )
                    if operator_ap_alignment_remediation_verification_mode:
                        operator_source_validation = (
                            editor_python_smoke._operator_ap_alignment_remediation_verification_source_validation(
                                engine_root
                            )
                        )
                        operator_source_validated = (
                            operator_source_validation.get("status")
                            == "operator_ap_alignment_remediation_verification_source_validation_pass"
                        )
                        template.update(
                            {
                                "operator_ap_alignment_remediation_source_validated": operator_source_validated,
                                "operator_ap_alignment_remediation_source_validation_status": (
                                    operator_source_validation.get("status", "")
                                ),
                                "operator_ap_alignment_remediation_source_validation": operator_source_validation,
                                "operator_ap_alignment_remediation_source_files": [
                                    str(spec["path"])
                                    for spec in editor_python_smoke._operator_ap_alignment_remediation_verification_source_specs(
                                        engine_root
                                    )
                                ],
                            }
                        )
                        template.update(_operator_ap_alignment_remediation_verification_payload(template))
                    if focused_viewport_materialization_mode:
                        operator_source_validation = (
                            editor_python_smoke._operator_ap_alignment_remediation_verification_source_validation(
                                engine_root
                            )
                        )
                        operator_source_validated = (
                            operator_source_validation.get("status")
                            == "operator_ap_alignment_remediation_verification_source_validation_pass"
                        )
                        focused_source_validation = (
                            editor_python_smoke._focused_editor_viewport_materialization_source_validation(
                                engine_root
                            )
                        )
                        focused_source_validated = (
                            focused_source_validation.get("status")
                            == "focused_editor_viewport_materialization_source_validation_pass"
                        )
                        template.update(
                            {
                                "operator_ap_alignment_remediation_source_validated": operator_source_validated,
                                "operator_ap_alignment_remediation_source_validation_status": (
                                    operator_source_validation.get("status", "")
                                ),
                                "operator_ap_alignment_remediation_source_validation": operator_source_validation,
                                "operator_ap_alignment_remediation_source_files": [
                                    str(spec["path"])
                                    for spec in editor_python_smoke._operator_ap_alignment_remediation_verification_source_specs(
                                        engine_root
                                    )
                                ],
                                "focused_viewport_materialization_source_validated": focused_source_validated,
                                "focused_viewport_materialization_source_validation_status": (
                                    focused_source_validation.get("status", "")
                                ),
                                "focused_viewport_materialization_source_validation": focused_source_validation,
                                "focused_viewport_materialization_source_files": [
                                    str(spec["path"])
                                    for spec in editor_python_smoke._focused_editor_viewport_materialization_source_specs(
                                        engine_root
                                    )
                                ],
                            }
                        )
                        template.update(_operator_ap_alignment_remediation_verification_payload(template))
        finally:
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        capture_source_blocked = (
            screenshot_capture_artifact_readiness_mode
            and template.get("editor_screenshot_capture_artifact_readiness_source_validation_verified") is not True
        )
        viewport_source_blocked = (
            active_viewport_temp_scene_readiness_mode
            and template.get("editor_active_viewport_temp_scene_readiness_source_validation_verified") is not True
        )
        temp_context_source_blocked = (
            safe_temp_scene_exercise_mode
            and template.get("temp_visual_scene_source_validated") is not True
        )
        nonblocking_source_blocked = (
            nonblocking_probe_family_mode
            and template.get("nonblocking_viewport_swapchain_probe_source_validated") is not True
        )
        ap_negotiation_source_blocked = (
            ap_negotiation_viewport_materialization_mode
            and template.get("editor_asset_processor_negotiation_source_validated") is not True
        )
        asset_processor_alignment_source_blocked = (
            asset_processor_alignment_family_mode
            and (
                template.get("editor_asset_processor_negotiation_source_validated") is not True
                or template.get("asset_processor_alignment_source_validated") is not True
                or (
                    (operator_ap_alignment_remediation_verification_mode or focused_viewport_materialization_mode)
                    and template.get("operator_ap_alignment_remediation_source_validated") is not True
                )
                or (
                    focused_viewport_materialization_mode
                    and template.get("focused_viewport_materialization_source_validated") is not True
                )
            )
        )
        if (
            template.get("non_null_editor_desktop_rhi_readiness_verified") is not True
            or template.get("live_non_null_editor_launch_source_validation_verified") is not True
            or capture_source_blocked
            or viewport_source_blocked
            or temp_context_source_blocked
            or nonblocking_source_blocked
            or ap_negotiation_source_blocked
            or asset_processor_alignment_source_blocked
        ):
            blocked_by_readiness = template.get("non_null_editor_desktop_rhi_readiness_verified") is not True
            blocked_by_launch_source = template.get("live_non_null_editor_launch_source_validation_verified") is not True
            preflight_blocker = str(
                (
                    template.get("editor_screenshot_capture_artifact_readiness_blocker")
                    if capture_source_blocked
                    else ""
                )
                or (
                    template.get("editor_active_viewport_temp_scene_readiness_blocker")
                    if viewport_source_blocked
                    else ""
                )
                or (
                    template.get("temp_visual_scene_context_exercise_blocker")
                    if temp_context_source_blocked
                    else ""
                )
                or (
                    template.get("nonblocking_viewport_swapchain_probe_blocker")
                    if nonblocking_source_blocked
                    else ""
                )
                or (
                    template.get("editor_asset_processor_negotiation_blocker")
                    if ap_negotiation_source_blocked
                    else ""
                )
                or (
                    (
                        template.get("asset_processor_alignment_blocker")
                        or template.get("editor_asset_processor_negotiation_blocker")
                    )
                    if asset_processor_alignment_source_blocked
                    else ""
                )
                or template.get("non_null_editor_launch_blocker")
                or template.get("live_non_null_editor_launch_blocker")
                or (
                    "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
                    if blocked_by_readiness
                    else "blocked_by_live_non_null_editor_launch_source_validation_failed"
                    if blocked_by_launch_source
                    else "blocked_by_editor_active_viewport_requires_additional_source_validation"
                    if viewport_source_blocked
                    else "blocked_by_temp_visual_scene_source_validation_unavailable"
                    if temp_context_source_blocked
                    else "blocked_by_nonblocking_viewport_or_swapchain_probe_source_validation_unavailable"
                    if nonblocking_source_blocked
                    else "blocked_by_editor_asset_processor_negotiation_source_validation_unavailable"
                    if ap_negotiation_source_blocked
                    else "blocked_by_asset_processor_alignment_repair_source_validation_unavailable"
                    if asset_processor_alignment_source_blocked
                    else "blocked_by_editor_screenshot_capture_requires_additional_source_validation"
                )
            )
            if operator_ap_alignment_remediation_verification_mode:
                template.update(_operator_ap_alignment_remediation_verification_payload(template))
            template.update(
                {
                    "live_non_null_editor_launch_attempted": False,
                    "live_non_null_editor_launch_completed": False,
                    "live_non_null_editor_launch_verified": False,
                    "live_non_null_editor_launch_blocker": preflight_blocker,
                    "non_null_editor_launch_attempted": False,
                    "non_null_editor_launch_completed": False,
                    "non_null_editor_launch_verified": False,
                    "non_null_editor_launch_exit_code": None,
                    "non_null_editor_launch_blocker": preflight_blocker,
                    "editor_screenshot_capture_artifact_readiness_attempted": False,
                    "editor_screenshot_capture_artifact_readiness_completed": False,
                    "editor_screenshot_capture_artifact_readiness_verified": False,
                    "editor_screenshot_capture_artifact_readiness_blocker": preflight_blocker,
                    "editor_active_viewport_temp_scene_readiness_attempted": False,
                    "editor_active_viewport_temp_scene_readiness_completed": False,
                    "editor_active_viewport_temp_scene_readiness_verified": False,
                    "editor_active_viewport_temp_scene_readiness_blocker": preflight_blocker,
                    "temp_visual_scene_context_exercise_attempted": False,
                    "temp_visual_scene_context_exercise_completed": False,
                    "temp_visual_scene_context_exercise_verified": False,
                    "temp_visual_scene_context_exercise_blocker": preflight_blocker,
                    "temp_visual_scene_blocker": preflight_blocker,
                    "nonblocking_viewport_swapchain_probe_attempted": False,
                    "nonblocking_viewport_swapchain_probe_verified": False,
                    "nonblocking_viewport_swapchain_probe_blocker": preflight_blocker,
                    "editor_asset_processor_negotiation_preflight_attempted": False,
                    "editor_asset_processor_negotiation_preflight_verified": False,
                    "editor_asset_processor_negotiation_blocker": preflight_blocker,
                    "viewport_window_materialization_repair_attempted": False,
                    "viewport_window_materialization_repair_verified": False,
                    "viewport_window_materialization_blocker": preflight_blocker,
                    "editor_visual_material_capture_requested": False,
                    "editor_visual_material_capture_request_accepted": False,
                    "editor_visual_material_capture_completed": False,
                    "visual_material_capture_readiness_verified": False,
                    "visual_material_gate_verified": False,
                    "runtime_character_proof_verified": False,
                }
            )
            finished_at = _utc_now()
            duration_seconds = round(time.monotonic() - start_time, 3)
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            _write_progress_marker(
                progress_path,
                phase="wrapper",
                step="live_non_null_editor_launch_preflight_blocked",
                status="blocked",
                started_monotonic=start_time,
                message=(
                    "Live non-null Editor launch was not attempted because desktop/GPU/RHI readiness regressed."
                    if blocked_by_readiness
                    else "Live non-null Editor launch was not attempted because launch source validation failed."
                    if blocked_by_launch_source
                    else "Active viewport/temp scene readiness was not attempted because source validation failed."
                    if viewport_source_blocked
                    else "Safe temp visual scene context exercise was not attempted because source validation failed."
                    if temp_context_source_blocked
                    else "Non-blocking viewport/SwapChain readiness probe was not attempted because source validation failed."
                    if nonblocking_source_blocked
                    else "Editor screenshot capture was not attempted because capture source validation failed."
                ),
                error_code=MXN_RUNTIME_SMOKE_FAIL,
            )
            progress_markers = _load_progress_markers(progress_path)
            report = dict(template)
            report.update(
                {
                    "generated_at": finished_at,
                    "status": "pass",
                    "diagnostic_mode": diagnostic_mode,
                    "live_editor_execution": False,
                    "live_asset_processor_batch_execution": False,
                    "live_publication": False,
                    "release_packaging": False,
                    "production_level_mutation": False,
                    "defaultlevel_mutation": False,
                    "exit_code": None,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_seconds": duration_seconds,
                    "timeout_seconds": selected_timeout_seconds,
                    "timed_out": False,
                    "timeout_stall": False,
                    "process_cleanup": {"attempted": False, "method": "preflight_no_process", "return_code": None},
                    "process_tree_cleanup": {"attempted": False, "method": "preflight_no_process", "return_code": None},
                    "stdout_log_ref": _repo_relative(stdout_path),
                    "stderr_log_ref": _repo_relative(stderr_path),
                    "editor_log_ref": "",
                    "progress_log_ref": _repo_relative(progress_path),
                    "last_progress_marker": _last_relevant_progress_marker(progress_markers),
                    "stall_phase": "",
                    "script_path_redacted": _redact_path(str(script_path)),
                    "script_path_mode": "absolute",
                    "editor_command_working_directory": _redact_path(str(project_path)),
                    "apb_baseline_ref": _repo_relative(apb_baseline),
                    "product_evidence_summary": product_summary,
                    "command_preview": _redacted_argv(argv),
                    "command_argv_redacted": _redacted_argv(argv),
                    "errors": [],
                    "warnings": [],
                    "messages": _unique(
                        list(report.get("messages", []))
                        + [
                            "Live non-null Editor launch was blocked before process start by readiness/source-validation preflight."
                        ]
                    ),
                }
            )
            report["evidence_refs"] = _merge_evidence_refs(
                report.get("evidence_refs", []),
                [
                    {"id": "live-non-null-editor-launch-report", "kind": "editor_smoke_report", "path": _repo_relative(report_path)},
                    {"id": "editor-smoke-progress-log", "kind": "editor_smoke_progress_log", "path": _repo_relative(progress_path)},
                    {"id": "apb-baseline", "kind": "asset_processor_batch_report", "path": _repo_relative(apb_baseline)},
                ],
            )
            schema_result = schema_validate(report, load_json(SCHEMA_PATH))
            semantic_result = validate_editor_smoke_report(report, strict=True)
            if schema_result.status == "fail" or semantic_result.status == "fail":
                report["status"] = "fail"
                report["errors"] = _unique(schema_result.error_codes + semantic_result.error_codes)
                report["messages"] = _unique(report.get("messages", []) + schema_result.messages + semantic_result.messages)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            template_path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
            return report
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
    if non_null_render_capture_mode:
        editor_env["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] = selected_render_capture_rhi
        editor_env.setdefault("MAXINE_ENABLE_NON_NULL_EDITOR_RENDER_CAPTURE_ENVELOPE", "1")
        editor_env.setdefault("MAXINE_ALLOW_NON_NULL_EDITOR_RENDER_CAPTURE_ENVELOPE", "1")
    if live_non_null_editor_launch_mode:
        editor_env["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] = selected_render_capture_rhi
        editor_env.setdefault("MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH", "1")
        editor_env.setdefault("MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH", "1")
    if screenshot_capture_artifact_readiness_mode:
        editor_env["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] = selected_render_capture_rhi
        editor_env["MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_ROOT"] = str(output_dir)
        editor_env["MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_PATH"] = str(
            output_dir / "editor_screenshot_capture_artifact_readiness.png"
        )
        editor_env.setdefault("MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH", "1")
        editor_env.setdefault("MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_READINESS", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_READINESS", "1")
    if active_viewport_temp_scene_readiness_mode:
        editor_env["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] = selected_render_capture_rhi
        editor_env.setdefault("MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH", "1")
        editor_env.setdefault("MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_ACTIVE_VIEWPORT_TEMP_SCENE_READINESS", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_ACTIVE_VIEWPORT_TEMP_SCENE_READINESS", "1")
    if safe_temp_scene_exercise_mode:
        editor_env["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] = selected_render_capture_rhi
        editor_env["MAXINE_EDITOR_SAFE_TEMP_VISUAL_SCENE_LEVEL_NAME"] = safe_temp_scene_level_name
        editor_env["MAXINE_EDITOR_SAFE_TEMP_VISUAL_SCENE_LEVEL_PATH"] = str(safe_temp_scene_abs)
        editor_env.setdefault("MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH", "1")
        editor_env.setdefault("MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT", "1")
    if nonblocking_probe_family_mode:
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS", "1")
    if ap_negotiation_viewport_materialization_mode:
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS", "1")
    if asset_processor_alignment_family_mode:
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS", "1")
        editor_env.setdefault("MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR", "1")
        editor_env.setdefault("MAXINE_ALLOW_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR", "1")
    if operator_ap_alignment_remediation_verification_mode:
        editor_env.setdefault("MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
    if focused_viewport_materialization_mode:
        editor_env.setdefault("MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
    if editor_main_window_activation_deep_dive_mode:
        editor_env.setdefault("MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE", "1")
    if alternate_editor_window_visible_shell_mode:
        editor_env.setdefault("MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL", "1")
        editor_env.setdefault("MAXINE_ALLOW_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL", "1")
    if editor_layout_bootstrap_window_lifecycle_mode:
        editor_env.setdefault("MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL", "1")
        editor_env.setdefault("MAXINE_ALLOW_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE", "1")
    if editor_bootstrap_wait_shell_ready_mode:
        editor_env.setdefault("MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
        editor_env.setdefault("MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL", "1")
        editor_env.setdefault("MAXINE_ALLOW_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE", "1")
        editor_env.setdefault("MAXINE_ENABLE_EDITOR_BOOTSTRAP_WAIT_SHELL_READY_SYNCHRONIZATION", "1")
        editor_env.setdefault("MAXINE_ALLOW_EDITOR_BOOTSTRAP_WAIT_SHELL_READY_SYNCHRONIZATION", "1")
    editor_env["MAXINE_EDITOR_SMOKE_TEMP_LEVEL_NAME"] = level_name_for_editor
    editor_env["MAXINE_EDITOR_SMOKE_TEMP_LEVEL_PATH"] = str(project_path / temp_level_rel)
    editor_env["MAXINE_EDITOR_SMOKE_ALLOW_TEMP_SANDBOX_LEVEL"] = "1"
    editor_env["MAXINE_ALLOW_LIVE_PUBLICATION"] = "0"
    editor_env["MAXINE_ENABLE_RELEASE_PACKAGING"] = "0"
    editor_env.setdefault("PYTHONIOENCODING", "utf-8")

    safe_temp_scene_mutation_before = (
        _safe_temp_visual_scene_mutation_snapshot(project_path) if safe_temp_scene_exercise_mode else {}
    )
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
    if non_null_render_capture_mode:
        command = " ".join(argv)
        report.update(
            {
                "non_null_editor_render_capture_rhi_requested": selected_render_capture_rhi,
                "non_null_editor_render_capture_null_renderer_used": (
                    "-NullRenderer" in command or "-rhi=Null" in command or "-rhi=null" in command.lower()
                ),
                "non_null_editor_render_capture_editor_launched": True,
                "non_null_editor_render_capture_editor_exited_cleanly": (not timed_out and proc.returncode == 0),
            }
        )
    if live_non_null_editor_launch_mode:
        command = " ".join(argv)
        null_renderer_used = "-NullRenderer" in command or "-rhi=Null" in command or "-rhi=null" in command.lower()
        blocking_matches: List[Dict[str, Any]] = []
        selected_log_scan_passed = not blocking_matches and not timed_out and proc.returncode == 0
        python_wrapper_executed = runtime_report_found and report.get("live_non_null_editor_launch_python_wrapper_executed") is True
        launch_completed = bool(not timed_out and runtime_report_found)
        launch_verified = bool(
            launch_completed
            and proc.returncode == 0
            and python_wrapper_executed
            and selected_log_scan_passed
            and not null_renderer_used
            and report.get("visible_desktop_session_verified") is True
            and report.get("gpu_or_driver_readiness_verified") is True
            and report.get("rhi_readiness_verified") is True
            and report.get("defaultlevel_mutation") is not True
            and report.get("production_level_mutation") is not True
            and report.get("editor_visual_material_capture_requested") is not True
            and report.get("editor_visual_material_temp_scene_created") is not True
        )
        if launch_verified:
            launch_blocker = ""
        elif timed_out:
            launch_blocker = "blocked_by_live_non_null_editor_launch_timeout"
        elif proc.returncode != 0:
            launch_blocker = "blocked_by_live_non_null_editor_exit_nonzero"
        elif not runtime_report_found:
            launch_blocker = "blocked_by_live_non_null_editor_python_wrapper_failed"
        elif null_renderer_used:
            launch_blocker = "blocked_by_editor_viewport_capture_requires_non_null_rhi"
        elif not selected_log_scan_passed:
            launch_blocker = "blocked_by_live_non_null_editor_selected_log_signal"
        else:
            launch_blocker = "blocked_by_live_non_null_editor_launch_not_verified"
        report.update(
            {
                "live_non_null_editor_launch_attempted": True,
                "live_non_null_editor_launch_completed": launch_completed,
                "live_non_null_editor_launch_verified": launch_verified,
                "live_non_null_editor_launch_blocker": launch_blocker,
                "live_non_null_editor_launch_command": _redacted_argv(argv),
                "live_non_null_editor_launch_selected_rhi": selected_render_capture_rhi,
                "live_non_null_editor_launch_null_renderer_used": null_renderer_used,
                "live_non_null_editor_launch_editor_executable": _redact_path(str(editor_executable)),
                "live_non_null_editor_launch_project_path": _redact_path(str(project_path)),
                "live_non_null_editor_launch_wrapper_path": _repo_relative(script_path),
                "live_non_null_editor_launch_wrapper_bootstrap_verified": report.get(
                    "live_non_null_editor_launch_wrapper_bootstrap_verified", False
                ),
                "live_non_null_editor_launch_python_wrapper_executed": python_wrapper_executed,
                "live_non_null_editor_launch_exit_code": proc.returncode,
                "live_non_null_editor_launch_exit_code_hex": f"0x{(proc.returncode or 0) & 0xFFFFFFFF:08X}",
                "live_non_null_editor_launch_timeout": timed_out,
                "live_non_null_editor_launch_killed": bool(process_cleanup.get("attempted")),
                "live_non_null_editor_launch_stdout_ref": _repo_relative(stdout_path),
                "live_non_null_editor_launch_stderr_ref": _repo_relative(stderr_path),
                "live_non_null_editor_launch_log_ref": _find_editor_log_ref(project_path),
                "live_non_null_editor_launch_selected_log_scan_passed": selected_log_scan_passed,
                "live_non_null_editor_launch_selected_log_blocking_matches": blocking_matches,
                "non_null_editor_launch_attempted": True,
                "non_null_editor_launch_completed": launch_completed,
                "non_null_editor_launch_verified": launch_verified,
                "non_null_editor_launch_exit_code": proc.returncode,
                "non_null_editor_launch_blocker": launch_blocker,
                "non_null_editor_render_capture_editor_launched": True,
                "non_null_editor_render_capture_editor_exited_cleanly": launch_verified,
                "non_null_editor_render_capture_rhi_requested": selected_render_capture_rhi,
                "non_null_editor_render_capture_null_renderer_used": null_renderer_used,
                "editor_visual_material_capture_requested": False,
                "editor_visual_material_capture_completed": False,
                "visual_material_capture_readiness_verified": False,
                "visual_material_rendered_evidence_gate_attempted": False,
                "visual_material_rendered_evidence_gate_verified": False,
                "visual_material_gate_claimed": False,
                "visual_material_gate_verified": False,
                "full_runtime_character_visual_material_gate_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
    if screenshot_capture_artifact_readiness_mode:
        command = " ".join(argv)
        null_renderer_used = "-NullRenderer" in command or "-rhi=Null" in command or "-rhi=null" in command.lower()
        blocking_matches = []
        selected_log_scan_passed = not blocking_matches and not timed_out and proc.returncode == 0
        python_wrapper_executed = runtime_report_found and report.get("live_non_null_editor_launch_python_wrapper_executed") is True
        launch_completed = bool(not timed_out and runtime_report_found)
        launch_verified = bool(
            launch_completed
            and proc.returncode == 0
            and python_wrapper_executed
            and selected_log_scan_passed
            and not null_renderer_used
            and report.get("visible_desktop_session_verified") is True
            and report.get("gpu_or_driver_readiness_verified") is True
            and report.get("rhi_readiness_verified") is True
            and report.get("defaultlevel_mutation") is not True
            and report.get("production_level_mutation") is not True
            and report.get("editor_visual_material_temp_scene_created") is not True
        )
        capture_verified = report.get("editor_screenshot_capture_artifact_readiness_verified") is True
        if launch_verified and capture_verified:
            capture_blocker = ""
        elif timed_out:
            capture_blocker = "blocked_by_live_non_null_editor_launch_timeout"
        elif proc.returncode != 0:
            capture_blocker = "blocked_by_editor_screenshot_capture_exit_nonzero"
        elif not runtime_report_found:
            capture_blocker = "blocked_by_live_non_null_editor_python_wrapper_failed"
        elif null_renderer_used:
            capture_blocker = "blocked_by_editor_viewport_capture_requires_non_null_rhi"
        elif not selected_log_scan_passed:
            capture_blocker = "blocked_by_editor_screenshot_capture_selected_log_signal"
        elif str(report.get("editor_screenshot_capture_artifact_readiness_blocker", "")).strip():
            capture_blocker = str(report.get("editor_screenshot_capture_artifact_readiness_blocker", "")).strip()
        else:
            capture_blocker = "blocked_by_editor_screenshot_capture_completion_not_observed"
        report.update(
            {
                "live_non_null_editor_launch_attempted": True,
                "live_non_null_editor_launch_completed": launch_completed,
                "live_non_null_editor_launch_verified": launch_verified,
                "live_non_null_editor_launch_blocker": "" if launch_verified else capture_blocker,
                "live_non_null_editor_launch_command": _redacted_argv(argv),
                "live_non_null_editor_launch_selected_rhi": selected_render_capture_rhi,
                "live_non_null_editor_launch_null_renderer_used": null_renderer_used,
                "live_non_null_editor_launch_editor_executable": _redact_path(str(editor_executable)),
                "live_non_null_editor_launch_project_path": _redact_path(str(project_path)),
                "live_non_null_editor_launch_wrapper_path": _repo_relative(script_path),
                "live_non_null_editor_launch_wrapper_bootstrap_verified": report.get(
                    "live_non_null_editor_launch_wrapper_bootstrap_verified", False
                ),
                "live_non_null_editor_launch_python_wrapper_executed": python_wrapper_executed,
                "live_non_null_editor_launch_exit_code": proc.returncode,
                "live_non_null_editor_launch_exit_code_hex": f"0x{(proc.returncode or 0) & 0xFFFFFFFF:08X}",
                "live_non_null_editor_launch_timeout": timed_out,
                "live_non_null_editor_launch_killed": bool(process_cleanup.get("attempted")),
                "live_non_null_editor_launch_stdout_ref": _repo_relative(stdout_path),
                "live_non_null_editor_launch_stderr_ref": _repo_relative(stderr_path),
                "live_non_null_editor_launch_log_ref": _find_editor_log_ref(project_path),
                "live_non_null_editor_launch_selected_log_scan_passed": selected_log_scan_passed,
                "live_non_null_editor_launch_selected_log_blocking_matches": blocking_matches,
                "non_null_editor_launch_attempted": True,
                "non_null_editor_launch_completed": launch_completed,
                "non_null_editor_launch_verified": launch_verified,
                "non_null_editor_launch_exit_code": proc.returncode,
                "non_null_editor_launch_blocker": "" if launch_verified else capture_blocker,
                "non_null_editor_render_capture_editor_launched": True,
                "non_null_editor_render_capture_editor_exited_cleanly": launch_verified,
                "non_null_editor_render_capture_rhi_requested": selected_render_capture_rhi,
                "non_null_editor_render_capture_null_renderer_used": null_renderer_used,
                "editor_screenshot_capture_artifact_readiness_verified": bool(capture_verified and launch_verified),
                "editor_screenshot_capture_artifact_readiness_blocker": ""
                if capture_verified and launch_verified
                else capture_blocker,
                "editor_visual_material_selected_log_scan_passed": selected_log_scan_passed,
                "visual_material_capture_readiness_verified": bool(capture_verified and launch_verified),
                "visual_material_rendered_evidence_gate_attempted": False,
                "visual_material_rendered_evidence_gate_verified": False,
                "visual_material_gate_claimed": False,
                "visual_material_gate_verified": False,
                "full_runtime_character_visual_material_gate_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
    if safe_temp_scene_exercise_mode:
        command = " ".join(argv)
        null_renderer_used = "-NullRenderer" in command or "-rhi=Null" in command or "-rhi=null" in command.lower()
        blocking_matches = []
        selected_log_scan_passed = not blocking_matches and not timed_out and proc.returncode == 0
        python_wrapper_executed = runtime_report_found and report.get("live_non_null_editor_launch_python_wrapper_executed") is True
        launch_completed = bool(not timed_out and runtime_report_found)
        launch_verified = bool(
            launch_completed
            and proc.returncode == 0
            and python_wrapper_executed
            and selected_log_scan_passed
            and not null_renderer_used
            and report.get("visible_desktop_session_verified") is True
            and report.get("gpu_or_driver_readiness_verified") is True
            and report.get("rhi_readiness_verified") is True
            and report.get("defaultlevel_mutation") is not True
            and report.get("production_level_mutation") is not True
            and report.get("editor_visual_material_capture_requested") is not True
        )
        if launch_verified:
            launch_blocker = ""
        elif timed_out:
            launch_blocker = "blocked_by_live_non_null_editor_launch_timeout"
        elif proc.returncode != 0:
            launch_blocker = "blocked_by_live_non_null_editor_exit_nonzero"
        elif not runtime_report_found:
            launch_blocker = "blocked_by_live_non_null_editor_python_wrapper_failed"
        elif null_renderer_used:
            launch_blocker = "blocked_by_editor_viewport_capture_requires_non_null_rhi"
        elif not selected_log_scan_passed:
            launch_blocker = "blocked_by_live_non_null_editor_selected_log_signal"
        else:
            launch_blocker = "blocked_by_live_non_null_editor_launch_not_verified"
        report.update(
            {
                "live_non_null_editor_launch_attempted": True,
                "live_non_null_editor_launch_completed": launch_completed,
                "live_non_null_editor_launch_verified": launch_verified,
                "live_non_null_editor_launch_blocker": launch_blocker,
                "live_non_null_editor_launch_command": _redacted_argv(argv),
                "live_non_null_editor_launch_selected_rhi": selected_render_capture_rhi,
                "live_non_null_editor_launch_null_renderer_used": null_renderer_used,
                "live_non_null_editor_launch_editor_executable": _redact_path(str(editor_executable)),
                "live_non_null_editor_launch_project_path": _redact_path(str(project_path)),
                "live_non_null_editor_launch_wrapper_path": _repo_relative(script_path),
                "live_non_null_editor_launch_wrapper_bootstrap_verified": report.get(
                    "live_non_null_editor_launch_wrapper_bootstrap_verified", False
                ),
                "live_non_null_editor_launch_python_wrapper_executed": python_wrapper_executed,
                "live_non_null_editor_launch_exit_code": proc.returncode,
                "live_non_null_editor_launch_exit_code_hex": f"0x{(proc.returncode or 0) & 0xFFFFFFFF:08X}",
                "live_non_null_editor_launch_timeout": timed_out,
                "live_non_null_editor_launch_killed": bool(process_cleanup.get("attempted")),
                "live_non_null_editor_launch_stdout_ref": _repo_relative(stdout_path),
                "live_non_null_editor_launch_stderr_ref": _repo_relative(stderr_path),
                "live_non_null_editor_launch_log_ref": _find_editor_log_ref(project_path),
                "live_non_null_editor_launch_selected_log_scan_passed": selected_log_scan_passed,
                "live_non_null_editor_launch_selected_log_blocking_matches": blocking_matches,
                "non_null_editor_launch_attempted": True,
                "non_null_editor_launch_completed": launch_completed,
                "non_null_editor_launch_verified": launch_verified,
                "non_null_editor_launch_exit_code": proc.returncode,
                "non_null_editor_launch_blocker": launch_blocker,
                "non_null_editor_render_capture_editor_launched": True,
                "non_null_editor_render_capture_editor_exited_cleanly": launch_verified,
                "non_null_editor_render_capture_rhi_requested": selected_render_capture_rhi,
                "non_null_editor_render_capture_null_renderer_used": null_renderer_used,
                "editor_visual_material_capture_requested": False,
                "editor_visual_material_capture_request_accepted": False,
                "editor_visual_material_capture_completed": False,
                "visual_material_capture_readiness_verified": False,
                "visual_material_rendered_evidence_gate_attempted": False,
                "visual_material_rendered_evidence_gate_verified": False,
                "visual_material_gate_claimed": False,
                "visual_material_gate_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
        report = _postprocess_safe_temp_visual_scene_cleanup(
            report,
            project_path=project_path,
            temp_scene_abs=safe_temp_scene_abs,
            mutation_before=safe_temp_scene_mutation_before,
        )
        if nonblocking_probe_family_mode:
            framecapture_target_verified = report.get("framecapture_target_readiness_verified") is True
            report.update(
                {
                    "safe_temp_visual_scene_context_preserved": report.get(
                        "temp_visual_scene_context_exercise_verified"
                    )
                    is True,
                    "editor_visual_material_capture_target_readiness_verified": framecapture_target_verified,
                    "visual_material_capture_readiness_verified": False,
                    "visual_material_rendered_evidence_gate_attempted": False,
                    "visual_material_rendered_evidence_gate_verified": False,
                    "visual_material_gate_claimed": False,
                    "visual_material_gate_verified": False,
                    "full_runtime_character_visual_material_gate_verified": False,
                    "runtime_character_proof_claimed": False,
                    "runtime_character_proof_verified": False,
                }
            )
        if ap_negotiation_viewport_materialization_mode or asset_processor_alignment_family_mode:
            report.update(
                {
                    "editor_visual_material_capture_requested": False,
                    "editor_visual_material_capture_request_accepted": False,
                    "editor_visual_material_capture_completed": False,
                    "visual_material_capture_readiness_verified": False,
                    "visual_material_rendered_evidence_gate_attempted": False,
                    "visual_material_rendered_evidence_gate_verified": False,
                    "visual_material_gate_claimed": False,
                    "visual_material_gate_verified": False,
                    "full_runtime_character_visual_material_gate_verified": False,
                    "runtime_character_proof_claimed": False,
                    "runtime_character_proof_verified": False,
                    "asset_cache_deleted": False,
                    "asset_cache_deletion_attempted": False,
                    "asset_processor_database_wipe_attempted": False,
                    "cache_heuristic_used": False,
                }
            )
        if operator_ap_alignment_remediation_verification_mode:
            report.update(_operator_ap_alignment_remediation_verification_payload(report))
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


def _tree_metadata_fingerprint(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"exists": False, "file_count": 0, "dir_count": 0, "fingerprint": ""}
    rows: List[str] = []
    file_count = 0
    dir_count = 0
    try:
        for child in sorted(path.rglob("*"), key=lambda item: item.as_posix().lower()):
            try:
                stat = child.stat()
            except OSError:
                continue
            rel = child.relative_to(path).as_posix().lower()
            if child.is_dir():
                dir_count += 1
                rows.append(f"d:{rel}:{stat.st_mtime_ns}")
            else:
                file_count += 1
                rows.append(f"f:{rel}:{stat.st_size}:{stat.st_mtime_ns}")
    except Exception as exc:
        return {
            "exists": True,
            "file_count": file_count,
            "dir_count": dir_count,
            "fingerprint": "",
            "error": str(exc),
        }
    import hashlib

    return {
        "exists": True,
        "file_count": file_count,
        "dir_count": dir_count,
        "fingerprint": hashlib.sha256(("\n".join(rows)).encode("utf-8")).hexdigest(),
    }


def _safe_temp_visual_scene_mutation_snapshot(project_path: Path) -> Dict[str, Any]:
    levels_root = project_path / "Levels"
    production_levels: Dict[str, Any] = {}
    if levels_root.exists():
        for child in levels_root.iterdir():
            if child.name.lower() == "_maxine_visual_smoke":
                continue
            if "production" in child.name.lower():
                production_levels[child.name] = _tree_metadata_fingerprint(child)
    return {
        "defaultlevel": _tree_metadata_fingerprint(levels_root / "defaultlevel"),
        "defaultlevel_title": _tree_metadata_fingerprint(levels_root / "DefaultLevel"),
        "production_levels": production_levels,
        "production_character_assets": _tree_metadata_fingerprint(
            project_path / "Assets" / "Characters" / "MAXINE_GoldenCorpus"
        ),
    }


def _safe_temp_visual_scene_mutation_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> Dict[str, bool]:
    return {
        "defaultlevel": before.get("defaultlevel") != after.get("defaultlevel")
        or before.get("defaultlevel_title") != after.get("defaultlevel_title"),
        "production_level": before.get("production_levels") != after.get("production_levels"),
        "production_character_asset": before.get("production_character_assets") != after.get(
            "production_character_assets"
        ),
    }


def _postprocess_safe_temp_visual_scene_cleanup(
    report: Mapping[str, Any],
    *,
    project_path: Path,
    temp_scene_abs: Path,
    mutation_before: Mapping[str, Any],
) -> Dict[str, Any]:
    payload = dict(report)
    cleanup_attempted = True
    cleanup_completed = False
    cleanup_blocker = ""
    cleanup_message = ""
    try:
        resolved_target = temp_scene_abs.resolve(strict=False)
        approved_root = (
            project_path / "Levels" / "_maxine_visual_smoke" / "editor_safe_temp_visual_scene_display_context"
        ).resolve(strict=False)
        resolved_target.relative_to(approved_root)
        if "defaultlevel" in resolved_target.as_posix().lower() or "production" in resolved_target.as_posix().lower():
            cleanup_blocker = "blocked_by_mutation_policy"
        elif resolved_target == approved_root:
            cleanup_blocker = "blocked_by_mutation_policy"
        elif resolved_target.exists():
            shutil.rmtree(resolved_target)
            cleanup_completed = not resolved_target.exists()
            if not cleanup_completed:
                cleanup_blocker = "failed_safe_cleanup_incomplete"
        else:
            cleanup_completed = True
            cleanup_message = "run-owned temp scene path was already absent"
    except Exception as exc:
        cleanup_blocker = "failed_safe_cleanup_incomplete"
        cleanup_message = str(exc)
        resolved_target = temp_scene_abs.resolve(strict=False)

    mutation_after = _safe_temp_visual_scene_mutation_snapshot(project_path)
    mutation_diff = _safe_temp_visual_scene_mutation_diff(mutation_before, mutation_after)
    verified = bool(
        payload.get("temp_visual_scene_created") is True
        and payload.get("temp_visual_scene_opened") is True
        and payload.get("temp_visual_scene_saved") is True
        and cleanup_attempted
        and cleanup_completed
        and not cleanup_blocker
        and not any(mutation_diff.values())
        and payload.get("live_non_null_editor_launch_verified") is True
    )
    blocker = ""
    if not verified:
        blocker = cleanup_blocker or str(payload.get("temp_visual_scene_blocker", "")).strip() or "failed_safe_cleanup_incomplete"
        if any(mutation_diff.values()):
            blocker = "blocked_by_mutation_policy"
    payload.update(
        {
            "temp_visual_scene_cleanup_attempted": cleanup_attempted,
            "temp_visual_scene_cleanup_completed": cleanup_completed,
            "temp_visual_scene_cleanup_policy": "post_editor_exit_run_owned_temp_root_cleanup",
            "temp_visual_scene_cleanup_path_abs": str(resolved_target),
            "temp_visual_scene_cleanup_message": cleanup_message,
            "temp_visual_scene_context_exercise_verified": verified,
            "temp_visual_scene_context_exercise_blocker": "" if verified else blocker,
            "temp_visual_scene_blocker": "" if verified else blocker,
            "editor_temp_visual_scene_cleanup_verified": cleanup_completed,
            "editor_visual_material_cleanup_verified": cleanup_completed,
            "editor_visual_material_capture_target_readiness_verified": verified,
            "defaultlevel_mutation_checked": True,
            "defaultlevel_mutation_detected": bool(mutation_diff["defaultlevel"]),
            "production_level_mutation_checked": True,
            "production_level_mutation_detected": bool(mutation_diff["production_level"]),
            "production_character_asset_mutation_checked": True,
            "production_character_asset_mutation_detected": bool(mutation_diff["production_character_asset"]),
            "defaultlevel_mutation": bool(mutation_diff["defaultlevel"]),
            "production_level_mutation": bool(mutation_diff["production_level"]),
            "editor_temp_visual_scene_defaultlevel_mutation": bool(mutation_diff["defaultlevel"]),
            "editor_temp_visual_scene_production_level_mutation": bool(mutation_diff["production_level"]),
            "editor_visual_material_defaultlevel_mutation": bool(mutation_diff["defaultlevel"]),
            "editor_visual_material_production_level_mutation": bool(mutation_diff["production_level"]),
            "visual_material_capture_readiness_verified": False,
            "visual_material_rendered_evidence_gate_attempted": False,
            "visual_material_rendered_evidence_gate_verified": False,
            "visual_material_gate_claimed": False,
            "visual_material_gate_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    )
    return payload


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
        "editor_viewport_visual_material_evidence_attempted": False,
        "editor_viewport_visual_material_evidence_completed": False,
        "editor_viewport_visual_material_evidence_source_validation_status": "",
        "editor_viewport_visual_material_evidence_source_validation_verified": False,
        "editor_viewport_visual_material_evidence_source_validation": {},
        "editor_viewport_visual_material_evidence_source_files": [],
        "editor_viewport_visual_material_evidence_blocker": "",
        "editor_viewport_visual_material_evidence_candidate_matrix": [],
        "editor_viewport_visual_material_evidence_selected_strategy": "",
        "non_null_editor_render_capture_envelope_attempted": False,
        "non_null_editor_render_capture_envelope_completed": False,
        "non_null_editor_render_capture_envelope_source_validation_status": "",
        "non_null_editor_render_capture_envelope_source_validation_verified": False,
        "non_null_editor_render_capture_envelope_source_validation": {},
        "non_null_editor_render_capture_envelope_source_files": [],
        "non_null_editor_render_capture_envelope_verified": False,
        "non_null_editor_render_capture_envelope_blocker": "",
        "non_null_editor_render_capture_envelope_candidate_matrix": [],
        "non_null_editor_render_capture_envelope_selected_strategy": "",
        "non_null_editor_render_capture_rhi_requested": "",
        "non_null_editor_render_capture_null_renderer_used": False,
        "non_null_editor_render_capture_editor_launched": False,
        "non_null_editor_render_capture_editor_exited_cleanly": False,
        "non_null_editor_render_capture_requires_visible_desktop": False,
        "non_null_editor_render_capture_gpu_or_driver_ready": None,
        "non_null_editor_visual_runner_readiness_attempted": False,
        "non_null_editor_visual_runner_readiness_completed": False,
        "non_null_editor_visual_runner_readiness_source_validation_status": "",
        "non_null_editor_visual_runner_readiness_source_validation_verified": False,
        "non_null_editor_visual_runner_readiness_source_validation": {},
        "non_null_editor_visual_runner_readiness_source_files": [],
        "non_null_editor_visual_runner_readiness_verified": False,
        "non_null_editor_visual_runner_readiness_blocker": "",
        "non_null_editor_visual_runner_readiness_candidate_matrix": [],
        "non_null_editor_visual_runner_readiness_selected_strategy": "",
        "visible_desktop_session_check_attempted": False,
        "visible_desktop_session_verified": False,
        "visible_desktop_session_blocker": "",
        "gpu_or_driver_readiness_check_attempted": False,
        "gpu_or_driver_readiness_verified": False,
        "gpu_or_driver_readiness_blocker": "",
        "selected_rhi": "",
        "rhi_readiness_check_attempted": False,
        "rhi_readiness_verified": False,
        "rhi_readiness_blocker": "",
        "non_null_editor_launch_attempted": False,
        "non_null_editor_launch_completed": False,
        "non_null_editor_launch_verified": False,
        "non_null_editor_launch_exit_code": None,
        "non_null_editor_launch_blocker": "",
        "live_non_null_editor_launch_attempted": False,
        "live_non_null_editor_launch_completed": False,
        "live_non_null_editor_launch_verified": False,
        "live_non_null_editor_launch_blocker": "",
        "live_non_null_editor_launch_candidate_matrix": [],
        "live_non_null_editor_launch_selected_strategy": "",
        "live_non_null_editor_launch_source_validation_status": "",
        "live_non_null_editor_launch_source_validation_verified": False,
        "live_non_null_editor_launch_source_validation": {},
        "live_non_null_editor_launch_source_files": [],
        "live_non_null_editor_launch_command": [],
        "live_non_null_editor_launch_selected_rhi": "",
        "live_non_null_editor_launch_null_renderer_used": False,
        "live_non_null_editor_launch_editor_executable": "",
        "live_non_null_editor_launch_project_path": "",
        "live_non_null_editor_launch_wrapper_path": "",
        "live_non_null_editor_launch_wrapper_bootstrap_verified": False,
        "live_non_null_editor_launch_python_wrapper_executed": False,
        "live_non_null_editor_launch_exit_code": None,
        "live_non_null_editor_launch_exit_code_hex": "",
        "live_non_null_editor_launch_timeout": False,
        "live_non_null_editor_launch_killed": False,
        "live_non_null_editor_launch_stdout_ref": "",
        "live_non_null_editor_launch_stderr_ref": "",
        "live_non_null_editor_launch_log_ref": "",
        "live_non_null_editor_launch_selected_log_scan_passed": False,
        "live_non_null_editor_launch_selected_log_blocking_matches": [],
        "editor_screenshot_capture_artifact_readiness_attempted": False,
        "editor_screenshot_capture_artifact_readiness_completed": False,
        "editor_screenshot_capture_artifact_readiness_verified": False,
        "editor_screenshot_capture_artifact_readiness_blocker": "",
        "editor_screenshot_capture_artifact_readiness_candidate_matrix": [],
        "editor_screenshot_capture_artifact_readiness_selected_strategy": "",
        "editor_screenshot_capture_artifact_readiness_source_validation_status": "",
        "editor_screenshot_capture_artifact_readiness_source_validation_verified": False,
        "editor_screenshot_capture_artifact_readiness_source_validation": {},
        "editor_screenshot_capture_artifact_readiness_source_files": [],
        "null_renderer_used": False,
        "existing_nullrenderer_safe_editor_lane_preserved": True,
        "editor_temp_visual_scene_contract_attempted": False,
        "editor_temp_visual_scene_contract_pinned": False,
        "editor_temp_visual_scene_contract_verified": False,
        "editor_temp_visual_scene_contract_blocker": "",
        "editor_temp_visual_scene_approved_root": "",
        "editor_temp_visual_scene_defaultlevel_mutation": False,
        "editor_temp_visual_scene_production_level_mutation": False,
        "editor_temp_visual_scene_cleanup_policy_verified": False,
        "temp_visual_scene_context_exercise_attempted": False,
        "temp_visual_scene_context_exercise_completed": False,
        "temp_visual_scene_context_exercise_verified": False,
        "temp_visual_scene_context_exercise_blocker": "",
        "temp_visual_scene_source_validated": False,
        "temp_visual_scene_path": "",
        "temp_visual_scene_created": False,
        "temp_visual_scene_opened": False,
        "temp_visual_scene_saved": False,
        "temp_visual_scene_cleanup_attempted": False,
        "temp_visual_scene_cleanup_completed": False,
        "temp_visual_scene_cleanup_policy": "",
        "temp_visual_scene_blocker": "",
        "active_viewport_after_temp_context_attempted": False,
        "active_viewport_after_temp_context_verified": False,
        "active_viewport_after_temp_context_state": "",
        "active_viewport_after_temp_context_blocker": "",
        "framecapture_target_after_temp_context_attempted": False,
        "framecapture_target_after_temp_context_verified": False,
        "framecapture_target_after_temp_context_blocker": "",
        "nonblocking_viewport_swapchain_probe_attempted": False,
        "nonblocking_viewport_swapchain_probe_verified": False,
        "nonblocking_viewport_swapchain_probe_source_validated": False,
        "nonblocking_viewport_swapchain_probe_source_validation_status": "",
        "nonblocking_viewport_swapchain_probe_source_validation": {},
        "nonblocking_viewport_swapchain_probe_source_files": [],
        "nonblocking_viewport_swapchain_probe_blocker": "",
        "nonblocking_viewport_swapchain_probe_strategies": [],
        "active_default_viewport_probe_attempted": False,
        "active_default_viewport_probe_verified": False,
        "active_default_viewport_probe_state": "",
        "active_default_viewport_probe_blocker": "",
        "active_default_viewport_window_handle_attempted": False,
        "active_default_viewport_window_handle_verified": False,
        "active_default_viewport_window_handle_source_validated": False,
        "active_default_viewport_window_handle_blocker": "",
        "qt_viewport_widget_probe_attempted": False,
        "qt_viewport_widget_probe_verified": False,
        "qt_viewport_widget_probe_blocker": "",
        "os_process_window_inventory_attempted": False,
        "os_process_window_inventory_verified": False,
        "os_process_window_inventory_blocker": "",
        "atom_swapchain_readiness_probe_attempted": False,
        "atom_swapchain_readiness_probe_verified": False,
        "atom_swapchain_readiness_probe_source_validated": False,
        "atom_swapchain_readiness_probe_blocker": "",
        "framecapture_target_readiness_attempted": False,
        "framecapture_target_readiness_verified": False,
        "framecapture_target_readiness_source_validated": False,
        "framecapture_target_readiness_blocker": "",
        "editor_asset_processor_negotiation_preflight_attempted": False,
        "editor_asset_processor_negotiation_preflight_verified": False,
        "editor_asset_processor_negotiation_source_validated": False,
        "editor_asset_processor_negotiation_source_validation_status": "",
        "editor_asset_processor_negotiation_source_validation": {},
        "editor_asset_processor_negotiation_source_files": [],
        "editor_asset_processor_negotiation_state": "",
        "editor_asset_processor_negotiation_blocker": "",
        "editor_asset_processor_negotiation_repair_attempted": False,
        "editor_asset_processor_negotiation_repair_verified": False,
        "editor_asset_processor_negotiation_repair_blocker": "",
        "editor_asset_processor_modal_detection_attempted": False,
        "editor_asset_processor_negotiation_failed_modal_detected": False,
        "editor_asset_processor_negotiation_failed_modal_blocker": "",
        "editor_asset_processor_project_alignment_attempted": False,
        "editor_asset_processor_project_alignment_verified": False,
        "editor_asset_processor_project_alignment_blocker": "",
        "editor_asset_processor_build_root_alignment_attempted": False,
        "editor_asset_processor_build_root_alignment_verified": False,
        "editor_asset_processor_build_root_alignment_blocker": "",
        "editor_process_inventory_attempted": False,
        "editor_process_inventory_sanitized": [],
        "asset_processor_process_inventory_attempted": False,
        "asset_processor_process_inventory_sanitized": [],
        "asset_processor_process_running": False,
        "asset_processor_process_owner_verified": False,
        "asset_processor_restart_attempted": False,
        "asset_processor_restart_completed": False,
        "asset_processor_restart_blocker": "",
        "asset_processor_launch_attempted": False,
        "asset_processor_launch_completed": False,
        "asset_processor_launch_blocker": "",
        "viewport_window_materialization_repair_attempted": False,
        "viewport_window_materialization_repair_verified": False,
        "viewport_window_materialization_state": "",
        "viewport_window_materialization_blocker": "",
        "active_default_viewport_after_ap_alignment_attempted": False,
        "active_default_viewport_after_ap_alignment_verified": False,
        "active_default_viewport_after_ap_alignment_blocker": "",
        "framecapture_target_after_ap_alignment_attempted": False,
        "framecapture_target_after_ap_alignment_verified": False,
        "framecapture_target_after_ap_alignment_blocker": "",
        "atom_swapchain_after_ap_alignment_attempted": False,
        "atom_swapchain_after_ap_alignment_verified": False,
        "atom_swapchain_after_ap_alignment_blocker": "",
        "safe_temp_visual_scene_context_preserved": False,
        "defaultlevel_mutation_checked": False,
        "defaultlevel_mutation_detected": False,
        "production_level_mutation_checked": False,
        "production_level_mutation_detected": False,
        "production_character_asset_mutation_checked": False,
        "production_character_asset_mutation_detected": False,
        "editor_visual_material_capture_artifact_root": "",
        "editor_visual_material_capture_artifact_policy_verified": False,
        "editor_visual_material_capture_api_available_under_non_null_rhi": False,
        "editor_visual_material_temp_scene_created": False,
        "editor_visual_material_temp_scene_path": "",
        "editor_visual_material_defaultlevel_mutation": False,
        "editor_visual_material_production_level_mutation": False,
        "editor_visual_material_character_instantiated": False,
        "editor_visual_material_character_source_path": "",
        "editor_visual_material_character_product_or_prefab_path": "",
        "editor_visual_material_camera_or_view_framed": False,
        "editor_visual_material_light_or_environment_prepared": False,
        "editor_visual_material_capture_api_found": False,
        "editor_visual_material_capture_api_used": "",
        "editor_visual_material_capture_requested": False,
        "editor_visual_material_capture_request_accepted": False,
        "editor_visual_material_capture_completed": False,
        "editor_visual_material_capture_completion_source": "",
        "editor_visual_material_capture_artifact_path": "",
        "editor_visual_material_capture_artifact_exists": False,
        "editor_visual_material_capture_artifact_format": "",
        "editor_visual_material_capture_artifact_width": 0,
        "editor_visual_material_capture_artifact_height": 0,
        "editor_visual_material_capture_artifact_size_bytes": 0,
        "editor_visual_material_capture_artifact_sha256": "",
        "editor_visual_material_capture_content_validation_attempted": False,
        "editor_visual_material_capture_content_validation_verified": False,
        "editor_visual_material_nonblank_validation_attempted": False,
        "editor_visual_material_nonblank_validation_verified": False,
        "editor_visual_material_character_presence_validation_verified": False,
        "editor_visual_material_material_presence_validation_verified": False,
        "editor_visual_material_cleanup_verified": False,
        "editor_visual_material_selected_log_scan_passed": False,
        "visual_material_capture_readiness_verified": False,
        "visual_material_product_inventory_gate_verified": False,
        "visual_material_rendered_evidence_gate_attempted": False,
        "visual_material_rendered_evidence_gate_verified": False,
        "visual_material_gate_claimed": False,
        "visual_material_gate_verified": False,
        "full_runtime_character_visual_material_gate_verified": False,
        "full_runtime_character_proof_contract_pinned": False,
        "full_runtime_character_proof_contract_verified": False,
        "full_runtime_character_proof_satisfied_gates": [],
        "full_runtime_character_proof_unsatisfied_gates": [],
        "full_runtime_character_proof_deferred_gates": [],
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
        "approved_runtime_animation_component_wiring_editor_generation_attempted": False,
        "approved_runtime_animation_component_wiring_editor_generation_completed": False,
        "approved_runtime_animation_component_wiring_editor_generation_verified": False,
        "approved_runtime_animation_component_wiring_editor_generation_blocker": "",
        "approved_runtime_animation_component_wiring_source_prefab_path": "",
        "approved_runtime_animation_component_wiring_source_prefab_modified": False,
        "approved_runtime_animation_component_wiring_editor_generated_update_used": False,
        "approved_runtime_animation_component_wiring_hand_authored_unknown_json_used": False,
        "approved_runtime_animation_component_wiring_actor_component_added": False,
        "approved_runtime_animation_component_wiring_simple_motion_component_added": False,
        "approved_runtime_animation_component_wiring_anim_graph_component_added": False,
        "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_actor_asset_id": "",
        "approved_runtime_animation_component_wiring_motion_asset_id": "",
        "approved_runtime_animation_component_wiring_property_readback_verified": False,
        "approved_runtime_animation_component_wiring_prefab_save_verified": False,
        "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": False,
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
            "runtime_character_animation_playback_surface_status": "runtime_character_animation_playback_surface_not_attempted",
            "runtime_character_animation_playback_surface_diagnostic_attempted": False,
            "runtime_character_animation_playback_surface_diagnostic_completed": False,
            "runtime_character_animation_playback_surface_found": False,
            "runtime_character_animation_playback_surface_verified": False,
            "runtime_character_animation_playback_surface_blocker": "",
            "runtime_character_animation_playback_candidate_matrix": [],
            "runtime_character_animation_spawn_prerequisite_verified": False,
            "runtime_character_animation_product_load_prerequisite_verified": False,
            "runtime_character_animation_component_inventory": [],
            "runtime_character_animation_actor_component_found": False,
            "runtime_character_animation_anim_graph_component_found": False,
            "runtime_character_animation_simple_motion_component_found": False,
            "runtime_character_animation_actor_instance_found": False,
            "runtime_character_animation_motion_set_found": False,
            "runtime_character_animation_anim_graph_instance_found": False,
            "runtime_character_animation_playback_attempted": False,
            "runtime_character_animation_playback_request_issued": False,
            "runtime_character_animation_playback_started": False,
            "runtime_character_animation_playback_observed": False,
            "runtime_character_animation_playback_tick_count": 0,
            "runtime_character_animation_playback_cleanup_complete": False,
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


def _selected_non_null_render_capture_rhi(env: Mapping[str, str]) -> str:
    requested = str(env.get("MAXINE_EDITOR_RENDER_CAPTURE_RHI", "dx12")).strip().lower()
    return requested if requested in NON_NULL_RENDER_CAPTURE_RHIS else "dx12"


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
    if step == "editor_viewport_visual_material_evidence_started":
        return "editor_viewport_visual_material_evidence_stall"
    if step == "editor_viewport_visual_material_source_validation_started":
        return "editor_viewport_visual_material_source_validation_stall"
    if step == "editor_viewport_visual_material_capture_blocked":
        return "editor_viewport_visual_material_capture_blocked"
    if step == "non_null_editor_render_capture_envelope_started":
        return "non_null_editor_render_capture_envelope_stall"
    if step == "non_null_editor_render_capture_source_validation_started":
        return "non_null_editor_render_capture_source_validation_stall"
    if step == "non_null_editor_render_capture_live_blocked":
        return "non_null_editor_render_capture_live_blocked"
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
    parser.add_argument(
        "--diagnose-approved-runtime-animation-component-wiring-editor-generation",
        action="store_true",
        help="Run the approved Editor-generated runtime animation component wiring diagnostic.",
    )
    parser.add_argument(
        "--enable-approved-runtime-animation-component-wiring-editor-generation",
        action="store_true",
        help="Set the explicit gated enablement marker for approved Editor-generated animation component wiring.",
    )
    parser.add_argument(
        "--diagnose-approved-prefab-save-update-automation-surface",
        action="store_true",
        help="Run the approved prefab save/update automation surface diagnostic.",
    )
    parser.add_argument(
        "--enable-approved-prefab-save-update-automation-surface-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for approved prefab save/update automation surface fixture proof.",
    )
    parser.add_argument(
        "--diagnose-approved-prefab-save-update-bridge",
        action="store_true",
        help="Run the approved prefab save/update bridge diagnostic.",
    )
    parser.add_argument(
        "--enable-approved-prefab-save-update-bridge-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for approved prefab save/update bridge fixture proof.",
    )
    parser.add_argument(
        "--diagnose-approved-prefab-save-update-bridge-host",
        action="store_true",
        help="Run the approved prefab save/update bridge-host diagnostic.",
    )
    parser.add_argument(
        "--enable-approved-prefab-save-update-bridge-host-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for approved prefab save/update bridge-host fixture proof.",
    )
    parser.add_argument(
        "--diagnose-approved-prefab-save-update-route",
        action="store_true",
        help="Run the approved prefab save/update route and scratch-proof diagnostic.",
    )
    parser.add_argument(
        "--enable-approved-prefab-save-update-route-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for approved prefab save/update route scratch proof.",
    )
    parser.add_argument(
        "--diagnose-approved-source-prefab-actor-simple-motion-wiring",
        action="store_true",
        help="Run the approved source-prefab Actor + Simple Motion wiring diagnostic.",
    )
    parser.add_argument(
        "--enable-approved-source-prefab-actor-simple-motion-wiring-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for approved source-prefab Actor + Simple Motion wiring.",
    )
    parser.add_argument(
        "--diagnose-approved-source-prefab-propagation-apply-step",
        action="store_true",
        help="Run the approved source-prefab propagation/apply-step diagnostic.",
    )
    parser.add_argument(
        "--enable-approved-source-prefab-propagation-apply-step-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for approved source-prefab propagation/apply-step proof.",
    )
    parser.add_argument(
        "--diagnose-approved-source-prefab-parent-link-override-apply-route",
        action="store_true",
        help="Run the approved source-prefab parent-focus/link-context override apply route diagnostic.",
    )
    parser.add_argument(
        "--enable-approved-source-prefab-parent-link-override-apply-route-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for approved source-prefab parent-link override apply proof.",
    )
    parser.add_argument(
        "--diagnose-approved-source-prefab-override-path-generation-template-update",
        action="store_true",
        help="Run the approved source-prefab source-backed override-path/template-update diagnostic.",
    )
    parser.add_argument(
        "--enable-approved-source-prefab-override-path-generation-template-update-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for approved source-prefab override-path/template-update proof.",
    )
    parser.add_argument(
        "--diagnose-editor-viewport-visual-material-evidence",
        action="store_true",
        help="Run the bounded Editor viewport visual/material evidence diagnostic.",
    )
    parser.add_argument(
        "--enable-editor-viewport-visual-material-evidence-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for Editor viewport visual/material evidence fixture proof.",
    )
    parser.add_argument(
        "--diagnose-non-null-editor-render-capture-envelope",
        action="store_true",
        help="Run the bounded non-null Editor render/capture safety-envelope diagnostic.",
    )
    parser.add_argument(
        "--enable-non-null-editor-render-capture-envelope-fixture",
        action="store_true",
        help="Set the explicit gated enablement marker for the non-null Editor render/capture envelope.",
    )
    parser.add_argument(
        "--diagnose-non-null-editor-visual-runner-readiness",
        action="store_true",
        help="Build the source-only non-null Editor visual runner readiness/temp-scene contract diagnostic.",
    )
    parser.add_argument(
        "--diagnose-editor-temp-visual-scene-contract",
        action="store_true",
        help="Alias for the source-only non-null Editor visual runner readiness/temp-scene contract diagnostic.",
    )
    parser.add_argument(
        "--enable-non-null-editor-visual-runner-readiness-fixture",
        action="store_true",
        help="Set the explicit gated marker for the non-null Editor visual runner readiness/temp-scene contract.",
    )
    parser.add_argument(
        "--diagnose-non-null-editor-desktop-rhi-readiness",
        action="store_true",
        help="Build the source-only non-null Editor desktop/session/GPU/RHI readiness diagnostic.",
    )
    parser.add_argument(
        "--enable-non-null-editor-desktop-rhi-readiness-fixture",
        action="store_true",
        help="Set the explicit gated marker for the non-null Editor desktop/session/GPU/RHI readiness diagnostic.",
    )
    parser.add_argument(
        "--diagnose-live-non-null-editor-launch",
        action="store_true",
        help="Run the bounded live non-null Editor launch diagnostic without screenshot capture.",
    )
    parser.add_argument(
        "--diagnose-non-null-editor-launch-no-screenshot",
        action="store_true",
        help="Alias for the bounded live non-null Editor launch diagnostic without screenshot capture.",
    )
    parser.add_argument(
        "--enable-live-non-null-editor-launch-fixture",
        action="store_true",
        help="Set the explicit gated marker for bounded live non-null Editor launch without screenshot capture.",
    )
    parser.add_argument(
        "--diagnose-editor-screenshot-capture-artifact-readiness",
        action="store_true",
        help="Run the bounded Editor screenshot capture artifact readiness diagnostic.",
    )
    parser.add_argument(
        "--diagnose-bounded-editor-screenshot-capture",
        action="store_true",
        help="Alias for the bounded Editor screenshot capture artifact readiness diagnostic.",
    )
    parser.add_argument(
        "--enable-editor-screenshot-capture-artifact-readiness-fixture",
        action="store_true",
        help="Set the explicit gated marker for bounded Editor screenshot capture artifact readiness.",
    )
    parser.add_argument(
        "--diagnose-editor-active-viewport-readiness",
        action="store_true",
        help="Run the bounded active Editor viewport/temp visual scene readiness diagnostic.",
    )
    parser.add_argument(
        "--diagnose-editor-temp-visual-scene-readiness",
        action="store_true",
        help="Alias for the active Editor viewport/temp visual scene readiness diagnostic.",
    )
    parser.add_argument(
        "--enable-editor-active-viewport-temp-scene-readiness-fixture",
        action="store_true",
        help="Set the explicit gated marker for active Editor viewport/temp visual scene readiness.",
    )
    parser.add_argument(
        "--diagnose-editor-safe-temp-visual-scene-display-context",
        action="store_true",
        help="Run the bounded safe temp visual scene/display context exercise diagnostic.",
    )
    parser.add_argument(
        "--diagnose-editor-temp-visual-scene-context-exercise",
        action="store_true",
        help="Alias for the safe temp visual scene/display context exercise diagnostic.",
    )
    parser.add_argument(
        "--enable-editor-safe-temp-visual-scene-display-context-fixture",
        action="store_true",
        help="Set the explicit gated marker for safe temp visual scene/display context exercise.",
    )
    parser.add_argument(
        "--diagnose-editor-nonblocking-viewport-swapchain-readiness",
        action="store_true",
        help="Run the bounded non-blocking active/default viewport or SwapChain readiness probe diagnostic.",
    )
    parser.add_argument(
        "--diagnose-nonblocking-viewport-swapchain-readiness",
        action="store_true",
        help="Alias for the bounded non-blocking viewport/SwapChain readiness probe diagnostic.",
    )
    parser.add_argument(
        "--enable-editor-nonblocking-viewport-swapchain-readiness-fixture",
        action="store_true",
        help="Set the explicit gated marker for non-blocking viewport/SwapChain readiness probing.",
    )
    parser.add_argument(
        "--diagnose-editor-ap-negotiation-viewport-materialization-readiness",
        action="store_true",
        help="Run the bounded Editor/Asset Processor negotiation and viewport materialization readiness diagnostic.",
    )
    parser.add_argument(
        "--diagnose-editor-asset-processor-negotiation",
        action="store_true",
        help="Alias for the Editor/Asset Processor negotiation and viewport materialization readiness diagnostic.",
    )
    parser.add_argument(
        "--enable-editor-ap-negotiation-viewport-materialization-readiness-fixture",
        action="store_true",
        help="Set the explicit gated marker for Editor/AP negotiation and viewport materialization readiness.",
    )
    parser.add_argument(
        "--diagnose-asset-processor-project-build-alignment-repair",
        action="store_true",
        help="Run deterministic Asset Processor project/build-root alignment repair or safe-block diagnostic.",
    )
    parser.add_argument(
        "--diagnose-asset-processor-alignment-repair",
        action="store_true",
        help="Alias for the Asset Processor project/build-root alignment repair diagnostic.",
    )
    parser.add_argument(
        "--enable-asset-processor-project-build-alignment-repair-fixture",
        action="store_true",
        help="Set the explicit gated marker for Asset Processor project/build-root alignment repair.",
    )
    parser.add_argument(
        "--diagnose-operator-ap-alignment-remediation-verification",
        action="store_true",
        help="Run post-operator Asset Processor alignment remediation verification.",
    )
    parser.add_argument(
        "--diagnose-operator-run-ap-alignment-remediation",
        action="store_true",
        help="Alias for post-operator Asset Processor alignment remediation verification.",
    )
    parser.add_argument(
        "--enable-operator-ap-alignment-remediation-verification-fixture",
        action="store_true",
        help="Set the explicit gated marker for operator-run AP alignment remediation verification.",
    )
    parser.add_argument(
        "--diagnose-focused-editor-viewport-materialization",
        action="store_true",
        help="Run focused Editor viewport activation/default viewport materialization readiness.",
    )
    parser.add_argument(
        "--diagnose-editor-viewport-materialization",
        action="store_true",
        help="Alias for focused Editor viewport materialization readiness.",
    )
    parser.add_argument(
        "--enable-focused-editor-viewport-materialization-fixture",
        action="store_true",
        help="Set the explicit gated marker for focused Editor viewport materialization.",
    )
    parser.add_argument(
        "--diagnose-editor-main-window-activation-materialization",
        action="store_true",
        help="Run bounded Editor main-window activation/materialization deep-dive readiness.",
    )
    parser.add_argument(
        "--diagnose-editor-main-window-deep-dive",
        action="store_true",
        help="Alias for Editor main-window activation/materialization deep-dive readiness.",
    )
    parser.add_argument(
        "--enable-editor-main-window-activation-deep-dive-fixture",
        action="store_true",
        help="Set the explicit gated marker for Editor main-window activation/materialization deep dive.",
    )
    parser.add_argument(
        "--diagnose-alternate-editor-window-discovery-visible-shell",
        action="store_true",
        help="Run alternate Editor window discovery / visible shell materialization readiness.",
    )
    parser.add_argument(
        "--diagnose-visible-editor-shell-materialization",
        action="store_true",
        help="Alias for alternate Editor window discovery / visible shell materialization readiness.",
    )
    parser.add_argument(
        "--enable-alternate-editor-window-discovery-visible-shell-fixture",
        action="store_true",
        help="Set the explicit gated marker for alternate Editor window discovery / visible shell materialization.",
    )
    parser.add_argument(
        "--diagnose-editor-layout-bootstrap-window-lifecycle",
        action="store_true",
        help="Run Editor layout/bootstrap/window lifecycle deep-dive readiness.",
    )
    parser.add_argument(
        "--diagnose-editor-layout-lifecycle",
        action="store_true",
        help="Alias for Editor layout/bootstrap/window lifecycle deep-dive readiness.",
    )
    parser.add_argument(
        "--enable-editor-layout-bootstrap-window-lifecycle-fixture",
        action="store_true",
        help="Set the explicit gated marker for Editor layout/bootstrap/window lifecycle deep dive.",
    )
    parser.add_argument(
        "--diagnose-editor-bootstrap-wait-shell-ready-synchronization",
        action="store_true",
        help="Run Editor bootstrap wait / shell-ready synchronization readiness.",
    )
    parser.add_argument(
        "--diagnose-editor-shell-ready-synchronization",
        action="store_true",
        help="Alias for Editor bootstrap wait / shell-ready synchronization readiness.",
    )
    parser.add_argument(
        "--enable-editor-bootstrap-wait-shell-ready-synchronization-fixture",
        action="store_true",
        help="Set the explicit gated marker for Editor bootstrap wait / shell-ready synchronization.",
    )
    parser.add_argument(
        "--editor-render-capture-rhi",
        choices=sorted(NON_NULL_RENDER_CAPTURE_RHIS),
        default=None,
        help="Requested non-null Editor render/capture RHI for the visual-capture envelope.",
    )
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
    diagnostic_mode = args.diagnostic_mode
    if (
        args.diagnose_approved_runtime_animation_component_wiring_editor_generation
        or args.enable_approved_runtime_animation_component_wiring_editor_generation
    ):
        diagnostic_mode = "approved-animation-component-wiring-generation"
        env_map["MAXINE_ENABLE_APPROVED_RUNTIME_ANIMATION_COMPONENT_WIRING_EDITOR_GENERATION"] = "1"
    if args.enable_approved_runtime_animation_component_wiring_editor_generation:
        env_map["MAXINE_ALLOW_APPROVED_RUNTIME_ANIMATION_COMPONENT_WIRING_EDITOR_GENERATION"] = "1"
    if (
        args.diagnose_approved_prefab_save_update_automation_surface
        or args.enable_approved_prefab_save_update_automation_surface_fixture
    ):
        diagnostic_mode = "approved-prefab-save-update-automation-surface"
        env_map["MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_AUTOMATION_SURFACE"] = "1"
    if args.enable_approved_prefab_save_update_automation_surface_fixture:
        env_map["MAXINE_ALLOW_APPROVED_PREFAB_SAVE_UPDATE_AUTOMATION_SURFACE"] = "1"
    if args.diagnose_approved_prefab_save_update_bridge or args.enable_approved_prefab_save_update_bridge_fixture:
        diagnostic_mode = "approved-prefab-save-update-bridge"
        env_map["MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_BRIDGE"] = "1"
    if args.enable_approved_prefab_save_update_bridge_fixture:
        env_map["MAXINE_ALLOW_APPROVED_PREFAB_SAVE_UPDATE_BRIDGE"] = "1"
    if (
        args.diagnose_approved_prefab_save_update_bridge_host
        or args.enable_approved_prefab_save_update_bridge_host_fixture
    ):
        diagnostic_mode = "approved-prefab-save-update-bridge-host"
        env_map["MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_BRIDGE_HOST"] = "1"
    if args.enable_approved_prefab_save_update_bridge_host_fixture:
        env_map["MAXINE_ALLOW_APPROVED_PREFAB_SAVE_UPDATE_BRIDGE_HOST"] = "1"
    if args.diagnose_approved_prefab_save_update_route or args.enable_approved_prefab_save_update_route_fixture:
        diagnostic_mode = "approved-prefab-save-update-route"
        env_map["MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_ROUTE"] = "1"
    if args.enable_approved_prefab_save_update_route_fixture:
        env_map["MAXINE_ALLOW_APPROVED_PREFAB_SAVE_UPDATE_ROUTE"] = "1"
    if (
        args.diagnose_approved_source_prefab_actor_simple_motion_wiring
        or args.enable_approved_source_prefab_actor_simple_motion_wiring_fixture
    ):
        diagnostic_mode = "approved-source-prefab-actor-simple-motion-wiring"
        env_map["MAXINE_ENABLE_APPROVED_SOURCE_PREFAB_ACTOR_SIMPLE_MOTION_WIRING"] = "1"
    if args.enable_approved_source_prefab_actor_simple_motion_wiring_fixture:
        env_map["MAXINE_ALLOW_APPROVED_SOURCE_PREFAB_ACTOR_SIMPLE_MOTION_WIRING"] = "1"
    if (
        args.diagnose_approved_source_prefab_propagation_apply_step
        or args.enable_approved_source_prefab_propagation_apply_step_fixture
    ):
        diagnostic_mode = "approved-source-prefab-propagation-apply-step"
        env_map["MAXINE_ENABLE_APPROVED_SOURCE_PREFAB_PROPAGATION_APPLY_STEP"] = "1"
    if args.enable_approved_source_prefab_propagation_apply_step_fixture:
        env_map["MAXINE_ALLOW_APPROVED_SOURCE_PREFAB_PROPAGATION_APPLY_STEP"] = "1"
    if (
        args.diagnose_approved_source_prefab_parent_link_override_apply_route
        or args.enable_approved_source_prefab_parent_link_override_apply_route_fixture
    ):
        diagnostic_mode = "approved-source-prefab-parent-link-override-apply-route"
        env_map["MAXINE_ENABLE_APPROVED_SOURCE_PREFAB_PARENT_LINK_OVERRIDE_APPLY_ROUTE"] = "1"
    if args.enable_approved_source_prefab_parent_link_override_apply_route_fixture:
        env_map["MAXINE_ALLOW_APPROVED_SOURCE_PREFAB_PARENT_LINK_OVERRIDE_APPLY_ROUTE"] = "1"
    if (
        args.diagnose_approved_source_prefab_override_path_generation_template_update
        or args.enable_approved_source_prefab_override_path_generation_template_update_fixture
    ):
        diagnostic_mode = "approved-source-prefab-override-path-generation-template-update"
        env_map["MAXINE_ENABLE_APPROVED_SOURCE_PREFAB_OVERRIDE_PATH_GENERATION_TEMPLATE_UPDATE"] = "1"
    if args.enable_approved_source_prefab_override_path_generation_template_update_fixture:
        env_map["MAXINE_ALLOW_APPROVED_SOURCE_PREFAB_OVERRIDE_PATH_GENERATION_TEMPLATE_UPDATE"] = "1"
    if (
        args.diagnose_editor_viewport_visual_material_evidence
        or args.enable_editor_viewport_visual_material_evidence_fixture
    ):
        diagnostic_mode = "editor-viewport-visual-material-evidence"
        env_map["MAXINE_ENABLE_EDITOR_VIEWPORT_VISUAL_MATERIAL_EVIDENCE"] = "1"
    if args.enable_editor_viewport_visual_material_evidence_fixture:
        env_map["MAXINE_ALLOW_EDITOR_VIEWPORT_VISUAL_MATERIAL_EVIDENCE"] = "1"
    if (
        args.diagnose_non_null_editor_render_capture_envelope
        or args.enable_non_null_editor_render_capture_envelope_fixture
    ):
        diagnostic_mode = "non-null-editor-render-capture-envelope"
        env_map["MAXINE_ENABLE_NON_NULL_EDITOR_RENDER_CAPTURE_ENVELOPE"] = "1"
    if args.enable_non_null_editor_render_capture_envelope_fixture:
        env_map["MAXINE_ALLOW_NON_NULL_EDITOR_RENDER_CAPTURE_ENVELOPE"] = "1"
    if (
        args.diagnose_non_null_editor_visual_runner_readiness
        or args.diagnose_editor_temp_visual_scene_contract
        or args.enable_non_null_editor_visual_runner_readiness_fixture
    ):
        diagnostic_mode = "non-null-editor-visual-runner-readiness"
        env_map["MAXINE_ENABLE_NON_NULL_EDITOR_VISUAL_RUNNER_READINESS"] = "1"
    if args.enable_non_null_editor_visual_runner_readiness_fixture:
        env_map["MAXINE_ALLOW_NON_NULL_EDITOR_VISUAL_RUNNER_READINESS"] = "1"
    if (
        args.diagnose_non_null_editor_desktop_rhi_readiness
        or args.enable_non_null_editor_desktop_rhi_readiness_fixture
    ):
        diagnostic_mode = "non-null-editor-desktop-rhi-readiness"
        env_map["MAXINE_ENABLE_NON_NULL_EDITOR_DESKTOP_RHI_READINESS"] = "1"
    if args.enable_non_null_editor_desktop_rhi_readiness_fixture:
        env_map["MAXINE_ALLOW_NON_NULL_EDITOR_DESKTOP_RHI_READINESS"] = "1"
    if (
        args.diagnose_live_non_null_editor_launch
        or args.diagnose_non_null_editor_launch_no_screenshot
        or args.enable_live_non_null_editor_launch_fixture
    ):
        diagnostic_mode = "live-non-null-editor-launch"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
    if args.enable_live_non_null_editor_launch_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
    if (
        args.diagnose_editor_screenshot_capture_artifact_readiness
        or args.diagnose_bounded_editor_screenshot_capture
        or args.enable_editor_screenshot_capture_artifact_readiness_fixture
    ):
        diagnostic_mode = "editor-screenshot-capture-artifact-readiness"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_READINESS"] = "1"
    if args.enable_editor_screenshot_capture_artifact_readiness_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_READINESS"] = "1"
    if (
        args.diagnose_editor_active_viewport_readiness
        or args.diagnose_editor_temp_visual_scene_readiness
        or args.enable_editor_active_viewport_temp_scene_readiness_fixture
    ):
        diagnostic_mode = "editor-active-viewport-temp-scene-readiness"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_ACTIVE_VIEWPORT_TEMP_SCENE_READINESS"] = "1"
    if args.enable_editor_active_viewport_temp_scene_readiness_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_ACTIVE_VIEWPORT_TEMP_SCENE_READINESS"] = "1"
    if (
        args.diagnose_editor_safe_temp_visual_scene_display_context
        or args.diagnose_editor_temp_visual_scene_context_exercise
        or args.enable_editor_safe_temp_visual_scene_display_context_fixture
    ):
        diagnostic_mode = "editor-safe-temp-visual-scene-display-context"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
    if args.enable_editor_safe_temp_visual_scene_display_context_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
    if (
        args.diagnose_editor_nonblocking_viewport_swapchain_readiness
        or args.diagnose_nonblocking_viewport_swapchain_readiness
        or args.enable_editor_nonblocking_viewport_swapchain_readiness_fixture
    ):
        diagnostic_mode = "editor-nonblocking-viewport-swapchain-readiness"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
    if args.enable_editor_nonblocking_viewport_swapchain_readiness_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
    if (
        args.diagnose_editor_ap_negotiation_viewport_materialization_readiness
        or args.diagnose_editor_asset_processor_negotiation
        or args.enable_editor_ap_negotiation_viewport_materialization_readiness_fixture
    ):
        diagnostic_mode = "editor-ap-negotiation-viewport-materialization-readiness"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
    if args.enable_editor_ap_negotiation_viewport_materialization_readiness_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
    if (
        args.diagnose_asset_processor_project_build_alignment_repair
        or args.diagnose_asset_processor_alignment_repair
        or args.enable_asset_processor_project_build_alignment_repair_fixture
    ):
        diagnostic_mode = "asset-processor-project-build-alignment-repair"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
    if args.enable_asset_processor_project_build_alignment_repair_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ALLOW_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
    if (
        args.diagnose_operator_ap_alignment_remediation_verification
        or args.diagnose_operator_run_ap_alignment_remediation
        or args.enable_operator_ap_alignment_remediation_verification_fixture
    ):
        diagnostic_mode = "operator-run-ap-alignment-remediation-verification"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
    if args.enable_operator_ap_alignment_remediation_verification_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ALLOW_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
    if (
        args.diagnose_focused_editor_viewport_materialization
        or args.diagnose_editor_viewport_materialization
        or args.enable_focused_editor_viewport_materialization_fixture
    ):
        diagnostic_mode = "focused-editor-viewport-activation-default-viewport-materialization"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
    if args.enable_focused_editor_viewport_materialization_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ALLOW_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
    if (
        args.diagnose_editor_main_window_activation_materialization
        or args.diagnose_editor_main_window_deep_dive
        or args.enable_editor_main_window_activation_deep_dive_fixture
    ):
        diagnostic_mode = "editor-main-window-activation-materialization-deep-dive"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
    if args.enable_editor_main_window_activation_deep_dive_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ALLOW_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
    if (
        args.diagnose_alternate_editor_window_discovery_visible_shell
        or args.diagnose_visible_editor_shell_materialization
        or args.enable_alternate_editor_window_discovery_visible_shell_fixture
    ):
        diagnostic_mode = "alternate-editor-window-discovery-visible-shell-materialization"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
        env_map["MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL"] = "1"
    if args.enable_alternate_editor_window_discovery_visible_shell_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ALLOW_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
        env_map["MAXINE_ALLOW_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL"] = "1"
    if (
        args.diagnose_editor_layout_bootstrap_window_lifecycle
        or args.diagnose_editor_layout_lifecycle
        or args.enable_editor_layout_bootstrap_window_lifecycle_fixture
    ):
        diagnostic_mode = "editor-layout-bootstrap-window-lifecycle-deep-dive"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
        env_map["MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE"] = "1"
    if args.enable_editor_layout_bootstrap_window_lifecycle_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ALLOW_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
        env_map["MAXINE_ALLOW_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE"] = "1"
    if (
        args.diagnose_editor_bootstrap_wait_shell_ready_synchronization
        or args.diagnose_editor_shell_ready_synchronization
        or args.enable_editor_bootstrap_wait_shell_ready_synchronization_fixture
    ):
        diagnostic_mode = "editor-bootstrap-wait-shell-ready-synchronization"
        env_map["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
        env_map["MAXINE_ENABLE_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE"] = "1"
        env_map["MAXINE_ENABLE_EDITOR_BOOTSTRAP_WAIT_SHELL_READY_SYNCHRONIZATION"] = "1"
    if args.enable_editor_bootstrap_wait_shell_ready_synchronization_fixture:
        env_map["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS"] = "1"
        env_map["MAXINE_ALLOW_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR"] = "1"
        env_map["MAXINE_ALLOW_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION"] = "1"
        env_map["MAXINE_ALLOW_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_MAIN_WINDOW_ACTIVATION_DEEP_DIVE"] = "1"
        env_map["MAXINE_ALLOW_ALTERNATE_EDITOR_WINDOW_DISCOVERY_VISIBLE_SHELL"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_LAYOUT_BOOTSTRAP_WINDOW_LIFECYCLE_DEEP_DIVE"] = "1"
        env_map["MAXINE_ALLOW_EDITOR_BOOTSTRAP_WAIT_SHELL_READY_SYNCHRONIZATION"] = "1"
    if args.editor_render_capture_rhi:
        env_map["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] = args.editor_render_capture_rhi
    result = run_editor_smoke_corpus(
        args.corpus,
        mode=args.mode,
        manifest=manifest,
        enable_editor_smoke=args.enable_editor_smoke,
        strict_integration=args.strict_integration,
        platform=args.platform,
        env=env_map,
        golden_project_fixture=args.golden_project_fixture,
        diagnostic_mode=diagnostic_mode,
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
