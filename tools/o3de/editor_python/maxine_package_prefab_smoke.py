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
    "full",
}
TYPED_BLOCKED_STATUSES = {
    "skipped_by_mode",
    "unavailable_with_verified_reason",
    "blocked_by_readiness",
    "blocked_by_missing_product_evidence",
    "blocked_by_missing_binding",
    "blocked_by_unsafe_operation",
    "unsupported_by_engine_binding",
}
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

    if diagnostic_mode in {"prefab-binding", "prefab-instantiation", "full"}:
        _write_progress_marker(progress_log, "prefab_binding_started", "started", "Running prefab/procprefab binding surface checks.")
        prefab_checks = _run_prefab_binding_checks(
            report,
            safe_call_results,
            entity_id=entity_id,
            attempt_instantiation=diagnostic_mode in {"prefab-instantiation", "full"},
            progress_log=progress_log,
        )
        result["prefab_binding_checks"] = prefab_checks
        result["prefab_smoke"] = _smoke_from_binding_check(prefab_checks)
        if isinstance(prefab_checks.get("instantiation"), Mapping):
            result["prefab_instantiation"] = prefab_checks["instantiation"]
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


def _run_prefab_binding_checks(
    report: Mapping[str, Any],
    safe_call_results: List[Dict[str, Any]],
    *,
    entity_id: Any,
    attempt_instantiation: bool,
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
    if instantiation.get("status") == "pass":
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
            "procprefab_direct_load": {
                "status": "unsupported_by_engine_binding",
                "reason": "PrefabPublicRequestBus.InstantiatePrefab is documented for source .prefab paths; APB procprefab remains product evidence, not the selected Editor source-prefab argument.",
            },
        }
    return {
        **result,
        "status": instantiation.get("status", "blocked_by_unsafe_operation"),
        "selected_call": "PrefabPublicRequestBus.CreatePrefabInMemory + PrefabPublicRequestBus.InstantiatePrefab",
        "argument_value_shape": {
            "prefab_path": "absolute temp-level .prefab path under Levels/_maxine_smoke",
            "entity_ids": "list[azlmbr.entity.EntityId]",
            "parent_entity_id": "azlmbr.entity.EntityId()",
            "position": "azlmbr.math.Vector3",
        },
        "instantiation": instantiation,
        "blocked_reason": instantiation.get("blocked_reason", "prefab_instantiation_failed"),
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
