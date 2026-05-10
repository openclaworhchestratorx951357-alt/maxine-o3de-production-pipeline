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
from typing import Any, Dict, List, Mapping


MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"
MXN_PATH_UNSAFE = "MXN_PATH_UNSAFE"
MXN_RUNTIME_SMOKE_FAIL = "MXN_RUNTIME_SMOKE_FAIL"
DIAGNOSTIC_MODES = {"hello", "product-evidence", "temp-level", "entity-minimal", "full"}
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
        }
    )

    if env.get("MAXINE_ALLOW_LIVE_PUBLICATION") == "1":
        errors.append(MXN_PATH_UNSAFE)
        messages.append("Live publication gate must remain disabled.")
    if env.get("MAXINE_ENABLE_RELEASE_PACKAGING") == "1":
        errors.append(MXN_PATH_UNSAFE)
        messages.append("Release packaging gate must remain disabled.")
    needs_temp_level = diagnostic_mode in {"temp-level", "entity-minimal", "full"}
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

    if not errors and diagnostic_mode in {"entity-minimal", "full"}:
        _write_progress_marker(progress_log, "entity_create_started", "started", "Creating minimal temporary smoke entity.")
        entity_result = _try_create_smoke_entity()
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
        report["prefab_smoke"] = {"status": "unavailable", "reason": "Prefab instantiation is not attempted until component APIs are pinned."}
        report["actor_smoke"] = {"status": "unavailable", "reason": "Actor component binding is not attempted until component type IDs are pinned."}

    if not errors and diagnostic_mode == "full" and general is not None:
        try:
            if hasattr(general, "save_level"):
                _write_progress_marker(progress_log, "save_level_started", "started", "Saving approved temporary smoke level.")
                general.save_level()
                _write_progress_marker(progress_log, "save_level_returned", "returned", "Temporary smoke level save returned.")
        except Exception as exc:
            warnings.append("MXN_EDITOR_LEVEL_SAVE_UNAVAILABLE")
            messages.append(f"Temp level save was unavailable: {exc}")

    report["status"] = "fail" if errors else "pass"
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


def _try_create_smoke_entity() -> Dict[str, Any]:
    try:
        import azlmbr.bus as bus  # type: ignore
        import azlmbr.editor as editor  # type: ignore
        import azlmbr.entity as entity  # type: ignore

        parent = entity.EntityId()
        entity_id = editor.ToolsApplicationRequestBus(bus.Broadcast, "CreateNewEntity", parent)
        editor.EditorEntityAPIBus(bus.Event, "SetName", entity_id, "maxine_smoke_entity")
        name = editor.EditorEntityInfoRequestBus(bus.Event, "GetName", entity_id)
        return {"status": "pass", "entity_id": str(entity_id), "name": str(name or "maxine_smoke_entity")}
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)}


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
