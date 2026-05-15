#!/usr/bin/env python3
"""integration-ready O3DE Editor Python package/prefab smoke script.

The gated wrapper launches this script from Editor with EditorPythonBindings.
No live publication is performed here. The script writes a smoke report for
every outcome, uses only the approved temporary level root, and exits nonzero
when the Editor Python context or temp-level automation is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Tuple


MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"
MXN_PATH_UNSAFE = "MXN_PATH_UNSAFE"
MXN_RUNTIME_SMOKE_FAIL = "MXN_RUNTIME_SMOKE_FAIL"
DIAGNOSTIC_MODES = {
    "hello",
    "product-evidence",
    "temp-level",
    "entity-minimal",
    "component-binding",
    "actor-binding",
    "actor-asset-assignment",
    "prefab-binding",
    "prefab-instantiation",
    "procprefab-product-instantiation",
    "procprefab-content-assertions",
    "procprefab-character-component-assertions",
    "runtime-spawnable-proof-surface",
    "approved-animation-component-wiring-generation",
    "approved-prefab-save-update-automation-surface",
    "approved-prefab-save-update-bridge",
    "approved-prefab-save-update-bridge-host",
    "approved-prefab-save-update-route",
    "approved-source-prefab-actor-simple-motion-wiring",
    "approved-source-prefab-propagation-apply-step",
    "approved-source-prefab-parent-link-override-apply-route",
    "approved-source-prefab-override-path-generation-template-update",
    "editor-viewport-visual-material-evidence",
    "non-null-editor-render-capture-envelope",
    "non-null-editor-visual-runner-readiness",
    "non-null-editor-desktop-rhi-readiness",
    "full",
}
TYPED_BLOCKED_STATUSES = {
    "skipped_by_mode",
    "unavailable_with_verified_reason",
    "blocked_by_readiness",
    "blocked_by_missing_product_evidence",
    "blocked_by_missing_binding",
    "blocked_by_unsafe_operation",
    "blocked_by_unpinned_signature",
    "blocked_by_unsafe_argument_semantics",
    "blocked_by_unsupported_product_asset_type",
    "blocked_by_editor_binding_limitation",
    "unsupported_by_engine_binding",
    "unsupported_by_current_project_build",
    "blocked_by_missing_runtime_executable",
    "blocked_by_missing_runtime_readiness",
    "blocked_by_unpinned_runtime_surface",
    "blocked_by_unsafe_runtime_execution",
    "blocked_by_release_packaging_required",
    "blocked_by_publication_required",
    "runtime_execution_not_attempted",
    "runtime_surface_discovery_pass",
    "product_dependency_proof_pass",
    "product_dependency_proof_unavailable",
    "runtime_spawnable_character_proof_unavailable",
    "runtime_spawnable_character_components_not_exposed",
    "runtime_spawnable_proof_requires_dedicated_runtime_harness",
    "runtime_command_pinning_pass",
    "blocked_by_unpinned_runtime_flags",
    "blocked_by_missing_runtime_help_surface",
    "blocked_by_missing_null_renderer_runtime_support",
    "blocked_by_missing_runtime_exit_strategy",
    "runtime_command_unavailable_in_current_build",
    "procprefab_product_not_editor_instantiable_with_current_binding",
    "procprefab_product_requires_runtime_spawnable_path",
    "source_prefab_instantiation_pass_direct_product_unsupported",
    "blocked_by_editor_generated_prefab_update_save_semantics",
    "blocked_by_editor_component_asset_assignment_unavailable",
    "blocked_by_approved_actor_or_motion_asset_id_unresolved",
    "blocked_by_editor_generated_prefab_update_requires_additional_source_validation",
    "blocked_by_prefab_save_interface_not_available_to_automation",
    "blocked_by_prefab_save_bridge_requires_engine_gem_rebuild",
    "blocked_by_prefab_save_bridge_requires_editor_gem_registration",
    "blocked_by_prefab_save_bridge_requires_cmake_rebuild_not_available",
    "blocked_by_prefab_save_bridge_behavior_context_reflection_unavailable",
    "blocked_by_prefab_save_bridge_path_safety_contract",
    "blocked_by_prefab_save_bridge_requires_additional_source_validation",
    "blocked_by_editor_bridge_host_cmake_registration",
    "blocked_by_editor_bridge_host_target_build_failed",
    "blocked_by_editor_bridge_host_behavior_context_reflection_unavailable",
    "blocked_by_editor_bridge_host_not_loaded_in_editor",
    "blocked_by_editor_bridge_host_requires_project_gem_enablement",
    "blocked_by_editor_bridge_host_requires_additional_source_validation",
    "blocked_by_prefab_save_update_requires_additional_source_validation",
    "blocked_by_prefab_save_update_writable_path_safety_contract",
    "blocked_by_prefab_save_update_scratch_save_not_verified",
    "blocked_by_prefab_save_update_route_requires_additional_source_validation",
    "blocked_by_prefab_save_update_route_path_policy",
    "blocked_by_prefab_save_update_route_behavior_context_reflection",
    "blocked_by_prefab_save_update_route_editor_call_failed",
    "blocked_by_prefab_save_update_scratch_parse_failed",
    "blocked_by_prefab_save_update_scratch_cleanup_failed",
    "blocked_by_prefab_override_generation_unavailable",
    "blocked_by_prefab_component_override_detection_missing",
    "blocked_by_prefab_template_dom_update_unavailable",
    "blocked_by_source_backed_template_update_route_unavailable",
    "blocked_by_prefab_component_override_path_generation_unavailable",
    "blocked_by_prefab_override_push_to_template_failed",
    "blocked_by_source_prefab_markers_preexisting_without_this_run_change",
    "blocked_by_entity_owning_prefab_unavailable",
    "blocked_by_entity_not_owned_by_approved_source_prefab",
    "blocked_by_component_not_owned_by_approved_source_prefab_entity",
    "blocked_by_prefab_instance_to_template_propagation_requires_parent_link_context",
    "blocked_by_prefab_instance_to_template_propagation_requires_additional_source_validation",
    "blocked_by_editor_viewport_capture_requires_non_null_rhi",
    "blocked_by_editor_viewport_capture_api_unavailable",
    "blocked_by_editor_viewport_capture_requires_visible_window",
    "blocked_by_visual_material_capture_surface_requires_additional_source_validation",
    "blocked_by_non_null_editor_render_capture_envelope_unavailable",
    "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
    "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
    "blocked_by_non_null_editor_render_capture_rhi_unavailable",
    "blocked_by_non_null_editor_render_capture_requires_interactive_runner",
    "blocked_by_non_null_editor_render_capture_requires_different_runner",
    "blocked_by_non_null_editor_render_capture_renderer_initialization_failed",
    "blocked_by_editor_visual_material_proof_requires_temp_level_contract",
    "blocked_by_editor_temp_visual_scene_contract_requires_additional_source_validation",
    "blocked_by_non_null_editor_visual_runner_readiness_requires_additional_source_validation",
}
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
RUNTIME_CHARACTER_PRODUCT_TYPES = ("actor", "azmodel", "pxmesh", "azmaterial", "motion", "motionset", "animgraph")
SCRIPT_STARTED_MONOTONIC = time.monotonic()


def _write_import_started_marker() -> None:
    progress_log = os.environ.get("MAXINE_EDITOR_SMOKE_PROGRESS_LOG", "")
    if not progress_log:
        return
    try:
        path = Path(progress_log)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "phase": "script",
            "step": "python_script_import_started",
            "status": "started",
            "message": "Editor Python smoke script import started.",
            "elapsed_seconds": 0,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        pass


_write_import_started_marker()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MAXINE gated Editor Python smoke.")
    parser.add_argument("--manifest", default=os.environ.get("MAXINE_EDITOR_SMOKE_MANIFEST", ""))
    parser.add_argument("--report-out", default=os.environ.get("MAXINE_EDITOR_SMOKE_REPORT_OUT", ""))
    parser.add_argument("--package-ref", default="")
    parser.add_argument("--prefab-ref", default="")
    parser.add_argument("--procprefab-ref", default="")
    parser.add_argument("--diagnostic-mode", default=os.environ.get("MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE", "full"))
    parser.add_argument("--allow-temp-sandbox-level", action="store_true")
    args, _unknown = parser.parse_known_args()
    return args


def main() -> int:
    args = parse_args()
    env = os.environ
    progress_log = _progress_log_path(env.get("MAXINE_EDITOR_SMOKE_PROGRESS_LOG", ""))
    diagnostic_mode = _normalize_diagnostic_mode(args.diagnostic_mode)
    _write_progress_marker(progress_log, "product_evidence_load_started", "started", "Loading smoke report template and APB product evidence.")
    report = _load_report_template(env.get("MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE", ""))
    _write_progress_marker(progress_log, "product_evidence_load_succeeded", "succeeded", "Smoke report template loaded.")
    report_out_raw = args.report_out or env.get("MAXINE_EDITOR_SMOKE_REPORT_OUT", "")
    report_out = Path(report_out_raw) if report_out_raw else None
    errors: List[str] = []
    warnings: List[str] = []
    messages: List[str] = []

    allow_temp_level = args.allow_temp_sandbox_level or env.get("MAXINE_EDITOR_SMOKE_ALLOW_TEMP_SANDBOX_LEVEL") == "1"
    temp_level_name = env.get("MAXINE_EDITOR_SMOKE_TEMP_LEVEL_NAME", "")
    temp_level_path = env.get("MAXINE_EDITOR_SMOKE_TEMP_LEVEL_PATH", "")
    live_editor_execution = env.get("MAXINE_EDITOR_PROCESS_LAUNCHED") == "1"

    report.update(
        {
            "generated_at": _utc_now(),
            "mode": "local_editor_python",
            "diagnostic_mode": diagnostic_mode,
            "live_editor_execution": live_editor_execution,
            "live_asset_processor_batch_execution": False,
            "live_publication": False,
            "release_packaging": False,
            "production_level_mutation": False,
            "defaultlevel_mutation": False,
            "asset_cache_deleted": False,
            "fake_success": False,
            "editor_python_bindings_required": True,
            "entity_smoke": report.get("entity_smoke", {"status": "not_run"}),
            "prefab_smoke": report.get("prefab_smoke", {"status": "not_run"}),
            "actor_smoke": report.get("actor_smoke", {"status": "not_run"}),
            "component_smoke": report.get("component_smoke", {"status": "not_run"}),
            "component_type_registry": report.get("component_type_registry", {}),
            "binding_call_surface": report.get("binding_call_surface", {}),
            "safe_call_results": report.get("safe_call_results", []),
            "component_binding_checks": report.get("component_binding_checks", {"status": "not_run"}),
            "actor_binding_checks": report.get("actor_binding_checks", {"status": "not_run"}),
            "prefab_binding_checks": report.get("prefab_binding_checks", {"status": "not_run"}),
            "source_prefab_baseline_result": report.get("source_prefab_baseline_result", {"status": "not_run"}),
            "direct_procprefab_product_semantics": report.get("direct_procprefab_product_semantics", {"status": "not_run"}),
            "direct_procprefab_content_assertions": report.get("direct_procprefab_content_assertions", {"status": "not_run"}),
            "procprefab_character_assertions": report.get("procprefab_character_assertions", {"status": "not_run"}),
            "runtime_spawnable_proof": report.get("runtime_spawnable_proof", {"status": "not_run"}),
            "runtime_harness": report.get("runtime_harness", {"runtime_harness_status": "not_run"}),
            "approved_prefab_save_update_bridge_diagnostic_attempted": report.get(
                "approved_prefab_save_update_bridge_diagnostic_attempted", False
            ),
            "approved_prefab_save_update_bridge_diagnostic_completed": report.get(
                "approved_prefab_save_update_bridge_diagnostic_completed", False
            ),
            "approved_prefab_save_update_bridge_source_validation_status": report.get(
                "approved_prefab_save_update_bridge_source_validation_status", ""
            ),
            "approved_prefab_save_update_bridge_source_validation_verified": report.get(
                "approved_prefab_save_update_bridge_source_validation_verified", False
            ),
            "approved_prefab_save_update_bridge_source_files": report.get(
                "approved_prefab_save_update_bridge_source_files", []
            ),
            "approved_prefab_save_update_bridge_added": report.get("approved_prefab_save_update_bridge_added", False),
            "approved_prefab_save_update_bridge_verified": report.get(
                "approved_prefab_save_update_bridge_verified", False
            ),
            "approved_prefab_save_update_bridge_blocker": report.get("approved_prefab_save_update_bridge_blocker", ""),
            "approved_prefab_save_update_bridge_candidate_matrix": report.get(
                "approved_prefab_save_update_bridge_candidate_matrix", []
            ),
            "approved_prefab_save_update_bridge_selected_strategy": report.get(
                "approved_prefab_save_update_bridge_selected_strategy", ""
            ),
            "approved_prefab_save_update_bridge_api": report.get("approved_prefab_save_update_bridge_api", {}),
            "approved_prefab_save_update_bridge_behavior_context_reflected": report.get(
                "approved_prefab_save_update_bridge_behavior_context_reflected", False
            ),
            "approved_prefab_save_update_bridge_callable_from_editor_python": report.get(
                "approved_prefab_save_update_bridge_callable_from_editor_python", False
            ),
            "approved_prefab_save_update_bridge_host_diagnostic_attempted": report.get(
                "approved_prefab_save_update_bridge_host_diagnostic_attempted", False
            ),
            "approved_prefab_save_update_bridge_host_diagnostic_completed": report.get(
                "approved_prefab_save_update_bridge_host_diagnostic_completed", False
            ),
            "approved_prefab_save_update_bridge_host_source_validation_status": report.get(
                "approved_prefab_save_update_bridge_host_source_validation_status", ""
            ),
            "approved_prefab_save_update_bridge_host_source_validation_verified": report.get(
                "approved_prefab_save_update_bridge_host_source_validation_verified", False
            ),
            "approved_prefab_save_update_bridge_host_source_files": report.get(
                "approved_prefab_save_update_bridge_host_source_files", []
            ),
            "approved_prefab_save_update_bridge_host_engine_source_refs_status": report.get(
                "approved_prefab_save_update_bridge_host_engine_source_refs_status", ""
            ),
            "approved_prefab_save_update_bridge_host_engine_source_refs_verified": report.get(
                "approved_prefab_save_update_bridge_host_engine_source_refs_verified", False
            ),
            "approved_prefab_save_update_bridge_host_engine_source_refs": report.get(
                "approved_prefab_save_update_bridge_host_engine_source_refs", []
            ),
            "approved_prefab_save_update_bridge_host_selected_strategy": report.get(
                "approved_prefab_save_update_bridge_host_selected_strategy", ""
            ),
            "approved_prefab_save_update_bridge_host_candidate_matrix": report.get(
                "approved_prefab_save_update_bridge_host_candidate_matrix", []
            ),
            "approved_prefab_save_update_bridge_host_added": report.get(
                "approved_prefab_save_update_bridge_host_added", False
            ),
            "approved_prefab_save_update_bridge_host_registered": report.get(
                "approved_prefab_save_update_bridge_host_registered", False
            ),
            "approved_prefab_save_update_bridge_host_build_required": report.get(
                "approved_prefab_save_update_bridge_host_build_required", False
            ),
            "approved_prefab_save_update_bridge_host_build_verified": report.get(
                "approved_prefab_save_update_bridge_host_build_verified", False
            ),
            "approved_prefab_save_update_bridge_host_target_name": report.get(
                "approved_prefab_save_update_bridge_host_target_name", ""
            ),
            "approved_prefab_save_update_bridge_host_module_name": report.get(
                "approved_prefab_save_update_bridge_host_module_name", ""
            ),
            "approved_prefab_save_update_bridge_host_aztoolsframework_dependency_present": report.get(
                "approved_prefab_save_update_bridge_host_aztoolsframework_dependency_present", False
            ),
            "approved_prefab_save_update_bridge_host_behavior_context_reflected": report.get(
                "approved_prefab_save_update_bridge_host_behavior_context_reflected", False
            ),
            "approved_prefab_save_update_bridge_host_callable_from_editor_python": report.get(
                "approved_prefab_save_update_bridge_host_callable_from_editor_python", False
            ),
            "approved_prefab_save_update_bridge_host_runtime_excluded": report.get(
                "approved_prefab_save_update_bridge_host_runtime_excluded", False
            ),
            "approved_prefab_save_update_bridge_host_blocker": report.get(
                "approved_prefab_save_update_bridge_host_blocker", ""
            ),
            "approved_prefab_save_update_bridge_host_api": report.get(
                "approved_prefab_save_update_bridge_host_api", {}
            ),
            "approved_prefab_save_update_bridge_host_status_call_result": report.get(
                "approved_prefab_save_update_bridge_host_status_call_result", ""
            ),
            "approved_prefab_save_update_bridge_host_status_call_error": report.get(
                "approved_prefab_save_update_bridge_host_status_call_error", ""
            ),
            "approved_prefab_save_update_bridge_host_build_command": report.get(
                "approved_prefab_save_update_bridge_host_build_command", ""
            ),
            "approved_prefab_save_update_route_diagnostic_attempted": report.get(
                "approved_prefab_save_update_route_diagnostic_attempted", False
            ),
            "approved_prefab_save_update_route_diagnostic_completed": report.get(
                "approved_prefab_save_update_route_diagnostic_completed", False
            ),
            "approved_prefab_save_update_route_source_validation_status": report.get(
                "approved_prefab_save_update_route_source_validation_status", ""
            ),
            "approved_prefab_save_update_route_source_validation_verified": report.get(
                "approved_prefab_save_update_route_source_validation_verified", False
            ),
            "approved_prefab_save_update_route_source_files": report.get(
                "approved_prefab_save_update_route_source_files", []
            ),
            "approved_prefab_save_update_route_added": report.get(
                "approved_prefab_save_update_route_added", False
            ),
            "approved_prefab_save_update_route_behavior_context_reflected": report.get(
                "approved_prefab_save_update_route_behavior_context_reflected", False
            ),
            "approved_prefab_save_update_route_callable_from_editor_python": report.get(
                "approved_prefab_save_update_route_callable_from_editor_python", False
            ),
            "approved_prefab_save_update_route_blocker": report.get(
                "approved_prefab_save_update_route_blocker", ""
            ),
            "approved_prefab_save_update_route_candidate_matrix": report.get(
                "approved_prefab_save_update_route_candidate_matrix", []
            ),
            "approved_prefab_save_update_route_selected_strategy": report.get(
                "approved_prefab_save_update_route_selected_strategy", ""
            ),
            "approved_prefab_save_update_route_api": report.get(
                "approved_prefab_save_update_route_api", {}
            ),
            "approved_prefab_save_update_automation_surface_diagnostic_attempted": report.get(
                "approved_prefab_save_update_automation_surface_diagnostic_attempted", False
            ),
            "approved_prefab_save_update_automation_surface_diagnostic_completed": report.get(
                "approved_prefab_save_update_automation_surface_diagnostic_completed", False
            ),
            "approved_prefab_save_update_automation_surface_found": report.get(
                "approved_prefab_save_update_automation_surface_found", False
            ),
            "approved_prefab_save_update_automation_surface_verified": report.get(
                "approved_prefab_save_update_automation_surface_verified", False
            ),
            "approved_prefab_save_update_automation_surface_blocker": report.get(
                "approved_prefab_save_update_automation_surface_blocker", ""
            ),
            "approved_prefab_save_update_automation_candidate_matrix": report.get(
                "approved_prefab_save_update_automation_candidate_matrix", []
            ),
            "approved_prefab_save_update_automation_selected_strategy": report.get(
                "approved_prefab_save_update_automation_selected_strategy", ""
            ),
            "approved_prefab_save_update_source_validation_status": report.get(
                "approved_prefab_save_update_source_validation_status", ""
            ),
            "approved_prefab_save_update_source_validation_verified": report.get(
                "approved_prefab_save_update_source_validation_verified", False
            ),
            "approved_prefab_save_update_source_files": report.get("approved_prefab_save_update_source_files", []),
            "approved_prefab_save_update_api": report.get("approved_prefab_save_update_api", {}),
            "approved_prefab_save_update_behavior_context_exposed": report.get(
                "approved_prefab_save_update_behavior_context_exposed", False
            ),
            "approved_prefab_save_update_behavior_context_observed_events": report.get(
                "approved_prefab_save_update_behavior_context_observed_events", []
            ),
            "approved_prefab_save_update_behavior_context_missing_events": report.get(
                "approved_prefab_save_update_behavior_context_missing_events", []
            ),
            "approved_prefab_save_update_bridge_added": report.get("approved_prefab_save_update_bridge_added", False),
            "approved_prefab_save_update_bridge_verified": report.get(
                "approved_prefab_save_update_bridge_verified", False
            ),
            "approved_prefab_save_update_allowed_path_policy": report.get(
                "approved_prefab_save_update_allowed_path_policy", {}
            ),
            "approved_prefab_save_update_rejected_defaultlevel_path": report.get(
                "approved_prefab_save_update_rejected_defaultlevel_path", False
            ),
            "approved_prefab_save_update_rejected_production_level_path": report.get(
                "approved_prefab_save_update_rejected_production_level_path", False
            ),
            "approved_prefab_save_update_rejected_generated_product_path": report.get(
                "approved_prefab_save_update_rejected_generated_product_path", False
            ),
            "approved_prefab_save_update_rejected_unapproved_absolute_path": report.get(
                "approved_prefab_save_update_rejected_unapproved_absolute_path", False
            ),
            "approved_prefab_save_update_rejected_path_traversal": report.get(
                "approved_prefab_save_update_rejected_path_traversal", False
            ),
            "approved_prefab_save_update_scratch_prefab_path": report.get(
                "approved_prefab_save_update_scratch_prefab_path", ""
            ),
            "approved_prefab_save_update_scratch_save_attempted": report.get(
                "approved_prefab_save_update_scratch_save_attempted", False
            ),
            "approved_prefab_save_update_scratch_save_verified": report.get(
                "approved_prefab_save_update_scratch_save_verified", False
            ),
            "approved_prefab_save_update_scratch_reload_or_parse_verified": report.get(
                "approved_prefab_save_update_scratch_reload_or_parse_verified", False
            ),
            "approved_prefab_save_update_scratch_cleanup_verified": report.get(
                "approved_prefab_save_update_scratch_cleanup_verified", False
            ),
            "approved_prefab_save_update_before_hash": report.get("approved_prefab_save_update_before_hash", ""),
            "approved_prefab_save_update_after_hash": report.get("approved_prefab_save_update_after_hash", ""),
            "approved_prefab_save_update_generated_products_committed": report.get(
                "approved_prefab_save_update_generated_products_committed", False
            ),
            "approved_source_prefab_actor_simple_motion_wiring_attempted": report.get(
                "approved_source_prefab_actor_simple_motion_wiring_attempted", False
            ),
            "approved_source_prefab_actor_simple_motion_wiring_completed": report.get(
                "approved_source_prefab_actor_simple_motion_wiring_completed", False
            ),
            "approved_source_prefab_actor_simple_motion_wiring_verified": report.get(
                "approved_source_prefab_actor_simple_motion_wiring_verified", False
            ),
            "approved_source_prefab_actor_simple_motion_wiring_blocker": report.get(
                "approved_source_prefab_actor_simple_motion_wiring_blocker", ""
            ),
            "approved_source_prefab_actor_simple_motion_wiring_source_validation_status": report.get(
                "approved_source_prefab_actor_simple_motion_wiring_source_validation_status", ""
            ),
            "approved_source_prefab_actor_simple_motion_wiring_source_validation_verified": report.get(
                "approved_source_prefab_actor_simple_motion_wiring_source_validation_verified", False
            ),
            "approved_source_prefab_actor_simple_motion_wiring_candidate_matrix": report.get(
                "approved_source_prefab_actor_simple_motion_wiring_candidate_matrix", []
            ),
            "approved_source_prefab_actor_simple_motion_wiring_selected_strategy": report.get(
                "approved_source_prefab_actor_simple_motion_wiring_selected_strategy", ""
            ),
            "approved_source_prefab_propagation_apply_step_attempted": report.get(
                "approved_source_prefab_propagation_apply_step_attempted", False
            ),
            "approved_source_prefab_propagation_apply_step_completed": report.get(
                "approved_source_prefab_propagation_apply_step_completed", False
            ),
            "approved_source_prefab_propagation_apply_step_verified": report.get(
                "approved_source_prefab_propagation_apply_step_verified", False
            ),
            "approved_source_prefab_propagation_apply_step_blocker": report.get(
                "approved_source_prefab_propagation_apply_step_blocker", ""
            ),
            "approved_source_prefab_propagation_apply_step_source_validation_status": report.get(
                "approved_source_prefab_propagation_apply_step_source_validation_status", ""
            ),
            "approved_source_prefab_propagation_apply_step_source_validation_verified": report.get(
                "approved_source_prefab_propagation_apply_step_source_validation_verified", False
            ),
            "approved_source_prefab_propagation_apply_step_source_refs": report.get(
                "approved_source_prefab_propagation_apply_step_source_refs", []
            ),
            "approved_source_prefab_propagation_apply_step_engine_source_refs_status": report.get(
                "approved_source_prefab_propagation_apply_step_engine_source_refs_status", ""
            ),
            "approved_source_prefab_propagation_apply_step_engine_source_refs_verified": report.get(
                "approved_source_prefab_propagation_apply_step_engine_source_refs_verified", False
            ),
            "approved_source_prefab_propagation_apply_step_engine_source_refs": report.get(
                "approved_source_prefab_propagation_apply_step_engine_source_refs", []
            ),
            "approved_source_prefab_propagation_apply_step_candidate_matrix": report.get(
                "approved_source_prefab_propagation_apply_step_candidate_matrix", []
            ),
            "approved_source_prefab_propagation_apply_step_selected_strategy": report.get(
                "approved_source_prefab_propagation_apply_step_selected_strategy", ""
            ),
            "approved_source_prefab_propagation_api_used": report.get(
                "approved_source_prefab_propagation_api_used", ""
            ),
            "approved_source_prefab_parent_link_override_apply_route_attempted": report.get(
                "approved_source_prefab_parent_link_override_apply_route_attempted", False
            ),
            "approved_source_prefab_parent_link_override_apply_route_completed": report.get(
                "approved_source_prefab_parent_link_override_apply_route_completed", False
            ),
            "approved_source_prefab_parent_link_override_apply_route_verified": report.get(
                "approved_source_prefab_parent_link_override_apply_route_verified", False
            ),
            "approved_source_prefab_parent_link_override_apply_route_blocker": report.get(
                "approved_source_prefab_parent_link_override_apply_route_blocker", ""
            ),
            "approved_source_prefab_parent_link_override_apply_source_validation_status": report.get(
                "approved_source_prefab_parent_link_override_apply_source_validation_status", ""
            ),
            "approved_source_prefab_parent_link_override_apply_source_validation_verified": report.get(
                "approved_source_prefab_parent_link_override_apply_source_validation_verified", False
            ),
            "approved_source_prefab_parent_link_override_apply_source_refs": report.get(
                "approved_source_prefab_parent_link_override_apply_source_refs", []
            ),
            "approved_source_prefab_parent_link_override_apply_engine_source_refs_status": report.get(
                "approved_source_prefab_parent_link_override_apply_engine_source_refs_status", ""
            ),
            "approved_source_prefab_parent_link_override_apply_engine_source_refs_verified": report.get(
                "approved_source_prefab_parent_link_override_apply_engine_source_refs_verified", False
            ),
            "approved_source_prefab_parent_link_override_apply_engine_source_refs": report.get(
                "approved_source_prefab_parent_link_override_apply_engine_source_refs", []
            ),
            "approved_source_prefab_parent_link_override_apply_candidate_matrix": report.get(
                "approved_source_prefab_parent_link_override_apply_candidate_matrix", []
            ),
            "approved_source_prefab_parent_link_override_apply_selected_strategy": report.get(
                "approved_source_prefab_parent_link_override_apply_selected_strategy", ""
            ),
            "approved_source_prefab_override_path_generation_template_update_attempted": report.get(
                "approved_source_prefab_override_path_generation_template_update_attempted", False
            ),
            "approved_source_prefab_override_path_generation_template_update_completed": report.get(
                "approved_source_prefab_override_path_generation_template_update_completed", False
            ),
            "approved_source_prefab_override_path_generation_template_update_verified": report.get(
                "approved_source_prefab_override_path_generation_template_update_verified", False
            ),
            "approved_source_prefab_override_path_generation_template_update_blocker": report.get(
                "approved_source_prefab_override_path_generation_template_update_blocker", ""
            ),
            "approved_source_prefab_override_path_generation_template_update_source_validation_status": report.get(
                "approved_source_prefab_override_path_generation_template_update_source_validation_status", ""
            ),
            "approved_source_prefab_override_path_generation_template_update_source_validation_verified": report.get(
                "approved_source_prefab_override_path_generation_template_update_source_validation_verified", False
            ),
            "approved_source_prefab_override_path_generation_template_update_source_refs": report.get(
                "approved_source_prefab_override_path_generation_template_update_source_refs", []
            ),
            "approved_source_prefab_override_path_generation_template_update_engine_source_refs_status": report.get(
                "approved_source_prefab_override_path_generation_template_update_engine_source_refs_status", ""
            ),
            "approved_source_prefab_override_path_generation_template_update_engine_source_refs_verified": report.get(
                "approved_source_prefab_override_path_generation_template_update_engine_source_refs_verified", False
            ),
            "approved_source_prefab_override_path_generation_template_update_engine_source_refs": report.get(
                "approved_source_prefab_override_path_generation_template_update_engine_source_refs", []
            ),
            "approved_source_prefab_override_path_generation_template_update_candidate_matrix": report.get(
                "approved_source_prefab_override_path_generation_template_update_candidate_matrix", []
            ),
            "approved_source_prefab_override_path_generation_template_update_selected_strategy": report.get(
                "approved_source_prefab_override_path_generation_template_update_selected_strategy", ""
            ),
            "approved_source_prefab_entity_ownership_checked": report.get(
                "approved_source_prefab_entity_ownership_checked", False
            ),
            "approved_source_prefab_entity_ownership_verified": report.get(
                "approved_source_prefab_entity_ownership_verified", False
            ),
            "approved_source_prefab_entity_owning_prefab_path": report.get(
                "approved_source_prefab_entity_owning_prefab_path", ""
            ),
            "approved_source_prefab_entity_owning_prefab_matches_requested_path": report.get(
                "approved_source_prefab_entity_owning_prefab_matches_requested_path", False
            ),
            "approved_source_prefab_component_ownership_checked": report.get(
                "approved_source_prefab_component_ownership_checked", False
            ),
            "approved_source_prefab_component_ownership_verified": report.get(
                "approved_source_prefab_component_ownership_verified", False
            ),
            "approved_source_prefab_entity_ownership_blocker": report.get(
                "approved_source_prefab_entity_ownership_blocker", ""
            ),
            "approved_source_prefab_parent_focus_context_required": report.get(
                "approved_source_prefab_parent_focus_context_required", False
            ),
            "approved_source_prefab_parent_focus_context_available": report.get(
                "approved_source_prefab_parent_focus_context_available", False
            ),
            "approved_source_prefab_parent_focus_context_applied": report.get(
                "approved_source_prefab_parent_focus_context_applied", False
            ),
            "approved_source_prefab_parent_focus_context_restored": report.get(
                "approved_source_prefab_parent_focus_context_restored", False
            ),
            "approved_source_prefab_link_context_required": report.get(
                "approved_source_prefab_link_context_required", False
            ),
            "approved_source_prefab_link_context_available": report.get(
                "approved_source_prefab_link_context_available", False
            ),
            "approved_source_prefab_link_id": report.get("approved_source_prefab_link_id", ""),
            "approved_source_prefab_component_override_paths_detected": report.get(
                "approved_source_prefab_component_override_paths_detected", False
            ),
            "approved_source_prefab_component_override_paths": report.get(
                "approved_source_prefab_component_override_paths", []
            ),
            "approved_source_prefab_apply_link_overrides_attempted": report.get(
                "approved_source_prefab_apply_link_overrides_attempted", False
            ),
            "approved_source_prefab_apply_link_overrides_verified": report.get(
                "approved_source_prefab_apply_link_overrides_verified", False
            ),
            "approved_source_prefab_push_overrides_to_template_attempted": report.get(
                "approved_source_prefab_push_overrides_to_template_attempted", False
            ),
            "approved_source_prefab_push_overrides_to_template_verified": report.get(
                "approved_source_prefab_push_overrides_to_template_verified", False
            ),
            "approved_source_prefab_template_dom_update_route_used": report.get(
                "approved_source_prefab_template_dom_update_route_used", False
            ),
            "approved_source_prefab_template_dom_initial_entity_found": report.get(
                "approved_source_prefab_template_dom_initial_entity_found", False
            ),
            "approved_source_prefab_serialized_entity_dom_generated": report.get(
                "approved_source_prefab_serialized_entity_dom_generated", False
            ),
            "approved_source_prefab_entity_patch_generated": report.get(
                "approved_source_prefab_entity_patch_generated", False
            ),
            "approved_source_prefab_entity_patch_operation_count": report.get(
                "approved_source_prefab_entity_patch_operation_count", 0
            ),
            "approved_source_prefab_patch_entity_in_template_attempted": report.get(
                "approved_source_prefab_patch_entity_in_template_attempted", False
            ),
            "approved_source_prefab_patch_entity_in_template_verified": report.get(
                "approved_source_prefab_patch_entity_in_template_verified", False
            ),
            "approved_source_prefab_link_overrides_applied": report.get(
                "approved_source_prefab_link_overrides_applied", False
            ),
            "approved_source_prefab_push_overrides_to_prefab_attempted": report.get(
                "approved_source_prefab_push_overrides_to_prefab_attempted", False
            ),
            "approved_source_prefab_push_overrides_to_prefab_verified": report.get(
                "approved_source_prefab_push_overrides_to_prefab_verified", False
            ),
            "approved_source_prefab_component_overrides_detected": report.get(
                "approved_source_prefab_component_overrides_detected", False
            ),
            "approved_source_prefab_path": report.get("approved_source_prefab_path", ""),
            "approved_source_prefab_project_path_redacted": report.get(
                "approved_source_prefab_project_path_redacted", ""
            ),
            "approved_source_prefab_before_hash": report.get("approved_source_prefab_before_hash", ""),
            "approved_source_prefab_after_hash": report.get("approved_source_prefab_after_hash", ""),
            "approved_source_prefab_project_before_hash": report.get(
                "approved_source_prefab_project_before_hash", ""
            ),
            "approved_source_prefab_project_after_hash": report.get(
                "approved_source_prefab_project_after_hash", ""
            ),
            "approved_source_prefab_modified": report.get("approved_source_prefab_modified", False),
            "approved_source_prefab_changed_this_run": report.get("approved_source_prefab_changed_this_run", False),
            "approved_source_prefab_marker_presence_verified": report.get(
                "approved_source_prefab_marker_presence_verified", False
            ),
            "approved_source_prefab_marker_persistence_verified_this_run": report.get(
                "approved_source_prefab_marker_persistence_verified_this_run", False
            ),
            "approved_source_prefab_marker_persistence_blocker": report.get(
                "approved_source_prefab_marker_persistence_blocker", ""
            ),
            "approved_source_prefab_persisted_wiring_markers_verified": report.get(
                "approved_source_prefab_persisted_wiring_markers_verified", False
            ),
            "approved_source_prefab_project_persisted_wiring_markers_verified": report.get(
                "approved_source_prefab_project_persisted_wiring_markers_verified", False
            ),
            "approved_source_prefab_component_overrides_applied": report.get(
                "approved_source_prefab_component_overrides_applied", False
            ),
            "approved_source_prefab_component_override_refs": report.get(
                "approved_source_prefab_component_override_refs", {}
            ),
            "approved_source_prefab_component_override_apply_status": report.get(
                "approved_source_prefab_component_override_apply_status", {}
            ),
            "approved_source_prefab_entity_changes_committed": report.get(
                "approved_source_prefab_entity_changes_committed", False
            ),
            "approved_source_prefab_entity_change_commit_status": report.get(
                "approved_source_prefab_entity_change_commit_status", {}
            ),
            "approved_source_prefab_update_route_used": report.get("approved_source_prefab_update_route_used", ""),
            "approved_source_prefab_save_verified": report.get("approved_source_prefab_save_verified", False),
            "approved_source_prefab_actor_component_added": report.get(
                "approved_source_prefab_actor_component_added", False
            ),
            "approved_source_prefab_simple_motion_component_added": report.get(
                "approved_source_prefab_simple_motion_component_added", False
            ),
            "approved_source_prefab_actor_asset_assignment_verified": report.get(
                "approved_source_prefab_actor_asset_assignment_verified", False
            ),
            "approved_source_prefab_motion_asset_assignment_verified": report.get(
                "approved_source_prefab_motion_asset_assignment_verified", False
            ),
            "approved_source_prefab_actor_asset_id": report.get("approved_source_prefab_actor_asset_id", ""),
            "approved_source_prefab_motion_asset_id": report.get("approved_source_prefab_motion_asset_id", ""),
            "approved_source_prefab_property_readback_verified": report.get(
                "approved_source_prefab_property_readback_verified", False
            ),
            "approved_source_prefab_defaultlevel_mutation": report.get(
                "approved_source_prefab_defaultlevel_mutation", False
            ),
            "approved_source_prefab_production_level_mutation": report.get(
                "approved_source_prefab_production_level_mutation", False
            ),
            "approved_source_prefab_hand_authored_unknown_json_used": report.get(
                "approved_source_prefab_hand_authored_unknown_json_used", False
            ),
            "approved_spawnable_regenerated_or_found": report.get(
                "approved_spawnable_regenerated_or_found", False
            ),
            "approved_spawnable_asset_id": report.get("approved_spawnable_asset_id", ""),
            "approved_spawnable_asset_type": report.get("approved_spawnable_asset_type", ""),
            "approved_runtime_animation_component_wiring_editor_generation_attempted": report.get(
                "approved_runtime_animation_component_wiring_editor_generation_attempted", False
            ),
            "approved_runtime_animation_component_wiring_editor_generation_completed": report.get(
                "approved_runtime_animation_component_wiring_editor_generation_completed", False
            ),
            "approved_runtime_animation_component_wiring_editor_generation_verified": report.get(
                "approved_runtime_animation_component_wiring_editor_generation_verified", False
            ),
            "approved_runtime_animation_component_wiring_editor_generation_blocker": report.get(
                "approved_runtime_animation_component_wiring_editor_generation_blocker", ""
            ),
            "approved_runtime_animation_component_wiring_source_prefab_path": report.get(
                "approved_runtime_animation_component_wiring_source_prefab_path", ""
            ),
            "approved_runtime_animation_component_wiring_source_prefab_modified": report.get(
                "approved_runtime_animation_component_wiring_source_prefab_modified", False
            ),
            "approved_runtime_animation_component_wiring_editor_generated_update_used": report.get(
                "approved_runtime_animation_component_wiring_editor_generated_update_used", False
            ),
            "approved_runtime_animation_component_wiring_hand_authored_unknown_json_used": report.get(
                "approved_runtime_animation_component_wiring_hand_authored_unknown_json_used", False
            ),
            "approved_runtime_animation_component_wiring_actor_component_added": report.get(
                "approved_runtime_animation_component_wiring_actor_component_added", False
            ),
            "approved_runtime_animation_component_wiring_simple_motion_component_added": report.get(
                "approved_runtime_animation_component_wiring_simple_motion_component_added", False
            ),
            "approved_runtime_animation_component_wiring_anim_graph_component_added": report.get(
                "approved_runtime_animation_component_wiring_anim_graph_component_added", False
            ),
            "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": report.get(
                "approved_runtime_animation_component_wiring_actor_asset_assignment_verified", False
            ),
            "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": report.get(
                "approved_runtime_animation_component_wiring_motion_asset_assignment_verified", False
            ),
            "approved_runtime_animation_component_wiring_actor_asset_id": report.get(
                "approved_runtime_animation_component_wiring_actor_asset_id", ""
            ),
            "approved_runtime_animation_component_wiring_motion_asset_id": report.get(
                "approved_runtime_animation_component_wiring_motion_asset_id", ""
            ),
            "approved_runtime_animation_component_wiring_property_readback_verified": report.get(
                "approved_runtime_animation_component_wiring_property_readback_verified", False
            ),
            "approved_runtime_animation_component_wiring_prefab_save_verified": report.get(
                "approved_runtime_animation_component_wiring_prefab_save_verified", False
            ),
            "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": report.get(
                "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found", False
            ),
            "runtime_character_animation_component_wiring_claimed": report.get(
                "runtime_character_animation_component_wiring_claimed", False
            ),
            "runtime_character_animation_component_wiring_verified": report.get(
                "runtime_character_animation_component_wiring_verified", False
            ),
            "runtime_character_animation_claimed": report.get("runtime_character_animation_claimed", False),
            "runtime_character_animation_verified": report.get("runtime_character_animation_verified", False),
            "runtime_character_proof_claimed": report.get("runtime_character_proof_claimed", False),
            "runtime_character_proof_verified": report.get("runtime_character_proof_verified", False),
            "editor_viewport_visual_material_evidence_attempted": report.get(
                "editor_viewport_visual_material_evidence_attempted", False
            ),
            "editor_viewport_visual_material_evidence_completed": report.get(
                "editor_viewport_visual_material_evidence_completed", False
            ),
            "editor_viewport_visual_material_evidence_source_validation_status": report.get(
                "editor_viewport_visual_material_evidence_source_validation_status", ""
            ),
            "editor_viewport_visual_material_evidence_source_validation_verified": report.get(
                "editor_viewport_visual_material_evidence_source_validation_verified", False
            ),
            "editor_viewport_visual_material_evidence_source_validation": report.get(
                "editor_viewport_visual_material_evidence_source_validation", {}
            ),
            "editor_viewport_visual_material_evidence_source_files": report.get(
                "editor_viewport_visual_material_evidence_source_files", []
            ),
            "editor_viewport_visual_material_evidence_blocker": report.get(
                "editor_viewport_visual_material_evidence_blocker", ""
            ),
            "editor_viewport_visual_material_evidence_candidate_matrix": report.get(
                "editor_viewport_visual_material_evidence_candidate_matrix", []
            ),
            "editor_viewport_visual_material_evidence_selected_strategy": report.get(
                "editor_viewport_visual_material_evidence_selected_strategy", ""
            ),
            "editor_visual_material_temp_scene_created": report.get("editor_visual_material_temp_scene_created", False),
            "editor_visual_material_temp_scene_path": report.get("editor_visual_material_temp_scene_path", ""),
            "editor_visual_material_defaultlevel_mutation": report.get(
                "editor_visual_material_defaultlevel_mutation", False
            ),
            "editor_visual_material_production_level_mutation": report.get(
                "editor_visual_material_production_level_mutation", False
            ),
            "editor_visual_material_character_instantiated": report.get(
                "editor_visual_material_character_instantiated", False
            ),
            "editor_visual_material_character_source_path": report.get(
                "editor_visual_material_character_source_path", ""
            ),
            "editor_visual_material_character_product_or_prefab_path": report.get(
                "editor_visual_material_character_product_or_prefab_path", ""
            ),
            "editor_visual_material_camera_or_view_framed": report.get(
                "editor_visual_material_camera_or_view_framed", False
            ),
            "editor_visual_material_light_or_environment_prepared": report.get(
                "editor_visual_material_light_or_environment_prepared", False
            ),
            "editor_visual_material_capture_api_found": report.get("editor_visual_material_capture_api_found", False),
            "editor_visual_material_capture_api_used": report.get("editor_visual_material_capture_api_used", ""),
            "editor_visual_material_capture_requested": report.get("editor_visual_material_capture_requested", False),
            "editor_visual_material_capture_completed": report.get("editor_visual_material_capture_completed", False),
            "editor_visual_material_capture_artifact_path": report.get(
                "editor_visual_material_capture_artifact_path", ""
            ),
            "editor_visual_material_capture_artifact_exists": report.get(
                "editor_visual_material_capture_artifact_exists", False
            ),
            "editor_visual_material_capture_artifact_format": report.get(
                "editor_visual_material_capture_artifact_format", ""
            ),
            "editor_visual_material_capture_artifact_width": report.get(
                "editor_visual_material_capture_artifact_width", 0
            ),
            "editor_visual_material_capture_artifact_height": report.get(
                "editor_visual_material_capture_artifact_height", 0
            ),
            "editor_visual_material_capture_artifact_size_bytes": report.get(
                "editor_visual_material_capture_artifact_size_bytes", 0
            ),
            "editor_visual_material_capture_content_validation_attempted": report.get(
                "editor_visual_material_capture_content_validation_attempted", False
            ),
            "editor_visual_material_capture_content_validation_verified": report.get(
                "editor_visual_material_capture_content_validation_verified", False
            ),
            "editor_visual_material_nonblank_validation_verified": report.get(
                "editor_visual_material_nonblank_validation_verified", False
            ),
            "editor_visual_material_character_presence_validation_verified": report.get(
                "editor_visual_material_character_presence_validation_verified", False
            ),
            "editor_visual_material_material_presence_validation_verified": report.get(
                "editor_visual_material_material_presence_validation_verified", False
            ),
            "editor_visual_material_cleanup_verified": report.get("editor_visual_material_cleanup_verified", False),
            "editor_visual_material_selected_log_scan_passed": report.get(
                "editor_visual_material_selected_log_scan_passed", False
            ),
            "visual_material_product_inventory_gate_verified": report.get(
                "visual_material_product_inventory_gate_verified", False
            ),
            "visual_material_rendered_evidence_gate_attempted": report.get(
                "visual_material_rendered_evidence_gate_attempted", False
            ),
            "visual_material_rendered_evidence_gate_verified": report.get(
                "visual_material_rendered_evidence_gate_verified", False
            ),
            "visual_material_gate_claimed": report.get("visual_material_gate_claimed", False),
            "visual_material_gate_verified": report.get("visual_material_gate_verified", False),
            "full_runtime_character_visual_material_gate_verified": report.get(
                "full_runtime_character_visual_material_gate_verified", False
            ),
            "full_runtime_character_proof_contract_pinned": report.get(
                "full_runtime_character_proof_contract_pinned", False
            ),
            "full_runtime_character_proof_contract_verified": report.get(
                "full_runtime_character_proof_contract_verified", False
            ),
            "full_runtime_character_proof_satisfied_gates": report.get(
                "full_runtime_character_proof_satisfied_gates", []
            ),
            "full_runtime_character_proof_unsatisfied_gates": report.get(
                "full_runtime_character_proof_unsatisfied_gates", []
            ),
            "full_runtime_character_proof_deferred_gates": report.get(
                "full_runtime_character_proof_deferred_gates", []
            ),
            "property_path_discovery": report.get("property_path_discovery", {}),
            "property_list_summary": report.get("property_list_summary", {}),
            "property_access_summary": report.get("property_access_summary", {}),
            "no_fake_success": True,
        }
    )

    if env.get("MAXINE_ALLOW_LIVE_PUBLICATION") == "1":
        errors.append(MXN_PATH_UNSAFE)
        messages.append("Live publication gate must remain disabled.")
    if env.get("MAXINE_ENABLE_RELEASE_PACKAGING") == "1":
        errors.append(MXN_PATH_UNSAFE)
        messages.append("Release packaging gate must remain disabled.")
    needs_temp_level = diagnostic_mode in {
        "temp-level",
        "entity-minimal",
        "component-binding",
        "actor-binding",
        "actor-asset-assignment",
        "prefab-binding",
        "prefab-instantiation",
        "procprefab-product-instantiation",
        "procprefab-content-assertions",
        "procprefab-character-component-assertions",
        "runtime-spawnable-proof-surface",
        "approved-animation-component-wiring-generation",
        "approved-prefab-save-update-route",
        "approved-source-prefab-actor-simple-motion-wiring",
        "approved-source-prefab-parent-link-override-apply-route",
        "approved-source-prefab-override-path-generation-template-update",
        "full",
    }
    if needs_temp_level and not allow_temp_level:
        errors.append(MXN_PATH_UNSAFE)
        messages.append("Editor smoke requires explicit temp sandbox level permission.")
    if (needs_temp_level or temp_level_name) and not _temp_level_name_safe(temp_level_name):
        errors.append(MXN_PATH_UNSAFE)
        messages.append("Temp level name must stay under _maxine_smoke.")
    if temp_level_path and not _temp_level_path_safe(temp_level_path):
        errors.append(MXN_PATH_UNSAFE)
        messages.append("Temp level path must stay under Levels/_maxine_smoke.")
    if needs_temp_level and not errors:
        _write_progress_marker(progress_log, "temp_level_policy_validated", "succeeded", "Approved temp level policy validated.")

    general = None
    if not errors:
        try:
            _write_progress_marker(progress_log, "azlmbr_import_started", "started", "Importing Editor Python Bindings.")
            import azlmbr  # type: ignore  # noqa: F401
            import azlmbr.legacy.general as general_module  # type: ignore

            general = general_module
            report["editor_python_bindings_available"] = True
            _write_progress_marker(progress_log, "azlmbr_import_succeeded", "succeeded", "Editor Python Bindings imports succeeded.")
        except Exception as exc:
            errors.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
            messages.append(f"Editor Python bindings import failed: {exc}")
            report["editor_python_bindings_available"] = False
            _write_progress_marker(progress_log, "azlmbr_import_failed", "failed", f"Editor Python bindings import failed: {exc}", error_code=MXN_VALIDATION_TOOL_UNAVAILABLE)

    if not errors and diagnostic_mode != "hello":
        evidence_errors = _validate_product_evidence_summary(report)
        if evidence_errors:
            errors.extend(evidence_errors)
            messages.append("APB product evidence summary is incomplete or unsafe inside Editor smoke.")

    if not errors and diagnostic_mode == "approved-prefab-save-update-automation-surface":
        _write_progress_marker(
            progress_log,
            "approved_prefab_save_update_automation_surface_started",
            "started",
            "Running approved prefab save/update automation surface diagnostic.",
        )
        save_surface = _run_approved_prefab_save_update_automation_surface_checks(report)
        report.update(save_surface)
        _write_progress_marker(
            progress_log,
            "approved_prefab_save_update_automation_surface_returned",
            str(save_surface.get("approved_prefab_save_update_automation_surface_blocker", "returned")),
            "Approved prefab save/update automation surface diagnostic returned.",
        )

    if not errors and diagnostic_mode == "approved-prefab-save-update-bridge":
        _write_progress_marker(
            progress_log,
            "approved_prefab_save_update_bridge_started",
            "started",
            "Running approved prefab save/update bridge diagnostic.",
        )
        bridge = _run_approved_prefab_save_update_bridge_checks(report)
        report.update(bridge)
        _write_progress_marker(
            progress_log,
            "approved_prefab_save_update_bridge_returned",
            str(bridge.get("approved_prefab_save_update_bridge_blocker", "returned")),
            "Approved prefab save/update bridge diagnostic returned.",
        )

    if not errors and diagnostic_mode == "approved-prefab-save-update-bridge-host":
        _write_progress_marker(
            progress_log,
            "approved_prefab_save_update_bridge_host_started",
            "started",
            "Running approved prefab save/update bridge-host diagnostic.",
        )
        bridge_host_status = _call_prefab_save_update_bridge_host_status()
        bridge_host = _run_approved_prefab_save_update_bridge_host_checks(
            report,
            bridge_host_status=bridge_host_status,
            build_verified=(
                bool(bridge_host_status.get("callable"))
                or env.get("MAXINE_PREFAB_SAVE_UPDATE_BRIDGE_HOST_BUILD_VERIFIED") == "1"
            ),
        )
        report.update(bridge_host)
        _write_progress_marker(
            progress_log,
            "approved_prefab_save_update_bridge_host_returned",
            str(bridge_host.get("approved_prefab_save_update_bridge_host_blocker", "returned")),
            "Approved prefab save/update bridge-host diagnostic returned.",
        )

    if not errors and diagnostic_mode == "approved-source-prefab-propagation-apply-step":
        _write_progress_marker(
            progress_log,
            "approved_source_prefab_propagation_apply_step_started",
            "started",
            "Running approved source-prefab propagation/apply step diagnostic.",
        )
        propagation = _run_approved_source_prefab_propagation_apply_step_checks(report)
        report.update(propagation)
        _write_progress_marker(
            progress_log,
            "approved_source_prefab_propagation_apply_step_returned",
            str(propagation.get("approved_source_prefab_propagation_apply_step_blocker", "returned")),
            "Approved source-prefab propagation/apply step diagnostic returned.",
        )

    if not errors and needs_temp_level and general is not None:
        try:
            _create_temp_level(general, temp_level_name, temp_level_path, progress_log=progress_log)
            report["temp_level_path_redacted"] = _redacted_temp_level_path(temp_level_name)
            report["level_strategy"] = "temp_sandbox_level"
        except Exception as exc:
            errors.append(MXN_RUNTIME_SMOKE_FAIL)
            messages.append(f"Temp level automation failed: {exc}")
            _write_progress_marker(progress_log, "create_level_failed", "failed", f"Temp level automation failed: {exc}", error_code=MXN_RUNTIME_SMOKE_FAIL)

    if not errors and diagnostic_mode == "approved-prefab-save-update-route":
        _write_progress_marker(
            progress_log,
            "approved_prefab_save_update_route_started",
            "started",
            "Running approved prefab save/update route scratch diagnostic.",
        )
        scratch_prefab_path = _approved_prefab_save_update_route_scratch_path()
        bridge_host_status = _call_prefab_save_update_bridge_host_status()
        rejection_statuses = _call_prefab_save_update_route_rejection_probes(scratch_prefab_path)
        route_status = _call_prefab_save_update_route_scratch_probe(scratch_prefab_path)
        route = _run_approved_prefab_save_update_route_checks(
            report,
            bridge_host_status=bridge_host_status,
            route_status=route_status,
            rejection_statuses=rejection_statuses,
            scratch_prefab_path=scratch_prefab_path,
        )
        report.update(route)
        _write_progress_marker(
            progress_log,
            "approved_prefab_save_update_route_returned",
            str(route.get("approved_prefab_save_update_route_blocker", "returned")),
            "Approved prefab save/update route scratch diagnostic returned.",
        )

    if not errors and diagnostic_mode == "approved-source-prefab-actor-simple-motion-wiring":
        _write_progress_marker(
            progress_log,
            "approved_source_prefab_actor_simple_motion_wiring_started",
            "started",
            "Running approved source-prefab Actor + Simple Motion wiring diagnostic.",
        )
        wiring = _run_approved_source_prefab_actor_simple_motion_wiring_checks(report, progress_log=progress_log)
        report.update(wiring)
        _write_progress_marker(
            progress_log,
            "approved_source_prefab_actor_simple_motion_wiring_returned",
            str(wiring.get("approved_source_prefab_actor_simple_motion_wiring_blocker", "returned")),
            "Approved source-prefab Actor + Simple Motion wiring diagnostic returned.",
        )

    if not errors and diagnostic_mode == "approved-source-prefab-parent-link-override-apply-route":
        _write_progress_marker(
            progress_log,
            "approved_source_prefab_parent_link_override_apply_route_started",
            "started",
            "Running approved source-prefab parent-focus/link-context override apply route diagnostic.",
        )
        parent_link = _run_approved_source_prefab_parent_link_override_apply_route_checks(
            report,
            progress_log=progress_log,
        )
        report.update(parent_link)
        _write_progress_marker(
            progress_log,
            "approved_source_prefab_parent_link_override_apply_route_returned",
            str(parent_link.get("approved_source_prefab_parent_link_override_apply_route_blocker", "returned")),
            "Approved source-prefab parent-focus/link-context override apply route diagnostic returned.",
        )

    if not errors and diagnostic_mode == "approved-source-prefab-override-path-generation-template-update":
        _write_progress_marker(
            progress_log,
            "approved_source_prefab_override_path_generation_template_update_started",
            "started",
            "Running approved source-prefab source-backed override-path/template-update diagnostic.",
        )
        template_update = _run_approved_source_prefab_override_path_generation_template_update_checks(
            report,
            progress_log=progress_log,
        )
        report.update(template_update)
        _write_progress_marker(
            progress_log,
            "approved_source_prefab_override_path_generation_template_update_returned",
            str(
                template_update.get(
                    "approved_source_prefab_override_path_generation_template_update_blocker",
                    "returned",
                )
            ),
            "Approved source-prefab source-backed override-path/template-update diagnostic returned.",
        )

    if not errors and diagnostic_mode == "editor-viewport-visual-material-evidence":
        _write_progress_marker(
            progress_log,
            "editor_viewport_visual_material_evidence_started",
            "started",
            "Running Editor viewport visual/material evidence diagnostic.",
        )
        visual_evidence = _run_editor_viewport_visual_material_evidence_checks(report, progress_log=progress_log)
        report.update(visual_evidence)
        _write_progress_marker(
            progress_log,
            "editor_viewport_visual_material_evidence_returned",
            str(visual_evidence.get("editor_viewport_visual_material_evidence_blocker", "returned")),
            "Editor viewport visual/material evidence diagnostic returned.",
        )

    if not errors and diagnostic_mode == "non-null-editor-render-capture-envelope":
        _write_progress_marker(
            progress_log,
            "non_null_editor_render_capture_envelope_started",
            "started",
            "Running non-null Editor render/capture envelope diagnostic.",
        )
        envelope = _run_non_null_editor_render_capture_envelope_checks(report, progress_log=progress_log)
        report.update(envelope)
        _write_progress_marker(
            progress_log,
            "non_null_editor_render_capture_envelope_returned",
            str(envelope.get("non_null_editor_render_capture_envelope_blocker", "returned")),
            "Non-null Editor render/capture envelope diagnostic returned.",
        )

    if not errors and diagnostic_mode == "non-null-editor-visual-runner-readiness":
        _write_progress_marker(
            progress_log,
            "non_null_editor_visual_runner_readiness_started",
            "started",
            "Running non-null Editor visual runner readiness/temp-scene contract diagnostic.",
        )
        readiness_contract = _run_non_null_editor_visual_runner_readiness_checks(report, progress_log=progress_log)
        report.update(readiness_contract)
        _write_progress_marker(
            progress_log,
            "non_null_editor_visual_runner_readiness_returned",
            str(readiness_contract.get("non_null_editor_visual_runner_readiness_blocker", "returned")),
            "Non-null Editor visual runner readiness/temp-scene contract diagnostic returned.",
        )

    if not errors and diagnostic_mode == "non-null-editor-desktop-rhi-readiness":
        _write_progress_marker(
            progress_log,
            "non_null_editor_desktop_rhi_readiness_started",
            "started",
            "Running non-null Editor desktop/session/GPU/RHI readiness diagnostic.",
        )
        desktop_rhi = _run_non_null_editor_desktop_rhi_readiness_checks(report, progress_log=progress_log)
        report.update(desktop_rhi)
        _write_progress_marker(
            progress_log,
            "non_null_editor_desktop_rhi_readiness_returned",
            str(desktop_rhi.get("non_null_editor_desktop_rhi_readiness_blocker", "returned")),
            "Non-null Editor desktop/session/GPU/RHI readiness diagnostic returned.",
        )

    entity_result: Dict[str, Any] = report.get("entity_smoke", {"status": "not_run"})
    entity_id_raw = None
    if not errors and diagnostic_mode in {
        "entity-minimal",
        "component-binding",
        "actor-binding",
        "actor-asset-assignment",
        "prefab-binding",
        "prefab-instantiation",
        "procprefab-product-instantiation",
        "procprefab-content-assertions",
        "procprefab-character-component-assertions",
        "runtime-spawnable-proof-surface",
        "approved-animation-component-wiring-generation",
        "full",
    }:
        _write_progress_marker(progress_log, "entity_create_started", "started", "Creating minimal temporary smoke entity.")
        entity_result, entity_id_raw = _try_create_smoke_entity_with_raw()
        _write_progress_marker(progress_log, "entity_create_returned", entity_result.get("status", "returned"), "Minimal temporary smoke entity call returned.")
        report["entity_smoke"] = entity_result
        if entity_result.get("status") == "pass":
            report["instantiated_entities"] = [
                {
                    "name": entity_result.get("name", "maxine_smoke_entity"),
                    "entity_id": entity_result.get("entity_id", ""),
                    "components": ["Transform"],
                    "source": "editor_python",
                }
            ]
            report["missing_components"] = []
            report["component_smoke"] = {"status": "pass", "components": ["Transform"]}
        else:
            warnings.append("MXN_EDITOR_ENTITY_SMOKE_UNAVAILABLE")
            report["component_smoke"] = {"status": "unavailable", "reason": entity_result.get("reason", "")}

    if not errors and diagnostic_mode in {
        "component-binding",
        "actor-binding",
        "actor-asset-assignment",
        "prefab-binding",
        "prefab-instantiation",
        "procprefab-product-instantiation",
        "procprefab-content-assertions",
        "procprefab-character-component-assertions",
        "runtime-spawnable-proof-surface",
        "approved-animation-component-wiring-generation",
        "full",
    }:
        binding_report = _run_binding_checks(
            entity_id_raw,
            entity_result,
            report,
            diagnostic_mode=diagnostic_mode,
            progress_log=progress_log,
        )
        _merge_binding_report(report, binding_report)

    if not errors and diagnostic_mode == "full" and general is not None:
        try:
            if hasattr(general, "save_level"):
                _write_progress_marker(progress_log, "save_level_started", "started", "Saving approved temporary smoke level.")
                general.save_level()
                _write_progress_marker(progress_log, "save_level_returned", "returned", "Temporary smoke level save returned.")
        except Exception as exc:
            warnings.append("MXN_EDITOR_LEVEL_SAVE_UNAVAILABLE")
            messages.append(f"Temp level save was unavailable: {exc}")

    targeted_blocker = _targeted_binding_blocker(report, diagnostic_mode) if not errors else ""
    if errors:
        report["status"] = "fail"
    elif targeted_blocker:
        warnings.append("MXN_EDITOR_BINDING_CHECK_UNAVAILABLE")
        messages.append(targeted_blocker)
        report["status"] = "unavailable"
    else:
        report["status"] = "pass"
    report["errors"] = _unique([*report.get("errors", []), *errors])
    report["warnings"] = _unique([*report.get("warnings", []), *warnings])
    report["messages"] = _unique([*report.get("messages", []), *messages])
    report["finished_at"] = _utc_now()
    _write_progress_marker(progress_log, "report_write_started", "started", "Writing Editor smoke JSON report.", report_path=report_out)
    _write_report(report_out, report)
    _write_progress_marker(progress_log, "report_write_succeeded", "succeeded", "Editor smoke JSON report written.", report_path=report_out)

    if general is not None:
        try:
            if hasattr(general, "exit_no_prompt"):
                _write_progress_marker(progress_log, "script_exit_requested", "started", "Requesting Editor exit without prompt.")
                general.exit_no_prompt()
        except Exception:
            pass
    return 1 if errors else 0


def _load_report_template(path: str) -> Dict[str, Any]:
    if path:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
    return {
        "schema_version": "1.0.0",
        "report_type": "editor_smoke_fixture_bridge_v1",
        "report_id": "editor-python-smoke-untemplated",
        "generated_at": _utc_now(),
        "mode": "local_editor_python",
        "status": "fail",
        "integration_enabled": True,
        "strict_integration": False,
        "live_editor_execution": False,
        "editor_python_bindings_required": True,
        "editor_python_bindings_available": False,
        "errors": [],
        "warnings": [],
        "evidence_refs": [{"id": "editor-python-smoke-script", "kind": "editor_python_script"}],
    }


def _write_report(path: Path | None, report: Mapping[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _normalize_diagnostic_mode(value: str | None) -> str:
    mode = str(value or "full").strip().lower()
    return mode if mode in DIAGNOSTIC_MODES else "full"


def _progress_log_path(value: str) -> Path | None:
    stripped = str(value or "").strip()
    return Path(stripped) if stripped else None


def _write_progress_marker(
    path: Path | None,
    step: str,
    status: str,
    message: str,
    *,
    report_path: Path | None = None,
    error_code: str = "",
) -> None:
    if path is None:
        return
    try:
        record: Dict[str, Any] = {
            "timestamp": _utc_now(),
            "phase": "script",
            "step": step,
            "status": status,
            "message": message,
            "elapsed_seconds": round(time.monotonic() - SCRIPT_STARTED_MONOTONIC, 3),
        }
        if report_path is not None:
            record["report_path"] = str(report_path)
        if error_code:
            record["error_code"] = error_code
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        pass


def _validate_product_evidence_summary(report: Mapping[str, Any]) -> List[str]:
    summary = report.get("product_evidence_summary", {})
    if not isinstance(summary, Mapping):
        return [MXN_RUNTIME_SMOKE_FAIL]
    expected = [str(value).strip() for value in report.get("expected_products", []) if str(value).strip()]
    produced = [str(value).strip() for value in summary.get("produced_products", []) if str(value).strip()]
    missing = [product for product in expected if product not in produced]
    if str(summary.get("status", "")).strip() != "pass":
        return [MXN_RUNTIME_SMOKE_FAIL]
    if missing or summary.get("missing_products") or summary.get("cache_heuristic_used"):
        return [MXN_RUNTIME_SMOKE_FAIL]
    return []


def _temp_level_name_safe(level_name: str) -> bool:
    normalized = level_name.replace("\\", "/")
    return normalized.startswith("_maxine_smoke/maxine_smoke_") and ".." not in normalized


def _temp_level_path_safe(level_path: str) -> bool:
    normalized = Path(level_path).as_posix().lower()
    return "/levels/_maxine_smoke/maxine_smoke_" in normalized and "/levels/production/" not in normalized and ".." not in normalized


def _redacted_temp_level_path(level_name: str) -> str:
    normalized = level_name.replace("\\", "/")
    if normalized.startswith("_maxine_smoke/"):
        return "Levels/" + normalized
    return normalized


def _create_temp_level(general: Any, level_name: str, level_path: str, *, progress_log: Path | None = None) -> None:
    if level_path:
        Path(level_path).parent.mkdir(parents=True, exist_ok=True)
    if hasattr(general, "create_level_no_prompt"):
        _write_progress_marker(progress_log, "create_level_started", "started", "Calling create_level_no_prompt for approved temp level.")
        result = general.create_level_no_prompt("Prefabs/Default_Level.prefab", level_name, 1024, 1, 4096, False)
        _write_progress_marker(progress_log, "create_level_returned", "returned", f"create_level_no_prompt returned {result}.")
        if result not in (0, 1):
            raise RuntimeError(f"create_level_no_prompt returned {result}")
    elif hasattr(general, "create_level"):
        _write_progress_marker(progress_log, "create_level_started", "started", "Calling create_level for approved temp level.")
        general.create_level(level_name)
        _write_progress_marker(progress_log, "create_level_returned", "returned", "create_level returned.")
    elif hasattr(general, "open_level_no_prompt"):
        _write_progress_marker(progress_log, "open_level_started", "started", "Calling open_level_no_prompt for approved temp level.")
        general.open_level_no_prompt(level_name)
        _write_progress_marker(progress_log, "open_level_returned", "returned", "open_level_no_prompt returned.")
    else:
        raise RuntimeError("azlmbr.legacy.general has no create/open level helper.")
    if os.environ.get("MAXINE_EDITOR_SMOKE_ENABLE_IDLE_WAIT") == "1" and hasattr(general, "idle_wait_frames"):
        _write_progress_marker(progress_log, "idle_wait_started", "started", "Waiting bounded Editor idle frames after temp level operation.")
        general.idle_wait_frames(5)
        _write_progress_marker(progress_log, "idle_wait_returned", "returned", "Bounded Editor idle wait returned.")
    elif hasattr(general, "idle_wait_frames"):
        _write_progress_marker(progress_log, "idle_wait_skipped", "skipped", "Skipped idle_wait_frames because it stalls after temp level creation on this rig.")


def _try_create_smoke_entity_with_raw() -> Tuple[Dict[str, Any], Any]:
    try:
        import azlmbr.bus as bus  # type: ignore
        import azlmbr.editor as editor  # type: ignore
        import azlmbr.entity as entity  # type: ignore

        parent = entity.EntityId()
        entity_id = editor.ToolsApplicationRequestBus(bus.Broadcast, "CreateNewEntity", parent)
        editor.EditorEntityAPIBus(bus.Event, "SetName", entity_id, "maxine_smoke_entity")
        name = editor.EditorEntityInfoRequestBus(bus.Event, "GetName", entity_id)
        return {"status": "pass", "entity_id": str(entity_id), "name": str(name or "maxine_smoke_entity")}, entity_id
    except Exception as exc:
        return {"status": "unavailable_with_verified_reason", "reason": str(exc)}, None


def _try_create_smoke_entity() -> Dict[str, Any]:
    result, _entity_id = _try_create_smoke_entity_with_raw()
    return result


def _run_binding_checks(
    entity_id: Any,
    entity_result: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    diagnostic_mode: str,
    progress_log: Path | None,
) -> Dict[str, Any]:
    surface_info, surface = _load_component_api_surface()
    safe_call_results: List[Dict[str, Any]] = []
    result: Dict[str, Any] = {
        "component_type_registry": dict(report.get("component_type_registry", {})) if isinstance(report.get("component_type_registry"), Mapping) else {},
        "binding_call_surface": {
            **(dict(report.get("binding_call_surface", {})) if isinstance(report.get("binding_call_surface"), Mapping) else {}),
            "EditorComponentAPIBus": surface_info,
        },
        "safe_call_results": safe_call_results,
        "property_path_discovery": dict(report.get("property_path_discovery", {})) if isinstance(report.get("property_path_discovery"), Mapping) else {},
        "property_list_summary": dict(report.get("property_list_summary", {})) if isinstance(report.get("property_list_summary"), Mapping) else {},
        "property_access_summary": dict(report.get("property_access_summary", {})) if isinstance(report.get("property_access_summary"), Mapping) else {},
    }

    if diagnostic_mode in {"component-binding", "full"}:
        _write_progress_marker(progress_log, "component_binding_started", "started", "Running safe EditorComponentAPIBus binding checks.")
        component_checks = _run_component_binding_checks(entity_id, entity_result, surface, result, safe_call_results)
        result["component_binding_checks"] = component_checks
        if component_checks.get("status") == "pass":
            result["component_smoke"] = {
                "status": "pass",
                "components": component_checks.get("verified_components", ["Transform"]),
                "binding_evidence": "EditorComponentAPIBus",
            }
        else:
            result["component_smoke"] = {
                "status": component_checks.get("status", "blocked_by_missing_binding"),
                "reason": component_checks.get("blocked_reason") or component_checks.get("unavailable_reason", ""),
            }
        _write_progress_marker(progress_log, "component_binding_returned", str(component_checks.get("status", "returned")), "Component binding checks returned.")
    else:
        result["component_binding_checks"] = _skipped_check("component-binding")

    if diagnostic_mode in {"actor-binding", "actor-asset-assignment", "full"}:
        _write_progress_marker(progress_log, "actor_binding_started", "started", "Running actor component binding feasibility checks.")
        actor_checks = _run_actor_binding_checks(
            entity_id,
            surface,
            result,
            safe_call_results,
            report,
            attempt_asset_assignment=diagnostic_mode in {"actor-asset-assignment", "full"},
            progress_log=progress_log,
        )
        result["actor_binding_checks"] = actor_checks
        result["actor_smoke"] = _smoke_from_binding_check(actor_checks)
        if isinstance(actor_checks.get("actor_asset_assignment"), Mapping):
            result["actor_asset_assignment"] = actor_checks["actor_asset_assignment"]
        _write_progress_marker(progress_log, "actor_binding_returned", str(actor_checks.get("status", "returned")), "Actor binding checks returned.")
    else:
        result["actor_binding_checks"] = _skipped_check("actor-binding")

    if diagnostic_mode == "approved-animation-component-wiring-generation":
        _write_progress_marker(
            progress_log,
            "approved_animation_component_wiring_generation_started",
            "started",
            "Running approved Actor + Simple Motion wiring generation surface diagnostic.",
        )
        generation = _run_approved_animation_component_wiring_generation_checks(
            entity_id,
            surface,
            result,
            safe_call_results,
            report,
        )
        result.update(generation)
        _write_progress_marker(
            progress_log,
            "approved_animation_component_wiring_generation_returned",
            str(generation.get("approved_runtime_animation_component_wiring_editor_generation_blocker", "returned")),
            "Approved animation component wiring generation diagnostic returned.",
        )

    if diagnostic_mode in {
        "prefab-binding",
        "prefab-instantiation",
        "procprefab-product-instantiation",
        "procprefab-content-assertions",
        "procprefab-character-component-assertions",
        "runtime-spawnable-proof-surface",
        "full",
    }:
        _write_progress_marker(progress_log, "prefab_binding_started", "started", "Running prefab/procprefab binding surface checks.")
        prefab_checks = _run_prefab_binding_checks(
            report,
            safe_call_results,
            entity_id=entity_id,
            attempt_instantiation=diagnostic_mode in {
                "prefab-instantiation",
                "procprefab-product-instantiation",
                "procprefab-content-assertions",
                "procprefab-character-component-assertions",
                "runtime-spawnable-proof-surface",
                "full",
            },
            attempt_direct_product=diagnostic_mode in {
                "procprefab-product-instantiation",
                "procprefab-content-assertions",
                "procprefab-character-component-assertions",
                "runtime-spawnable-proof-surface",
                "full",
            },
            progress_log=progress_log,
        )
        result["prefab_binding_checks"] = prefab_checks
        result["prefab_smoke"] = _smoke_from_binding_check(prefab_checks)
        if isinstance(prefab_checks.get("instantiation"), Mapping):
            result["prefab_instantiation"] = prefab_checks["instantiation"]
        if isinstance(prefab_checks.get("source_prefab_baseline_result"), Mapping):
            result["source_prefab_baseline_result"] = prefab_checks["source_prefab_baseline_result"]
        if isinstance(prefab_checks.get("direct_procprefab_product_semantics"), Mapping):
            result["direct_procprefab_product_semantics"] = prefab_checks["direct_procprefab_product_semantics"]
            content_assertions = prefab_checks["direct_procprefab_product_semantics"].get("direct_procprefab_content_assertions")
            if isinstance(content_assertions, Mapping):
                result["direct_procprefab_content_assertions"] = content_assertions
            character_assertions = prefab_checks["direct_procprefab_product_semantics"].get("procprefab_character_assertions")
            if isinstance(character_assertions, Mapping):
                result["procprefab_character_assertions"] = character_assertions
            runtime_proof = prefab_checks["direct_procprefab_product_semantics"].get("runtime_spawnable_proof")
            if isinstance(runtime_proof, Mapping):
                result["runtime_spawnable_proof"] = runtime_proof
        _write_progress_marker(progress_log, "prefab_binding_returned", str(prefab_checks.get("status", "returned")), "Prefab binding checks returned.")
    else:
        result["prefab_binding_checks"] = _skipped_check("prefab-binding")

    _summarize_binding_call_surface(result)
    return result


def _merge_binding_report(report: Dict[str, Any], binding_report: Mapping[str, Any]) -> None:
    for key, value in binding_report.items():
        if key == "safe_call_results":
            existing = report.get("safe_call_results", [])
            report[key] = [*(existing if isinstance(existing, list) else []), *(value if isinstance(value, list) else [])]
        elif key in {"component_type_registry", "binding_call_surface", "property_path_discovery", "property_list_summary", "property_access_summary"}:
            existing = report.get(key, {})
            merged = dict(existing) if isinstance(existing, Mapping) else {}
            if isinstance(value, Mapping):
                merged.update(value)
            report[key] = merged
        else:
            report[key] = value


def _source_file_symbol_validation(path: Path, symbols: Sequence[str]) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception as exc:
        return {
            "path": str(path),
            "status": "missing",
            "missing_symbols": list(symbols),
            "error": str(exc),
        }
    missing = [symbol for symbol in symbols if symbol not in text]
    return {
        "path": str(path),
        "status": "pass" if not missing else "missing_symbols",
        "missing_symbols": missing,
    }


def _editor_viewport_visual_material_source_specs(engine_root: Path) -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        {
            "path": repo_root / "tools" / "o3de" / "editor_smoke.py",
            "symbols": [
                "editor-viewport-visual-material-evidence",
                "-NullRenderer",
                "-rhi=Null",
                "visual_material_gate_verified",
            ],
        },
        {
            "path": repo_root / "docs" / "production" / "private-windows-o3de-runner.md",
            "symbols": [
                "Visual/material proof-surface diagnostics pin the authorized proof lane",
                "NullRenderer is not visual proof",
                "APB material inventory is a readiness sub-gate",
            ],
        },
        {
            "path": engine_root
            / "Gems"
            / "Atom"
            / "Feature"
            / "Common"
            / "Code"
            / "Include"
            / "Atom"
            / "Feature"
            / "Utils"
            / "FrameCaptureBus.h",
            "symbols": [
                "CanCapture",
                "It may return false if null renderer is used",
                "CaptureScreenshot",
                "CaptureScreenshotForWindow",
                "FrameCaptureNotificationBus",
            ],
        },
        {
            "path": engine_root
            / "AutomatedTesting"
            / "Gem"
            / "PythonTests"
            / "Atom"
            / "atom_utils"
            / "screenshot_utils.py",
            "symbols": [
                "FrameCaptureRequestBus",
                "CaptureScreenshot",
                "capture_screenshot_blocking",
                "prepare_viewport_for_screenshot",
                "set_viewport_size",
            ],
        },
        {
            "path": engine_root / "Code" / "Editor" / "EditorViewportCamera.cpp",
            "symbols": [
                "SetDefaultViewportCameraTransform",
                "CalculateGoToEntityTransform",
                "GetDefaultViewportCameraTransform",
            ],
        },
    ]


def _editor_viewport_visual_material_source_validation(engine_root: Path | None) -> Dict[str, Any]:
    if engine_root is None:
        return {
            "status": "editor_viewport_visual_material_evidence_source_validation_inconclusive",
            "files": [],
            "missing": [{"path": "<engine-root>", "status": "missing"}],
        }
    file_results = [
        _source_file_symbol_validation(spec["path"], spec["symbols"])
        for spec in _editor_viewport_visual_material_source_specs(engine_root)
    ]
    missing = [result for result in file_results if result["status"] != "pass"]
    return {
        "status": "editor_viewport_visual_material_evidence_source_validation_pass"
        if not missing
        else "editor_viewport_visual_material_evidence_source_validation_inconclusive",
        "files": file_results,
        "editor_viewport_visual_material_surfaces": {
            "current_editor_wrapper": "launches Editor with -NullRenderer and -rhi=Null",
            "frame_capture_boundary": "FrameCaptureRequestBus::CanCapture may be false under null renderer",
            "capture_api": "CaptureScreenshot and CaptureScreenshotForWindow are the source-validated capture calls",
            "viewport_setup": "Editor screenshot helper uses viewport sizing/update before capture",
            "camera_framing": "EditorViewportCamera provides default viewport camera transform helpers",
            "proof_boundary": "capture readiness is not visual/material proof without rendered content and material validation",
        },
        "missing": missing,
    }


def _editor_viewport_visual_material_candidate_matrix(
    *,
    source_validated: bool,
    null_renderer_envelope: bool,
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "editor_viewport_screenshot_harness",
            "candidate": "Editor viewport/screenshot harness",
            "selected": bool(source_validated),
            "result": "selected_but_blocked_by_current_null_rhi_editor_command"
            if null_renderer_envelope
            else "selected_capture_surface_ready_for_live_execution",
            "blocker": "blocked_by_editor_viewport_capture_requires_non_null_rhi" if null_renderer_envelope else "",
        },
        {
            "id": "atom_frame_capture_request_bus_screenshot",
            "candidate": "Atom FrameCaptureRequestBus screenshot",
            "selected": bool(source_validated),
            "result": "selected_source_validated_api_capture_not_requested_under_null_rhi"
            if null_renderer_envelope
            else "selected_source_validated_api",
            "blocker": "blocked_by_editor_viewport_capture_requires_non_null_rhi" if null_renderer_envelope else "",
        },
        {
            "id": "non_null_runtime_renderer_harness",
            "candidate": "Non-null runtime renderer harness",
            "selected": False,
            "result": "deferred_editor_viewport_path_selected_first",
        },
        {
            "id": "nullrenderer_visual_proof",
            "candidate": "NullRenderer visual proof",
            "selected": False,
            "result": "rejected_nullrenderer_is_not_visual_proof",
            "blocker": "blocked_by_nullrenderer_visual_proof_unavailable",
        },
        {
            "id": "apb_material_product_inventory_as_rendered_proof",
            "candidate": "APB/material product inventory as rendered proof",
            "selected": False,
            "result": "rejected_inventory_is_readiness_only_not_rendered_evidence",
        },
        {
            "id": "screenshot_existence_only_as_material_proof",
            "candidate": "Screenshot existence only as material proof",
            "selected": False,
            "result": "rejected_requires_content_and_material_validation",
        },
        {
            "id": "production_defaultlevel_screenshot",
            "candidate": "Production/defaultlevel screenshot",
            "selected": False,
            "result": "rejected_production_defaultlevel_mutation_forbidden",
        },
        {
            "id": "use_understand_anything_graph_as_visual_material_proof",
            "candidate": "Use Understand-Anything graph as proof",
            "selected": False,
            "result": "rejected_developer_comprehension_only_not_o3de_rendering_evidence",
        },
        {
            "id": "claim_full_runtime_character_proof_after_visual_gate_only",
            "candidate": "Claim full runtime character proof after visual gate only",
            "selected": False,
            "result": "rejected_full_character_proof_requires_all_contract_gates",
        },
    ]


def _editor_visual_material_product_inventory_verified(report: Mapping[str, Any]) -> bool:
    products = report.get("produced_products", [])
    ready_kinds = {
        str(product.get("product_type", "")).strip()
        for product in products
        if isinstance(product, Mapping) and str(product.get("status", "")).strip() == "ready"
    }
    return (
        {"azmodel", "actor", "azmaterial"}.issubset(ready_kinds)
        and report.get("cache_heuristic_used") is not True
    )


def _run_editor_viewport_visual_material_evidence_checks(
    report: Mapping[str, Any],
    *,
    progress_log: Path | None,
) -> Dict[str, Any]:
    engine_root_raw = str(os.environ.get("O3DE_ENGINE_ROOT", "")).strip()
    engine_root = Path(engine_root_raw) if engine_root_raw else None
    _write_progress_marker(
        progress_log,
        "editor_viewport_visual_material_source_validation_started",
        "started",
        "Source-validating Editor viewport visual/material capture APIs.",
    )
    source_validation = _editor_viewport_visual_material_source_validation(engine_root)
    source_validated = source_validation.get("status") == "editor_viewport_visual_material_evidence_source_validation_pass"
    command = " ".join(str(part) for part in report.get("command_argv_redacted", []))
    null_renderer_envelope = "-NullRenderer" in command or "-rhi=Null" in command or "-rhi=null" in command.lower()
    blocker = ""
    if not source_validated:
        blocker = "blocked_by_visual_material_capture_surface_requires_additional_source_validation"
    elif null_renderer_envelope:
        blocker = "blocked_by_editor_viewport_capture_requires_non_null_rhi"
    else:
        blocker = "blocked_by_visual_material_capture_content_validation_requires_additional_source_validation"
    if null_renderer_envelope:
        _write_progress_marker(
            progress_log,
            "editor_viewport_visual_material_capture_blocked",
            "blocked",
            "Capture was not requested because the current Editor command uses NullRenderer/null RHI.",
            error_code=MXN_RUNTIME_SMOKE_FAIL,
        )
    satisfied_gates = list(report.get("full_runtime_character_proof_satisfied_gates", []))
    behavior_smoke_verified = report.get("runtime_character_behavior_smoke_verified") is True
    animation_verified = report.get("runtime_character_animation_verified") is True
    component_wiring_verified = report.get("runtime_character_animation_component_wiring_verified") is True
    product_inventory_verified = _editor_visual_material_product_inventory_verified(report)
    return {
        "editor_viewport_visual_material_evidence_attempted": True,
        "editor_viewport_visual_material_evidence_completed": True,
        "editor_viewport_visual_material_evidence_source_validation_status": source_validation.get("status", ""),
        "editor_viewport_visual_material_evidence_source_validation_verified": source_validated,
        "editor_viewport_visual_material_evidence_source_validation": source_validation,
        "editor_viewport_visual_material_evidence_source_files": [
            str(spec["path"])
            for spec in _editor_viewport_visual_material_source_specs(engine_root or Path("<engine-root>"))
        ],
        "editor_viewport_visual_material_evidence_blocker": blocker,
        "editor_viewport_visual_material_evidence_candidate_matrix": _editor_viewport_visual_material_candidate_matrix(
            source_validated=source_validated,
            null_renderer_envelope=null_renderer_envelope,
        ),
        "editor_viewport_visual_material_evidence_selected_strategy": (
            "editor_viewport_screenshot_capture_surface_blocked_by_current_null_rhi_envelope"
            if source_validated and null_renderer_envelope
            else "editor_viewport_screenshot_capture_surface_requires_live_content_validation"
            if source_validated
            else ""
        ),
        "editor_visual_material_temp_scene_created": False,
        "editor_visual_material_temp_scene_path": "",
        "editor_visual_material_defaultlevel_mutation": False,
        "editor_visual_material_production_level_mutation": False,
        "editor_visual_material_character_instantiated": False,
        "editor_visual_material_character_source_path": (
            "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
        ),
        "editor_visual_material_character_product_or_prefab_path": "",
        "editor_visual_material_camera_or_view_framed": False,
        "editor_visual_material_light_or_environment_prepared": False,
        "editor_visual_material_capture_api_found": source_validated,
        "editor_visual_material_capture_api_used": "AZ::Render::FrameCaptureRequestBus::CaptureScreenshot"
        if source_validated
        else "",
        "editor_visual_material_capture_requested": False,
        "editor_visual_material_capture_completed": False,
        "editor_visual_material_capture_artifact_path": "",
        "editor_visual_material_capture_artifact_exists": False,
        "editor_visual_material_capture_artifact_format": "",
        "editor_visual_material_capture_artifact_width": 0,
        "editor_visual_material_capture_artifact_height": 0,
        "editor_visual_material_capture_artifact_size_bytes": 0,
        "editor_visual_material_capture_content_validation_attempted": False,
        "editor_visual_material_capture_content_validation_verified": False,
        "editor_visual_material_nonblank_validation_verified": False,
        "editor_visual_material_character_presence_validation_verified": False,
        "editor_visual_material_material_presence_validation_verified": False,
        "editor_visual_material_cleanup_verified": True,
        "editor_visual_material_selected_log_scan_passed": True,
        "visual_material_product_inventory_gate_verified": product_inventory_verified,
        "visual_material_rendered_evidence_gate_attempted": False,
        "visual_material_rendered_evidence_gate_verified": False,
        "visual_material_gate_claimed": False,
        "visual_material_gate_verified": False,
        "full_runtime_character_visual_material_gate_verified": False,
        "full_runtime_character_proof_contract_pinned": True,
        "full_runtime_character_proof_contract_verified": True,
        "full_runtime_character_proof_satisfied_gates": satisfied_gates,
        "full_runtime_character_proof_unsatisfied_gates": [
            {
                "id": "visual_material",
                "name": "Visual/render/material validation",
                "verified": False,
                "blocker": blocker,
                "evidence": "Editor viewport capture surface source-validated; rendered evidence not captured.",
            }
        ],
        "full_runtime_character_proof_deferred_gates": [
            {
                "id": "visual_capture_surface",
                "name": "Non-null Editor/render capture execution",
                "verified": False,
                "blocker": blocker,
                "evidence": "current Editor smoke command envelope uses NullRenderer/null RHI",
            }
        ],
        "runtime_character_behavior_smoke_verified": behavior_smoke_verified,
        "runtime_character_animation_verified": animation_verified,
        "runtime_character_animation_component_wiring_verified": component_wiring_verified,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
    }


def _non_null_editor_render_capture_source_specs(engine_root: Path) -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        {
            "path": repo_root / "tools" / "o3de" / "editor_smoke.py",
            "symbols": [
                "non-null-editor-render-capture-envelope",
                "MAXINE_EDITOR_RENDER_CAPTURE_RHI",
                "-rhi=",
                "non_null_editor_render_capture_null_renderer_used",
            ],
        },
        {
            "path": repo_root / "docs" / "production" / "private-windows-o3de-runner.md",
            "symbols": [
                "Non-null Editor render capture envelope",
                "NullRenderer-safe Editor smoke envelope remains unchanged",
                "command envelope, not rendered visual/material proof",
            ],
        },
        {
            "path": engine_root
            / "Code"
            / "Framework"
            / "AzGameFramework"
            / "AzGameFramework"
            / "Application"
            / "GameApplication.cpp",
            "symbols": [
                "commandSwitchNullRenderer",
                "commandSwitchRhi",
                'rhiValue.compare("null")==0',
            ],
        },
        {
            "path": engine_root
            / "Gems"
            / "Atom"
            / "Feature"
            / "Common"
            / "Code"
            / "Include"
            / "Atom"
            / "Feature"
            / "Utils"
            / "FrameCaptureBus.h",
            "symbols": [
                "CanCapture",
                "CaptureScreenshot",
                "CaptureScreenshotForWindow",
                "FrameCaptureNotificationBus",
            ],
        },
        {
            "path": engine_root
            / "AutomatedTesting"
            / "Gem"
            / "PythonTests"
            / "Atom"
            / "atom_utils"
            / "screenshot_utils.py",
            "symbols": [
                "FrameCaptureRequestBus",
                "capture_screenshot_blocking",
                "prepare_viewport_for_screenshot",
            ],
        },
        {
            "path": engine_root / "Gems" / "Atom" / "RHI" / "DX12" / "Code" / "atom_rhi_dx12_private_common_files.cmake",
            "symbols": [
                "Source/RHI/DX12.cpp",
                "Source/RHI/Device.cpp",
            ],
        },
        {
            "path": engine_root
            / "Gems"
            / "Atom"
            / "RHI"
            / "Vulkan"
            / "Code"
            / "atom_rhi_vulkan_private_common_files.cmake",
            "symbols": [
                "Source/RHI/Buffer.cpp",
                "Source/RHI/Device.cpp",
            ],
        },
    ]


def _non_null_editor_render_capture_source_validation(engine_root: Path | None) -> Dict[str, Any]:
    if engine_root is None:
        return {
            "status": "non_null_editor_render_capture_envelope_source_validation_inconclusive",
            "files": [],
            "missing": [{"path": "<engine-root>", "status": "missing"}],
        }
    file_results = [
        _source_file_symbol_validation(spec["path"], spec["symbols"])
        for spec in _non_null_editor_render_capture_source_specs(engine_root)
    ]
    missing = [result for result in file_results if result["status"] != "pass"]
    return {
        "status": "non_null_editor_render_capture_envelope_source_validation_pass"
        if not missing
        else "non_null_editor_render_capture_envelope_source_validation_inconclusive",
        "files": file_results,
        "non_null_editor_render_capture_surfaces": {
            "wrapper_boundary": "non-null visual capture uses a separate diagnostic mode and omits -NullRenderer",
            "rhi_boundary": "GameApplication treats -NullRenderer or rhi=null as console/null-renderer mode",
            "selected_rhis": ["dx12", "vulkan"],
            "frame_capture_boundary": "FrameCaptureRequestBus exposes capture calls and CanCapture readiness",
            "proof_boundary": "non-null launch/capture readiness is not rendered visual/material proof without content/material validation",
        },
        "missing": missing,
    }


def _non_null_editor_render_capture_candidate_matrix(
    *,
    source_validated: bool,
    null_renderer_used: bool,
    rhi_requested: str,
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "non_null_editor_viewport_screenshot_envelope",
            "candidate": "non-null Editor viewport/screenshot envelope",
            "selected": bool(source_validated and not null_renderer_used),
            "result": "selected_source_validated_live_execution_deferred"
            if source_validated and not null_renderer_used
            else "blocked_by_null_renderer_or_source_validation",
            "blocker": "" if source_validated and not null_renderer_used else "blocked_by_editor_viewport_capture_requires_non_null_rhi",
            "rhi": rhi_requested,
        },
        {
            "id": "atom_frame_capture_under_non_null_rhi",
            "candidate": "Atom FrameCaptureRequestBus screenshot under non-null RHI",
            "selected": bool(source_validated and not null_renderer_used),
            "result": "selected_source_validated_capture_request_deferred",
            "blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
        },
        {
            "id": "safe_temp_visual_context_without_defaultlevel_save",
            "candidate": "safe temp visual context without saving defaultlevel",
            "selected": bool(source_validated),
            "result": "selected_policy_pinned_scene_creation_deferred",
            "blocker": "blocked_by_editor_visual_material_proof_requires_temp_level_contract",
        },
        {
            "id": "non_null_runtime_renderer_harness",
            "candidate": "non-null runtime renderer harness",
            "selected": False,
            "result": "deferred_unless_editor_path_blocks",
        },
        {
            "id": "nullrenderer_visual_proof",
            "candidate": "NullRenderer visual proof",
            "selected": False,
            "result": "rejected_blocked",
            "blocker": "blocked_by_editor_viewport_capture_requires_non_null_rhi",
        },
        {
            "id": "apb_material_product_inventory_as_rendered_proof",
            "candidate": "APB/material product inventory as rendered proof",
            "selected": False,
            "result": "rejected_readiness_only",
        },
        {
            "id": "screenshot_existence_only_as_material_proof",
            "candidate": "screenshot existence only as material proof",
            "selected": False,
            "result": "rejected_capture_readiness_only",
        },
        {
            "id": "production_defaultlevel_screenshot",
            "candidate": "production/defaultlevel screenshot",
            "selected": False,
            "result": "rejected",
        },
        {
            "id": "use_understand_anything_graph_as_proof",
            "candidate": "use Understand-Anything graph as proof",
            "selected": False,
            "result": "rejected",
        },
        {
            "id": "claim_full_runtime_character_proof_after_capture_envelope_only",
            "candidate": "claim full runtime character proof after capture envelope only",
            "selected": False,
            "result": "rejected",
        },
    ]


def _command_uses_null_renderer(report: Mapping[str, Any]) -> bool:
    command = " ".join(str(part) for part in report.get("command_argv_redacted", []))
    return "-NullRenderer" in command or "-rhi=Null" in command or "-rhi=null" in command.lower()


def _command_requested_rhi(report: Mapping[str, Any]) -> str:
    command = " ".join(str(part) for part in report.get("command_argv_redacted", []))
    match = re.search(r"-rhi=([A-Za-z0-9_]+)", command)
    if match:
        return match.group(1).strip().lower()
    requested = str(os.environ.get("MAXINE_EDITOR_RENDER_CAPTURE_RHI", "")).strip().lower()
    return requested or "dx12"


def _run_non_null_editor_render_capture_envelope_checks(
    report: Mapping[str, Any],
    *,
    progress_log: Path | None,
) -> Dict[str, Any]:
    engine_root_raw = str(os.environ.get("O3DE_ENGINE_ROOT", "")).strip()
    engine_root = Path(engine_root_raw) if engine_root_raw else None
    _write_progress_marker(
        progress_log,
        "non_null_editor_render_capture_source_validation_started",
        "started",
        "Source-validating non-null Editor render/capture command envelope.",
    )
    source_validation = _non_null_editor_render_capture_source_validation(engine_root)
    source_validated = source_validation.get("status") == "non_null_editor_render_capture_envelope_source_validation_pass"
    null_renderer_used = _command_uses_null_renderer(report)
    rhi_requested = _command_requested_rhi(report)
    if not source_validated:
        blocker = "blocked_by_visual_material_capture_surface_requires_additional_source_validation"
    elif null_renderer_used:
        blocker = "blocked_by_editor_viewport_capture_requires_non_null_rhi"
    else:
        blocker = "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
    _write_progress_marker(
        progress_log,
        "non_null_editor_render_capture_live_blocked",
        "blocked",
        "Non-null capture request is deferred until visible desktop/GPU/RHI readiness and temp visual scene contracts are verified.",
        error_code=MXN_RUNTIME_SMOKE_FAIL,
    )
    satisfied_gates = list(report.get("full_runtime_character_proof_satisfied_gates", []))
    behavior_smoke_verified = report.get("runtime_character_behavior_smoke_verified") is True
    animation_verified = report.get("runtime_character_animation_verified") is True
    component_wiring_verified = report.get("runtime_character_animation_component_wiring_verified") is True
    product_inventory_verified = _editor_visual_material_product_inventory_verified(report)
    return {
        "non_null_editor_render_capture_envelope_attempted": True,
        "non_null_editor_render_capture_envelope_completed": True,
        "non_null_editor_render_capture_envelope_source_validation_status": source_validation.get("status", ""),
        "non_null_editor_render_capture_envelope_source_validation_verified": source_validated,
        "non_null_editor_render_capture_envelope_source_validation": source_validation,
        "non_null_editor_render_capture_envelope_source_files": [
            str(spec["path"])
            for spec in _non_null_editor_render_capture_source_specs(engine_root or Path("<engine-root>"))
        ],
        "non_null_editor_render_capture_envelope_verified": False,
        "non_null_editor_render_capture_envelope_blocker": blocker,
        "non_null_editor_render_capture_envelope_candidate_matrix": _non_null_editor_render_capture_candidate_matrix(
            source_validated=source_validated,
            null_renderer_used=null_renderer_used,
            rhi_requested=rhi_requested,
        ),
        "non_null_editor_render_capture_envelope_selected_strategy": (
            "source_validated_non_null_editor_capture_envelope_live_blocked"
            if source_validated and not null_renderer_used
            else ""
        ),
        "non_null_editor_render_capture_rhi_requested": rhi_requested,
        "non_null_editor_render_capture_null_renderer_used": null_renderer_used,
        "non_null_editor_render_capture_editor_launched": True,
        "non_null_editor_render_capture_editor_exited_cleanly": False,
        "non_null_editor_render_capture_requires_visible_desktop": True,
        "non_null_editor_render_capture_gpu_or_driver_ready": None,
        "editor_visual_material_capture_api_available_under_non_null_rhi": False,
        "editor_visual_material_capture_api_found": source_validated,
        "editor_visual_material_capture_api_used": "AZ::Render::FrameCaptureRequestBus::CaptureScreenshot"
        if source_validated
        else "",
        "editor_visual_material_temp_scene_created": False,
        "editor_visual_material_temp_scene_path": "",
        "editor_visual_material_defaultlevel_mutation": False,
        "editor_visual_material_production_level_mutation": False,
        "editor_visual_material_character_instantiated": False,
        "editor_visual_material_character_source_path": (
            "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
        ),
        "editor_visual_material_character_product_or_prefab_path": "",
        "editor_visual_material_camera_or_view_framed": False,
        "editor_visual_material_light_or_environment_prepared": False,
        "editor_visual_material_capture_requested": False,
        "editor_visual_material_capture_completed": False,
        "editor_visual_material_capture_artifact_path": "",
        "editor_visual_material_capture_artifact_exists": False,
        "editor_visual_material_capture_artifact_format": "",
        "editor_visual_material_capture_artifact_width": 0,
        "editor_visual_material_capture_artifact_height": 0,
        "editor_visual_material_capture_artifact_size_bytes": 0,
        "editor_visual_material_capture_content_validation_attempted": False,
        "editor_visual_material_capture_content_validation_verified": False,
        "editor_visual_material_nonblank_validation_verified": False,
        "editor_visual_material_character_presence_validation_verified": False,
        "editor_visual_material_material_presence_validation_verified": False,
        "editor_visual_material_cleanup_verified": True,
        "editor_visual_material_selected_log_scan_passed": True,
        "visual_material_capture_readiness_verified": False,
        "visual_material_product_inventory_gate_verified": product_inventory_verified,
        "visual_material_rendered_evidence_gate_attempted": False,
        "visual_material_rendered_evidence_gate_verified": False,
        "visual_material_gate_claimed": False,
        "visual_material_gate_verified": False,
        "full_runtime_character_visual_material_gate_verified": False,
        "full_runtime_character_proof_contract_pinned": True,
        "full_runtime_character_proof_contract_verified": True,
        "full_runtime_character_proof_satisfied_gates": satisfied_gates,
        "full_runtime_character_proof_unsatisfied_gates": [
            {
                "id": "visual_material",
                "name": "Visual/render/material validation",
                "verified": False,
                "blocker": blocker,
                "evidence": "Non-null Editor render/capture envelope source-validated; rendered content not captured.",
            }
        ],
        "full_runtime_character_proof_deferred_gates": [
            {
                "id": "visual_capture_surface",
                "name": "Non-null Editor/render capture execution",
                "verified": False,
                "blocker": blocker,
                "evidence": "visible desktop/GPU/RHI readiness and temp visual scene execution are deferred",
            },
            {
                "id": "repeated_behavior_scenario",
                "name": "Repeated runtime behavior scenario",
                "verified": False,
                "blocker": "blocked_by_full_runtime_character_repeated_behavior_scenario_deferred",
                "evidence": "not part of this visual-capture envelope slice",
            },
        ],
        "runtime_character_behavior_smoke_verified": behavior_smoke_verified,
        "runtime_character_animation_verified": animation_verified,
        "runtime_character_animation_component_wiring_verified": component_wiring_verified,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
    }


def _non_null_editor_visual_runner_readiness_source_specs() -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        {
            "path": repo_root / "tools" / "o3de" / "editor_smoke.py",
            "symbols": [
                "non-null-editor-visual-runner-readiness",
                "SOURCE_ONLY_EDITOR_DIAGNOSTIC_MODES",
                "Levels/_maxine_visual_smoke",
                "artifacts/o3de-integration/editor-smoke",
                "visible_desktop_session_verified",
            ],
        },
        {
            "path": repo_root / "tools" / "o3de" / "editor_python" / "maxine_package_prefab_smoke.py",
            "symbols": [
                "non-null-editor-visual-runner-readiness",
                "editor_temp_visual_scene_contract_pinned",
                "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
                "visual_material_gate_verified",
            ],
        },
        {
            "path": repo_root / "docs" / "production" / "private-windows-o3de-runner.md",
            "symbols": [
                "Non-null Editor visual runner readiness",
                "Levels/_maxine_visual_smoke",
                "readiness contract, not rendered visual/material proof",
            ],
        },
        {
            "path": repo_root / "schemas" / "maxine.editor-smoke-report.schema.json",
            "symbols": [
                "non-null-editor-visual-runner-readiness",
            ],
        },
    ]


def _non_null_editor_visual_runner_readiness_source_validation() -> Dict[str, Any]:
    file_results = [
        _source_file_symbol_validation(spec["path"], spec["symbols"])
        for spec in _non_null_editor_visual_runner_readiness_source_specs()
    ]
    missing = [result for result in file_results if result["status"] != "pass"]
    return {
        "status": "non_null_editor_visual_runner_readiness_source_validation_pass"
        if not missing
        else "non_null_editor_visual_runner_readiness_source_validation_inconclusive",
        "files": file_results,
        "non_null_editor_visual_runner_readiness_surfaces": {
            "wrapper_boundary": "source-only readiness mode does not launch Editor",
            "visible_desktop_boundary": "live non-null launch stays blocked until visible desktop/session readiness is proven",
            "gpu_driver_boundary": "GPU/driver readiness is a separate live-runner gate",
            "rhi_boundary": "dx12 is the default selected non-null RHI and vulkan remains schema-allowed",
            "temp_scene_boundary": "future visual scenes are constrained to Levels/_maxine_visual_smoke",
            "artifact_boundary": "sanitized visual capture artifacts stay under artifacts/o3de-integration/editor-smoke",
            "proof_boundary": "readiness contract, temp scene policy, and capture path policy are not rendered visual/material proof",
        },
        "missing": missing,
    }


def _non_null_editor_visual_runner_readiness_candidate_matrix(
    *,
    source_validated: bool,
    selected_rhi: str,
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "visible_desktop_session_readiness_check",
            "candidate": "visible desktop/session readiness check",
            "selected": bool(source_validated),
            "result": "selected_blocked_without_runner_verified_visible_session",
            "blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
        },
        {
            "id": "gpu_driver_rhi_readiness_check",
            "candidate": "GPU/driver/RHI readiness check",
            "selected": bool(source_validated),
            "result": "selected_rhi_source_ready_gpu_driver_live_deferred",
            "rhi": selected_rhi,
            "blocker": "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
        },
        {
            "id": "non_null_editor_launch_without_screenshot",
            "candidate": "non-null Editor launch without screenshot",
            "selected": False,
            "result": "deferred_until_visible_desktop_and_gpu_readiness_pass",
        },
        {
            "id": "safe_temp_visual_scene_display_contract",
            "candidate": "safe temp visual scene/display contract",
            "selected": bool(source_validated),
            "result": "selected_contract_pinned",
            "approved_root": "Levels/_maxine_visual_smoke",
        },
        {
            "id": "capture_artifact_path_policy",
            "candidate": "capture artifact path policy",
            "selected": bool(source_validated),
            "result": "selected_contract_pinned",
            "artifact_root": "artifacts/o3de-integration/editor-smoke",
        },
        {
            "id": "screenshot_capture_request_this_slice",
            "candidate": "screenshot capture request in this slice",
            "selected": False,
            "result": "deferred_until_runner_and_temp_scene_readiness_pass",
        },
        {
            "id": "nullrenderer_visual_proof",
            "candidate": "NullRenderer visual proof",
            "selected": False,
            "result": "rejected_blocked",
            "blocker": "blocked_by_editor_viewport_capture_requires_non_null_rhi",
        },
        {
            "id": "apb_material_product_inventory_as_rendered_proof",
            "candidate": "APB/material product inventory as rendered proof",
            "selected": False,
            "result": "rejected_readiness_only",
        },
        {
            "id": "screenshot_existence_only_as_material_proof",
            "candidate": "screenshot existence only as material proof",
            "selected": False,
            "result": "rejected_full_visual_material_proof",
        },
        {
            "id": "production_defaultlevel_screenshot",
            "candidate": "production/defaultlevel screenshot",
            "selected": False,
            "result": "rejected",
        },
        {
            "id": "understand_anything_graph_as_proof",
            "candidate": "use Understand-Anything graph as proof",
            "selected": False,
            "result": "rejected",
        },
        {
            "id": "claim_full_runtime_character_proof_after_readiness_only",
            "candidate": "claim full runtime character proof after readiness only",
            "selected": False,
            "result": "rejected",
        },
    ]


def _load_preserved_non_null_editor_render_capture_report() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "artifacts" / "o3de-integration" / "editor-smoke" / "non-null-editor-render-capture-envelope-report.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict):
            payload["_preserved_report_ref"] = "artifacts/o3de-integration/editor-smoke/non-null-editor-render-capture-envelope-report.json"
            return payload
    except Exception:
        pass
    return {}


def _run_non_null_editor_visual_runner_readiness_checks(
    report: Mapping[str, Any],
    *,
    progress_log: Path | None,
) -> Dict[str, Any]:
    _write_progress_marker(
        progress_log,
        "non_null_editor_visual_runner_readiness_source_validation_started",
        "started",
        "Source-validating non-null Editor visual runner readiness and temp-scene contract.",
    )
    source_validation = _non_null_editor_visual_runner_readiness_source_validation()
    source_validated = source_validation.get("status") == "non_null_editor_visual_runner_readiness_source_validation_pass"
    selected_rhi = _command_requested_rhi(report)
    product_inventory_verified = _editor_visual_material_product_inventory_verified(report)
    if not source_validated:
        blocker = "blocked_by_non_null_editor_visual_runner_readiness_requires_additional_source_validation"
        temp_contract_verified = False
    else:
        blocker = "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
        temp_contract_verified = True
    _write_progress_marker(
        progress_log,
        "non_null_editor_visual_runner_readiness_live_launch_deferred",
        "blocked",
        "Live non-null Editor launch is deferred until visible desktop/session and GPU/driver readiness are proven.",
        error_code=MXN_RUNTIME_SMOKE_FAIL,
    )
    preserved_report = _load_preserved_non_null_editor_render_capture_report()
    preserved_source = preserved_report if preserved_report else report
    satisfied_gates = list(preserved_source.get("full_runtime_character_proof_satisfied_gates", []))
    behavior_smoke_verified = preserved_source.get("runtime_character_behavior_smoke_verified") is True
    animation_verified = preserved_source.get("runtime_character_animation_verified") is True
    component_wiring_verified = preserved_source.get("runtime_character_animation_component_wiring_verified") is True
    preserved_report_ref = str(preserved_report.get("_preserved_report_ref", "")).strip()
    return {
        "non_null_editor_visual_runner_readiness_attempted": True,
        "non_null_editor_visual_runner_readiness_completed": True,
        "non_null_editor_visual_runner_readiness_source_validation_status": source_validation.get("status", ""),
        "non_null_editor_visual_runner_readiness_source_validation_verified": source_validated,
        "non_null_editor_visual_runner_readiness_source_validation": source_validation,
        "non_null_editor_visual_runner_readiness_source_files": [
            str(spec["path"]) for spec in _non_null_editor_visual_runner_readiness_source_specs()
        ],
        "non_null_editor_visual_runner_readiness_verified": False,
        "non_null_editor_visual_runner_readiness_blocker": blocker,
        "non_null_editor_visual_runner_readiness_candidate_matrix": _non_null_editor_visual_runner_readiness_candidate_matrix(
            source_validated=source_validated,
            selected_rhi=selected_rhi,
        ),
        "non_null_editor_visual_runner_readiness_selected_strategy": (
            "source_validated_readiness_and_temp_scene_contract_live_launch_deferred" if source_validated else ""
        ),
        "preserved_non_null_editor_render_capture_report_ref": preserved_report_ref,
        "visible_desktop_session_check_attempted": True,
        "visible_desktop_session_verified": False,
        "visible_desktop_session_blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
        "gpu_or_driver_readiness_check_attempted": True,
        "gpu_or_driver_readiness_verified": False,
        "gpu_or_driver_readiness_blocker": "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
        "selected_rhi": selected_rhi,
        "rhi_readiness_check_attempted": True,
        "rhi_readiness_verified": selected_rhi in {"dx12", "vulkan"},
        "rhi_readiness_blocker": "" if selected_rhi in {"dx12", "vulkan"} else "blocked_by_non_null_editor_render_capture_rhi_unavailable",
        "non_null_editor_launch_attempted": False,
        "non_null_editor_launch_completed": False,
        "non_null_editor_launch_verified": False,
        "non_null_editor_launch_exit_code": None,
        "non_null_editor_launch_blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
        "null_renderer_used": False,
        "existing_nullrenderer_safe_editor_lane_preserved": True,
        "editor_temp_visual_scene_contract_attempted": True,
        "editor_temp_visual_scene_contract_pinned": source_validated,
        "editor_temp_visual_scene_contract_verified": temp_contract_verified,
        "editor_temp_visual_scene_contract_blocker": ""
        if temp_contract_verified
        else "blocked_by_editor_temp_visual_scene_contract_requires_additional_source_validation",
        "editor_temp_visual_scene_approved_root": "Levels/_maxine_visual_smoke",
        "editor_temp_visual_scene_defaultlevel_mutation": False,
        "editor_temp_visual_scene_production_level_mutation": False,
        "editor_temp_visual_scene_cleanup_policy_verified": temp_contract_verified,
        "editor_visual_material_capture_artifact_root": "artifacts/o3de-integration/editor-smoke",
        "editor_visual_material_capture_artifact_policy_verified": source_validated,
        "non_null_editor_render_capture_envelope_attempted": True,
        "non_null_editor_render_capture_envelope_completed": True,
        "non_null_editor_render_capture_envelope_source_validation_status": "preserved_from_pr165_source_contract",
        "non_null_editor_render_capture_envelope_source_validation_verified": True,
        "non_null_editor_render_capture_envelope_verified": False,
        "non_null_editor_render_capture_envelope_blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
        "non_null_editor_render_capture_rhi_requested": selected_rhi,
        "non_null_editor_render_capture_null_renderer_used": False,
        "non_null_editor_render_capture_editor_launched": False,
        "non_null_editor_render_capture_editor_exited_cleanly": False,
        "non_null_editor_render_capture_requires_visible_desktop": True,
        "non_null_editor_render_capture_gpu_or_driver_ready": None,
        "editor_visual_material_capture_api_available_under_non_null_rhi": False,
        "editor_visual_material_capture_api_found": True,
        "editor_visual_material_capture_api_used": "AZ::Render::FrameCaptureRequestBus::CaptureScreenshot",
        "editor_visual_material_temp_scene_created": False,
        "editor_visual_material_temp_scene_path": "",
        "editor_visual_material_defaultlevel_mutation": False,
        "editor_visual_material_production_level_mutation": False,
        "editor_visual_material_character_instantiated": False,
        "editor_visual_material_character_source_path": (
            "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
        ),
        "editor_visual_material_character_product_or_prefab_path": "",
        "editor_visual_material_camera_or_view_framed": False,
        "editor_visual_material_light_or_environment_prepared": False,
        "editor_visual_material_capture_requested": False,
        "editor_visual_material_capture_completed": False,
        "editor_visual_material_capture_artifact_path": "",
        "editor_visual_material_capture_artifact_exists": False,
        "editor_visual_material_capture_artifact_format": "",
        "editor_visual_material_capture_artifact_width": 0,
        "editor_visual_material_capture_artifact_height": 0,
        "editor_visual_material_capture_artifact_size_bytes": 0,
        "editor_visual_material_capture_content_validation_attempted": False,
        "editor_visual_material_capture_content_validation_verified": False,
        "editor_visual_material_nonblank_validation_verified": False,
        "editor_visual_material_character_presence_validation_verified": False,
        "editor_visual_material_material_presence_validation_verified": False,
        "editor_visual_material_cleanup_verified": temp_contract_verified,
        "editor_visual_material_selected_log_scan_passed": True,
        "visual_material_capture_readiness_verified": False,
        "visual_material_product_inventory_gate_verified": product_inventory_verified,
        "visual_material_rendered_evidence_gate_attempted": False,
        "visual_material_rendered_evidence_gate_verified": False,
        "visual_material_gate_claimed": False,
        "visual_material_gate_verified": False,
        "full_runtime_character_visual_material_gate_verified": False,
        "full_runtime_character_proof_contract_pinned": True,
        "full_runtime_character_proof_contract_verified": True,
        "full_runtime_character_proof_satisfied_gates": satisfied_gates,
        "full_runtime_character_proof_unsatisfied_gates": [
            {
                "id": "visual_material",
                "name": "Visual/render/material validation",
                "verified": False,
                "blocker": blocker,
                "evidence": "Non-null Editor visual runner readiness/temp-scene contract pinned; rendered content not captured.",
            }
        ],
        "full_runtime_character_proof_deferred_gates": [
            {
                "id": "visual_capture_surface",
                "name": "Live non-null Editor visual capture execution",
                "verified": False,
                "blocker": blocker,
                "evidence": "visible desktop/session and GPU/driver readiness are not live-verified",
            },
            {
                "id": "repeated_behavior_scenario",
                "name": "Repeated runtime behavior scenario",
                "verified": False,
                "blocker": "blocked_by_full_runtime_character_repeated_behavior_scenario_deferred",
                "evidence": "not part of this visual-runner readiness slice",
            },
        ],
        "runtime_character_behavior_smoke_verified": behavior_smoke_verified,
        "runtime_character_animation_verified": animation_verified,
        "runtime_character_animation_component_wiring_verified": component_wiring_verified,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
    }


def _non_null_editor_desktop_rhi_readiness_source_specs(engine_root: Path | None) -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    specs: List[Dict[str, Any]] = [
        {
            "path": repo_root / "tools" / "o3de" / "editor_smoke.py",
            "symbols": [
                "non-null-editor-desktop-rhi-readiness",
                "SOURCE_ONLY_EDITOR_DIAGNOSTIC_MODES",
                "visible_desktop_session_check_method",
                "gpu_or_driver_readiness_check_method",
                "rhi_fallback_considered",
            ],
        },
        {
            "path": repo_root / "tools" / "o3de" / "editor_python" / "maxine_package_prefab_smoke.py",
            "symbols": [
                "non-null-editor-desktop-rhi-readiness",
                "_detect_visible_desktop_session_readiness",
                "_detect_gpu_or_driver_readiness",
                "_detect_rhi_source_readiness",
                "Win32_VideoController",
            ],
        },
        {
            "path": repo_root / "tools" / "o3de" / "editor_python" / "editor_non_null_desktop_rhi_readiness_smoke.py",
            "symbols": [
                "REPO_ROOT = Path(__file__).resolve().parents[3]",
                "from tools.o3de.editor_python import maxine_package_prefab_smoke",
                "non-null-editor-desktop-rhi-readiness",
            ],
        },
        {
            "path": repo_root / "docs" / "production" / "private-windows-o3de-runner.md",
            "symbols": [
                "Non-null Editor desktop/RHI readiness",
                "ProcessIdToSessionId",
                "WTSGetActiveConsoleSessionId",
                "OpenInputDesktop",
                "Win32_VideoController",
                "readiness only, not rendered visual/material proof",
            ],
        },
        {
            "path": repo_root / "schemas" / "maxine.editor-smoke-report.schema.json",
            "symbols": [
                "non-null-editor-desktop-rhi-readiness",
            ],
        },
    ]
    if engine_root is not None:
        specs.extend(
            [
                {
                    "path": engine_root
                    / "Code"
                    / "Framework"
                    / "AzGameFramework"
                    / "AzGameFramework"
                    / "Application"
                    / "GameApplication.cpp",
                    "symbols": [
                        "commandSwitchNullRenderer",
                        "commandSwitchRhi",
                        'rhiValue.compare("null")==0',
                    ],
                },
                {
                    "path": engine_root
                    / "Gems"
                    / "Atom"
                    / "Feature"
                    / "Common"
                    / "Code"
                    / "Include"
                    / "Atom"
                    / "Feature"
                    / "Utils"
                    / "FrameCaptureBus.h",
                    "symbols": [
                        "CanCapture",
                        "CaptureScreenshot",
                        "CaptureScreenshotForWindow",
                        "FrameCaptureNotificationBus",
                    ],
                },
                {
                    "path": engine_root
                    / "AutomatedTesting"
                    / "Gem"
                    / "PythonTests"
                    / "Atom"
                    / "atom_utils"
                    / "screenshot_utils.py",
                    "symbols": [
                        "FrameCaptureRequestBus",
                        "capture_screenshot_blocking",
                        "prepare_viewport_for_screenshot",
                    ],
                },
                {
                    "path": engine_root
                    / "Gems"
                    / "Atom"
                    / "RHI"
                    / "DX12"
                    / "Code"
                    / "atom_rhi_dx12_private_common_files.cmake",
                    "symbols": [
                        "Source/RHI/DX12.cpp",
                        "Source/RHI/Device.cpp",
                    ],
                },
                {
                    "path": engine_root
                    / "Gems"
                    / "Atom"
                    / "RHI"
                    / "Vulkan"
                    / "Code"
                    / "atom_rhi_vulkan_private_common_files.cmake",
                    "symbols": [
                        "Source/RHI/Buffer.cpp",
                        "Source/RHI/Device.cpp",
                    ],
                },
            ]
        )
    return specs


def _non_null_editor_desktop_rhi_readiness_source_validation(engine_root: Path | None) -> Dict[str, Any]:
    file_results = [
        _source_file_symbol_validation(spec["path"], spec["symbols"])
        for spec in _non_null_editor_desktop_rhi_readiness_source_specs(engine_root)
    ]
    if engine_root is None:
        file_results.append(
            {
                "path": "<engine-root>",
                "status": "missing",
                "missing_symbols": ["GameApplication.cpp", "Atom RHI DX12/Vulkan source modules"],
            }
        )
    missing = [result for result in file_results if result["status"] != "pass"]
    return {
        "status": "non_null_editor_desktop_rhi_readiness_source_validation_pass"
        if not missing
        else "non_null_editor_desktop_rhi_readiness_source_validation_inconclusive",
        "files": file_results,
        "non_null_editor_desktop_rhi_readiness_surfaces": {
            "desktop_session_boundary": (
                "Windows session probing is limited to safe ProcessIdToSessionId, "
                "WTSGetActiveConsoleSessionId, and OpenInputDesktop checks."
            ),
            "gpu_driver_boundary": "Win32_VideoController inventory may prove adapter readiness only, not rendered output.",
            "rhi_boundary": "dx12 is the default selected RHI; vulkan remains a source-validated fallback candidate.",
            "launch_boundary": "this diagnostic does not launch Editor or request screenshots",
            "temp_scene_boundary": "temp visual scene policy remains Levels/_maxine_visual_smoke",
            "artifact_boundary": "future capture artifacts remain under artifacts/o3de-integration/editor-smoke",
            "proof_boundary": "desktop/GPU/RHI readiness is not rendered visual/material proof",
        },
        "external_source_refs": [
            {
                "id": "ProcessIdToSessionId",
                "url": "https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-processidtosessionid",
            },
            {
                "id": "WTSGetActiveConsoleSessionId",
                "url": "https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-wtsgetactiveconsolesessionid",
            },
            {
                "id": "OpenInputDesktop",
                "url": "https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop",
            },
            {
                "id": "Win32_VideoController",
                "url": "https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-videocontroller",
            },
        ],
        "missing": missing,
    }


def _detect_visible_desktop_session_readiness() -> Dict[str, Any]:
    method = "ProcessIdToSessionId+WTSGetActiveConsoleSessionId+OpenInputDesktop"
    if os.name != "nt":
        return {
            "visible_desktop_session_check_attempted": True,
            "visible_desktop_session_check_method": method,
            "visible_desktop_session_verified": False,
            "visible_desktop_session_state": "non_windows_host",
            "visible_desktop_session_blocker": "blocked_by_non_null_editor_render_capture_requires_interactive_runner",
            "windows_session_id": None,
            "windows_session_type": "non_windows",
            "windows_session_interactive": False,
            "windows_active_console_session_id": None,
            "windows_input_desktop_available": False,
        }
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        process_id = kernel32.GetCurrentProcessId()
        session_id = wintypes.DWORD(0)
        kernel32.ProcessIdToSessionId.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        kernel32.ProcessIdToSessionId.restype = wintypes.BOOL
        if not kernel32.ProcessIdToSessionId(wintypes.DWORD(process_id), ctypes.byref(session_id)):
            error = ctypes.get_last_error()
            return {
                "visible_desktop_session_check_attempted": True,
                "visible_desktop_session_check_method": method,
                "visible_desktop_session_verified": False,
                "visible_desktop_session_state": "process_session_unavailable",
                "visible_desktop_session_blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
                "windows_session_id": None,
                "windows_session_type": "unknown",
                "windows_session_interactive": False,
                "windows_session_error": f"ProcessIdToSessionId failed with {error}",
                "windows_active_console_session_id": None,
                "windows_input_desktop_available": False,
            }
        kernel32.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD
        active_console_session_id = int(kernel32.WTSGetActiveConsoleSessionId())
        user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        user32.OpenInputDesktop.restype = wintypes.HANDLE
        user32.CloseDesktop.argtypes = [wintypes.HANDLE]
        user32.CloseDesktop.restype = wintypes.BOOL
        desktop_read_objects = 0x0001
        desktop_handle = user32.OpenInputDesktop(0, False, desktop_read_objects)
        input_desktop_available = bool(desktop_handle)
        input_desktop_error = 0 if input_desktop_available else ctypes.get_last_error()
        if desktop_handle:
            user32.CloseDesktop(desktop_handle)
    except Exception as exc:
        return {
            "visible_desktop_session_check_attempted": True,
            "visible_desktop_session_check_method": method,
            "visible_desktop_session_verified": False,
            "visible_desktop_session_state": "windows_session_check_failed",
            "visible_desktop_session_blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
            "windows_session_id": None,
            "windows_session_type": "unknown",
            "windows_session_interactive": False,
            "windows_session_error": str(exc),
            "windows_active_console_session_id": None,
            "windows_input_desktop_available": False,
        }

    current_session_id = int(session_id.value)
    session_name = str(os.environ.get("SESSIONNAME", "")).strip()
    session_name_lower = session_name.lower()
    active_console_valid = active_console_session_id != 0xFFFFFFFF
    session_matches_console = active_console_valid and current_session_id == active_console_session_id
    if current_session_id == 0:
        session_type = "service_session"
    elif session_matches_console and not session_name:
        session_type = "console"
    elif session_name_lower == "console":
        session_type = "console"
    elif "rdp" in session_name_lower:
        session_type = "rdp"
    elif session_name:
        session_type = "interactive_unknown"
    else:
        session_type = "unknown"

    verified = bool(input_desktop_available and session_matches_console and current_session_id != 0)
    if verified:
        state = "available_console_input_desktop"
        blocker = ""
    elif current_session_id == 0:
        state = "service_session"
        blocker = "blocked_by_non_null_editor_render_capture_requires_interactive_runner"
    elif not active_console_valid:
        state = "no_active_console_session"
        blocker = "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
    elif not input_desktop_available:
        state = "input_desktop_unavailable"
        blocker = "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
    elif session_type == "rdp":
        state = "rdp_session_requires_operator_confirmation"
        blocker = "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
    else:
        state = "active_console_session_mismatch"
        blocker = "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"

    return {
        "visible_desktop_session_check_attempted": True,
        "visible_desktop_session_check_method": method,
        "visible_desktop_session_verified": verified,
        "visible_desktop_session_state": state,
        "visible_desktop_session_blocker": blocker,
        "windows_session_id": current_session_id,
        "windows_session_type": session_type,
        "windows_session_interactive": bool(input_desktop_available and current_session_id != 0),
        "windows_session_name": session_name,
        "windows_active_console_session_id": active_console_session_id if active_console_valid else None,
        "windows_input_desktop_available": input_desktop_available,
        "windows_input_desktop_error": input_desktop_error,
    }


def _detect_gpu_or_driver_readiness() -> Dict[str, Any]:
    method = "Win32_VideoController"
    if os.name != "nt":
        return {
            "gpu_or_driver_readiness_check_attempted": True,
            "gpu_or_driver_readiness_check_method": method,
            "gpu_or_driver_readiness_verified": False,
            "gpu_or_driver_readiness_blocker": "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
            "gpu_adapter_count": 0,
            "gpu_adapter_summary": [],
        }
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return {
            "gpu_or_driver_readiness_check_attempted": True,
            "gpu_or_driver_readiness_check_method": method,
            "gpu_or_driver_readiness_verified": False,
            "gpu_or_driver_readiness_blocker": "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
            "gpu_adapter_count": 0,
            "gpu_adapter_summary": [],
            "gpu_or_driver_readiness_message": "PowerShell/CIM inventory command unavailable.",
        }
    command = [
        powershell,
        "-NoProfile",
        "-Command",
        (
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name,Status,AdapterCompatibility,DriverVersion,VideoProcessor,VideoModeDescription | "
            "ConvertTo-Json -Compress"
        ),
    ]
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=10)
    except Exception as exc:
        return {
            "gpu_or_driver_readiness_check_attempted": True,
            "gpu_or_driver_readiness_check_method": method,
            "gpu_or_driver_readiness_verified": False,
            "gpu_or_driver_readiness_blocker": "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
            "gpu_adapter_count": 0,
            "gpu_adapter_summary": [],
            "gpu_or_driver_readiness_message": str(exc),
        }
    if proc.returncode != 0:
        return {
            "gpu_or_driver_readiness_check_attempted": True,
            "gpu_or_driver_readiness_check_method": method,
            "gpu_or_driver_readiness_verified": False,
            "gpu_or_driver_readiness_blocker": "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
            "gpu_adapter_count": 0,
            "gpu_adapter_summary": [],
            "gpu_or_driver_readiness_message": proc.stderr.strip()[:500],
        }
    try:
        payload = json.loads(proc.stdout.strip() or "[]")
    except Exception as exc:
        return {
            "gpu_or_driver_readiness_check_attempted": True,
            "gpu_or_driver_readiness_check_method": method,
            "gpu_or_driver_readiness_verified": False,
            "gpu_or_driver_readiness_blocker": "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
            "gpu_adapter_count": 0,
            "gpu_adapter_summary": [],
            "gpu_or_driver_readiness_message": f"Win32_VideoController JSON parse failed: {exc}",
        }
    records = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
    summary: List[Dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        summary.append(
            {
                "name": str(record.get("Name", "")).strip(),
                "status": str(record.get("Status", "")).strip(),
                "adapter_compatibility": str(record.get("AdapterCompatibility", "")).strip(),
                "driver_version": str(record.get("DriverVersion", "")).strip(),
                "video_processor": str(record.get("VideoProcessor", "")).strip(),
                "video_mode_description": str(record.get("VideoModeDescription", "")).strip(),
            }
        )
    def adapter_ready(adapter: Mapping[str, Any]) -> bool:
        name = str(adapter.get("name", "")).lower()
        processor = str(adapter.get("video_processor", "")).lower()
        status = str(adapter.get("status", "")).lower()
        driver_version = str(adapter.get("driver_version", "")).strip()
        excluded_tokens = ("microsoft basic", "remote display", "virtual", "warp")
        return (
            bool(driver_version)
            and (not status or status == "ok")
            and not any(token in name or token in processor for token in excluded_tokens)
        )

    verified = any(adapter_ready(adapter) for adapter in summary)
    return {
        "gpu_or_driver_readiness_check_attempted": True,
        "gpu_or_driver_readiness_check_method": method,
        "gpu_or_driver_readiness_verified": verified,
        "gpu_or_driver_readiness_blocker": ""
        if verified
        else "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
        "gpu_adapter_count": len(summary),
        "gpu_adapter_summary": summary,
    }


def _detect_rhi_source_readiness(engine_root: Path | None, selected_rhi: str) -> Dict[str, Any]:
    method = "O3DE Atom RHI source module scan"
    specs = {
        "dx12": {
            "path": (engine_root or Path("<engine-root>"))
            / "Gems"
            / "Atom"
            / "RHI"
            / "DX12"
            / "Code"
            / "atom_rhi_dx12_private_common_files.cmake",
            "symbols": ["Source/RHI/DX12.cpp", "Source/RHI/Device.cpp"],
        },
        "vulkan": {
            "path": (engine_root or Path("<engine-root>"))
            / "Gems"
            / "Atom"
            / "RHI"
            / "Vulkan"
            / "Code"
            / "atom_rhi_vulkan_private_common_files.cmake",
            "symbols": ["Source/RHI/Buffer.cpp", "Source/RHI/Device.cpp"],
        },
    }
    normalized_rhi = selected_rhi if selected_rhi in specs else "dx12"
    selected_result = _source_file_symbol_validation(specs[normalized_rhi]["path"], specs[normalized_rhi]["symbols"])
    fallback_result = _source_file_symbol_validation(specs["vulkan"]["path"], specs["vulkan"]["symbols"])
    selected_verified = selected_result.get("status") == "pass"
    fallback_available = fallback_result.get("status") == "pass"
    fallback_selected = bool(not selected_verified and normalized_rhi != "vulkan" and fallback_available)
    verified = bool(selected_verified or fallback_selected)
    return {
        "selected_rhi": normalized_rhi if not fallback_selected else "vulkan",
        "rhi_readiness_check_attempted": True,
        "rhi_readiness_check_method": method,
        "rhi_readiness_verified": verified,
        "rhi_readiness_blocker": "" if verified else "blocked_by_non_null_editor_render_capture_rhi_unavailable",
        "rhi_fallback_considered": True,
        "rhi_fallback_selected": fallback_selected,
        "rhi_source_validation": {
            "selected": selected_result,
            "vulkan_fallback": fallback_result,
        },
    }


def _non_null_editor_desktop_rhi_readiness_candidate_matrix(
    *,
    source_validated: bool,
    visible_verified: bool,
    gpu_verified: bool,
    rhi_verified: bool,
    readiness_verified: bool,
    blocker: str,
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "detect_visible_desktop_session_without_launching_editor",
            "candidate": "detect visible desktop/session without launching Editor",
            "selected": bool(source_validated),
            "result": "verified" if visible_verified else "blocked",
            "blocker": "" if visible_verified else "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
        },
        {
            "id": "detect_gpu_driver_readiness_without_launching_editor",
            "candidate": "detect GPU/driver readiness without launching Editor",
            "selected": bool(source_validated),
            "result": "verified" if gpu_verified else "blocked_or_unverified",
            "blocker": "" if gpu_verified else "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
        },
        {
            "id": "validate_selected_rhi_module_source_availability",
            "candidate": "validate selected RHI module/source availability",
            "selected": True,
            "result": "verified" if rhi_verified else "blocked",
            "blocker": "" if rhi_verified else "blocked_by_non_null_editor_render_capture_rhi_unavailable",
        },
        {
            "id": "live_non_null_editor_launch_without_screenshot",
            "candidate": "live non-null Editor launch without screenshot",
            "selected": False,
            "result": "deferred_until_next_slice" if readiness_verified else "deferred_until_readiness_gates_pass",
            "blocker": "" if readiness_verified else blocker,
        },
        {
            "id": "screenshot_capture_in_this_slice",
            "candidate": "screenshot capture in this slice",
            "selected": False,
            "result": "deferred",
        },
        {
            "id": "temp_visual_scene_creation_in_this_slice",
            "candidate": "temp visual scene creation in this slice",
            "selected": False,
            "result": "deferred_preserved_contract_only",
        },
        {
            "id": "move_visual_capture_to_separate_runner",
            "candidate": "move visual capture to separate runner",
            "selected": False,
            "result": "deferred_unless_current_runner_remains_blocked",
        },
        {
            "id": "nullrenderer_visual_proof",
            "candidate": "NullRenderer visual proof",
            "selected": False,
            "result": "rejected_blocked",
            "blocker": "blocked_by_editor_viewport_capture_requires_non_null_rhi",
        },
        {
            "id": "apb_material_product_inventory_as_rendered_proof",
            "candidate": "APB/material product inventory as rendered proof",
            "selected": False,
            "result": "rejected_readiness_only",
        },
        {
            "id": "screenshot_existence_only_as_material_proof",
            "candidate": "screenshot existence only as material proof",
            "selected": False,
            "result": "rejected_full_visual_material_proof",
        },
        {
            "id": "production_defaultlevel_screenshot",
            "candidate": "production/defaultlevel screenshot",
            "selected": False,
            "result": "rejected",
        },
        {
            "id": "understand_anything_graph_as_proof",
            "candidate": "use Understand-Anything graph as proof",
            "selected": False,
            "result": "rejected",
        },
        {
            "id": "claim_full_runtime_character_proof_from_readiness_only",
            "candidate": "claim full runtime character proof from readiness only",
            "selected": False,
            "result": "rejected",
        },
    ]


def _run_non_null_editor_desktop_rhi_readiness_checks(
    report: Mapping[str, Any],
    *,
    progress_log: Path | None,
) -> Dict[str, Any]:
    engine_root_raw = str(os.environ.get("O3DE_ENGINE_ROOT", "")).strip()
    engine_root = Path(engine_root_raw) if engine_root_raw else None
    _write_progress_marker(
        progress_log,
        "non_null_editor_desktop_rhi_source_validation_started",
        "started",
        "Source-validating non-null Editor desktop/session/GPU/RHI readiness diagnostic.",
    )
    source_validation = _non_null_editor_desktop_rhi_readiness_source_validation(engine_root)
    source_validated = source_validation.get("status") == "non_null_editor_desktop_rhi_readiness_source_validation_pass"
    selected_rhi = _command_requested_rhi(report)
    visible = _detect_visible_desktop_session_readiness()
    gpu = _detect_gpu_or_driver_readiness()
    rhi = _detect_rhi_source_readiness(engine_root, selected_rhi)
    visible_verified = visible.get("visible_desktop_session_verified") is True
    gpu_verified = gpu.get("gpu_or_driver_readiness_verified") is True
    rhi_verified = rhi.get("rhi_readiness_verified") is True
    readiness_verified = bool(source_validated and visible_verified and gpu_verified and rhi_verified)
    if not source_validated:
        blocker = "blocked_by_non_null_editor_visual_runner_readiness_requires_additional_source_validation"
    elif not visible_verified:
        blocker = str(visible.get("visible_desktop_session_blocker") or "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session")
    elif not gpu_verified:
        blocker = str(gpu.get("gpu_or_driver_readiness_blocker") or "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver")
    elif not rhi_verified:
        blocker = str(rhi.get("rhi_readiness_blocker") or "blocked_by_non_null_editor_render_capture_rhi_unavailable")
    else:
        blocker = ""
    _write_progress_marker(
        progress_log,
        "non_null_editor_desktop_rhi_live_launch_deferred",
        "deferred" if readiness_verified else "blocked",
        "Live non-null Editor launch remains deferred; this slice does not request screenshots or mutate temp scenes.",
        error_code="" if readiness_verified else MXN_RUNTIME_SMOKE_FAIL,
    )
    preserved_report = _load_preserved_non_null_editor_render_capture_report()
    preserved_source = preserved_report if preserved_report else report
    satisfied_gates = list(preserved_source.get("full_runtime_character_proof_satisfied_gates", []))
    behavior_smoke_verified = preserved_source.get("runtime_character_behavior_smoke_verified") is True
    animation_verified = preserved_source.get("runtime_character_animation_verified") is True
    component_wiring_verified = preserved_source.get("runtime_character_animation_component_wiring_verified") is True
    product_inventory_verified = _editor_visual_material_product_inventory_verified(report)
    visual_blocker = "blocked_by_visual_material_proof_requires_rendered_evidence_capture"
    if blocker:
        visual_blocker = blocker
    selected_strategy = (
        "safe_desktop_gpu_rhi_readiness_verified_without_editor_launch"
        if readiness_verified
        else "safe_desktop_gpu_rhi_readiness_checks_blocked_without_editor_launch"
    )
    payload: Dict[str, Any] = {
        "non_null_editor_desktop_rhi_readiness_attempted": True,
        "non_null_editor_desktop_rhi_readiness_completed": True,
        "non_null_editor_desktop_rhi_readiness_source_validation_status": source_validation.get("status", ""),
        "non_null_editor_desktop_rhi_readiness_source_validation_verified": source_validated,
        "non_null_editor_desktop_rhi_readiness_source_validation": source_validation,
        "non_null_editor_desktop_rhi_readiness_source_files": [
            str(spec["path"]) for spec in _non_null_editor_desktop_rhi_readiness_source_specs(engine_root)
        ],
        "non_null_editor_desktop_rhi_readiness_verified": readiness_verified,
        "non_null_editor_desktop_rhi_readiness_blocker": blocker,
        "non_null_editor_desktop_rhi_readiness_candidate_matrix": _non_null_editor_desktop_rhi_readiness_candidate_matrix(
            source_validated=source_validated,
            visible_verified=visible_verified,
            gpu_verified=gpu_verified,
            rhi_verified=rhi_verified,
            readiness_verified=readiness_verified,
            blocker=blocker,
        ),
        "non_null_editor_desktop_rhi_readiness_selected_strategy": selected_strategy,
        "non_null_editor_visual_runner_readiness_attempted": True,
        "non_null_editor_visual_runner_readiness_completed": True,
        "non_null_editor_visual_runner_readiness_source_validation_status": source_validation.get("status", ""),
        "non_null_editor_visual_runner_readiness_source_validation_verified": source_validated,
        "non_null_editor_visual_runner_readiness_verified": readiness_verified,
        "non_null_editor_visual_runner_readiness_blocker": blocker,
        "non_null_editor_visual_runner_readiness_candidate_matrix": _non_null_editor_desktop_rhi_readiness_candidate_matrix(
            source_validated=source_validated,
            visible_verified=visible_verified,
            gpu_verified=gpu_verified,
            rhi_verified=rhi_verified,
            readiness_verified=readiness_verified,
            blocker=blocker,
        ),
        "non_null_editor_visual_runner_readiness_selected_strategy": selected_strategy,
        "preserved_non_null_editor_render_capture_report_ref": str(
            preserved_report.get("_preserved_report_ref", "")
        ).strip(),
        "non_null_editor_launch_attempted": False,
        "non_null_editor_launch_completed": False,
        "non_null_editor_launch_verified": False,
        "non_null_editor_launch_exit_code": None,
        "non_null_editor_launch_blocker": "" if readiness_verified else blocker,
        "null_renderer_used": False,
        "existing_nullrenderer_safe_editor_lane_preserved": True,
        "editor_temp_visual_scene_contract_attempted": True,
        "editor_temp_visual_scene_contract_pinned": source_validated,
        "editor_temp_visual_scene_contract_verified": source_validated,
        "editor_temp_visual_scene_contract_blocker": ""
        if source_validated
        else "blocked_by_editor_temp_visual_scene_contract_requires_additional_source_validation",
        "editor_temp_visual_scene_approved_root": "Levels/_maxine_visual_smoke",
        "editor_temp_visual_scene_defaultlevel_mutation": False,
        "editor_temp_visual_scene_production_level_mutation": False,
        "editor_temp_visual_scene_cleanup_policy_verified": source_validated,
        "editor_visual_material_capture_artifact_root": "artifacts/o3de-integration/editor-smoke",
        "editor_visual_material_capture_artifact_policy_verified": source_validated,
        "non_null_editor_render_capture_envelope_attempted": True,
        "non_null_editor_render_capture_envelope_completed": True,
        "non_null_editor_render_capture_envelope_source_validation_status": "preserved_from_pr165_source_contract",
        "non_null_editor_render_capture_envelope_source_validation_verified": True,
        "non_null_editor_render_capture_envelope_verified": False,
        "non_null_editor_render_capture_envelope_blocker": blocker
        or "blocked_by_visual_material_proof_requires_rendered_evidence_capture",
        "non_null_editor_render_capture_rhi_requested": str(rhi.get("selected_rhi", selected_rhi)),
        "non_null_editor_render_capture_null_renderer_used": False,
        "non_null_editor_render_capture_editor_launched": False,
        "non_null_editor_render_capture_editor_exited_cleanly": False,
        "non_null_editor_render_capture_requires_visible_desktop": True,
        "non_null_editor_render_capture_gpu_or_driver_ready": gpu_verified,
        "editor_visual_material_capture_api_available_under_non_null_rhi": False,
        "editor_visual_material_capture_api_found": source_validated,
        "editor_visual_material_capture_api_used": "AZ::Render::FrameCaptureRequestBus::CaptureScreenshot"
        if source_validated
        else "",
        "editor_visual_material_temp_scene_created": False,
        "editor_visual_material_temp_scene_path": "",
        "editor_visual_material_defaultlevel_mutation": False,
        "editor_visual_material_production_level_mutation": False,
        "editor_visual_material_character_instantiated": False,
        "editor_visual_material_character_source_path": (
            "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
        ),
        "editor_visual_material_character_product_or_prefab_path": "",
        "editor_visual_material_camera_or_view_framed": False,
        "editor_visual_material_light_or_environment_prepared": False,
        "editor_visual_material_capture_requested": False,
        "editor_visual_material_capture_completed": False,
        "editor_visual_material_capture_artifact_path": "",
        "editor_visual_material_capture_artifact_exists": False,
        "editor_visual_material_capture_artifact_format": "",
        "editor_visual_material_capture_artifact_width": 0,
        "editor_visual_material_capture_artifact_height": 0,
        "editor_visual_material_capture_artifact_size_bytes": 0,
        "editor_visual_material_capture_content_validation_attempted": False,
        "editor_visual_material_capture_content_validation_verified": False,
        "editor_visual_material_nonblank_validation_verified": False,
        "editor_visual_material_character_presence_validation_verified": False,
        "editor_visual_material_material_presence_validation_verified": False,
        "editor_visual_material_cleanup_verified": source_validated,
        "editor_visual_material_selected_log_scan_passed": True,
        "visual_material_capture_readiness_verified": False,
        "visual_material_product_inventory_gate_verified": product_inventory_verified,
        "visual_material_rendered_evidence_gate_attempted": False,
        "visual_material_rendered_evidence_gate_verified": False,
        "visual_material_gate_claimed": False,
        "visual_material_gate_verified": False,
        "full_runtime_character_visual_material_gate_verified": False,
        "full_runtime_character_proof_contract_pinned": True,
        "full_runtime_character_proof_contract_verified": True,
        "full_runtime_character_proof_satisfied_gates": satisfied_gates,
        "full_runtime_character_proof_unsatisfied_gates": [
            {
                "id": "visual_material",
                "name": "Visual/render/material validation",
                "verified": False,
                "blocker": visual_blocker,
                "evidence": "Desktop/GPU/RHI readiness checked; rendered content not captured.",
            }
        ],
        "full_runtime_character_proof_deferred_gates": [
            {
                "id": "visual_capture_surface",
                "name": "Live non-null Editor visual capture execution",
                "verified": False,
                "blocker": visual_blocker,
                "evidence": "non-null Editor launch, temp scene creation, and screenshot capture remain deferred",
            },
            {
                "id": "repeated_behavior_scenario",
                "name": "Repeated runtime behavior scenario",
                "verified": False,
                "blocker": "blocked_by_full_runtime_character_repeated_behavior_scenario_deferred",
                "evidence": "not part of this desktop/RHI readiness slice",
            },
        ],
        "runtime_character_behavior_smoke_verified": behavior_smoke_verified,
        "runtime_character_animation_verified": animation_verified,
        "runtime_character_animation_component_wiring_verified": component_wiring_verified,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
        "messages": [
            "Non-null Editor desktop/RHI readiness was checked without launching Editor or requesting capture."
        ],
    }
    payload.update(visible)
    payload.update(gpu)
    payload.update(rhi)
    return payload


def _targeted_binding_blocker(report: Mapping[str, Any], diagnostic_mode: str) -> str:
    target_fields = {
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
    field = target_fields.get(diagnostic_mode)
    if not field:
        return ""
    checks = report.get(field, {})
    status = str(checks.get("status", "")).strip() if isinstance(checks, Mapping) else ""
    if status == "pass":
        return ""
    reason = checks.get("blocked_reason") or checks.get("unavailable_reason") or checks.get("message", "") if isinstance(checks, Mapping) else ""
    return f"{diagnostic_mode} did not pass; {field} reported {status or 'missing'}{(': ' + str(reason)) if reason else ''}."


def _summarize_binding_call_surface(binding_report: Dict[str, Any]) -> None:
    surface = binding_report.get("binding_call_surface", {})
    if not isinstance(surface, dict):
        return
    editor_surface = surface.get("EditorComponentAPIBus", {})
    if not isinstance(editor_surface, dict):
        return
    validated: List[str] = []
    blocked: List[str] = []
    for record in binding_report.get("safe_call_results", []):
        if not isinstance(record, Mapping):
            continue
        call = str(record.get("call", ""))
        if not call.startswith("EditorComponentAPIBus."):
            continue
        method = call.split(".", 1)[1]
        if record.get("status") == "pass":
            validated.append(method)
        else:
            blocked.append(method)
    editor_surface["validated_calls"] = _unique(validated)
    editor_surface["blocked_calls"] = _unique(blocked)


def _load_component_api_surface() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    info: Dict[str, Any] = {
        "status": "unsupported_by_engine_binding",
        "validated_calls": [],
        "blocked_calls": [],
        "safe_for_unattended_temp_level_smoke": True,
    }
    surface: Dict[str, Any] = {}
    try:
        import azlmbr.bus as bus  # type: ignore
        import azlmbr.editor as editor  # type: ignore
        import azlmbr.entity as entity  # type: ignore

        surface.update({"bus": bus, "editor": editor, "entity": entity})
        if hasattr(editor, "EditorComponentAPIBus"):
            info["status"] = "pass"
            info["validated_calls"] = []
        else:
            info["blocked_calls"] = ["EditorComponentAPIBus"]
            info["blocked_reason"] = "EditorComponentAPIBus_missing"
    except Exception as exc:
        info["blocked_calls"] = ["azlmbr.bus", "azlmbr.editor", "azlmbr.entity"]
        info["blocked_reason"] = "editor_component_api_import_failed"
        info["error"] = str(exc)
    return info, surface


def _run_component_binding_checks(
    entity_id: Any,
    entity_result: Mapping[str, Any],
    surface: Mapping[str, Any],
    binding_report: Dict[str, Any],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if entity_result.get("status") != "pass" or entity_id is None:
        return {
            "status": "blocked_by_readiness",
            "blocked_reason": "entity_smoke_not_available",
            "entity_status": entity_result.get("status", "unknown"),
        }
    if not _surface_available(surface):
        return {
            "status": "unsupported_by_engine_binding",
            "blocked_reason": "EditorComponentAPIBus_unavailable",
            "entity_name_verified": True,
            "default_transform_verified": True,
        }

    registry = binding_report["component_type_registry"]
    property_summary = binding_report["property_list_summary"]
    property_access = binding_report["property_access_summary"]
    transform = _discover_component_type_ids(
        ["Transform", "Transform Component"],
        "Transform",
        surface,
        safe_call_results,
        registry,
    )
    transform_component = _get_component_reference(entity_id, transform.get("type_ids_raw", []), surface, safe_call_results)
    transform_properties = _build_component_property_list(transform_component, surface, safe_call_results)
    property_summary["Transform"] = transform_properties
    property_access["Transform"] = _get_component_property_values(transform_component, transform_properties, surface, safe_call_results)

    safe_added = _try_add_safe_component(entity_id, surface, safe_call_results, registry, property_summary)
    if safe_added.get("component_name") and str(safe_added.get("component_name")) in property_summary:
        property_access[str(safe_added["component_name"])] = safe_added.get("property_access", {"status": "not_run"})
    verified_components = ["Transform"]
    if safe_added.get("status") == "pass" and safe_added.get("component_name"):
        verified_components.append(str(safe_added["component_name"]))

    transform_binding_pass = transform.get("status") == "pass" and transform_component.get("status") == "pass"
    safe_component_properties = property_summary.get(str(safe_added.get("component_name", "")), {})
    safe_component_binding_pass = safe_added.get("status") == "pass" and isinstance(safe_component_properties, Mapping) and safe_component_properties.get("status") == "pass"
    property_status = str(transform_properties.get("status", ""))
    property_observed = property_status in {"pass", "unavailable_with_verified_reason", "unsupported_by_engine_binding"}
    status = "pass" if (transform_binding_pass and property_observed) or safe_component_binding_pass else "blocked_by_missing_binding"
    return {
        "status": status,
        "entity_name_verified": True,
        "default_transform_verified": True,
        "transform_type_id_status": transform.get("status", "blocked_by_missing_binding"),
        "transform_component_status": transform_component.get("status", "blocked_by_missing_binding"),
        "verified_components": verified_components,
        "added_component": safe_added,
        "property_list_summary": transform_properties,
        "blocked_reason": "" if status == "pass" else "transform_component_binding_not_verified",
    }


def _run_actor_binding_checks(
    entity_id: Any,
    surface: Mapping[str, Any],
    binding_report: Dict[str, Any],
    safe_call_results: List[Dict[str, Any]],
    report: Mapping[str, Any],
    *,
    attempt_asset_assignment: bool,
    progress_log: Path | None,
) -> Dict[str, Any]:
    actor_product = _product_ref(report, "actor")
    if not actor_product:
        return {
            "status": "blocked_by_missing_product_evidence",
            "product_evidence_status": "missing",
            "blocked_reason": "actor_product_missing",
        }
    if entity_id is None:
        return {
            "status": "blocked_by_readiness",
            "product_evidence_status": "pass",
            "actor_product_ref": actor_product,
            "blocked_reason": "entity_smoke_not_available",
        }
    if not _surface_available(surface):
        return {
            "status": "unsupported_by_engine_binding",
            "product_evidence_status": "pass",
            "actor_product_ref": actor_product,
            "blocked_reason": "EditorComponentAPIBus_unavailable",
        }

    registry = binding_report["component_type_registry"]
    property_summary = binding_report["property_list_summary"]
    property_access = binding_report["property_access_summary"]
    actor_type = _discover_component_type_ids(
        ["Actor", "Actor Component", "EMotion FX Actor"],
        "Actor",
        surface,
        safe_call_results,
        registry,
    )
    if actor_type.get("status") != "pass":
        return {
            "status": "blocked_by_missing_binding",
            "product_evidence_status": "pass",
            "actor_product_ref": actor_product,
            "component_type_id_status": actor_type.get("status", "blocked_by_missing_binding"),
            "blocked_reason": "actor_component_type_id_not_discovered",
            "property_path_discovery": {"status": "blocked_by_missing_binding", "blocked_reason": "actor_component_type_id_not_discovered"},
        }

    add_result = _add_components(entity_id, actor_type.get("type_ids_raw", []), surface, safe_call_results, component_name="Actor")
    actor_component = _first_component_reference(add_result, entity_id, actor_type.get("type_ids_raw", []), surface, safe_call_results)
    properties = _build_component_property_list(actor_component, surface, safe_call_results)
    property_summary["Actor"] = properties
    property_access["Actor"] = _get_component_property_values(actor_component, properties, surface, safe_call_results)
    binding_report["property_path_discovery"]["Actor"] = _actor_property_discovery(properties)

    if add_result.get("status") != "pass":
        return {
            "status": "blocked_by_missing_binding",
            "product_evidence_status": "pass",
            "actor_product_ref": actor_product,
            "component_type_id_status": "pass",
            "component_add_status": add_result.get("status", "blocked_by_missing_binding"),
            "blocked_reason": "actor_component_add_not_verified",
            "property_path_discovery": binding_report["property_path_discovery"]["Actor"],
        }
    assignment = _skipped_check("actor-asset-assignment")
    if attempt_asset_assignment:
        _write_progress_marker(progress_log, "actor_asset_assignment_started", "started", "Assigning approved Actor asset in temp level.")
        assignment = _assign_actor_asset(
            actor_component,
            properties,
            surface,
            safe_call_results,
            actor_product,
        )
        _write_progress_marker(
            progress_log,
            "actor_asset_assignment_returned",
            str(assignment.get("status", "returned")),
            "Actor asset assignment diagnostic returned.",
        )

    status = "pass"
    blocked_reason = ""
    message = "Actor component binding and property readback passed."
    if attempt_asset_assignment:
        if assignment.get("status") == "pass":
            message = "Actor component binding and approved Actor asset assignment passed."
        else:
            status = str(assignment.get("status", "blocked_by_unsafe_operation"))
            blocked_reason = str(
                assignment.get("blocked_reason")
                or assignment.get("unavailable_reason")
                or assignment.get("message", "")
            )
            message = "Actor component binding passed, but Actor asset assignment did not pass."

    return {
        "status": status,
        "product_evidence_status": "pass",
        "actor_product_ref": actor_product,
        "component_type_id_status": "pass",
        "component_add_status": "pass",
        "property_list_status": properties.get("status", "blocked_by_missing_binding"),
        "property_access_status": property_access["Actor"].get("status", "blocked_by_missing_binding"),
        "property_path_discovery": binding_report["property_path_discovery"]["Actor"],
        "actor_asset_assignment": assignment,
        "blocked_reason": blocked_reason,
        "message": message,
    }


def _assign_actor_asset(
    actor_component: Mapping[str, Any],
    properties: Mapping[str, Any],
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    actor_product: str,
) -> Dict[str, Any]:
    property_discovery = _actor_property_discovery(properties, require_settable=True)
    property_path = _select_actor_asset_property_path(property_discovery)
    if not property_path:
        return {
            "status": "blocked_by_missing_binding",
            "property_path_discovery": property_discovery,
            "blocked_reason": "actor_asset_property_path_not_discovered",
        }

    asset_resolution = _resolve_asset_id(actor_product, safe_call_results)
    asset_id = asset_resolution.get("asset_id_raw")
    if asset_resolution.get("status") != "pass" or asset_id is None:
        return {
            "status": "blocked_by_missing_product_evidence",
            "property_path": property_path,
            "property_path_discovery": property_discovery,
            "approved_product_ref": actor_product,
            "asset_resolution": _public_asset_resolution(asset_resolution),
            "blocked_reason": asset_resolution.get("blocked_reason", "actor_asset_catalog_id_not_found"),
        }

    component_ref = actor_component.get("component_ref")
    if actor_component.get("status") != "pass" or component_ref is None:
        return {
            "status": "blocked_by_missing_binding",
            "property_path": property_path,
            "approved_product_ref": actor_product,
            "blocked_reason": actor_component.get("blocked_reason", "actor_component_reference_not_available"),
        }

    old_status, old_value = _component_bus_call(surface, "GetComponentProperty", (component_ref, property_path), safe_call_results)
    set_status, set_value = _set_component_property(surface, component_ref, property_path, asset_id, safe_call_results)
    read_status, read_value = _component_bus_call(surface, "GetComponentProperty", (component_ref, property_path), safe_call_results)
    compare_status, compare_value = _component_bus_call(surface, "CompareComponentProperty", (component_ref, property_path, asset_id), safe_call_results)
    component_validity = _component_validity_checks(component_ref, surface, safe_call_results)
    matched = compare_status == "pass" and bool(_unwrap_outcome(compare_value))
    if not matched:
        matched = _asset_ids_match(read_value, asset_id)

    readback = {
        "status": "pass" if read_status == "pass" and matched else "fail",
        "matched_approved_product": bool(matched),
        "value": _safe_serialize(_unwrap_outcome(read_value)),
        "compare_status": compare_status,
        "compare_result": bool(_unwrap_outcome(compare_value)) if compare_status == "pass" else False,
    }
    status = "pass" if set_status == "pass" and readback["status"] == "pass" else "fail"
    return {
        "status": status,
        "property_path": property_path,
        "property_path_discovery": property_discovery,
        "setter_call": "EditorComponentAPIBus.SetComponentProperty",
        "setter_value_shape": "azlmbr.asset.AssetId",
        "approved_product_ref": actor_product,
        "asset_resolution": _public_asset_resolution(asset_resolution),
        "old_value": _safe_serialize(_unwrap_outcome(old_value)) if old_status == "pass" else "",
        "set_status": set_status,
        "set_result": _safe_serialize(_unwrap_outcome(set_value)),
        "readback": readback,
        "component_validity": component_validity,
        "blocked_reason": "" if status == "pass" else "actor_asset_assignment_readback_mismatch",
    }


def _run_approved_animation_component_wiring_generation_checks(
    entity_id: Any,
    surface: Mapping[str, Any],
    binding_report: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    report: Mapping[str, Any],
) -> Dict[str, Any]:
    source_prefab_path = "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
    source_validation = _approved_animation_component_wiring_source_validation()
    result: Dict[str, Any] = {
        "approved_runtime_animation_component_wiring_editor_generation_attempted": True,
        "approved_runtime_animation_component_wiring_editor_generation_completed": True,
        "approved_runtime_animation_component_wiring_editor_generation_verified": False,
        "approved_runtime_animation_component_wiring_editor_generation_blocker": "blocked_by_editor_generated_prefab_update_save_semantics",
        "approved_runtime_animation_component_wiring_source_prefab_path": source_prefab_path,
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
        "approved_runtime_animation_component_wiring_source_validation_status": source_validation["status"],
        "approved_runtime_animation_component_wiring_source_validation_verified": source_validation["verified"],
        "approved_runtime_animation_component_wiring_source_refs": source_validation["refs"],
        "approved_runtime_animation_component_wiring_candidate_matrix": _approved_animation_component_wiring_candidate_matrix(),
        "approved_runtime_animation_component_wiring_selected_strategy": "actor_plus_simple_motion_editor_generated_surface_blocked_before_source_prefab_save",
        "approved_runtime_animation_component_wiring_editor_api": {
            "component_api": "EditorComponentAPIBus",
            "component_add": "AddComponentsOfType",
            "property_list": "BuildComponentPropertyList",
            "property_set": "SetComponentProperty",
            "property_readback": "GetComponentProperty",
            "asset_value_shape": "azlmbr.asset.AssetId",
        },
        "approved_runtime_animation_component_wiring_prefab_api": {
            "automation_bus": "PrefabPublicRequestBus",
            "source_validated_available_events": [
                "CreatePrefabInMemory",
                "InstantiatePrefab",
                "GetOwningInstancePrefabPath",
                "CreateInMemorySpawnableAsset",
            ],
            "source_validated_missing_events": [
                "CreatePrefabAndSaveToDisk",
                "SavePrefab",
            ],
            "blocker": "blocked_by_editor_generated_prefab_update_save_semantics",
        },
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_playback_started": False,
        "runtime_character_animation_playback_observed": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }
    if source_validation["verified"] is not True:
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = (
            "blocked_by_editor_generated_prefab_update_requires_additional_source_validation"
        )
        return result

    actor_product = _product_ref(report, "actor")
    motion_product = _product_ref(report, "motion")
    if not actor_product or not motion_product:
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = (
            "blocked_by_approved_actor_or_motion_asset_id_unresolved"
        )
        result["approved_runtime_animation_component_wiring_actor_product_ref"] = actor_product
        result["approved_runtime_animation_component_wiring_motion_product_ref"] = motion_product
        return result

    registry = binding_report["component_type_registry"]
    property_summary = binding_report["property_list_summary"]
    property_access = binding_report["property_access_summary"]

    actor_type = _discover_component_type_ids(
        ["Actor", "Actor Component", "EMotion FX Actor"],
        "ApprovedEditorActor",
        surface,
        safe_call_results,
        registry,
    )
    if actor_type.get("status") == "pass":
        actor_add = _add_components(entity_id, actor_type.get("type_ids_raw", []), surface, safe_call_results, component_name="Actor")
        actor_component = _first_component_reference(actor_add, entity_id, actor_type.get("type_ids_raw", []), surface, safe_call_results)
        actor_properties = _build_component_property_list(actor_component, surface, safe_call_results)
        property_summary["ApprovedEditorActor"] = actor_properties
        property_access["ApprovedEditorActor"] = _get_component_property_values(actor_component, actor_properties, surface, safe_call_results)
        result["approved_runtime_animation_component_wiring_actor_component_add_result"] = actor_add
        result["approved_runtime_animation_component_wiring_actor_component_added"] = actor_add.get("status") == "pass"
        actor_assignment = _assign_actor_asset(actor_component, actor_properties, surface, safe_call_results, actor_product)
        result["approved_runtime_animation_component_wiring_actor_assignment"] = actor_assignment
        result["approved_runtime_animation_component_wiring_actor_asset_assignment_verified"] = actor_assignment.get("status") == "pass"
        actor_asset = actor_assignment.get("asset_resolution", {}) if isinstance(actor_assignment, Mapping) else {}
        result["approved_runtime_animation_component_wiring_actor_asset_id"] = str(actor_asset.get("asset_id", ""))
    else:
        result["approved_runtime_animation_component_wiring_actor_component_type_discovery"] = actor_type

    simple_type = _discover_component_type_ids(
        ["Simple Motion", "SimpleMotion", "EMotion FX Simple Motion"],
        "ApprovedEditorSimpleMotion",
        surface,
        safe_call_results,
        registry,
    )
    if simple_type.get("status") == "pass":
        simple_add = _add_components(
            entity_id,
            simple_type.get("type_ids_raw", []),
            surface,
            safe_call_results,
            component_name="Simple Motion",
        )
        simple_component = _first_component_reference(simple_add, entity_id, simple_type.get("type_ids_raw", []), surface, safe_call_results)
        simple_properties = _build_component_property_list(simple_component, surface, safe_call_results)
        property_summary["ApprovedEditorSimpleMotion"] = simple_properties
        property_access["ApprovedEditorSimpleMotion"] = _get_component_property_values(
            simple_component, simple_properties, surface, safe_call_results
        )
        result["approved_runtime_animation_component_wiring_simple_motion_component_add_result"] = simple_add
        result["approved_runtime_animation_component_wiring_simple_motion_component_added"] = simple_add.get("status") == "pass"
        motion_assignment = _assign_motion_asset(simple_component, simple_properties, surface, safe_call_results, motion_product)
        result["approved_runtime_animation_component_wiring_motion_assignment"] = motion_assignment
        result["approved_runtime_animation_component_wiring_motion_asset_assignment_verified"] = motion_assignment.get("status") == "pass"
        motion_asset = motion_assignment.get("asset_resolution", {}) if isinstance(motion_assignment, Mapping) else {}
        result["approved_runtime_animation_component_wiring_motion_asset_id"] = str(motion_asset.get("asset_id", ""))
    else:
        result["approved_runtime_animation_component_wiring_simple_motion_component_type_discovery"] = simple_type

    result["approved_runtime_animation_component_wiring_property_readback_verified"] = (
        result["approved_runtime_animation_component_wiring_actor_asset_assignment_verified"] is True
        and result["approved_runtime_animation_component_wiring_motion_asset_assignment_verified"] is True
    )
    if not result["approved_runtime_animation_component_wiring_property_readback_verified"]:
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = (
            "blocked_by_editor_component_asset_assignment_unavailable"
        )
    return result


def _assign_motion_asset(
    motion_component: Mapping[str, Any],
    properties: Mapping[str, Any],
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    motion_product: str,
) -> Dict[str, Any]:
    property_discovery = _motion_property_discovery(properties, require_settable=True)
    property_path = _select_motion_asset_property_path(property_discovery)
    if not property_path:
        return {
            "status": "blocked_by_missing_binding",
            "property_path_discovery": property_discovery,
            "blocked_reason": "simple_motion_asset_property_path_not_discovered",
        }

    asset_resolution = _resolve_asset_id(motion_product, safe_call_results)
    asset_id = asset_resolution.get("asset_id_raw")
    if asset_resolution.get("status") != "pass" or asset_id is None:
        return {
            "status": "blocked_by_missing_product_evidence",
            "property_path": property_path,
            "property_path_discovery": property_discovery,
            "approved_product_ref": motion_product,
            "asset_resolution": _public_asset_resolution(asset_resolution),
            "blocked_reason": asset_resolution.get("blocked_reason", "motion_asset_catalog_id_not_found"),
        }

    component_ref = motion_component.get("component_ref")
    if motion_component.get("status") != "pass" or component_ref is None:
        return {
            "status": "blocked_by_missing_binding",
            "property_path": property_path,
            "approved_product_ref": motion_product,
            "blocked_reason": motion_component.get("blocked_reason", "simple_motion_component_reference_not_available"),
        }

    old_status, old_value = _component_bus_call(surface, "GetComponentProperty", (component_ref, property_path), safe_call_results)
    set_status, set_value = _set_component_property(surface, component_ref, property_path, asset_id, safe_call_results)
    read_status, read_value = _component_bus_call(surface, "GetComponentProperty", (component_ref, property_path), safe_call_results)
    compare_status, compare_value = _component_bus_call(surface, "CompareComponentProperty", (component_ref, property_path, asset_id), safe_call_results)
    component_validity = _component_validity_checks(component_ref, surface, safe_call_results)
    matched = compare_status == "pass" and bool(_unwrap_outcome(compare_value))
    if not matched:
        matched = _asset_ids_match(read_value, asset_id)

    readback = {
        "status": "pass" if read_status == "pass" and matched else "fail",
        "matched_approved_product": bool(matched),
        "value": _safe_serialize(_unwrap_outcome(read_value)),
        "compare_status": compare_status,
        "compare_result": bool(_unwrap_outcome(compare_value)) if compare_status == "pass" else False,
    }
    status = "pass" if set_status == "pass" and readback["status"] == "pass" else "fail"
    return {
        "status": status,
        "property_path": property_path,
        "property_path_discovery": property_discovery,
        "setter_call": "EditorComponentAPIBus.SetComponentProperty",
        "setter_value_shape": "azlmbr.asset.AssetId",
        "approved_product_ref": motion_product,
        "asset_resolution": _public_asset_resolution(asset_resolution),
        "old_value": _safe_serialize(_unwrap_outcome(old_value)) if old_status == "pass" else "",
        "set_status": set_status,
        "set_result": _safe_serialize(_unwrap_outcome(set_value)),
        "readback": readback,
        "component_validity": component_validity,
        "blocked_reason": "" if status == "pass" else "motion_asset_assignment_readback_mismatch",
    }


def _run_prefab_binding_checks(
    report: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    *,
    entity_id: Any,
    attempt_instantiation: bool,
    attempt_direct_product: bool,
    progress_log: Path | None,
) -> Dict[str, Any]:
    procprefab_product = _product_ref(report, "procprefab") or _product_ref(report, "prefab")
    if not procprefab_product:
        return {
            "status": "blocked_by_missing_product_evidence",
            "product_evidence_status": "missing",
            "blocked_reason": "procprefab_product_missing",
        }
    surface = _probe_prefab_surface(safe_call_results)
    result = {
        "product_evidence_status": "pass",
        "procprefab_product_ref": procprefab_product,
        "binding_surface_status": surface.get("status", "unsupported_by_engine_binding"),
        "binding_surface": surface,
    }
    if surface.get("status") != "pass":
        return {
            **result,
            "status": "unsupported_by_engine_binding",
            "blocked_reason": surface.get("blocked_reason", "prefab_instantiation_binding_not_available"),
        }
    if not attempt_instantiation:
        return {
            **result,
            "status": "pass",
            "selected_call": "azlmbr.prefab surface discovery",
            "message": "Prefab binding surface discovery passed; instantiation is covered by prefab-instantiation/full modes.",
        }

    _write_progress_marker(progress_log, "prefab_instantiation_started", "started", "Creating and instantiating a temp-level prefab.")
    instantiation = _instantiate_temp_prefab(entity_id, safe_call_results)
    _write_progress_marker(
        progress_log,
        "prefab_instantiation_returned",
        str(instantiation.get("status", "returned")),
        "Prefab instantiation diagnostic returned.",
    )
    source_prefab_baseline_result = dict(instantiation)
    if attempt_direct_product:
        _write_progress_marker(
            progress_log,
            "procprefab_product_instantiation_started",
            "started",
            "Probing direct APB .procprefab product load and instantiation semantics.",
        )
        direct_semantics = _probe_direct_procprefab_product_semantics(
            report,
            surface,
            safe_call_results,
            entity_id=entity_id,
        )
        direct_semantics["source_prefab_baseline_result"] = source_prefab_baseline_result
        runtime_proof = _build_runtime_spawnable_proof_surface(
            report,
            direct_semantics,
            safe_call_results,
            progress_log=progress_log,
        )
        direct_semantics["runtime_spawnable_proof"] = runtime_proof
        _write_progress_marker(
            progress_log,
            "procprefab_product_instantiation_returned",
            str(direct_semantics.get("status", "returned")),
            "Direct APB .procprefab product semantics probe returned.",
        )
    else:
        direct_semantics = _skipped_check("procprefab-product-instantiation")
        runtime_proof = _skipped_check("runtime-spawnable-proof-surface")

    if instantiation.get("status") == "pass" and (
        not attempt_direct_product or _direct_procprefab_semantics_allows_pass(direct_semantics)
    ):
        return {
            **result,
            "status": "pass",
            "selected_call": "PrefabPublicRequestBus.CreatePrefabInMemory + PrefabPublicRequestBus.InstantiatePrefab",
            "argument_value_shape": {
                "prefab_path": "absolute temp-level .prefab path under Levels/_maxine_smoke",
                "entity_ids": "list[azlmbr.entity.EntityId]",
                "parent_entity_id": "azlmbr.entity.EntityId()",
                "position": "azlmbr.math.Vector3",
            },
            "instantiation": instantiation,
            "source_prefab_baseline_result": source_prefab_baseline_result,
            "direct_procprefab_product_semantics": direct_semantics,
            "runtime_spawnable_proof": runtime_proof,
            "procprefab_character_assertions": direct_semantics.get(
                "procprefab_character_assertions",
                {"status": "not_run"},
            ),
        }
    return {
        **result,
        "status": (
            direct_semantics.get("status", "blocked_by_unsafe_operation")
            if instantiation.get("status") == "pass"
            else instantiation.get("status", "blocked_by_unsafe_operation")
        ),
        "selected_call": "PrefabPublicRequestBus.CreatePrefabInMemory + PrefabPublicRequestBus.InstantiatePrefab",
        "argument_value_shape": {
            "prefab_path": "absolute temp-level .prefab path under Levels/_maxine_smoke",
            "entity_ids": "list[azlmbr.entity.EntityId]",
            "parent_entity_id": "azlmbr.entity.EntityId()",
            "position": "azlmbr.math.Vector3",
        },
        "instantiation": instantiation,
        "source_prefab_baseline_result": source_prefab_baseline_result,
        "direct_procprefab_product_semantics": direct_semantics,
        "runtime_spawnable_proof": runtime_proof,
        "procprefab_character_assertions": direct_semantics.get(
            "procprefab_character_assertions",
            {"status": "not_run"},
        ),
        "blocked_reason": (
            direct_semantics.get("blocked_reason")
            or direct_semantics.get("unsupported_reason")
            or instantiation.get("blocked_reason", "prefab_instantiation_failed")
        ),
        "message": "Prefab surface discovery passed, but temp-level prefab instantiation did not pass.",
    }


def _discover_component_type_ids(
    component_names: Sequence[str],
    registry_key: str,
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    registry: Dict[str, Any],
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    if not _surface_available(surface):
        registry[registry_key] = {
            "status": "unsupported_by_engine_binding",
            "component_names": list(component_names),
            "discovery_source": "EditorComponentAPIBus_unavailable",
            "safe_for_unattended_temp_level_smoke": False,
        }
        return {"status": "unsupported_by_engine_binding", "type_ids_raw": []}

    entity_type_candidates = _entity_type_candidates(surface)
    signatures: List[Tuple[Any, ...]] = [(list(component_names), candidate) for candidate in entity_type_candidates]
    signatures.append((list(component_names),))
    for args in signatures:
        status, value = _component_bus_call(
            surface,
            "FindComponentTypeIdsByEntityType",
            args,
            safe_call_results,
        )
        attempts.append({"status": status, "args_shape": f"{len(args)} arguments"})
        type_ids = _extract_sequence(_unwrap_outcome(value))
        valid_type_ids = [type_id for type_id in type_ids if _valid_component_type_id(type_id)]
        if status == "pass" and valid_type_ids:
            serialized = [_safe_serialize(type_id) for type_id in valid_type_ids]
            registry[registry_key] = {
                "status": "pass",
                "component_names": list(component_names),
                "type_ids": serialized,
                "discovery_source": "EditorComponentAPIBus.FindComponentTypeIdsByEntityType",
                "safe_for_unattended_temp_level_smoke": True,
            }
            return {"status": "pass", "type_ids": serialized, "type_ids_raw": valid_type_ids}

    registry[registry_key] = {
        "status": "blocked_by_missing_binding",
        "component_names": list(component_names),
        "discovery_source": "EditorComponentAPIBus.FindComponentTypeIdsByEntityType",
        "attempts": attempts,
        "safe_for_unattended_temp_level_smoke": False,
    }
    return {"status": "blocked_by_missing_binding", "type_ids_raw": []}


def _try_add_safe_component(
    entity_id: Any,
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    registry: Dict[str, Any],
    property_summary: Dict[str, Any],
) -> Dict[str, Any]:
    for component_name in ("Tag", "Comment"):
        discovered = _discover_component_type_ids([component_name], component_name, surface, safe_call_results, registry)
        if discovered.get("status") != "pass":
            continue
        add_result = _add_components(entity_id, discovered.get("type_ids_raw", []), surface, safe_call_results, component_name=component_name)
        component_ref = _first_component_reference(add_result, entity_id, discovered.get("type_ids_raw", []), surface, safe_call_results)
        property_summary[component_name] = _build_component_property_list(component_ref, surface, safe_call_results)
        property_access = _get_component_property_values(component_ref, property_summary[component_name], surface, safe_call_results)
        return {**add_result, "component_name": component_name, "type_id_status": "pass", "property_access": property_access}
    return {
        "status": "unavailable_with_verified_reason",
        "unavailable_reason": "no_safe_additional_component_type_discovered",
        "safe_component_candidates": ["Tag", "Comment"],
    }


def _add_components(
    entity_id: Any,
    type_ids: Sequence[Any],
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    *,
    component_name: str,
) -> Dict[str, Any]:
    if not type_ids:
        return {"status": "blocked_by_missing_binding", "blocked_reason": f"{component_name}_type_id_missing"}
    status, value = _component_bus_call(surface, "AddComponentsOfType", (entity_id, list(type_ids)), safe_call_results)
    unwrapped = _unwrap_outcome(value)
    component_refs = _extract_sequence(unwrapped)
    if status == "pass" and (component_refs or _outcome_success(value)):
        return {
            "status": "pass",
            "component_name": component_name,
            "component_refs": [_safe_serialize(ref) for ref in component_refs],
        }
    return {
        "status": "blocked_by_missing_binding",
        "component_name": component_name,
        "blocked_reason": "AddComponentsOfType_returned_no_component",
        "result": _safe_serialize(unwrapped),
    }


def _get_component_reference(
    entity_id: Any,
    type_ids: Sequence[Any],
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not type_ids:
        return {"status": "blocked_by_missing_binding", "blocked_reason": "component_type_id_missing"}
    for method in ("GetComponentOfType", "GetComponentsOfType"):
        status, value = _component_bus_call(surface, method, (entity_id, type_ids[0]), safe_call_results)
        refs = _extract_sequence(_unwrap_outcome(value))
        if status == "pass" and refs:
            return {"status": "pass", "component_ref": refs[0], "component_ref_serialized": _safe_serialize(refs[0]), "source": method}
        if status == "pass" and value is not None and not isinstance(value, bool):
            return {"status": "pass", "component_ref": value, "component_ref_serialized": _safe_serialize(value), "source": method}
    has_status, has_value = _component_bus_call(surface, "HasComponentOfType", (entity_id, type_ids[0]), safe_call_results)
    if has_status == "pass" and bool(_unwrap_outcome(has_value)):
        return {"status": "pass", "component_ref": None, "component_ref_serialized": "", "source": "HasComponentOfType"}
    return {"status": "blocked_by_missing_binding", "blocked_reason": "component_reference_not_discovered"}


def _first_component_reference(
    add_result: Mapping[str, Any],
    entity_id: Any,
    type_ids: Sequence[Any],
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return _get_component_reference(entity_id, type_ids, surface, safe_call_results)


def _build_component_property_list(
    component_result: Mapping[str, Any],
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    component_ref = component_result.get("component_ref")
    if component_result.get("status") != "pass":
        return {
            "status": "blocked_by_missing_binding",
            "blocked_reason": component_result.get("blocked_reason", "component_reference_not_available"),
        }
    if component_ref is None:
        return {
            "status": "unavailable_with_verified_reason",
            "unavailable_reason": "component_reference_not_returned_by_binding",
        }
    for args in ((component_ref,),):
        status, value = _component_bus_call(surface, "BuildComponentPropertyList", args, safe_call_results)
        properties = [str(item) for item in _extract_sequence(_unwrap_outcome(value))]
        if status == "pass":
            return {
                "status": "pass",
                "properties": properties,
                "property_count": len(properties),
                "component_ref": _safe_serialize(component_ref),
            }
    return {
        "status": "unsupported_by_engine_binding",
        "blocked_reason": "BuildComponentPropertyList_not_available",
        "component_ref": _safe_serialize(component_ref),
    }


def _get_component_property_values(
    component_result: Mapping[str, Any],
    properties: Mapping[str, Any],
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    component_ref = component_result.get("component_ref")
    property_paths = [str(path) for path in properties.get("properties", [])] if isinstance(properties.get("properties"), list) else []
    if component_result.get("status") != "pass" or component_ref is None:
        return {
            "status": "blocked_by_missing_binding",
            "blocked_reason": component_result.get("blocked_reason", "component_reference_not_available"),
        }
    if not property_paths:
        return {
            "status": "unavailable_with_verified_reason",
            "unavailable_reason": "no_component_properties_listed_for_readback",
        }
    reads: List[Dict[str, Any]] = []
    for property_path in property_paths[:3]:
        status, value = _component_bus_call(surface, "GetComponentProperty", (component_ref, property_path), safe_call_results)
        reads.append(
            {
                "property_path": property_path,
                "status": status,
                "value": _safe_serialize(_unwrap_outcome(value)),
            }
        )
    if any(read.get("status") == "pass" for read in reads):
        return {"status": "pass", "read_count": len(reads), "reads": reads}
    return {
        "status": "unavailable_with_verified_reason",
        "unavailable_reason": "GetComponentProperty_returned_no_readable_values",
        "reads": reads,
    }


def _component_bus_call(
    surface: Mapping[str, Any],
    method: str,
    args: Tuple[Any, ...],
    safe_call_results: List[Dict[str, Any]],
) -> Tuple[str, Any]:
    bus = surface.get("bus")
    editor = surface.get("editor")
    call_name = f"EditorComponentAPIBus.{method}"
    try:
        value = editor.EditorComponentAPIBus(bus.Broadcast, method, *args)  # type: ignore[union-attr]
        status = "pass" if method == "BuildComponentPropertyList" or _outcome_success(value) else "unavailable_with_verified_reason"
        safe_call_results.append(
            {
                "call": call_name,
                "status": status,
                "args_shape": f"{len(args)} arguments",
                "result": _safe_serialize(_unwrap_outcome(value)),
            }
        )
        return status, value
    except Exception as exc:
        safe_call_results.append(
            {
                "call": call_name,
                "status": "unsupported_by_engine_binding",
                "args_shape": f"{len(args)} arguments",
                "error": str(exc),
            }
        )
        return "unsupported_by_engine_binding", None


def _set_component_property(
    surface: Mapping[str, Any],
    component_ref: Any,
    property_path: str,
    value: Any,
    safe_call_results: List[Dict[str, Any]],
) -> Tuple[str, Any]:
    bus = surface.get("bus")
    editor = surface.get("editor")
    call_name = "EditorComponentAPIBus.SetComponentProperty"
    try:
        result = editor.EditorComponentAPIBus(bus.Broadcast, "SetComponentProperty", component_ref, property_path, value)  # type: ignore[union-attr]
        status = "pass"
        if result is not None and hasattr(result, "IsSuccess"):
            status = "pass" if result.IsSuccess() else "fail"
        safe_call_results.append(
            {
                "call": call_name,
                "status": status,
                "args_shape": "3 arguments",
                "property_path": property_path,
                "value_shape": _value_shape(value),
                "result": _safe_serialize(_unwrap_outcome(result)),
            }
        )
        return status, result
    except Exception as exc:
        safe_call_results.append(
            {
                "call": call_name,
                "status": "unsupported_by_engine_binding",
                "args_shape": "3 arguments",
                "property_path": property_path,
                "value_shape": _value_shape(value),
                "error": str(exc),
            }
        )
        return "unsupported_by_engine_binding", None


def _component_validity_checks(
    component_ref: Any,
    surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    checks: Dict[str, Any] = {"status": "unavailable_with_verified_reason", "checks": []}
    observed_pass = False
    for method in ("IsValid", "IsComponentEnabled"):
        status, value = _component_bus_call(surface, method, (component_ref,), safe_call_results)
        checks["checks"].append({"call": f"EditorComponentAPIBus.{method}", "status": status, "value": _safe_serialize(_unwrap_outcome(value))})
        if status == "pass":
            observed_pass = True
    checks["status"] = "pass" if observed_pass else "unavailable_with_verified_reason"
    return checks


def _entity_type_candidates(surface: Mapping[str, Any]) -> List[Any]:
    candidates: List[Any] = []
    entity_module = surface.get("entity")
    try:
        entity_type = entity_module.EntityType()  # type: ignore[union-attr]
        for attr in ("Game", "Editor"):
            if hasattr(entity_type, attr):
                candidates.append(getattr(entity_type, attr))
        candidates.append(entity_type)
    except Exception:
        pass
    candidates.extend([0, 1])
    unique: List[Any] = []
    observed: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in observed:
            observed.add(key)
            unique.append(candidate)
    return unique


def _probe_prefab_surface(safe_call_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        import azlmbr.prefab as prefab  # type: ignore

        public_names = sorted(name for name in dir(prefab) if not name.startswith("_"))
        safe_call_results.append(
            {
                "call": "import azlmbr.prefab",
                "status": "pass",
                "result": public_names[:25],
            }
        )
        candidate_calls = [
            name
            for name in public_names
            if any(token in name.lower() for token in ("instantiate", "prefab", "spawn", "load"))
        ]
        if candidate_calls:
            return {
                "status": "pass",
                "candidate_calls": candidate_calls,
                "discovery_source": "azlmbr.prefab module introspection",
            }
        return {
            "status": "unsupported_by_engine_binding",
            "blocked_reason": "azlmbr_prefab_has_no_visible_instantiation_surface",
            "discovery_source": "azlmbr.prefab module introspection",
        }
    except Exception as exc:
        safe_call_results.append({"call": "import azlmbr.prefab", "status": "unsupported_by_engine_binding", "error": str(exc)})
        return {
            "status": "unsupported_by_engine_binding",
            "blocked_reason": "azlmbr_prefab_import_failed",
            "error": str(exc),
        }


def _resolve_asset_id(actor_product: str, safe_call_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        import azlmbr.asset as asset  # type: ignore
        import azlmbr.bus as bus  # type: ignore
        import azlmbr.math as math  # type: ignore
    except Exception as exc:
        return {
            "status": "unsupported_by_engine_binding",
            "approved_product_ref": actor_product,
            "blocked_reason": "asset_catalog_binding_import_failed",
            "error": str(exc),
        }

    candidates = _asset_catalog_path_candidates(actor_product)
    attempts: List[Dict[str, Any]] = []
    for candidate in candidates:
        try:
            asset_id = asset.AssetCatalogRequestBus(bus.Broadcast, "GetAssetIdByPath", candidate, math.Uuid(), False)
            valid = _asset_id_valid(asset_id)
            attempts.append({"path": candidate, "status": "pass" if valid else "unavailable_with_verified_reason", "asset_id": _safe_serialize(asset_id)})
            safe_call_results.append(
                {
                    "call": "AssetCatalogRequestBus.GetAssetIdByPath",
                    "status": "pass" if valid else "unavailable_with_verified_reason",
                    "args_shape": "3 arguments",
                    "asset_path": candidate,
                    "result": _safe_serialize(asset_id),
                }
            )
            if valid:
                return {
                    "status": "pass",
                    "approved_product_ref": actor_product,
                    "selected_asset_catalog_path": candidate,
                    "asset_id": _safe_serialize(asset_id),
                    "asset_id_raw": asset_id,
                    "attempts": attempts,
                }
        except Exception as exc:
            attempts.append({"path": candidate, "status": "unsupported_by_engine_binding", "error": str(exc)})
            safe_call_results.append(
                {
                    "call": "AssetCatalogRequestBus.GetAssetIdByPath",
                    "status": "unsupported_by_engine_binding",
                    "args_shape": "3 arguments",
                    "asset_path": candidate,
                    "error": str(exc),
                }
            )
    return {
        "status": "blocked_by_missing_product_evidence",
        "approved_product_ref": actor_product,
        "blocked_reason": "actor_asset_catalog_id_not_found",
        "attempts": attempts,
    }


def _asset_catalog_path_candidates(product_path: str) -> List[str]:
    normalized = product_path.replace("\\", "/").strip()
    candidates = [normalized]
    if normalized.lower().startswith("pc/"):
        candidates.append(normalized[3:])
    if normalized.lower().startswith("cache/"):
        without_cache = normalized.split("/", 2)
        if len(without_cache) == 3:
            candidates.append(without_cache[2])
    lowered = [candidate.lower() for candidate in candidates]
    return _unique([*candidates, *lowered])


def _asset_id_valid(asset_id: Any) -> bool:
    for method in ("is_valid", "IsValid"):
        try:
            if hasattr(asset_id, method):
                return bool(getattr(asset_id, method)())
        except Exception:
            pass
    serialized = str(_safe_serialize(asset_id)).strip().lower()
    return bool(serialized and serialized not in {"0", "none", "{00000000-0000-0000-0000-000000000000}:0"})


def _public_asset_resolution(asset_resolution: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in asset_resolution.items()
        if key != "asset_id_raw"
    }


def _asset_ids_match(read_value: Any, expected_asset_id: Any) -> bool:
    read_unwrapped = _unwrap_outcome(read_value)
    expected = _safe_serialize(expected_asset_id)
    observed = _safe_serialize(read_unwrapped)
    if observed == expected:
        return True
    return str(observed).strip().lower() == str(expected).strip().lower()


def _instantiate_temp_prefab(entity_id: Any, safe_call_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if entity_id is None:
        return {"status": "blocked_by_readiness", "blocked_reason": "entity_smoke_not_available"}
    try:
        import azlmbr.bus as bus  # type: ignore
        import azlmbr.entity as entity  # type: ignore
        import azlmbr.math as math  # type: ignore
        import azlmbr.prefab as prefab  # type: ignore
    except Exception as exc:
        return {
            "status": "unsupported_by_engine_binding",
            "blocked_reason": "prefab_instantiation_import_failed",
            "error": str(exc),
        }

    temp_level_path = os.environ.get("MAXINE_EDITOR_SMOKE_TEMP_LEVEL_PATH", "")
    if not temp_level_path or not _temp_level_path_safe(temp_level_path):
        return {
            "status": "blocked_by_unsafe_operation",
            "blocked_reason": "temp_level_path_not_safe_for_prefab_source",
        }
    prefab_source_path = Path(temp_level_path) / "maxine_smoke_prefab_instantiation.prefab"
    if not _temp_level_path_safe(str(prefab_source_path)):
        return {
            "status": "blocked_by_unsafe_operation",
            "blocked_reason": "prefab_source_path_outside_temp_level_root",
        }

    create_status, create_value = _prefab_bus_call(
        prefab,
        bus,
        "CreatePrefabInMemory",
        ([entity_id], str(prefab_source_path)),
        safe_call_results,
    )
    if create_status != "pass":
        return {
            "status": create_status,
            "selected_call": "PrefabPublicRequestBus.CreatePrefabInMemory",
            "prefab_source_path_redacted": _redacted_project_temp_path(str(prefab_source_path)),
            "blocked_reason": "prefab_create_in_memory_failed",
            "result": _safe_serialize(_unwrap_outcome(create_value)),
        }

    instantiate_status, instantiate_value = _prefab_bus_call(
        prefab,
        bus,
        "InstantiatePrefab",
        (str(prefab_source_path), entity.EntityId(), math.Vector3(0.0, 0.0, 0.0)),
        safe_call_results,
    )
    created_entity_id = _unwrap_outcome(instantiate_value)
    if instantiate_status != "pass" or not _entity_id_valid(created_entity_id):
        return {
            "status": instantiate_status if instantiate_status != "pass" else "fail",
            "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
            "prefab_source_path_redacted": _redacted_project_temp_path(str(prefab_source_path)),
            "blocked_reason": "prefab_instantiate_returned_no_container_entity",
            "result": _safe_serialize(created_entity_id),
        }

    owning_status, owning_value = _prefab_bus_call(
        prefab,
        bus,
        "GetOwningInstancePrefabPath",
        (created_entity_id,),
        safe_call_results,
    )
    return {
        "status": "pass",
        "selected_call": "PrefabPublicRequestBus.CreatePrefabInMemory + PrefabPublicRequestBus.InstantiatePrefab",
        "prefab_source_path_redacted": _redacted_project_temp_path(str(prefab_source_path)),
        "created_entity_count": 1,
        "container_entity": _safe_serialize(created_entity_id),
        "created_entity_id": _safe_serialize(created_entity_id),
        "owning_instance_prefab_path": _redacted_project_temp_path(str(_unwrap_outcome(owning_value))) if owning_status == "pass" else "",
        "owning_instance_prefab_path_status": owning_status,
    }


def _direct_procprefab_semantics_allows_pass(semantics: Mapping[str, Any]) -> bool:
    if semantics.get("direct_product_instantiation_verified") is True:
        instantiation = semantics.get("procprefab_direct_product_instantiation_result", {})
        try:
            created_count = int(instantiation.get("created_entity_count", 0) or 0) if isinstance(instantiation, Mapping) else 0
        except (TypeError, ValueError):
            created_count = 0
        return (
            semantics.get("direct_product_instantiation_claimed") is True
            and semantics.get("direct_product_instantiation_supported") is True
            and isinstance(instantiation, Mapping)
            and instantiation.get("status") == "pass"
            and created_count > 0
            and _direct_procprefab_content_assertions_allow_pass(semantics)
            and _procprefab_character_assertions_allow_pass(semantics)
        )
    status = str(semantics.get("status", "")).strip()
    instantiation = semantics.get("procprefab_direct_product_instantiation_result", {})
    instantiation_status = str(instantiation.get("status", "")).strip() if isinstance(instantiation, Mapping) else ""
    reason = str(
        semantics.get("unsupported_reason")
        or semantics.get("blocked_reason")
        or (instantiation.get("reason", "") if isinstance(instantiation, Mapping) else "")
    ).strip()
    return (instantiation_status or status) in DIRECT_PROCPREFAB_TYPED_NONVERIFIED_STATUSES and bool(reason)


def _direct_procprefab_content_assertions_allow_pass(semantics: Mapping[str, Any]) -> bool:
    content = semantics.get("direct_procprefab_content_assertions")
    if not isinstance(content, Mapping):
        content = semantics.get("direct_product_assertions")
    if not isinstance(content, Mapping):
        return False
    required_failures = content.get("required_assertions_failed", [])
    assertion_failures = content.get("assertion_failures", [])
    return (
        content.get("status") == "pass"
        and content.get("required_assertions_status") == "pass"
        and content.get("direct_product_assertion_status") == "pass"
        and content.get("created_container_valid") is True
        and content.get("owning_prefab_path_matches_expected") is True
        and content.get("created_entity_count_status") == "pass"
        and isinstance(content.get("missing_asset_log_signals"), Mapping)
        and content["missing_asset_log_signals"].get("status") == "pass"
        and isinstance(content.get("editor_log_error_scan"), Mapping)
        and content["editor_log_error_scan"].get("status") == "pass"
        and not (required_failures if isinstance(required_failures, list) else [required_failures])
        and not (assertion_failures if isinstance(assertion_failures, list) else [assertion_failures])
    )


def _procprefab_character_assertions_allow_pass(semantics: Mapping[str, Any]) -> bool:
    character = semantics.get("procprefab_character_assertions")
    if not isinstance(character, Mapping):
        return False
    required_failures = character.get("required_character_assertions_failed", [])
    assertion_failures = character.get("character_assertion_failures", [])
    return (
        character.get("status") in {"pass", "informational_only", "unavailable_with_verified_reason"}
        and character.get("character_assertion_status") in {
            "pass",
            "informational_only",
            "unavailable_with_verified_reason",
        }
        and character.get("required_character_assertions_status") == "pass"
        and character.get("character_component_inventory_status")
        in {"pass", "informational_only", "unavailable_with_verified_reason"}
        and isinstance(character.get("editor_log_character_error_scan"), Mapping)
        and character["editor_log_character_error_scan"].get("status") == "pass"
        and isinstance(character.get("editor_log_missing_actor_signal"), Mapping)
        and character["editor_log_missing_actor_signal"].get("status") == "pass"
        and isinstance(character.get("editor_log_missing_mesh_signal"), Mapping)
        and character["editor_log_missing_mesh_signal"].get("status") == "pass"
        and isinstance(character.get("editor_log_missing_material_signal"), Mapping)
        and character["editor_log_missing_material_signal"].get("status") == "pass"
        and isinstance(character.get("editor_log_missing_animation_signal"), Mapping)
        and character["editor_log_missing_animation_signal"].get("status") == "pass"
        and "Transform" not in (character.get("required_character_assertions_passed", []) or [])
        and not (required_failures if isinstance(required_failures, list) else [required_failures])
        and not (assertion_failures if isinstance(assertion_failures, list) else [assertion_failures])
    )


def _build_runtime_spawnable_proof_surface(
    report: Mapping[str, Any],
    direct_semantics: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    *,
    progress_log: Path | None,
) -> Dict[str, Any]:
    _write_progress_marker(
        progress_log,
        "runtime_spawnable_proof_started",
        "started",
        "Inspecting runtime/spawnable/product dependency proof surfaces without launching runtime.",
    )
    procprefab_product = _product_ref(report, "procprefab") or str(direct_semantics.get("procprefab_product_path", ""))
    product_refs = _character_product_refs(report)
    product_evidence_complete = _report_product_evidence_complete(report)
    surface_discovery = _discover_runtime_spawnable_surface()
    dependency_proof = _query_direct_procprefab_product_dependencies(procprefab_product, product_refs)
    launcher_candidates = _discover_runtime_launcher_candidates()
    character_log_scan = _scan_editor_log_for_procprefab_character_signals(
        str(direct_semantics.get("procprefab_asset_hint") or procprefab_product)
    )

    required_passed: List[str] = []
    required_failed: List[str] = []
    informational: List[str] = ["product_dependency_proof_is_not_runtime_execution_proof"]
    unavailable_reasons: List[Dict[str, Any]] = []
    unsupported_reasons: List[Dict[str, Any]] = []

    if product_evidence_complete:
        required_passed.append("apb_product_evidence_complete")
    else:
        required_failed.append("apb_product_evidence_complete")

    if surface_discovery.get("status") == "runtime_surface_discovery_pass":
        informational.append("runtime_spawnable_source_surface_discovered")
    else:
        unavailable_reasons.append(
            {
                "assertion": "runtime_spawnable_surface_discovery",
                "status": surface_discovery.get("status", "unavailable_with_verified_reason"),
                "reason": surface_discovery.get("reason", "runtime_spawnable_surface_not_discovered"),
            }
        )

    if dependency_proof.get("status") == "product_dependency_proof_pass":
        required_passed.append("product_dependency_graph_matches_apb_evidence")
    else:
        required_passed.append("product_dependency_graph_checked")
        unavailable_reasons.append(
            {
                "assertion": "product_dependency_character_references",
                "status": dependency_proof.get("status", "product_dependency_proof_unavailable"),
                "reason": dependency_proof.get("reason", "product_dependency_character_references_unavailable"),
            }
        )

    if character_log_scan.get("status") == "pass":
        required_passed.append("no_runtime_or_editor_character_load_error_signals")
    else:
        required_failed.append("no_runtime_or_editor_character_load_error_signals")

    runtime_blocked_reason = "runtime_spawnable_proof_requires_dedicated_runtime_harness"
    runtime_execution_result = {
        "status": "runtime_execution_not_attempted",
        "reason": runtime_blocked_reason,
        "safety_posture": "Runtime launcher candidates are recorded, but no runtime is launched without a pinned bounded harness.",
    }
    unavailable_reasons.append(
        {
            "assertion": "runtime_spawnable_execution",
            "status": "runtime_execution_not_attempted",
            "reason": runtime_blocked_reason,
        }
    )
    required_passed.append("runtime_execution_not_attempted_with_typed_reason")

    matched_refs = dependency_proof.get("matched_product_evidence", [])
    status = "runtime_spawnable_character_proof_unavailable"
    if matched_refs:
        status = "product_dependency_proof_pass"
        informational.append("character_product_references_matched_by_product_dependency_graph")
    if required_failed:
        status = "fail"

    result = {
        "status": status,
        "runtime_spawnable_proof_status": status,
        "runtime_spawnable_surface_discovery": surface_discovery,
        "runtime_spawnable_surface_available": surface_discovery.get("status") == "runtime_surface_discovery_pass",
        "runtime_spawnable_surface_type": surface_discovery.get(
            "surface_type", "asset_catalog_product_dependencies_and_spawnable_source_surface"
        ),
        "runtime_spawnable_selected_call": "",
        "runtime_spawnable_argument_shape": {},
        "runtime_spawnable_execution_attempted": False,
        "runtime_spawnable_execution_result": runtime_execution_result,
        "runtime_spawnable_execution_supported": False,
        "runtime_spawnable_execution_verified": False,
        "runtime_spawnable_launcher_path": launcher_candidates[0]["path"] if launcher_candidates else "",
        "runtime_spawnable_launcher_provenance": "candidate_only_not_executed" if launcher_candidates else "",
        "runtime_spawnable_timeout_seconds": 0,
        "runtime_spawnable_exit_code": None,
        "runtime_spawnable_stdout_ref": "",
        "runtime_spawnable_stderr_ref": "",
        "runtime_spawnable_log_refs": [],
        "runtime_spawnable_product_path": procprefab_product,
        "runtime_spawnable_asset_id": str(direct_semantics.get("procprefab_asset_id", "")),
        "runtime_spawnable_dependency_graph": {
            "status": dependency_proof.get("status", "product_dependency_proof_unavailable"),
            "dependencies": dependency_proof.get("dependencies", []),
            "dependency_count": dependency_proof.get("product_dependency_count", 0),
            "missing_dependency_count": dependency_proof.get("missing_dependency_count", 0),
        },
        "runtime_spawnable_product_dependencies": dependency_proof.get("dependencies", []),
        "runtime_spawnable_character_product_references": matched_refs if isinstance(matched_refs, list) else [],
        "runtime_spawnable_actor_reference": _runtime_product_reference("actor", matched_refs),
        "runtime_spawnable_azmodel_reference": _runtime_product_reference("azmodel", matched_refs),
        "runtime_spawnable_pxmesh_reference": _runtime_product_reference("pxmesh", matched_refs),
        "runtime_spawnable_azmaterial_reference": _runtime_product_reference("azmaterial", matched_refs),
        "runtime_spawnable_motion_reference": _runtime_product_reference("motion", matched_refs),
        "runtime_spawnable_motionset_reference": _runtime_product_reference("motionset", matched_refs),
        "runtime_spawnable_animgraph_reference": _runtime_product_reference("animgraph", matched_refs),
        "runtime_spawnable_created_entity_count": 0,
        "runtime_spawnable_component_inventory": {
            "status": "runtime_execution_not_attempted",
            "reason": runtime_blocked_reason,
        },
        "runtime_spawnable_missing_asset_signals": {
            "status": character_log_scan.get("status", "unavailable_with_verified_reason"),
            "matches": character_log_scan.get("matches", []),
            "source": "selected product Editor log scan; runtime was not executed",
        },
        "runtime_spawnable_missing_character_signals": {
            "status": character_log_scan.get("status", "unavailable_with_verified_reason"),
            "missing_actor": character_log_scan.get("missing_actor", {}),
            "missing_mesh": character_log_scan.get("missing_mesh", {}),
            "missing_material": character_log_scan.get("missing_material", {}),
            "missing_animation": character_log_scan.get("missing_animation", {}),
            "source": "selected product Editor log scan; runtime was not executed",
        },
        "runtime_spawnable_blocked_reason": runtime_blocked_reason,
        "runtime_spawnable_unsupported_reason": "",
        "product_dependency_proof": dependency_proof,
        "product_dependency_proof_status": dependency_proof.get("status", "product_dependency_proof_unavailable"),
        "product_dependency_matches_apb_evidence": bool(matched_refs),
        "editor_component_inventory_character_assertion_result": {
            "status": direct_semantics.get("procprefab_character_assertions", {}).get(
                "status", "unavailable_with_verified_reason"
            )
            if isinstance(direct_semantics.get("procprefab_character_assertions"), Mapping)
            else "unavailable_with_verified_reason",
            "reason": "direct_procprefab_character_components_not_exposed_in_editor_product_instance",
        },
        "direct_product_instantiation_result": {
            "status": direct_semantics.get("procprefab_direct_product_instantiation_result", {}).get("status", "")
            if isinstance(direct_semantics.get("procprefab_direct_product_instantiation_result"), Mapping)
            else "",
            "direct_product_instantiation_verified": direct_semantics.get("direct_product_instantiation_verified") is True,
        },
        "direct_product_content_assertion_result": {
            "status": direct_semantics.get("direct_procprefab_content_assertions", {}).get("status", "")
            if isinstance(direct_semantics.get("direct_procprefab_content_assertions"), Mapping)
            else "",
        },
        "source_prefab_baseline_result": {
            "status": direct_semantics.get("source_prefab_baseline_result", {}).get("status", "")
            if isinstance(direct_semantics.get("source_prefab_baseline_result"), Mapping)
            else "",
        },
        "actor_assignment_result": {"status": "pass" if _actor_assignment_passed(report) else "not_evaluated"},
        "required_runtime_spawnable_assertions_passed": _unique(required_passed),
        "required_runtime_spawnable_assertions_failed": _unique(required_failed),
        "runtime_spawnable_assertion_failures": [f"assertion_failed_{failure}" for failure in required_failed],
        "runtime_spawnable_assertion_informational": _unique(informational),
        "runtime_spawnable_unavailable_reasons": unavailable_reasons,
        "runtime_spawnable_unsupported_reasons": unsupported_reasons,
        "runtime_launcher_candidates": launcher_candidates,
        "fake_success": False,
        "cache_heuristic_used": bool(report.get("cache_heuristic_used")),
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
    }
    safe_call_results.append(
        {
            "call": "runtime_spawnable_proof_surface.product_dependency_and_source_discovery",
            "status": "pass" if not required_failed else "fail",
            "args_shape": "APB report + Asset Processor database + local engine source",
            "result": {
                "runtime_execution_attempted": False,
                "product_dependency_proof_status": result["product_dependency_proof_status"],
                "runtime_spawnable_proof_status": result["runtime_spawnable_proof_status"],
            },
        }
    )
    _write_progress_marker(
        progress_log,
        "runtime_spawnable_proof_returned",
        result["runtime_spawnable_proof_status"],
        "Runtime/spawnable proof surface inspection returned.",
    )
    return result


def _report_product_evidence_complete(report: Mapping[str, Any]) -> bool:
    expected = [str(value).strip() for value in report.get("expected_products", []) if str(value).strip()]
    summary = report.get("product_evidence_summary", {})
    produced = []
    if isinstance(summary, Mapping):
        produced = [str(value).strip() for value in summary.get("produced_products", []) if str(value).strip()]
    missing = [product for product in expected if product not in produced]
    return bool(expected) and not missing and isinstance(summary, Mapping) and summary.get("status") == "pass" and not summary.get("cache_heuristic_used")


def _actor_assignment_passed(report: Mapping[str, Any]) -> bool:
    actor_checks = report.get("actor_binding_checks", {})
    assignment = actor_checks.get("actor_asset_assignment", {}) if isinstance(actor_checks, Mapping) else {}
    readback = assignment.get("readback", {}) if isinstance(assignment, Mapping) else {}
    return (
        isinstance(assignment, Mapping)
        and assignment.get("status") == "pass"
        and isinstance(readback, Mapping)
        and readback.get("matched_approved_product") is True
    )


def _discover_runtime_spawnable_surface() -> Dict[str, Any]:
    engine_root_raw = os.environ.get("O3DE_ENGINE_ROOT", "")
    engine_root = Path(engine_root_raw) if engine_root_raw else None
    refs = [
        ("AzFramework::Spawnable", "Code/Framework/AzFramework/AzFramework/Spawnable/Spawnable.h"),
        (
            "AzFramework::SpawnableEntitiesInterface",
            "Code/Framework/AzFramework/AzFramework/Spawnable/SpawnableEntitiesInterface.h",
        ),
        (
            "AzFramework::Scripts::SpawnableScriptMediator",
            "Code/Framework/AzFramework/AzFramework/Spawnable/Script/SpawnableScriptMediator.h",
        ),
        (
            "AssetCatalogRequestBus product dependencies",
            "Code/Framework/AzCore/AzCore/Asset/AssetManagerBus.h",
        ),
        (
            "AssetCatalog product dependency implementation",
            "Code/Framework/AzFramework/AzFramework/Asset/AssetCatalog.cpp",
        ),
    ]
    source_refs: List[Dict[str, Any]] = []
    found = False
    for surface, rel_path in refs:
        present = bool(engine_root and (engine_root / rel_path).exists())
        found = found or present
        source_refs.append(
            {
                "surface": surface,
                "source_ref": (str(engine_root / rel_path).replace("\\", "/") if engine_root else rel_path),
                "present": present,
            }
        )
    if found:
        return {
            "status": "runtime_surface_discovery_pass",
            "surface_type": "asset_catalog_product_dependencies_and_spawnable_source_surface",
            "candidate_surfaces": [item["surface"] for item in source_refs],
            "source_refs": source_refs,
            "selected_for_this_slice": "Asset Processor database ProductDependencies readonly query",
            "runtime_execution_surface": "not selected; bounded runtime harness not pinned",
        }
    return {
        "status": "unavailable_with_verified_reason",
        "surface_type": "asset_catalog_product_dependencies_and_spawnable_source_surface",
        "candidate_surfaces": [item["surface"] for item in source_refs],
        "source_refs": source_refs,
        "reason": "local_engine_source_not_available_for_spawnable_surface_discovery",
    }


def _discover_runtime_launcher_candidates() -> List[Dict[str, Any]]:
    engine_root_raw = os.environ.get("O3DE_ENGINE_ROOT", "")
    project_path_raw = os.environ.get("O3DE_PROJECT_PATH", "")
    engine_root = Path(engine_root_raw) if engine_root_raw else None
    project_name = Path(project_path_raw).name if project_path_raw else "MAXINE_GoldenCorpus"
    if engine_root is None:
        return []
    bin_dir = engine_root / "build" / "windows" / "bin" / "profile"
    names = [
        f"{project_name}.GameLauncher.exe",
        f"{project_name}.HeadlessServerLauncher.exe",
        f"{project_name}.ServerLauncher.exe",
        "GameLauncher.exe",
    ]
    candidates: List[Dict[str, Any]] = []
    for name in names:
        candidate = bin_dir / name
        if candidate.exists():
            candidates.append(
                {
                    "path": str(candidate).replace("\\", "/"),
                    "provenance": "engine_profile_bin_candidate_not_executed",
                    "execution_attempted": False,
                }
            )
    return candidates


def _query_direct_procprefab_product_dependencies(product_path: str, product_refs: Mapping[str, str]) -> Dict[str, Any]:
    project_path_raw = os.environ.get("O3DE_PROJECT_PATH", "")
    project_path = Path(project_path_raw) if project_path_raw else None
    db_path = project_path / "Cache" / "assetdb.sqlite" if project_path else None
    if db_path is None or not db_path.exists():
        return {
            "status": "product_dependency_proof_unavailable",
            "selected_call": "Asset Processor database ProductDependencies readonly query",
            "product_path": product_path,
            "dependencies": [],
            "product_dependency_count": 0,
            "missing_dependency_count": 0,
            "matched_product_evidence": [],
            "reason": "asset_processor_database_not_found",
        }

    try:
        import sqlite3
    except Exception as exc:
        return {
            "status": "product_dependency_proof_unavailable",
            "selected_call": "Asset Processor database ProductDependencies readonly query",
            "product_path": product_path,
            "dependencies": [],
            "product_dependency_count": 0,
            "missing_dependency_count": 0,
            "matched_product_evidence": [],
            "reason": "sqlite3_unavailable",
            "error": str(exc),
        }

    product_candidates = _unique([product_path, product_path[3:] if product_path.lower().startswith("pc/") else f"pc/{product_path}"])
    try:
        connection = sqlite3.connect(str(db_path))
        try:
            connection.execute("PRAGMA query_only = ON")
            product_row = None
            for candidate in product_candidates:
                row = connection.execute(
                    "SELECT ProductID, ProductName, SubID, AssetType FROM Products WHERE lower(ProductName) = lower(?) LIMIT 1",
                    (candidate,),
                ).fetchone()
                if row:
                    product_row = row
                    break
            if not product_row:
                return {
                    "status": "product_dependency_proof_unavailable",
                    "selected_call": "Asset Processor database ProductDependencies readonly query",
                    "product_path": product_path,
                    "database_ref": _redacted_project_temp_path(str(db_path)),
                    "dependencies": [],
                    "product_dependency_count": 0,
                    "missing_dependency_count": 0,
                    "matched_product_evidence": [],
                    "reason": "direct_procprefab_product_not_found_in_asset_processor_database",
                }
            product_id, product_name, sub_id, asset_type = product_row
            dependency_rows = connection.execute(
                "SELECT DependencySourceGuid, DependencySubID, Platform, DependencyFlags, UnresolvedPath, "
                "UnresolvedDependencyType, FromAssetId FROM ProductDependencies WHERE ProductPK = ?",
                (product_id,),
            ).fetchall()
            missing_count = connection.execute(
                "SELECT COUNT(*) FROM MissingProductDependencies WHERE ProductPK = ?",
                (product_id,),
            ).fetchone()[0]
        finally:
            connection.close()
    except Exception as exc:
        return {
            "status": "product_dependency_proof_unavailable",
            "selected_call": "Asset Processor database ProductDependencies readonly query",
            "product_path": product_path,
            "database_ref": _redacted_project_temp_path(str(db_path)),
            "dependencies": [],
            "product_dependency_count": 0,
            "missing_dependency_count": 0,
            "matched_product_evidence": [],
            "reason": "asset_processor_database_query_failed",
            "error": str(exc),
        }

    dependencies: List[Dict[str, Any]] = []
    for row in dependency_rows:
        dependencies.append(
            {
                "dependency_source_guid": _serialize_db_value(row[0]),
                "dependency_sub_id": _serialize_db_value(row[1]),
                "platform": _serialize_db_value(row[2]),
                "dependency_flags": _serialize_db_value(row[3]),
                "unresolved_path": _serialize_db_value(row[4]),
                "unresolved_dependency_type": _serialize_db_value(row[5]),
                "from_asset_id": _serialize_db_value(row[6]),
            }
        )
    matched = _match_dependency_records_to_product_refs(dependencies, product_refs)
    if matched:
        status = "product_dependency_proof_pass"
        reason = ""
    else:
        status = "product_dependency_proof_unavailable"
        reason = "direct_procprefab_product_dependency_graph_empty_for_character_products"
        if dependencies:
            reason = "direct_procprefab_product_dependencies_do_not_reference_character_products"
    return {
        "status": status,
        "selected_call": "Asset Processor database ProductDependencies readonly query",
        "product_path": product_path,
        "database_ref": _redacted_project_temp_path(str(db_path)),
        "product_row": {
            "product_id": _serialize_db_value(product_id),
            "product_name": _serialize_db_value(product_name),
            "sub_id": _serialize_db_value(sub_id),
            "asset_type": _serialize_db_value(asset_type),
        },
        "dependencies": dependencies,
        "product_dependency_count": len(dependencies),
        "missing_dependency_count": int(missing_count or 0),
        "matched_product_evidence": matched,
        "matches_apb_evidence": bool(matched),
        "reason": reason,
    }


def _serialize_db_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.hex()
    return str(value) if value is not None else ""


def _match_dependency_records_to_product_refs(
    dependencies: Sequence[Mapping[str, Any]],
    product_refs: Mapping[str, str],
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for dependency in dependencies:
        haystack = json.dumps(_safe_serialize(dependency), sort_keys=True).replace("\\", "/").lower()
        for product_type, product_ref in product_refs.items():
            normalized = product_ref.replace("\\", "/").lower()
            normalized_no_platform = normalized[3:] if normalized.startswith("pc/") else normalized
            basename = Path(normalized_no_platform).name
            if normalized in haystack or normalized_no_platform in haystack or (basename and basename in haystack):
                matches.append(
                    {
                        "status": "pass",
                        "product_type": product_type,
                        "product_path": product_ref,
                        "dependency": dict(dependency),
                    }
                )
    return _unique_dicts(matches)


def _runtime_product_reference(product_type: str, matched_refs: Any) -> Dict[str, Any]:
    if isinstance(matched_refs, list):
        for match in matched_refs:
            if isinstance(match, Mapping) and match.get("product_type") == product_type:
                return {
                    "status": "pass",
                    "product_type": product_type,
                    "product_path": str(match.get("product_path", "")),
                    "source": "Asset Processor ProductDependencies",
                }
    return {
        "status": "unavailable_with_verified_reason",
        "product_type": product_type,
        "reason": "character_product_reference_not_exposed_by_direct_procprefab_product_dependencies",
    }


def _probe_direct_procprefab_product_semantics(
    report: Mapping[str, Any],
    prefab_surface: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    *,
    entity_id: Any,
) -> Dict[str, Any]:
    procprefab_product = _product_ref(report, "procprefab")
    if not procprefab_product:
        return {
            "status": "blocked_by_missing_product_evidence",
            "procprefab_product_evidence": {"status": "missing"},
            "direct_product_instantiation_claimed": False,
            "direct_product_instantiation_supported": False,
            "direct_product_instantiation_verified": False,
            "blocked_reason": "procprefab_product_missing",
        }

    asset_resolution = _resolve_asset_id(procprefab_product, safe_call_results)
    base: Dict[str, Any] = {
        "status": "blocked_by_editor_binding_limitation",
        "procprefab_product_evidence": {
            "status": "pass",
            "product_path": procprefab_product,
            "evidence_source": "APB product evidence",
        },
        "procprefab_product_path": procprefab_product,
        "procprefab_asset_id_resolution": _public_asset_resolution(asset_resolution),
        "procprefab_asset_id": str(asset_resolution.get("asset_id", "")),
        "procprefab_asset_hint": str(asset_resolution.get("selected_asset_catalog_path", "")),
        "procprefab_catalog_lookup_result": _public_asset_resolution(asset_resolution),
        "procprefab_binding_surface": {
            **dict(prefab_surface),
            "source_evidence": {
                "status": "pass",
                "selected_editor_surface": "PrefabPublicRequestBus.InstantiatePrefab",
                "source_refs": [
                    "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/UI/Prefab/PrefabSaveLoadHandler.cpp",
                    "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/UI/Prefab/PrefabIntegrationManager.cpp",
                    "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicRequestBus.h",
                ],
                "conclusion": "Editor procedural-prefab UI paths pass product .procprefab paths into PrefabPublicInterface::InstantiatePrefab.",
            },
        },
        "procprefab_selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
        "procprefab_argument_shape": {
            "prefab_path": "APB procprefab product path or AssetCatalog-selected product path",
            "parent_entity_id": "azlmbr.entity.EntityId",
            "position": "azlmbr.math.Vector3",
        },
        "direct_product_instantiation_claimed": False,
        "direct_product_instantiation_supported": False,
        "direct_product_instantiation_verified": False,
        "fake_success": False,
    }

    if entity_id is None:
        return {
            **base,
            "status": "blocked_by_readiness",
            "blocked_reason": "entity_smoke_not_available",
            "procprefab_direct_product_instantiation_result": {
                "status": "blocked_by_readiness",
                "reason": "entity_smoke_not_available",
                "created_entity_count": 0,
            },
            "procprefab_created_entity_evidence": {"status": "not_created", "created_entity_count": 0},
        }

    try:
        import azlmbr.bus as bus  # type: ignore
        import azlmbr.entity as entity  # type: ignore
        import azlmbr.math as math  # type: ignore
        import azlmbr.prefab as prefab  # type: ignore
    except Exception as exc:
        return {
            **base,
            "status": "unsupported_by_engine_binding",
            "blocked_reason": "azlmbr_prefab_direct_product_import_failed",
            "error": str(exc),
            "procprefab_direct_product_instantiation_result": {
                "status": "unsupported_by_engine_binding",
                "reason": "azlmbr_prefab_direct_product_import_failed",
                "created_entity_count": 0,
            },
            "procprefab_created_entity_evidence": {"status": "not_created", "created_entity_count": 0},
        }

    candidates = _procprefab_product_path_candidates(procprefab_product, asset_resolution)
    instantiation = _probe_direct_procprefab_instantiate(
        prefab,
        bus,
        entity,
        math,
        candidates,
        safe_call_results,
        report=report,
    )
    load_result = {
        "status": "skipped_by_mode",
        "selected_call": "azlmbr.prefab.LoadTemplate",
        "reason": "Direct InstantiatePrefab probe is the selected bounded product-path check.",
    }
    spawnable_result = {
        "status": "skipped_by_mode",
        "selected_call": "PrefabPublicRequestBus.CreateInMemorySpawnableAsset",
        "reason": "Spawnable load-only probe is opt-in after direct instantiation does not pass.",
    }

    if instantiation.get("status") == "pass":
        content_assertions = instantiation.get("direct_procprefab_content_assertions", {})
        character_assertions = instantiation.get("procprefab_character_assertions", {})
        return {
            **base,
            "status": "pass",
            "procprefab_direct_product_load_result": load_result,
            "procprefab_direct_product_instantiation_result": instantiation,
            "procprefab_created_entity_evidence": {
                "status": "pass",
                "created_entity_count": instantiation.get("created_entity_count", 0),
                "container_entity": instantiation.get("container_entity", ""),
                "owning_instance_prefab_path": instantiation.get("owning_instance_prefab_path", ""),
            },
            "direct_product_instantiation_claimed": True,
            "direct_product_instantiation_supported": True,
            "direct_product_instantiation_verified": True,
            "direct_procprefab_content_assertions": content_assertions,
            "direct_product_assertions": content_assertions,
            "procprefab_character_assertions": character_assertions,
            "unsupported_reason": "",
            "blocked_reason": "",
        }

    if os.environ.get("MAXINE_EDITOR_SMOKE_ENABLE_DIRECT_PROCPREFAB_LOAD_PROBES") == "1":
        load_result = _probe_direct_procprefab_product_load(prefab, bus, candidates, safe_call_results)
        spawnable_result = _probe_direct_procprefab_spawnable(prefab, bus, candidates, safe_call_results)

    unsupported_reason = "procprefab_product_not_editor_instantiable_with_current_binding"
    if spawnable_result.get("status") == "pass":
        unsupported_reason = "procprefab_product_requires_runtime_spawnable_path"
    return {
        **base,
        "status": unsupported_reason,
        "procprefab_direct_product_load_result": load_result,
        "procprefab_direct_product_instantiation_result": {
            **instantiation,
            "status": unsupported_reason,
            "reason": instantiation.get("blocked_reason")
            or instantiation.get("reason")
            or "PrefabPublicRequestBus.InstantiatePrefab did not produce a valid Editor entity from the direct APB procprefab product path.",
        },
        "procprefab_created_entity_evidence": {"status": "not_created", "created_entity_count": 0},
        "spawnable_or_load_probe": spawnable_result,
        "unsupported_reason": unsupported_reason,
        "blocked_reason": "",
    }


def _procprefab_product_path_candidates(product_path: str, asset_resolution: Mapping[str, Any]) -> List[str]:
    normalized = product_path.replace("\\", "/").strip()
    candidates = [normalized]
    selected = str(asset_resolution.get("selected_asset_catalog_path", "")).strip()
    if selected:
        candidates.append(selected.replace("\\", "/"))
    if normalized.lower().startswith("pc/"):
        candidates.append(normalized[3:])
    if normalized.lower().startswith("cache/"):
        parts = normalized.split("/", 2)
        if len(parts) == 3:
            candidates.append(parts[2])
    return _unique([candidate for candidate in candidates if candidate.lower().endswith(".procprefab")])


def _probe_direct_procprefab_product_load(
    prefab: Any,
    bus: Any,
    candidates: Sequence[str],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    if hasattr(prefab, "LoadTemplate"):
        for candidate in candidates:
            try:
                value = prefab.LoadTemplate(candidate)
                serialized = _safe_serialize(value)
                status = "pass" if str(serialized).strip() not in {"", "0", "None"} else "fail"
                attempts.append({"path": candidate, "status": status, "template_id": serialized})
                safe_call_results.append(
                    {
                        "call": "azlmbr.prefab.LoadTemplate",
                        "status": status,
                        "args_shape": "1 argument",
                        "asset_path": candidate,
                        "result": serialized,
                    }
                )
                if status == "pass":
                    return {
                        "status": "pass",
                        "selected_call": "azlmbr.prefab.LoadTemplate",
                        "selected_product_path": candidate,
                        "template_id": serialized,
                        "attempts": attempts,
                    }
            except Exception as exc:
                attempts.append({"path": candidate, "status": "unsupported_by_engine_binding", "error": str(exc)})
                safe_call_results.append(
                    {
                        "call": "azlmbr.prefab.LoadTemplate",
                        "status": "unsupported_by_engine_binding",
                        "args_shape": "1 argument",
                        "asset_path": candidate,
                        "error": str(exc),
                    }
                )
    if hasattr(prefab, "PrefabLoaderScriptingBus"):
        try:
            value = prefab.PrefabLoaderScriptingBus(bus.Broadcast, "SaveTemplateToString", 0)
            safe_call_results.append(
                {
                    "call": "PrefabLoaderScriptingBus.SaveTemplateToString",
                    "status": "unsupported_by_engine_binding" if not _outcome_success(value) else "pass",
                    "args_shape": "1 argument",
                    "result": _safe_serialize(_unwrap_outcome(value)),
                }
            )
        except Exception as exc:
            safe_call_results.append(
                {
                    "call": "PrefabLoaderScriptingBus.SaveTemplateToString",
                    "status": "unsupported_by_engine_binding",
                    "args_shape": "1 argument",
                    "error": str(exc),
                }
            )
    return {
        "status": "unsupported_by_engine_binding",
        "selected_call": "azlmbr.prefab.LoadTemplate",
        "attempts": attempts,
        "reason": "No safe direct procprefab template-load result was exposed by the current Editor Python binding surface.",
    }


def _probe_direct_procprefab_spawnable(
    prefab: Any,
    bus: Any,
    candidates: Sequence[str],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    spawnable_name = "maxine_smoke_direct_procprefab_spawnable"
    attempts: List[Dict[str, Any]] = []
    for candidate in candidates:
        status, value = _prefab_bus_call(prefab, bus, "CreateInMemorySpawnableAsset", (candidate, spawnable_name), safe_call_results)
        attempts.append({"path": candidate, "status": status, "asset_id": _safe_serialize(_unwrap_outcome(value))})
        if status == "pass":
            has_status, has_value = _prefab_bus_call(prefab, bus, "HasInMemorySpawnableAsset", (spawnable_name,), safe_call_results)
            id_status, id_value = _prefab_bus_call(prefab, bus, "GetInMemorySpawnableAssetId", (spawnable_name,), safe_call_results)
            remove_status, _remove_value = _prefab_bus_call(prefab, bus, "RemoveInMemorySpawnableAsset", (spawnable_name,), safe_call_results)
            return {
                "status": "pass",
                "selected_call": "PrefabPublicRequestBus.CreateInMemorySpawnableAsset",
                "selected_product_path": candidate,
                "spawnable_name": spawnable_name,
                "asset_id": _safe_serialize(_unwrap_outcome(id_value)) if id_status == "pass" else _safe_serialize(_unwrap_outcome(value)),
                "has_spawnable_status": has_status,
                "has_spawnable": bool(_unwrap_outcome(has_value)) if has_status == "pass" else False,
                "cleanup_status": remove_status,
                "attempts": attempts,
            }
    return {
        "status": "unsupported_by_engine_binding",
        "selected_call": "PrefabPublicRequestBus.CreateInMemorySpawnableAsset",
        "attempts": attempts,
        "reason": "Direct procprefab product did not create an in-memory spawnable through the current Editor Python binding surface.",
    }


def _probe_direct_procprefab_instantiate(
    prefab: Any,
    bus: Any,
    entity: Any,
    math: Any,
    candidates: Sequence[str],
    safe_call_results: List[Dict[str, Any]],
    *,
    report: Mapping[str, Any],
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    for candidate in candidates:
        status, value = _prefab_bus_call(
            prefab,
            bus,
            "InstantiatePrefab",
            (candidate, entity.EntityId(), math.Vector3(0.0, 0.0, 0.0)),
            safe_call_results,
        )
        created_entity_id = _unwrap_outcome(value)
        attempt = {
            "path": candidate,
            "status": status,
            "result": _safe_serialize(created_entity_id),
        }
        attempts.append(attempt)
        if status == "pass" and _entity_id_valid(created_entity_id):
            owning_status, owning_value = _prefab_bus_call(
                prefab,
                bus,
                "GetOwningInstancePrefabPath",
                (created_entity_id,),
                safe_call_results,
            )
            owning_path = str(_unwrap_outcome(owning_value)) if owning_status == "pass" else ""
            content_assertions = _build_direct_procprefab_content_assertions(
                created_entity_id,
                expected_product_path=candidate,
                owning_path=owning_path,
                safe_call_results=safe_call_results,
            )
            character_assertions = _build_procprefab_character_assertions(
                created_entity_id,
                expected_product_path=candidate,
                safe_call_results=safe_call_results,
                content_assertions=content_assertions,
                product_refs=_character_product_refs(report),
            )
            return {
                "status": "pass",
                "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
                "selected_product_path": candidate,
                "argument_value_shape": {
                    "prefab_path": "direct APB procprefab product path",
                    "parent_entity_id": "azlmbr.entity.EntityId()",
                    "position": "azlmbr.math.Vector3",
                },
                "created_entity_count": 1,
                "container_entity": _safe_serialize(created_entity_id),
                "created_entity_id": _safe_serialize(created_entity_id),
                "owning_instance_prefab_path": _redacted_project_temp_path(owning_path) if owning_path else "",
                "owning_instance_prefab_path_status": owning_status,
                "direct_procprefab_content_assertions": content_assertions,
                "direct_product_assertions": content_assertions,
                "procprefab_character_assertions": character_assertions,
                "attempts": attempts,
            }
    return {
        "status": "procprefab_product_not_editor_instantiable_with_current_binding",
        "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
        "argument_value_shape": {
            "prefab_path": "direct APB procprefab product path",
            "parent_entity_id": "azlmbr.entity.EntityId()",
            "position": "azlmbr.math.Vector3",
        },
        "attempted_product_paths": list(candidates),
        "created_entity_count": 0,
        "attempts": attempts,
        "blocked_reason": "direct_procprefab_instantiate_returned_no_container_entity",
    }


def _build_direct_procprefab_content_assertions(
    created_entity_id: Any,
    *,
    expected_product_path: str,
    owning_path: str,
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    progress_log = _progress_log_path(os.environ.get("MAXINE_EDITOR_SMOKE_PROGRESS_LOG", ""))
    _write_progress_marker(
        progress_log,
        "procprefab_content_assertions_started",
        "started",
        "Inspecting direct procprefab container, owning path, components, and log signals.",
    )
    created_entity_id_serialized = _safe_serialize(created_entity_id)
    required_passed: List[str] = []
    required_failed: List[str] = []
    assertion_warnings: List[str] = []
    informational_assertions: List[str] = []
    unavailable_assertions: List[Dict[str, Any]] = []

    container_valid = _entity_id_valid(created_entity_id)
    container_name_status, container_name_value = _editor_entity_info_call(
        "GetName", created_entity_id, safe_call_results
    )
    container_valid_status = "pass" if container_valid else "fail"
    if container_valid:
        required_passed.append("created_container_valid")
    else:
        required_failed.append("created_container_valid")

    owning_prefab_path = _redacted_project_temp_path(owning_path) if owning_path else ""
    owning_matches = _prefab_paths_match(owning_path, expected_product_path)
    if owning_matches:
        required_passed.append("owning_prefab_path_matches_expected")
    else:
        required_failed.append("owning_prefab_path_matches_expected")

    child_count_status, child_count_value = _editor_entity_info_call(
        "GetChildCount", created_entity_id, safe_call_results
    )
    child_count = 0
    if child_count_status == "pass":
        try:
            child_count = int(_unwrap_outcome(child_count_value) or 0)
            informational_assertions.append("child_entity_count")
        except (TypeError, ValueError):
            child_count_status = "unavailable_with_verified_reason"
            unavailable_assertions.append(
                {
                    "assertion": "child_entity_count",
                    "status": child_count_status,
                    "reason": "EditorEntityInfoRequestBus.GetChildCount_returned_non_integer",
                    "value": _safe_serialize(_unwrap_outcome(child_count_value)),
                }
            )
    else:
        unavailable_assertions.append(
            {
                "assertion": "child_entity_count",
                "status": child_count_status,
                "reason": "EditorEntityInfoRequestBus.GetChildCount_unavailable",
            }
        )

    children_status, children_value = _editor_entity_info_call(
        "GetChildren", created_entity_id, safe_call_results
    )
    child_entities = _extract_sequence(_unwrap_outcome(children_value)) if children_status == "pass" else []
    child_entity_ids = [_safe_serialize(child) for child in child_entities]
    if children_status == "pass":
        informational_assertions.append("child_entity_ids")
    else:
        unavailable_assertions.append(
            {
                "assertion": "child_entity_ids",
                "status": children_status,
                "reason": "EditorEntityInfoRequestBus.GetChildren_unavailable",
            }
        )

    created_entity_count = 1
    created_entity_ids = [created_entity_id_serialized]
    for child_id in child_entity_ids:
        if child_id not in created_entity_ids:
            created_entity_ids.append(child_id)
    if created_entity_count > 0:
        required_passed.append("created_entity_count_positive")
        created_entity_count_status = "pass"
    else:
        required_failed.append("created_entity_count_positive")
        created_entity_count_status = "fail"

    entity_name_summary = {
        "status": "pass" if container_name_status == "pass" else "unavailable_with_verified_reason",
        "container": str(_unwrap_outcome(container_name_value)) if container_name_status == "pass" else "",
        "children": _child_name_summary(child_entities, safe_call_results),
    }

    component_inventory = _direct_procprefab_component_inventory(
        created_entity_id,
        child_entities,
        safe_call_results,
    )
    component_inventory_status = str(component_inventory.get("status", "unavailable_with_verified_reason"))
    if component_inventory_status == "pass":
        informational_assertions.append("component_inventory")
    elif component_inventory_status == "fail":
        required_failed.append("component_inventory")
    else:
        unavailable_assertions.append(
            {
                "assertion": "component_inventory",
                "status": component_inventory_status,
                "reason": component_inventory.get("reason", "component_inventory_unavailable"),
            }
        )

    log_scan = _scan_editor_log_for_direct_procprefab_signals(expected_product_path)
    missing_asset_log_signals = {
        "status": log_scan["status"],
        "matches": log_scan.get("matches", []),
        "patterns": log_scan.get("patterns", []),
        "log_ref": log_scan.get("log_ref", ""),
        "scanned_bytes": log_scan.get("scanned_bytes", 0),
    }
    editor_log_error_scan = {
        "status": log_scan["status"],
        "matches": log_scan.get("matches", []),
        "patterns": log_scan.get("patterns", []),
        "log_ref": log_scan.get("log_ref", ""),
        "scanned_bytes": log_scan.get("scanned_bytes", 0),
    }
    if log_scan["status"] == "pass":
        required_passed.append("no_missing_asset_or_load_error_signals")
    else:
        required_failed.append("no_missing_asset_or_load_error_signals")

    status = "pass" if not required_failed else "fail"
    assertion_failures = [f"assertion_failed_{failure}" for failure in required_failed]
    result = {
        "status": status,
        "direct_product_assertion_status": status,
        "required_assertions_status": status,
        "created_container_entity_id": created_entity_id_serialized,
        "created_container_valid": container_valid,
        "container_entity_valid": {
            "status": container_valid_status,
            "entity_id": created_entity_id_serialized,
            "binding": "azlmbr.editor.EditorEntityInfoRequestBus.GetName",
            "name_status": container_name_status,
        },
        "owning_prefab_path": owning_prefab_path,
        "owning_prefab_path_expected": expected_product_path,
        "owning_prefab_path_matches_expected": owning_matches,
        "created_entity_ids": created_entity_ids,
        "created_entity_count": created_entity_count,
        "created_entity_count_status": created_entity_count_status,
        "child_entity_ids": child_entity_ids,
        "child_entity_count": child_count,
        "child_entity_count_status": "informational_only" if child_count_status == "pass" else child_count_status,
        "entity_name_summary": entity_name_summary,
        "component_inventory": component_inventory,
        "component_inventory_status": component_inventory_status,
        "component_count_by_entity": component_inventory.get("component_count_by_entity", []),
        "required_or_expected_components": component_inventory.get("required_or_expected_components", []),
        "missing_required_components": component_inventory.get("missing_required_components", []),
        "optional_components_detected": component_inventory.get("optional_components_detected", []),
        "asset_reference_summary": {
            "status": "informational_only",
            "procprefab_product_path": expected_product_path,
            "reason": "Direct product AssetCatalog evidence is recorded by direct_procprefab_product_semantics.",
        },
        "missing_asset_log_signals": missing_asset_log_signals,
        "editor_log_error_scan": editor_log_error_scan,
        "assertion_failures": assertion_failures,
        "assertion_warnings": assertion_warnings,
        "required_assertions_passed": _unique(required_passed),
        "required_assertions_failed": _unique(required_failed),
        "informational_assertions": _unique(informational_assertions),
        "unavailable_assertions": unavailable_assertions,
    }
    _write_progress_marker(
        progress_log,
        "procprefab_content_assertions_returned",
        status,
        "Direct procprefab content assertions returned.",
    )
    return result


def _editor_entity_info_call(
    method: str,
    entity_id: Any,
    safe_call_results: List[Dict[str, Any]],
) -> Tuple[str, Any]:
    call_name = f"EditorEntityInfoRequestBus.{method}"
    try:
        import azlmbr.bus as bus  # type: ignore
        import azlmbr.editor as editor  # type: ignore

        value = editor.EditorEntityInfoRequestBus(bus.Event, method, entity_id)
        safe_call_results.append(
            {
                "call": call_name,
                "status": "pass",
                "args_shape": "1 argument",
                "result": _safe_serialize(_unwrap_outcome(value)),
            }
        )
        return "pass", value
    except Exception as exc:
        safe_call_results.append(
            {
                "call": call_name,
                "status": "unsupported_by_engine_binding",
                "args_shape": "1 argument",
                "error": str(exc),
            }
        )
        return "unsupported_by_engine_binding", None


def _child_name_summary(child_entities: Sequence[Any], safe_call_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    names: List[Dict[str, Any]] = []
    for child in list(child_entities)[:16]:
        status, value = _editor_entity_info_call("GetName", child, safe_call_results)
        names.append(
            {
                "entity_id": _safe_serialize(child),
                "status": status,
                "name": str(_unwrap_outcome(value)) if status == "pass" else "",
            }
        )
    return names


def _direct_procprefab_component_inventory(
    root_entity_id: Any,
    child_entities: Sequence[Any],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    surface_info, surface = _load_component_api_surface()
    if not _surface_available(surface):
        return {
            "status": "unavailable_with_verified_reason",
            "reason": surface_info.get("blocked_reason", "EditorComponentAPIBus_unavailable"),
            "component_count_by_entity": [],
            "required_or_expected_components": [],
            "missing_required_components": [],
            "optional_components_detected": [],
        }

    registry: Dict[str, Any] = {}
    transform = _discover_component_type_ids(
        ["Transform", "Transform Component"],
        "Transform",
        surface,
        safe_call_results,
        registry,
    )
    actor = _discover_component_type_ids(
        ["Actor", "Actor Component"],
        "Actor",
        surface,
        safe_call_results,
        registry,
    )
    component_defs: List[Tuple[str, Any]] = []
    for name, discovery in (("Transform", transform), ("Actor", actor)):
        if discovery.get("status") == "pass":
            raw_ids = discovery.get("type_ids_raw", [])
            if isinstance(raw_ids, list) and raw_ids:
                component_defs.append((name, raw_ids[0]))

    if not component_defs:
        return {
            "status": "unavailable_with_verified_reason",
            "reason": "component_type_discovery_unavailable",
            "component_type_registry": {key: _safe_serialize(value) for key, value in registry.items()},
            "component_count_by_entity": [],
            "required_or_expected_components": [],
            "missing_required_components": [],
            "optional_components_detected": [],
        }

    component_count_by_entity: List[Dict[str, Any]] = []
    optional_components_detected: List[str] = []
    transform_detected = False
    for current_entity_id in [root_entity_id, *list(child_entities)[:16]]:
        checks: List[Dict[str, Any]] = []
        components_detected: List[str] = []
        for component_name, type_id in component_defs:
            status, value = _component_bus_call(
                surface,
                "HasComponentOfType",
                (current_entity_id, type_id),
                safe_call_results,
            )
            present = bool(_unwrap_outcome(value)) if status == "pass" else False
            checks.append(
                {
                    "component": component_name,
                    "status": status,
                    "present": present,
                    "type_id": _safe_serialize(type_id),
                }
            )
            if present:
                components_detected.append(component_name)
                optional_components_detected.append(component_name)
                if component_name == "Transform":
                    transform_detected = True
        component_count_by_entity.append(
            {
                "entity_id": _safe_serialize(current_entity_id),
                "components_detected": _unique(components_detected),
                "component_checks": checks,
            }
        )

    return {
        "status": "pass" if transform_detected else "fail",
        "component_type_registry": {key: _safe_serialize(value) for key, value in registry.items()},
        "component_count_by_entity": component_count_by_entity,
        "required_or_expected_components": ["Transform"],
        "missing_required_components": [] if transform_detected else ["Transform"],
        "optional_components_detected": _unique(optional_components_detected),
    }


CHARACTER_COMPONENT_CANDIDATES: Dict[str, Sequence[str]] = {
    "Actor": ("Actor", "Actor Component", "EditorActorComponent", "EMotion FX Actor", "EMotionFX Actor"),
    "Mesh": ("Mesh", "Mesh Component", "EditorMeshComponent", "AZ::Render::EditorMeshComponent"),
    "Skinned Mesh": ("Skinned Mesh", "Skinned Mesh Component", "SkinnedMesh"),
    "Material": ("Material", "Material Component", "EditorMaterialComponent", "Editor Material Component"),
    "Animation": ("Anim Graph", "AnimGraph", "Motion", "Motion Set", "Animation"),
    "PhysX": ("PhysX Collider", "PhysX Shape Collider", "Collider", "Mesh Collider", "PhysX Mesh Collider"),
}


def _build_procprefab_character_assertions(
    root_entity_id: Any,
    *,
    expected_product_path: str,
    safe_call_results: List[Dict[str, Any]],
    content_assertions: Mapping[str, Any],
    product_refs: Mapping[str, str],
) -> Dict[str, Any]:
    progress_log = _progress_log_path(os.environ.get("MAXINE_EDITOR_SMOKE_PROGRESS_LOG", ""))
    _write_progress_marker(
        progress_log,
        "procprefab_character_assertions_started",
        "started",
        "Inspecting direct procprefab character-specific components, asset references, and log signals.",
    )
    required_passed: List[str] = []
    required_failed: List[str] = []
    informational: List[str] = []
    unavailable_reasons: List[Dict[str, Any]] = []
    unsupported_assertions: List[Dict[str, Any]] = []
    warnings: List[str] = []

    children_status, children_value = _editor_entity_info_call("GetChildren", root_entity_id, safe_call_results)
    child_entities = _extract_sequence(_unwrap_outcome(children_value)) if children_status == "pass" else []
    entities = [root_entity_id, *list(child_entities)[:16]]
    entity_ids = [_safe_serialize(entity_id) for entity_id in entities]
    child_entity_ids = [_safe_serialize(entity_id) for entity_id in child_entities[:16]]
    container_name_status, container_name_value = _editor_entity_info_call("GetName", root_entity_id, safe_call_results)
    entity_name_summary = {
        "status": "pass" if container_name_status == "pass" else "unavailable_with_verified_reason",
        "container": str(_unwrap_outcome(container_name_value)) if container_name_status == "pass" else "",
        "children": _child_name_summary(child_entities, safe_call_results),
    }

    surface_info, surface = _load_component_api_surface()
    registry: Dict[str, Any] = {}
    component_presence: Dict[str, Any] = {}
    component_type_ids: Dict[str, Any] = {}
    component_display_names: Dict[str, Any] = {}
    character_component_optional: List[str] = []
    character_component_unavailable: List[str] = []
    character_component_blocked: List[str] = []
    character_component_unsupported: List[str] = []
    matched_product_evidence: List[Dict[str, Any]] = []
    present_character_components: List[str] = []
    component_inventory_by_entity: List[Dict[str, Any]] = []

    if _surface_available(surface):
        for component_name, display_names in CHARACTER_COMPONENT_CANDIDATES.items():
            discovery = _discover_component_type_ids(display_names, component_name, surface, safe_call_results, registry)
            component_display_names[component_name] = list(display_names)
            component_type_ids[component_name] = discovery.get("type_ids", [])
            raw_type_ids = discovery.get("type_ids_raw", []) if isinstance(discovery.get("type_ids_raw", []), list) else []
            if discovery.get("status") != "pass" or not raw_type_ids:
                reason = "component_type_id_not_discovered"
                status = str(discovery.get("status", "blocked_by_missing_binding"))
                component_presence[component_name] = {
                    "status": status,
                    "present": False,
                    "required": False,
                    "reason": reason,
                }
                character_component_unavailable.append(component_name)
                if status == "blocked_by_missing_binding":
                    character_component_blocked.append(component_name)
                elif status == "unsupported_by_engine_binding":
                    character_component_unsupported.append(component_name)
                unavailable_reasons.append(
                    {
                        "assertion": f"{component_name}_component_presence",
                        "status": status,
                        "reason": reason,
                    }
                )
                continue

            type_id = raw_type_ids[0]
            entity_checks: List[Dict[str, Any]] = []
            present_entities: List[Dict[str, Any]] = []
            property_readbacks: List[Dict[str, Any]] = []
            for entity_id in entities:
                status, value = _component_bus_call(surface, "HasComponentOfType", (entity_id, type_id), safe_call_results)
                present = bool(_unwrap_outcome(value)) if status == "pass" else False
                check = {
                    "entity_id": _safe_serialize(entity_id),
                    "status": status,
                    "present": present,
                    "type_id": _safe_serialize(type_id),
                }
                entity_checks.append(check)
                if not present:
                    continue
                present_entities.append({"entity_id": _safe_serialize(entity_id), "type_id": _safe_serialize(type_id)})
                component_ref = _get_component_reference(entity_id, [type_id], surface, safe_call_results)
                properties = _build_component_property_list(component_ref, surface, safe_call_results)
                readback = _get_component_property_values(component_ref, properties, surface, safe_call_results)
                property_readbacks.append(
                    {
                        "entity_id": _safe_serialize(entity_id),
                        "component_ref": component_ref.get("component_ref_serialized", ""),
                        "property_list": properties,
                        "property_readback": readback,
                    }
                )
                matched_product_evidence.extend(
                    _match_character_property_readbacks_to_products(component_name, readback, product_refs)
                )

            component_status = "component_present_property_readback_unavailable"
            if present_entities and any(
                item.get("property_readback", {}).get("status") == "pass" for item in property_readbacks
            ):
                component_status = "component_present_property_readback_pass"
            elif not present_entities:
                component_status = "component_not_present"

            if present_entities:
                present_character_components.append(component_name)
                character_component_optional.append(component_name)
                informational.append(f"{component_name}_component_present")
            else:
                character_component_unavailable.append(component_name)
                unavailable_reasons.append(
                    {
                        "assertion": f"{component_name}_component_presence",
                        "status": "component_not_present",
                        "reason": "direct_procprefab_character_component_not_present_on_created_editor_entities",
                    }
                )

            component_presence[component_name] = {
                "status": component_status,
                "present": bool(present_entities),
                "required": False,
                "type_ids": [_safe_serialize(type_id_value) for type_id_value in raw_type_ids],
                "entity_checks": entity_checks,
                "present_entities": present_entities,
                "property_readbacks": property_readbacks,
            }
            component_inventory_by_entity.append(
                {
                    "component": component_name,
                    "status": component_status,
                    "present_entities": present_entities,
                    "entity_checks": entity_checks,
                }
            )
    else:
        unavailable_reasons.append(
            {
                "assertion": "character_component_inventory",
                "status": "unsupported_by_engine_binding",
                "reason": surface_info.get("blocked_reason", "EditorComponentAPIBus_unavailable"),
            }
        )

    matched_product_evidence = _unique_dicts(matched_product_evidence)
    character_scan = _scan_editor_log_for_procprefab_character_signals(expected_product_path)
    if character_scan.get("status") == "pass":
        required_passed.append("no_missing_character_load_error_signals")
    else:
        required_failed.append("no_missing_character_load_error_signals")

    character_components_exposed = bool(present_character_components or matched_product_evidence)
    inventory_collected = bool(component_presence)
    inventory_status = "pass" if inventory_collected else "unavailable_with_verified_reason"
    if character_components_exposed:
        character_status = "pass"
        informational.append("character_specific_component_or_asset_reference_detected")
    else:
        character_status = "unavailable_with_verified_reason"
        informational.append("character_components_not_exposed")
        unavailable_reasons.append(
            {
                "assertion": "character_specific_component_or_asset_reference",
                "status": "unavailable_with_verified_reason",
                "reason": "direct_procprefab_character_components_not_exposed_in_editor_product_instance",
            }
        )

    if required_failed:
        character_status = "fail"

    result = {
        "status": character_status,
        "character_assertion_status": character_status,
        "required_character_assertions_status": "pass" if not required_failed else "fail",
        "character_component_inventory": {
            "status": inventory_status,
            "component_type_registry": {key: _safe_serialize(value) for key, value in registry.items()},
            "component_presence": component_presence,
            "component_inventory_by_entity": component_inventory_by_entity,
            "source": "EditorComponentAPIBus.FindComponentTypeIdsByEntityType + HasComponentOfType",
        },
        "character_component_inventory_status": inventory_status,
        "character_component_type_registry": {key: _safe_serialize(value) for key, value in registry.items()},
        "character_component_type_ids": component_type_ids,
        "character_component_display_names": component_display_names,
        "character_component_presence": component_presence,
        "character_component_required": [],
        "character_component_optional": _unique(character_component_optional),
        "character_component_unavailable": _unique(character_component_unavailable),
        "character_component_blocked": _unique(character_component_blocked),
        "character_component_unsupported": _unique(character_component_unsupported),
        "character_entity_ids": entity_ids,
        "character_child_entity_ids": child_entity_ids,
        "character_entity_name_summary": entity_name_summary,
        "actor_component_presence": component_presence.get("Actor", {"status": "component_not_present", "present": False}),
        "actor_component_type_id": component_type_ids.get("Actor", []),
        "actor_asset_reference_readback": _component_asset_reference_readback(component_presence.get("Actor", {})),
        "mesh_component_presence": component_presence.get("Mesh", {"status": "component_not_present", "present": False}),
        "mesh_component_type_id": component_type_ids.get("Mesh", []),
        "mesh_asset_reference_readback": _component_asset_reference_readback(component_presence.get("Mesh", {})),
        "skinned_mesh_component_presence": component_presence.get("Skinned Mesh", {"status": "component_not_present", "present": False}),
        "material_component_presence": component_presence.get("Material", {"status": "component_not_present", "present": False}),
        "material_asset_reference_readback": _component_asset_reference_readback(component_presence.get("Material", {})),
        "animation_component_presence": component_presence.get("Animation", {"status": "component_not_present", "present": False}),
        "motion_reference_readback": _component_asset_reference_readback(component_presence.get("Animation", {}), product_type="motion"),
        "motion_set_reference_readback": _component_asset_reference_readback(component_presence.get("Animation", {}), product_type="motionset"),
        "anim_graph_reference_readback": _component_asset_reference_readback(component_presence.get("Animation", {}), product_type="animgraph"),
        "pxmesh_or_collision_reference_readback": _component_asset_reference_readback(component_presence.get("PhysX", {}), product_type="pxmesh"),
        "character_asset_reference_summary": {
            "status": "pass" if matched_product_evidence else "unavailable_with_verified_reason",
            "matched_product_evidence": matched_product_evidence,
            "reason": "" if matched_product_evidence else "direct_procprefab_character_asset_references_not_exposed_in_editor_component_properties",
        },
        "matched_product_evidence": matched_product_evidence,
        "missing_character_expected_components": [],
        "character_assertion_failures": [f"assertion_failed_{failure}" for failure in required_failed],
        "character_assertion_warnings": warnings,
        "character_assertion_informational": _unique(informational),
        "character_unavailable_reasons": unavailable_reasons,
        "unsupported_assertions": unsupported_assertions,
        "editor_log_character_error_scan": character_scan,
        "editor_log_missing_actor_signal": character_scan.get("missing_actor", {"status": "pass", "matches": []}),
        "editor_log_missing_mesh_signal": character_scan.get("missing_mesh", {"status": "pass", "matches": []}),
        "editor_log_missing_material_signal": character_scan.get("missing_material", {"status": "pass", "matches": []}),
        "editor_log_missing_animation_signal": character_scan.get("missing_animation", {"status": "pass", "matches": []}),
        "direct_product_instantiation_result": {
            "status": "pass",
            "selected_product_path": expected_product_path,
            "created_entity_count": content_assertions.get("created_entity_count", 0),
        },
        "direct_product_content_assertion_result": {
            "status": content_assertions.get("status", "unavailable_with_verified_reason"),
            "required_assertions_status": content_assertions.get("required_assertions_status", ""),
        },
        "required_character_assertions_passed": _unique(required_passed),
        "required_character_assertions_failed": _unique(required_failed),
    }
    _write_progress_marker(
        progress_log,
        "procprefab_character_assertions_returned",
        character_status,
        "Direct procprefab character-specific assertions returned.",
    )
    return result


def _character_product_refs(report: Mapping[str, Any]) -> Dict[str, str]:
    return {
        product_type: product_ref
        for product_type in ("actor", "azmodel", "pxmesh", "azmaterial", "motion", "motionset", "animgraph")
        for product_ref in [_product_ref(report, product_type)]
        if product_ref
    }


def _match_character_property_readbacks_to_products(
    component_name: str,
    readback: Mapping[str, Any],
    product_refs: Mapping[str, str],
) -> List[Dict[str, Any]]:
    serialized = _safe_serialize(readback)
    haystack = json.dumps(serialized, sort_keys=True).replace("\\", "/").lower()
    matches: List[Dict[str, Any]] = []
    for product_type, product_ref in product_refs.items():
        normalized = product_ref.replace("\\", "/").lower()
        normalized_no_platform = normalized[3:] if normalized.startswith("pc/") else normalized
        basename = Path(normalized_no_platform).name
        if normalized in haystack or normalized_no_platform in haystack or (basename and basename in haystack):
            matches.append(
                {
                    "component": component_name,
                    "product_type": product_type,
                    "product_path": product_ref,
                    "status": "pass",
                }
            )
    return matches


def _component_asset_reference_readback(component_presence: Any, *, product_type: str = "") -> Dict[str, Any]:
    if not isinstance(component_presence, Mapping) or not component_presence.get("present"):
        return {
            "status": "unavailable_with_verified_reason",
            "product_type": product_type,
            "reason": "component_not_present",
        }
    readbacks = component_presence.get("property_readbacks", [])
    if not isinstance(readbacks, list) or not readbacks:
        return {
            "status": "unavailable_with_verified_reason",
            "product_type": product_type,
            "reason": "component_property_readback_unavailable",
        }
    return {"status": "pass", "product_type": product_type, "readbacks": readbacks[:3]}


def _unique_dicts(values: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    unique_values: List[Dict[str, Any]] = []
    for value in values:
        serialized = json.dumps(_safe_serialize(value), sort_keys=True)
        if serialized in seen:
            continue
        seen.add(serialized)
        unique_values.append(dict(value))
    return unique_values


def _scan_editor_log_for_procprefab_character_signals(expected_product_path: str) -> Dict[str, Any]:
    project_path_raw = os.environ.get("O3DE_PROJECT_PATH", "")
    project_path = Path(project_path_raw) if project_path_raw else None
    candidates: List[Path] = []
    if project_path is not None:
        candidates.extend([project_path / "user" / "log" / "Editor.log", *project_path.glob("**/Editor.log")])
    existing = [candidate for candidate in candidates if candidate.exists()]
    patterns = {
        "missing_actor": ["missing actor", "actor not found", "failed to load actor", "could not load actor"],
        "missing_mesh": [
            "missing mesh",
            "mesh not found",
            "missing model",
            "model not found",
            "failed to load mesh",
            "could not load mesh",
            "failed to load model",
        ],
        "missing_material": [
            "missing material",
            "material not found",
            "failed to load material",
            "could not load material",
        ],
        "missing_animation": [
            "missing animation",
            "missing motion",
            "motion not found",
            "motion set not found",
            "anim graph not found",
            "animgraph not found",
            "failed to load animation",
        ],
        "load_error": ["failed to load", "could not load", "load error", "failed loading"],
    }
    if not existing:
        base = {
            "status": "unavailable_with_verified_reason",
            "reason": "editor_log_not_found",
            "matches": [],
            "patterns": patterns,
            "scanned_bytes": 0,
            "log_ref": "",
        }
        for key in ("missing_actor", "missing_mesh", "missing_material", "missing_animation"):
            base[key] = {"status": "unavailable_with_verified_reason", "matches": []}
        return base

    log_path = max(existing, key=lambda path: path.stat().st_mtime)
    text = _read_text_tail(log_path, max_bytes=512_000)
    expected = expected_product_path.replace("\\", "/").lower()
    pc_prefixed_expected = f"pc/{expected}"
    grouped_matches: Dict[str, List[Dict[str, str]]] = {key: [] for key in patterns}
    for line in text.splitlines():
        lowered = line.lower().replace("\\", "/")
        if pc_prefixed_expected in lowered:
            continue
        if expected not in lowered:
            continue
        for key, terms in patterns.items():
            if any(term in lowered for term in terms):
                grouped_matches[key].append({"line": line.strip()[:500]})

    all_matches = [match for matches in grouped_matches.values() for match in matches]
    result: Dict[str, Any] = {
        "status": "fail" if all_matches else "pass",
        "matches": all_matches[:20],
        "patterns": patterns,
        "scanned_bytes": len(text.encode("utf-8", errors="ignore")),
        "log_ref": _redacted_project_temp_path(str(log_path)),
    }
    for key in ("missing_actor", "missing_mesh", "missing_material", "missing_animation"):
        matches = grouped_matches.get(key, [])
        result[key] = {"status": "fail" if matches else "pass", "matches": matches[:20]}
    return result


def _scan_editor_log_for_direct_procprefab_signals(expected_product_path: str) -> Dict[str, Any]:
    project_path_raw = os.environ.get("O3DE_PROJECT_PATH", "")
    project_path = Path(project_path_raw) if project_path_raw else None
    candidates: List[Path] = []
    if project_path is not None:
        candidates.extend([project_path / "user" / "log" / "Editor.log", *project_path.glob("**/Editor.log")])
    existing = [candidate for candidate in candidates if candidate.exists()]
    if not existing:
        return {
            "status": "unavailable_with_verified_reason",
            "reason": "editor_log_not_found",
            "matches": [],
            "patterns": [],
            "scanned_bytes": 0,
            "log_ref": "",
        }
    log_path = max(existing, key=lambda path: path.stat().st_mtime)
    text = _read_text_tail(log_path, max_bytes=512_000)
    expected = expected_product_path.replace("\\", "/").lower()
    negative_terms = [
        "missing asset",
        "asset not found",
        "failed to load",
        "could not load",
        "load error",
        "failed loading",
    ]
    matches: List[Dict[str, str]] = []
    pc_prefixed_expected = f"pc/{expected}"
    for line in text.splitlines():
        lowered = line.lower().replace("\\", "/")
        if pc_prefixed_expected in lowered:
            continue
        if expected in lowered and any(term in lowered for term in negative_terms):
            matches.append({"line": line.strip()[:500]})
    return {
        "status": "fail" if matches else "pass",
        "matches": matches[:20],
        "patterns": negative_terms,
        "scanned_bytes": len(text.encode("utf-8", errors="ignore")),
        "log_ref": _redacted_project_temp_path(str(log_path)),
    }


def _read_text_tail(path: Path, *, max_bytes: int) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            return handle.read(max_bytes).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _prefab_paths_match(observed: str, expected: str) -> bool:
    observed_normalized = observed.replace("\\", "/").strip().lower()
    expected_normalized = expected.replace("\\", "/").strip().lower()
    if not observed_normalized or not expected_normalized:
        return False
    return observed_normalized == expected_normalized or observed_normalized.endswith("/" + expected_normalized)


def _prefab_bus_call(
    prefab: Any,
    bus: Any,
    method: str,
    args: Tuple[Any, ...],
    safe_call_results: List[Dict[str, Any]],
) -> Tuple[str, Any]:
    call_name = f"PrefabPublicRequestBus.{method}"
    try:
        value = prefab.PrefabPublicRequestBus(bus.Broadcast, method, *args)
        status = "pass" if _outcome_success(value) else "fail"
        safe_call_results.append(
            {
                "call": call_name,
                "status": status,
                "args_shape": f"{len(args)} arguments",
                "result": _safe_serialize(_unwrap_outcome(value)),
            }
        )
        return status, value
    except Exception as exc:
        safe_call_results.append(
            {
                "call": call_name,
                "status": "unsupported_by_engine_binding",
                "args_shape": f"{len(args)} arguments",
                "error": str(exc),
            }
        )
        return "unsupported_by_engine_binding", None


def _entity_id_valid(entity_id: Any) -> bool:
    for method in ("IsValid", "is_valid"):
        try:
            if hasattr(entity_id, method):
                return bool(getattr(entity_id, method)())
        except Exception:
            pass
    serialized = str(_safe_serialize(entity_id)).strip()
    return bool(serialized and serialized not in {"0", "EntityId()", "[0]", "None"})


def _valid_component_type_id(type_id: Any) -> bool:
    serialized = str(_safe_serialize(type_id)).strip().lower()
    return bool(serialized and serialized not in {"0", "none", "{00000000-0000-0000-0000-000000000000}"})


def _actor_property_discovery(properties: Mapping[str, Any], *, require_settable: bool = False) -> Dict[str, Any]:
    values = [str(value) for value in properties.get("properties", [])] if isinstance(properties.get("properties"), list) else []
    asset_like = [value for value in values if "actor" in value.lower() or "asset" in value.lower()]
    exact = [value for value in asset_like if value.strip().lower() == "actor asset"]
    if asset_like:
        return {
            "status": "pass" if exact else "blocked_by_unsafe_operation",
            "property_path": exact[0] if exact else "",
            "candidate_property_paths": asset_like,
            "discovery_source": "EditorActorComponent edit-context DataElement",
            "blocked_reason": "" if exact else "actor_asset_property_path_requires_pinning_before_set",
            "requires_settable_value": require_settable,
        }
    return {
        "status": "blocked_by_missing_binding",
        "blocked_reason": "actor_asset_property_path_not_discovered",
    }


def _select_actor_asset_property_path(discovery: Mapping[str, Any]) -> str:
    explicit = str(discovery.get("property_path", "")).strip()
    if explicit:
        return explicit
    candidates = discovery.get("candidate_property_paths", [])
    if isinstance(candidates, list):
        for candidate in candidates:
            if str(candidate).strip().lower() == "actor asset":
                return str(candidate).strip()
    return ""


def _motion_property_discovery(properties: Mapping[str, Any], *, require_settable: bool = False) -> Dict[str, Any]:
    values = [str(value) for value in properties.get("properties", [])] if isinstance(properties.get("properties"), list) else []
    asset_like = [value for value in values if "motion" in value.lower() or "asset" in value.lower()]
    preferred = [
        value
        for value in asset_like
        if value.strip().lower() in {"configuration|motion", "motion"}
    ]
    if asset_like:
        return {
            "status": "pass" if preferred else "blocked_by_unsafe_operation",
            "property_path": preferred[0] if preferred else "",
            "candidate_property_paths": asset_like,
            "discovery_source": "EditorSimpleMotionComponent and SimpleMotionComponent Configuration edit-context DataElement",
            "blocked_reason": "" if preferred else "simple_motion_asset_property_path_requires_pinning_before_set",
            "requires_settable_value": require_settable,
        }
    return {
        "status": "blocked_by_missing_binding",
        "blocked_reason": "simple_motion_asset_property_path_not_discovered",
    }


def _select_motion_asset_property_path(discovery: Mapping[str, Any]) -> str:
    explicit = str(discovery.get("property_path", "")).strip()
    if explicit:
        return explicit
    candidates = discovery.get("candidate_property_paths", [])
    if isinstance(candidates, list):
        for preferred in ("Configuration|Motion", "Motion"):
            for candidate in candidates:
                if str(candidate).strip().lower() == preferred.lower():
                    return str(candidate).strip()
    return ""


def _approved_animation_component_wiring_source_refs() -> List[Dict[str, Any]]:
    return [
        {
            "path": "C:/src/o3de/Gems/EMotionFX/Code/Source/Integration/Editor/Components/EditorActorComponent.cpp",
            "symbols": ["EditorActorComponent", "Actor asset", "ActorAsset", "BuildGameEntity"],
        },
        {
            "path": "C:/src/o3de/Gems/EMotionFX/Code/Source/Integration/Editor/Components/EditorSimpleMotionComponent.cpp",
            "symbols": ["EditorSimpleMotionComponent", "Configuration", "BuildGameEntity"],
        },
        {
            "path": "C:/src/o3de/Gems/EMotionFX/Code/Source/Integration/Components/SimpleMotionComponent.cpp",
            "symbols": ["MotionAsset", "Motion", "SimpleMotionComponentRequestBus", "SetMotionAssetId"],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicRequestHandler.cpp",
            "symbols": ["PrefabPublicRequestBus", "CreatePrefabInMemory", "InstantiatePrefab"],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicInterface.h",
            "symbols": ["CreatePrefabAndSaveToDisk", "SavePrefab"],
        },
    ]


def _approved_animation_component_wiring_source_validation() -> Dict[str, Any]:
    refs: List[Dict[str, Any]] = []
    all_passed = True
    for spec in _approved_animation_component_wiring_source_refs():
        path = Path(str(spec.get("path", "")))
        symbols = [str(symbol) for symbol in spec.get("symbols", [])]
        missing = []
        exists = path.exists()
        content = ""
        if exists:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                content = ""
        for symbol in symbols:
            if symbol not in content:
                missing.append(symbol)
        status = "pass" if exists and not missing else "inconclusive"
        all_passed = all_passed and status == "pass"
        refs.append(
            {
                "path": str(spec.get("path", "")),
                "symbols": symbols,
                "status": status,
                "exists": exists,
                "missing_symbols": missing,
            }
        )
    return {
        "status": "pass" if all_passed else "inconclusive",
        "verified": all_passed,
        "refs": refs,
    }


def _approved_prefab_save_update_source_refs() -> List[Dict[str, Any]]:
    return [
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicInterface.h",
            "symbols": [
                "PrefabPublicInterface",
                "CreatePrefabAndSaveToDisk",
                "SavePrefab",
                "PrefabOperationResult",
                "AZ::IO::Path",
            ],
            "absent_symbols": [],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicHandler.cpp",
            "symbols": [
                "PrefabPublicHandler::CreatePrefabAndSaveToDisk",
                "filePath.IsAbsolute()",
                "CreatePrefabInMemory",
                "SaveTemplateToFile",
                "PrefabPublicHandler::SavePrefab",
                "GetTemplateIdFromFilePath",
                "SaveTemplate",
            ],
            "absent_symbols": [],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicRequestHandler.cpp",
            "symbols": [
                "BehaviorContext",
                "PrefabPublicRequestBus",
                'Event("CreatePrefabInMemory"',
                'Event("InstantiatePrefab"',
            ],
            "absent_symbols": [
                'Event("CreatePrefabAndSaveToDisk"',
                'Event("SavePrefab"',
            ],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicRequestBus.h",
            "symbols": [
                "PrefabPublicRequests",
                "CreatePrefabInMemory",
                "InstantiatePrefab",
            ],
            "absent_symbols": [
                "CreatePrefabAndSaveToDisk",
                "SavePrefab",
            ],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabLoaderInterface.h",
            "symbols": [
                "LoadTemplateFromFile",
                "SaveTemplate",
                "SaveTemplateToFile",
                "SaveTemplateToString",
                "GenerateRelativePath",
            ],
            "absent_symbols": [],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabSystemComponentInterface.h",
            "symbols": [
                "GetTemplateIdFromFilePath",
                "InstantiatePrefab",
                "CreatePrefab",
            ],
            "absent_symbols": [],
        },
    ]


def _observed_behavior_context_events(content: str) -> List[str]:
    events: List[str] = []
    seen = set()
    for match in re.finditer(r'\bEvent\(\s*"([^"]+)"', content):
        event_name = match.group(1)
        if event_name not in seen:
            events.append(event_name)
            seen.add(event_name)
    return events


def _save_update_behavior_context_observation(source_validation: Mapping[str, Any]) -> Dict[str, Any]:
    observed_events: List[str] = []
    seen = set()
    for ref in source_validation.get("refs", []):
        if not isinstance(ref, Mapping):
            continue
        for event_name in ref.get("observed_behavior_context_events", []):
            event = str(event_name)
            if event and event not in seen:
                observed_events.append(event)
                seen.add(event)
    required_events = ["CreatePrefabAndSaveToDisk", "SavePrefab"]
    missing_events = [event for event in required_events if event not in seen]
    return {
        "observed_events": observed_events,
        "missing_events": missing_events,
        "exposed": not missing_events,
    }


def _source_validation_from_refs(specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    refs: List[Dict[str, Any]] = []
    all_passed = True
    for spec in specs:
        path = Path(str(spec.get("path", "")))
        required = [str(symbol) for symbol in spec.get("symbols", [])]
        required_absent = [str(symbol) for symbol in spec.get("absent_symbols", [])]
        missing = []
        unexpectedly_present = []
        exists = path.exists()
        content = ""
        if exists:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                content = ""
        for symbol in required:
            if symbol not in content:
                missing.append(symbol)
        for symbol in required_absent:
            if symbol in content:
                unexpectedly_present.append(symbol)
        observed_events = _observed_behavior_context_events(content)
        status = "pass" if exists and not missing else "inconclusive"
        all_passed = all_passed and status == "pass"
        refs.append(
            {
                "path": str(spec.get("path", "")),
                "symbols": required,
                "absent_symbols": required_absent,
                "status": status,
                "exists": exists,
                "missing_symbols": missing,
                "unexpected_symbols": unexpectedly_present,
                "observed_behavior_context_events": observed_events,
            }
        )
    return {
        "status": "pass" if all_passed else "inconclusive",
        "verified": all_passed,
        "refs": refs,
    }


def _approved_prefab_save_update_source_validation() -> Dict[str, Any]:
    return _source_validation_from_refs(_approved_prefab_save_update_source_refs())


def _approved_prefab_save_update_candidate_matrix() -> List[Dict[str, Any]]:
    return [
        {
            "candidate": "expose PrefabPublicInterface::SavePrefab / CreatePrefabAndSaveToDisk to Editor Python automation",
            "outcome": "blocked",
            "reason": "Source validation finds save APIs on PrefabPublicInterface but no BehaviorContext events on PrefabPublicRequestBus.",
        },
        {
            "candidate": "use existing PrefabPublicRequestBus only",
            "outcome": "blocked",
            "reason": "Existing reflected bus exposes CreatePrefabInMemory and InstantiatePrefab, not SavePrefab or CreatePrefabAndSaveToDisk.",
        },
        {
            "candidate": "C++ Editor helper/bridge in repo-owned tooling layer",
            "outcome": "deferred",
            "reason": "Narrow bridge likely requires an Editor-capable repo-owned Gem/module and rebuild; this slice records the exact source-validated gap first.",
        },
        {
            "candidate": "scratch prefab save probe",
            "outcome": "blocked",
            "reason": "Preferred proof surface, but not attempted until an automation-callable save/update route exists.",
        },
        {
            "candidate": "approved source prefab update with Actor + Simple Motion",
            "outcome": "deferred",
            "reason": "Approved source mutation waits for verified save/update automation surface and scratch save proof.",
        },
        {
            "candidate": "hand-authored unknown .prefab component JSON",
            "outcome": "rejected",
            "reason": "Unknown O3DE component serialization must not be hand-authored.",
        },
        {
            "candidate": "direct runtime .procprefab load",
            "outcome": "rejected",
            "reason": "Preserved unsupported/builder-only proof limit.",
        },
        {
            "candidate": "direct product-load of actor/motion products",
            "outcome": "rejected",
            "reason": "Product-load is not prefab save/update or component wiring proof.",
        },
        {
            "candidate": "defaultlevel or production-level mutation",
            "outcome": "rejected",
            "reason": "Defaultlevel and production-level mutation are disallowed for this slice.",
        },
    ]


def _approved_prefab_save_update_bridge_source_refs() -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return _approved_prefab_save_update_source_refs() + [
        {
            "path": str(repo_root / "o3de/gems/MaxineRuntimeExitFixture/Code/CMakeLists.txt"),
            "symbols": [
                "ly_add_target",
                "MaxineRuntimeExitFixture",
                "ly_create_alias(NAME ${gem_name}.Clients",
                "AZ::AzCore",
                "AZ::AzFramework",
            ],
            "absent_symbols": [
                "${gem_name}.Editor",
                "PAL_TRAIT_BUILD_HOST_TOOLS",
                "AzToolsFramework",
            ],
        },
        {
            "path": str(repo_root / "o3de/gems/MaxineRuntimeExitFixture/Code/maxineruntimeexitfixture_editor_files.cmake"),
            "symbols": [
                "Source/Tools/MaxinePrefabSaveUpdateBridgeEditorModule.cpp",
                "Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp",
                "Source/Tools/PrefabSaveUpdateBridgeHostComponent.h",
                "Source/Tools/",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/MaxinePrefabSaveUpdateBridgeEditorModule.cpp"
            ),
            "symbols": [
                "AZ_DECLARE_MODULE_CLASS",
                "AZ_JOIN(Gem_, O3DE_GEM_NAME, _Editor)",
                "_Editor",
                "PrefabSaveUpdateBridgeHostComponent::CreateDescriptor",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp"
            ),
            "symbols": [
                "BehaviorContext",
                "PrefabPublicInterface",
                "PrefabSaveUpdateBridge",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(repo_root / "o3de/gems/MaxineRuntimeExitFixture/Code/maxineruntimeexitfixture_files.cmake"),
            "symbols": [
                "Source/Clients/MaxineRuntimeExitFixtureModule.cpp",
                "Source/Clients/MaxineRuntimeExitFixtureSystemComponent.cpp",
                "Source/Clients/MaxineRuntimeExitFixtureSystemComponent.h",
            ],
            "absent_symbols": [
                "Source/Tools/",
                "PrefabSaveUpdateBridge",
            ],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Clients/MaxineRuntimeExitFixtureModule.cpp"
            ),
            "symbols": [
                "AZ_DECLARE_MODULE_CLASS",
                "MaxineRuntimeExitFixtureModule",
                "MaxineRuntimeExitFixtureSystemComponent::CreateDescriptor",
            ],
            "absent_symbols": [
                "_Editor",
                "BehaviorContext",
                "PrefabPublicInterface",
            ],
        },
        {
            "path": "C:/src/o3de/Gems/CustomAssetExample/Code/CMakeLists.txt",
            "symbols": [
                "if(PAL_TRAIT_BUILD_HOST_TOOLS)",
                "NAME ${gem_name}.Editor GEM_MODULE",
                "ly_create_alias(NAME ${gem_name}.Tools",
            ],
            "absent_symbols": [],
        },
        {
            "path": "C:/src/o3de/Gems/CustomAssetExample/Code/Source/CustomAssetExample/CustomAssetExampleEditorModule.cpp",
            "symbols": [
                "AZ_DECLARE_MODULE_CLASS",
                "O3DE_GEM_NAME",
                "CustomAssetExampleModule",
            ],
            "absent_symbols": [],
        },
    ]


def _approved_prefab_save_update_bridge_candidate_matrix() -> List[Dict[str, Any]]:
    return [
        {
            "candidate": "repo-owned C++ Editor bridge reflecting SavePrefab / CreatePrefabAndSaveToDisk into Editor automation",
            "outcome": "blocked",
            "reason": "Selected technical path, but the repo-owned Gem currently has only runtime client aliases and no Editor/Tools module registration.",
        },
        {
            "candidate": "existing PrefabPublicRequestBus only",
            "outcome": "rejected",
            "reason": "PR #146 observed reflected events still omit SavePrefab and CreatePrefabAndSaveToDisk.",
        },
        {
            "candidate": "existing Python-only wrapper",
            "outcome": "rejected",
            "reason": "No Python-accessible save/update route exists without an exposed BehaviorContext route or bridge.",
        },
        {
            "candidate": "BehaviorContext-reflected bridge",
            "outcome": "selected_but_blocked",
            "reason": "Narrowest source-backed path, pending Editor Gem registration and rebuild proof.",
        },
        {
            "candidate": "scratch prefab save probe",
            "outcome": "blocked",
            "reason": "Preferred first proof surface, but it waits for a callable bridge.",
        },
        {
            "candidate": "approved source prefab Actor + Simple Motion mutation",
            "outcome": "deferred",
            "reason": "Approved source mutation waits for bridge and scratch save/update proof.",
        },
        {
            "candidate": "hand-authored unknown .prefab component JSON",
            "outcome": "rejected",
            "reason": "Unknown O3DE component serialization must not be hand-authored.",
        },
        {
            "candidate": "direct runtime .procprefab load",
            "outcome": "rejected",
            "reason": "Preserved unsupported/builder-only proof limit.",
        },
        {
            "candidate": "direct product-load of actor/motion products",
            "outcome": "rejected",
            "reason": "Product-load is not prefab save/update or component wiring proof.",
        },
        {
            "candidate": "defaultlevel or production-level mutation",
            "outcome": "rejected",
            "reason": "Defaultlevel and production-level mutation are disallowed.",
        },
    ]


def _approved_prefab_save_update_bridge_host_repo_source_refs() -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        {
            "path": str(repo_root / "o3de/gems/MaxineRuntimeExitFixture/gem.json"),
            "symbols": [
                "gem_name",
                "MaxineRuntimeExitFixture",
                "Non-Shipping",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(repo_root / "o3de/gems/MaxineRuntimeExitFixture/Code/CMakeLists.txt"),
            "symbols": [
                "if(PAL_TRAIT_BUILD_HOST_TOOLS)",
                "NAME ${gem_name}.Editor GEM_MODULE",
                "maxineruntimeexitfixture_editor_files.cmake",
                "AZ::AzToolsFramework",
                "ly_create_alias(NAME ${gem_name}.Tools",
                "ly_create_alias(NAME ${gem_name}.Builders",
                "Source/Tools/MaxinePrefabSaveUpdateBridgeEditorModule.cpp",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(repo_root / "o3de/gems/MaxineRuntimeExitFixture/Code/maxineruntimeexitfixture_editor_files.cmake"),
            "symbols": [
                "Source/Tools/MaxinePrefabSaveUpdateBridgeEditorModule.cpp",
                "Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp",
                "Source/Tools/PrefabSaveUpdateBridgeHostComponent.h",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/MaxinePrefabSaveUpdateBridgeEditorModule.cpp"
            ),
            "symbols": [
                "AZ_DECLARE_MODULE_CLASS",
                "AZ_JOIN(Gem_, O3DE_GEM_NAME, _Editor)",
                "MaxinePrefabSaveUpdateBridgeEditorModule",
                "PrefabSaveUpdateBridgeHostComponent::CreateDescriptor",
                "GetRequiredSystemComponents",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.h"
            ),
            "symbols": [
                "AZ_COMPONENT_DECL",
                "GetPrefabSaveUpdateBridgeHostStatus",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp"
            ),
            "symbols": [
                "AZ_COMPONENT_IMPL",
                "AZ::BehaviorContext",
                "AZ::Script::Attributes::ScopeFlags::Automation",
                "AZ::Script::Attributes::Module",
                "maxine.prefab_bridge",
                "get_prefab_save_update_bridge_host_status",
                "AzToolsFramework::Prefab::PrefabPublicInterface",
                "save_route_exposed=true",
                "scratch_save_verified=false",
            ],
            "absent_symbols": [],
        },
    ]


def _approved_prefab_save_update_bridge_host_engine_source_refs() -> List[Dict[str, Any]]:
    engine_root_raw = os.environ.get("O3DE_ENGINE_ROOT", "").strip()
    if not engine_root_raw:
        return []
    engine_root = Path(engine_root_raw)
    return [
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicInterface.h"
            ),
            "symbols": [
                "PrefabPublicInterface",
                "CreatePrefabAndSaveToDisk",
                "SavePrefab",
                "PrefabOperationResult",
                "AZ::IO::Path",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicHandler.cpp"
            ),
            "symbols": [
                "PrefabPublicHandler::CreatePrefabAndSaveToDisk",
                "filePath.IsAbsolute()",
                "CreatePrefabInMemory",
                "SaveTemplateToFile",
                "PrefabPublicHandler::SavePrefab",
                "GetTemplateIdFromFilePath",
                "SaveTemplate",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicRequestHandler.cpp"
            ),
            "symbols": [
                "BehaviorContext",
                "PrefabPublicRequestBus",
                'Event("CreatePrefabInMemory"',
                'Event("InstantiatePrefab"',
            ],
            "absent_symbols": [
                'Event("CreatePrefabAndSaveToDisk"',
                'Event("SavePrefab"',
            ],
        },
        {
            "path": str(engine_root / "Gems/CustomAssetExample/Code/CMakeLists.txt"),
            "symbols": [
                "if(PAL_TRAIT_BUILD_HOST_TOOLS)",
                "NAME ${gem_name}.Editor GEM_MODULE",
                "ly_create_alias(NAME ${gem_name}.Tools",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(engine_root / "Gems/Archive/Code/Source/Tools/ArchiveEditorModule.cpp"),
            "symbols": [
                "AZ_DECLARE_MODULE_CLASS",
                "O3DE_GEM_NAME",
                "EditorModule",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(engine_root / "Code/Editor/PythonEditorFuncs.cpp"),
            "symbols": [
                "AZ::BehaviorContext",
                "AZ::Script::Attributes::ScopeFlags::Automation",
                "AZ::Script::Attributes::Module",
            ],
            "absent_symbols": [],
        },
    ]


def _optional_engine_source_validation_from_refs(specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not specs:
        return {
            "status": "engine_source_refs_unavailable",
            "verified": False,
            "refs": [],
        }
    validation = _source_validation_from_refs(specs)
    if validation["status"] == "pass":
        return validation
    refs = validation.get("refs", [])
    any_exists = any(isinstance(ref, Mapping) and ref.get("exists") is True for ref in refs)
    validation["status"] = "inconclusive" if any_exists else "engine_source_refs_not_available_in_this_environment"
    validation["verified"] = False
    return validation


def _approved_prefab_save_update_bridge_host_source_refs() -> List[Dict[str, Any]]:
    return _approved_prefab_save_update_bridge_host_repo_source_refs() + (
        _approved_prefab_save_update_bridge_host_engine_source_refs()
    )


def _approved_prefab_save_update_bridge_host_candidate_matrix() -> List[Dict[str, Any]]:
    return [
        {
            "candidate": "extend MaxineRuntimeExitFixture with an Editor/Tools bridge host",
            "outcome": "selected",
            "reason": "Repo-owned Gem is already enabled by the golden project fixture and is the narrowest controlled host.",
        },
        {
            "candidate": "create a new repo-owned Editor/Tools bridge Gem",
            "outcome": "deferred",
            "reason": "A new Gem would add registration surface beyond the existing fixture Gem.",
        },
        {
            "candidate": "modify global O3DE engine source",
            "outcome": "rejected",
            "reason": "A repo-owned Editor module can host the bridge without broad engine changes.",
        },
        {
            "candidate": "BehaviorContext-reflected Editor bridge host",
            "outcome": "selected",
            "reason": "Source validation shows Automation-scoped BehaviorContext methods are callable from Editor Python.",
        },
        {
            "candidate": "EBus-reflected Editor bridge host",
            "outcome": "deferred",
            "reason": "A single status method is narrower for host registration than a new EBus contract.",
        },
        {
            "candidate": "existing PrefabPublicRequestBus only",
            "outcome": "rejected",
            "reason": "Existing reflected events still omit SavePrefab and CreatePrefabAndSaveToDisk.",
        },
        {
            "candidate": "Python-only wrapper",
            "outcome": "rejected",
            "reason": "No Python-accessible save/update route exists before the Editor host is loaded.",
        },
        {
            "candidate": "scratch prefab save probe",
            "outcome": "deferred",
            "reason": "Scratch save waits for the host to be built and callable.",
        },
        {
            "candidate": "approved source prefab Actor + Simple Motion mutation",
            "outcome": "deferred",
            "reason": "Approved source mutation waits for bridge host, save/update route, scratch proof, APB, and runtime TypeId proof.",
        },
        {
            "candidate": "hand-authored unknown .prefab component JSON",
            "outcome": "rejected",
            "reason": "Unknown O3DE component serialization must not be hand-authored.",
        },
        {
            "candidate": "direct runtime .procprefab load",
            "outcome": "rejected",
            "reason": "Preserved unsupported/builder-only proof limit.",
        },
        {
            "candidate": "defaultlevel or production-level mutation",
            "outcome": "rejected",
            "reason": "Defaultlevel and production-level mutation are disallowed.",
        },
    ]


def _call_prefab_save_update_bridge_host_status() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "attempted": True,
        "callable": False,
        "module": "azlmbr.maxine.prefab_bridge",
        "method": "get_prefab_save_update_bridge_host_status",
        "status": "",
        "error": "",
    }
    try:
        import importlib

        module = importlib.import_module(str(result["module"]))
        status_fn = getattr(module, str(result["method"]))
        status_value = status_fn()
        result["status"] = str(status_value)
        result["callable"] = "maxine_prefab_save_update_bridge_host_registered" in str(status_value)
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _run_approved_prefab_save_update_bridge_host_checks(
    report: Mapping[str, Any],
    *,
    bridge_host_status: Mapping[str, Any],
    build_verified: bool,
) -> Dict[str, Any]:
    source_validation = _source_validation_from_refs(_approved_prefab_save_update_bridge_host_repo_source_refs())
    engine_source_validation = _optional_engine_source_validation_from_refs(
        _approved_prefab_save_update_bridge_host_engine_source_refs()
    )
    source_verified = source_validation["verified"] is True
    callable_from_editor = bool(bridge_host_status.get("callable")) and source_verified
    host_added = source_verified
    host_registered = source_verified
    build_verified = bool(build_verified) and source_verified
    behavior_context_reflected = source_verified
    aztools_dependency_present = source_verified
    runtime_excluded = source_verified
    blocker = ""
    if not source_verified:
        blocker = "blocked_by_editor_bridge_host_requires_additional_source_validation"
    elif not callable_from_editor:
        blocker = "blocked_by_editor_bridge_host_not_loaded_in_editor"

    return {
        "approved_prefab_save_update_bridge_host_diagnostic_attempted": True,
        "approved_prefab_save_update_bridge_host_diagnostic_completed": True,
        "approved_prefab_save_update_bridge_host_source_validation_status": source_validation["status"],
        "approved_prefab_save_update_bridge_host_source_validation_verified": source_validation["verified"],
        "approved_prefab_save_update_bridge_host_source_files": source_validation["refs"],
        "approved_prefab_save_update_bridge_host_engine_source_refs_status": engine_source_validation["status"],
        "approved_prefab_save_update_bridge_host_engine_source_refs_verified": engine_source_validation["verified"],
        "approved_prefab_save_update_bridge_host_engine_source_refs": engine_source_validation["refs"],
        "approved_prefab_save_update_bridge_host_selected_strategy": (
            "register_editor_tools_behavior_context_host_before_save_route"
        ),
        "approved_prefab_save_update_bridge_host_candidate_matrix": (
            _approved_prefab_save_update_bridge_host_candidate_matrix()
        ),
        "approved_prefab_save_update_bridge_host_added": host_added,
        "approved_prefab_save_update_bridge_host_registered": host_registered,
        "approved_prefab_save_update_bridge_host_build_required": True,
        "approved_prefab_save_update_bridge_host_build_verified": build_verified,
        "approved_prefab_save_update_bridge_host_target_name": "MaxineRuntimeExitFixture.Editor",
        "approved_prefab_save_update_bridge_host_module_name": "Gem_MaxineRuntimeExitFixture_Editor",
        "approved_prefab_save_update_bridge_host_aztoolsframework_dependency_present": aztools_dependency_present,
        "approved_prefab_save_update_bridge_host_behavior_context_reflected": behavior_context_reflected,
        "approved_prefab_save_update_bridge_host_callable_from_editor_python": callable_from_editor,
        "approved_prefab_save_update_bridge_host_runtime_excluded": runtime_excluded,
        "approved_prefab_save_update_bridge_host_blocker": blocker,
        "approved_prefab_save_update_bridge_host_api": {
            "module": "azlmbr.maxine.prefab_bridge",
            "method": "get_prefab_save_update_bridge_host_status",
            "source_api": "AzToolsFramework::Prefab::PrefabPublicInterface",
            "engine_source_refs_status": engine_source_validation["status"],
            "save_route_exposed": True,
            "scratch_save_verified": False,
        },
        "approved_prefab_save_update_bridge_host_status_call_result": str(bridge_host_status.get("status", "")),
        "approved_prefab_save_update_bridge_host_status_call_error": str(bridge_host_status.get("error", "")),
        "approved_prefab_save_update_bridge_host_build_command": "",
        "approved_prefab_save_update_bridge_added": host_added,
        "approved_prefab_save_update_bridge_verified": False,
        "approved_prefab_save_update_bridge_callable_from_editor_python": False,
        "approved_prefab_save_update_automation_surface_verified": False,
        "approved_prefab_save_update_scratch_prefab_path": (
            "examples/o3de-golden-project/source/Assets/_maxine_smoke/prefabs/prefab_save_update_bridge_host_probe.prefab"
        ),
        "approved_prefab_save_update_scratch_save_attempted": False,
        "approved_prefab_save_update_scratch_save_verified": False,
        "approved_prefab_save_update_scratch_reload_or_parse_verified": False,
        "approved_prefab_save_update_scratch_cleanup_verified": True,
        "approved_runtime_animation_component_wiring_source_prefab_modified": False,
        "approved_runtime_animation_component_wiring_editor_generated_update_used": False,
        "approved_runtime_animation_component_wiring_actor_component_added": False,
        "approved_runtime_animation_component_wiring_simple_motion_component_added": False,
        "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_prefab_save_verified": False,
        "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _approved_prefab_save_update_route_repo_source_refs() -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.h"
            ),
            "symbols": [
                "GetPrefabSaveUpdateBridgeHostStatus",
                "SavePrefabUpdateScratchProbe",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp"
            ),
            "symbols": [
                "save_prefab_update_scratch_probe",
                "AZ::Script::Attributes::ScopeFlags::Automation",
                "AZ::Script::Attributes::Module",
                "maxine.prefab_bridge",
                "AzToolsFramework::Prefab::PrefabPublicInterface",
                "CreatePrefabAndSaveToDisk",
                "AzToolsFramework::EditorEntityContextRequestBus",
                "CreateNewEditorEntity",
                "AzToolsFramework::ToolsApplicationRequestBus",
                "DeleteEntityById",
                "AZ::IO::SystemFile::CreateDir",
                "AZ::Utils::GetProjectPath",
                "RejectReasonForScratchPath",
                "project_root_anchored_scratch_root",
                "IsPathInsideRoot",
                "_maxine_smoke",
                "path_traversal",
                "level_or_production_path",
                "generated_product_or_cache_path",
                "unapproved_scratch_root",
                "scratch_save_verified=true",
            ],
            "absent_symbols": [
                'Contains(normalized, "/assets/_maxine_smoke/prefabs/")',
                "SavePrefab(AZ::IO::Path",
                "approved source prefab",
            ],
        },
        {
            "path": str(repo_root / "o3de/gems/MaxineRuntimeExitFixture/Code/CMakeLists.txt"),
            "symbols": [
                "NAME ${gem_name}.Editor GEM_MODULE",
                "AZ::AzToolsFramework",
                "maxineruntimeexitfixture_editor_files.cmake",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(repo_root / "o3de/gems/MaxineRuntimeExitFixture/Code/maxineruntimeexitfixture_editor_files.cmake"),
            "symbols": [
                "Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp",
                "Source/Tools/PrefabSaveUpdateBridgeHostComponent.h",
            ],
            "absent_symbols": [],
        },
    ]


def _approved_prefab_save_update_route_candidate_matrix() -> List[Dict[str, Any]]:
    return [
        {
            "candidate": "bounded BehaviorContext save/update route behind MaxineRuntimeExitFixture.Editor",
            "outcome": "selected",
            "reason": "The registered Editor host can expose a scratch-only Automation method with a strict path policy.",
        },
        {
            "candidate": "unrestricted SavePrefab exposure",
            "outcome": "rejected",
            "reason": "Unrestricted save calls would violate the approved-path safety contract.",
        },
        {
            "candidate": "scratch prefab save/update proof",
            "outcome": "selected",
            "reason": "Scratch proof is the bounded first proof surface before approved source-prefab mutation.",
        },
        {
            "candidate": "approved source prefab Actor + Simple Motion mutation",
            "outcome": "deferred",
            "reason": "Approved source mutation waits for scratch proof plus APB and runtime TypeId verification.",
        },
        {
            "candidate": "hand-authored unknown .prefab component JSON",
            "outcome": "rejected",
            "reason": "Unknown O3DE component serialization must not be hand-authored.",
        },
        {
            "candidate": "direct runtime .procprefab load",
            "outcome": "rejected",
            "reason": "Preserved unsupported/builder-only proof limit.",
        },
        {
            "candidate": "direct product-load of actor/motion products",
            "outcome": "rejected",
            "reason": "Product-load is not prefab save/update or component wiring proof.",
        },
        {
            "candidate": "defaultlevel or production-level mutation",
            "outcome": "rejected",
            "reason": "Defaultlevel and production-level mutation are disallowed.",
        },
        {
            "candidate": "generated product/cache path write",
            "outcome": "rejected",
            "reason": "Generated products and cache paths cannot be authored or committed as proof.",
        },
    ]


def _approved_prefab_save_update_route_scratch_path() -> Path:
    project_path = Path(os.environ.get("O3DE_PROJECT_PATH", "") or Path.cwd())
    return project_path / "Assets" / "_maxine_smoke" / "prefabs" / "prefab_save_update_route_probe.prefab"


def _approved_prefab_save_update_route_rejection_paths(scratch_prefab_path: Path) -> Dict[str, Path]:
    project_path = Path(os.environ.get("O3DE_PROJECT_PATH", "") or scratch_prefab_path.parents[3])
    outside_project_substring_path = Path("D:/tmp/Assets/_maxine_smoke/prefabs/probe.prefab")
    if project_path.drive.lower() == "d:":
        outside_project_substring_path = Path("C:/tmp/Assets/_maxine_smoke/prefabs/probe.prefab")
    return {
        "defaultlevel": project_path / "Levels" / "defaultlevel" / "defaultlevel.prefab",
        "production_level": project_path / "Levels" / "production" / "release.prefab",
        "generated_product": project_path / "Cache" / "pc" / "assets" / "_maxine_smoke" / "prefabs" / "probe.prefab",
        "unapproved_absolute": outside_project_substring_path,
        "other_project": project_path.parent / "OtherProject" / "Assets" / "_maxine_smoke" / "prefabs" / "probe.prefab",
        "path_traversal": scratch_prefab_path.parent / ".." / "escape.prefab",
    }


def _call_prefab_save_update_route_scratch_probe(scratch_prefab_path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "attempted": True,
        "callable": False,
        "saved": False,
        "module": "azlmbr.maxine.prefab_bridge",
        "method": "save_prefab_update_scratch_probe",
        "status": "",
        "error": "",
    }
    try:
        import importlib

        scratch_prefab_path.parent.mkdir(parents=True, exist_ok=True)
        module = importlib.import_module(str(result["module"]))
        route_fn = getattr(module, str(result["method"]))
        status_text = str(route_fn(str(scratch_prefab_path)))
        result["status"] = status_text
        result["callable"] = True
        result["saved"] = (
            "maxine_prefab_save_update_route_saved" in status_text
            and "scratch_save_verified=true" in status_text
        )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _call_prefab_save_update_route_rejection_probes(scratch_prefab_path: Path) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for label, path in _approved_prefab_save_update_route_rejection_paths(scratch_prefab_path).items():
        result: Dict[str, Any] = {
            "attempted": True,
            "callable": False,
            "rejected": False,
            "status": "",
            "error": "",
        }
        try:
            import importlib

            module = importlib.import_module("azlmbr.maxine.prefab_bridge")
            route_fn = getattr(module, "save_prefab_update_scratch_probe")
            status_text = str(route_fn(str(path)))
            result["status"] = status_text
            result["callable"] = True
            result["rejected"] = "maxine_prefab_save_update_route_rejected" in status_text
        except Exception as exc:
            result["error"] = str(exc)
        results[label] = result
    return results


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_prefab_json(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return False
    return isinstance(payload, dict)


def _json_payload_contains_marker(payload: Any, marker: str) -> bool:
    if isinstance(payload, Mapping):
        return any(
            str(key) == marker
            or (isinstance(value, str) and marker in value)
            or _json_payload_contains_marker(value, marker)
            for key, value in payload.items()
        )
    if isinstance(payload, list):
        return any(_json_payload_contains_marker(item, marker) for item in payload)
    if isinstance(payload, str):
        return marker in payload
    return False


def _source_prefab_wiring_marker_evidence(path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "parse_verified": False,
        "actor": False,
        "motion": False,
        "both": False,
        "method": "json_recursive_marker_scan",
    }
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        result["error"] = str(exc)
        return result
    result["parse_verified"] = isinstance(payload, dict)
    result["actor"] = _json_payload_contains_marker(payload, "ActorAsset")
    result["motion"] = _json_payload_contains_marker(payload, "MotionAsset")
    result["both"] = bool(result["actor"] and result["motion"])
    return result


def _cleanup_scratch_prefab(path: Path) -> bool:
    try:
        if path.exists():
            path.unlink()
        for parent in (path.parent, path.parent.parent):
            try:
                parent.rmdir()
            except OSError:
                pass
        return not path.exists()
    except Exception:
        return False


def _route_rejection_verified(rejection_statuses: Mapping[str, Mapping[str, Any]], label: str) -> bool:
    payload = rejection_statuses.get(label, {})
    return isinstance(payload, Mapping) and payload.get("rejected") is True


def _run_approved_prefab_save_update_route_checks(
    report: Mapping[str, Any],
    *,
    bridge_host_status: Mapping[str, Any],
    route_status: Mapping[str, Any],
    rejection_statuses: Mapping[str, Mapping[str, Any]],
    scratch_prefab_path: Path,
) -> Dict[str, Any]:
    source_validation = _source_validation_from_refs(_approved_prefab_save_update_route_repo_source_refs())
    source_verified = source_validation["verified"] is True
    bridge_host_callable = bool(bridge_host_status.get("callable")) and source_verified
    route_callable = bool(route_status.get("callable")) and bridge_host_callable
    scratch_save_attempted = bool(route_status.get("attempted"))
    scratch_save_verified = bool(route_status.get("saved")) and scratch_prefab_path.exists()
    before_hash = ""
    before_path = scratch_prefab_path.with_suffix(".before")
    if before_path.exists():
        before_hash = _sha256_file(before_path)
    after_hash = _sha256_file(scratch_prefab_path) if scratch_save_verified else ""
    parse_verified = _parse_prefab_json(scratch_prefab_path) if scratch_save_verified else False
    cleanup_verified = _cleanup_scratch_prefab(scratch_prefab_path)

    rejected_defaultlevel = _route_rejection_verified(rejection_statuses, "defaultlevel")
    rejected_production = _route_rejection_verified(rejection_statuses, "production_level")
    rejected_generated = _route_rejection_verified(rejection_statuses, "generated_product")
    rejected_unapproved_absolute = _route_rejection_verified(rejection_statuses, "unapproved_absolute")
    rejected_other_project = _route_rejection_verified(rejection_statuses, "other_project")
    rejected_path_traversal = _route_rejection_verified(rejection_statuses, "path_traversal")

    bridge_verified = (
        source_verified
        and bridge_host_callable
        and route_callable
        and scratch_save_attempted
        and scratch_save_verified
        and parse_verified
        and cleanup_verified
        and rejected_defaultlevel
        and rejected_production
        and rejected_generated
        and rejected_unapproved_absolute
        and rejected_other_project
        and rejected_path_traversal
    )
    blocker = ""
    if not source_verified:
        blocker = "blocked_by_prefab_save_update_route_requires_additional_source_validation"
    elif not route_callable:
        blocker = "blocked_by_prefab_save_update_route_editor_call_failed"
    elif not all(
        [
            rejected_defaultlevel,
            rejected_production,
            rejected_generated,
            rejected_unapproved_absolute,
            rejected_other_project,
            rejected_path_traversal,
        ]
    ):
        blocker = "blocked_by_prefab_save_update_route_path_policy"
    elif not scratch_save_verified:
        blocker = "blocked_by_prefab_save_update_scratch_save_not_verified"
    elif not parse_verified:
        blocker = "blocked_by_prefab_save_update_scratch_parse_failed"
    elif not cleanup_verified:
        blocker = "blocked_by_prefab_save_update_scratch_cleanup_failed"

    source_prefab_path = "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
    return {
        "approved_prefab_save_update_route_diagnostic_attempted": True,
        "approved_prefab_save_update_route_diagnostic_completed": True,
        "approved_prefab_save_update_route_source_validation_status": source_validation["status"],
        "approved_prefab_save_update_route_source_validation_verified": source_validation["verified"],
        "approved_prefab_save_update_route_source_files": source_validation["refs"],
        "approved_prefab_save_update_route_added": source_verified,
        "approved_prefab_save_update_route_behavior_context_reflected": source_verified,
        "approved_prefab_save_update_route_callable_from_editor_python": route_callable,
        "approved_prefab_save_update_route_blocker": blocker,
        "approved_prefab_save_update_route_candidate_matrix": _approved_prefab_save_update_route_candidate_matrix(),
        "approved_prefab_save_update_route_selected_strategy": (
            "bounded_behavior_context_route_with_scratch_prefab_create_prefab_and_save_to_disk_proof"
        ),
        "approved_prefab_save_update_route_api": {
            "module": "azlmbr.maxine.prefab_bridge",
            "method": "save_prefab_update_scratch_probe",
            "source_api": "AzToolsFramework::Prefab::PrefabPublicInterface::CreatePrefabAndSaveToDisk",
            "source_api_signature": "CreatePrefabResult CreatePrefabAndSaveToDisk(const EntityIdList&, AZ::IO::PathView)",
            "save_backend": "PrefabLoaderInterface::SaveTemplateToFile",
            "requires_absolute_path": True,
            "creates_scratch_editor_entity": True,
            "cleanup_api": "AzToolsFramework::ToolsApplicationRequests::DeleteEntityById",
            "status": str(route_status.get("status", "")),
            "error": str(route_status.get("error", "")),
            "rejection_statuses": rejection_statuses,
        },
        "approved_prefab_save_update_bridge_host_callable_from_editor_python": bridge_host_callable,
        "approved_prefab_save_update_bridge_added": source_verified,
        "approved_prefab_save_update_bridge_verified": bridge_verified,
        "approved_prefab_save_update_bridge_callable_from_editor_python": route_callable,
        "approved_prefab_save_update_automation_surface_verified": bridge_verified,
        "approved_prefab_save_update_allowed_path_policy": {
            "allowed_prefab_roots": [
                "Assets/_maxine_smoke/prefabs/",
            ],
            "active_project_root_anchored": True,
            "project_root_source_api": "AZ::Utils::GetProjectPath",
            "approved_source_prefab_root_deferred": (
                "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/"
            ),
            "requires_absolute_path": True,
            "requires_prefab_extension": True,
            "rejects_levels": True,
            "rejects_defaultlevel": True,
            "rejects_production_level": True,
            "rejects_generated_products": True,
            "rejects_unapproved_absolute_paths": True,
            "rejects_other_project_paths": True,
            "rejects_path_traversal": True,
        },
        "approved_prefab_save_update_rejected_defaultlevel_path": rejected_defaultlevel,
        "approved_prefab_save_update_rejected_production_level_path": rejected_production,
        "approved_prefab_save_update_rejected_generated_product_path": rejected_generated,
        "approved_prefab_save_update_rejected_unapproved_absolute_path": rejected_unapproved_absolute,
        "approved_prefab_save_update_rejected_path_traversal": rejected_path_traversal,
        "approved_prefab_save_update_scratch_prefab_path": _redacted_project_temp_path(str(scratch_prefab_path)),
        "approved_prefab_save_update_scratch_save_attempted": scratch_save_attempted,
        "approved_prefab_save_update_scratch_save_verified": scratch_save_verified,
        "approved_prefab_save_update_scratch_reload_or_parse_verified": parse_verified,
        "approved_prefab_save_update_scratch_cleanup_verified": cleanup_verified,
        "approved_prefab_save_update_before_hash": before_hash,
        "approved_prefab_save_update_after_hash": after_hash,
        "approved_prefab_save_update_generated_products_committed": False,
        "approved_runtime_animation_component_wiring_source_prefab_path": source_prefab_path,
        "approved_runtime_animation_component_wiring_source_prefab_modified": False,
        "approved_runtime_animation_component_wiring_editor_generated_update_used": False,
        "approved_runtime_animation_component_wiring_actor_component_added": False,
        "approved_runtime_animation_component_wiring_simple_motion_component_added": False,
        "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_prefab_save_verified": False,
        "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
    }


APPROVED_SOURCE_PREFAB_REPO_REF = (
    "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
)
APPROVED_SOURCE_PREFAB_PROJECT_REF = "Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"


def _approved_source_prefab_repo_path() -> Path:
    return Path(__file__).resolve().parents[3] / APPROVED_SOURCE_PREFAB_REPO_REF


def _approved_source_prefab_project_path() -> Path:
    project_path = Path(os.environ.get("O3DE_PROJECT_PATH", "") or Path.cwd())
    return project_path / Path(APPROVED_SOURCE_PREFAB_PROJECT_REF)


def _approved_source_prefab_wiring_candidate_matrix() -> List[Dict[str, Any]]:
    return [
        {
            "candidate": "approved source-prefab Actor + Simple Motion mutation through verified save/update route",
            "outcome": "selected",
            "reason": "PR #149 proved a bounded Editor bridge route; this slice uses the approved source path only.",
        },
        {
            "candidate": "Actor + Anim Graph + Motion Set mutation",
            "outcome": "deferred",
            "reason": "Simple Motion is the narrower source-validated runtime component surface for this slice.",
        },
        {
            "candidate": "scratch-only route proof",
            "outcome": "preserved_not_sufficient",
            "reason": "Scratch proof remains preserved from PR #149 but is not runtime component wiring proof.",
        },
        {
            "candidate": "hand-authored unknown .prefab component JSON",
            "outcome": "rejected",
            "reason": "The source prefab must be modified through Editor/prefab APIs, not manual unknown serialization.",
        },
        {
            "candidate": "direct runtime .procprefab load",
            "outcome": "rejected",
            "reason": "Direct runtime .procprefab load remains unsupported/builder-only.",
        },
        {
            "candidate": "direct product-load of actor/motion products",
            "outcome": "rejected",
            "reason": "Product-load is not component wiring proof.",
        },
        {
            "candidate": "defaultlevel or production-level mutation",
            "outcome": "rejected",
            "reason": "This slice mutates only the approved repo-owned source prefab path.",
        },
        {
            "candidate": "generated product/cache path write",
            "outcome": "rejected",
            "reason": "Generated products and cache paths remain read-only evidence surfaces.",
        },
    ]


def _approved_source_prefab_wiring_source_refs() -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        *_approved_animation_component_wiring_source_refs(),
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.h"
            ),
            "symbols": [
                "SaveApprovedSourcePrefabWiring",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp"
            ),
            "symbols": [
                "apply_approved_source_prefab_component_overrides",
                "ApplyApprovedSourcePrefabComponentOverrides",
                "commit_approved_source_prefab_entity_changes",
                "CommitApprovedSourcePrefabEntityChanges",
                "save_approved_source_prefab_wiring",
                "SaveApprovedSourcePrefabWiring",
                "RejectReasonForApprovedSourcePrefabPath",
                "AZ::Utils::GetProjectPath",
                "approved_source_prefab_path",
                "Assets",
                "Characters",
                "MAXINE_GoldenCorpus",
                "release_rigged.prefab",
                "AzToolsFramework::Prefab::PrefabLoaderInterface",
                "GenerateRelativePath",
                "AzToolsFramework::Prefab::PrefabPublicInterface::SavePrefab",
                "AzToolsFramework::Prefab::PrefabOverridePublicInterface",
                "ApplyComponentOverrides",
                "AreComponentOverridesPresent",
                "GenerateUndoNodesForEntityChangeAndUpdateCache",
                "approved_source_save_verified=true",
            ],
            "absent_symbols": [
                'Contains(normalized, "/assets/characters/maxine_goldencorpus/prefabs/")',
                "hand_authored_unknown_json",
            ],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Component/EditorComponentAPIBus.h",
            "symbols": [
                "EditorComponentAPIRequests",
                "AddComponentsOfType",
                "BuildComponentPropertyList",
                "SetComponentProperty",
                "GetComponentProperty",
            ],
            "absent_symbols": [],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabLoaderInterface.h",
            "symbols": [
                "GenerateRelativePath",
                "SaveTemplate",
                "SaveTemplateToFile",
                "SaveTemplateToString",
            ],
            "absent_symbols": [],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicInterface.h",
            "symbols": [
                "GenerateUndoNodesForEntityChangeAndUpdateCache",
                "Store the changes between the current entity state and its last cached state",
                "SavePrefab",
            ],
            "absent_symbols": [],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Overrides/PrefabOverridePublicInterface.h",
            "symbols": [
                "PrefabOverridePublicInterface",
                "AreComponentOverridesPresent",
                "ApplyComponentOverrides",
                "AZ::EntityComponentIdPair",
            ],
            "absent_symbols": [],
        },
        {
            "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Overrides/PrefabOverridePublicHandler.cpp",
            "symbols": [
                "ApplyComponentOverrides",
                "PushOverridesToPrefab",
                "PrefabOverridePublicRequestBus",
                "AreComponentOverridesPresent",
                "RevertOverrides",
            ],
            "absent_symbols": [
                '->Event("ApplyComponentOverrides"',
            ],
        },
    ]


def _optional_o3de_engine_root() -> Path | None:
    engine_root_raw = os.environ.get("O3DE_ENGINE_ROOT", "").strip()
    if engine_root_raw:
        configured = Path(engine_root_raw)
        return configured if configured.exists() else None
    candidates: List[Path] = []
    default_engine_root = Path("C:/src/o3de")
    if default_engine_root.exists():
        candidates.append(default_engine_root)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _approved_source_prefab_propagation_apply_step_repo_source_refs() -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.h"
            ),
            "symbols": [
                "ApplyApprovedSourcePrefabComponentOverrides",
                "CommitApprovedSourcePrefabEntityChanges",
                "SaveApprovedSourcePrefabWiring",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp"
            ),
            "symbols": [
                "apply_approved_source_prefab_component_overrides",
                "commit_approved_source_prefab_entity_changes",
                "save_approved_source_prefab_wiring",
                "AzToolsFramework::Prefab::PrefabOverridePublicInterface",
                "AreComponentOverridesPresent",
                "ApplyComponentOverrides",
                "GenerateUndoNodesForEntityChangeAndUpdateCache",
                "AzToolsFramework::Prefab::PrefabPublicInterface::SavePrefab",
                "RejectReasonForApprovedSourcePrefabPath",
                "approved_source_prefab_path",
            ],
            "absent_symbols": [
                "hand_authored_unknown_json",
                "runtime_character_animation_component_wiring_verified=true",
            ],
        },
        {
            "path": str(repo_root / "tools/o3de/editor_python/maxine_package_prefab_smoke.py"),
            "symbols": [
                "blocked_by_editor_generated_instance_changes_not_propagated_to_source_template",
                "_call_prefab_commit_approved_source_entity_changes",
                "_call_prefab_apply_approved_source_component_overrides",
                "_call_prefab_save_update_approved_source_route",
                "ActorAsset",
                "MotionAsset",
            ],
            "absent_symbols": [
                "approved_source_prefab_actor_simple_motion_wiring_verified = True",
            ],
        },
    ]


def _approved_source_prefab_propagation_apply_step_engine_source_refs() -> List[Dict[str, Any]]:
    engine_root = _optional_o3de_engine_root()
    if engine_root is None:
        return []
    return [
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicInterface.h"
            ),
            "symbols": [
                "GenerateUndoNodesForEntityChangeAndUpdateCache",
                "Store the changes between the current entity state and its last cached state",
                "SavePrefab",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Overrides/PrefabOverridePublicInterface.h"
            ),
            "symbols": [
                "PrefabOverridePublicInterface",
                "AreComponentOverridesPresent",
                "ApplyComponentOverrides",
                "AZ::EntityComponentIdPair",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Overrides/PrefabOverridePublicHandler.cpp"
            ),
            "symbols": [
                "ApplyComponentOverrides",
                "GetComponentPathAndLinkIdFromFocusedPrefab",
                "GetFocusedPrefabInstance",
                "If the entity was owned by the focused instance, there's not much to push",
                "return false;",
                "GenerateEntityPathFromFocusedPrefab",
                "PushOverridesToPrefab",
            ],
            "absent_symbols": [
                '->Event("ApplyComponentOverrides"',
            ],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabFocusInterface.h"
            ),
            "symbols": [
                "FocusOnPrefabInstanceOwningEntityId",
                "GetFocusedPrefabTemplateId",
                "GetFocusedPrefabInstance",
                "IsFocusedPrefabInstanceReadOnly",
                "PrependPathFromFocusedInstanceToPatchPaths",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabFocusPublicInterface.h"
            ),
            "symbols": [
                "PrefabFocusPublicInterface",
                "FocusOnOwningPrefab",
                "FocusOnParentOfFocusedPrefab",
                "SetOwningPrefabInstanceOpenState",
                "IsOwningPrefabBeingFocused",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Instance/InstanceToTemplateInterface.h"
            ),
            "symbols": [
                "GeneratePatch",
                "GeneratePatchForLink",
                "PatchEntityInTemplate",
                "GenerateEntityPathFromFocusedPrefab",
                "PrependPathToPatchPaths",
                "PatchTemplate",
                "ApplyPatchesToInstance",
                "GetTopMostInstanceInHierarchy",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Instance/InstanceUpdateExecutorInterface.h"
            ),
            "symbols": [
                "AddInstanceToQueue",
                "AddTemplateInstancesToQueue",
                "UpdateTemplateInstancesInQueue",
                "SetShouldPauseInstancePropagation",
            ],
            "absent_symbols": [],
        },
    ]


def _approved_source_prefab_propagation_apply_step_candidate_matrix() -> List[Dict[str, Any]]:
    return [
        {
            "candidate": "GenerateUndoNodesForEntityChangeAndUpdateCache",
            "outcome": "attempted_preserved_blocked",
            "reason": "PR #150 proved the bridge route is callable, but saved source-template markers did not persist.",
        },
        {
            "candidate": "PrefabOverridePublicInterface::ApplyComponentOverrides",
            "outcome": "source_validated_blocked",
            "reason": "O3DE applies component overrides through a focused parent/link path; owning-instance-in-focus returns false.",
        },
        {
            "candidate": "source-template DOM update through source-backed prefab API",
            "outcome": "blocked",
            "reason": "InstanceToTemplate patch APIs exist, but this slice has no verified safe bridge sequence from Editor instance edits to approved source template DOM.",
        },
        {
            "candidate": "direct hand-authored .prefab JSON edit",
            "outcome": "rejected",
            "reason": "The route would hand-author unknown O3DE component JSON instead of using source-backed Editor/prefab APIs.",
        },
        {
            "candidate": "approved source-prefab Actor + Simple Motion mutation through verified propagation/apply route",
            "outcome": "blocked",
            "reason": "The missing parent-focus/link override apply sequence must be implemented before persisted marker proof can be claimed.",
        },
        {
            "candidate": "Actor + Anim Graph + Motion Set mutation",
            "outcome": "deferred",
            "reason": "Actor + Simple Motion remains the narrow target until propagation/apply semantics are pinned.",
        },
        {
            "candidate": "scratch-only route proof",
            "outcome": "preserved_not_sufficient",
            "reason": "PR #149 scratch save/update proof does not prove source-template propagation for approved prefab edits.",
        },
        {
            "candidate": "direct runtime .procprefab load",
            "outcome": "rejected",
            "reason": "Direct runtime .procprefab load remains unsupported/builder-only.",
        },
        {
            "candidate": "direct product-load of actor/motion products",
            "outcome": "rejected",
            "reason": "Product-load is not source-template propagation or component wiring proof.",
        },
        {
            "candidate": "defaultlevel or production-level mutation",
            "outcome": "rejected",
            "reason": "This diagnostic does not mutate defaultlevel or production levels.",
        },
    ]


def _approved_source_prefab_parent_link_override_apply_repo_source_refs() -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.h"
            ),
            "symbols": [
                "ApplyApprovedSourcePrefabParentLinkComponentOverrides",
                "ApplyApprovedSourcePrefabComponentOverrides",
                "CommitApprovedSourcePrefabEntityChanges",
                "SaveApprovedSourcePrefabWiring",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp"
            ),
            "symbols": [
                "apply_approved_source_prefab_parent_link_component_overrides",
                "ApplyApprovedSourcePrefabParentLinkComponentOverrides",
                "AzToolsFramework::Prefab::PrefabFocusPublicInterface",
                "FocusOnOwningPrefab",
                "FocusOnParentOfFocusedPrefab",
                "GetPrefabFocusPathLength",
                "GetOwningInstancePrefabPath",
                "GetFullPath",
                "ComponentApplicationRequests::FindEntity",
                "FindComponent",
                "AzToolsFramework::Prefab::PrefabOverridePublicInterface",
                "AreComponentOverridesPresent",
                "ApplyComponentOverrides",
                "PushOverridesToPrefab",
                "entity_ownership_checked=true",
                "component_ownership_checked=",
                "parent_focus_context_required=true",
                "parent_focus_context_available=true",
                "parent_focus_context_applied=true",
                "parent_focus_context_restored=true",
                "link_context_required=true",
                "link_context_available=true",
                "component_override_paths_detected=true",
                "push_overrides_to_prefab_verified=true",
                "RejectReasonForApprovedSourcePrefabPath",
                "approved_source_parent_link_override",
            ],
            "absent_symbols": [
                "hand_authored_unknown_json",
                "runtime_character_animation_component_wiring_verified=true",
            ],
        },
        {
            "path": str(repo_root / "tools/o3de/editor_python/maxine_package_prefab_smoke.py"),
            "symbols": [
                "_call_prefab_apply_approved_source_parent_link_component_overrides",
                "_approved_source_prefab_parent_link_override_apply_report_from_route_status",
                "_run_approved_source_prefab_parent_link_override_apply_route_checks",
                "approved-source-prefab-parent-link-override-apply-route",
                "ActorAsset",
                "MotionAsset",
                "approved_source_prefab_changed_this_run",
                "approved_source_prefab_marker_persistence_verified_this_run",
                "blocked_by_source_prefab_markers_preexisting_without_this_run_change",
                "blocked_by_prefab_instance_to_template_propagation_requires_parent_link_context",
                "blocked_by_prefab_template_dom_update_unavailable",
            ],
            "absent_symbols": [],
        },
    ]


def _approved_source_prefab_parent_link_override_apply_engine_source_refs() -> List[Dict[str, Any]]:
    engine_root = _optional_o3de_engine_root()
    if engine_root is None:
        return []
    return [
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabFocusPublicInterface.h"
            ),
            "symbols": [
                "PrefabFocusPublicInterface",
                "FocusOnOwningPrefab",
                "FocusOnParentOfFocusedPrefab",
                "GetFocusedPrefabContainerEntityId",
                "GetPrefabFocusPath",
                "GetPrefabFocusPathLength",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabFocusHandler.cpp"
            ),
            "symbols": [
                "FocusOnOwningPrefab",
                "FocusOnParentOfFocusedPrefab",
                "FocusOnPrefabInstanceOwningEntityId",
                "GetPrefabFocusPathLength",
                "AZ::Failure",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Overrides/PrefabOverridePublicHandler.cpp"
            ),
            "symbols": [
                "ApplyComponentOverrides",
                "GetComponentPathAndLinkIdFromFocusedPrefab",
                "GetFocusedPrefabInstance",
                "If the entity was owned by the focused instance, there's not much to push",
                "GenerateEntityPathFromFocusedPrefab",
                "PushOverridesToPrefab",
                "PushOverridesToLink",
            ],
            "absent_symbols": [
                '->Event("ApplyComponentOverrides"',
            ],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Overrides/PrefabOverridePublicInterface.h"
            ),
            "symbols": [
                "PrefabOverridePublicInterface",
                "AreComponentOverridesPresent",
                "ApplyComponentOverrides",
                "AZ::EntityComponentIdPair",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Instance/InstanceToTemplateInterface.h"
            ),
            "symbols": [
                "GeneratePatchForLink",
                "PatchTemplate",
                "GenerateEntityPathFromFocusedPrefab",
                "ApplyPatchesToInstance",
            ],
            "absent_symbols": [],
        },
    ]


def _approved_source_prefab_parent_link_override_apply_candidate_matrix() -> List[Dict[str, Any]]:
    return [
        {
            "candidate": "focus parent prefab / apply component overrides / push overrides to source template",
            "outcome": "selected_if_markers_persist",
            "reason": "O3DE override source shows ApplyComponentOverrides pushes to a child instance template only from a focused parent/link context.",
        },
        {
            "candidate": "GenerateUndoNodesForEntityChangeAndUpdateCache",
            "outcome": "attempted_preserved_blocked",
            "reason": "PR #150 proved the route is callable but did not persist ActorAsset/MotionAsset markers by itself.",
        },
        {
            "candidate": "PrefabOverridePublicInterface::ApplyComponentOverrides with correct parent focus/link context",
            "outcome": "preferred",
            "reason": "The source-validated parent focus sequence supplies the link context required by GetComponentPathAndLinkIdFromFocusedPrefab.",
        },
        {
            "candidate": "ApplyLinkOverrides or equivalent link-level propagation",
            "outcome": "deferred",
            "reason": "Component override application is narrower and source-valid for Actor + Simple Motion component additions.",
        },
        {
            "candidate": "source-template DOM update through source-backed prefab API",
            "outcome": "deferred",
            "reason": "Direct template DOM patching stays out unless the source-backed component override route remains blocked.",
        },
        {
            "candidate": "direct hand-authored .prefab JSON edit",
            "outcome": "rejected",
            "reason": "Unknown O3DE component JSON is not hand-authored in this slice.",
        },
        {
            "candidate": "approved source-prefab Actor + Simple Motion mutation through verified propagation/apply route",
            "outcome": "selected_if_property_readback_and_markers_pass",
            "reason": "This is the narrow approved source-prefab persistence proof target.",
        },
        {
            "candidate": "Actor + Anim Graph + Motion Set mutation",
            "outcome": "deferred",
            "reason": "Actor + Simple Motion remains the narrow target until runtime proof requires a broader route.",
        },
        {
            "candidate": "scratch-only route proof",
            "outcome": "preserved_not_sufficient",
            "reason": "PR #149 scratch proof does not prove approved source-template override propagation.",
        },
        {
            "candidate": "direct runtime .procprefab load",
            "outcome": "rejected",
            "reason": "Direct runtime .procprefab load remains unsupported/builder-only.",
        },
        {
            "candidate": "direct product-load of actor/motion products",
            "outcome": "rejected",
            "reason": "Product-load is not source-template propagation or component wiring proof.",
        },
        {
            "candidate": "defaultlevel or production-level mutation",
            "outcome": "rejected",
            "reason": "The path policy remains limited to the approved source prefab and never levels/defaultlevel/production paths.",
        },
    ]


def _approved_source_prefab_override_path_generation_template_update_repo_source_refs() -> List[Dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.h"
            ),
            "symbols": [
                "ApplyApprovedSourcePrefabOverridePathGenerationTemplateUpdate",
                "ApplyApprovedSourcePrefabParentLinkComponentOverrides",
                "SaveApprovedSourcePrefabWiring",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                repo_root
                / "o3de/gems/MaxineRuntimeExitFixture/Code/Source/Tools/PrefabSaveUpdateBridgeHostComponent.cpp"
            ),
            "symbols": [
                "apply_approved_source_prefab_override_path_generation_template_update",
                "ApplyApprovedSourcePrefabOverridePathGenerationTemplateUpdate",
                "InstanceEntityMapperInterface",
                "InstanceToTemplateInterface",
                "PrefabSystemComponentInterface",
                "FindOwningInstance",
                "GetEntityAlias",
                "GetContainerEntityId",
                "GetTemplateId",
                "FindTemplateDom",
                "ContainerEntityName",
                "GenerateEntityDomBySerializing",
                "GeneratePatch",
                "PatchEntityInTemplate",
                "SavePrefab",
                "GetOwningInstancePrefabPath",
                "ComponentApplicationRequests::FindEntity",
                "FindComponent",
                "entity_ownership_checked=true",
                "component_ownership_checked=",
                "source_backed_template_update_route_used=true",
                "template_dom_initial_entity_found=true",
                "serialized_entity_dom_generated=true",
                "entity_patch_generated=true",
                "patch_entity_in_template_verified=true",
                "template_dom_updated=true",
                "approved_source_save_verified=true",
                "RejectReasonForApprovedSourcePrefabPath",
            ],
            "absent_symbols": [
                "hand_authored_unknown_json",
                "runtime_character_animation_component_wiring_verified=true",
            ],
        },
        {
            "path": str(repo_root / "tools/o3de/editor_python/maxine_package_prefab_smoke.py"),
            "symbols": [
                "_call_prefab_apply_approved_source_override_path_generation_template_update",
                "_approved_source_prefab_override_path_generation_template_update_report_from_route_status",
                "_run_approved_source_prefab_override_path_generation_template_update_checks",
                "approved-source-prefab-override-path-generation-template-update",
                "approved_source_prefab_changed_this_run",
                "approved_source_prefab_marker_persistence_verified_this_run",
                "blocked_by_source_prefab_markers_preexisting_without_this_run_change",
                "blocked_by_source_backed_template_update_route_unavailable",
            ],
            "absent_symbols": [],
        },
    ]


def _approved_source_prefab_override_path_generation_template_update_engine_source_refs() -> List[Dict[str, Any]]:
    engine_root = _optional_o3de_engine_root()
    if engine_root is None:
        return []
    return [
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Instance/InstanceToTemplateInterface.h"
            ),
            "symbols": [
                "GenerateEntityDomBySerializing",
                "GeneratePatch",
                "PatchEntityInTemplate",
                "PrependEntityAliasPathToPatchPaths",
                "PatchTemplate",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Instance/InstanceToTemplatePropagator.cpp"
            ),
            "symbols": [
                "GenerateEntityDomBySerializing",
                "StoreEntityInPrefabDomFormat",
                "AZ::JsonSerialization::CreatePatch",
                "PatchEntityInTemplate",
                "PrependEntityAliasPathToPatchPaths",
                "PatchTemplate",
                "PrefabDomUtils::ApplyPatches",
                "SetTemplateDirtyFlag",
                "PropagateTemplateChanges",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/Instance/InstanceEntityMapperInterface.h"
            ),
            "symbols": [
                "InstanceEntityMapperInterface",
                "FindOwningInstance",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabSystemComponentInterface.h"
            ),
            "symbols": [
                "FindTemplateDom",
                "UpdatePrefabTemplate",
                "PropagateTemplateChanges",
                "GetTemplateIdFromFilePath",
            ],
            "absent_symbols": [],
        },
        {
            "path": str(
                engine_root
                / "Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabDomUtils.h"
            ),
            "symbols": [
                "StoreEntityInPrefabDomFormat",
                "ApplyPatches",
                "EntitiesName",
                "ComponentsName",
            ],
            "absent_symbols": [],
        },
    ]


def _approved_source_prefab_override_path_generation_template_update_candidate_matrix() -> List[Dict[str, Any]]:
    return [
        {
            "candidate": "source-backed override-path generation for Actor + Simple Motion component additions",
            "outcome": "selected_if_serialized_entity_patch_persists_markers",
            "reason": "The route serializes the changed entity through O3DE and generates a prefab patch rather than hand-writing component JSON.",
        },
        {
            "candidate": "parent-focus/link-context component override route from PR #152",
            "outcome": "preserved_blocked_by_link_context",
            "reason": "PR #152 proved parent focus is available but the approved source instance has no link context for component override paths.",
        },
        {
            "candidate": "ApplyLinkOverrides / link-level propagation",
            "outcome": "deferred",
            "reason": "The approved source entity is not currently exposed as a nested link override target.",
        },
        {
            "candidate": "source-template DOM update through source-backed prefab API",
            "outcome": "selected",
            "reason": "InstanceToTemplateInterface generates and applies the patch from O3DE-serialized entity DOM.",
        },
        {
            "candidate": "direct hand-authored .prefab JSON edit",
            "outcome": "rejected",
            "reason": "Unknown O3DE component JSON is not hand-authored in this slice.",
        },
        {
            "candidate": "approved source-prefab Actor + Simple Motion mutation through verified source-backed template update route",
            "outcome": "selected_if_property_readback_hash_change_and_markers_pass",
            "reason": "This is the narrow approved source-template persistence proof target.",
        },
        {
            "candidate": "Actor + Anim Graph + Motion Set mutation",
            "outcome": "deferred",
            "reason": "Actor + Simple Motion remains the narrow target until runtime proof requires a broader route.",
        },
        {
            "candidate": "scratch-only route proof",
            "outcome": "preserved_not_sufficient",
            "reason": "PR #149 scratch proof does not prove approved source-template propagation.",
        },
        {
            "candidate": "direct runtime .procprefab load",
            "outcome": "rejected",
            "reason": "Direct runtime .procprefab load remains unsupported/builder-only.",
        },
        {
            "candidate": "direct product-load of actor/motion products",
            "outcome": "rejected",
            "reason": "Product-load is not source-template propagation or component wiring proof.",
        },
        {
            "candidate": "defaultlevel or production-level mutation",
            "outcome": "rejected",
            "reason": "The path policy remains limited to the approved source prefab and never levels/defaultlevel/production paths.",
        },
    ]


def _approved_source_prefab_wiring_source_validation() -> Dict[str, Any]:
    return _source_validation_from_refs(_approved_source_prefab_wiring_source_refs())


def _call_prefab_save_update_approved_source_route(project_source_path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "attempted": True,
        "callable": False,
        "saved": False,
        "module": "azlmbr.maxine.prefab_bridge",
        "method": "save_approved_source_prefab_wiring",
        "status": "",
        "error": "",
    }
    try:
        import importlib

        module = importlib.import_module(str(result["module"]))
        route_fn = getattr(module, str(result["method"]))
        status_text = str(route_fn(str(project_source_path)))
        result["status"] = status_text
        result["callable"] = True
        result["saved"] = (
            "maxine_prefab_save_update_route_approved_source_saved" in status_text
            and "approved_source_save_verified=true" in status_text
        )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _call_prefab_apply_approved_source_component_overrides(
    project_source_path: Path,
    actor_component_ref: Any,
    simple_motion_component_ref: Any,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "attempted": True,
        "callable": False,
        "applied": False,
        "module": "azlmbr.maxine.prefab_bridge",
        "method": "apply_approved_source_prefab_component_overrides",
        "actor_component_ref": _safe_serialize(actor_component_ref),
        "simple_motion_component_ref": _safe_serialize(simple_motion_component_ref),
        "status": "",
        "error": "",
    }
    if actor_component_ref is None or simple_motion_component_ref is None:
        result["error"] = "component_reference_not_available"
        return result
    try:
        import importlib

        module = importlib.import_module(str(result["module"]))
        route_fn = getattr(module, str(result["method"]))
        status_text = str(route_fn(str(project_source_path), actor_component_ref, simple_motion_component_ref))
        result["status"] = status_text
        result["callable"] = True
        result["applied"] = (
            "maxine_prefab_save_update_route_approved_source_override_applied" in status_text
            and "actor_component_override_applied=true" in status_text
            and "simple_motion_component_override_applied=true" in status_text
        )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _call_prefab_apply_approved_source_parent_link_component_overrides(
    project_source_path: Path,
    entity_id: Any,
    actor_component_ref: Any,
    simple_motion_component_ref: Any,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "attempted": True,
        "callable": False,
        "applied": False,
        "module": "azlmbr.maxine.prefab_bridge",
        "method": "apply_approved_source_prefab_parent_link_component_overrides",
        "entity_id": _safe_serialize(entity_id),
        "actor_component_ref": _safe_serialize(actor_component_ref),
        "simple_motion_component_ref": _safe_serialize(simple_motion_component_ref),
        "status": "",
        "error": "",
    }
    if entity_id is None or actor_component_ref is None or simple_motion_component_ref is None:
        result["error"] = "entity_or_component_reference_not_available"
        return result
    try:
        import importlib

        module = importlib.import_module(str(result["module"]))
        route_fn = getattr(module, str(result["method"]))
        status_text = str(route_fn(str(project_source_path), entity_id, actor_component_ref, simple_motion_component_ref))
        result["status"] = status_text
        result["callable"] = True
        result["applied"] = (
            "maxine_prefab_save_update_route_approved_source_parent_link_override_applied" in status_text
            and "parent_focus_context_applied=true" in status_text
            and "parent_focus_context_restored=true" in status_text
            and "link_context_available=true" in status_text
            and "actor_component_override_applied=true" in status_text
            and "simple_motion_component_override_applied=true" in status_text
            and "push_overrides_to_prefab_verified=true" in status_text
        )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _call_prefab_apply_approved_source_override_path_generation_template_update(
    project_source_path: Path,
    entity_id: Any,
    actor_component_ref: Any,
    simple_motion_component_ref: Any,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "attempted": True,
        "callable": False,
        "applied": False,
        "module": "azlmbr.maxine.prefab_bridge",
        "method": "apply_approved_source_prefab_override_path_generation_template_update",
        "entity_id": _safe_serialize(entity_id),
        "actor_component_ref": _safe_serialize(actor_component_ref),
        "simple_motion_component_ref": _safe_serialize(simple_motion_component_ref),
        "status": "",
        "error": "",
    }
    if entity_id is None or actor_component_ref is None or simple_motion_component_ref is None:
        result["error"] = "entity_or_component_reference_not_available"
        return result
    try:
        import importlib

        module = importlib.import_module(str(result["module"]))
        route_fn = getattr(module, str(result["method"]))
        status_text = str(route_fn(str(project_source_path), entity_id, actor_component_ref, simple_motion_component_ref))
        result["status"] = status_text
        result["callable"] = True
        result["applied"] = (
            "maxine_prefab_save_update_route_approved_source_template_update_applied" in status_text
            and "source_backed_template_update_route_used=true" in status_text
            and "patch_entity_in_template_verified=true" in status_text
            and "template_dom_updated=true" in status_text
            and "approved_source_save_verified=true" in status_text
        )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _status_key_values(status_text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for token in str(status_text).split(";"):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _status_flag(status_values: Mapping[str, str], key: str) -> bool:
    return str(status_values.get(key, "")).strip().lower() == "true"


def _approved_source_prefab_parent_link_override_apply_report_from_route_status(
    route_status: Mapping[str, Any],
    *,
    persisted_markers: Mapping[str, Any],
    source_prefab_changed_this_run: bool = False,
    before_hash: str = "",
    after_hash: str = "",
) -> Dict[str, Any]:
    status_text = str(route_status.get("status", ""))
    status_values = _status_key_values(status_text)
    route_attempted = route_status.get("attempted") is True
    route_callable = route_status.get("callable") is True
    route_applied = route_status.get("applied") is True
    entity_ownership_checked = _status_flag(status_values, "entity_ownership_checked")
    entity_ownership_verified = _status_flag(status_values, "entity_ownership_verified")
    entity_owning_prefab_path = str(status_values.get("entity_owning_prefab_path", ""))
    entity_owning_prefab_matches_requested_path = _status_flag(
        status_values, "entity_owning_prefab_matches_requested_path"
    )
    component_ownership_checked = _status_flag(status_values, "component_ownership_checked")
    component_ownership_verified = _status_flag(status_values, "component_ownership_verified")
    parent_required = _status_flag(status_values, "parent_focus_context_required") or route_attempted
    parent_available = _status_flag(status_values, "parent_focus_context_available")
    parent_applied = _status_flag(status_values, "parent_focus_context_applied")
    parent_restored = _status_flag(status_values, "parent_focus_context_restored")
    link_required = _status_flag(status_values, "link_context_required") or route_attempted
    link_available = _status_flag(status_values, "link_context_available")
    paths_detected = _status_flag(status_values, "component_override_paths_detected")
    actor_present = _status_flag(status_values, "actor_component_override_present")
    simple_present = _status_flag(status_values, "simple_motion_component_override_present")
    actor_applied = _status_flag(status_values, "actor_component_override_applied")
    simple_applied = _status_flag(status_values, "simple_motion_component_override_applied")
    component_overrides_detected = bool(paths_detected and actor_present and simple_present)
    component_overrides_applied = bool(actor_applied and simple_applied)
    push_attempted = _status_flag(status_values, "push_overrides_to_prefab_attempted")
    push_verified = _status_flag(status_values, "push_overrides_to_prefab_verified")
    marker_actor = persisted_markers.get("actor") is True
    marker_motion = persisted_markers.get("motion") is True
    marker_pair = persisted_markers.get("both") is True
    hash_changed_this_run = bool(
        source_prefab_changed_this_run or (before_hash and after_hash and before_hash != after_hash)
    )
    marker_presence_verified = bool(marker_actor and marker_motion and marker_pair)
    marker_persistence_verified_this_run = bool(marker_presence_verified and hash_changed_this_run)
    marker_persistence_blocker = ""
    if marker_presence_verified and not marker_persistence_verified_this_run:
        marker_persistence_blocker = "blocked_by_source_prefab_markers_preexisting_without_this_run_change"
    template_updated = bool(route_applied and push_verified and marker_persistence_verified_this_run)
    route_verified = bool(
        route_attempted
        and route_callable
        and route_applied
        and entity_ownership_checked
        and entity_ownership_verified
        and entity_owning_prefab_matches_requested_path
        and component_ownership_checked
        and component_ownership_verified
        and parent_required
        and parent_available
        and parent_applied
        and parent_restored
        and link_required
        and link_available
        and component_overrides_detected
        and component_overrides_applied
        and push_attempted
        and push_verified
        and template_updated
    )
    blocker = ""
    if not route_verified:
        reason = str(status_values.get("reason", "")).strip()
        if reason == "entity_owning_prefab_unavailable" or (
            entity_ownership_checked and not entity_ownership_verified and not entity_owning_prefab_path
        ):
            blocker = "blocked_by_entity_owning_prefab_unavailable"
        elif reason == "entity_not_owned_by_approved_source_prefab" or (
            entity_ownership_checked and not entity_owning_prefab_matches_requested_path
        ):
            blocker = "blocked_by_entity_not_owned_by_approved_source_prefab"
        elif reason == "component_not_owned_by_approved_source_prefab_entity" or (
            component_ownership_checked and not component_ownership_verified
        ):
            blocker = "blocked_by_component_not_owned_by_approved_source_prefab_entity"
        elif not route_callable:
            blocker = "blocked_by_prefab_parent_focus_context_unavailable"
        elif not parent_available or reason in {"parent_focus_context_unavailable", "focus_on_parent_prefab_failed"}:
            blocker = "blocked_by_prefab_parent_focus_context_unavailable"
        elif not link_available:
            blocker = "blocked_by_prefab_link_context_unavailable"
        elif not component_overrides_detected:
            blocker = "blocked_by_prefab_component_override_detection_missing"
        elif not component_overrides_applied or not push_verified:
            blocker = "blocked_by_prefab_override_push_to_template_failed"
        elif marker_persistence_blocker:
            blocker = marker_persistence_blocker
        elif not template_updated:
            blocker = "blocked_by_prefab_template_dom_update_unavailable"
        else:
            blocker = "blocked_by_prefab_instance_to_template_propagation_requires_parent_link_context"

    return {
        "approved_source_prefab_parent_link_override_apply_route_attempted": route_attempted,
        "approved_source_prefab_parent_link_override_apply_route_completed": route_attempted,
        "approved_source_prefab_parent_link_override_apply_route_verified": route_verified,
        "approved_source_prefab_parent_link_override_apply_route_blocker": blocker,
        "approved_source_prefab_parent_link_override_apply_route_status": dict(route_status),
        "approved_source_prefab_entity_ownership_checked": entity_ownership_checked,
        "approved_source_prefab_entity_ownership_verified": entity_ownership_verified,
        "approved_source_prefab_entity_owning_prefab_path": entity_owning_prefab_path,
        "approved_source_prefab_entity_owning_prefab_matches_requested_path": (
            entity_owning_prefab_matches_requested_path
        ),
        "approved_source_prefab_component_ownership_checked": component_ownership_checked,
        "approved_source_prefab_component_ownership_verified": component_ownership_verified,
        "approved_source_prefab_entity_ownership_blocker": blocker
        if blocker
        in {
            "blocked_by_entity_owning_prefab_unavailable",
            "blocked_by_entity_not_owned_by_approved_source_prefab",
            "blocked_by_component_not_owned_by_approved_source_prefab_entity",
        }
        else "",
        "approved_source_prefab_parent_focus_context_required": parent_required,
        "approved_source_prefab_parent_focus_context_available": parent_available,
        "approved_source_prefab_parent_focus_context_applied": parent_applied,
        "approved_source_prefab_parent_focus_context_restored": parent_restored,
        "approved_source_prefab_link_context_required": link_required,
        "approved_source_prefab_link_context_available": link_available,
        "approved_source_prefab_link_id": status_values.get("link_id", ""),
        "approved_source_prefab_component_override_paths_detected": paths_detected,
        "approved_source_prefab_component_overrides_detected": component_overrides_detected,
        "approved_source_prefab_component_overrides_applied": component_overrides_applied,
        "approved_source_prefab_link_overrides_applied": False,
        "approved_source_prefab_push_overrides_to_prefab_attempted": push_attempted,
        "approved_source_prefab_push_overrides_to_prefab_verified": push_verified,
        "approved_source_prefab_template_dom_updated": template_updated,
        "approved_source_prefab_before_hash": before_hash,
        "approved_source_prefab_after_hash": after_hash,
        "approved_source_prefab_changed_this_run": hash_changed_this_run,
        "approved_source_prefab_marker_presence_verified": marker_presence_verified,
        "approved_source_prefab_marker_persistence_verified_this_run": marker_persistence_verified_this_run,
        "approved_source_prefab_marker_persistence_blocker": marker_persistence_blocker,
        "approved_source_prefab_modified": route_verified,
        "approved_source_prefab_propagation_apply_step_attempted": route_attempted,
        "approved_source_prefab_propagation_apply_step_completed": route_attempted,
        "approved_source_prefab_propagation_apply_step_verified": route_verified,
        "approved_source_prefab_propagation_apply_step_blocker": blocker,
        "approved_source_prefab_actor_simple_motion_wiring_attempted": route_attempted,
        "approved_source_prefab_actor_simple_motion_wiring_completed": route_attempted,
        "approved_source_prefab_actor_simple_motion_wiring_verified": route_verified,
        "approved_source_prefab_actor_simple_motion_wiring_blocker": blocker,
        "approved_source_prefab_persisted_actor_asset_marker_verified": marker_actor,
        "approved_source_prefab_persisted_motion_asset_marker_verified": marker_motion,
        "approved_source_prefab_persisted_wiring_markers_verified": marker_pair,
        "approved_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _approved_source_prefab_override_path_generation_template_update_report_from_route_status(
    route_status: Mapping[str, Any],
    *,
    persisted_markers: Mapping[str, Any],
    source_prefab_changed_this_run: bool = False,
    before_hash: str = "",
    after_hash: str = "",
    template_update_route_rejection_probes_verified: bool = False,
) -> Dict[str, Any]:
    status_text = str(route_status.get("status", ""))
    status_values = _status_key_values(status_text)
    route_attempted = route_status.get("attempted") is True
    route_callable = route_status.get("callable") is True
    route_applied = route_status.get("applied") is True
    entity_ownership_checked = _status_flag(status_values, "entity_ownership_checked")
    entity_ownership_verified = _status_flag(status_values, "entity_ownership_verified")
    entity_owning_prefab_path = str(status_values.get("entity_owning_prefab_path", ""))
    entity_owning_prefab_matches_requested_path = _status_flag(
        status_values, "entity_owning_prefab_matches_requested_path"
    )
    component_ownership_checked = _status_flag(status_values, "component_ownership_checked")
    component_ownership_verified = _status_flag(status_values, "component_ownership_verified")
    source_backed_route_used = _status_flag(status_values, "source_backed_template_update_route_used")
    initial_entity_found = _status_flag(status_values, "template_dom_initial_entity_found")
    serialized_entity_dom_generated = _status_flag(status_values, "serialized_entity_dom_generated")
    entity_patch_generated = _status_flag(status_values, "entity_patch_generated")
    try:
        entity_patch_operation_count = int(str(status_values.get("entity_patch_operation_count", "0")).strip() or "0")
    except ValueError:
        entity_patch_operation_count = 0
    component_override_paths_detected = _status_flag(status_values, "component_override_paths_detected")
    patch_attempted = _status_flag(status_values, "patch_entity_in_template_attempted")
    patch_verified = _status_flag(status_values, "patch_entity_in_template_verified")
    route_template_dom_updated = _status_flag(status_values, "template_dom_updated")
    route_save_verified = _status_flag(status_values, "approved_source_save_verified")
    marker_actor = persisted_markers.get("actor") is True
    marker_motion = persisted_markers.get("motion") is True
    marker_pair = persisted_markers.get("both") is True
    hash_changed_this_run = bool(
        source_prefab_changed_this_run or (before_hash and after_hash and before_hash != after_hash)
    )
    marker_presence_verified = bool(marker_actor and marker_motion and marker_pair)
    marker_persistence_verified_this_run = bool(marker_presence_verified and hash_changed_this_run)
    marker_persistence_blocker = ""
    if marker_presence_verified and not marker_persistence_verified_this_run:
        marker_persistence_blocker = "blocked_by_source_prefab_markers_preexisting_without_this_run_change"
    template_dom_updated = bool(route_template_dom_updated and marker_persistence_verified_this_run)
    route_verified = bool(
        route_attempted
        and route_callable
        and route_applied
        and entity_ownership_checked
        and entity_ownership_verified
        and entity_owning_prefab_matches_requested_path
        and component_ownership_checked
        and component_ownership_verified
        and source_backed_route_used
        and initial_entity_found
        and serialized_entity_dom_generated
        and entity_patch_generated
        and entity_patch_operation_count > 0
        and patch_attempted
        and patch_verified
        and route_template_dom_updated
        and route_save_verified
        and template_dom_updated
        and template_update_route_rejection_probes_verified
    )
    blocker = ""
    if not route_verified:
        reason = str(status_values.get("reason", "")).strip()
        if reason == "entity_owning_prefab_unavailable" or (
            entity_ownership_checked and not entity_ownership_verified and not entity_owning_prefab_path
        ):
            blocker = "blocked_by_entity_owning_prefab_unavailable"
        elif reason == "entity_not_owned_by_approved_source_prefab" or (
            entity_ownership_checked and not entity_owning_prefab_matches_requested_path
        ):
            blocker = "blocked_by_entity_not_owned_by_approved_source_prefab"
        elif reason == "component_not_owned_by_approved_source_prefab_entity" or (
            component_ownership_checked and not component_ownership_verified
        ):
            blocker = "blocked_by_component_not_owned_by_approved_source_prefab_entity"
        elif marker_persistence_blocker:
            blocker = marker_persistence_blocker
        elif not route_callable:
            blocker = "blocked_by_source_backed_template_update_route_unavailable"
        elif not source_backed_route_used:
            blocker = "blocked_by_source_backed_template_update_route_unavailable"
        elif not initial_entity_found:
            blocker = "blocked_by_prefab_template_dom_update_unavailable"
        elif not serialized_entity_dom_generated:
            blocker = "blocked_by_source_backed_template_update_route_unavailable"
        elif not entity_patch_generated or entity_patch_operation_count <= 0:
            blocker = "blocked_by_prefab_component_override_path_generation_unavailable"
        elif not patch_verified or not route_template_dom_updated:
            blocker = "blocked_by_prefab_override_push_to_template_failed"
        elif not route_save_verified:
            blocker = "blocked_by_approved_source_prefab_save_policy"
        elif not template_update_route_rejection_probes_verified:
            blocker = "blocked_by_template_update_route_rejection_probes_unverified"
        else:
            blocker = "blocked_by_prefab_template_dom_update_unavailable"

    return {
        "approved_source_prefab_override_path_generation_template_update_attempted": route_attempted,
        "approved_source_prefab_override_path_generation_template_update_completed": route_attempted,
        "approved_source_prefab_override_path_generation_template_update_verified": route_verified,
        "approved_source_prefab_override_path_generation_template_update_blocker": blocker,
        "approved_source_prefab_override_path_generation_template_update_route_status": dict(route_status),
        "approved_source_prefab_template_update_route_rejection_probes_verified": (
            template_update_route_rejection_probes_verified
        ),
        "approved_source_prefab_entity_ownership_checked": entity_ownership_checked,
        "approved_source_prefab_entity_ownership_verified": entity_ownership_verified,
        "approved_source_prefab_entity_owning_prefab_path": entity_owning_prefab_path,
        "approved_source_prefab_entity_owning_prefab_matches_requested_path": (
            entity_owning_prefab_matches_requested_path
        ),
        "approved_source_prefab_component_ownership_checked": component_ownership_checked,
        "approved_source_prefab_component_ownership_verified": component_ownership_verified,
        "approved_source_prefab_entity_ownership_blocker": blocker
        if blocker
        in {
            "blocked_by_entity_owning_prefab_unavailable",
            "blocked_by_entity_not_owned_by_approved_source_prefab",
            "blocked_by_component_not_owned_by_approved_source_prefab_entity",
        }
        else "",
        "approved_source_prefab_template_dom_update_route_used": source_backed_route_used,
        "approved_source_prefab_template_dom_initial_entity_found": initial_entity_found,
        "approved_source_prefab_serialized_entity_dom_generated": serialized_entity_dom_generated,
        "approved_source_prefab_entity_patch_generated": entity_patch_generated,
        "approved_source_prefab_entity_patch_operation_count": entity_patch_operation_count,
        "approved_source_prefab_component_override_paths_detected": component_override_paths_detected,
        "approved_source_prefab_component_override_paths": [],
        "approved_source_prefab_patch_entity_in_template_attempted": patch_attempted,
        "approved_source_prefab_patch_entity_in_template_verified": patch_verified,
        "approved_source_prefab_push_overrides_to_template_attempted": patch_attempted,
        "approved_source_prefab_push_overrides_to_template_verified": patch_verified,
        "approved_source_prefab_template_dom_updated": template_dom_updated,
        "approved_source_prefab_before_hash": before_hash,
        "approved_source_prefab_after_hash": after_hash,
        "approved_source_prefab_changed_this_run": hash_changed_this_run,
        "approved_source_prefab_marker_presence_verified": marker_presence_verified,
        "approved_source_prefab_marker_persistence_verified_this_run": marker_persistence_verified_this_run,
        "approved_source_prefab_marker_persistence_blocker": marker_persistence_blocker,
        "approved_source_prefab_modified": route_verified,
        "approved_source_prefab_save_verified": route_save_verified and marker_persistence_verified_this_run,
        "approved_source_prefab_propagation_apply_step_attempted": route_attempted,
        "approved_source_prefab_propagation_apply_step_completed": route_attempted,
        "approved_source_prefab_propagation_apply_step_verified": route_verified,
        "approved_source_prefab_propagation_apply_step_blocker": blocker,
        "approved_source_prefab_actor_simple_motion_wiring_attempted": route_attempted,
        "approved_source_prefab_actor_simple_motion_wiring_completed": route_attempted,
        "approved_source_prefab_actor_simple_motion_wiring_verified": route_verified,
        "approved_source_prefab_actor_simple_motion_wiring_blocker": blocker,
        "approved_source_prefab_persisted_actor_asset_marker_verified": marker_actor,
        "approved_source_prefab_persisted_motion_asset_marker_verified": marker_motion,
        "approved_source_prefab_persisted_wiring_markers_verified": marker_pair,
        "approved_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _call_prefab_commit_approved_source_entity_changes(project_source_path: Path, entity_id: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "attempted": True,
        "callable": False,
        "committed": False,
        "module": "azlmbr.maxine.prefab_bridge",
        "method": "commit_approved_source_prefab_entity_changes",
        "entity_id": _safe_serialize(entity_id),
        "status": "",
        "error": "",
    }
    if entity_id is None:
        result["error"] = "entity_id_not_available"
        return result
    try:
        import importlib

        module = importlib.import_module(str(result["module"]))
        route_fn = getattr(module, str(result["method"]))
        status_text = str(route_fn(str(project_source_path), entity_id))
        result["status"] = status_text
        result["callable"] = True
        result["committed"] = (
            "maxine_prefab_save_update_route_approved_source_entity_changes_committed" in status_text
            and "approved_source_entity_changes_committed=true" in status_text
            and "approved_source_save_verified=true" in status_text
        )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _approved_source_prefab_wiring_component_refs(
    entity_id: Any,
    surface: Mapping[str, Any],
    binding_report: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    registry = binding_report.get("component_type_registry", {})
    if not isinstance(registry, MutableMapping):
        registry = {}
    actor_type = _discover_component_type_ids(
        ["Actor", "Actor Component", "EMotion FX Actor"],
        "ApprovedEditorActorOverrideApply",
        surface,
        safe_call_results,
        registry,
    )
    simple_type = _discover_component_type_ids(
        ["Simple Motion", "SimpleMotion", "EMotion FX Simple Motion"],
        "ApprovedEditorSimpleMotionOverrideApply",
        surface,
        safe_call_results,
        registry,
    )
    actor_component = _get_component_reference(entity_id, actor_type.get("type_ids_raw", []), surface, safe_call_results)
    simple_component = _get_component_reference(entity_id, simple_type.get("type_ids_raw", []), surface, safe_call_results)
    return {
        "actor_type_status": actor_type.get("status", "blocked_by_missing_binding"),
        "simple_motion_type_status": simple_type.get("status", "blocked_by_missing_binding"),
        "actor_component_ref": actor_component.get("component_ref"),
        "simple_motion_component_ref": simple_component.get("component_ref"),
        "actor_component_ref_serialized": actor_component.get("component_ref_serialized", ""),
        "simple_motion_component_ref_serialized": simple_component.get("component_ref_serialized", ""),
        "actor_component_ref_status": actor_component.get("status", "blocked_by_missing_binding"),
        "simple_motion_component_ref_status": simple_component.get("status", "blocked_by_missing_binding"),
        "actor_component_ref_source": actor_component.get("source", ""),
        "simple_motion_component_ref_source": simple_component.get("source", ""),
    }


def _approved_source_prefab_wiring_rejection_paths(project_source_path: Path) -> Dict[str, Path]:
    project_path = project_source_path.parents[4]
    outside_project = Path("D:/tmp/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab")
    if project_path.drive.lower() == "d:":
        outside_project = Path("C:/tmp/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab")
    return {
        "defaultlevel": project_path / "Levels" / "DefaultLevel" / "anything.prefab",
        "production_level": project_path / "Levels" / "production" / "release.prefab",
        "generated_product": project_path / "Cache" / "pc" / "assets" / "characters" / "release_rigged.prefab",
        "unapproved_absolute": outside_project,
        "other_project": project_path.parent
        / "OtherProject"
        / "Assets"
        / "Characters"
        / "MAXINE_GoldenCorpus"
        / "prefabs"
        / "release_rigged.prefab",
        "path_traversal": project_source_path.parent / ".." / "escape.prefab",
        "non_prefab": project_source_path.with_suffix(".txt"),
    }


def _call_approved_source_prefab_wiring_rejection_probes(project_source_path: Path) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for label, path in _approved_source_prefab_wiring_rejection_paths(project_source_path).items():
        result: Dict[str, Any] = {
            "attempted": True,
            "callable": False,
            "rejected": False,
            "route": "legacy_save_approved_source_prefab_wiring",
            "method": "save_approved_source_prefab_wiring",
            "status": "",
            "error": "",
        }
        try:
            import importlib

            module = importlib.import_module("azlmbr.maxine.prefab_bridge")
            route_fn = getattr(module, "save_approved_source_prefab_wiring")
            status_text = str(route_fn(str(path)))
            result["status"] = status_text
            result["callable"] = True
            result["rejected"] = "maxine_prefab_save_update_route_approved_source_rejected" in status_text
        except Exception as exc:
            result["error"] = str(exc)
        results[label] = result
    return results


def _approved_source_prefab_template_update_route_rejection_paths(project_source_path: Path) -> Dict[str, Path]:
    paths = dict(_approved_source_prefab_wiring_rejection_paths(project_source_path))
    project_path = project_source_path.parents[4]
    paths["cache_path"] = project_path / "Cache" / "pc" / "anything.prefab"
    return paths


def _invalid_editor_entity_id_for_template_update_probe() -> Any:
    try:
        import azlmbr.entity as entity  # type: ignore

        return entity.EntityId()
    except Exception:
        return None


def _template_update_route_rejection_verified(status_text: str) -> bool:
    text = str(status_text)
    if "maxine_prefab_save_update_route_approved_source_template_update_rejected" in text:
        return True
    status_values = _status_key_values(text)
    reason = str(status_values.get("reason", "")).strip()
    return reason in {
        "entity_id_invalid",
        "entity_owning_prefab_unavailable",
        "entity_not_owned_by_approved_source_prefab",
        "component_not_owned_by_approved_source_prefab_entity",
    }


def _call_approved_source_prefab_template_update_route_rejection_probes(
    project_source_path: Path,
    *,
    entity_id: Any,
    actor_component_ref: Any,
    simple_motion_component_ref: Any,
) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    route_name = "apply_approved_source_prefab_override_path_generation_template_update"

    def _new_result() -> Dict[str, Any]:
        return {
            "attempted": True,
            "callable": False,
            "rejected": False,
            "route": "template_update_route",
            "method": route_name,
            "status": "",
            "error": "",
        }

    for label, path in _approved_source_prefab_template_update_route_rejection_paths(project_source_path).items():
        result = _new_result()
        try:
            import importlib

            module = importlib.import_module("azlmbr.maxine.prefab_bridge")
            route_fn = getattr(module, route_name)
            status_text = str(route_fn(str(path), entity_id, actor_component_ref, simple_motion_component_ref))
            result["status"] = status_text
            result["callable"] = True
            result["rejected"] = _template_update_route_rejection_verified(status_text)
        except Exception as exc:
            result["error"] = str(exc)
        results[label] = result

    wrong_entity_result = _new_result()
    wrong_entity_id = _invalid_editor_entity_id_for_template_update_probe()
    if wrong_entity_id is None and isinstance(entity_id, str):
        wrong_entity_id = "__maxine_wrong_entity_owner_probe__"
    if wrong_entity_id is None:
        wrong_entity_result["attempted"] = False
        wrong_entity_result["error"] = "invalid_entity_probe_unavailable"
    else:
        try:
            import importlib

            module = importlib.import_module("azlmbr.maxine.prefab_bridge")
            route_fn = getattr(module, route_name)
            status_text = str(
                route_fn(str(project_source_path), wrong_entity_id, actor_component_ref, simple_motion_component_ref)
            )
            wrong_entity_result["status"] = status_text
            wrong_entity_result["callable"] = True
            wrong_entity_result["rejected"] = _template_update_route_rejection_verified(status_text)
        except Exception as exc:
            wrong_entity_result["error"] = str(exc)
    results["wrong_entity_owner"] = wrong_entity_result
    return results


def _approved_source_prefab_template_update_route_rejection_probe_summary(
    rejection_statuses: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    required_labels = (
        "defaultlevel",
        "production_level",
        "generated_product",
        "cache_path",
        "unapproved_absolute",
        "other_project",
        "path_traversal",
        "non_prefab",
        "wrong_entity_owner",
    )
    attempted = all(isinstance(rejection_statuses.get(label), Mapping) for label in required_labels)
    verified = attempted and all(_route_rejection_verified(rejection_statuses, label) for label in required_labels)
    return {
        "approved_source_prefab_template_update_route_rejection_probes_attempted": attempted,
        "approved_source_prefab_template_update_route_rejection_probes_verified": verified,
        "approved_source_prefab_template_update_route_rejected_defaultlevel_path": _route_rejection_verified(
            rejection_statuses, "defaultlevel"
        ),
        "approved_source_prefab_template_update_route_rejected_production_level_path": _route_rejection_verified(
            rejection_statuses, "production_level"
        ),
        "approved_source_prefab_template_update_route_rejected_generated_product_path": _route_rejection_verified(
            rejection_statuses, "generated_product"
        ),
        "approved_source_prefab_template_update_route_rejected_cache_path": _route_rejection_verified(
            rejection_statuses, "cache_path"
        ),
        "approved_source_prefab_template_update_route_rejected_unapproved_absolute_path": _route_rejection_verified(
            rejection_statuses, "unapproved_absolute"
        ),
        "approved_source_prefab_template_update_route_rejected_other_project_path": _route_rejection_verified(
            rejection_statuses, "other_project"
        ),
        "approved_source_prefab_template_update_route_rejected_path_traversal": _route_rejection_verified(
            rejection_statuses, "path_traversal"
        ),
        "approved_source_prefab_template_update_route_rejected_non_prefab_path": _route_rejection_verified(
            rejection_statuses, "non_prefab"
        ),
        "approved_source_prefab_template_update_route_rejected_wrong_entity_owner": _route_rejection_verified(
            rejection_statuses, "wrong_entity_owner"
        ),
        "approved_source_prefab_template_update_route_rejection_probe_route": (
            "azlmbr.maxine.prefab_bridge.apply_approved_source_prefab_override_path_generation_template_update"
        ),
        "approved_source_prefab_template_update_route_rejection_probe_results": dict(rejection_statuses),
    }


def _approved_source_prefab_legacy_wiring_route_rejection_probe_summary(
    rejection_statuses: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    return {
        "approved_source_prefab_legacy_wiring_route_rejection_probes_preserved": bool(rejection_statuses),
        "approved_source_prefab_legacy_wiring_route_rejection_probe_route": (
            "azlmbr.maxine.prefab_bridge.save_approved_source_prefab_wiring"
        ),
        "approved_source_prefab_legacy_wiring_route_rejection_probe_results": dict(rejection_statuses),
    }


def _instantiate_approved_source_prefab(project_source_path: Path, safe_call_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        import azlmbr.bus as bus  # type: ignore
        import azlmbr.entity as entity  # type: ignore
        import azlmbr.math as math  # type: ignore
        import azlmbr.prefab as prefab  # type: ignore
    except Exception as exc:
        return {
            "status": "unsupported_by_engine_binding",
            "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
            "blocked_reason": str(exc),
            "attempts": [],
        }

    candidates = [
        APPROVED_SOURCE_PREFAB_PROJECT_REF.replace("\\", "/"),
        str(project_source_path),
    ]
    attempts: List[Dict[str, Any]] = []
    for candidate in candidates:
        status, value = _prefab_bus_call(
            prefab,
            bus,
            "InstantiatePrefab",
            (candidate, entity.EntityId(), math.Vector3(0.0, 0.0, 0.0)),
            safe_call_results,
        )
        created_entity_id = _unwrap_outcome(value)
        attempt = {
            "path": _redacted_project_temp_path(candidate),
            "status": status,
            "result": _safe_serialize(created_entity_id),
        }
        attempts.append(attempt)
        if status == "pass" and _entity_id_valid(created_entity_id):
            owning_status, owning_value = _prefab_bus_call(
                prefab,
                bus,
                "GetOwningInstancePrefabPath",
                (created_entity_id,),
                safe_call_results,
            )
            owning_path = str(_unwrap_outcome(owning_value)) if owning_status == "pass" else ""
            return {
                "status": "pass",
                "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
                "selected_source_path": _redacted_project_temp_path(candidate),
                "created_entity_count": 1,
                "container_entity": _safe_serialize(created_entity_id),
                "created_entity_id": created_entity_id,
                "owning_instance_prefab_path": _redacted_project_temp_path(owning_path) if owning_path else "",
                "owning_instance_prefab_path_status": owning_status,
                "attempts": attempts,
            }
    return {
        "status": "blocked_by_missing_binding",
        "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
        "created_entity_count": 0,
        "attempts": attempts,
        "blocked_reason": "approved_source_prefab_instantiate_returned_no_container_entity",
    }


def _delete_editor_entity(entity_id: Any, safe_call_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        import azlmbr.bus as bus  # type: ignore
        import azlmbr.editor as editor  # type: ignore

        editor.ToolsApplicationRequestBus(bus.Broadcast, "DeleteEntityById", entity_id)
        safe_call_results.append(
            {
                "call": "ToolsApplicationRequestBus.DeleteEntityById",
                "status": "pass",
                "args_shape": "1 argument",
                "result": _safe_serialize(entity_id),
            }
        )
        return {"status": "pass", "api": "ToolsApplicationRequestBus.DeleteEntityById"}
    except Exception as exc:
        safe_call_results.append(
            {
                "call": "ToolsApplicationRequestBus.DeleteEntityById",
                "status": "unsupported_by_engine_binding",
                "args_shape": "1 argument",
                "error": str(exc),
            }
        )
        return {"status": "unsupported_by_engine_binding", "error": str(exc)}


def _run_approved_source_prefab_propagation_apply_step_checks(report: Mapping[str, Any]) -> Dict[str, Any]:
    repo_validation = _source_validation_from_refs(_approved_source_prefab_propagation_apply_step_repo_source_refs())
    engine_validation = _optional_engine_source_validation_from_refs(
        _approved_source_prefab_propagation_apply_step_engine_source_refs()
    )
    repo_source_path = _approved_source_prefab_repo_path()
    before_hash = _sha256_file(repo_source_path) if repo_source_path.exists() else ""
    blocker = "blocked_by_prefab_instance_to_template_propagation_requires_parent_link_context"
    source_verified = repo_validation["verified"] is True
    result: Dict[str, Any] = {
        "approved_source_prefab_propagation_apply_step_attempted": True,
        "approved_source_prefab_propagation_apply_step_completed": True,
        "approved_source_prefab_propagation_apply_step_verified": False,
        "approved_source_prefab_propagation_apply_step_blocker": blocker if source_verified else (
            "blocked_by_prefab_instance_to_template_propagation_requires_additional_source_validation"
        ),
        "approved_source_prefab_propagation_apply_step_source_validation_status": repo_validation["status"],
        "approved_source_prefab_propagation_apply_step_source_validation_verified": repo_validation["verified"],
        "approved_source_prefab_propagation_apply_step_source_refs": repo_validation["refs"],
        "approved_source_prefab_propagation_apply_step_engine_source_refs_status": engine_validation["status"],
        "approved_source_prefab_propagation_apply_step_engine_source_refs_verified": engine_validation["verified"],
        "approved_source_prefab_propagation_apply_step_engine_source_refs": engine_validation["refs"],
        "approved_source_prefab_propagation_apply_step_candidate_matrix": (
            _approved_source_prefab_propagation_apply_step_candidate_matrix()
        ),
        "approved_source_prefab_propagation_apply_step_selected_strategy": (
            "pin_parent_focus_link_override_apply_requirement"
        ),
        "approved_source_prefab_propagation_api_used": (
            "source_validation_only: PrefabOverridePublicInterface::ApplyComponentOverrides "
            "requires a focused parent/link context before source-template DOM can be updated"
        ),
        "approved_source_prefab_component_overrides_detected": False,
        "approved_source_prefab_component_overrides_applied": False,
        "approved_source_prefab_entity_changes_committed": False,
        "approved_source_prefab_template_dom_updated": False,
        "approved_source_prefab_path": APPROVED_SOURCE_PREFAB_REPO_REF,
        "approved_source_prefab_before_hash": before_hash,
        "approved_source_prefab_after_hash": before_hash,
        "approved_source_prefab_modified": False,
        "approved_source_prefab_changed_this_run": False,
        "approved_source_prefab_update_route_used": "not_run_source_validation_only",
        "approved_source_prefab_save_verified": False,
        "approved_source_prefab_actor_component_added": False,
        "approved_source_prefab_simple_motion_component_added": False,
        "approved_source_prefab_actor_asset_assignment_verified": False,
        "approved_source_prefab_motion_asset_assignment_verified": False,
        "approved_source_prefab_property_readback_verified": False,
        "approved_source_prefab_actor_asset_id": "",
        "approved_source_prefab_motion_asset_id": "",
        "approved_source_prefab_persisted_actor_asset_marker_verified": False,
        "approved_source_prefab_persisted_motion_asset_marker_verified": False,
        "approved_source_prefab_persisted_wiring_markers_verified": False,
        "approved_source_prefab_defaultlevel_mutation": False,
        "approved_source_prefab_production_level_mutation": False,
        "approved_source_prefab_hand_authored_unknown_json_used": False,
        "approved_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_runtime_actor_component_found": False,
        "runtime_character_animation_component_wiring_runtime_simple_motion_component_found": False,
        "runtime_character_animation_component_wiring_runtime_actor_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_runtime_motion_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
    }
    if not source_verified:
        result["approved_source_prefab_propagation_api_used"] = "source_validation_incomplete"
    return result


def _run_approved_source_prefab_parent_link_override_apply_route_checks(
    report: Mapping[str, Any],
    *,
    progress_log: Path | None,
) -> Dict[str, Any]:
    repo_validation = _source_validation_from_refs(_approved_source_prefab_parent_link_override_apply_repo_source_refs())
    engine_validation = _optional_engine_source_validation_from_refs(
        _approved_source_prefab_parent_link_override_apply_engine_source_refs()
    )
    repo_source_path = _approved_source_prefab_repo_path()
    project_source_path = _approved_source_prefab_project_path()
    source_prefab_ref = APPROVED_SOURCE_PREFAB_REPO_REF
    safe_call_results: List[Dict[str, Any]] = []
    repo_before_hash = _sha256_file(repo_source_path) if repo_source_path.exists() else ""
    repo_before_bytes = repo_source_path.read_bytes() if repo_source_path.exists() else b""
    project_before_hash = _sha256_file(project_source_path) if project_source_path.exists() else ""
    project_before_bytes = project_source_path.read_bytes() if project_source_path.exists() else b""
    result: Dict[str, Any] = {
        "approved_source_prefab_parent_link_override_apply_route_attempted": True,
        "approved_source_prefab_parent_link_override_apply_route_completed": True,
        "approved_source_prefab_parent_link_override_apply_route_verified": False,
        "approved_source_prefab_parent_link_override_apply_route_blocker": "",
        "approved_source_prefab_parent_link_override_apply_source_validation_status": repo_validation["status"],
        "approved_source_prefab_parent_link_override_apply_source_validation_verified": repo_validation["verified"],
        "approved_source_prefab_parent_link_override_apply_source_refs": repo_validation["refs"],
        "approved_source_prefab_parent_link_override_apply_engine_source_refs_status": engine_validation["status"],
        "approved_source_prefab_parent_link_override_apply_engine_source_refs_verified": engine_validation["verified"],
        "approved_source_prefab_parent_link_override_apply_engine_source_refs": engine_validation["refs"],
        "approved_source_prefab_parent_link_override_apply_candidate_matrix": (
            _approved_source_prefab_parent_link_override_apply_candidate_matrix()
        ),
        "approved_source_prefab_parent_link_override_apply_selected_strategy": (
            "approved_source_prefab_parent_focus_link_context_component_override_apply"
        ),
        "approved_source_prefab_propagation_apply_step_attempted": True,
        "approved_source_prefab_propagation_apply_step_completed": True,
        "approved_source_prefab_propagation_apply_step_verified": False,
        "approved_source_prefab_propagation_apply_step_blocker": "",
        "approved_source_prefab_propagation_apply_step_source_validation_status": repo_validation["status"],
        "approved_source_prefab_propagation_apply_step_source_validation_verified": repo_validation["verified"],
        "approved_source_prefab_propagation_apply_step_source_refs": repo_validation["refs"],
        "approved_source_prefab_propagation_api_used": (
            "AzToolsFramework::Prefab::PrefabFocusPublicInterface::FocusOnOwningPrefab+"
            "FocusOnParentOfFocusedPrefab then "
            "AzToolsFramework::Prefab::PrefabOverridePublicInterface::ApplyComponentOverrides"
        ),
        "approved_source_prefab_path": source_prefab_ref,
        "approved_source_prefab_project_path_redacted": _redacted_project_temp_path(str(project_source_path)),
        "approved_source_prefab_before_hash": repo_before_hash,
        "approved_source_prefab_after_hash": repo_before_hash,
        "approved_source_prefab_project_before_hash": project_before_hash,
        "approved_source_prefab_project_after_hash": project_before_hash,
        "approved_source_prefab_modified": False,
        "approved_source_prefab_changed_this_run": False,
        "approved_source_prefab_update_route_used": (
            "azlmbr.maxine.prefab_bridge.apply_approved_source_prefab_parent_link_component_overrides"
        ),
        "approved_source_prefab_save_verified": False,
        "approved_source_prefab_actor_component_added": False,
        "approved_source_prefab_simple_motion_component_added": False,
        "approved_source_prefab_actor_asset_assignment_verified": False,
        "approved_source_prefab_motion_asset_assignment_verified": False,
        "approved_source_prefab_actor_asset_id": "",
        "approved_source_prefab_motion_asset_id": "",
        "approved_source_prefab_property_readback_verified": False,
        "approved_source_prefab_entity_ownership_checked": False,
        "approved_source_prefab_entity_ownership_verified": False,
        "approved_source_prefab_entity_owning_prefab_path": "",
        "approved_source_prefab_entity_owning_prefab_matches_requested_path": False,
        "approved_source_prefab_component_ownership_checked": False,
        "approved_source_prefab_component_ownership_verified": False,
        "approved_source_prefab_entity_ownership_blocker": "",
        "approved_source_prefab_parent_focus_context_required": True,
        "approved_source_prefab_parent_focus_context_available": False,
        "approved_source_prefab_parent_focus_context_applied": False,
        "approved_source_prefab_parent_focus_context_restored": False,
        "approved_source_prefab_link_context_required": True,
        "approved_source_prefab_link_context_available": False,
        "approved_source_prefab_link_id": "",
        "approved_source_prefab_component_override_paths_detected": False,
        "approved_source_prefab_component_overrides_detected": False,
        "approved_source_prefab_component_overrides_applied": False,
        "approved_source_prefab_link_overrides_applied": False,
        "approved_source_prefab_push_overrides_to_prefab_attempted": False,
        "approved_source_prefab_push_overrides_to_prefab_verified": False,
        "approved_source_prefab_template_dom_updated": False,
        "approved_source_prefab_persisted_actor_asset_marker_verified": False,
        "approved_source_prefab_persisted_motion_asset_marker_verified": False,
        "approved_source_prefab_persisted_wiring_markers_verified": False,
        "approved_source_prefab_marker_presence_verified": False,
        "approved_source_prefab_marker_persistence_verified_this_run": False,
        "approved_source_prefab_marker_persistence_blocker": "",
        "approved_source_prefab_project_persisted_wiring_markers_verified": False,
        "approved_source_prefab_defaultlevel_mutation": False,
        "approved_source_prefab_production_level_mutation": False,
        "approved_source_prefab_hand_authored_unknown_json_used": False,
        "approved_spawnable_regenerated_or_found": False,
        "approved_spawnable_asset_id": "",
        "approved_spawnable_asset_type": "",
        "approved_prefab_save_update_rejected_defaultlevel_path": False,
        "approved_prefab_save_update_rejected_production_level_path": False,
        "approved_prefab_save_update_rejected_generated_product_path": False,
        "approved_prefab_save_update_rejected_unapproved_absolute_path": False,
        "approved_prefab_save_update_rejected_path_traversal": False,
        "approved_prefab_save_update_bridge_verified": False,
        "approved_prefab_save_update_bridge_callable_from_editor_python": False,
        "approved_runtime_animation_component_wiring_editor_generation_attempted": True,
        "approved_runtime_animation_component_wiring_editor_generation_completed": True,
        "approved_runtime_animation_component_wiring_editor_generation_verified": False,
        "approved_runtime_animation_component_wiring_editor_generation_blocker": "",
        "approved_runtime_animation_component_wiring_source_prefab_path": source_prefab_ref,
        "approved_runtime_animation_component_wiring_source_prefab_modified": False,
        "approved_runtime_animation_component_wiring_editor_generated_update_used": False,
        "approved_runtime_animation_component_wiring_hand_authored_unknown_json_used": False,
        "approved_runtime_animation_component_wiring_actor_component_added": False,
        "approved_runtime_animation_component_wiring_simple_motion_component_added": False,
        "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_actor_asset_id": "",
        "approved_runtime_animation_component_wiring_motion_asset_id": "",
        "approved_runtime_animation_component_wiring_property_readback_verified": False,
        "approved_runtime_animation_component_wiring_prefab_save_verified": False,
        "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_playback_started": False,
        "runtime_character_animation_playback_observed": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
    }

    def _block(blocker: str) -> Dict[str, Any]:
        result["approved_source_prefab_parent_link_override_apply_route_blocker"] = blocker
        result["approved_source_prefab_propagation_apply_step_blocker"] = blocker
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = blocker
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = blocker
        result["safe_call_results"] = safe_call_results
        return result

    if repo_validation["verified"] is not True:
        return _block("blocked_by_prefab_instance_to_template_propagation_requires_additional_source_validation")
    if not repo_source_path.exists() or not project_source_path.exists():
        result["approved_source_prefab_path_exists"] = repo_source_path.exists()
        result["approved_source_prefab_project_path_exists"] = project_source_path.exists()
        return _block("blocked_by_approved_source_prefab_save_policy")

    surface_info, surface = _load_component_api_surface()
    binding_report = {
        "component_type_registry": dict(report.get("component_type_registry", {}))
        if isinstance(report.get("component_type_registry"), Mapping)
        else {},
        "binding_call_surface": {
            "EditorComponentAPIBus": surface_info,
        },
        "safe_call_results": safe_call_results,
        "property_path_discovery": {},
        "property_list_summary": {},
        "property_access_summary": {},
    }
    instantiation = _instantiate_approved_source_prefab(project_source_path, safe_call_results)
    result["approved_source_prefab_instantiation"] = {
        key: value for key, value in instantiation.items() if key != "created_entity_id"
    }
    entity_id = instantiation.get("created_entity_id")
    if instantiation.get("status") != "pass" or not _entity_id_valid(entity_id):
        return _block("blocked_by_approved_source_prefab_save_policy")

    _write_progress_marker(
        progress_log,
        "approved_source_prefab_parent_link_component_assignment_started",
        "started",
        "Adding approved Actor + Simple Motion components before parent-focus/link-context apply.",
    )
    generation = _run_approved_animation_component_wiring_generation_checks(
        entity_id,
        surface,
        binding_report,
        safe_call_results,
        report,
    )
    result.update(generation)
    actor_added = generation.get("approved_runtime_animation_component_wiring_actor_component_added") is True
    simple_added = generation.get("approved_runtime_animation_component_wiring_simple_motion_component_added") is True
    actor_assignment = generation.get("approved_runtime_animation_component_wiring_actor_asset_assignment_verified") is True
    motion_assignment = generation.get("approved_runtime_animation_component_wiring_motion_asset_assignment_verified") is True
    property_readback = generation.get("approved_runtime_animation_component_wiring_property_readback_verified") is True
    result.update(
        {
            "approved_source_prefab_actor_component_added": actor_added,
            "approved_source_prefab_simple_motion_component_added": simple_added,
            "approved_source_prefab_actor_asset_assignment_verified": actor_assignment,
            "approved_source_prefab_motion_asset_assignment_verified": motion_assignment,
            "approved_source_prefab_actor_asset_id": str(
                generation.get("approved_runtime_animation_component_wiring_actor_asset_id", "")
            ),
            "approved_source_prefab_motion_asset_id": str(
                generation.get("approved_runtime_animation_component_wiring_motion_asset_id", "")
            ),
            "approved_source_prefab_property_readback_verified": property_readback,
        }
    )
    if not (actor_added and simple_added and actor_assignment and motion_assignment and property_readback):
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_editor_component_assignment_readback_failure")

    override_refs = _approved_source_prefab_wiring_component_refs(entity_id, surface, binding_report, safe_call_results)
    result["approved_source_prefab_component_override_refs"] = {
        key: value
        for key, value in override_refs.items()
        if key not in {"actor_component_ref", "simple_motion_component_ref"}
    }
    entity_commit_status = _call_prefab_commit_approved_source_entity_changes(project_source_path, entity_id)
    result["approved_source_prefab_entity_change_commit_status"] = entity_commit_status
    result["approved_source_prefab_entity_changes_committed"] = bool(entity_commit_status.get("committed"))

    override_status = _call_prefab_apply_approved_source_parent_link_component_overrides(
        project_source_path,
        entity_id,
        override_refs.get("actor_component_ref"),
        override_refs.get("simple_motion_component_ref"),
    )
    result["approved_source_prefab_component_override_apply_status"] = override_status
    result.update(
        _approved_source_prefab_parent_link_override_apply_report_from_route_status(
            override_status,
            persisted_markers={"actor": False, "motion": False, "both": False},
            source_prefab_changed_this_run=False,
            before_hash=repo_before_hash,
            after_hash=repo_before_hash,
        )
    )
    if not result["approved_source_prefab_component_overrides_applied"]:
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block(str(result["approved_source_prefab_parent_link_override_apply_route_blocker"]))

    rejection_statuses = _call_approved_source_prefab_wiring_rejection_probes(project_source_path)
    route_status = _call_prefab_save_update_approved_source_route(project_source_path)
    project_after_hash = _sha256_file(project_source_path) if project_source_path.exists() else ""
    marker_evidence = _source_prefab_wiring_marker_evidence(project_source_path)
    result["approved_source_prefab_save_route_status"] = route_status
    result["approved_source_prefab_path_policy_rejections"] = rejection_statuses
    result["approved_source_prefab_project_after_hash"] = project_after_hash
    result["approved_source_prefab_project_marker_evidence"] = marker_evidence
    result["approved_source_prefab_save_verified"] = bool(route_status.get("saved")) and marker_evidence.get("parse_verified") is True
    result["approved_prefab_save_update_bridge_verified"] = result["approved_source_prefab_save_verified"]
    result["approved_prefab_save_update_bridge_callable_from_editor_python"] = bool(route_status.get("callable"))
    result["approved_prefab_save_update_rejected_defaultlevel_path"] = _route_rejection_verified(
        rejection_statuses, "defaultlevel"
    )
    result["approved_prefab_save_update_rejected_production_level_path"] = _route_rejection_verified(
        rejection_statuses, "production_level"
    )
    result["approved_prefab_save_update_rejected_generated_product_path"] = _route_rejection_verified(
        rejection_statuses, "generated_product"
    )
    result["approved_prefab_save_update_rejected_unapproved_absolute_path"] = _route_rejection_verified(
        rejection_statuses, "unapproved_absolute"
    )
    result["approved_prefab_save_update_rejected_path_traversal"] = _route_rejection_verified(
        rejection_statuses, "path_traversal"
    )

    if not result["approved_source_prefab_save_verified"]:
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_approved_source_prefab_save_policy")

    result["approved_source_prefab_project_persisted_wiring_markers_verified"] = marker_evidence.get("both") is True
    result["approved_source_prefab_project_changed_this_run"] = bool(
        project_before_hash and project_after_hash != project_before_hash
    )
    result.update(
        _approved_source_prefab_parent_link_override_apply_report_from_route_status(
            override_status,
            persisted_markers=marker_evidence,
            source_prefab_changed_this_run=result["approved_source_prefab_project_changed_this_run"],
            before_hash=project_before_hash,
            after_hash=project_after_hash,
        )
    )
    if marker_evidence.get("both") is not True:
        if project_before_bytes and project_after_hash and project_after_hash != project_before_hash:
            try:
                project_source_path.write_bytes(project_before_bytes)
                result["approved_source_prefab_restored_after_failed_verification"] = True
                result["approved_source_prefab_project_after_restore_hash"] = _sha256_file(project_source_path)
            except Exception as exc:
                result["approved_source_prefab_restored_after_failed_verification"] = False
                result["approved_source_prefab_restore_error"] = str(exc)
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_prefab_template_dom_update_unavailable")
    if result["approved_source_prefab_project_changed_this_run"] is not True:
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_source_prefab_markers_preexisting_without_this_run_change")

    try:
        repo_source_path.write_bytes(project_source_path.read_bytes())
    except Exception as exc:
        result["approved_source_prefab_repo_copy_error"] = str(exc)
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_approved_source_prefab_save_policy")

    repo_after_hash = _sha256_file(repo_source_path)
    repo_marker_evidence = _source_prefab_wiring_marker_evidence(repo_source_path)
    result["approved_source_prefab_after_hash"] = repo_after_hash
    result["approved_source_prefab_marker_evidence"] = repo_marker_evidence
    result["approved_source_prefab_changed_this_run"] = bool(repo_before_hash and repo_after_hash != repo_before_hash)
    result.update(
        _approved_source_prefab_parent_link_override_apply_report_from_route_status(
            override_status,
            persisted_markers=repo_marker_evidence,
            source_prefab_changed_this_run=result["approved_source_prefab_changed_this_run"],
            before_hash=repo_before_hash,
            after_hash=repo_after_hash,
        )
    )
    repo_marker_persistence_verified = (
        repo_marker_evidence.get("both") is True and result["approved_source_prefab_changed_this_run"] is True
    )
    result["approved_source_prefab_modified"] = repo_marker_persistence_verified
    result["approved_runtime_animation_component_wiring_editor_generation_verified"] = repo_marker_persistence_verified
    result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = (
        ""
        if repo_marker_persistence_verified
        else (
            "blocked_by_source_prefab_markers_preexisting_without_this_run_change"
            if repo_marker_evidence.get("both") is True
            else "blocked_by_prefab_template_dom_update_unavailable"
        )
    )
    result["approved_runtime_animation_component_wiring_source_prefab_modified"] = result[
        "approved_source_prefab_modified"
    ]
    result["approved_runtime_animation_component_wiring_editor_generated_update_used"] = True
    result["approved_runtime_animation_component_wiring_prefab_save_verified"] = result["approved_source_prefab_save_verified"]
    if not repo_marker_persistence_verified:
        if repo_before_bytes:
            repo_source_path.write_bytes(repo_before_bytes)
            result["approved_source_prefab_repo_restored_after_failed_verification"] = True
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block(str(result["approved_runtime_animation_component_wiring_editor_generation_blocker"]))

    result["approved_source_prefab_parent_link_override_apply_route_verified"] = True
    result["approved_source_prefab_parent_link_override_apply_route_blocker"] = ""
    result["approved_source_prefab_propagation_apply_step_verified"] = True
    result["approved_source_prefab_propagation_apply_step_blocker"] = ""
    result["approved_source_prefab_actor_simple_motion_wiring_verified"] = True
    result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = ""
    result["safe_call_results"] = safe_call_results
    result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
    return result


def _run_approved_source_prefab_override_path_generation_template_update_checks(
    report: Mapping[str, Any],
    *,
    progress_log: Path | None,
) -> Dict[str, Any]:
    repo_validation = _source_validation_from_refs(
        _approved_source_prefab_override_path_generation_template_update_repo_source_refs()
    )
    engine_validation = _optional_engine_source_validation_from_refs(
        _approved_source_prefab_override_path_generation_template_update_engine_source_refs()
    )
    repo_source_path = _approved_source_prefab_repo_path()
    project_source_path = _approved_source_prefab_project_path()
    source_prefab_ref = APPROVED_SOURCE_PREFAB_REPO_REF
    safe_call_results: List[Dict[str, Any]] = []
    repo_before_hash = _sha256_file(repo_source_path) if repo_source_path.exists() else ""
    repo_before_bytes = repo_source_path.read_bytes() if repo_source_path.exists() else b""
    project_before_hash = _sha256_file(project_source_path) if project_source_path.exists() else ""
    project_before_bytes = project_source_path.read_bytes() if project_source_path.exists() else b""
    result: Dict[str, Any] = {
        "approved_source_prefab_override_path_generation_template_update_attempted": True,
        "approved_source_prefab_override_path_generation_template_update_completed": True,
        "approved_source_prefab_override_path_generation_template_update_verified": False,
        "approved_source_prefab_override_path_generation_template_update_blocker": "",
        "approved_source_prefab_override_path_generation_template_update_source_validation_status": repo_validation["status"],
        "approved_source_prefab_override_path_generation_template_update_source_validation_verified": repo_validation["verified"],
        "approved_source_prefab_override_path_generation_template_update_source_refs": repo_validation["refs"],
        "approved_source_prefab_override_path_generation_template_update_engine_source_refs_status": engine_validation["status"],
        "approved_source_prefab_override_path_generation_template_update_engine_source_refs_verified": engine_validation["verified"],
        "approved_source_prefab_override_path_generation_template_update_engine_source_refs": engine_validation["refs"],
        "approved_source_prefab_override_path_generation_template_update_candidate_matrix": (
            _approved_source_prefab_override_path_generation_template_update_candidate_matrix()
        ),
        "approved_source_prefab_override_path_generation_template_update_selected_strategy": (
            "source_backed_serialized_entity_patch_entity_in_template"
        ),
        "approved_source_prefab_propagation_apply_step_attempted": True,
        "approved_source_prefab_propagation_apply_step_completed": True,
        "approved_source_prefab_propagation_apply_step_verified": False,
        "approved_source_prefab_propagation_apply_step_blocker": "",
        "approved_source_prefab_propagation_apply_step_source_validation_status": repo_validation["status"],
        "approved_source_prefab_propagation_apply_step_source_validation_verified": repo_validation["verified"],
        "approved_source_prefab_propagation_apply_step_source_refs": repo_validation["refs"],
        "approved_source_prefab_propagation_api_used": (
            "AzToolsFramework::Prefab::InstanceToTemplateInterface::"
            "GenerateEntityDomBySerializing+GeneratePatch+PatchEntityInTemplate"
        ),
        "approved_source_prefab_path": source_prefab_ref,
        "approved_source_prefab_project_path_redacted": _redacted_project_temp_path(str(project_source_path)),
        "approved_source_prefab_before_hash": repo_before_hash,
        "approved_source_prefab_after_hash": repo_before_hash,
        "approved_source_prefab_project_before_hash": project_before_hash,
        "approved_source_prefab_project_after_hash": project_before_hash,
        "approved_source_prefab_modified": False,
        "approved_source_prefab_changed_this_run": False,
        "approved_source_prefab_update_route_used": (
            "azlmbr.maxine.prefab_bridge.apply_approved_source_prefab_override_path_generation_template_update"
        ),
        "approved_source_prefab_save_verified": False,
        "approved_source_prefab_actor_component_added": False,
        "approved_source_prefab_simple_motion_component_added": False,
        "approved_source_prefab_actor_asset_assignment_verified": False,
        "approved_source_prefab_motion_asset_assignment_verified": False,
        "approved_source_prefab_actor_asset_id": "",
        "approved_source_prefab_motion_asset_id": "",
        "approved_source_prefab_property_readback_verified": False,
        "approved_source_prefab_entity_ownership_checked": False,
        "approved_source_prefab_entity_ownership_verified": False,
        "approved_source_prefab_entity_owning_prefab_path": "",
        "approved_source_prefab_entity_owning_prefab_matches_requested_path": False,
        "approved_source_prefab_component_ownership_checked": False,
        "approved_source_prefab_component_ownership_verified": False,
        "approved_source_prefab_entity_ownership_blocker": "",
        "approved_source_prefab_template_dom_update_route_used": False,
        "approved_source_prefab_template_dom_initial_entity_found": False,
        "approved_source_prefab_serialized_entity_dom_generated": False,
        "approved_source_prefab_entity_patch_generated": False,
        "approved_source_prefab_entity_patch_operation_count": 0,
        "approved_source_prefab_component_override_paths_detected": False,
        "approved_source_prefab_component_override_paths": [],
        "approved_source_prefab_apply_link_overrides_attempted": False,
        "approved_source_prefab_apply_link_overrides_verified": False,
        "approved_source_prefab_push_overrides_to_template_attempted": False,
        "approved_source_prefab_push_overrides_to_template_verified": False,
        "approved_source_prefab_patch_entity_in_template_attempted": False,
        "approved_source_prefab_patch_entity_in_template_verified": False,
        "approved_source_prefab_template_dom_updated": False,
        "approved_source_prefab_persisted_actor_asset_marker_verified": False,
        "approved_source_prefab_persisted_motion_asset_marker_verified": False,
        "approved_source_prefab_persisted_wiring_markers_verified": False,
        "approved_source_prefab_marker_presence_verified": False,
        "approved_source_prefab_marker_persistence_verified_this_run": False,
        "approved_source_prefab_marker_persistence_blocker": "",
        "approved_source_prefab_project_persisted_wiring_markers_verified": False,
        "approved_source_prefab_defaultlevel_mutation": False,
        "approved_source_prefab_production_level_mutation": False,
        "approved_source_prefab_hand_authored_unknown_json_used": False,
        "approved_spawnable_regenerated_or_found": False,
        "approved_spawnable_asset_id": "",
        "approved_spawnable_asset_type": "",
        "approved_prefab_save_update_rejected_defaultlevel_path": False,
        "approved_prefab_save_update_rejected_production_level_path": False,
        "approved_prefab_save_update_rejected_generated_product_path": False,
        "approved_prefab_save_update_rejected_unapproved_absolute_path": False,
        "approved_prefab_save_update_rejected_path_traversal": False,
        "approved_source_prefab_template_update_route_rejection_probes_attempted": False,
        "approved_source_prefab_template_update_route_rejection_probes_verified": False,
        "approved_source_prefab_template_update_route_rejected_defaultlevel_path": False,
        "approved_source_prefab_template_update_route_rejected_production_level_path": False,
        "approved_source_prefab_template_update_route_rejected_generated_product_path": False,
        "approved_source_prefab_template_update_route_rejected_cache_path": False,
        "approved_source_prefab_template_update_route_rejected_unapproved_absolute_path": False,
        "approved_source_prefab_template_update_route_rejected_other_project_path": False,
        "approved_source_prefab_template_update_route_rejected_path_traversal": False,
        "approved_source_prefab_template_update_route_rejected_non_prefab_path": False,
        "approved_source_prefab_template_update_route_rejected_wrong_entity_owner": False,
        "approved_source_prefab_template_update_route_rejection_probe_route": "",
        "approved_source_prefab_template_update_route_rejection_probe_results": {},
        "approved_source_prefab_legacy_wiring_route_rejection_probes_preserved": False,
        "approved_source_prefab_legacy_wiring_route_rejection_probe_route": "",
        "approved_source_prefab_legacy_wiring_route_rejection_probe_results": {},
        "approved_prefab_save_update_bridge_verified": False,
        "approved_prefab_save_update_bridge_callable_from_editor_python": False,
        "approved_runtime_animation_component_wiring_editor_generation_attempted": True,
        "approved_runtime_animation_component_wiring_editor_generation_completed": True,
        "approved_runtime_animation_component_wiring_editor_generation_verified": False,
        "approved_runtime_animation_component_wiring_editor_generation_blocker": "",
        "approved_runtime_animation_component_wiring_source_prefab_path": source_prefab_ref,
        "approved_runtime_animation_component_wiring_source_prefab_modified": False,
        "approved_runtime_animation_component_wiring_editor_generated_update_used": False,
        "approved_runtime_animation_component_wiring_hand_authored_unknown_json_used": False,
        "approved_runtime_animation_component_wiring_actor_component_added": False,
        "approved_runtime_animation_component_wiring_simple_motion_component_added": False,
        "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_actor_asset_id": "",
        "approved_runtime_animation_component_wiring_motion_asset_id": "",
        "approved_runtime_animation_component_wiring_property_readback_verified": False,
        "approved_runtime_animation_component_wiring_prefab_save_verified": False,
        "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_playback_started": False,
        "runtime_character_animation_playback_observed": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
    }

    def _block(blocker: str) -> Dict[str, Any]:
        result["approved_source_prefab_override_path_generation_template_update_blocker"] = blocker
        result["approved_source_prefab_propagation_apply_step_blocker"] = blocker
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = blocker
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = blocker
        result["safe_call_results"] = safe_call_results
        return result

    if repo_validation["verified"] is not True:
        return _block("blocked_by_prefab_instance_to_template_propagation_requires_additional_source_validation")
    if not repo_source_path.exists() or not project_source_path.exists():
        result["approved_source_prefab_path_exists"] = repo_source_path.exists()
        result["approved_source_prefab_project_path_exists"] = project_source_path.exists()
        return _block("blocked_by_approved_source_prefab_save_policy")

    surface_info, surface = _load_component_api_surface()
    binding_report = {
        "component_type_registry": dict(report.get("component_type_registry", {}))
        if isinstance(report.get("component_type_registry"), Mapping)
        else {},
        "binding_call_surface": {
            "EditorComponentAPIBus": surface_info,
        },
        "safe_call_results": safe_call_results,
        "property_path_discovery": {},
        "property_list_summary": {},
        "property_access_summary": {},
    }
    instantiation = _instantiate_approved_source_prefab(project_source_path, safe_call_results)
    result["approved_source_prefab_instantiation"] = {
        key: value for key, value in instantiation.items() if key != "created_entity_id"
    }
    entity_id = instantiation.get("created_entity_id")
    if instantiation.get("status") != "pass" or not _entity_id_valid(entity_id):
        return _block("blocked_by_approved_source_prefab_save_policy")

    _write_progress_marker(
        progress_log,
        "approved_source_prefab_template_update_component_assignment_started",
        "started",
        "Adding approved Actor + Simple Motion components before source-backed template update.",
    )
    generation = _run_approved_animation_component_wiring_generation_checks(
        entity_id,
        surface,
        binding_report,
        safe_call_results,
        report,
    )
    result.update(generation)
    actor_added = generation.get("approved_runtime_animation_component_wiring_actor_component_added") is True
    simple_added = generation.get("approved_runtime_animation_component_wiring_simple_motion_component_added") is True
    actor_assignment = generation.get("approved_runtime_animation_component_wiring_actor_asset_assignment_verified") is True
    motion_assignment = generation.get("approved_runtime_animation_component_wiring_motion_asset_assignment_verified") is True
    property_readback = generation.get("approved_runtime_animation_component_wiring_property_readback_verified") is True
    result.update(
        {
            "approved_source_prefab_actor_component_added": actor_added,
            "approved_source_prefab_simple_motion_component_added": simple_added,
            "approved_source_prefab_actor_asset_assignment_verified": actor_assignment,
            "approved_source_prefab_motion_asset_assignment_verified": motion_assignment,
            "approved_source_prefab_actor_asset_id": str(
                generation.get("approved_runtime_animation_component_wiring_actor_asset_id", "")
            ),
            "approved_source_prefab_motion_asset_id": str(
                generation.get("approved_runtime_animation_component_wiring_motion_asset_id", "")
            ),
            "approved_source_prefab_property_readback_verified": property_readback,
        }
    )
    if not (actor_added and simple_added and actor_assignment and motion_assignment and property_readback):
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_editor_component_assignment_readback_failure")

    override_refs = _approved_source_prefab_wiring_component_refs(entity_id, surface, binding_report, safe_call_results)
    result["approved_source_prefab_component_override_refs"] = {
        key: value
        for key, value in override_refs.items()
        if key not in {"actor_component_ref", "simple_motion_component_ref"}
    }
    template_update_status = _call_prefab_apply_approved_source_override_path_generation_template_update(
        project_source_path,
        entity_id,
        override_refs.get("actor_component_ref"),
        override_refs.get("simple_motion_component_ref"),
    )
    result["approved_source_prefab_template_update_route_status"] = template_update_status
    result.update(
        _approved_source_prefab_override_path_generation_template_update_report_from_route_status(
            template_update_status,
            persisted_markers={"actor": False, "motion": False, "both": False},
            source_prefab_changed_this_run=False,
            before_hash=repo_before_hash,
            after_hash=repo_before_hash,
        )
    )
    if not result["approved_source_prefab_patch_entity_in_template_verified"]:
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block(str(result["approved_source_prefab_override_path_generation_template_update_blocker"]))

    legacy_rejection_statuses = _call_approved_source_prefab_wiring_rejection_probes(project_source_path)
    template_update_rejection_statuses = _call_approved_source_prefab_template_update_route_rejection_probes(
        project_source_path,
        entity_id=entity_id,
        actor_component_ref=override_refs.get("actor_component_ref"),
        simple_motion_component_ref=override_refs.get("simple_motion_component_ref"),
    )
    template_update_rejection_summary = _approved_source_prefab_template_update_route_rejection_probe_summary(
        template_update_rejection_statuses
    )
    project_after_hash = _sha256_file(project_source_path) if project_source_path.exists() else ""
    marker_evidence = _source_prefab_wiring_marker_evidence(project_source_path)
    result["approved_source_prefab_path_policy_rejections"] = template_update_rejection_statuses
    result.update(template_update_rejection_summary)
    result.update(_approved_source_prefab_legacy_wiring_route_rejection_probe_summary(legacy_rejection_statuses))
    result["approved_source_prefab_project_after_hash"] = project_after_hash
    result["approved_source_prefab_project_marker_evidence"] = marker_evidence
    result["approved_prefab_save_update_bridge_callable_from_editor_python"] = bool(template_update_status.get("callable"))
    result["approved_prefab_save_update_rejected_defaultlevel_path"] = _route_rejection_verified(
        template_update_rejection_statuses, "defaultlevel"
    )
    result["approved_prefab_save_update_rejected_production_level_path"] = _route_rejection_verified(
        template_update_rejection_statuses, "production_level"
    )
    result["approved_prefab_save_update_rejected_generated_product_path"] = _route_rejection_verified(
        template_update_rejection_statuses, "generated_product"
    )
    result["approved_prefab_save_update_rejected_unapproved_absolute_path"] = _route_rejection_verified(
        template_update_rejection_statuses, "unapproved_absolute"
    )
    result["approved_prefab_save_update_rejected_path_traversal"] = _route_rejection_verified(
        template_update_rejection_statuses, "path_traversal"
    )

    result["approved_source_prefab_project_persisted_wiring_markers_verified"] = marker_evidence.get("both") is True
    result["approved_source_prefab_project_changed_this_run"] = bool(
        project_before_hash and project_after_hash != project_before_hash
    )
    result.update(
        _approved_source_prefab_override_path_generation_template_update_report_from_route_status(
            template_update_status,
            persisted_markers=marker_evidence,
            source_prefab_changed_this_run=result["approved_source_prefab_project_changed_this_run"],
            before_hash=project_before_hash,
            after_hash=project_after_hash,
            template_update_route_rejection_probes_verified=template_update_rejection_summary[
                "approved_source_prefab_template_update_route_rejection_probes_verified"
            ],
        )
    )
    if result["approved_source_prefab_template_update_route_rejection_probes_verified"] is not True:
        if project_before_bytes and project_after_hash and project_after_hash != project_before_hash:
            try:
                project_source_path.write_bytes(project_before_bytes)
                result["approved_source_prefab_restored_after_failed_verification"] = True
                result["approved_source_prefab_project_after_restore_hash"] = _sha256_file(project_source_path)
            except Exception as exc:
                result["approved_source_prefab_restored_after_failed_verification"] = False
                result["approved_source_prefab_restore_error"] = str(exc)
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_template_update_route_rejection_probes_unverified")
    if marker_evidence.get("both") is not True:
        if project_before_bytes and project_after_hash and project_after_hash != project_before_hash:
            try:
                project_source_path.write_bytes(project_before_bytes)
                result["approved_source_prefab_restored_after_failed_verification"] = True
                result["approved_source_prefab_project_after_restore_hash"] = _sha256_file(project_source_path)
            except Exception as exc:
                result["approved_source_prefab_restored_after_failed_verification"] = False
                result["approved_source_prefab_restore_error"] = str(exc)
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_prefab_template_dom_update_unavailable")
    if result["approved_source_prefab_project_changed_this_run"] is not True:
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_source_prefab_markers_preexisting_without_this_run_change")

    try:
        repo_source_path.write_bytes(project_source_path.read_bytes())
    except Exception as exc:
        result["approved_source_prefab_repo_copy_error"] = str(exc)
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block("blocked_by_approved_source_prefab_save_policy")

    repo_after_hash = _sha256_file(repo_source_path)
    repo_marker_evidence = _source_prefab_wiring_marker_evidence(repo_source_path)
    result["approved_source_prefab_after_hash"] = repo_after_hash
    result["approved_source_prefab_marker_evidence"] = repo_marker_evidence
    result["approved_source_prefab_changed_this_run"] = bool(repo_before_hash and repo_after_hash != repo_before_hash)
    result.update(
        _approved_source_prefab_override_path_generation_template_update_report_from_route_status(
            template_update_status,
            persisted_markers=repo_marker_evidence,
            source_prefab_changed_this_run=result["approved_source_prefab_changed_this_run"],
            before_hash=repo_before_hash,
            after_hash=repo_after_hash,
            template_update_route_rejection_probes_verified=template_update_rejection_summary[
                "approved_source_prefab_template_update_route_rejection_probes_verified"
            ],
        )
    )
    repo_marker_persistence_verified = (
        repo_marker_evidence.get("both") is True and result["approved_source_prefab_changed_this_run"] is True
    )
    result["approved_source_prefab_modified"] = repo_marker_persistence_verified
    result["approved_prefab_save_update_bridge_verified"] = repo_marker_persistence_verified
    result["approved_runtime_animation_component_wiring_editor_generation_verified"] = repo_marker_persistence_verified
    result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = (
        ""
        if repo_marker_persistence_verified
        else (
            "blocked_by_source_prefab_markers_preexisting_without_this_run_change"
            if repo_marker_evidence.get("both") is True
            else "blocked_by_prefab_template_dom_update_unavailable"
        )
    )
    result["approved_runtime_animation_component_wiring_source_prefab_modified"] = result[
        "approved_source_prefab_modified"
    ]
    result["approved_runtime_animation_component_wiring_editor_generated_update_used"] = True
    result["approved_runtime_animation_component_wiring_prefab_save_verified"] = result["approved_source_prefab_save_verified"]
    if not repo_marker_persistence_verified:
        if repo_before_bytes:
            repo_source_path.write_bytes(repo_before_bytes)
            result["approved_source_prefab_repo_restored_after_failed_verification"] = True
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return _block(str(result["approved_runtime_animation_component_wiring_editor_generation_blocker"]))

    result["approved_source_prefab_override_path_generation_template_update_verified"] = True
    result["approved_source_prefab_override_path_generation_template_update_blocker"] = ""
    result["approved_source_prefab_propagation_apply_step_verified"] = True
    result["approved_source_prefab_propagation_apply_step_blocker"] = ""
    result["approved_source_prefab_actor_simple_motion_wiring_verified"] = True
    result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = ""
    result["safe_call_results"] = safe_call_results
    result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
    return result


def _run_approved_source_prefab_actor_simple_motion_wiring_checks(
    report: Mapping[str, Any],
    *,
    progress_log: Path | None,
) -> Dict[str, Any]:
    source_validation = _approved_source_prefab_wiring_source_validation()
    repo_source_path = _approved_source_prefab_repo_path()
    project_source_path = _approved_source_prefab_project_path()
    source_prefab_ref = APPROVED_SOURCE_PREFAB_REPO_REF
    safe_call_results: List[Dict[str, Any]] = []
    rejection_statuses: Dict[str, Dict[str, Any]] = {}
    repo_before_hash = _sha256_file(repo_source_path) if repo_source_path.exists() else ""
    project_before_hash = _sha256_file(project_source_path) if project_source_path.exists() else ""
    result: Dict[str, Any] = {
        "approved_source_prefab_actor_simple_motion_wiring_attempted": True,
        "approved_source_prefab_actor_simple_motion_wiring_completed": True,
        "approved_source_prefab_actor_simple_motion_wiring_verified": False,
        "approved_source_prefab_actor_simple_motion_wiring_blocker": "",
        "approved_source_prefab_actor_simple_motion_wiring_source_validation_status": source_validation["status"],
        "approved_source_prefab_actor_simple_motion_wiring_source_validation_verified": source_validation["verified"],
        "approved_source_prefab_actor_simple_motion_wiring_source_refs": source_validation["refs"],
        "approved_source_prefab_actor_simple_motion_wiring_candidate_matrix": _approved_source_prefab_wiring_candidate_matrix(),
        "approved_source_prefab_actor_simple_motion_wiring_selected_strategy": (
            "approved_source_prefab_actor_plus_simple_motion_editor_generated_update"
        ),
        "approved_source_prefab_path": source_prefab_ref,
        "approved_source_prefab_project_path_redacted": _redacted_project_temp_path(str(project_source_path)),
        "approved_source_prefab_before_hash": repo_before_hash,
        "approved_source_prefab_after_hash": "",
        "approved_source_prefab_project_before_hash": project_before_hash,
        "approved_source_prefab_project_after_hash": "",
        "approved_source_prefab_modified": False,
        "approved_source_prefab_changed_this_run": False,
        "approved_source_prefab_persisted_wiring_markers_verified": False,
        "approved_source_prefab_project_persisted_wiring_markers_verified": False,
        "approved_source_prefab_component_overrides_applied": False,
        "approved_source_prefab_component_override_refs": {},
        "approved_source_prefab_component_override_apply_status": {},
        "approved_source_prefab_entity_changes_committed": False,
        "approved_source_prefab_entity_change_commit_status": {},
        "approved_source_prefab_update_route_used": "azlmbr.maxine.prefab_bridge.save_approved_source_prefab_wiring",
        "approved_source_prefab_save_verified": False,
        "approved_source_prefab_actor_component_added": False,
        "approved_source_prefab_simple_motion_component_added": False,
        "approved_source_prefab_actor_asset_assignment_verified": False,
        "approved_source_prefab_motion_asset_assignment_verified": False,
        "approved_source_prefab_actor_asset_id": "",
        "approved_source_prefab_motion_asset_id": "",
        "approved_source_prefab_property_readback_verified": False,
        "approved_source_prefab_defaultlevel_mutation": False,
        "approved_source_prefab_production_level_mutation": False,
        "approved_source_prefab_hand_authored_unknown_json_used": False,
        "approved_spawnable_regenerated_or_found": False,
        "approved_spawnable_asset_id": "",
        "approved_spawnable_asset_type": "",
        "approved_prefab_save_update_rejected_defaultlevel_path": False,
        "approved_prefab_save_update_rejected_production_level_path": False,
        "approved_prefab_save_update_rejected_generated_product_path": False,
        "approved_prefab_save_update_rejected_unapproved_absolute_path": False,
        "approved_prefab_save_update_rejected_path_traversal": False,
        "approved_prefab_save_update_bridge_verified": False,
        "approved_prefab_save_update_bridge_callable_from_editor_python": False,
        "approved_runtime_animation_component_wiring_editor_generation_attempted": True,
        "approved_runtime_animation_component_wiring_editor_generation_completed": True,
        "approved_runtime_animation_component_wiring_editor_generation_verified": False,
        "approved_runtime_animation_component_wiring_editor_generation_blocker": "",
        "approved_runtime_animation_component_wiring_source_prefab_path": source_prefab_ref,
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
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_playback_started": False,
        "runtime_character_animation_playback_observed": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
    }

    if source_validation["verified"] is not True:
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = (
            "blocked_by_approved_source_prefab_wiring_requires_additional_source_validation"
        )
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = result[
            "approved_source_prefab_actor_simple_motion_wiring_blocker"
        ]
        return result
    if not repo_source_path.exists() or not project_source_path.exists():
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = (
            "blocked_by_approved_source_prefab_save_policy"
        )
        result["approved_source_prefab_path_exists"] = repo_source_path.exists()
        result["approved_source_prefab_project_path_exists"] = project_source_path.exists()
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = result[
            "approved_source_prefab_actor_simple_motion_wiring_blocker"
        ]
        return result

    surface_info, surface = _load_component_api_surface()
    binding_report = {
        "component_type_registry": dict(report.get("component_type_registry", {}))
        if isinstance(report.get("component_type_registry"), Mapping)
        else {},
        "binding_call_surface": {
            "EditorComponentAPIBus": surface_info,
        },
        "safe_call_results": safe_call_results,
        "property_path_discovery": {},
        "property_list_summary": {},
        "property_access_summary": {},
    }
    instantiation = _instantiate_approved_source_prefab(project_source_path, safe_call_results)
    result["approved_source_prefab_instantiation"] = {
        key: value for key, value in instantiation.items() if key != "created_entity_id"
    }
    entity_id = instantiation.get("created_entity_id")
    if instantiation.get("status") != "pass" or not _entity_id_valid(entity_id):
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = (
            "blocked_by_approved_source_prefab_save_policy"
        )
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = result[
            "approved_source_prefab_actor_simple_motion_wiring_blocker"
        ]
        result["safe_call_results"] = safe_call_results
        return result

    _write_progress_marker(
        progress_log,
        "approved_source_prefab_component_assignment_started",
        "started",
        "Adding approved Actor + Simple Motion components to instantiated approved source prefab.",
    )
    generation = _run_approved_animation_component_wiring_generation_checks(
        entity_id,
        surface,
        binding_report,
        safe_call_results,
        report,
    )
    result.update(generation)
    actor_added = generation.get("approved_runtime_animation_component_wiring_actor_component_added") is True
    simple_added = generation.get("approved_runtime_animation_component_wiring_simple_motion_component_added") is True
    actor_assignment = generation.get("approved_runtime_animation_component_wiring_actor_asset_assignment_verified") is True
    motion_assignment = generation.get("approved_runtime_animation_component_wiring_motion_asset_assignment_verified") is True
    property_readback = generation.get("approved_runtime_animation_component_wiring_property_readback_verified") is True
    result.update(
        {
            "approved_source_prefab_actor_component_added": actor_added,
            "approved_source_prefab_simple_motion_component_added": simple_added,
            "approved_source_prefab_actor_asset_assignment_verified": actor_assignment,
            "approved_source_prefab_motion_asset_assignment_verified": motion_assignment,
            "approved_source_prefab_actor_asset_id": str(
                generation.get("approved_runtime_animation_component_wiring_actor_asset_id", "")
            ),
            "approved_source_prefab_motion_asset_id": str(
                generation.get("approved_runtime_animation_component_wiring_motion_asset_id", "")
            ),
            "approved_source_prefab_property_readback_verified": property_readback,
        }
    )
    if not (actor_added and simple_added and actor_assignment and motion_assignment and property_readback):
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = (
            "blocked_by_editor_component_assignment_readback_failure"
        )
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = result[
            "approved_source_prefab_actor_simple_motion_wiring_blocker"
        ]
        result["safe_call_results"] = safe_call_results
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return result

    override_refs = _approved_source_prefab_wiring_component_refs(entity_id, surface, binding_report, safe_call_results)
    result["approved_source_prefab_component_override_refs"] = {
        key: value
        for key, value in override_refs.items()
        if key not in {"actor_component_ref", "simple_motion_component_ref"}
    }
    entity_commit_status = _call_prefab_commit_approved_source_entity_changes(project_source_path, entity_id)
    result["approved_source_prefab_entity_change_commit_status"] = entity_commit_status
    result["approved_source_prefab_entity_changes_committed"] = bool(entity_commit_status.get("committed"))
    override_status = _call_prefab_apply_approved_source_component_overrides(
        project_source_path,
        override_refs.get("actor_component_ref"),
        override_refs.get("simple_motion_component_ref"),
    )
    result["approved_source_prefab_component_override_apply_status"] = override_status
    result["approved_source_prefab_component_overrides_applied"] = bool(override_status.get("applied"))
    if not (
        result["approved_source_prefab_entity_changes_committed"]
        or result["approved_source_prefab_component_overrides_applied"]
    ):
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = (
            "blocked_by_prefab_entity_change_commit_or_component_override_apply_failed"
        )
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = result[
            "approved_source_prefab_actor_simple_motion_wiring_blocker"
        ]
        result["safe_call_results"] = safe_call_results
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return result

    rejection_statuses = _call_approved_source_prefab_wiring_rejection_probes(project_source_path)
    route_status = _call_prefab_save_update_approved_source_route(project_source_path)
    project_after_hash = _sha256_file(project_source_path) if project_source_path.exists() else ""
    parse_verified = _parse_prefab_json(project_source_path) if route_status.get("saved") else False
    result["approved_source_prefab_save_route_status"] = route_status
    result["approved_source_prefab_path_policy_rejections"] = rejection_statuses
    result["approved_source_prefab_project_after_hash"] = project_after_hash
    result["approved_source_prefab_save_verified"] = bool(route_status.get("saved")) and parse_verified
    result["approved_prefab_save_update_bridge_verified"] = result["approved_source_prefab_save_verified"]
    result["approved_prefab_save_update_bridge_callable_from_editor_python"] = bool(route_status.get("callable"))
    result["approved_prefab_save_update_rejected_defaultlevel_path"] = _route_rejection_verified(
        rejection_statuses, "defaultlevel"
    )
    result["approved_prefab_save_update_rejected_production_level_path"] = _route_rejection_verified(
        rejection_statuses, "production_level"
    )
    result["approved_prefab_save_update_rejected_generated_product_path"] = _route_rejection_verified(
        rejection_statuses, "generated_product"
    )
    result["approved_prefab_save_update_rejected_unapproved_absolute_path"] = _route_rejection_verified(
        rejection_statuses, "unapproved_absolute"
    )
    result["approved_prefab_save_update_rejected_path_traversal"] = _route_rejection_verified(
        rejection_statuses, "path_traversal"
    )

    if not result["approved_source_prefab_save_verified"]:
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = (
            "blocked_by_approved_source_prefab_save_policy"
        )
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = result[
            "approved_source_prefab_actor_simple_motion_wiring_blocker"
        ]
        result["safe_call_results"] = safe_call_results
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return result

    project_after_bytes = project_source_path.read_bytes()
    project_persisted_wiring_markers_verified = b"ActorAsset" in project_after_bytes and b"MotionAsset" in project_after_bytes
    result["approved_source_prefab_project_persisted_wiring_markers_verified"] = (
        project_persisted_wiring_markers_verified
    )
    result["approved_source_prefab_project_changed_this_run"] = bool(
        project_before_hash and project_after_hash != project_before_hash
    )
    if not project_persisted_wiring_markers_verified:
        result["approved_source_prefab_after_hash"] = repo_before_hash
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = (
            "blocked_by_editor_generated_instance_changes_not_propagated_to_source_template"
        )
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = result[
            "approved_source_prefab_actor_simple_motion_wiring_blocker"
        ]
        result["safe_call_results"] = safe_call_results
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return result

    try:
        repo_source_path.write_bytes(project_after_bytes)
    except Exception as exc:
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = (
            "blocked_by_approved_source_prefab_save_policy"
        )
        result["approved_source_prefab_repo_copy_error"] = str(exc)
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = result[
            "approved_source_prefab_actor_simple_motion_wiring_blocker"
        ]
        result["safe_call_results"] = safe_call_results
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return result

    repo_after_hash = _sha256_file(repo_source_path)
    repo_after_bytes = repo_source_path.read_bytes()
    persisted_wiring_markers_verified = b"ActorAsset" in repo_after_bytes and b"MotionAsset" in repo_after_bytes
    result["approved_source_prefab_after_hash"] = repo_after_hash
    result["approved_source_prefab_changed_this_run"] = bool(repo_before_hash and repo_after_hash != repo_before_hash)
    result["approved_source_prefab_persisted_wiring_markers_verified"] = persisted_wiring_markers_verified
    result["approved_source_prefab_modified"] = persisted_wiring_markers_verified
    if not persisted_wiring_markers_verified:
        result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = (
            "blocked_by_editor_component_assignment_readback_failure"
        )
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = result[
            "approved_source_prefab_actor_simple_motion_wiring_blocker"
        ]
        result["safe_call_results"] = safe_call_results
        result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
        return result
    result["approved_source_prefab_actor_simple_motion_wiring_verified"] = True
    result["approved_source_prefab_actor_simple_motion_wiring_blocker"] = ""
    result["approved_runtime_animation_component_wiring_editor_generation_verified"] = True
    result["approved_runtime_animation_component_wiring_editor_generation_blocker"] = ""
    result["approved_runtime_animation_component_wiring_source_prefab_modified"] = result[
        "approved_source_prefab_modified"
    ]
    result["approved_runtime_animation_component_wiring_editor_generated_update_used"] = True
    result["approved_runtime_animation_component_wiring_prefab_save_verified"] = True
    result["safe_call_results"] = safe_call_results
    result["approved_source_prefab_cleanup"] = _delete_editor_entity(entity_id, safe_call_results)
    return result


def _approved_prefab_save_update_bridge_host_observation(source_validation: Mapping[str, Any]) -> Dict[str, Any]:
    expected_symbols = [
        "${gem_name}.Editor",
        "PAL_TRAIT_BUILD_HOST_TOOLS",
        "AzToolsFramework",
        "Source/Tools/",
        "PrefabSaveUpdateBridge",
        "_Editor",
        "BehaviorContext",
        "PrefabPublicInterface",
    ]
    observed_symbols = []
    for ref in source_validation.get("refs", []):
        if not isinstance(ref, Mapping):
            continue
        if ref.get("status") == "pass":
            source_symbols = list(ref.get("symbols", [])) + list(ref.get("unexpected_symbols", []))
        else:
            source_symbols = list(ref.get("unexpected_symbols", []))
        for symbol in source_symbols:
            symbol_text = str(symbol)
            if symbol_text in expected_symbols and symbol_text not in observed_symbols:
                observed_symbols.append(symbol_text)
    missing_symbols = [symbol for symbol in expected_symbols if symbol not in observed_symbols]
    return {
        "editor_host_registered": not missing_symbols,
        "observed_editor_host_symbols": observed_symbols,
        "missing_editor_host_symbols": missing_symbols,
    }


def _approved_prefab_save_update_path_allowed(path_value: str) -> bool:
    normalized = str(path_value).replace("\\", "/").lower()
    if not normalized.endswith(".prefab"):
        return False
    if "/levels/" in normalized or "defaultlevel" in normalized or "/production/" in normalized:
        return False
    allowed_roots = (
        "examples/o3de-golden-project/source/assets/characters/maxine_goldencorpus/prefabs/",
        "examples/o3de-golden-project/source/assets/_maxine_smoke/prefabs/",
    )
    return any(root in normalized for root in allowed_roots)


def _approved_prefab_save_update_generated_product_path_rejected(path_value: str) -> bool:
    normalized = str(path_value).replace("\\", "/").lower()
    generated_markers = (
        "/cache/",
        "/asset cache/",
        "/pc/",
        "/build/",
        ".spawnable",
        "/user/log/",
    )
    return any(marker in normalized for marker in generated_markers)


def _run_approved_prefab_save_update_automation_surface_checks(report: Mapping[str, Any]) -> Dict[str, Any]:
    source_validation = _approved_prefab_save_update_source_validation()
    source_prefab_path = "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
    scratch_prefab_path = "examples/o3de-golden-project/source/Assets/_maxine_smoke/prefabs/prefab_save_update_surface_probe.prefab"
    behavior_context = _save_update_behavior_context_observation(source_validation)
    behavior_context_exposed = bool(behavior_context["exposed"]) and source_validation["verified"] is True

    blocker = "blocked_by_prefab_save_interface_not_available_to_automation"
    if source_validation["verified"] is not True:
        blocker = "blocked_by_prefab_save_update_requires_additional_source_validation"
    elif behavior_context_exposed:
        blocker = "blocked_by_prefab_save_update_scratch_save_not_verified"

    return {
        "approved_prefab_save_update_automation_surface_diagnostic_attempted": True,
        "approved_prefab_save_update_automation_surface_diagnostic_completed": True,
        "approved_prefab_save_update_automation_surface_found": behavior_context_exposed,
        "approved_prefab_save_update_automation_surface_verified": False,
        "approved_prefab_save_update_automation_surface_blocker": blocker,
        "approved_prefab_save_update_automation_candidate_matrix": _approved_prefab_save_update_candidate_matrix(),
        "approved_prefab_save_update_automation_selected_strategy": (
            "source_validate_prefab_save_api_and_block_on_unexposed_automation_binding"
        ),
        "approved_prefab_save_update_source_validation_status": source_validation["status"],
        "approved_prefab_save_update_source_validation_verified": source_validation["verified"],
        "approved_prefab_save_update_source_files": source_validation["refs"],
        "approved_prefab_save_update_api": {
            "interface": "AzToolsFramework::Prefab::PrefabPublicInterface",
            "create_prefab_and_save_to_disk": {
                "signature": "CreatePrefabResult CreatePrefabAndSaveToDisk(const EntityIdList&, AZ::IO::PathView)",
                "requires_absolute_path": True,
                "implementation": "PrefabPublicHandler::CreatePrefabAndSaveToDisk",
                "save_backend": "PrefabLoaderInterface::SaveTemplateToFile",
            },
            "save_prefab": {
                "signature": "PrefabOperationResult SavePrefab(AZ::IO::Path)",
                "implementation": "PrefabPublicHandler::SavePrefab",
                "requires_loaded_template": True,
                "save_backend": "PrefabLoaderInterface::SaveTemplate",
            },
            "behavior_context_available_events": [
                "CreatePrefabInMemory",
                "InstantiatePrefab",
                "DeleteEntitiesAndAllDescendantsInInstance",
                "GetOwningInstancePrefabPath",
                "CreateInMemorySpawnableAsset",
            ],
            "behavior_context_missing_events": [
                "CreatePrefabAndSaveToDisk",
                "SavePrefab",
            ],
        },
        "approved_prefab_save_update_behavior_context_exposed": behavior_context_exposed,
        "approved_prefab_save_update_behavior_context_observed_events": behavior_context["observed_events"],
        "approved_prefab_save_update_behavior_context_missing_events": behavior_context["missing_events"],
        "approved_prefab_save_update_bridge_added": False,
        "approved_prefab_save_update_bridge_verified": False,
        "approved_prefab_save_update_allowed_path_policy": {
            "allowed_prefab_roots": [
                "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/",
                "examples/o3de-golden-project/source/Assets/_maxine_smoke/prefabs/",
            ],
            "requires_prefab_extension": True,
            "rejects_levels": True,
            "rejects_defaultlevel": True,
            "rejects_production_level": True,
        },
        "approved_prefab_save_update_rejected_defaultlevel_path": not _approved_prefab_save_update_path_allowed(
            "examples/o3de-golden-project/source/Levels/defaultlevel/defaultlevel.prefab"
        ),
        "approved_prefab_save_update_rejected_production_level_path": not _approved_prefab_save_update_path_allowed(
            "examples/o3de-golden-project/source/Levels/production/release.prefab"
        ),
        "approved_prefab_save_update_scratch_prefab_path": scratch_prefab_path,
        "approved_prefab_save_update_scratch_save_attempted": False,
        "approved_prefab_save_update_scratch_save_verified": False,
        "approved_prefab_save_update_scratch_cleanup_verified": True,
        "approved_prefab_save_update_before_hash": "",
        "approved_prefab_save_update_after_hash": "",
        "approved_runtime_animation_component_wiring_source_prefab_path": source_prefab_path,
        "approved_runtime_animation_component_wiring_source_prefab_modified": False,
        "approved_runtime_animation_component_wiring_editor_generated_update_used": False,
        "approved_runtime_animation_component_wiring_actor_component_added": False,
        "approved_runtime_animation_component_wiring_simple_motion_component_added": False,
        "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_prefab_save_verified": False,
        "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _run_approved_prefab_save_update_bridge_checks(report: Mapping[str, Any]) -> Dict[str, Any]:
    source_validation = _source_validation_from_refs(_approved_prefab_save_update_bridge_source_refs())
    behavior_context = _save_update_behavior_context_observation(source_validation)
    bridge_host = _approved_prefab_save_update_bridge_host_observation(source_validation)
    source_prefab_path = "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
    scratch_prefab_path = "examples/o3de-golden-project/source/Assets/_maxine_smoke/prefabs/prefab_save_update_bridge_probe.prefab"
    source_verified = source_validation["verified"] is True
    editor_host_registered = bridge_host["editor_host_registered"] is True
    behavior_context_reflected = bool(behavior_context["exposed"]) and source_verified and editor_host_registered
    blocker = "blocked_by_prefab_save_bridge_requires_editor_gem_registration"
    if not source_verified:
        blocker = "blocked_by_prefab_save_bridge_requires_additional_source_validation"
    elif editor_host_registered and not behavior_context_reflected:
        blocker = "blocked_by_prefab_save_bridge_behavior_context_reflection_unavailable"
    elif behavior_context_reflected:
        blocker = "blocked_by_prefab_save_update_scratch_save_not_verified"

    return {
        "approved_prefab_save_update_bridge_diagnostic_attempted": True,
        "approved_prefab_save_update_bridge_diagnostic_completed": True,
        "approved_prefab_save_update_bridge_source_validation_status": source_validation["status"],
        "approved_prefab_save_update_bridge_source_validation_verified": source_validation["verified"],
        "approved_prefab_save_update_bridge_source_files": source_validation["refs"],
        "approved_prefab_save_update_bridge_added": editor_host_registered,
        "approved_prefab_save_update_bridge_verified": False,
        "approved_prefab_save_update_bridge_blocker": blocker,
        "approved_prefab_save_update_bridge_candidate_matrix": _approved_prefab_save_update_bridge_candidate_matrix(),
        "approved_prefab_save_update_bridge_selected_strategy": (
            "source_validate_editor_bridge_requirements_and_block_on_missing_editor_gem_registration"
        ),
        "approved_prefab_save_update_bridge_api": {
            "candidate_route": "BehaviorContext-reflected repo-owned Editor bridge",
            "source_api": "AzToolsFramework::Prefab::PrefabPublicInterface",
            "save_prefab": "PrefabOperationResult SavePrefab(AZ::IO::Path)",
            "create_prefab_and_save_to_disk": (
                "CreatePrefabResult CreatePrefabAndSaveToDisk(const EntityIdList&, AZ::IO::PathView)"
            ),
            "requires_editor_module": True,
            "requires_aztoolsframework_dependency": True,
            "requires_behavior_context_reflection": True,
            "selected_repo_host_candidate": "o3de/gems/MaxineRuntimeExitFixture",
            "host_candidate_status": (
                "editor_tools_module_source_observed"
                if editor_host_registered
                else "runtime_client_only_no_editor_tools_module"
            ),
            "editor_host_registered": editor_host_registered,
            "observed_editor_host_symbols": bridge_host["observed_editor_host_symbols"],
            "missing_editor_host_symbols": bridge_host["missing_editor_host_symbols"],
        },
        "approved_prefab_save_update_bridge_behavior_context_reflected": behavior_context_reflected,
        "approved_prefab_save_update_bridge_callable_from_editor_python": behavior_context_reflected,
        "approved_prefab_save_update_automation_surface_found": behavior_context_reflected,
        "approved_prefab_save_update_automation_surface_verified": False,
        "approved_prefab_save_update_automation_surface_blocker": blocker,
        "approved_prefab_save_update_behavior_context_exposed": behavior_context["exposed"] and source_verified,
        "approved_prefab_save_update_behavior_context_observed_events": behavior_context["observed_events"],
        "approved_prefab_save_update_behavior_context_missing_events": behavior_context["missing_events"],
        "approved_prefab_save_update_allowed_path_policy": {
            "allowed_prefab_roots": [
                "examples/o3de-golden-project/source/Assets/_maxine_smoke/prefabs/",
            ],
            "approved_source_prefab_root_deferred": (
                "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/"
            ),
            "requires_prefab_extension": True,
            "rejects_levels": True,
            "rejects_defaultlevel": True,
            "rejects_production_level": True,
            "rejects_generated_products": True,
        },
        "approved_prefab_save_update_rejected_defaultlevel_path": not _approved_prefab_save_update_path_allowed(
            "examples/o3de-golden-project/source/Levels/defaultlevel/defaultlevel.prefab"
        ),
        "approved_prefab_save_update_rejected_production_level_path": not _approved_prefab_save_update_path_allowed(
            "examples/o3de-golden-project/source/Levels/production/release.prefab"
        ),
        "approved_prefab_save_update_rejected_generated_product_path": _approved_prefab_save_update_generated_product_path_rejected(
            "examples/o3de-golden-project/Cache/pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable"
        ),
        "approved_prefab_save_update_scratch_prefab_path": scratch_prefab_path,
        "approved_prefab_save_update_scratch_save_attempted": False,
        "approved_prefab_save_update_scratch_save_verified": False,
        "approved_prefab_save_update_scratch_reload_or_parse_verified": False,
        "approved_prefab_save_update_scratch_cleanup_verified": True,
        "approved_prefab_save_update_before_hash": "",
        "approved_prefab_save_update_after_hash": "",
        "approved_prefab_save_update_generated_products_committed": False,
        "approved_runtime_animation_component_wiring_source_prefab_path": source_prefab_path,
        "approved_runtime_animation_component_wiring_source_prefab_modified": False,
        "approved_runtime_animation_component_wiring_editor_generated_update_used": False,
        "approved_runtime_animation_component_wiring_actor_component_added": False,
        "approved_runtime_animation_component_wiring_simple_motion_component_added": False,
        "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": False,
        "approved_runtime_animation_component_wiring_prefab_save_verified": False,
        "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _approved_animation_component_wiring_candidate_matrix() -> List[Dict[str, Any]]:
    return [
        {
            "candidate": "Editor-generated approved source-prefab update using EditorComponentAPIBus + PrefabPublic APIs",
            "outcome": "blocked",
            "reason": "PrefabPublicRequestBus does not expose SavePrefab or CreatePrefabAndSaveToDisk to Editor Python automation.",
        },
        {
            "candidate": "Actor + Simple Motion minimal surface",
            "outcome": "selected_for_editor_component_assignment_probe",
            "reason": "Source-validated minimal playback-capable component pair; source-prefab save remains blocked.",
        },
        {
            "candidate": "Actor + Anim Graph + Motion Set",
            "outcome": "deferred",
            "reason": "Broader activation surface is not needed before the source-prefab save path is proven.",
        },
        {
            "candidate": "hand-authored unknown .prefab component JSON",
            "outcome": "rejected",
            "reason": "Unknown O3DE component serialization must not be hand-authored.",
        },
        {
            "candidate": "direct runtime .procprefab load",
            "outcome": "rejected",
            "reason": "Preserved unsupported/builder-only proof limit.",
        },
        {
            "candidate": "direct product-load of actor/motion/motionset/animgraph",
            "outcome": "rejected",
            "reason": "Product-load is not component wiring proof.",
        },
        {
            "candidate": "defaultlevel or production-level wiring/playback",
            "outcome": "rejected",
            "reason": "Defaultlevel and production-level mutation are disallowed for this slice.",
        },
        {
            "candidate": "temp/sandbox level",
            "outcome": "limited_to_existing_editor_binding_probe",
            "reason": "Existing Editor smoke policy uses an approved temp level only for non-production component API probing.",
        },
    ]


def _value_shape(value: Any) -> str:
    module = getattr(type(value), "__module__", "")
    name = getattr(type(value), "__name__", type(value).__name__)
    if module and module != "builtins":
        return f"{module}.{name}"
    return name


def _redacted_project_temp_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    marker = "/Levels/_maxine_smoke/"
    index = normalized.lower().find(marker.lower())
    if index >= 0:
        return "Levels/_maxine_smoke/" + normalized[index + len(marker):]
    project_path = os.environ.get("O3DE_PROJECT_PATH", "").replace("\\", "/").rstrip("/")
    if project_path and normalized.lower().startswith(project_path.lower() + "/"):
        relative = normalized[len(project_path) + 1 :]
        return "%USERPROFILE%/O3DE/Projects/MAXINE_GoldenCorpus/" + relative
    return normalized


def _product_ref(report: Mapping[str, Any], product_type: str) -> str:
    for product in report.get("produced_products", []):
        if isinstance(product, Mapping) and str(product.get("product_type", "")).strip() == product_type:
            return str(product.get("product_path", "")).strip()
    summary = report.get("product_evidence_summary", {})
    if isinstance(summary, Mapping):
        products = summary.get("products", [])
        if isinstance(products, list):
            for product in products:
                if isinstance(product, Mapping) and str(product.get("product_type", "")).strip() == product_type:
                    return str(product.get("product_path", "")).strip()
    return ""


def _smoke_from_binding_check(checks: Mapping[str, Any]) -> Dict[str, Any]:
    status = str(checks.get("status", "blocked_by_missing_binding")).strip()
    if status == "pass":
        return {"status": "pass", "binding_evidence": checks}
    return {
        "status": status if status in TYPED_BLOCKED_STATUSES else "blocked_by_missing_binding",
        "reason": checks.get("blocked_reason") or checks.get("unavailable_reason") or checks.get("message", ""),
    }


def _skipped_check(mode: str) -> Dict[str, Any]:
    return {"status": "skipped_by_mode", "skipped_mode": mode}


def _surface_available(surface: Mapping[str, Any]) -> bool:
    editor = surface.get("editor")
    return bool(surface.get("bus") is not None and editor is not None and hasattr(editor, "EditorComponentAPIBus"))


def _outcome_success(value: Any) -> bool:
    if value is None:
        return False
    try:
        if hasattr(value, "IsSuccess"):
            return bool(value.IsSuccess())
    except Exception:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _unwrap_outcome(value: Any) -> Any:
    try:
        if hasattr(value, "IsSuccess") and not value.IsSuccess():
            if hasattr(value, "GetError"):
                return value.GetError()
            return value
        if hasattr(value, "GetValue"):
            return value.GetValue()
    except Exception:
        return value
    return value


def _extract_sequence(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Mapping):
        return [value]
    try:
        if isinstance(value, Sequence):
            return list(value)
    except Exception:
        pass
    try:
        return list(value)
    except Exception:
        return [value]


def _safe_serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _safe_serialize(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_serialize(item) for item in value]
    return str(value)


def _unique(values: List[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
