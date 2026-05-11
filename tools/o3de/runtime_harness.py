#!/usr/bin/env python3
"""Bounded, non-publishing O3DE runtime harness contract.

This tool pins the runtime harness readiness layer separately from runtime
character proof.  It can discover launcher candidates, validate provenance and
project pairing, require explicit live runtime gates, and record a typed blocker
when a bounded runtime command has not yet been pinned.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.validation.results import ValidationResult


MXN_RUNTIME_SMOKE_FAIL = "MXN_RUNTIME_SMOKE_FAIL"
MXN_PATH_UNSAFE = "MXN_PATH_UNSAFE"
MXN_ASSET_PRODUCT_MISSING = "MXN_ASSET_PRODUCT_MISSING"
MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN = "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN"
MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"

DEFAULT_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "o3de-integration" / "runtime-harness"
EXPECTED_PRODUCTS = ("azmodel", "actor", "procprefab", "motion", "motionset", "animgraph", "pxmesh", "azmaterial")
RUNTIME_GATE_ENV_VARS = ("MAXINE_ENABLE_O3DE_RUNTIME_HARNESS", "MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS")
PROJECT_NAME = "MAXINE_GoldenCorpus"

MISSING_RUNTIME_SIGNAL_PATTERNS = {
    "runtime_missing_actor_signal": ("missing actor", "failed to load actor", ".actor not found"),
    "runtime_missing_mesh_signal": ("missing mesh", "failed to load mesh", ".azmodel not found", ".pxmesh not found"),
    "runtime_missing_material_signal": ("missing material", "failed to load material", ".azmaterial not found"),
    "runtime_missing_animation_signal": (
        "missing animation",
        "failed to load motion",
        "failed to load anim graph",
        ".motion not found",
        ".motionset not found",
        ".animgraph not found",
    ),
    "runtime_load_error_signal": ("load error", "failed to load", "asset load failed"),
}


def fixture_runtime_harness_report() -> Dict[str, Any]:
    report = _base_report(mode="fixture", status="pass")
    report.update(
        {
            "runtime_harness_status": "runtime_harness_ready_but_execution_not_requested",
            "runtime_harness_readiness_status": "runtime_harness_readiness_pass",
            "runtime_harness_readiness": {
                "status": "runtime_harness_readiness_pass",
                "mode": "fixture",
                "reason": "Fixture mode validates report semantics without launching runtime.",
            },
            "runtime_harness_mode": "fixture",
            "runtime_harness_proof_claimed": True,
            "runtime_harness_proof_verified": True,
            "runtime_harness_proof_is_character_proof": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_harness_report_contract",
                "runtime_execution_not_attempted_with_explicit_status",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "fixture_mode_does_not_launch_runtime",
                "runtime_harness_readiness_is_not_runtime_character_proof",
            ],
        }
    )
    return _with_nested_runtime_harness(report)


def run_runtime_harness(
    *,
    manifest: Path | str = DEFAULT_MANIFEST,
    mode: str = "fixture",
    check_local_readiness: bool = False,
    pin_runtime_command: bool = False,
    strict: bool = False,
    enable_runtime_harness: bool = False,
    strict_integration: bool = False,
    engine_root: Path | str | None = None,
    project: Path | str | None = None,
    apb_report: Path | str | None = None,
    timeout_seconds: int = 120,
    env: Mapping[str, str] | None = None,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
) -> Dict[str, Any]:
    env_map = dict(env if env is not None else os.environ)
    if mode == "fixture" and not check_local_readiness and not pin_runtime_command and not enable_runtime_harness:
        return fixture_runtime_harness_report()

    manifest_path = _resolve_path(manifest)
    selected_engine = _resolve_optional_path(engine_root or env_map.get("O3DE_ENGINE_ROOT", ""))
    selected_project = _resolve_optional_path(project or env_map.get("O3DE_PROJECT_PATH", ""))
    selected_apb = _resolve_optional_path(apb_report or env_map.get("MAXINE_APB_BASELINE_REPORT", ""))
    artifact_dir = _resolve_path(artifact_root)

    report = _base_report(mode="local_runtime_harness", status="pass")
    report.update(
        {
            "manifest_ref": _repo_relative(manifest_path),
            "strict": bool(strict),
            "strict_integration": bool(strict_integration),
            "runtime_harness_mode": "readiness"
            if check_local_readiness
            else "command_pinning"
            if pin_runtime_command and not enable_runtime_harness
            else "live_bounded_command",
            "runtime_command_timeout_seconds": int(timeout_seconds),
            "runtime_timeout_seconds": int(timeout_seconds),
            "runtime_command_gate_env": _runtime_gate_status(env_map),
        }
    )

    product_evidence = _product_evidence_from_apb(selected_apb)
    readiness = _runtime_readiness(
        engine_root=selected_engine,
        project=selected_project,
        product_evidence=product_evidence,
    )
    report.update(readiness["flat"])
    report["runtime_harness_readiness"] = readiness["payload"]
    report["runtime_executable_candidates"] = readiness["candidates"]
    report["product_evidence_summary"] = product_evidence
    report["expected_products"] = list(EXPECTED_PRODUCTS)
    report["produced_products"] = product_evidence.get("produced_products", [])
    report["missing_products"] = product_evidence.get("missing_products", [])
    report["pending_products"] = product_evidence.get("pending_products", [])
    report["cache_heuristic_used"] = bool(product_evidence.get("cache_heuristic_used", False))

    readiness_status = str(readiness["flat"].get("runtime_harness_readiness_status", "")).strip()
    if readiness_status != "runtime_harness_readiness_pass":
        strict_failure = strict or strict_integration or enable_runtime_harness
        report.update(
            {
                "status": "fail" if strict_failure else "skipped",
                "runtime_harness_status": readiness_status,
                "runtime_harness_blocked_reason": readiness_status,
                "runtime_harness_unavailable_reason": readiness_status,
                "required_runtime_harness_assertions_failed": ["runtime_harness_readiness"] if strict_failure else [],
                "runtime_harness_unavailable_reasons": [
                    {
                        "assertion": "runtime_harness_readiness",
                        "status": readiness_status,
                        "reason": readiness_status,
                    }
                ],
            }
        )
        return _finalize_report(report)

    if check_local_readiness and not enable_runtime_harness:
        report.update(
            {
                "status": "pass",
                "runtime_harness_status": "runtime_harness_readiness_pass",
                "runtime_harness_proof_claimed": True,
                "runtime_harness_proof_verified": True,
                "runtime_harness_proof_is_character_proof": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
                "required_runtime_harness_assertions_passed": [
                    "apb_product_evidence_complete",
                    "runtime_executable_candidate_discovered",
                    "runtime_executable_provenance_valid",
                    "runtime_project_engine_pairing_valid",
                    "runtime_execution_not_attempted_in_readiness_mode",
                ],
                "runtime_harness_assertion_informational": [
                    "readiness_mode_does_not_launch_runtime",
                    "runtime_harness_readiness_is_not_runtime_character_proof",
                ],
            }
        )
        return _finalize_report(report)

    if pin_runtime_command and not enable_runtime_harness:
        command = _select_runtime_command(report, artifact_dir=artifact_dir, timeout_seconds=timeout_seconds)
        if not command["selected"]:
            report.update(_unpinned_runtime_command_payload(command))
            return _finalize_report(report)
        report.update(_runtime_command_pin_payload(command, timeout_seconds=timeout_seconds, execution_requested=False))
        report.update(
            {
                "status": "pass",
                "runtime_harness_status": "runtime_command_pinning_pass",
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "runtime_harness_proof_claimed": True,
                "runtime_harness_proof_verified": True,
                "runtime_harness_proof_is_character_proof": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
                "required_runtime_harness_assertions_passed": [
                    "apb_product_evidence_complete",
                    "runtime_readiness_pass",
                    "runtime_command_pinning_pass",
                    "runtime_execution_not_attempted_in_command_pinning_mode",
                    "runtime_character_proof_not_claimed",
                ],
                "runtime_harness_assertion_informational": [
                    "command_pinning_mode_does_not_launch_runtime",
                    "runtime_command_pinning_is_not_runtime_character_proof",
                ],
            }
        )
        return _finalize_report(report)

    gate_status = _runtime_gate_status(env_map)
    if gate_status["status"] != "pass":
        report.update(
            {
                "status": "fail",
                "runtime_harness_status": "blocked_by_missing_runtime_gate",
                "runtime_harness_blocked_reason": "blocked_by_missing_runtime_gate",
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "required_runtime_harness_assertions_failed": ["runtime_live_gate"],
            }
        )
        return _finalize_report(report)

    command = _select_runtime_command(report, artifact_dir=artifact_dir, timeout_seconds=timeout_seconds)
    if not command["selected"]:
        report.update(_unpinned_runtime_command_payload(command))
        return _finalize_report(report)

    return _run_bounded_runtime_command(
        report,
        command=command,
        env=env_map,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
        command_runner=command_runner,
    )


def validate_runtime_harness_report(report: Mapping[str, Any], *, strict: bool = True) -> ValidationResult:
    result = ValidationResult()
    if report.get("fake_success") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime harness cannot set fake_success=true.")
    if report.get("cache_heuristic_used") is True:
        result.add_error(MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN, "Runtime harness cannot use cache heuristic release proof.")
    if report.get("live_publication") is True:
        result.add_error(MXN_PATH_UNSAFE, "Runtime harness must not enable live publication.")
    if report.get("release_packaging") is True:
        result.add_error(MXN_PATH_UNSAFE, "Runtime harness must not enable release packaging.")
    if report.get("production_level_mutation") is True:
        result.add_error(MXN_PATH_UNSAFE, "Runtime harness must not mutate production levels.")

    attempted = report.get("runtime_execution_attempted") is True
    completed = report.get("runtime_execution_completed") is True
    verified = report.get("runtime_execution_verified") is True
    execution_status = str(report.get("runtime_execution_status", "")).strip()
    if verified and not attempted:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime execution cannot be verified unless it was attempted.")
    if verified and not completed:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime execution verified=true requires runtime_execution_completed=true.")
    if verified and execution_status != "runtime_execution_pass":
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime execution verified=true requires runtime_execution_status=runtime_execution_pass.")
    if report.get("live_runtime_execution") is True and not attempted:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "live_runtime_execution=true requires runtime_execution_attempted=true.")
    if attempted and report.get("runtime_command_pin_verified") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime execution requires a verified pinned runtime command.")
    if report.get("runtime_command_pin_verified") is True and report.get("runtime_command_pinned") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_command_pin_verified=true requires runtime_command_pinned=true.")
    if report.get("runtime_command_pinned") is True:
        if report.get("runtime_command_allows_publication") is True:
            result.add_error(MXN_PATH_UNSAFE, "Pinned runtime command must not allow publication.")
        if report.get("runtime_command_allows_release_packaging") is True:
            result.add_error(MXN_PATH_UNSAFE, "Pinned runtime command must not allow release packaging.")
        if report.get("runtime_command_allows_production_mutation") is True:
            result.add_error(MXN_PATH_UNSAFE, "Pinned runtime command must not allow production mutation.")
        safety_profile = report.get("runtime_command_safety_profile", {})
        if isinstance(safety_profile, Mapping) and safety_profile.get("uses_production_level") is True:
            result.add_error(MXN_PATH_UNSAFE, "Pinned runtime command must not use production levels.")
    if report.get("runtime_harness_proof_is_character_proof") is True and not report.get("runtime_character_proof_verified"):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime harness readiness cannot be counted as runtime character proof.")
    if report.get("runtime_character_proof_claimed") is True and not report.get("runtime_character_proof_verified"):
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime character proof cannot be claimed without verified character evidence.")
    if report.get("runtime_timed_out") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime harness command timed out.")
    if execution_status in {"runtime_execution_failed", "runtime_execution_timed_out", "runtime_execution_killed_after_timeout"}:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"Runtime harness execution failed with status {execution_status}.")
    if not attempted and report.get("runtime_harness_status") in {"pass", "runtime_execution_pass"}:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Unattempted runtime execution cannot report runtime execution pass.")

    failed = report.get("required_runtime_harness_assertions_failed", [])
    if isinstance(failed, list) and failed:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime harness cannot pass with failed required assertions.")

    scan = report.get("runtime_log_scan", {})
    scan_status = str(scan.get("status", "")).strip() if isinstance(scan, Mapping) else ""
    if scan_status in {"fail", "assertion_failed_editor_log_missing_asset", "assertion_failed_editor_log_load_error"}:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime harness log scan found missing asset or load-error signals.")
    return result


def print_text_report(report: Mapping[str, Any]) -> None:
    print(f"Runtime harness: {report.get('status', '')}")
    print(f"mode: {report.get('mode', '')}")
    print(f"runtime_harness_status: {report.get('runtime_harness_status', '')}")
    print(f"runtime_harness_readiness_status: {report.get('runtime_harness_readiness_status', '')}")
    print(f"runtime_executable_selected: {report.get('runtime_executable_selected', '')}")
    print(f"runtime_executable_path: {report.get('runtime_executable_path', '')}")
    print(f"runtime_executable_provenance: {report.get('runtime_executable_provenance', '')}")
    print(f"runtime_command_pinning_status: {report.get('runtime_command_pinning_status', '')}")
    print(f"runtime_command_selected: {report.get('runtime_command_selected', '')}")
    print(f"runtime_command_pinned: {str(report.get('runtime_command_pinned', False)).lower()}")
    print(f"runtime_command_pin_verified: {str(report.get('runtime_command_pin_verified', False)).lower()}")
    print(f"runtime_execution_attempted: {str(report.get('runtime_execution_attempted', False)).lower()}")
    print(f"runtime_execution_completed: {str(report.get('runtime_execution_completed', False)).lower()}")
    print(f"runtime_execution_verified: {str(report.get('runtime_execution_verified', False)).lower()}")
    print(f"runtime_character_proof_claimed: {str(report.get('runtime_character_proof_claimed', False)).lower()}")
    print(f"runtime_character_proof_verified: {str(report.get('runtime_character_proof_verified', False)).lower()}")
    print(f"live_runtime_execution: {str(report.get('live_runtime_execution', False)).lower()}")
    print(f"live_publication: {str(report.get('live_publication', False)).lower()}")
    print(f"release_packaging: {str(report.get('release_packaging', False)).lower()}")
    print(f"production_level_mutation: {str(report.get('production_level_mutation', False)).lower()}")
    for code in report.get("errors", []):
        print(f"  error: {code}")
    for message in report.get("messages", []):
        print(f"  message: {message}")


def _base_report(*, mode: str, status: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": "1.0.0",
        "report_type": "runtime_harness_v1",
        "generated_at": now,
        "mode": mode,
        "status": status,
        "runtime_harness_status": "not_run",
        "runtime_harness_mode": mode,
        "runtime_harness_readiness": {"status": "not_run"},
        "runtime_harness_readiness_status": "not_run",
        "runtime_executable_candidates": [],
        "runtime_executable_selected": "",
        "runtime_executable_path": "",
        "runtime_executable_exists": False,
        "runtime_executable_provenance": "",
        "runtime_executable_project_pairing": {"status": "not_run"},
        "runtime_executable_engine_pairing": {"status": "not_run"},
        "runtime_command_pinning": {"status": "not_run"},
        "runtime_command_pinning_status": "not_run",
        "runtime_command_discovery_status": "not_run",
        "runtime_command_selected": "",
        "runtime_command_selected_reason": "",
        "runtime_command_arguments": [],
        "runtime_command_argument_shape": {},
        "runtime_command_kind": "",
        "runtime_command_safety_profile": {},
        "runtime_command_safety_flags": [],
        "runtime_command_timeout_seconds": 0,
        "runtime_command_expected_exit_codes": [],
        "runtime_command_kill_policy": "",
        "runtime_command_requires_gate_env": list(RUNTIME_GATE_ENV_VARS),
        "runtime_command_allows_publication": False,
        "runtime_command_allows_release_packaging": False,
        "runtime_command_allows_production_mutation": False,
        "runtime_command_is_non_publishing": False,
        "runtime_command_is_non_packaging": False,
        "runtime_command_mutates_production": False,
        "runtime_command_uses_production_level": False,
        "runtime_command_uses_temp_level": False,
        "runtime_command_uses_no_level": False,
        "runtime_command_exits_on_own": False,
        "runtime_command_pinned": False,
        "runtime_command_pin_verified": False,
        "runtime_command_blocked_reason": "",
        "runtime_command_unavailable_reason": "",
        "runtime_command_unsupported_reason": "",
        "runtime_command_stdout_ref": "",
        "runtime_command_stderr_ref": "",
        "runtime_command_log_refs": [],
        "runtime_command_log_scan": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_command_gate_env": {"status": "not_run", "required": list(RUNTIME_GATE_ENV_VARS), "missing": []},
        "runtime_execution_attempted": False,
        "runtime_execution_completed": False,
        "runtime_execution_verified": False,
        "runtime_execution_status": "runtime_execution_not_attempted",
        "runtime_exit_code": None,
        "runtime_timed_out": False,
        "runtime_timeout_stall": False,
        "runtime_kill_attempted": False,
        "runtime_kill_result": {"status": "not_run"},
        "runtime_stdout_ref": "",
        "runtime_stderr_ref": "",
        "runtime_log_refs": [],
        "runtime_log_scan": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_missing_actor_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_missing_mesh_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_missing_material_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_missing_animation_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_missing_asset_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_load_error_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_harness_blocked_reason": "",
        "runtime_harness_unavailable_reason": "",
        "runtime_harness_unsupported_reason": "",
        "runtime_harness_candidate_summary": {},
        "runtime_harness_proof_is_character_proof": False,
        "runtime_harness_proof_claimed": False,
        "runtime_harness_proof_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "runtime_spawnable_proof_surface_result": {"status": "runtime_spawnable_proof_requires_dedicated_runtime_harness"},
        "product_dependency_proof_result": {"status": "product_dependency_proof_unavailable"},
        "editor_component_inventory_character_assertion_result": {
            "status": "unavailable_with_verified_reason",
            "reason": "direct_procprefab_character_components_not_exposed_in_editor_product_instance",
        },
        "direct_product_instantiation_result": {"status": "preserved_from_editor_smoke"},
        "direct_product_content_assertion_result": {"status": "preserved_from_editor_smoke"},
        "source_prefab_baseline_result": {"status": "preserved_from_editor_smoke"},
        "actor_assignment_result": {"status": "preserved_from_editor_smoke"},
        "required_runtime_harness_assertions_passed": [],
        "required_runtime_harness_assertions_failed": [],
        "runtime_harness_assertion_failures": [],
        "runtime_harness_assertion_informational": [],
        "runtime_harness_unavailable_reasons": [],
        "runtime_harness_unsupported_reasons": [],
        "live_runtime_execution": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "fake_success": False,
        "cache_heuristic_used": False,
        "errors": [],
        "warnings": [],
        "messages": [],
    }


def _runtime_readiness(
    *,
    engine_root: Path | None,
    project: Path | None,
    product_evidence: Mapping[str, Any],
) -> Dict[str, Any]:
    project_name = _project_name(project) or PROJECT_NAME
    candidates = _runtime_candidates(engine_root, project_name)
    selected = _select_candidate(candidates)
    errors: List[str] = []

    if not product_evidence.get("product_evidence_complete"):
        errors.append("blocked_by_missing_product_evidence")
    if engine_root is None or not engine_root.exists() or not (engine_root / "engine.json").exists():
        errors.append("blocked_by_missing_engine_pairing")
    if project is None or not project.exists() or not (project / "project.json").exists():
        errors.append("blocked_by_missing_project_pairing")
    if not selected:
        errors.append("blocked_by_missing_runtime_executable")

    if errors:
        readiness_status = errors[0]
        selected_payload: Dict[str, Any] = {}
    else:
        readiness_status = "runtime_harness_readiness_pass"
        selected_payload = selected

    candidate_summary = {
        "candidate_count": len(candidates),
        "existing_candidate_count": sum(1 for candidate in candidates if candidate.get("exists") is True),
        "project_paired_candidate_count": sum(
            1 for candidate in candidates if candidate.get("runtime_executable_project_pairing", {}).get("status") == "pass"
        ),
        "selected": selected_payload.get("name", ""),
    }
    flat = {
        "runtime_harness_readiness_status": readiness_status,
        "runtime_executable_selected": selected_payload.get("name", ""),
        "runtime_executable_path": selected_payload.get("path", ""),
        "runtime_executable_exists": bool(selected_payload.get("exists")),
        "runtime_executable_provenance": selected_payload.get("runtime_executable_provenance", ""),
        "runtime_executable_project_pairing": selected_payload.get(
            "runtime_executable_project_pairing", {"status": "not_run"}
        ),
        "runtime_executable_engine_pairing": selected_payload.get("runtime_executable_engine_pairing", {"status": "not_run"}),
        "runtime_harness_candidate_summary": candidate_summary,
    }
    payload = {
        "status": readiness_status,
        "engine_root": str(engine_root or ""),
        "project_path": str(project or ""),
        "product_evidence_status": product_evidence.get("status", "unavailable_with_verified_reason"),
        "selected_runtime_executable": selected_payload.get("name", ""),
        "blocked_reasons": errors,
    }
    return {"flat": flat, "payload": payload, "candidates": candidates}


def _runtime_candidates(engine_root: Path | None, project_name: str) -> List[Dict[str, Any]]:
    profile_bin = _profile_bin(engine_root) if engine_root is not None else None
    names = [
        f"{project_name}.HeadlessServerLauncher.exe",
        f"{project_name}.GameLauncher.exe",
        f"{project_name}.ServerLauncher.exe",
        "GameLauncher.exe",
        "ServerLauncher.exe",
    ]
    candidates: List[Dict[str, Any]] = []
    for name in names:
        path = (profile_bin / name) if profile_bin is not None else Path(name)
        exists = path.exists()
        project_paired = name.startswith(f"{project_name}.")
        engine_paired = False
        if profile_bin is not None:
            try:
                path.resolve().relative_to(profile_bin.resolve())
                engine_paired = True
            except ValueError:
                engine_paired = False
        candidates.append(
            {
                "name": name,
                "path": str(path),
                "exists": exists,
                "runtime_executable_provenance": "engine_profile_bin" if exists and engine_paired else "missing",
                "runtime_executable_project_pairing": {
                    "status": "pass" if exists and project_paired else "not_project_paired" if exists else "missing",
                    "expected_project": project_name,
                },
                "runtime_executable_engine_pairing": {
                    "status": "pass" if exists and engine_paired else "missing",
                    "expected_profile_bin": str(profile_bin or ""),
                },
            }
        )
    return candidates


def _select_candidate(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    for candidate in candidates:
        if (
            candidate.get("exists") is True
            and candidate.get("runtime_executable_provenance") == "engine_profile_bin"
            and candidate.get("runtime_executable_project_pairing", {}).get("status") == "pass"
            and candidate.get("runtime_executable_engine_pairing", {}).get("status") == "pass"
        ):
            return dict(candidate)
    return {}


def _select_runtime_command(
    report: Mapping[str, Any],
    *,
    artifact_dir: Path,
    timeout_seconds: int,
) -> Dict[str, Any]:
    executable = str(report.get("runtime_executable_path", "")).strip()
    readiness = report.get("runtime_harness_readiness", {})
    project_path = str(readiness.get("project_path", "")).strip() if isinstance(readiness, Mapping) else ""
    if not executable or not project_path:
        return {
            "selected": False,
            "blocked_reason": "blocked_by_missing_runtime_readiness",
            "safety_flags": _runtime_command_safety_flags(),
        }

    command_file = artifact_dir / "maxine_runtime_command_quit.cfg"
    command_file.parent.mkdir(parents=True, exist_ok=True)
    command_file.write_text("quit\n", encoding="utf-8")
    argv = [
        executable,
        f"--project-path={project_path}",
        "-NullRenderer",
        "-rhi=null",
        "--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0",
        f"--console-command-file={command_file}",
    ]
    return {
        "selected": True,
        "argv": argv,
        "kind": "headless_console_quit_envelope",
        "selected_reason": "source_validated_headless_launcher_console_command_file_quit_envelope",
        "expected_exit_codes": [0],
        "timeout_seconds": int(timeout_seconds),
        "kill_policy": "subprocess_timeout_kill_and_report",
        "safety_flags": _runtime_command_safety_flags()
        + [
            "project_path_explicit",
            "null_renderer_requested",
            "no_level_or_map_argument",
            "console_command_file_contains_quit",
            "wait_for_connect_nonfatal",
        ],
        "argument_shape": {
            "argv0": "runtime executable path",
            "project_path": "--project-path=<MAXINE_GoldenCorpus project path>",
            "rendering": ["-NullRenderer", "-rhi=null"],
            "asset_processor_connect": "--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0",
            "exit_strategy": "--console-command-file=<artifact cfg containing quit>",
        },
        "safety_profile": {
            "local": True,
            "bounded_by_timeout": True,
            "evidence_captured": True,
            "stdout_stderr_capture_required": True,
            "log_capture_best_effort": True,
            "non_publishing": True,
            "non_packaging": True,
            "mutates_production": False,
            "uses_production_level": False,
            "uses_temp_level": False,
            "uses_no_level": True,
            "loads_character_content": False,
            "runtime_character_proof": False,
            "headless_launcher": True,
            "null_renderer_requested": True,
            "safe_to_kill_after_timeout": True,
            "command_file_ref": _repo_relative(command_file),
        },
        "source_evidence_refs": [
            "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:68",
            "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:606",
            "C:/src/o3de/Code/Legacy/CrySystem/SystemInit.cpp:1199",
            "C:/src/o3de/Code/Framework/AzGameFramework/AzGameFramework/Application/GameApplication.cpp:129",
            "C:/src/o3de/Code/Framework/AzCore/AzCore/Settings/SettingsRegistryMergeUtils.cpp:76",
        ],
    }


def _runtime_command_safety_flags() -> List[str]:
    return [
        "timeout_required",
        "stdout_stderr_capture_required",
        "runtime_logs_best_effort",
        "live_publication_false",
        "release_packaging_false",
        "production_level_mutation_false",
    ]


def _unpinned_runtime_command_payload(command: Mapping[str, Any]) -> Dict[str, Any]:
    blocked_reason = str(command.get("blocked_reason", "blocked_by_unpinned_runtime_command")).strip()
    return {
        "status": "pass",
        "runtime_harness_status": blocked_reason,
        "runtime_command_pinning_status": blocked_reason,
        "runtime_command_discovery_status": blocked_reason,
        "runtime_command_selected": "",
        "runtime_command_arguments": [],
        "runtime_command_safety_flags": command.get("safety_flags", _runtime_command_safety_flags()),
        "runtime_harness_blocked_reason": blocked_reason,
        "runtime_command_blocked_reason": blocked_reason,
        "runtime_execution_status": "runtime_execution_not_attempted",
        "runtime_execution_attempted": False,
        "runtime_execution_completed": False,
        "runtime_execution_verified": False,
        "runtime_command_pinned": False,
        "runtime_command_pin_verified": False,
        "runtime_harness_proof_claimed": True,
        "runtime_harness_proof_verified": True,
        "runtime_harness_proof_is_character_proof": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "required_runtime_harness_assertions_passed": [
            "apb_product_evidence_complete",
            "runtime_readiness_pass",
            "runtime_execution_not_attempted_with_typed_blocker",
            "runtime_character_proof_not_claimed",
        ],
        "runtime_harness_assertion_informational": [
            "runtime_executable_candidate_ready",
            "runtime_command_not_pinned",
            "runtime_harness_readiness_is_not_runtime_character_proof",
        ],
    }


def _runtime_command_pin_payload(
    command: Mapping[str, Any],
    *,
    timeout_seconds: int,
    execution_requested: bool,
) -> Dict[str, Any]:
    argv = list(command.get("argv", []))
    safety_profile = dict(command.get("safety_profile", {}))
    payload = {
        "runtime_command_pinning": {
            "status": "runtime_command_pinning_pass",
            "selected_reason": command.get("selected_reason", ""),
            "source_evidence_refs": command.get("source_evidence_refs", []),
            "execution_requested": bool(execution_requested),
        },
        "runtime_command_pinning_status": "runtime_command_pinning_pass",
        "runtime_command_discovery_status": "runtime_command_pinning_pass",
        "runtime_command_selected": argv[0] if argv else "",
        "runtime_command_selected_reason": command.get("selected_reason", ""),
        "runtime_command_arguments": argv[1:],
        "runtime_command_argument_shape": command.get("argument_shape", {}),
        "runtime_command_kind": command.get("kind", ""),
        "runtime_command_safety_profile": safety_profile,
        "runtime_command_safety_flags": command.get("safety_flags", _runtime_command_safety_flags()),
        "runtime_command_expected_exit_codes": command.get("expected_exit_codes", [0]),
        "runtime_command_timeout_seconds": int(timeout_seconds),
        "runtime_command_kill_policy": command.get("kill_policy", "subprocess_timeout_kill_and_report"),
        "runtime_command_allows_publication": False,
        "runtime_command_allows_release_packaging": False,
        "runtime_command_allows_production_mutation": False,
        "runtime_command_is_non_publishing": True,
        "runtime_command_is_non_packaging": True,
        "runtime_command_mutates_production": False,
        "runtime_command_uses_production_level": False,
        "runtime_command_uses_temp_level": False,
        "runtime_command_uses_no_level": True,
        "runtime_command_exits_on_own": True,
        "runtime_command_pinned": True,
        "runtime_command_pin_verified": True,
        "runtime_command_blocked_reason": "",
        "runtime_command_unavailable_reason": "",
        "runtime_command_unsupported_reason": "",
    }
    return payload


def _run_bounded_runtime_command(
    report: Dict[str, Any],
    *,
    command: Mapping[str, Any],
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> Dict[str, Any]:
    argv = list(command.get("argv", []))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = artifact_dir / "runtime_stdout.txt"
    stderr_path = artifact_dir / "runtime_stderr.txt"
    report.update(_runtime_command_pin_payload(command, timeout_seconds=timeout_seconds, execution_requested=True))
    report.update(
        {
            "runtime_execution_attempted": True,
            "live_runtime_execution": True,
            "runtime_stdout_ref": _repo_relative(stdout_path),
            "runtime_stderr_ref": _repo_relative(stderr_path),
            "runtime_command_stdout_ref": _repo_relative(stdout_path),
            "runtime_command_stderr_ref": _repo_relative(stderr_path),
        }
    )
    timed_out = False
    try:
        if command_runner is not None:
            proc = command_runner(argv=argv, cwd=str(REPO_ROOT), env=dict(env), timeout_seconds=timeout_seconds)
        else:
            proc = subprocess.run(argv, cwd=str(REPO_ROOT), env=dict(env), text=True, capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        proc = subprocess.CompletedProcess(argv, None, stdout=exc.output or "", stderr=exc.stderr or "")

    stdout_path.write_text(str(proc.stdout or ""), encoding="utf-8")
    stderr_path.write_text(str(proc.stderr or ""), encoding="utf-8")
    project_path = _runtime_project_path(report)
    log_refs = _runtime_log_refs(project_path)
    log_text = _read_runtime_logs(log_refs)
    scan = _scan_runtime_output(str(proc.stdout or "") + "\n" + str(proc.stderr or "") + "\n" + log_text)
    exit_code = proc.returncode
    expected_exit_codes = set(int(code) for code in command.get("expected_exit_codes", [0]))
    passed = exit_code in expected_exit_codes and not timed_out and scan["status"] == "pass"
    report.update(
        {
            "status": "pass" if passed else "fail",
            "runtime_harness_status": "runtime_execution_pass" if passed else "runtime_execution_timed_out" if timed_out else "runtime_execution_failed",
            "runtime_execution_completed": True,
            "runtime_execution_verified": passed,
            "runtime_execution_status": "runtime_execution_pass" if passed else "runtime_execution_timed_out" if timed_out else "runtime_execution_failed",
            "runtime_exit_code": exit_code,
            "runtime_timed_out": timed_out,
            "runtime_timeout_stall": timed_out,
            "runtime_kill_attempted": timed_out,
            "runtime_kill_result": {"status": "runtime_execution_killed_after_timeout" if timed_out else "not_run"},
            "runtime_log_refs": log_refs,
            "runtime_command_log_refs": log_refs,
            "runtime_log_scan": scan,
            "runtime_command_log_scan": scan,
            "runtime_harness_proof_claimed": passed,
            "runtime_harness_proof_verified": passed,
            "runtime_harness_proof_is_character_proof": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_command_pinning_pass",
                "runtime_bounded_command_executed",
                "runtime_character_proof_not_claimed",
            ]
            if passed
            else [],
            "required_runtime_harness_assertions_failed": [] if passed else ["runtime_bounded_command"],
        }
    )
    report.update(_runtime_signal_fields(scan))
    return _finalize_report(report)


def _product_evidence_from_apb(apb_report: Path | None) -> Dict[str, Any]:
    if apb_report is None or not apb_report.exists():
        return {
            "status": "blocked_by_missing_product_evidence",
            "report_ref": str(apb_report or ""),
            "product_evidence_complete": False,
            "produced_products": [],
            "missing_products": list(EXPECTED_PRODUCTS),
            "pending_products": [],
            "cache_heuristic_used": False,
        }
    try:
        payload = json.loads(apb_report.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "status": "blocked_by_missing_product_evidence",
            "report_ref": str(apb_report),
            "product_evidence_complete": False,
            "produced_products": [],
            "missing_products": list(EXPECTED_PRODUCTS),
            "pending_products": [],
            "cache_heuristic_used": False,
            "error": str(exc),
        }
    products = [product for product in payload.get("produced_products", []) if isinstance(product, Mapping)]
    ready_types = {str(product.get("product_type", "")).strip() for product in products if str(product.get("status", "ready")).strip() == "ready"}
    missing = [product_type for product_type in EXPECTED_PRODUCTS if product_type not in ready_types]
    pending = payload.get("pending_products", payload.get("pending_assets", []))
    failed = payload.get("failed_assets", [])
    cache_heuristic_used = bool(payload.get("cache_heuristic_used", False))
    complete = not missing and not pending and not failed and not cache_heuristic_used and str(payload.get("status", "pass")).strip() == "pass"
    return {
        "status": "pass" if complete else "blocked_by_missing_product_evidence",
        "report_ref": _repo_relative(apb_report),
        "product_evidence_complete": complete,
        "produced_products": products,
        "complete_products": sorted(ready_types.intersection(EXPECTED_PRODUCTS)),
        "missing_products": missing,
        "pending_products": pending if isinstance(pending, list) else [],
        "failed_assets": failed if isinstance(failed, list) else [],
        "cache_heuristic_used": cache_heuristic_used,
    }


def _runtime_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    missing = [name for name in RUNTIME_GATE_ENV_VARS if str(env.get(name, "")).strip() != "1"]
    return {
        "status": "pass" if not missing else "blocked_by_missing_runtime_gate",
        "required": list(RUNTIME_GATE_ENV_VARS),
        "missing": missing,
    }


def _scan_runtime_output(text: str) -> Dict[str, Any]:
    lower = text.lower()
    matches: List[Dict[str, str]] = []
    for signal, patterns in MISSING_RUNTIME_SIGNAL_PATTERNS.items():
        for pattern in patterns:
            if pattern in lower:
                matches.append({"signal": signal, "pattern": pattern})
    return {"status": "fail" if matches else "pass", "matches": matches}


def _runtime_signal_fields(scan: Mapping[str, Any]) -> Dict[str, Any]:
    matches = scan.get("matches", []) if isinstance(scan.get("matches", []), list) else []
    fields: Dict[str, Any] = {}
    for signal in MISSING_RUNTIME_SIGNAL_PATTERNS:
        signal_matches = [match for match in matches if isinstance(match, Mapping) and match.get("signal") == signal]
        fields[signal] = {"status": "fail" if signal_matches else "pass", "matches": signal_matches}
    fields["runtime_missing_asset_signal"] = {"status": "fail" if matches else "pass", "matches": matches}
    return fields


def _runtime_project_path(report: Mapping[str, Any]) -> Path | None:
    readiness = report.get("runtime_harness_readiness", {})
    if not isinstance(readiness, Mapping):
        return None
    raw = str(readiness.get("project_path", "")).strip()
    return Path(raw) if raw else None


def _runtime_log_refs(project: Path | None) -> List[str]:
    if project is None:
        return []
    log_dir = project / "user" / "log"
    if not log_dir.exists():
        return []
    names = {"Server.log", "Game.log", "Launcher.log"}
    candidates = [path for path in log_dir.iterdir() if path.is_file() and path.name in names]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return [str(path).replace("\\", "/") for path in candidates[:5]]


def _read_runtime_logs(refs: Sequence[str], *, max_chars_per_log: int = 200_000) -> str:
    chunks: List[str] = []
    for ref in refs:
        path = Path(ref)
        if not path.exists() or not path.is_file():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace")[:max_chars_per_log])
        except Exception:
            continue
    return "\n".join(chunks)


def _finalize_report(report: Dict[str, Any]) -> Dict[str, Any]:
    validation = validate_runtime_harness_report(report, strict=True)
    if validation.status == "fail":
        report["errors"] = _unique(list(report.get("errors", [])) + validation.error_codes)
        report["messages"] = _unique(list(report.get("messages", [])) + validation.messages)
        if str(report.get("status", "")).strip() == "pass":
            report["status"] = "fail"
    return _with_nested_runtime_harness(report)


def _with_nested_runtime_harness(report: Dict[str, Any]) -> Dict[str, Any]:
    nested_keys = [key for key in report if key.startswith("runtime_") or key in {"live_publication", "release_packaging", "production_level_mutation", "fake_success", "cache_heuristic_used"}]
    nested = {key: report[key] for key in nested_keys}
    report["runtime_harness"] = nested
    return report


def _project_name(project: Path | None) -> str:
    if project is not None and (project / "project.json").exists():
        try:
            payload = json.loads((project / "project.json").read_text(encoding="utf-8-sig"))
            name = str(payload.get("project_name") or payload.get("projectName") or "").strip()
            if name:
                return name
        except Exception:
            pass
    return project.name if project is not None else PROJECT_NAME


def _profile_bin(engine_root: Path | None) -> Path:
    return (engine_root or Path("")) / "build" / "windows" / "bin" / "profile"


def _resolve_path(path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def _resolve_optional_path(path: Path | str | None) -> Path | None:
    if path is None or str(path).strip() == "":
        return None
    return _resolve_path(path)


def _repo_relative(path: Path | str) -> str:
    candidate = Path(path)
    try:
        return str(candidate.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _unique(values: Sequence[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MAXINE bounded runtime harness contract.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--mode", choices=["fixture"], default="fixture")
    parser.add_argument("--check-local-readiness", action="store_true")
    parser.add_argument("--pin-runtime-command", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--enable-runtime-harness", action="store_true")
    parser.add_argument("--strict-integration", action="store_true")
    parser.add_argument("--engine-root", help="O3DE engine root.")
    parser.add_argument("--project", help="O3DE project path.")
    parser.add_argument("--apb-report", help="Trusted APB product evidence report.")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", help="Optional report output path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_runtime_harness(
        manifest=args.manifest,
        mode=args.mode,
        check_local_readiness=args.check_local_readiness,
        pin_runtime_command=args.pin_runtime_command,
        strict=args.strict,
        enable_runtime_harness=args.enable_runtime_harness,
        strict_integration=args.strict_integration,
        engine_root=args.engine_root,
        project=args.project,
        apb_report=args.apb_report,
        timeout_seconds=args.timeout_seconds,
    )
    if args.output:
        output = _resolve_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report)
    return 1 if report.get("status") == "fail" else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
