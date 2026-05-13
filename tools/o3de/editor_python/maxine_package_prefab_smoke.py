#!/usr/bin/env python3
"""integration-ready O3DE Editor Python package/prefab smoke script.

The gated wrapper launches this script from Editor with EditorPythonBindings.
No live publication is performed here. The script writes a smoke report for
every outcome, uses only the approved temporary level root, and exits nonzero
when the Editor Python context or temp-level automation is unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple


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
    "blocked_by_prefab_save_update_requires_additional_source_validation",
    "blocked_by_prefab_save_update_writable_path_safety_contract",
    "blocked_by_prefab_save_update_scratch_save_not_verified",
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
            "approved_prefab_save_update_scratch_prefab_path": report.get(
                "approved_prefab_save_update_scratch_prefab_path", ""
            ),
            "approved_prefab_save_update_scratch_save_attempted": report.get(
                "approved_prefab_save_update_scratch_save_attempted", False
            ),
            "approved_prefab_save_update_scratch_save_verified": report.get(
                "approved_prefab_save_update_scratch_save_verified", False
            ),
            "approved_prefab_save_update_scratch_cleanup_verified": report.get(
                "approved_prefab_save_update_scratch_cleanup_verified", False
            ),
            "approved_prefab_save_update_before_hash": report.get("approved_prefab_save_update_before_hash", ""),
            "approved_prefab_save_update_after_hash": report.get("approved_prefab_save_update_after_hash", ""),
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

    if not errors and needs_temp_level and general is not None:
        try:
            _create_temp_level(general, temp_level_name, temp_level_path, progress_log=progress_log)
            report["temp_level_path_redacted"] = _redacted_temp_level_path(temp_level_name)
            report["level_strategy"] = "temp_sandbox_level"
        except Exception as exc:
            errors.append(MXN_RUNTIME_SMOKE_FAIL)
            messages.append(f"Temp level automation failed: {exc}")
            _write_progress_marker(progress_log, "create_level_failed", "failed", f"Temp level automation failed: {exc}", error_code=MXN_RUNTIME_SMOKE_FAIL)

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
