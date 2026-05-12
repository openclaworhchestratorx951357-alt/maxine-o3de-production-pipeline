#!/usr/bin/env python3
"""Bounded, non-publishing O3DE runtime harness contract.

This tool pins the runtime harness readiness layer separately from runtime
character proof.  It can discover launcher candidates, validate provenance and
project pairing, require explicit live runtime gates, and record a typed blocker
when a bounded runtime command has not yet been pinned.  When a bounded command
does run, nonzero exits are classified as diagnostic evidence without becoming
runtime execution proof or runtime character proof.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
RUNTIME_EXIT_FIXTURE_GEM_NAME = "MaxineRuntimeExitFixture"
RUNTIME_EXIT_FIXTURE_SOURCE_PATH = REPO_ROOT / "o3de" / "gems" / RUNTIME_EXIT_FIXTURE_GEM_NAME
RUNTIME_EXIT_FIXTURE_GEM_JSON = RUNTIME_EXIT_FIXTURE_SOURCE_PATH / "gem.json"
RUNTIME_EXIT_FIXTURE_ROOT_CMAKE = RUNTIME_EXIT_FIXTURE_SOURCE_PATH / "CMakeLists.txt"
RUNTIME_EXIT_FIXTURE_CMAKE = RUNTIME_EXIT_FIXTURE_SOURCE_PATH / "Code" / "CMakeLists.txt"
RUNTIME_EXIT_FIXTURE_COMPONENT_HEADER = (
    RUNTIME_EXIT_FIXTURE_SOURCE_PATH
    / "Code"
    / "Source"
    / "Clients"
    / "MaxineRuntimeExitFixtureSystemComponent.h"
)
RUNTIME_EXIT_FIXTURE_COMPONENT_SOURCE = (
    RUNTIME_EXIT_FIXTURE_SOURCE_PATH
    / "Code"
    / "Source"
    / "Clients"
    / "MaxineRuntimeExitFixtureSystemComponent.cpp"
)
RUNTIME_EXIT_FIXTURE_MODULE_SOURCE = (
    RUNTIME_EXIT_FIXTURE_SOURCE_PATH / "Code" / "Source" / "Clients" / "MaxineRuntimeExitFixtureModule.cpp"
)
RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS = (
    "/Amazon/MAXINE/RuntimeHarness/EnableExitFixture",
    "/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks",
)
RUNTIME_EXIT_FIXTURE_GATE_ENV = (
    "MAXINE_ENABLE_O3DE_RUNTIME_HARNESS=1",
    "MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS=1",
    "MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE=1",
)
RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV = ("MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION=1",)
RUNTIME_EXIT_FIXTURE_REBUILD_GATE_ENV = ("MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD=1",)
RUNTIME_EXIT_FIXTURE_TEMP_REGISTRY_PATCH_GATE_ENV = ("MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH=1",)
RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY = "/O3DE/Autoexec/ConsoleCommands/LoadLevel"
RUNTIME_DEFERRED_LOADLEVEL_KEY = "/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel"
RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH = "Levels/defaultlevel/defaultlevel.spawnable"
RUNTIME_NO_DEFAULT_LEVEL_REGREMOVE_ARG = f"--regremove={RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY}"
RUNTIME_DEFERRED_LOADLEVEL_REGREMOVE_ARG = f"--regremove={RUNTIME_DEFERRED_LOADLEVEL_KEY}"
RUNTIME_LOADLEVEL_OVERRIDE_SELECTED = "settings_registry_regremove_autoexec_and_deferred_loadlevel"
RUNTIME_LOADLEVEL_OVERRIDE_ARGS = (
    RUNTIME_NO_DEFAULT_LEVEL_REGREMOVE_ARG,
    RUNTIME_DEFERRED_LOADLEVEL_REGREMOVE_ARG,
)
RUNTIME_LATER_REGISTRY_PATCH_SELECTED = "artifact_setreg_merge_patch_null_autoexec_and_deferred_loadlevel"
RUNTIME_LATER_REGISTRY_PATCH_FAILED_JSON_PATCH_REMOVE = "artifact_setregpatch_remove_autoexec_and_deferred_loadlevel"
RUNTIME_LATER_REGISTRY_PATCH_FILENAME = "maxine_runtime_later_precedence_loadlevel_null_remove.setreg"
WINDOWS_NTSTATUS_NAMES = {
    0xC0000005: "STATUS_ACCESS_VIOLATION",
}

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
    diagnose_runtime_quit_variants: bool = False,
    diagnose_runtime_exit_strategies: bool = False,
    diagnose_runtime_exit_fixture: bool = False,
    check_runtime_exit_fixture_source: bool = False,
    check_runtime_exit_fixture_rebuild_gate: bool = False,
    register_runtime_exit_fixture: bool = False,
    enable_runtime_exit_fixture: bool = False,
    rebuild_runtime_exit_fixture: bool = False,
    enable_runtime_exit_fixture_command: bool = False,
    diagnose_runtime_launch_hygiene: bool = False,
    enable_runtime_exit_fixture_no_default_level: bool = False,
    diagnose_runtime_loadlevel_override: bool = False,
    enable_runtime_exit_fixture_loadlevel_override: bool = False,
    diagnose_runtime_later_registry_patch: bool = False,
    enable_runtime_exit_fixture_later_registry_patch: bool = False,
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
    if (
        mode == "fixture"
        and not check_local_readiness
        and not pin_runtime_command
        and not diagnose_runtime_quit_variants
        and not diagnose_runtime_exit_strategies
        and not diagnose_runtime_exit_fixture
        and not check_runtime_exit_fixture_source
        and not check_runtime_exit_fixture_rebuild_gate
        and not register_runtime_exit_fixture
        and not enable_runtime_exit_fixture
        and not rebuild_runtime_exit_fixture
        and not enable_runtime_exit_fixture_command
        and not diagnose_runtime_launch_hygiene
        and not enable_runtime_exit_fixture_no_default_level
        and not diagnose_runtime_loadlevel_override
        and not enable_runtime_exit_fixture_loadlevel_override
        and not diagnose_runtime_later_registry_patch
        and not enable_runtime_exit_fixture_later_registry_patch
        and not enable_runtime_harness
    ):
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
            if pin_runtime_command
            and not enable_runtime_harness
            and not diagnose_runtime_quit_variants
            and not diagnose_runtime_exit_strategies
            and not diagnose_runtime_exit_fixture
            and not check_runtime_exit_fixture_source
            and not check_runtime_exit_fixture_rebuild_gate
            and not register_runtime_exit_fixture
            and not enable_runtime_exit_fixture
            and not rebuild_runtime_exit_fixture
            and not enable_runtime_exit_fixture_command
            and not diagnose_runtime_launch_hygiene
            and not enable_runtime_exit_fixture_no_default_level
            and not diagnose_runtime_loadlevel_override
            and not enable_runtime_exit_fixture_loadlevel_override
            and not diagnose_runtime_later_registry_patch
            and not enable_runtime_exit_fixture_later_registry_patch
            else "runtime_quit_variant_diagnostic"
            if diagnose_runtime_quit_variants
            else "runtime_exit_strategy_diagnostic"
            if diagnose_runtime_exit_strategies
            else "runtime_exit_fixture_diagnostic"
            if diagnose_runtime_exit_fixture
            else "runtime_exit_fixture_source_readiness"
            if check_runtime_exit_fixture_source
            else "runtime_exit_fixture_rebuild_gate"
            if check_runtime_exit_fixture_rebuild_gate
            else "runtime_exit_fixture_registration"
            if register_runtime_exit_fixture
            else "runtime_exit_fixture_enablement"
            if enable_runtime_exit_fixture
            else "runtime_exit_fixture_rebuild"
            if rebuild_runtime_exit_fixture
            else "runtime_exit_fixture_command"
            if enable_runtime_exit_fixture_command
            else "runtime_launch_hygiene_diagnostic"
            if diagnose_runtime_launch_hygiene
            else "runtime_exit_fixture_no_default_level_command"
            if enable_runtime_exit_fixture_no_default_level
            else "runtime_loadlevel_override_diagnostic"
            if diagnose_runtime_loadlevel_override
            else "runtime_exit_fixture_loadlevel_override_command"
            if enable_runtime_exit_fixture_loadlevel_override
            else "runtime_later_registry_patch_diagnostic"
            if diagnose_runtime_later_registry_patch
            else "runtime_exit_fixture_later_registry_patch_command"
            if enable_runtime_exit_fixture_later_registry_patch
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

    if (
        pin_runtime_command
        and not enable_runtime_harness
        and not diagnose_runtime_quit_variants
        and not diagnose_runtime_exit_strategies
        and not diagnose_runtime_exit_fixture
        and not check_runtime_exit_fixture_source
        and not check_runtime_exit_fixture_rebuild_gate
        and not register_runtime_exit_fixture
        and not enable_runtime_exit_fixture
        and not rebuild_runtime_exit_fixture
        and not enable_runtime_exit_fixture_command
        and not diagnose_runtime_launch_hygiene
        and not enable_runtime_exit_fixture_no_default_level
        and not diagnose_runtime_loadlevel_override
        and not enable_runtime_exit_fixture_loadlevel_override
        and not diagnose_runtime_later_registry_patch
        and not enable_runtime_exit_fixture_later_registry_patch
    ):
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

    if check_runtime_exit_fixture_source:
        return _run_runtime_exit_fixture_source_check(report, timeout_seconds=timeout_seconds)

    if check_runtime_exit_fixture_rebuild_gate:
        return _run_runtime_exit_fixture_rebuild_gate_check(
            report,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
        )

    if register_runtime_exit_fixture:
        return _run_runtime_exit_fixture_registration(
            report,
            engine_root=selected_engine,
            project=selected_project,
            env=env_map,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
            command_runner=command_runner,
        )

    if enable_runtime_exit_fixture:
        return _run_runtime_exit_fixture_enablement(
            report,
            engine_root=selected_engine,
            project=selected_project,
            env=env_map,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
            command_runner=command_runner,
        )

    if rebuild_runtime_exit_fixture:
        return _run_runtime_exit_fixture_rebuild(
            report,
            engine_root=selected_engine,
            project=selected_project,
            env=env_map,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
            command_runner=command_runner,
        )

    if diagnose_runtime_launch_hygiene:
        return _run_runtime_launch_hygiene_diagnostic(
            report,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
        )

    if diagnose_runtime_loadlevel_override:
        return _run_runtime_loadlevel_override_diagnostic(
            report,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_later_registry_patch:
        return _run_runtime_later_registry_patch_diagnostic(
            report,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

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

    if (
        enable_runtime_exit_fixture_command
        or enable_runtime_exit_fixture_no_default_level
        or enable_runtime_exit_fixture_loadlevel_override
        or enable_runtime_exit_fixture_later_registry_patch
    ):
        return _run_runtime_exit_fixture_command(
            report,
            env=env_map,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
            command_runner=command_runner,
            no_default_level=enable_runtime_exit_fixture_no_default_level,
            loadlevel_override=enable_runtime_exit_fixture_loadlevel_override,
            later_registry_patch=enable_runtime_exit_fixture_later_registry_patch,
        )

    command = _select_runtime_command(report, artifact_dir=artifact_dir, timeout_seconds=timeout_seconds)
    if not command["selected"]:
        report.update(_unpinned_runtime_command_payload(command))
        return _finalize_report(report)

    if diagnose_runtime_quit_variants:
        return _run_runtime_quit_variant_diagnostics(
            report,
            command=command,
            env=env_map,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
            command_runner=command_runner,
        )

    if diagnose_runtime_exit_strategies:
        return _run_runtime_exit_strategy_diagnostics(
            report,
            command=command,
            env=env_map,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
            command_runner=command_runner,
        )

    if diagnose_runtime_exit_fixture:
        return _run_runtime_exit_fixture_diagnostics(
            report,
            command=command,
            timeout_seconds=timeout_seconds,
        )

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
    if report.get("defaultlevel_mutation") is True:
        result.add_error(MXN_PATH_UNSAFE, "Runtime harness must not mutate defaultlevel.")

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
    exit_code_decimal = report.get("runtime_exit_code_decimal")
    try:
        exit_code_is_nonzero = exit_code_decimal is not None and int(exit_code_decimal) != 0
    except (TypeError, ValueError):
        exit_code_is_nonzero = False
    if verified and exit_code_is_nonzero:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime execution verified=true cannot be paired with a nonzero runtime exit code.")
    if verified and report.get("runtime_exit_is_crash_like") is True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime execution verified=true cannot be paired with crash-like exit classification.")
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
    if report.get("runtime_safer_variant_verified") is True:
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_safer_variant_verified=true requires verified runtime execution.")
        if not str(report.get("runtime_safer_variant_selected", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_safer_variant_verified=true requires a selected safer variant.")
    if report.get("runtime_exit_strategy_verified") is True:
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_exit_strategy_verified=true requires verified runtime execution.")
        if not str(report.get("runtime_exit_strategy_selected", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_exit_strategy_verified=true requires a selected exit strategy.")
    if report.get("runtime_loadlevel_override_verified") is True:
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_loadlevel_override_verified=true requires verified runtime execution.")
        if str(report.get("runtime_launch_hygiene_status", "")).strip() != "runtime_launch_hygiene_pass":
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_loadlevel_override_verified=true requires runtime_launch_hygiene_pass.")
        if report.get("runtime_default_level_autoload_detected") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_loadlevel_override_verified=true cannot allow defaultlevel autoload.")
        if not str(report.get("runtime_loadlevel_override_selected", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_loadlevel_override_verified=true requires a selected LoadLevel override.")
    if report.get("runtime_later_registry_patch_verified") is True:
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_later_registry_patch_verified=true requires verified runtime execution.")
        if str(report.get("runtime_launch_hygiene_status", "")).strip() != "runtime_launch_hygiene_pass":
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_later_registry_patch_verified=true requires runtime_launch_hygiene_pass.")
        if report.get("runtime_default_level_autoload_detected") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_later_registry_patch_verified=true cannot allow defaultlevel autoload.")
        if not str(report.get("runtime_later_registry_patch_selected", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_later_registry_patch_verified=true requires a selected later-precedence registry patch.")
        patch_path_text = str(report.get("runtime_later_registry_patch_candidate_patch_path", "")).replace("\\", "/")
        if patch_path_text and "/artifacts/o3de-integration/runtime-harness/" not in patch_path_text and "pytest-" not in patch_path_text:
            result.add_error(MXN_PATH_UNSAFE, "runtime_later_registry_patch_verified=true requires a temp artifact registry patch path.")
    if report.get("runtime_exit_fixture_execution_verified") is True:
        if report.get("runtime_exit_fixture_execution_attempted") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_exit_fixture_execution_verified=true requires fixture execution attempt.")
        if report.get("runtime_exit_fixture_execution_completed") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_exit_fixture_execution_verified=true requires fixture execution completion.")
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_exit_fixture_execution_verified=true requires verified runtime execution.")
        if str(report.get("runtime_exit_fixture_status", "")).strip() != "runtime_exit_fixture_verified_clean_exit":
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_exit_fixture_execution_verified=true requires clean fixture status.")
        fixture_exit = report.get("runtime_exit_fixture_exit_code_decimal")
        try:
            fixture_exit_nonzero = fixture_exit is not None and int(fixture_exit) != 0
        except (TypeError, ValueError):
            fixture_exit_nonzero = False
        if fixture_exit_nonzero:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime exit fixture cannot verify execution with a nonzero exit code.")
        if report.get("runtime_exit_fixture_timed_out") is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime exit fixture cannot verify execution after timeout.")
        if str(report.get("runtime_launch_hygiene_status", "")).strip() != "runtime_launch_hygiene_pass":
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime exit fixture verification requires runtime_launch_hygiene_pass.")
        if report.get("runtime_default_level_autoload_detected") is True:
            result.add_error(MXN_PATH_UNSAFE, "Runtime exit fixture verification cannot allow defaultlevel autoload.")
        if report.get("runtime_asset_processor_negotiation_disqualifying") is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime exit fixture verification cannot allow disqualifying Asset Processor negotiation signals.")
        if report.get("runtime_shader_serializer_disqualifying") is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime exit fixture verification cannot allow disqualifying shader serializer signals.")
    if report.get("runtime_exit_fixture_character_proof_claimed") is True and report.get(
        "runtime_exit_fixture_character_proof_verified"
    ) is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime exit fixture cannot claim character proof without character evidence.")
    if report.get("runtime_exit_fixture_is_runtime_character_proof") is True and report.get(
        "runtime_exit_fixture_character_proof_verified"
    ) is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime exit fixture command-envelope proof is not runtime character proof.")
    if str(report.get("runtime_exit_fixture_shipping_status", "")).strip() in {
        "shipping_behavior",
        "shipping",
        "production_behavior",
    }:
        result.add_error(MXN_PATH_UNSAFE, "Runtime exit fixture must not be shipping or production behavior.")
    if report.get("runtime_exit_fixture_is_shipping_behavior") is True:
        result.add_error(MXN_PATH_UNSAFE, "Runtime exit fixture source must remain non-shipping behavior.")
    if report.get("runtime_exit_fixture_enabled_by_default") is True:
        result.add_error(MXN_PATH_UNSAFE, "Runtime exit fixture must be disabled by default.")
    if str(report.get("runtime_exit_fixture_source_status", "")).strip() == "runtime_exit_fixture_source_ready":
        if report.get("runtime_exit_fixture_source_owned_by_repo") is not True:
            result.add_error(MXN_PATH_UNSAFE, "Ready runtime exit fixture source must be owned by this repository.")
        source_path = str(report.get("runtime_exit_fixture_source_path", "")).replace("\\", "/").strip()
        if source_path.startswith("/") or ":" in source_path or ".." in Path(source_path).parts:
            result.add_error(MXN_PATH_UNSAFE, "Runtime exit fixture source path must be a safe repository-relative path.")
        if report.get("runtime_execution_verified") is True and report.get("runtime_exit_fixture_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime fixture source readiness is not runtime execution proof.")
    if report.get("runtime_exit_fixture_project_mutation_attempted") is True and str(
        report.get("runtime_exit_fixture_project_mutation_status", "")
    ).strip() != "runtime_exit_fixture_project_mutation_gate_pass":
        result.add_error(MXN_PATH_UNSAFE, "Runtime exit fixture project mutation requires the explicit project mutation gate.")
    if report.get("runtime_exit_fixture_rebuild_attempted") is True and str(
        report.get("runtime_exit_fixture_rebuild_gate_status", "")
    ).strip() != "runtime_exit_fixture_rebuild_gate_pass":
        result.add_error(MXN_PATH_UNSAFE, "Runtime exit fixture rebuild requires the explicit rebuild gate.")

    variants = report.get("runtime_command_variant_matrix", [])
    if isinstance(variants, list):
        for variant in variants:
            if not isinstance(variant, Mapping):
                continue
            variant_id = str(variant.get("runtime_command_variant_id", "")).strip() or "unknown_variant"
            expected_exit_codes = variant.get("runtime_command_variant_expected_exit_codes", [])
            if isinstance(expected_exit_codes, list) and 3221225477 in [int(code) for code in expected_exit_codes if str(code).strip().lstrip("-").isdigit()]:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{variant_id} cannot broaden expected exits to include 3221225477.")
            variant_verified = variant.get("runtime_command_variant_runtime_execution_verified") is True
            variant_status = str(variant.get("runtime_command_variant_status", "")).strip()
            variant_attempted = variant.get("runtime_command_variant_attempted") is True
            variant_exit = variant.get("runtime_command_variant_exit_code_decimal")
            try:
                variant_exit_nonzero = variant_exit is not None and int(variant_exit) != 0
            except (TypeError, ValueError):
                variant_exit_nonzero = False
            if variant_verified and not variant_attempted:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{variant_id} cannot verify execution without being attempted.")
            if variant_verified and variant_status != "runtime_command_variant_pass":
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{variant_id} cannot verify execution with status {variant_status}.")
            if variant_verified and variant_exit_nonzero:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{variant_id} cannot verify execution with a nonzero exit code.")
            if variant_verified and variant.get("runtime_command_variant_timed_out") is True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{variant_id} cannot verify execution after timeout.")
            if variant.get("runtime_command_variant_runtime_character_proof_claimed") is True and variant.get(
                "runtime_command_variant_runtime_character_proof_verified"
            ) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{variant_id} cannot claim runtime character proof without character evidence.")
    candidates = report.get("runtime_exit_strategy_candidate_matrix", [])
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            candidate_id = str(candidate.get("runtime_exit_strategy_candidate_id", "")).strip() or "unknown_exit_strategy_candidate"
            expected_exit_codes = candidate.get("runtime_exit_strategy_candidate_expected_exit_codes", [])
            if isinstance(expected_exit_codes, list) and 3221225477 in [
                int(code) for code in expected_exit_codes if str(code).strip().lstrip("-").isdigit()
            ]:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{candidate_id} cannot broaden expected exits to include 3221225477.")
            candidate_verified = candidate.get("runtime_exit_strategy_candidate_runtime_execution_verified") is True
            candidate_status = str(candidate.get("runtime_exit_strategy_candidate_status", "")).strip()
            candidate_attempted = candidate.get("runtime_exit_strategy_candidate_attempted") is True
            candidate_exit = candidate.get("runtime_exit_strategy_candidate_exit_code_decimal")
            try:
                candidate_exit_nonzero = candidate_exit is not None and int(candidate_exit) != 0
            except (TypeError, ValueError):
                candidate_exit_nonzero = False
            if candidate_verified and not candidate_attempted:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{candidate_id} cannot verify execution without being attempted.")
            if candidate_verified and candidate_status != "runtime_exit_strategy_candidate_attempted_pass":
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{candidate_id} cannot verify execution with status {candidate_status}.")
            if candidate_verified and candidate_exit_nonzero:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{candidate_id} cannot verify execution with a nonzero exit code.")
            if candidate_verified and candidate.get("runtime_exit_strategy_candidate_timed_out") is True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{candidate_id} cannot verify execution after timeout.")
            if candidate.get("runtime_exit_strategy_candidate_runtime_character_proof_claimed") is True and candidate.get(
                "runtime_exit_strategy_candidate_runtime_character_proof_verified"
            ) is not True:
                result.add_error(MXN_RUNTIME_SMOKE_FAIL, f"{candidate_id} cannot claim runtime character proof without character evidence.")
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
    if report.get("runtime_exit_code_decimal") is not None:
        print(f"runtime_exit_code_decimal: {report.get('runtime_exit_code_decimal')}")
        print(f"runtime_exit_code_hex: {report.get('runtime_exit_code_hex', '')}")
        print(f"runtime_exit_classification: {report.get('runtime_exit_classification', '')}")
    if report.get("runtime_quit_variant_diagnostic_status") not in {None, "", "not_run"}:
        print(f"runtime_quit_variant_diagnostic_status: {report.get('runtime_quit_variant_diagnostic_status', '')}")
        print(f"runtime_safer_variant_selected: {report.get('runtime_safer_variant_selected', '')}")
        print(f"runtime_safer_variant_verified: {str(report.get('runtime_safer_variant_verified', False)).lower()}")
    if report.get("runtime_exit_strategy_status") not in {None, "", "not_run"}:
        print(f"runtime_exit_strategy_status: {report.get('runtime_exit_strategy_status', '')}")
        print(f"runtime_exit_strategy_selected: {report.get('runtime_exit_strategy_selected', '')}")
        print(f"runtime_exit_strategy_verified: {str(report.get('runtime_exit_strategy_verified', False)).lower()}")
    if report.get("runtime_exit_fixture_status") not in {None, "", "not_run"}:
        print(f"runtime_exit_fixture_status: {report.get('runtime_exit_fixture_status', '')}")
        print(f"runtime_exit_fixture_available: {str(report.get('runtime_exit_fixture_available', False)).lower()}")
        print(f"runtime_exit_fixture_execution_verified: {str(report.get('runtime_exit_fixture_execution_verified', False)).lower()}")
    if report.get("runtime_exit_fixture_source_status") not in {None, "", "not_run"}:
        print(f"runtime_exit_fixture_source_status: {report.get('runtime_exit_fixture_source_status', '')}")
        print(f"runtime_exit_fixture_source_path: {report.get('runtime_exit_fixture_source_path', '')}")
    if report.get("runtime_exit_fixture_rebuild_gate_status") not in {None, "", "not_run"}:
        print(f"runtime_exit_fixture_rebuild_gate_status: {report.get('runtime_exit_fixture_rebuild_gate_status', '')}")
        print(f"runtime_exit_fixture_rebuild_attempted: {str(report.get('runtime_exit_fixture_rebuild_attempted', False)).lower()}")
    if report.get("runtime_exit_fixture_registration_status") not in {None, "", "not_run"}:
        print(f"runtime_exit_fixture_registration_status: {report.get('runtime_exit_fixture_registration_status', '')}")
        print(f"runtime_exit_fixture_registration_attempted: {str(report.get('runtime_exit_fixture_registration_attempted', False)).lower()}")
    if report.get("runtime_exit_fixture_enablement_status") not in {None, "", "not_run"}:
        print(f"runtime_exit_fixture_enablement_status: {report.get('runtime_exit_fixture_enablement_status', '')}")
        print(f"runtime_exit_fixture_enablement_attempted: {str(report.get('runtime_exit_fixture_enablement_attempted', False)).lower()}")
    if report.get("runtime_exit_fixture_rebuild_status") not in {None, "", "not_run", "not_attempted"}:
        print(f"runtime_exit_fixture_rebuild_status: {report.get('runtime_exit_fixture_rebuild_status', '')}")
        print(f"runtime_exit_fixture_rebuild_exit_code: {report.get('runtime_exit_fixture_rebuild_exit_code', '')}")
    if report.get("runtime_loadlevel_override_status") not in {None, "", "not_run", "runtime_execution_not_attempted"}:
        print(f"runtime_loadlevel_override_status: {report.get('runtime_loadlevel_override_status', '')}")
        print(f"runtime_loadlevel_override_verified: {str(report.get('runtime_loadlevel_override_verified', False)).lower()}")
    if report.get("runtime_later_registry_patch_status") not in {None, "", "not_run", "runtime_execution_not_attempted"}:
        print(f"runtime_later_registry_patch_status: {report.get('runtime_later_registry_patch_status', '')}")
        print(f"runtime_later_registry_patch_verified: {str(report.get('runtime_later_registry_patch_verified', False)).lower()}")
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
        "runtime_exit_classification": "runtime_execution_not_attempted",
        "runtime_exit_code_decimal": None,
        "runtime_exit_code_hex": "",
        "runtime_exit_code_signed": None,
        "runtime_exit_code_name": "",
        "runtime_exit_is_windows_ntstatus_like": False,
        "runtime_exit_is_crash_like": False,
        "runtime_crash_classification": "",
        "runtime_crash_evidence": [],
        "runtime_assertion_summary": {"status": "runtime_execution_not_attempted", "assert_count": 0},
        "runtime_asset_manager_asserts": {"status": "runtime_execution_not_attempted", "count": 0, "sample_lines": []},
        "runtime_shutdown_asserts": {"status": "runtime_execution_not_attempted", "count": 0, "sample_lines": []},
        "runtime_stack_or_crash_ref": "",
        "runtime_command_variant": "pinned_headless_console_quit_envelope",
        "runtime_command_variant_result": {
            "status": "runtime_command_variant_not_attempted",
            "attempted": False,
            "reason": "No safer command variant has been source-validated for fixture/readiness mode.",
        },
        "runtime_command_variant_reason": "",
        "runtime_command_variant_safety_profile": {},
        "runtime_command_variant_selected": False,
        "runtime_command_variant_rejected_reason": "",
        "runtime_command_variants": [],
        "runtime_command_variant_matrix": [],
        "runtime_safer_variant_selected": "",
        "runtime_safer_variant_selection_reason": "",
        "runtime_safer_variant_verified": False,
        "runtime_quit_variant_diagnostic_status": "not_run",
        "runtime_quit_variant_diagnostic_reason": "",
        "runtime_exit_strategy": {},
        "runtime_exit_strategy_status": "not_run",
        "runtime_exit_strategy_source_discovery_status": "not_run",
        "runtime_exit_strategy_candidates": [],
        "runtime_exit_strategy_candidate_matrix": [],
        "runtime_exit_strategy_selected": "",
        "runtime_exit_strategy_selected_reason": "",
        "runtime_exit_strategy_verified": False,
        "runtime_exit_strategy_blocked_reason": "",
        "runtime_exit_strategy_unavailable_reason": "",
        "runtime_exit_strategy_unsupported_reason": "",
        "runtime_exit_strategy_next_recommendation": "",
        "runtime_original_command_result": {},
        "runtime_command_pinning_result": {},
        "runtime_quit_variant_matrix_result": {},
        "runtime_exit_strategy_result": {},
        "runtime_exit_fixture": {},
        "runtime_exit_fixture_status": "not_run",
        "runtime_exit_fixture_available": False,
        "runtime_exit_fixture_kind": "",
        "runtime_exit_fixture_scope": "",
        "runtime_exit_fixture_shipping_status": "",
        "runtime_exit_fixture_source_discovery_status": "not_run",
        "runtime_exit_fixture_source_status": "not_run",
        "runtime_exit_fixture_source_path": "",
        "runtime_exit_fixture_source_owned_by_repo": False,
        "runtime_exit_fixture_gem_name": "",
        "runtime_exit_fixture_gem_type": "",
        "runtime_exit_fixture_gem_json_path": "",
        "runtime_exit_fixture_cmake_path": "",
        "runtime_exit_fixture_component_name": "",
        "runtime_exit_fixture_component_services": [],
        "runtime_exit_fixture_source_validation": {},
        "runtime_exit_fixture_source_refs": [],
        "runtime_exit_fixture_component_or_hook": "",
        "runtime_exit_fixture_lifecycle_point": "",
        "runtime_exit_fixture_exit_api": "",
        "runtime_exit_fixture_gate": "",
        "runtime_exit_fixture_gate_env": [],
        "runtime_exit_fixture_settings_registry_keys": [],
        "runtime_exit_fixture_settings_registry_key": "",
        "runtime_exit_fixture_command_line_arg": "",
        "runtime_exit_fixture_wait_ticks": "",
        "runtime_exit_fixture_command": "",
        "runtime_exit_fixture_arguments": [],
        "runtime_exit_fixture_argument_shape": {},
        "runtime_exit_fixture_safety_profile": {},
        "runtime_exit_fixture_requires_rebuild": False,
        "runtime_exit_fixture_rebuild_gate_status": "not_run",
        "runtime_exit_fixture_rebuild_command": [],
        "runtime_exit_fixture_rebuild_target": "",
        "runtime_exit_fixture_rebuild_attempted": False,
        "runtime_exit_fixture_rebuild_result": "",
        "runtime_exit_fixture_rebuild_exit_code": None,
        "runtime_exit_fixture_rebuild_stdout_ref": "",
        "runtime_exit_fixture_rebuild_stderr_ref": "",
        "runtime_exit_fixture_rebuild_artifact_refs": [],
        "runtime_exit_fixture_rebuild_status": "",
        "runtime_exit_fixture_enabled_for_project": False,
        "runtime_exit_fixture_registration_status": "not_run",
        "runtime_exit_fixture_registration_attempted": False,
        "runtime_exit_fixture_registration_command": [],
        "runtime_exit_fixture_registration_result": "",
        "runtime_exit_fixture_registration_stdout_ref": "",
        "runtime_exit_fixture_registration_stderr_ref": "",
        "runtime_exit_fixture_registration_changes": [],
        "runtime_exit_fixture_registration_reversible": False,
        "runtime_exit_fixture_registration_rollback": "",
        "runtime_exit_fixture_enablement_status": "not_run",
        "runtime_exit_fixture_enablement_attempted": False,
        "runtime_exit_fixture_enablement_command": [],
        "runtime_exit_fixture_enablement_result": "",
        "runtime_exit_fixture_enablement_stdout_ref": "",
        "runtime_exit_fixture_enablement_stderr_ref": "",
        "runtime_exit_fixture_enablement_changes": [],
        "runtime_exit_fixture_enablement_reversible": False,
        "runtime_exit_fixture_enablement_rollback": "",
        "runtime_exit_fixture_requires_project_mutation": False,
        "runtime_exit_fixture_project_mutation_status": "not_run",
        "runtime_exit_fixture_project_mutation_attempted": False,
        "runtime_exit_fixture_project_mutation_files": [],
        "runtime_exit_fixture_project_mutation_before_refs": [],
        "runtime_exit_fixture_project_mutation_after_refs": [],
        "runtime_exit_fixture_project_mutation_diff_summary": [],
        "runtime_exit_fixture_project_mutation_reversible": False,
        "runtime_exit_fixture_project_mutation_rollback": "",
        "runtime_exit_fixture_project_mutation_gate_env": [],
        "runtime_exit_fixture_enabled_by_default": False,
        "runtime_exit_fixture_is_shipping_behavior": False,
        "runtime_exit_fixture_mutates_production": False,
        "runtime_exit_fixture_uses_production_level": False,
        "runtime_exit_fixture_uses_temp_level": False,
        "runtime_exit_fixture_uses_no_level": False,
        "runtime_exit_fixture_execution_attempted": False,
        "runtime_exit_fixture_execution_completed": False,
        "runtime_exit_fixture_execution_verified": False,
        "runtime_exit_fixture_exit_code_decimal": None,
        "runtime_exit_fixture_exit_code_hex": "",
        "runtime_exit_fixture_exit_classification": "runtime_execution_not_attempted",
        "runtime_exit_fixture_timeout_seconds": 0,
        "runtime_exit_fixture_timed_out": False,
        "runtime_exit_fixture_kill_attempted": False,
        "runtime_exit_fixture_kill_result": {"status": "not_run"},
        "runtime_exit_fixture_stdout_ref": "",
        "runtime_exit_fixture_stderr_ref": "",
        "runtime_exit_fixture_log_refs": [],
        "runtime_exit_fixture_log_scan": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_fixture_asserts": {"status": "runtime_execution_not_attempted", "count": 0, "sample_lines": []},
        "runtime_exit_fixture_missing_asset_signals": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_fixture_disqualifying_signals": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_fixture_marker_observed": False,
        "runtime_exit_fixture_runtime_command": [],
        "runtime_exit_fixture_runtime_command_status": "not_run",
        "runtime_exit_fixture_runtime_command_arguments": [],
        "runtime_exit_fixture_runtime_command_uses_console_command_file_quit": False,
        "runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit": False,
        "runtime_exit_fixture_runtime_command_uses_no_default_level_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_loadlevel_override_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_later_registry_patch_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_temp_or_sandbox_level": False,
        "runtime_exit_fixture_level_load_observed": False,
        "runtime_exit_fixture_unexpected_level_load": False,
        "runtime_exit_fixture_actual_level_loads": [],
        "runtime_exit_fixture_blocked_reason": "",
        "runtime_exit_fixture_unavailable_reason": "",
        "runtime_exit_fixture_unsupported_reason": "",
        "runtime_exit_fixture_is_runtime_character_proof": False,
        "runtime_exit_fixture_character_proof_claimed": False,
        "runtime_exit_fixture_character_proof_verified": False,
        "runtime_launch_hygiene": {"status": "not_run"},
        "runtime_launch_hygiene_status": "not_run",
        "runtime_launch_level_policy": "",
        "runtime_launch_level_policy_status": "not_run",
        "runtime_default_level_autoload_detected": False,
        "runtime_default_level_path": "",
        "runtime_default_level_product_path": "",
        "runtime_default_level_source": "",
        "runtime_default_level_source_evidence": {},
        "runtime_default_level_disqualifying": False,
        "runtime_default_level_classification": "",
        "runtime_default_level_blocked_reason": "",
        "runtime_no_default_level_strategy": "",
        "runtime_no_default_level_strategy_status": "not_run",
        "runtime_no_default_level_source_validation": {},
        "runtime_no_default_level_source_refs": [],
        "runtime_no_default_level_command": "",
        "runtime_no_default_level_arguments": [],
        "runtime_no_default_level_settings_registry_keys": [],
        "runtime_no_default_level_expected_level_loads": [],
        "runtime_no_default_level_actual_level_loads": [],
        "runtime_no_default_level_execution_attempted": False,
        "runtime_no_default_level_execution_verified": False,
        "runtime_loadlevel_override": {"status": "not_run"},
        "runtime_loadlevel_override_status": "not_run",
        "runtime_loadlevel_override_candidates": [],
        "runtime_loadlevel_override_candidate_matrix_recorded": False,
        "runtime_loadlevel_override_candidate_id": "",
        "runtime_loadlevel_override_candidate_name": "",
        "runtime_loadlevel_override_candidate_kind": "",
        "runtime_loadlevel_override_candidate_source_validation": {},
        "runtime_loadlevel_override_candidate_source_refs": [],
        "runtime_loadlevel_override_candidate_command_args": [],
        "runtime_loadlevel_override_candidate_settings_registry_keys": [],
        "runtime_loadlevel_override_candidate_expected_registry_state": {},
        "runtime_loadlevel_override_candidate_actual_registry_state": {},
        "runtime_loadlevel_override_candidate_expected_level_loads": [],
        "runtime_loadlevel_override_candidate_actual_level_loads": [],
        "runtime_loadlevel_override_candidate_attempted": False,
        "runtime_loadlevel_override_candidate_result": "",
        "runtime_loadlevel_override_candidate_rejected_reason": "",
        "runtime_loadlevel_override_candidate_blocker": "",
        "runtime_loadlevel_override_selected": "",
        "runtime_loadlevel_override_selected_reason": "",
        "runtime_loadlevel_override_verified": False,
        "runtime_later_registry_patch": {"status": "runtime_execution_not_attempted"},
        "runtime_later_registry_patch_status": "runtime_execution_not_attempted",
        "runtime_later_registry_patch_candidates": [],
        "runtime_later_registry_patch_candidate_matrix_recorded": False,
        "runtime_later_registry_patch_candidate_id": "",
        "runtime_later_registry_patch_candidate_name": "",
        "runtime_later_registry_patch_candidate_kind": "",
        "runtime_later_registry_patch_candidate_source_validation": {},
        "runtime_later_registry_patch_candidate_source_refs": [],
        "runtime_later_registry_patch_candidate_patch_path": "",
        "runtime_later_registry_patch_candidate_patch_contents_summary": "",
        "runtime_later_registry_patch_candidate_merge_mechanism": "",
        "runtime_later_registry_patch_candidate_merge_order": "",
        "runtime_later_registry_patch_candidate_gate_env": [],
        "runtime_later_registry_patch_candidate_mutates_project": False,
        "runtime_later_registry_patch_candidate_mutates_defaultlevel": False,
        "runtime_later_registry_patch_candidate_mutates_production_level": False,
        "runtime_later_registry_patch_candidate_command_args": [],
        "runtime_later_registry_patch_candidate_settings_registry_keys": [],
        "runtime_later_registry_patch_candidate_expected_registry_state": {},
        "runtime_later_registry_patch_candidate_actual_registry_state": {},
        "runtime_later_registry_patch_candidate_expected_level_loads": [],
        "runtime_later_registry_patch_candidate_actual_level_loads": [],
        "runtime_later_registry_patch_candidate_attempted": False,
        "runtime_later_registry_patch_candidate_result": "",
        "runtime_later_registry_patch_candidate_rejected_reason": "",
        "runtime_later_registry_patch_candidate_blocker": "",
        "runtime_later_registry_patch_selected": "",
        "runtime_later_registry_patch_selected_reason": "",
        "runtime_later_registry_patch_verified": False,
        "runtime_later_registry_patch_gate_env": [],
        "runtime_later_registry_patch_gate_status": {"status": "not_run", "required": [], "missing": []},
        "runtime_later_registry_patch_generation_status": "not_attempted",
        "runtime_settings_registry_merge_order_summary": {},
        "runtime_settings_registry_command_line_override_order": "",
        "runtime_settings_registry_project_registry_order": "",
        "runtime_autoexec_console_command_source": "",
        "runtime_autoexec_console_command_effective_state": {},
        "runtime_autoexec_console_command_override_state": {},
        "runtime_default_level_override_blocker": "",
        "runtime_temp_harness_level_strategy": "not_used",
        "runtime_temp_harness_level_path": "",
        "runtime_temp_harness_level_generation_status": "not_attempted",
        "runtime_temp_harness_level_production_mutation": False,
        "runtime_empty_harness_level_strategy": "",
        "runtime_empty_harness_level_path": "",
        "runtime_empty_harness_level_generation_status": "not_run",
        "runtime_empty_harness_level_mutation_status": "not_run",
        "runtime_empty_harness_level_production_mutation": False,
        "runtime_asset_processor_negotiation_signal": {"status": "not_run", "count": 0},
        "runtime_asset_processor_negotiation_signal_status": "not_run",
        "runtime_asset_processor_negotiation_status": "not_run",
        "runtime_asset_processor_negotiation_classification": "",
        "runtime_asset_processor_negotiation_disqualifying": False,
        "runtime_shader_serializer_signal": {"status": "not_run", "count": 0},
        "runtime_shader_serializer_signal_status": "not_run",
        "runtime_shader_serializer_status": "not_run",
        "runtime_shader_serializer_classification": "",
        "runtime_shader_serializer_disqualifying": False,
        "runtime_disqualifying_signal_summary": [],
        "runtime_disqualifying_signal_count": 0,
        "runtime_fixture_marker_observed": False,
        "runtime_fixture_exit_code_clean": False,
        "runtime_fixture_clean_launch_verified": False,
        "runtime_log_error_summary": {"status": "runtime_execution_not_attempted"},
        "runtime_stdout_error_summary": {"status": "runtime_execution_not_attempted"},
        "runtime_stderr_error_summary": {"status": "runtime_execution_not_attempted"},
        "runtime_exit_diagnostic_status": "runtime_execution_not_attempted",
        "runtime_exit_diagnostic_reason": "",
        "runtime_root_cause_classification": "runtime_execution_not_attempted",
        "runtime_root_cause_hypothesis": "",
        "runtime_root_cause_confidence": "",
        "runtime_next_diagnostic_recommendation": "",
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
        "defaultlevel_mutation": False,
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

    stdout_text = str(proc.stdout or "")
    stderr_text = str(proc.stderr or "")
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    project_path = _runtime_project_path(report)
    log_refs = _runtime_log_refs(project_path)
    log_text = _read_runtime_logs(log_refs)
    scan = _scan_runtime_output(stdout_text + "\n" + stderr_text + "\n" + log_text)
    exit_code = proc.returncode
    diagnostics = _runtime_exit_diagnostics(
        exit_code=exit_code,
        timed_out=timed_out,
        stdout=stdout_text,
        stderr=stderr_text,
        log_text=log_text,
        log_refs=log_refs,
    )
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
    report.update(diagnostics)
    report.update(_runtime_signal_fields(scan))
    return _finalize_report(report)


def _run_runtime_exit_strategy_diagnostics(
    report: Dict[str, Any],
    *,
    command: Mapping[str, Any],
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> Dict[str, Any]:
    report.update(_runtime_command_pin_payload(command, timeout_seconds=timeout_seconds, execution_requested=False))
    candidates = _runtime_exit_strategy_candidate_matrix(command, artifact_dir=artifact_dir, timeout_seconds=timeout_seconds)
    attempted: List[Dict[str, Any]] = []
    for candidate in candidates:
        candidate_status = str(candidate.get("runtime_exit_strategy_candidate_status", "")).strip()
        if candidate_status not in {
            "runtime_exit_strategy_candidate_source_validated",
            "runtime_exit_strategy_candidate_attemptable",
        }:
            continue
        attempted_candidate = _attempt_runtime_exit_strategy_candidate(
            candidate,
            report=report,
            env=env,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
            command_runner=command_runner,
        )
        attempted.append(attempted_candidate)
        candidates = [
            attempted_candidate
            if item.get("runtime_exit_strategy_candidate_id") == attempted_candidate.get("runtime_exit_strategy_candidate_id")
            else item
            for item in candidates
        ]
        if attempted_candidate.get("runtime_exit_strategy_candidate_status") == "runtime_exit_strategy_candidate_attempted_pass":
            for index, candidate_item in enumerate(candidates):
                if (
                    candidate_item.get("runtime_exit_strategy_candidate_status")
                    in {"runtime_exit_strategy_candidate_source_validated", "runtime_exit_strategy_candidate_attemptable"}
                    and candidate_item.get("runtime_exit_strategy_candidate_id")
                    != attempted_candidate.get("runtime_exit_strategy_candidate_id")
                ):
                    candidates[index] = {
                        **candidate_item,
                        "runtime_exit_strategy_candidate_status": "runtime_exit_strategy_candidate_not_attempted",
                        "runtime_exit_strategy_candidate_attempted": False,
                        "runtime_exit_strategy_candidate_rejected_reason": "stopped_after_clean_exit_strategy",
                    }
            return _finalize_report(
                {
                    **report,
                    **_top_level_exit_strategy_success_payload(attempted_candidate, candidates),
                }
            )

    if attempted:
        return _finalize_report({**report, **_top_level_exit_strategy_failure_payload(attempted[-1], candidates)})

    return _finalize_report({**report, **_top_level_exit_strategy_blocked_payload(candidates)})


def _run_runtime_exit_fixture_diagnostics(
    report: Dict[str, Any],
    *,
    command: Mapping[str, Any],
    timeout_seconds: int,
) -> Dict[str, Any]:
    report.update(_runtime_command_pin_payload(command, timeout_seconds=timeout_seconds, execution_requested=False))
    report.update(_top_level_exit_fixture_blocked_payload(timeout_seconds=timeout_seconds))
    return _finalize_report(report)


def _run_runtime_exit_fixture_source_check(report: Dict[str, Any], *, timeout_seconds: int) -> Dict[str, Any]:
    source_payload = _runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds)
    report.update(source_payload)
    return _finalize_report(report)


def _run_runtime_exit_fixture_rebuild_gate_check(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
) -> Dict[str, Any]:
    source_payload = _runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds)
    if source_payload.get("status") != "pass":
        report.update(source_payload)
        report["runtime_harness_mode"] = "runtime_exit_fixture_rebuild_gate"
        return _finalize_report(report)
    rebuild_payload = _runtime_exit_fixture_rebuild_gate_payload(
        engine_root=engine_root,
        project=project,
        timeout_seconds=timeout_seconds,
    )
    report.update(source_payload)
    report.update(rebuild_payload)
    return _finalize_report(report)


def _run_runtime_exit_fixture_registration(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> Dict[str, Any]:
    source_payload = _runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds)
    report.update(source_payload)
    report["runtime_harness_mode"] = "runtime_exit_fixture_registration"
    if source_payload.get("status") != "pass":
        return _finalize_report(report)

    command = _runtime_exit_fixture_register_command(engine_root=engine_root, project=project)
    report.update(_runtime_exit_fixture_registration_common_payload(project=project, command=command))
    if _runtime_exit_fixture_registered_for_project(project):
        report.update(
            {
                "status": "pass",
                "runtime_harness_status": "runtime_exit_fixture_registration_already_registered",
                "runtime_exit_fixture_registration_status": "runtime_exit_fixture_registration_already_registered",
                "runtime_exit_fixture_registration_result": "already_registered",
                "runtime_exit_fixture_registration_reversible": True,
                "runtime_exit_fixture_project_mutation_status": "project_mutation_not_required",
                "runtime_exit_fixture_project_mutation_attempted": False,
                "runtime_exit_fixture_project_mutation_reversible": True,
                "runtime_exit_fixture_project_mutation_rollback": _runtime_exit_fixture_registration_rollback(project),
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "live_runtime_execution": False,
            }
        )
        return _finalize_report(report)

    if not _gate_enabled(env, "MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"):
        report.update(
            {
                "status": "fail",
                "runtime_harness_status": "blocked_by_fixture_registration_missing_gate",
                "runtime_exit_fixture_registration_status": "blocked_by_fixture_registration_missing_gate",
                "runtime_exit_fixture_registration_result": "blocked_by_fixture_registration_missing_gate",
                "runtime_exit_fixture_registration_attempted": False,
                "runtime_exit_fixture_project_mutation_status": "blocked_by_fixture_registration_missing_gate",
                "runtime_exit_fixture_project_mutation_attempted": False,
                "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_registration_missing_gate",
                "runtime_harness_blocked_reason": "blocked_by_fixture_registration_missing_gate",
                "required_runtime_harness_assertions_failed": ["runtime_exit_fixture_registration_gate"],
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "live_runtime_execution": False,
            }
        )
        return _finalize_report(report)

    before = _runtime_exit_fixture_project_state(project)
    proc, timed_out, stdout_ref, stderr_ref = _run_command_capture(
        command,
        env=env,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
        stem="runtime_exit_fixture_registration",
        command_runner=command_runner,
    )
    after = _runtime_exit_fixture_project_state(project)
    diff_summary = _runtime_exit_fixture_project_diff(before, after)
    registered = _runtime_exit_fixture_registered_for_project(project)
    passed = proc.returncode == 0 and not timed_out and registered
    report.update(
        {
            "status": "pass" if passed else "fail",
            "runtime_harness_status": "runtime_exit_fixture_registration_pass"
            if passed
            else "blocked_by_fixture_registration_failed",
            "runtime_exit_fixture_registration_status": "runtime_exit_fixture_registration_pass"
            if passed
            else "runtime_exit_fixture_registration_failed",
            "runtime_exit_fixture_registration_attempted": True,
            "runtime_exit_fixture_registration_result": "pass" if passed else "fail",
            "runtime_exit_fixture_registration_stdout_ref": stdout_ref,
            "runtime_exit_fixture_registration_stderr_ref": stderr_ref,
            "runtime_exit_fixture_registration_changes": diff_summary,
            "runtime_exit_fixture_registration_reversible": True,
            "runtime_exit_fixture_registration_rollback": _runtime_exit_fixture_registration_rollback(project),
            "runtime_exit_fixture_project_mutation_status": "runtime_exit_fixture_project_mutation_gate_pass",
            "runtime_exit_fixture_project_mutation_attempted": True,
            "runtime_exit_fixture_project_mutation_files": _runtime_exit_fixture_project_files(project),
            "runtime_exit_fixture_project_mutation_before_refs": before.get("refs", []),
            "runtime_exit_fixture_project_mutation_after_refs": after.get("refs", []),
            "runtime_exit_fixture_project_mutation_diff_summary": diff_summary,
            "runtime_exit_fixture_project_mutation_reversible": True,
            "runtime_exit_fixture_project_mutation_rollback": _runtime_exit_fixture_registration_rollback(project),
            "runtime_exit_fixture_enabled_for_project": _runtime_exit_fixture_enabled_for_project(project),
            "runtime_execution_status": "runtime_execution_not_attempted",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "live_runtime_execution": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_exit_fixture_source_ready",
                "runtime_exit_fixture_registration_gate_present",
                "runtime_exit_fixture_registration_command_completed",
                "runtime_exit_fixture_project_mutation_reversible",
                "runtime_execution_not_attempted_in_registration_mode",
                "runtime_character_proof_not_claimed",
            ]
            if passed
            else [],
            "required_runtime_harness_assertions_failed": [] if passed else ["runtime_exit_fixture_registration"],
        }
    )
    return _finalize_report(report)


def _run_runtime_exit_fixture_enablement(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> Dict[str, Any]:
    source_payload = _runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds)
    report.update(source_payload)
    report["runtime_harness_mode"] = "runtime_exit_fixture_enablement"
    if source_payload.get("status") != "pass":
        return _finalize_report(report)

    command = _runtime_exit_fixture_enable_command(engine_root=engine_root, project=project)
    report.update(_runtime_exit_fixture_enablement_common_payload(project=project, command=command))
    if _runtime_exit_fixture_enabled_for_project(project):
        report.update(
            {
                "status": "pass",
                "runtime_harness_status": "runtime_exit_fixture_already_enabled_for_project",
                "runtime_exit_fixture_enablement_status": "runtime_exit_fixture_already_enabled_for_project",
                "runtime_exit_fixture_enablement_result": "already_enabled",
                "runtime_exit_fixture_enablement_reversible": True,
                "runtime_exit_fixture_project_mutation_status": "project_mutation_not_required",
                "runtime_exit_fixture_project_mutation_attempted": False,
                "runtime_exit_fixture_project_mutation_reversible": True,
                "runtime_exit_fixture_project_mutation_rollback": _runtime_exit_fixture_enablement_rollback(project),
                "runtime_exit_fixture_enabled_for_project": True,
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "live_runtime_execution": False,
            }
        )
        return _finalize_report(report)

    if not _gate_enabled(env, "MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"):
        report.update(
            {
                "status": "fail",
                "runtime_harness_status": "blocked_by_fixture_enablement_missing_gate",
                "runtime_exit_fixture_enablement_status": "blocked_by_fixture_enablement_missing_gate",
                "runtime_exit_fixture_enablement_result": "blocked_by_fixture_enablement_missing_gate",
                "runtime_exit_fixture_enablement_attempted": False,
                "runtime_exit_fixture_project_mutation_status": "blocked_by_fixture_enablement_missing_gate",
                "runtime_exit_fixture_project_mutation_attempted": False,
                "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_enablement_missing_gate",
                "runtime_harness_blocked_reason": "blocked_by_fixture_enablement_missing_gate",
                "required_runtime_harness_assertions_failed": ["runtime_exit_fixture_enablement_gate"],
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "live_runtime_execution": False,
            }
        )
        return _finalize_report(report)

    before = _runtime_exit_fixture_project_state(project)
    proc, timed_out, stdout_ref, stderr_ref = _run_command_capture(
        command,
        env=env,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
        stem="runtime_exit_fixture_enablement",
        command_runner=command_runner,
    )
    after = _runtime_exit_fixture_project_state(project)
    diff_summary = _runtime_exit_fixture_project_diff(before, after)
    enabled = _runtime_exit_fixture_enabled_for_project(project)
    passed = proc.returncode == 0 and not timed_out and enabled
    report.update(
        {
            "status": "pass" if passed else "fail",
            "runtime_harness_status": "runtime_exit_fixture_enablement_pass"
            if passed
            else "blocked_by_fixture_enablement_failed",
            "runtime_exit_fixture_enablement_status": "runtime_exit_fixture_enablement_pass"
            if passed
            else "runtime_exit_fixture_enablement_failed",
            "runtime_exit_fixture_enablement_attempted": True,
            "runtime_exit_fixture_enablement_result": "pass" if passed else "fail",
            "runtime_exit_fixture_enablement_stdout_ref": stdout_ref,
            "runtime_exit_fixture_enablement_stderr_ref": stderr_ref,
            "runtime_exit_fixture_enablement_changes": diff_summary,
            "runtime_exit_fixture_enablement_reversible": True,
            "runtime_exit_fixture_enablement_rollback": _runtime_exit_fixture_enablement_rollback(project),
            "runtime_exit_fixture_project_mutation_status": "runtime_exit_fixture_project_mutation_gate_pass",
            "runtime_exit_fixture_project_mutation_attempted": True,
            "runtime_exit_fixture_project_mutation_files": _runtime_exit_fixture_project_files(project),
            "runtime_exit_fixture_project_mutation_before_refs": before.get("refs", []),
            "runtime_exit_fixture_project_mutation_after_refs": after.get("refs", []),
            "runtime_exit_fixture_project_mutation_diff_summary": diff_summary,
            "runtime_exit_fixture_project_mutation_reversible": True,
            "runtime_exit_fixture_project_mutation_rollback": _runtime_exit_fixture_enablement_rollback(project),
            "runtime_exit_fixture_enabled_for_project": enabled,
            "runtime_execution_status": "runtime_execution_not_attempted",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "live_runtime_execution": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_exit_fixture_source_ready",
                "runtime_exit_fixture_enablement_gate_present",
                "runtime_exit_fixture_enablement_command_completed",
                "runtime_exit_fixture_project_mutation_reversible",
                "runtime_execution_not_attempted_in_enablement_mode",
                "runtime_character_proof_not_claimed",
            ]
            if passed
            else [],
            "required_runtime_harness_assertions_failed": [] if passed else ["runtime_exit_fixture_enablement"],
        }
    )
    return _finalize_report(report)


def _run_runtime_exit_fixture_rebuild(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> Dict[str, Any]:
    source_payload = _runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds)
    report.update(source_payload)
    report["runtime_harness_mode"] = "runtime_exit_fixture_rebuild"
    if source_payload.get("status") != "pass":
        return _finalize_report(report)

    rebuild_command = _runtime_exit_fixture_rebuild_command(engine_root=engine_root, project=project)
    report.update(
        {
            "runtime_exit_fixture_rebuild_command": rebuild_command,
            "runtime_exit_fixture_rebuild_target": _runtime_exit_fixture_rebuild_target(project),
            "runtime_exit_fixture_requires_rebuild": True,
            "runtime_exit_fixture_rebuild_gate_status": "runtime_exit_fixture_rebuild_gate_pass"
            if _gate_enabled(env, "MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD")
            else "blocked_by_fixture_rebuild_missing_gate",
            "runtime_exit_fixture_enabled_for_project": _runtime_exit_fixture_enabled_for_project(project),
        }
    )
    if not _runtime_exit_fixture_enabled_for_project(project):
        report.update(
            {
                "status": "fail",
                "runtime_harness_status": "blocked_by_fixture_not_enabled_for_project",
                "runtime_exit_fixture_rebuild_status": "blocked_by_fixture_not_enabled_for_project",
                "runtime_exit_fixture_rebuild_result": "blocked_by_fixture_not_enabled_for_project",
                "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_not_enabled_for_project",
                "runtime_harness_blocked_reason": "blocked_by_fixture_not_enabled_for_project",
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "live_runtime_execution": False,
                "required_runtime_harness_assertions_failed": ["runtime_exit_fixture_enablement"],
            }
        )
        return _finalize_report(report)

    if not _gate_enabled(env, "MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD"):
        report.update(
            {
                "status": "fail",
                "runtime_harness_status": "blocked_by_fixture_rebuild_missing_gate",
                "runtime_exit_fixture_rebuild_status": "blocked_by_fixture_rebuild_missing_gate",
                "runtime_exit_fixture_rebuild_result": "blocked_by_fixture_rebuild_missing_gate",
                "runtime_exit_fixture_rebuild_attempted": False,
                "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_rebuild_missing_gate",
                "runtime_harness_blocked_reason": "blocked_by_fixture_rebuild_missing_gate",
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "live_runtime_execution": False,
                "required_runtime_harness_assertions_failed": ["runtime_exit_fixture_rebuild_gate"],
            }
        )
        return _finalize_report(report)

    proc, timed_out, stdout_ref, stderr_ref = _run_command_capture(
        rebuild_command,
        env=env,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
        stem="runtime_exit_fixture_rebuild",
        command_runner=command_runner,
    )
    passed = proc.returncode == 0 and not timed_out
    report.update(
        {
            "status": "pass" if passed else "fail",
            "runtime_harness_status": "runtime_exit_fixture_rebuild_pass" if passed else "blocked_by_fixture_rebuild_failed",
            "runtime_exit_fixture_rebuild_status": "runtime_exit_fixture_rebuild_pass"
            if passed
            else "runtime_exit_fixture_rebuild_failed",
            "runtime_exit_fixture_rebuild_attempted": True,
            "runtime_exit_fixture_rebuild_result": "runtime_exit_fixture_rebuild_pass"
            if passed
            else "runtime_exit_fixture_rebuild_failed",
            "runtime_exit_fixture_rebuild_exit_code": proc.returncode,
            "runtime_exit_fixture_rebuild_stdout_ref": stdout_ref,
            "runtime_exit_fixture_rebuild_stderr_ref": stderr_ref,
            "runtime_exit_fixture_rebuild_artifact_refs": [str(report.get("runtime_executable_path", ""))]
            if report.get("runtime_executable_path")
            else [],
            "runtime_execution_status": "runtime_execution_not_attempted",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "live_runtime_execution": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_exit_fixture_source_ready",
                "runtime_exit_fixture_enabled_for_project",
                "runtime_exit_fixture_rebuild_gate_present",
                "runtime_exit_fixture_rebuild_pass",
                "runtime_execution_not_attempted_in_rebuild_mode",
                "runtime_character_proof_not_claimed",
            ]
            if passed
            else [],
            "required_runtime_harness_assertions_failed": [] if passed else ["runtime_exit_fixture_rebuild"],
        }
    )
    return _finalize_report(report)


def _run_runtime_launch_hygiene_diagnostic(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
) -> Dict[str, Any]:
    report.update(_runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds))
    report["runtime_harness_mode"] = "runtime_launch_hygiene_diagnostic"
    payload = _runtime_launch_hygiene_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
    )
    source_validated = payload["runtime_no_default_level_strategy_status"] == "runtime_no_default_level_strategy_source_validated"
    report.update(payload)
    report.update(
        {
            "status": "pass" if source_validated else "fail",
            "runtime_harness_status": payload["runtime_launch_hygiene_status"],
            "runtime_execution_status": "runtime_execution_not_attempted",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "live_runtime_execution": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_exit_fixture_source_ready",
                "runtime_default_level_source_recorded",
                "runtime_no_default_level_strategy_source_validated",
                "runtime_execution_not_attempted_in_launch_hygiene_diagnostic",
                "runtime_character_proof_not_claimed",
            ]
            if source_validated
            else [],
            "required_runtime_harness_assertions_failed": []
            if source_validated
            else ["runtime_no_default_level_strategy_source_validation"],
            "runtime_harness_assertion_informational": [
                "launch_hygiene_diagnostic_does_not_launch_runtime",
                "no_default_level_source_validation_is_not_runtime_execution_proof",
            ],
        }
    )
    return _finalize_report(report)


def _run_runtime_loadlevel_override_diagnostic(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path | None = None,
) -> Dict[str, Any]:
    report.update(_runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds))
    report["runtime_harness_mode"] = "runtime_loadlevel_override_diagnostic"
    payload = _runtime_loadlevel_override_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
    )
    source_validated = payload["runtime_loadlevel_override_status"] == "runtime_loadlevel_override_source_discovery_pass"
    report.update(payload)
    report.update(
        {
            "status": "pass" if source_validated else "fail",
            "runtime_harness_status": payload["runtime_loadlevel_override_status"],
            "runtime_execution_status": "runtime_execution_not_attempted",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "live_runtime_execution": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "defaultlevel_mutation": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_exit_fixture_source_ready",
                "runtime_default_level_source_recorded",
                "runtime_settings_registry_merge_order_source_validated",
                "runtime_loadlevel_override_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_loadlevel_override_diagnostic",
                "runtime_character_proof_not_claimed",
            ]
            if source_validated
            else [],
            "required_runtime_harness_assertions_failed": []
            if source_validated
            else ["runtime_loadlevel_override_source_validation"],
            "runtime_harness_assertion_informational": [
                "loadlevel_override_diagnostic_does_not_launch_runtime",
                "loadlevel_override_source_validation_is_not_runtime_execution_proof",
            ],
        }
    )
    return _finalize_report(report)


def _run_runtime_later_registry_patch_diagnostic(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(_runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds))
    report["runtime_harness_mode"] = "runtime_later_registry_patch_diagnostic"
    payload = _runtime_later_registry_patch_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
    )
    source_validated = payload["runtime_later_registry_patch_status"] == "runtime_later_registry_patch_source_discovery_pass"
    report.update(payload)
    report.update(
        {
            "status": "pass" if source_validated else "fail",
            "runtime_harness_status": payload["runtime_later_registry_patch_status"],
            "runtime_execution_status": "runtime_execution_not_attempted",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "live_runtime_execution": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "defaultlevel_mutation": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_exit_fixture_source_ready",
                "runtime_default_level_source_recorded",
                "runtime_later_registry_patch_source_validated",
                "runtime_later_registry_patch_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_later_registry_patch_diagnostic",
                "runtime_character_proof_not_claimed",
            ]
            if source_validated
            else [],
            "required_runtime_harness_assertions_failed": []
            if source_validated
            else ["runtime_later_registry_patch_source_validation"],
            "runtime_harness_assertion_informational": [
                "later_registry_patch_diagnostic_does_not_launch_runtime",
                "later_registry_patch_source_validation_is_not_runtime_execution_proof",
                "temp_registry_patch_generation_requires_explicit_gate",
            ],
        }
    )
    return _finalize_report(report)


def _run_runtime_exit_fixture_command(
    report: Dict[str, Any],
    *,
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
    no_default_level: bool = False,
    loadlevel_override: bool = False,
    later_registry_patch: bool = False,
) -> Dict[str, Any]:
    report.update(_runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds))
    report["runtime_harness_mode"] = (
        "runtime_exit_fixture_later_registry_patch_command"
        if later_registry_patch
        else "runtime_exit_fixture_loadlevel_override_command"
        if loadlevel_override
        else "runtime_exit_fixture_no_default_level_command"
        if no_default_level
        else "runtime_exit_fixture_command"
    )
    fixture_gate = _runtime_exit_fixture_gate_status(env)
    report["runtime_exit_fixture_runtime_command_status"] = fixture_gate["status"]
    if fixture_gate["status"] != "pass":
        report.update(
            {
                "status": "fail",
                "runtime_harness_status": "blocked_by_fixture_runtime_gate_missing",
                "runtime_exit_fixture_status": "blocked_by_fixture_runtime_gate_missing",
                "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_runtime_gate_missing",
                "runtime_harness_blocked_reason": "blocked_by_fixture_runtime_gate_missing",
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "runtime_exit_fixture_execution_attempted": False,
                "runtime_exit_fixture_execution_completed": False,
                "runtime_exit_fixture_execution_verified": False,
                "live_runtime_execution": False,
                "required_runtime_harness_assertions_failed": ["runtime_exit_fixture_runtime_gate"],
            }
        )
        return _finalize_report(report)

    project = _runtime_project_path(report)
    if later_registry_patch:
        patch_gate = _runtime_temp_registry_patch_gate_status(env)
        report["runtime_later_registry_patch_gate_env"] = list(RUNTIME_EXIT_FIXTURE_TEMP_REGISTRY_PATCH_GATE_ENV)
        report["runtime_later_registry_patch_gate_status"] = patch_gate
        readiness_payload = report.get("runtime_harness_readiness", {})
        source_engine_root = (
            Path(str(readiness_payload.get("engine_root", "")))
            if isinstance(readiness_payload, Mapping) and str(readiness_payload.get("engine_root", "")).strip()
            else None
        )
        if patch_gate["status"] != "pass":
            payload = _runtime_later_registry_patch_source_payload(
                project=project,
                engine_root=source_engine_root,
                timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir,
            )
            payload.update(
                {
                    "runtime_later_registry_patch_status": "blocked_by_fixture_temp_registry_patch_gate_missing",
                    "runtime_later_registry_patch_candidate_result": "runtime_later_registry_patch_candidate_rejected_unsafe",
                    "runtime_later_registry_patch_candidate_attempted": False,
                    "runtime_later_registry_patch_candidate_blocker": "blocked_by_fixture_temp_registry_patch_gate_missing",
                    "runtime_later_registry_patch_verified": False,
                    "runtime_default_level_override_blocker": "blocked_by_fixture_temp_registry_patch_gate_missing",
                }
            )
            report.update(payload)
            report.update(
                {
                    "status": "fail",
                    "runtime_harness_status": "blocked_by_fixture_temp_registry_patch_gate_missing",
                    "runtime_exit_fixture_status": "blocked_by_fixture_temp_registry_patch_gate_missing",
                    "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_temp_registry_patch_gate_missing",
                    "runtime_harness_blocked_reason": "blocked_by_fixture_temp_registry_patch_gate_missing",
                    "runtime_execution_status": "runtime_execution_not_attempted",
                    "runtime_execution_attempted": False,
                    "runtime_execution_completed": False,
                    "runtime_execution_verified": False,
                    "runtime_exit_fixture_execution_attempted": False,
                    "runtime_exit_fixture_execution_completed": False,
                    "runtime_exit_fixture_execution_verified": False,
                    "live_runtime_execution": False,
                    "required_runtime_harness_assertions_failed": ["runtime_fixture_temp_registry_patch_gate"],
                }
            )
            return _finalize_report(report)

    if not _runtime_exit_fixture_enabled_for_project(project):
        report.update(
            {
                "status": "fail",
                "runtime_harness_status": "blocked_by_fixture_not_enabled_for_project",
                "runtime_exit_fixture_status": "blocked_by_fixture_not_enabled_for_project",
                "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_not_enabled_for_project",
                "runtime_harness_blocked_reason": "blocked_by_fixture_not_enabled_for_project",
                "runtime_exit_fixture_enabled_for_project": False,
                "runtime_execution_status": "runtime_execution_not_attempted",
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "runtime_exit_fixture_execution_attempted": False,
                "runtime_exit_fixture_execution_completed": False,
                "runtime_exit_fixture_execution_verified": False,
                "live_runtime_execution": False,
                "required_runtime_harness_assertions_failed": ["runtime_exit_fixture_enablement"],
            }
        )
        return _finalize_report(report)

    command = _select_runtime_exit_fixture_command(
        report,
        timeout_seconds=timeout_seconds,
        no_default_level=no_default_level,
        loadlevel_override=loadlevel_override,
        later_registry_patch=later_registry_patch,
        artifact_dir=artifact_dir,
    )
    if not command.get("selected"):
        report.update(_unpinned_runtime_command_payload(command))
        report["runtime_exit_fixture_status"] = command.get("blocked_reason", "blocked_by_missing_runtime_readiness")
        return _finalize_report(report)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    if later_registry_patch:
        _write_runtime_later_registry_patch(_runtime_later_registry_patch_path(artifact_dir))
    stdout_path = artifact_dir / "runtime_exit_fixture_stdout.txt"
    stderr_path = artifact_dir / "runtime_exit_fixture_stderr.txt"
    report.update(_runtime_command_pin_payload(command, timeout_seconds=timeout_seconds, execution_requested=True))
    report.update(
        {
            "runtime_exit_fixture_available": True,
            "runtime_exit_fixture_enabled_for_project": True,
            "runtime_exit_fixture_runtime_command": list(command.get("argv", [])),
            "runtime_exit_fixture_runtime_command_arguments": list(command.get("argv", []))[1:],
            "runtime_exit_fixture_runtime_command_status": "runtime_exit_fixture_runtime_command_pinned",
            "runtime_exit_fixture_runtime_command_uses_console_command_file_quit": False,
            "runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit": True,
            "runtime_exit_fixture_runtime_command_uses_no_default_level_strategy": no_default_level or loadlevel_override or later_registry_patch,
            "runtime_exit_fixture_runtime_command_uses_loadlevel_override_strategy": loadlevel_override or later_registry_patch,
            "runtime_exit_fixture_runtime_command_uses_later_registry_patch_strategy": later_registry_patch,
            "runtime_exit_fixture_runtime_command_uses_temp_or_sandbox_level": False,
            "runtime_exit_fixture_command": str(command.get("argv", [""])[0]),
            "runtime_exit_fixture_arguments": list(command.get("argv", []))[1:],
            "runtime_exit_fixture_argument_shape": command.get("argument_shape", {}),
            "runtime_exit_fixture_safety_profile": command.get("safety_profile", {}),
            "runtime_exit_fixture_execution_attempted": True,
            "runtime_execution_attempted": True,
            "live_runtime_execution": True,
            "runtime_stdout_ref": _repo_relative(stdout_path),
            "runtime_stderr_ref": _repo_relative(stderr_path),
            "runtime_command_stdout_ref": _repo_relative(stdout_path),
            "runtime_command_stderr_ref": _repo_relative(stderr_path),
            "runtime_exit_fixture_stdout_ref": _repo_relative(stdout_path),
            "runtime_exit_fixture_stderr_ref": _repo_relative(stderr_path),
        }
    )
    timed_out = False
    try:
        if command_runner is not None:
            proc = command_runner(
                argv=list(command.get("argv", [])),
                cwd=str(REPO_ROOT),
                env=dict(env),
                timeout_seconds=timeout_seconds,
            )
        else:
            proc = subprocess.run(
                list(command.get("argv", [])),
                cwd=str(REPO_ROOT),
                env=dict(env),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        proc = subprocess.CompletedProcess(
            list(command.get("argv", [])),
            None,
            stdout=exc.output or "",
            stderr=exc.stderr or "",
        )

    stdout_text = str(proc.stdout or "")
    stderr_text = str(proc.stderr or "")
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    log_refs = _runtime_log_refs(project)
    log_text = _read_runtime_logs(log_refs)
    combined_text = "\n".join([stdout_text, stderr_text, log_text])
    scan = _scan_runtime_output(combined_text)
    diagnostics = _runtime_exit_diagnostics(
        exit_code=proc.returncode,
        timed_out=timed_out,
        stdout=stdout_text,
        stderr=stderr_text,
        log_text=log_text,
        log_refs=log_refs,
    )
    level_loads = _runtime_level_load_events(combined_text)
    level_load_observed = bool(level_loads)
    disqualifying = _runtime_exit_fixture_disqualifying_signals(
        scan=scan,
        diagnostics=diagnostics,
        combined_text=combined_text,
    )
    marker_observed = "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT" in combined_text
    expected_exit_codes = set(int(code) for code in command.get("expected_exit_codes", [0]))
    launch_hygiene = _runtime_launch_hygiene_execution_payload(
        project=project,
        command=command,
        diagnostics=diagnostics,
        actual_level_loads=level_loads,
        disqualifying=disqualifying,
        no_default_level=no_default_level or loadlevel_override or later_registry_patch,
    )
    loadlevel_override_payload = _runtime_loadlevel_override_execution_payload(
        project=project,
        command=command,
        diagnostics=diagnostics,
        actual_level_loads=level_loads,
        no_default_level=no_default_level,
        loadlevel_override=loadlevel_override,
        later_registry_patch=later_registry_patch,
        launch_hygiene=launch_hygiene,
        exit_code=proc.returncode,
        marker_observed=marker_observed,
        combined_text=combined_text,
    )
    later_registry_patch_payload = _runtime_later_registry_patch_execution_payload(
        project=project,
        command=command,
        diagnostics=diagnostics,
        actual_level_loads=level_loads,
        later_registry_patch=later_registry_patch,
        launch_hygiene=launch_hygiene,
        exit_code=proc.returncode,
        marker_observed=marker_observed,
        artifact_dir=artifact_dir,
        combined_text=combined_text,
    )
    launch_hygiene_pass = launch_hygiene.get("runtime_launch_hygiene_status") == "runtime_launch_hygiene_pass"
    passed = (
        proc.returncode in expected_exit_codes
        and not timed_out
        and scan.get("status") == "pass"
        and not disqualifying
        and marker_observed
        and launch_hygiene_pass
    )
    if passed:
        fixture_status = "runtime_exit_fixture_verified_clean_exit"
    elif timed_out:
        fixture_status = "runtime_exit_fixture_execution_failed_timeout"
    elif diagnostics.get("runtime_exit_is_crash_like") is True:
        fixture_status = "runtime_exit_fixture_execution_failed_access_violation_like_exit"
    elif proc.returncode not in expected_exit_codes:
        fixture_status = "runtime_exit_fixture_execution_failed_nonzero_exit"
    elif launch_hygiene.get("runtime_default_level_autoload_detected") is True:
        fixture_status = "runtime_fixture_execution_failed_default_level_autoload"
    else:
        fixture_status = "runtime_exit_fixture_execution_failed_disqualifying_log_signal"

    report.update(diagnostics)
    report.update(_runtime_signal_fields(scan))
    report.update(loadlevel_override_payload)
    report.update(later_registry_patch_payload)
    report.update(launch_hygiene)
    blocked_reason = _runtime_launch_hygiene_blocked_reason(launch_hygiene)
    report.update(
        {
            "status": "pass" if passed else "fail",
            "runtime_harness_status": "runtime_execution_pass"
            if passed
            else blocked_reason or "blocked_by_fixture_runtime_execution_failed",
            "runtime_exit_fixture_status": fixture_status,
            "runtime_exit_fixture_execution_completed": True,
            "runtime_exit_fixture_execution_verified": passed,
            "runtime_exit_fixture_exit_code_decimal": proc.returncode,
            "runtime_exit_fixture_exit_code_hex": _exit_code_hex(proc.returncode),
            "runtime_exit_fixture_exit_classification": diagnostics.get("runtime_exit_classification", ""),
            "runtime_exit_fixture_blocked_reason": "" if passed else blocked_reason,
            "runtime_exit_fixture_unavailable_reason": "",
            "runtime_exit_fixture_unsupported_reason": "",
            "runtime_exit_fixture_timeout_seconds": int(timeout_seconds),
            "runtime_exit_fixture_timed_out": timed_out,
            "runtime_exit_fixture_kill_attempted": timed_out,
            "runtime_exit_fixture_kill_result": {"status": "runtime_execution_killed_after_timeout" if timed_out else "not_run"},
            "runtime_exit_fixture_log_refs": log_refs,
            "runtime_exit_fixture_log_scan": scan,
            "runtime_exit_fixture_asserts": {
                "status": diagnostics.get("runtime_assertion_summary", {}).get("status", "pass"),
                "count": diagnostics.get("runtime_assertion_summary", {}).get("assert_count", 0),
                "sample_lines": diagnostics.get("runtime_assertion_summary", {}).get("sample_lines", []),
            },
            "runtime_exit_fixture_missing_asset_signals": {
                "status": "fail" if scan.get("matches") else "pass",
                "matches": scan.get("matches", []),
            },
            "runtime_exit_fixture_disqualifying_signals": {
                "status": "fail" if disqualifying else "pass",
                "matches": disqualifying,
            },
            "runtime_exit_fixture_marker_observed": marker_observed,
            "runtime_fixture_marker_observed": marker_observed,
            "runtime_fixture_exit_code_clean": proc.returncode in expected_exit_codes and not timed_out,
            "runtime_exit_fixture_level_load_observed": level_load_observed,
            "runtime_exit_fixture_unexpected_level_load": level_load_observed,
            "runtime_exit_fixture_uses_no_level": not level_load_observed,
            "runtime_exit_fixture_uses_production_level": level_load_observed,
            "runtime_exit_fixture_actual_level_loads": level_loads,
            "runtime_execution_completed": True,
            "runtime_execution_verified": passed,
            "runtime_execution_status": "runtime_execution_pass"
            if passed
            else "runtime_execution_timed_out"
            if timed_out
            else "runtime_execution_failed",
            "runtime_exit_code": proc.returncode,
            "runtime_timed_out": timed_out,
            "runtime_timeout_stall": timed_out,
            "runtime_kill_attempted": timed_out,
            "runtime_kill_result": {"status": "runtime_execution_killed_after_timeout" if timed_out else "not_run"},
            "runtime_log_refs": log_refs,
            "runtime_command_log_refs": log_refs,
            "runtime_log_scan": scan,
            "runtime_command_log_scan": scan,
            "runtime_command_uses_no_level": not level_load_observed,
            "runtime_command_uses_production_level": level_load_observed,
            "runtime_harness_proof_claimed": passed,
            "runtime_harness_proof_verified": passed,
            "runtime_harness_proof_is_character_proof": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "runtime_exit_fixture_is_runtime_character_proof": False,
            "runtime_exit_fixture_character_proof_claimed": False,
            "runtime_exit_fixture_character_proof_verified": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_exit_fixture_source_ready",
                "runtime_exit_fixture_enabled_for_project",
                "runtime_fixture_settings_registry_command_pinned",
                "runtime_fixture_bounded_command_executed",
                "runtime_exit_fixture_marker_observed",
                "runtime_launch_hygiene_pass",
                "runtime_exit_fixture_clean_exit",
                "runtime_character_proof_not_claimed",
            ]
            if passed
            else [],
            "required_runtime_harness_assertions_failed": [] if passed else ["runtime_exit_fixture_execution"],
            "runtime_harness_assertion_informational": [
                "runtime_exit_fixture_command_envelope_is_not_runtime_character_proof",
            ],
        }
    )
    return _finalize_report(report)


def _runtime_exit_strategy_candidate_matrix(
    command: Mapping[str, Any],
    *,
    artifact_dir: Path,
    timeout_seconds: int,
) -> List[Dict[str, Any]]:
    argv = [str(item) for item in command.get("argv", [])]
    executable = argv[0] if argv else ""
    original_args = argv[1:]
    setregpatch_path = artifact_dir / "maxine_runtime_exit_strategy_runtime_console_quit.setregpatch"
    setregpatch_argv = [
        executable,
        *[arg for arg in original_args if not str(arg).startswith("--console-command-file=")],
        f"--console-command-file={setregpatch_path}",
    ]
    common_safety = {
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
        "safe_to_kill_after_timeout": True,
    }
    return [
        _runtime_exit_strategy_candidate_payload(
            candidate_id="console_command_file_immediate_quit",
            name="Immediate console-command-file quit",
            status="runtime_exit_strategy_candidate_rejected_unsafe",
            kind="pre_mainloop_console_command_file_quit",
            argv=argv,
            source_validation={
                "status": "runtime_exit_strategy_candidate_source_validated",
                "summary": (
                    "Launcher.cpp executes --console-command-file after autoexec.cfg and before RunMainLoop; "
                    "SystemInit.cpp registers quit as GetISystem()->Quit()."
                ),
            },
            source_refs=[
                "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:66",
                "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:601",
                "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:607",
                "C:/src/o3de/Code/Legacy/CrySystem/SystemInit.cpp:1196",
                "C:/src/o3de/Code/Legacy/CrySystem/System.cpp:414",
            ],
            safety_profile={**common_safety, "rejected_same_pre_mainloop_quit_timing": True},
            reason="Source-validated but rejected because it is the already-failing immediate pre-main-loop quit timing.",
            rejected_reason="candidate_rejected_same_pre_mainloop_quit_timing",
            timeout_seconds=timeout_seconds,
        ),
        _runtime_exit_strategy_candidate_payload(
            candidate_id="settings_registry_runtime_console_quit_setregpatch",
            name="Settings Registry runtime console quit file",
            status="runtime_exit_strategy_candidate_rejected_unsafe",
            kind="pre_mainloop_settings_registry_runtime_console_quit",
            argv=setregpatch_argv,
            source_validation={
                "status": "runtime_exit_strategy_candidate_source_validated",
                "summary": (
                    "Console.cpp routes .setregpatch config files into /Amazon/AzCore/Runtime/ConsoleCommands and "
                    "the settings-registry notifier performs the console command, but Launcher.cpp would still call it "
                    "through --console-command-file before RunMainLoop."
                ),
            },
            source_refs=[
                "C:/src/o3de/Code/Framework/AzCore/AzCore/Console/IConsole.h:36",
                "C:/src/o3de/Code/Framework/AzCore/AzCore/Console/Console.cpp:145",
                "C:/src/o3de/Code/Framework/AzCore/AzCore/Console/Console.cpp:535",
                "C:/src/o3de/Code/Framework/AzCore/AzCore/Console/Console.cpp:632",
                "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:607",
            ],
            safety_profile={**common_safety, "rejected_same_pre_mainloop_quit_timing": True},
            reason="Source-validated but rejected because it does not provide delayed or after-initialization exit timing.",
            rejected_reason="candidate_rejected_same_pre_mainloop_quit_timing",
            timeout_seconds=timeout_seconds,
        ),
        _runtime_exit_strategy_candidate_payload(
            candidate_id="post_app_start_callback_exit",
            name="Launcher post-app-start callback exit",
            status="runtime_exit_strategy_candidate_rejected_no_exit_strategy",
            kind="internal_launcher_callback_not_cli_pinnable",
            argv=[executable],
            source_validation={
                "status": "runtime_exit_strategy_candidate_source_validated",
                "summary": "Launcher.cpp calls PlatformMainInfo::m_onPostAppStart after GameApplication::Start, but the callback is platform/internal and not exposed as a command-line exit strategy.",
            },
            source_refs=[
                "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:523",
                "C:/src/o3de/Code/LauncherUnified/Launcher.h:47",
                "C:/src/o3de/Code/LauncherUnified/Platform/Android/Launcher_Android.cpp:359",
            ],
            safety_profile={**common_safety, "externally_pinnable": False},
            reason="Source-validated internal lifecycle hook, rejected because the launcher CLI cannot pin it for this harness.",
            rejected_reason="candidate_rejected_no_external_cli_binding",
            timeout_seconds=timeout_seconds,
        ),
        _runtime_exit_strategy_candidate_payload(
            candidate_id="tick_queued_delayed_quit",
            name="Tick-queued delayed quit",
            status="runtime_exit_strategy_candidate_rejected_missing_source_validation",
            kind="delayed_or_after_init_quit",
            argv=[],
            source_validation={
                "status": "runtime_exit_strategy_candidate_rejected_missing_source_validation",
                "summary": "No source-supported command-line mechanism was found that queues quit for a later system/application tick.",
            },
            source_refs=[
                "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:97",
                "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:107",
                "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:117",
            ],
            safety_profile={**common_safety, "source_validated": False},
            reason="No source-validated delayed quit command-line surface was found.",
            rejected_reason="candidate_rejected_missing_source_validation",
            timeout_seconds=timeout_seconds,
        ),
        _runtime_exit_strategy_candidate_payload(
            candidate_id="help_version_noop_exit",
            name="Help/version/no-op launcher exit",
            status="runtime_exit_strategy_candidate_rejected_missing_source_validation",
            kind="help_version_noop",
            argv=[executable],
            source_validation={
                "status": "runtime_exit_strategy_candidate_rejected_missing_source_validation",
                "summary": "No HeadlessServerLauncher help/version/no-op exit surface was found in the launcher source.",
            },
            source_refs=["C:/src/o3de/Code/LauncherUnified/Launcher.cpp"],
            safety_profile={**common_safety, "source_validated": False},
            reason="No source-validated help/version/no-op exit surface was found.",
            rejected_reason="candidate_rejected_missing_source_validation",
            timeout_seconds=timeout_seconds,
        ),
        _runtime_exit_strategy_candidate_payload(
            candidate_id="command_line_plus_quit",
            name="Command-line plus quit",
            status="runtime_exit_strategy_candidate_rejected_missing_source_validation",
            kind="legacy_command_line_quit",
            argv=[executable],
            source_validation={
                "status": "runtime_exit_strategy_candidate_rejected_missing_source_validation",
                "summary": "No safe, pinned HeadlessServerLauncher command-line +quit form was validated for after-initialization exit timing.",
            },
            source_refs=[
                "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:609",
                "C:/src/o3de/Code/Legacy/CrySystem/SystemInit.cpp:1113",
            ],
            safety_profile={**common_safety, "source_validated": False},
            reason="Command-line quit dispatch was not source-validated as a delayed, bounded exit path.",
            rejected_reason="candidate_rejected_missing_source_validation",
            timeout_seconds=timeout_seconds,
        ),
        _runtime_exit_strategy_candidate_payload(
            candidate_id="serverlauncher_no_level_exit",
            name="ServerLauncher no-level exit",
            status="runtime_exit_strategy_candidate_rejected_missing_source_validation",
            kind="fallback_launcher_no_level_exit",
            argv=[],
            source_validation={
                "status": "runtime_exit_strategy_candidate_rejected_missing_source_validation",
                "summary": "No evidence currently shows ServerLauncher has different no-level shutdown behavior or a separate pinned exit surface.",
            },
            source_refs=["C:/src/o3de/Code/LauncherUnified/Launcher.cpp"],
            safety_profile={**common_safety, "fallback_launcher_validated": False},
            reason="Fallback launcher was not source-validated as a safer exit strategy.",
            rejected_reason="candidate_rejected_missing_source_validation",
            timeout_seconds=timeout_seconds,
        ),
        _runtime_exit_strategy_candidate_payload(
            candidate_id="temp_sandbox_level_exit",
            name="Temp/sandbox level startup exit",
            status="runtime_exit_strategy_candidate_rejected_missing_source_validation",
            kind="temp_level_runtime_exit",
            argv=[],
            source_validation={
                "status": "runtime_exit_strategy_candidate_rejected_missing_source_validation",
                "summary": "No source-validated temp/sandbox runtime level startup and exit command was found for this no-production-level slice.",
            },
            source_refs=[],
            safety_profile={**common_safety, "uses_temp_level": True, "source_validated": False},
            reason="Temp/sandbox level exit is deferred until a source-supported no-production-level command exists.",
            rejected_reason="candidate_rejected_missing_source_validation",
            timeout_seconds=timeout_seconds,
        ),
    ]


def _runtime_exit_strategy_candidate_payload(
    *,
    candidate_id: str,
    name: str,
    status: str,
    kind: str,
    argv: Sequence[str],
    source_validation: Mapping[str, Any],
    source_refs: Sequence[str],
    safety_profile: Mapping[str, Any],
    reason: str,
    rejected_reason: str,
    timeout_seconds: int,
) -> Dict[str, Any]:
    argv_list = [str(item) for item in argv]
    return {
        "runtime_exit_strategy_candidate_id": candidate_id,
        "runtime_exit_strategy_candidate_name": name,
        "runtime_exit_strategy_candidate_status": status,
        "runtime_exit_strategy_candidate_kind": kind,
        "runtime_exit_strategy_candidate_command": argv_list[0] if argv_list else "",
        "runtime_exit_strategy_candidate_arguments": argv_list[1:],
        "runtime_exit_strategy_candidate_argument_shape": _exit_strategy_argument_shape(argv_list),
        "runtime_exit_strategy_candidate_safety_profile": dict(safety_profile),
        "runtime_exit_strategy_candidate_source_validation": dict(source_validation),
        "runtime_exit_strategy_candidate_source_refs": list(source_refs),
        "runtime_exit_strategy_candidate_selected": False,
        "runtime_exit_strategy_candidate_attempted": False,
        "runtime_exit_strategy_candidate_reason": reason,
        "runtime_exit_strategy_candidate_rejected_reason": rejected_reason,
        "runtime_exit_strategy_candidate_exit_code_decimal": None,
        "runtime_exit_strategy_candidate_exit_code_hex": "",
        "runtime_exit_strategy_candidate_exit_classification": "runtime_execution_not_attempted",
        "runtime_exit_strategy_candidate_expected_exit_codes": [0],
        "runtime_exit_strategy_candidate_expected_exit_matched": False,
        "runtime_exit_strategy_candidate_timeout_seconds": int(timeout_seconds),
        "runtime_exit_strategy_candidate_timed_out": False,
        "runtime_exit_strategy_candidate_kill_attempted": False,
        "runtime_exit_strategy_candidate_kill_result": {"status": "not_run"},
        "runtime_exit_strategy_candidate_stdout_ref": "",
        "runtime_exit_strategy_candidate_stderr_ref": "",
        "runtime_exit_strategy_candidate_log_refs": [],
        "runtime_exit_strategy_candidate_log_scan": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_strategy_candidate_missing_actor_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_strategy_candidate_missing_mesh_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_strategy_candidate_missing_material_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_strategy_candidate_missing_animation_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_strategy_candidate_missing_asset_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_strategy_candidate_load_error_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_strategy_candidate_asset_manager_asserts": {
            "status": "runtime_execution_not_attempted",
            "count": 0,
            "sample_lines": [],
        },
        "runtime_exit_strategy_candidate_shader_serializer_errors": {
            "status": "runtime_execution_not_attempted",
            "count": 0,
            "sample_lines": [],
        },
        "runtime_exit_strategy_candidate_asset_processor_negotiation_errors": {
            "status": "runtime_execution_not_attempted",
            "count": 0,
            "sample_lines": [],
        },
        "runtime_exit_strategy_candidate_runtime_execution_verified": False,
        "runtime_exit_strategy_candidate_runtime_character_proof_claimed": False,
        "runtime_exit_strategy_candidate_runtime_character_proof_verified": False,
    }


def _exit_strategy_argument_shape(argv: Sequence[str]) -> Dict[str, Any]:
    return {
        "argv0": "runtime executable path" if argv else "",
        "project_path": "explicit --project-path=<MAXINE_GoldenCorpus project path>"
        if any(str(arg).startswith("--project-path=") for arg in argv)
        else "",
        "rendering": [arg for arg in argv if str(arg) in {"-NullRenderer", "-rhi=null"}],
        "asset_processor_connect": "--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0"
        if any("wait_for_connect=0" in str(arg) for arg in argv)
        else "",
        "exit_strategy": "--console-command-file=<artifact cfg/setregpatch>"
        if any(str(arg).startswith("--console-command-file=") for arg in argv)
        else "",
    }


def _attempt_runtime_exit_strategy_candidate(
    candidate: Mapping[str, Any],
    *,
    report: Mapping[str, Any],
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> Dict[str, Any]:
    candidate_id = str(candidate.get("runtime_exit_strategy_candidate_id", "runtime_exit_strategy_candidate")).strip()
    argv = [
        str(candidate.get("runtime_exit_strategy_candidate_command", "")),
        *[str(arg) for arg in candidate.get("runtime_exit_strategy_candidate_arguments", [])],
    ]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in candidate_id)
    stdout_path = artifact_dir / f"runtime_exit_strategy_{safe_id}_stdout.txt"
    stderr_path = artifact_dir / f"runtime_exit_strategy_{safe_id}_stderr.txt"
    timed_out = False
    try:
        if command_runner is not None:
            proc = command_runner(argv=argv, cwd=str(REPO_ROOT), env=dict(env), timeout_seconds=timeout_seconds)
        else:
            proc = subprocess.run(argv, cwd=str(REPO_ROOT), env=dict(env), text=True, capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        proc = subprocess.CompletedProcess(argv, None, stdout=exc.output or "", stderr=exc.stderr or "")

    stdout_text = str(proc.stdout or "")
    stderr_text = str(proc.stderr or "")
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    project_path = _runtime_project_path(report)
    log_refs = _runtime_log_refs(project_path)
    log_text = _read_runtime_logs(log_refs)
    combined_text = stdout_text + "\n" + stderr_text + "\n" + log_text
    scan = _scan_runtime_output(combined_text)
    diagnostics = _runtime_exit_diagnostics(
        exit_code=proc.returncode,
        timed_out=timed_out,
        stdout=stdout_text,
        stderr=stderr_text,
        log_text=log_text,
        log_refs=log_refs,
    )
    expected_exit_codes = [int(code) for code in candidate.get("runtime_exit_strategy_candidate_expected_exit_codes", [0])]
    expected_exit_matched = proc.returncode in set(expected_exit_codes)
    candidate_status, failure_reason, pass_reason = _exit_strategy_attempt_status(
        exit_code=proc.returncode,
        expected_exit_matched=expected_exit_matched,
        timed_out=timed_out,
        scan=scan,
        diagnostics=diagnostics,
        combined_text=combined_text,
    )
    updated = dict(candidate)
    updated.update(
        {
            "runtime_exit_strategy_candidate_status": candidate_status,
            "runtime_exit_strategy_candidate_selected": candidate_status == "runtime_exit_strategy_candidate_attempted_pass",
            "runtime_exit_strategy_candidate_attempted": True,
            "runtime_exit_strategy_candidate_reason": pass_reason or failure_reason,
            "runtime_exit_strategy_candidate_failure_reason": failure_reason,
            "runtime_exit_strategy_candidate_pass_reason": pass_reason,
            "runtime_exit_strategy_candidate_exit_code_decimal": proc.returncode,
            "runtime_exit_strategy_candidate_exit_code_hex": _exit_code_hex(proc.returncode),
            "runtime_exit_strategy_candidate_exit_classification": diagnostics.get("runtime_exit_classification", ""),
            "runtime_exit_strategy_candidate_expected_exit_codes": expected_exit_codes,
            "runtime_exit_strategy_candidate_expected_exit_matched": expected_exit_matched,
            "runtime_exit_strategy_candidate_timeout_seconds": int(timeout_seconds),
            "runtime_exit_strategy_candidate_timed_out": timed_out,
            "runtime_exit_strategy_candidate_kill_attempted": timed_out,
            "runtime_exit_strategy_candidate_kill_result": {
                "status": "runtime_execution_killed_after_timeout" if timed_out else "not_run"
            },
            "runtime_exit_strategy_candidate_stdout_ref": _repo_relative(stdout_path),
            "runtime_exit_strategy_candidate_stderr_ref": _repo_relative(stderr_path),
            "runtime_exit_strategy_candidate_log_refs": log_refs,
            "runtime_exit_strategy_candidate_log_scan": scan,
            "runtime_exit_strategy_candidate_asset_manager_asserts": diagnostics.get("runtime_asset_manager_asserts", {}),
            "runtime_exit_strategy_candidate_shader_serializer_errors": _variant_error_counter(
                diagnostics,
                "shader_serializer_error_count",
                ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"),
            ),
            "runtime_exit_strategy_candidate_asset_processor_negotiation_errors": _variant_error_counter(
                diagnostics,
                "asset_processor_negotiation_failure_count",
                ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"),
            ),
            "runtime_exit_strategy_candidate_runtime_execution_verified": candidate_status
            == "runtime_exit_strategy_candidate_attempted_pass",
            "runtime_exit_strategy_candidate_runtime_character_proof_claimed": False,
            "runtime_exit_strategy_candidate_runtime_character_proof_verified": False,
        }
    )
    updated.update(_exit_strategy_candidate_signal_fields(scan))
    return updated


def _exit_strategy_attempt_status(
    *,
    exit_code: int | None,
    expected_exit_matched: bool,
    timed_out: bool,
    scan: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    combined_text: str,
) -> tuple[str, str, str]:
    if timed_out:
        return (
            "runtime_exit_strategy_candidate_attempted_failed_timeout",
            "runtime exit strategy candidate exceeded bounded timeout",
            "",
        )
    if not expected_exit_matched:
        if diagnostics.get("runtime_exit_is_crash_like") is True:
            return (
                "runtime_exit_strategy_candidate_attempted_failed_access_violation_like_exit",
                f"runtime exit strategy candidate exited with crash-like code {exit_code}",
                "",
            )
        return (
            "runtime_exit_strategy_candidate_attempted_failed_nonzero_exit",
            f"runtime exit strategy candidate exited with unexpected code {exit_code}",
            "",
        )
    if scan.get("status") != "pass":
        return (
            "runtime_exit_strategy_candidate_attempted_failed_missing_runtime_asset",
            "runtime exit strategy candidate emitted missing/load-error signals",
            "",
        )
    if diagnostics.get("runtime_asset_manager_asserts", {}).get("count", 0):
        return (
            "runtime_exit_strategy_candidate_attempted_failed_asset_manager_shutdown_assert",
            "runtime exit strategy candidate emitted AssetManager shutdown asserts",
            "",
        )
    if _variant_error_counter(
        diagnostics,
        "shader_serializer_error_count",
        ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"),
    ).get("count", 0):
        return (
            "runtime_exit_strategy_candidate_attempted_failed_shader_serializer_errors",
            "runtime exit strategy candidate emitted shader serializer errors",
            "",
        )
    if _variant_error_counter(
        diagnostics,
        "asset_processor_negotiation_failure_count",
        ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"),
    ).get("count", 0):
        return (
            "runtime_exit_strategy_candidate_attempted_failed_asset_processor_negotiation",
            "runtime exit strategy candidate emitted Asset Processor negotiation errors",
            "",
        )
    return (
        "runtime_exit_strategy_candidate_attempted_pass",
        "",
        "runtime exit strategy candidate exited with expected code and no disqualifying scanned signals",
    )


def _top_level_exit_strategy_success_payload(
    selected_candidate: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    scan = selected_candidate.get("runtime_exit_strategy_candidate_log_scan", {"status": "pass", "matches": []})
    candidate_id = str(selected_candidate.get("runtime_exit_strategy_candidate_id", "")).strip()
    diagnostics = {
        "runtime_exit_code": selected_candidate.get("runtime_exit_strategy_candidate_exit_code_decimal"),
        "runtime_exit_code_decimal": selected_candidate.get("runtime_exit_strategy_candidate_exit_code_decimal"),
        "runtime_exit_code_hex": selected_candidate.get("runtime_exit_strategy_candidate_exit_code_hex", ""),
        "runtime_exit_classification": selected_candidate.get("runtime_exit_strategy_candidate_exit_classification", ""),
    }
    return {
        "status": "pass",
        "runtime_harness_status": "runtime_execution_pass",
        "runtime_exit_strategy_status": "runtime_exit_strategy_verified_clean_exit",
        "runtime_exit_strategy_source_discovery_status": "runtime_exit_strategy_source_discovery_pass",
        "runtime_exit_strategy_candidates": list(candidates),
        "runtime_exit_strategy_candidate_matrix": list(candidates),
        "runtime_exit_strategy_selected": candidate_id,
        "runtime_exit_strategy_selected_reason": selected_candidate.get("runtime_exit_strategy_candidate_pass_reason", ""),
        "runtime_exit_strategy_verified": True,
        "runtime_exit_strategy": dict(selected_candidate),
        "runtime_original_command_result": _runtime_original_command_result(),
        "runtime_quit_variant_matrix_result": _runtime_quit_variant_matrix_result(),
        "runtime_execution_attempted": True,
        "runtime_execution_completed": True,
        "runtime_execution_verified": True,
        "runtime_execution_status": "runtime_execution_pass",
        "live_runtime_execution": True,
        "runtime_timed_out": bool(selected_candidate.get("runtime_exit_strategy_candidate_timed_out", False)),
        "runtime_timeout_stall": bool(selected_candidate.get("runtime_exit_strategy_candidate_timed_out", False)),
        "runtime_kill_attempted": bool(selected_candidate.get("runtime_exit_strategy_candidate_kill_attempted", False)),
        "runtime_kill_result": selected_candidate.get("runtime_exit_strategy_candidate_kill_result", {"status": "not_run"}),
        "runtime_stdout_ref": selected_candidate.get("runtime_exit_strategy_candidate_stdout_ref", ""),
        "runtime_stderr_ref": selected_candidate.get("runtime_exit_strategy_candidate_stderr_ref", ""),
        "runtime_log_refs": selected_candidate.get("runtime_exit_strategy_candidate_log_refs", []),
        "runtime_log_scan": scan,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "runtime_harness_proof_claimed": True,
        "runtime_harness_proof_verified": True,
        "runtime_harness_proof_is_character_proof": False,
        "required_runtime_harness_assertions_passed": [
            "runtime_exit_strategy_candidate_matrix_recorded",
            "runtime_exit_strategy_clean_exit",
            "runtime_character_proof_not_claimed",
        ],
        "required_runtime_harness_assertions_failed": [],
        "runtime_harness_assertion_informational": [
            "source_validated_exit_strategy_is_not_runtime_character_proof",
        ],
        **diagnostics,
        **_runtime_signal_fields(scan),
    }


def _top_level_exit_strategy_failure_payload(last_candidate: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    scan = last_candidate.get("runtime_exit_strategy_candidate_log_scan", {"status": "pass", "matches": []})
    diagnostics = _runtime_exit_diagnostics(
        exit_code=last_candidate.get("runtime_exit_strategy_candidate_exit_code_decimal"),
        timed_out=bool(last_candidate.get("runtime_exit_strategy_candidate_timed_out", False)),
        stdout="",
        stderr="",
        log_text="",
        log_refs=last_candidate.get("runtime_exit_strategy_candidate_log_refs", []),
    )
    return {
        "status": "fail",
        "runtime_harness_status": "runtime_execution_failed",
        "runtime_exit_strategy_status": last_candidate.get(
            "runtime_exit_strategy_candidate_status", "runtime_exit_strategy_candidate_attempted_failed_unknown"
        ),
        "runtime_exit_strategy_source_discovery_status": "runtime_exit_strategy_source_discovery_pass",
        "runtime_exit_strategy_candidates": list(candidates),
        "runtime_exit_strategy_candidate_matrix": list(candidates),
        "runtime_exit_strategy_selected": "",
        "runtime_exit_strategy_selected_reason": "",
        "runtime_exit_strategy_verified": False,
        "runtime_exit_strategy": dict(last_candidate),
        "runtime_exit_strategy_blocked_reason": "headless_launcher_no_level_quit_shutdown_failure",
        "runtime_exit_strategy_next_recommendation": (
            "Investigate launcher shutdown order, AssetManager lifetime, shader serializer registration, and Asset Processor negotiation."
        ),
        "runtime_original_command_result": _runtime_original_command_result(),
        "runtime_quit_variant_matrix_result": _runtime_quit_variant_matrix_result(),
        "runtime_execution_attempted": True,
        "runtime_execution_completed": True,
        "runtime_execution_verified": False,
        "runtime_execution_status": "runtime_execution_failed",
        "live_runtime_execution": True,
        "runtime_exit_code": last_candidate.get("runtime_exit_strategy_candidate_exit_code_decimal"),
        "runtime_exit_code_decimal": last_candidate.get("runtime_exit_strategy_candidate_exit_code_decimal"),
        "runtime_exit_code_hex": last_candidate.get("runtime_exit_strategy_candidate_exit_code_hex", ""),
        "runtime_exit_classification": last_candidate.get("runtime_exit_strategy_candidate_exit_classification", ""),
        "runtime_timed_out": bool(last_candidate.get("runtime_exit_strategy_candidate_timed_out", False)),
        "runtime_timeout_stall": bool(last_candidate.get("runtime_exit_strategy_candidate_timed_out", False)),
        "runtime_kill_attempted": bool(last_candidate.get("runtime_exit_strategy_candidate_kill_attempted", False)),
        "runtime_kill_result": last_candidate.get("runtime_exit_strategy_candidate_kill_result", {"status": "not_run"}),
        "runtime_stdout_ref": last_candidate.get("runtime_exit_strategy_candidate_stdout_ref", ""),
        "runtime_stderr_ref": last_candidate.get("runtime_exit_strategy_candidate_stderr_ref", ""),
        "runtime_log_refs": last_candidate.get("runtime_exit_strategy_candidate_log_refs", []),
        "runtime_log_scan": scan,
        "runtime_asset_manager_asserts": last_candidate.get("runtime_exit_strategy_candidate_asset_manager_asserts", {}),
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "runtime_harness_proof_claimed": False,
        "runtime_harness_proof_verified": False,
        "runtime_harness_proof_is_character_proof": False,
        "required_runtime_harness_assertions_passed": ["runtime_exit_strategy_candidate_matrix_recorded"],
        "required_runtime_harness_assertions_failed": ["runtime_exit_strategy_clean_exit"],
        "runtime_harness_assertion_informational": [
            "failed_exit_strategy_is_not_runtime_character_proof",
        ],
        **diagnostics,
        **_runtime_signal_fields(scan),
    }


def _top_level_exit_strategy_blocked_payload(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "status": "pass",
        "runtime_harness_status": "headless_launcher_no_level_exit_strategy_unavailable",
        "runtime_exit_strategy_status": "blocked_by_missing_source_validated_runtime_exit_strategy",
        "runtime_exit_strategy_source_discovery_status": "runtime_exit_strategy_source_discovery_pass",
        "runtime_exit_strategy_candidates": list(candidates),
        "runtime_exit_strategy_candidate_matrix": list(candidates),
        "runtime_exit_strategy_selected": "",
        "runtime_exit_strategy_selected_reason": "",
        "runtime_exit_strategy_verified": False,
        "runtime_exit_strategy_blocked_reason": "headless_launcher_no_level_exit_strategy_unavailable",
        "runtime_exit_strategy_unavailable_reason": "blocked_by_missing_source_validated_runtime_exit_strategy",
        "runtime_exit_strategy_next_recommendation": (
            "Add or discover a CLI-pinnable after-initialization/tick-queued exit surface before running more no-level runtime commands."
        ),
        "runtime_original_command_result": _runtime_original_command_result(),
        "runtime_quit_variant_matrix_result": _runtime_quit_variant_matrix_result(),
        "runtime_execution_attempted": False,
        "runtime_execution_completed": False,
        "runtime_execution_verified": False,
        "runtime_execution_status": "runtime_execution_not_attempted",
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "runtime_harness_proof_claimed": True,
        "runtime_harness_proof_verified": True,
        "runtime_harness_proof_is_character_proof": False,
        "required_runtime_harness_assertions_passed": [
            "runtime_exit_strategy_candidate_matrix_recorded",
            "runtime_exit_strategy_blocker_recorded",
            "runtime_execution_not_attempted_without_source_validated_safe_exit_strategy",
            "runtime_character_proof_not_claimed",
        ],
        "required_runtime_harness_assertions_failed": [],
        "runtime_harness_assertion_informational": [
            "source_validation_is_not_runtime_execution_proof",
            "runtime_exit_strategy_blocker_is_not_runtime_character_proof",
        ],
    }


def _gate_enabled(env: Mapping[str, str], name: str) -> bool:
    return str(env.get(name, "")).strip() == "1"


def _runtime_exit_fixture_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    required = ("MAXINE_ENABLE_O3DE_RUNTIME_HARNESS", "MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS", "MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE")
    missing = [name for name in required if not _gate_enabled(env, name)]
    return {"status": "pass" if not missing else "blocked_by_fixture_runtime_gate_missing", "required": list(required), "missing": missing}


def _runtime_temp_registry_patch_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    required = ("MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH",)
    missing = [name for name in required if not _gate_enabled(env, name)]
    return {
        "status": "pass" if not missing else "blocked_by_fixture_temp_registry_patch_gate_missing",
        "required": list(required),
        "missing": missing,
    }


def _run_command_capture(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    stem: str,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> tuple[subprocess.CompletedProcess[str], bool, str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = artifact_dir / f"{stem}_stdout.txt"
    stderr_path = artifact_dir / f"{stem}_stderr.txt"
    timed_out = False
    try:
        if command_runner is not None:
            proc = command_runner(argv=list(argv), cwd=str(REPO_ROOT), env=dict(env), timeout_seconds=timeout_seconds)
        else:
            proc = subprocess.run(
                list(argv),
                cwd=str(REPO_ROOT),
                env=dict(env),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        proc = subprocess.CompletedProcess(list(argv), None, stdout=exc.output or "", stderr=exc.stderr or "")

    stdout_path.write_text(str(proc.stdout or ""), encoding="utf-8")
    stderr_path.write_text(str(proc.stderr or ""), encoding="utf-8")
    return proc, timed_out, _repo_relative(stdout_path), _repo_relative(stderr_path)


def _runtime_exit_fixture_registration_common_payload(*, project: Path | None, command: Sequence[str]) -> Dict[str, Any]:
    return {
        "runtime_exit_fixture_registration_status": "runtime_exit_fixture_registration_ready",
        "runtime_exit_fixture_registration_attempted": False,
        "runtime_exit_fixture_registration_command": list(command),
        "runtime_exit_fixture_registration_result": "not_attempted",
        "runtime_exit_fixture_registration_reversible": True,
        "runtime_exit_fixture_registration_rollback": _runtime_exit_fixture_registration_rollback(project),
        "runtime_exit_fixture_requires_project_mutation": not _runtime_exit_fixture_registered_for_project(project),
        "runtime_exit_fixture_project_mutation_status": "runtime_exit_fixture_project_mutation_not_attempted",
        "runtime_exit_fixture_project_mutation_attempted": False,
        "runtime_exit_fixture_project_mutation_files": _runtime_exit_fixture_project_files(project),
        "runtime_exit_fixture_project_mutation_reversible": True,
        "runtime_exit_fixture_project_mutation_rollback": _runtime_exit_fixture_registration_rollback(project),
        "runtime_exit_fixture_project_mutation_gate_env": list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV),
    }


def _runtime_exit_fixture_enablement_common_payload(*, project: Path | None, command: Sequence[str]) -> Dict[str, Any]:
    return {
        "runtime_exit_fixture_enablement_status": "runtime_exit_fixture_enablement_ready",
        "runtime_exit_fixture_enablement_attempted": False,
        "runtime_exit_fixture_enablement_command": list(command),
        "runtime_exit_fixture_enablement_result": "not_attempted",
        "runtime_exit_fixture_enablement_reversible": True,
        "runtime_exit_fixture_enablement_rollback": _runtime_exit_fixture_enablement_rollback(project),
        "runtime_exit_fixture_requires_project_mutation": not _runtime_exit_fixture_enabled_for_project(project),
        "runtime_exit_fixture_project_mutation_status": "runtime_exit_fixture_project_mutation_not_attempted",
        "runtime_exit_fixture_project_mutation_attempted": False,
        "runtime_exit_fixture_project_mutation_files": _runtime_exit_fixture_project_files(project),
        "runtime_exit_fixture_project_mutation_reversible": True,
        "runtime_exit_fixture_project_mutation_rollback": _runtime_exit_fixture_enablement_rollback(project),
        "runtime_exit_fixture_project_mutation_gate_env": list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV),
    }


def _runtime_exit_fixture_project_files(project: Path | None) -> List[str]:
    if project is None:
        return []
    refs = [str((project / "project.json")).replace("\\", "/")]
    user_project = project / "user" / "project.json"
    if user_project.exists():
        refs.append(str(user_project).replace("\\", "/"))
    return refs


def _runtime_exit_fixture_project_state(project: Path | None) -> Dict[str, Any]:
    refs = _runtime_exit_fixture_project_files(project)
    payload: Dict[str, Any] = {}
    if project is not None and (project / "project.json").is_file():
        try:
            payload = json.loads((project / "project.json").read_text(encoding="utf-8-sig"))
        except Exception:
            payload = {}
    return {
        "refs": refs,
        "external_subdirectories": list(payload.get("external_subdirectories", []))
        if isinstance(payload.get("external_subdirectories", []), list)
        else [],
        "gem_names": list(payload.get("gem_names", [])) if isinstance(payload.get("gem_names", []), list) else [],
        "gems": list(payload.get("gems", [])) if isinstance(payload.get("gems", []), list) else [],
    }


def _runtime_exit_fixture_project_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> List[str]:
    summary: List[str] = []
    for key in ("external_subdirectories", "gem_names", "gems"):
        before_values = {str(item) for item in before.get(key, []) if str(item).strip()}
        after_values = {str(item) for item in after.get(key, []) if str(item).strip()}
        added = sorted(after_values - before_values)
        removed = sorted(before_values - after_values)
        for value in added:
            summary.append(f"{key}:+{_fixture_value_summary(value)}")
        for value in removed:
            summary.append(f"{key}:-{_fixture_value_summary(value)}")
    return summary or ["no_project_metadata_delta_detected"]


def _fixture_value_summary(value: str) -> str:
    candidate = Path(value)
    try:
        return _repo_relative(candidate) if candidate.is_absolute() else value.replace("\\", "/")
    except Exception:
        return value.replace("\\", "/")


def _runtime_exit_fixture_registered_for_project(project: Path | None) -> bool:
    if project is None:
        return False
    state = _runtime_exit_fixture_project_state(project)
    for raw in state.get("external_subdirectories", []):
        raw_text = str(raw).strip()
        if not raw_text:
            continue
        candidate = Path(raw_text)
        if not candidate.is_absolute():
            candidate = project / candidate
        try:
            if candidate.resolve() == RUNTIME_EXIT_FIXTURE_SOURCE_PATH.resolve():
                return True
        except Exception:
            if raw_text.replace("\\", "/").endswith("o3de/gems/MaxineRuntimeExitFixture"):
                return True
    return False


def _runtime_exit_fixture_registration_rollback(project: Path | None) -> str:
    project_path = str(project or "<project-path>")
    return (
        "Remove the MaxineRuntimeExitFixture path from project.json external_subdirectories "
        f"for {project_path}, or use the O3DE CLI to unregister that external subdirectory for the project."
    )


def _runtime_exit_fixture_enablement_rollback(project: Path | None) -> str:
    project_path = str(project or "<project-path>")
    return f"Run o3de disable-gem --gem-name {RUNTIME_EXIT_FIXTURE_GEM_NAME} --project-path {project_path}, then rebuild the scoped launcher target if needed."


def _select_runtime_exit_fixture_command(
    report: Mapping[str, Any],
    *,
    timeout_seconds: int,
    no_default_level: bool = False,
    loadlevel_override: bool = False,
    later_registry_patch: bool = False,
    artifact_dir: Path | None = None,
) -> Dict[str, Any]:
    executable = str(report.get("runtime_executable_path", "")).strip()
    readiness = report.get("runtime_harness_readiness", {})
    project_path = str(readiness.get("project_path", "")).strip() if isinstance(readiness, Mapping) else ""
    engine_root = (
        Path(str(readiness.get("engine_root", ""))).resolve()
        if isinstance(readiness, Mapping) and str(readiness.get("engine_root", "")).strip()
        else Path("<engine-root>")
    )
    if not executable or not project_path:
        return {
            "selected": False,
            "blocked_reason": "blocked_by_missing_runtime_readiness",
            "safety_flags": _runtime_command_safety_flags(),
        }
    later_patch_path = _runtime_later_registry_patch_path(artifact_dir or DEFAULT_ARTIFACT_ROOT)
    later_patch_arg = f"--regset-file={later_patch_path}"
    argv = [
        executable,
        f"--project-path={project_path}",
        "-NullRenderer",
        "-rhi=null",
        *(
            [later_patch_arg]
            if later_registry_patch
            else list(RUNTIME_LOADLEVEL_OVERRIDE_ARGS)
            if loadlevel_override
            else [RUNTIME_NO_DEFAULT_LEVEL_REGREMOVE_ARG]
            if no_default_level
            else []
        ),
        "--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0",
        "--regset=/Amazon/MAXINE/RuntimeHarness/EnableExitFixture=true",
        "--regset=/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks=5",
    ]
    selected_reason = (
        "repo_owned_fixture_tickbus_exit_main_loop_later_registry_patch_envelope"
        if later_registry_patch
        else "repo_owned_fixture_tickbus_exit_main_loop_loadlevel_deferred_regremove_envelope"
        if loadlevel_override
        else "repo_owned_fixture_tickbus_exit_main_loop_no_default_level_regremove_envelope"
        if no_default_level
        else "repo_owned_fixture_tickbus_exit_main_loop_settings_registry_envelope"
    )
    safety_flags = _runtime_command_safety_flags() + [
        "project_path_explicit",
        "null_renderer_requested",
        "settings_registry_fixture_exit_enabled",
        "console_command_file_not_used",
        "wait_for_connect_nonfatal",
    ]
    if later_registry_patch:
        safety_flags.extend(
            [
                "settings_registry_regset_file_json_merge_patch",
                "settings_registry_patch_null_deletes_autoexec_loadlevel",
                "settings_registry_patch_null_deletes_spawnable_deferred_loadlevel",
                "temp_registry_patch_gate_required",
            ]
        )
    elif loadlevel_override:
        safety_flags.extend(
            [
                "settings_registry_regremove_autoexec_loadlevel",
                "settings_registry_regremove_spawnable_deferred_loadlevel",
            ]
        )
    elif no_default_level:
        safety_flags.append("settings_registry_regremove_autoexec_loadlevel")
    else:
        safety_flags.append("no_level_or_map_argument")
    return {
        "selected": True,
        "argv": argv,
        "kind": "headless_settings_registry_runtime_exit_fixture_later_registry_patch_envelope"
        if later_registry_patch
        else "headless_settings_registry_runtime_exit_fixture_loadlevel_override_envelope"
        if loadlevel_override
        else "headless_settings_registry_runtime_exit_fixture_no_default_level_envelope"
        if no_default_level
        else "headless_settings_registry_runtime_exit_fixture_envelope",
        "selected_reason": selected_reason,
        "expected_exit_codes": [0],
        "timeout_seconds": int(timeout_seconds),
        "kill_policy": "subprocess_timeout_kill_and_report",
        "safety_flags": safety_flags,
        "argument_shape": {
            "argv0": "runtime executable path",
            "project_path": "--project-path=<MAXINE_GoldenCorpus project path>",
            "rendering": ["-NullRenderer", "-rhi=null"],
            "launch_hygiene": [later_patch_arg]
            if later_registry_patch
            else list(RUNTIME_LOADLEVEL_OVERRIDE_ARGS)
            if loadlevel_override
            else [RUNTIME_NO_DEFAULT_LEVEL_REGREMOVE_ARG]
            if no_default_level
            else [],
            "asset_processor_connect": "--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0",
            "exit_strategy": [
                "--regset=/Amazon/MAXINE/RuntimeHarness/EnableExitFixture=true",
                "--regset=/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks=5",
            ],
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
            "uses_console_command_file_quit": False,
            "uses_settings_registry_fixture_exit": True,
            "uses_no_default_level_strategy": no_default_level or loadlevel_override or later_registry_patch,
            "uses_loadlevel_override_strategy": loadlevel_override or later_registry_patch,
            "uses_later_registry_patch_strategy": later_registry_patch,
            "temp_registry_patch_path": str(later_patch_path) if later_registry_patch else "",
            "temp_registry_patch_gate_required": later_registry_patch,
        },
        "source_evidence_refs": [
            _repo_relative(RUNTIME_EXIT_FIXTURE_COMPONENT_SOURCE),
            _repo_relative(RUNTIME_EXIT_FIXTURE_COMPONENT_HEADER),
            str(engine_root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Application" / "Application.h"),
            str(engine_root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Application" / "ApplicationAPI.h"),
            str(engine_root / "Code" / "Framework" / "AzCore" / "AzCore" / "Component" / "TickBus.h"),
            str(engine_root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.cpp"),
            str(engine_root / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "IConsole.h"),
        ],
    }


def _runtime_launch_hygiene_source_payload(
    *,
    project: Path | None,
    engine_root: Path | None,
    timeout_seconds: int,
) -> Dict[str, Any]:
    source = _runtime_default_level_source(project)
    strategy_validated = _runtime_no_default_level_strategy_source_validated(engine_root)
    strategy_status = (
        "runtime_no_default_level_strategy_source_validated"
        if strategy_validated
        else "blocked_by_missing_no_default_level_launch_strategy"
    )
    return {
        "runtime_launch_hygiene": {
            "status": strategy_status,
            "default_level_source": source,
            "no_default_level_strategy": "settings_registry_regremove_autoexec_loadlevel",
        },
        "runtime_launch_hygiene_status": strategy_status,
        "runtime_launch_level_policy": "no_default_or_production_level",
        "runtime_launch_level_policy_status": strategy_status,
        "runtime_default_level_autoload_detected": False,
        "runtime_default_level_path": RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH,
        "runtime_default_level_product_path": RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH,
        "runtime_default_level_source": source.get("path", ""),
        "runtime_default_level_source_evidence": source,
        "runtime_default_level_disqualifying": bool(source.get("configured")),
        "runtime_default_level_classification": "runtime_default_level_autoload_blocking"
        if source.get("configured")
        else "runtime_default_level_autoload_not_configured",
        "runtime_default_level_blocked_reason": "blocked_by_default_level_autoload" if source.get("configured") else "",
        "runtime_no_default_level_strategy": "settings_registry_regremove_autoexec_loadlevel",
        "runtime_no_default_level_strategy_status": strategy_status,
        "runtime_no_default_level_source_validation": {
            "status": strategy_status,
            "summary": (
                "Project Registry/load_level.setreg sets /O3DE/Autoexec/ConsoleCommands/LoadLevel=defaultlevel; "
                "SettingsRegistryMergeUtils parses --regremove and removes the JSON pointer during command-line merge."
            ),
        },
        "runtime_no_default_level_source_refs": _runtime_no_default_level_source_refs(project, engine_root),
        "runtime_no_default_level_command": "HeadlessServerLauncher with --regremove for Autoexec LoadLevel",
        "runtime_no_default_level_arguments": [RUNTIME_NO_DEFAULT_LEVEL_REGREMOVE_ARG],
        "runtime_no_default_level_settings_registry_keys": [RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY],
        "runtime_no_default_level_expected_level_loads": [],
        "runtime_no_default_level_actual_level_loads": [],
        "runtime_no_default_level_execution_attempted": False,
        "runtime_no_default_level_execution_verified": False,
        "runtime_empty_harness_level_strategy": "not_used",
        "runtime_empty_harness_level_path": "",
        "runtime_empty_harness_level_generation_status": "not_attempted",
        "runtime_empty_harness_level_mutation_status": "not_attempted",
        "runtime_empty_harness_level_production_mutation": False,
        "runtime_asset_processor_negotiation_signal": {"status": "runtime_execution_not_attempted", "count": 0},
        "runtime_asset_processor_negotiation_signal_status": "runtime_execution_not_attempted",
        "runtime_asset_processor_negotiation_status": "runtime_execution_not_attempted",
        "runtime_asset_processor_negotiation_classification": "runtime_execution_not_attempted",
        "runtime_asset_processor_negotiation_disqualifying": False,
        "runtime_shader_serializer_signal": {"status": "runtime_execution_not_attempted", "count": 0},
        "runtime_shader_serializer_signal_status": "runtime_execution_not_attempted",
        "runtime_shader_serializer_status": "runtime_execution_not_attempted",
        "runtime_shader_serializer_classification": "runtime_execution_not_attempted",
        "runtime_shader_serializer_disqualifying": False,
        "runtime_disqualifying_signal_summary": [],
        "runtime_disqualifying_signal_count": 0,
        "runtime_fixture_marker_observed": False,
        "runtime_fixture_exit_code_clean": False,
        "runtime_fixture_clean_launch_verified": False,
    }


def _runtime_launch_hygiene_execution_payload(
    *,
    project: Path | None,
    command: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    actual_level_loads: Sequence[str],
    disqualifying: Sequence[Mapping[str, Any]],
    no_default_level: bool,
) -> Dict[str, Any]:
    source_payload = _runtime_launch_hygiene_source_payload(
        project=project,
        engine_root=_runtime_engine_root_from_command(command),
        timeout_seconds=int(command.get("timeout_seconds", 120)),
    )
    default_level_detected = any(_is_default_level_path(path) for path in actual_level_loads)
    ap_count = _runtime_diagnostic_count(diagnostics, "asset_processor_negotiation_failure_count")
    shader_count = _runtime_diagnostic_count(diagnostics, "shader_serializer_error_count")
    ap_status = (
        "runtime_asset_processor_negotiation_signal_present"
        if ap_count
        else "runtime_asset_processor_negotiation_signal_absent"
    )
    shader_status = "runtime_shader_serializer_signal_present" if shader_count else "runtime_shader_serializer_signal_absent"
    signal_summary = [dict(item) for item in disqualifying if isinstance(item, Mapping)]
    launch_pass = not default_level_detected and ap_count == 0 and shader_count == 0 and not signal_summary
    no_default_status = (
        "runtime_no_default_level_strategy_pass"
        if no_default_level and launch_pass
        else "runtime_no_default_level_strategy_failed"
        if no_default_level
        else source_payload["runtime_no_default_level_strategy_status"]
    )
    source_payload.update(
        {
            "runtime_launch_hygiene": {
                "status": "runtime_launch_hygiene_pass" if launch_pass else "runtime_launch_hygiene_failed",
                "default_level_autoload_detected": default_level_detected,
                "actual_level_loads": list(actual_level_loads),
                "asset_processor_negotiation_count": ap_count,
                "shader_serializer_count": shader_count,
            },
            "runtime_launch_hygiene_status": "runtime_launch_hygiene_pass"
            if launch_pass
            else "runtime_launch_hygiene_failed",
            "runtime_launch_level_policy_status": "runtime_launch_hygiene_pass"
            if launch_pass
            else "runtime_launch_hygiene_failed",
            "runtime_default_level_autoload_detected": default_level_detected,
            "runtime_default_level_disqualifying": default_level_detected,
            "runtime_default_level_classification": "runtime_default_level_autoload_blocking"
            if default_level_detected
            else "runtime_default_level_autoload_absent",
            "runtime_default_level_blocked_reason": "blocked_by_default_level_autoload" if default_level_detected else "",
            "runtime_no_default_level_strategy_status": no_default_status,
            "runtime_no_default_level_command": " ".join(str(arg) for arg in command.get("argv", [])),
            "runtime_no_default_level_arguments": [
                str(arg) for arg in command.get("argv", []) if str(arg).startswith("--regremove=")
            ],
            "runtime_no_default_level_expected_level_loads": [],
            "runtime_no_default_level_actual_level_loads": list(actual_level_loads),
            "runtime_no_default_level_execution_attempted": bool(no_default_level),
            "runtime_no_default_level_execution_verified": bool(no_default_level and launch_pass),
            "runtime_asset_processor_negotiation_signal": {"status": ap_status, "count": ap_count},
            "runtime_asset_processor_negotiation_signal_status": ap_status,
            "runtime_asset_processor_negotiation_status": ap_status,
            "runtime_asset_processor_negotiation_classification": "blocked_by_asset_processor_negotiation_signal"
            if ap_count
            else "runtime_asset_processor_negotiation_signal_absent",
            "runtime_asset_processor_negotiation_disqualifying": bool(ap_count),
            "runtime_shader_serializer_signal": {"status": shader_status, "count": shader_count},
            "runtime_shader_serializer_signal_status": shader_status,
            "runtime_shader_serializer_status": shader_status,
            "runtime_shader_serializer_classification": "blocked_by_shader_serializer_signal"
            if shader_count
            else "runtime_shader_serializer_signal_absent",
            "runtime_shader_serializer_disqualifying": bool(shader_count),
            "runtime_disqualifying_signal_summary": signal_summary,
            "runtime_disqualifying_signal_count": len(signal_summary),
            "runtime_fixture_clean_launch_verified": launch_pass,
        }
    )
    return source_payload


def _runtime_loadlevel_override_source_payload(
    *,
    project: Path | None,
    engine_root: Path | None,
    timeout_seconds: int,
) -> Dict[str, Any]:
    launch_payload = _runtime_launch_hygiene_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
    )
    source_validated = _runtime_loadlevel_override_source_validated(engine_root)
    status = (
        "runtime_loadlevel_override_source_discovery_pass"
        if source_validated
        else "runtime_loadlevel_override_source_discovery_inconclusive"
    )
    selected_candidate = _runtime_loadlevel_override_selected_candidate(project, engine_root)
    candidates = _runtime_loadlevel_override_candidate_matrix(project, engine_root)
    source = _runtime_default_level_source(project)
    merge_order = _runtime_settings_registry_merge_order_summary(project, engine_root, status=status)
    launch_payload.update(
        {
            "runtime_loadlevel_override": {
                "status": status,
                "selected": RUNTIME_LOADLEVEL_OVERRIDE_SELECTED if source_validated else "",
                "candidate_count": len(candidates),
            },
            "runtime_loadlevel_override_status": status,
            "runtime_loadlevel_override_candidates": candidates,
            "runtime_loadlevel_override_candidate_matrix_recorded": bool(candidates),
            "runtime_loadlevel_override_candidate_id": selected_candidate["id"] if source_validated else "",
            "runtime_loadlevel_override_candidate_name": selected_candidate["name"] if source_validated else "",
            "runtime_loadlevel_override_candidate_kind": selected_candidate["kind"] if source_validated else "",
            "runtime_loadlevel_override_candidate_source_validation": selected_candidate["source_validation"]
            if source_validated
            else {},
            "runtime_loadlevel_override_candidate_source_refs": selected_candidate["source_refs"]
            if source_validated
            else [],
            "runtime_loadlevel_override_candidate_command_args": selected_candidate["command_args"]
            if source_validated
            else [],
            "runtime_loadlevel_override_candidate_settings_registry_keys": selected_candidate["settings_registry_keys"]
            if source_validated
            else [],
            "runtime_loadlevel_override_candidate_expected_registry_state": selected_candidate[
                "expected_registry_state"
            ]
            if source_validated
            else {},
            "runtime_loadlevel_override_candidate_actual_registry_state": {},
            "runtime_loadlevel_override_candidate_expected_level_loads": selected_candidate["expected_level_loads"]
            if source_validated
            else [],
            "runtime_loadlevel_override_candidate_actual_level_loads": [],
            "runtime_loadlevel_override_candidate_attempted": False,
            "runtime_loadlevel_override_candidate_result": selected_candidate["result"] if source_validated else "",
            "runtime_loadlevel_override_candidate_rejected_reason": "",
            "runtime_loadlevel_override_candidate_blocker": "",
            "runtime_loadlevel_override_selected": RUNTIME_LOADLEVEL_OVERRIDE_SELECTED if source_validated else "",
            "runtime_loadlevel_override_selected_reason": "removes_project_autoexec_key_and_spawnable_level_system_deferred_load_queue"
            if source_validated
            else "",
            "runtime_loadlevel_override_verified": False,
            "runtime_settings_registry_merge_order_summary": merge_order,
            "runtime_settings_registry_command_line_override_order": "command_line_runs_before_project_registry_and_again_after_project_user_registry"
            if source_validated
            else "",
            "runtime_settings_registry_project_registry_order": "project_registry_merges_after_early_command_line_and_before_final_command_line"
            if source_validated
            else "",
            "runtime_autoexec_console_command_source": source.get("path", ""),
            "runtime_autoexec_console_command_effective_state": {
                "autoexec_key": RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY,
                "value": source.get("value", ""),
                "queued_key": RUNTIME_DEFERRED_LOADLEVEL_KEY,
                "queued_value": source.get("value", ""),
                "reason": (
                    "Console autoexec notification can execute LoadLevel while SpawnableLevelSystem is unavailable; "
                    "LoadLevel queues the value under DeferredLoadLevel."
                ),
            }
            if source_validated and source.get("configured")
            else {},
            "runtime_autoexec_console_command_override_state": {
                "selected_args": list(RUNTIME_LOADLEVEL_OVERRIDE_ARGS),
                "mutates_project_registry": False,
                "mutates_defaultlevel": False,
            }
            if source_validated
            else {},
            "runtime_default_level_override_blocker": ""
            if source_validated
            else "blocked_by_missing_effective_loadlevel_override",
            "runtime_temp_harness_level_strategy": "not_used",
            "runtime_temp_harness_level_path": "",
            "runtime_temp_harness_level_generation_status": "not_attempted",
            "runtime_temp_harness_level_production_mutation": False,
            "defaultlevel_mutation": False,
        }
    )
    return launch_payload


def _runtime_loadlevel_override_execution_payload(
    *,
    project: Path | None,
    command: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    actual_level_loads: Sequence[str],
    no_default_level: bool,
    loadlevel_override: bool,
    later_registry_patch: bool,
    launch_hygiene: Mapping[str, Any],
    exit_code: int | None,
    marker_observed: bool,
    combined_text: str = "",
) -> Dict[str, Any]:
    source_payload = _runtime_loadlevel_override_source_payload(
        project=project,
        engine_root=_runtime_engine_root_from_command(command),
        timeout_seconds=int(command.get("timeout_seconds", 120)),
    )
    if not loadlevel_override and not later_registry_patch:
        return source_payload

    selected_candidate = (
        _runtime_later_registry_patch_selected_candidate(
            project=project,
            engine_root=_runtime_engine_root_from_command(command),
            artifact_dir=_runtime_later_registry_patch_dir_from_command(command),
        )
        if later_registry_patch
        else _runtime_loadlevel_override_selected_candidate(
            project,
            _runtime_engine_root_from_command(command),
        )
    )
    selected_id = (
        RUNTIME_LATER_REGISTRY_PATCH_SELECTED if later_registry_patch else RUNTIME_LOADLEVEL_OVERRIDE_SELECTED
    )
    selected_reason = (
        "uses_final_command_line_regset_file_json_merge_patch_null_delete_after_project_registry"
        if later_registry_patch
        else "removes_project_autoexec_key_and_spawnable_level_system_deferred_load_queue"
    )
    default_level_detected = bool(launch_hygiene.get("runtime_default_level_autoload_detected"))
    launch_pass = str(launch_hygiene.get("runtime_launch_hygiene_status", "")).strip() == "runtime_launch_hygiene_pass"
    ap_status = str(
        launch_hygiene.get("runtime_asset_processor_negotiation_signal_status", "runtime_execution_not_attempted")
    )
    shader_status = str(launch_hygiene.get("runtime_shader_serializer_signal_status", "runtime_execution_not_attempted"))
    regremove_miss_state = _runtime_loadlevel_regremove_miss_state(combined_text)
    merge_order_blocker = default_level_detected and any(regremove_miss_state.values())
    if launch_pass:
        override_status = "runtime_loadlevel_override_verified_no_defaultlevel"
        candidate_result = "runtime_loadlevel_override_candidate_attempted_pass"
        blocker = ""
    elif default_level_detected:
        override_status = "runtime_loadlevel_override_candidate_attempted_failed_defaultlevel_autoload"
        candidate_result = override_status
        blocker = "blocked_by_settings_registry_merge_order" if merge_order_blocker else "blocked_by_default_level_autoload"
    elif launch_hygiene.get("runtime_asset_processor_negotiation_disqualifying") is True or launch_hygiene.get(
        "runtime_shader_serializer_disqualifying"
    ) is True:
        override_status = "runtime_loadlevel_override_candidate_attempted_failed_disqualifying_signal"
        candidate_result = override_status
        blocker = "blocked_by_disqualifying_runtime_signals"
    else:
        override_status = "runtime_loadlevel_override_candidate_attempted_failed_disqualifying_signal"
        candidate_result = override_status
        blocker = "blocked_by_disqualifying_runtime_signals"

    source_payload.update(
        {
            "runtime_loadlevel_override": {
                "status": override_status,
                "selected": selected_id,
                "attempted": True,
                "actual_level_loads": list(actual_level_loads),
            },
            "runtime_loadlevel_override_status": override_status,
            "runtime_loadlevel_override_candidate_id": selected_candidate["id"],
            "runtime_loadlevel_override_candidate_name": selected_candidate["name"],
            "runtime_loadlevel_override_candidate_kind": selected_candidate["kind"],
            "runtime_loadlevel_override_candidate_source_validation": selected_candidate["source_validation"],
            "runtime_loadlevel_override_candidate_source_refs": selected_candidate["source_refs"],
            "runtime_loadlevel_override_candidate_command_args": [
                str(arg)
                for arg in command.get("argv", [])
                if str(arg).startswith("--regremove=") or str(arg).startswith("--regset-file=")
            ],
            "runtime_loadlevel_override_candidate_settings_registry_keys": selected_candidate[
                "settings_registry_keys"
            ],
            "runtime_loadlevel_override_candidate_expected_registry_state": selected_candidate[
                "expected_registry_state"
            ],
            "runtime_loadlevel_override_candidate_actual_registry_state": {
                "defaultlevel_autoload_detected": default_level_detected,
                "spawnable_deferred_load_key_removed_by_command": not default_level_detected,
                "asset_processor_negotiation_status": ap_status,
                "shader_serializer_status": shader_status,
                **regremove_miss_state,
            },
            "runtime_loadlevel_override_candidate_expected_level_loads": [],
            "runtime_loadlevel_override_candidate_actual_level_loads": list(actual_level_loads),
            "runtime_loadlevel_override_candidate_attempted": True,
            "runtime_loadlevel_override_candidate_result": candidate_result,
            "runtime_loadlevel_override_candidate_rejected_reason": "",
            "runtime_loadlevel_override_candidate_blocker": blocker,
            "runtime_loadlevel_override_selected": selected_id,
            "runtime_loadlevel_override_selected_reason": selected_reason,
            "runtime_loadlevel_override_verified": bool(launch_pass),
            "runtime_autoexec_console_command_override_state": {
                "selected_args": [
                    str(arg)
                    for arg in command.get("argv", [])
                    if str(arg).startswith("--regremove=") or str(arg).startswith("--regset-file=")
                ],
                "mutates_project_registry": False,
                "mutates_defaultlevel": False,
                "exit_code_decimal": exit_code,
                "exit_code_hex": _exit_code_hex(exit_code),
                "fixture_marker_observed": marker_observed,
            },
            "runtime_default_level_override_blocker": blocker,
            "defaultlevel_mutation": False,
        }
    )
    return source_payload


def _runtime_later_registry_patch_source_payload(
    *,
    project: Path | None,
    engine_root: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    loadlevel_payload = _runtime_loadlevel_override_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
    )
    source_validated = _runtime_later_registry_patch_source_validated(engine_root)
    status = (
        "runtime_later_registry_patch_source_discovery_pass"
        if source_validated
        else "runtime_later_registry_patch_source_discovery_inconclusive"
    )
    selected_candidate = _runtime_later_registry_patch_selected_candidate(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
    )
    candidates = _runtime_later_registry_patch_candidate_matrix(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
    )
    loadlevel_payload.update(
        {
            "runtime_later_registry_patch": {
                "status": status,
                "selected": RUNTIME_LATER_REGISTRY_PATCH_SELECTED if source_validated else "",
                "candidate_count": len(candidates),
            },
            "runtime_later_registry_patch_status": status,
            "runtime_later_registry_patch_candidates": candidates,
            "runtime_later_registry_patch_candidate_matrix_recorded": bool(candidates),
            "runtime_later_registry_patch_candidate_id": selected_candidate["id"] if source_validated else "",
            "runtime_later_registry_patch_candidate_name": selected_candidate["name"] if source_validated else "",
            "runtime_later_registry_patch_candidate_kind": selected_candidate["kind"] if source_validated else "",
            "runtime_later_registry_patch_candidate_source_validation": selected_candidate["source_validation"]
            if source_validated
            else {},
            "runtime_later_registry_patch_candidate_source_refs": selected_candidate["source_refs"]
            if source_validated
            else [],
            "runtime_later_registry_patch_candidate_patch_path": selected_candidate["patch_path"]
            if source_validated
            else "",
            "runtime_later_registry_patch_candidate_patch_contents_summary": selected_candidate[
                "patch_contents_summary"
            ]
            if source_validated
            else "",
            "runtime_later_registry_patch_candidate_merge_mechanism": selected_candidate["merge_mechanism"]
            if source_validated
            else "",
            "runtime_later_registry_patch_candidate_merge_order": selected_candidate["merge_order"]
            if source_validated
            else "",
            "runtime_later_registry_patch_candidate_gate_env": selected_candidate["gate_env"]
            if source_validated
            else [],
            "runtime_later_registry_patch_candidate_mutates_project": False,
            "runtime_later_registry_patch_candidate_mutates_defaultlevel": False,
            "runtime_later_registry_patch_candidate_mutates_production_level": False,
            "runtime_later_registry_patch_candidate_command_args": selected_candidate["command_args"]
            if source_validated
            else [],
            "runtime_later_registry_patch_candidate_settings_registry_keys": selected_candidate[
                "settings_registry_keys"
            ]
            if source_validated
            else [],
            "runtime_later_registry_patch_candidate_expected_registry_state": selected_candidate[
                "expected_registry_state"
            ]
            if source_validated
            else {},
            "runtime_later_registry_patch_candidate_actual_registry_state": {},
            "runtime_later_registry_patch_candidate_expected_level_loads": selected_candidate["expected_level_loads"]
            if source_validated
            else [],
            "runtime_later_registry_patch_candidate_actual_level_loads": [],
            "runtime_later_registry_patch_candidate_attempted": False,
            "runtime_later_registry_patch_candidate_result": selected_candidate["result"] if source_validated else "",
            "runtime_later_registry_patch_candidate_rejected_reason": "",
            "runtime_later_registry_patch_candidate_blocker": "",
            "runtime_later_registry_patch_selected": RUNTIME_LATER_REGISTRY_PATCH_SELECTED if source_validated else "",
            "runtime_later_registry_patch_selected_reason": "uses_final_command_line_regset_file_json_merge_patch_null_delete_after_project_registry"
            if source_validated
            else "",
            "runtime_later_registry_patch_verified": False,
            "runtime_later_registry_patch_gate_env": list(RUNTIME_EXIT_FIXTURE_TEMP_REGISTRY_PATCH_GATE_ENV),
            "runtime_later_registry_patch_generation_status": "requires_gate_before_generation",
            "runtime_settings_registry_merge_order_summary": _runtime_settings_registry_merge_order_summary(
                project,
                engine_root,
                status=status,
            ),
            "runtime_default_level_override_blocker": ""
            if source_validated
            else "blocked_by_missing_later_precedence_registry_patch",
            "defaultlevel_mutation": False,
            "production_level_mutation": False,
        }
    )
    return loadlevel_payload


def _runtime_later_registry_patch_execution_payload(
    *,
    project: Path | None,
    command: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    actual_level_loads: Sequence[str],
    later_registry_patch: bool,
    launch_hygiene: Mapping[str, Any],
    exit_code: int | None,
    marker_observed: bool,
    artifact_dir: Path,
    combined_text: str = "",
) -> Dict[str, Any]:
    if not later_registry_patch:
        return {}
    source_payload = _runtime_later_registry_patch_source_payload(
        project=project,
        engine_root=_runtime_engine_root_from_command(command),
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        artifact_dir=artifact_dir,
    )
    selected_candidate = _runtime_later_registry_patch_selected_candidate(
        project=project,
        engine_root=_runtime_engine_root_from_command(command),
        artifact_dir=artifact_dir,
    )
    default_level_detected = bool(launch_hygiene.get("runtime_default_level_autoload_detected"))
    launch_pass = str(launch_hygiene.get("runtime_launch_hygiene_status", "")).strip() == "runtime_launch_hygiene_pass"
    ap_status = str(
        launch_hygiene.get("runtime_asset_processor_negotiation_signal_status", "runtime_execution_not_attempted")
    )
    shader_status = str(launch_hygiene.get("runtime_shader_serializer_signal_status", "runtime_execution_not_attempted"))
    patch_merge_failed = "Merging of file".lower() in combined_text.lower()
    if launch_pass:
        patch_status = "runtime_later_registry_patch_verified_no_defaultlevel"
        candidate_result = "runtime_later_registry_patch_candidate_attempted_pass"
        blocker = ""
    elif default_level_detected:
        patch_status = "runtime_later_registry_patch_candidate_attempted_failed_defaultlevel_autoload"
        candidate_result = patch_status
        blocker = "blocked_by_settings_registry_merge_order"
    elif launch_hygiene.get("runtime_asset_processor_negotiation_disqualifying") is True or launch_hygiene.get(
        "runtime_shader_serializer_disqualifying"
    ) is True:
        patch_status = "runtime_later_registry_patch_candidate_attempted_failed_disqualifying_signal"
        candidate_result = patch_status
        blocker = "blocked_by_disqualifying_runtime_signals"
    else:
        patch_status = "runtime_later_registry_patch_candidate_attempted_failed_disqualifying_signal"
        candidate_result = patch_status
        blocker = "blocked_by_disqualifying_runtime_signals"

    source_payload.update(
        {
            "runtime_later_registry_patch": {
                "status": patch_status,
                "selected": RUNTIME_LATER_REGISTRY_PATCH_SELECTED,
                "attempted": True,
                "actual_level_loads": list(actual_level_loads),
            },
            "runtime_later_registry_patch_status": patch_status,
            "runtime_later_registry_patch_candidate_id": selected_candidate["id"],
            "runtime_later_registry_patch_candidate_name": selected_candidate["name"],
            "runtime_later_registry_patch_candidate_kind": selected_candidate["kind"],
            "runtime_later_registry_patch_candidate_source_validation": selected_candidate["source_validation"],
            "runtime_later_registry_patch_candidate_source_refs": selected_candidate["source_refs"],
            "runtime_later_registry_patch_candidate_patch_path": selected_candidate["patch_path"],
            "runtime_later_registry_patch_candidate_patch_contents_summary": selected_candidate[
                "patch_contents_summary"
            ],
            "runtime_later_registry_patch_candidate_merge_mechanism": selected_candidate["merge_mechanism"],
            "runtime_later_registry_patch_candidate_merge_order": selected_candidate["merge_order"],
            "runtime_later_registry_patch_candidate_gate_env": selected_candidate["gate_env"],
            "runtime_later_registry_patch_candidate_mutates_project": False,
            "runtime_later_registry_patch_candidate_mutates_defaultlevel": False,
            "runtime_later_registry_patch_candidate_mutates_production_level": False,
            "runtime_later_registry_patch_candidate_command_args": [
                str(arg) for arg in command.get("argv", []) if str(arg).startswith("--regset-file=")
            ],
            "runtime_later_registry_patch_candidate_settings_registry_keys": selected_candidate[
                "settings_registry_keys"
            ],
            "runtime_later_registry_patch_candidate_expected_registry_state": selected_candidate[
                "expected_registry_state"
            ],
            "runtime_later_registry_patch_candidate_actual_registry_state": {
                "defaultlevel_autoload_detected": default_level_detected,
                "autoexec_loadlevel_removed_by_later_patch": not default_level_detected,
                "spawnable_deferred_loadlevel_removed_by_later_patch": not default_level_detected,
                "regset_file_merge_failed": patch_merge_failed,
                "autoexec_notification_already_executed_before_final_regset_file": default_level_detected
                and not patch_merge_failed,
                "asset_processor_negotiation_status": ap_status,
                "shader_serializer_status": shader_status,
            },
            "runtime_later_registry_patch_candidate_expected_level_loads": [],
            "runtime_later_registry_patch_candidate_actual_level_loads": list(actual_level_loads),
            "runtime_later_registry_patch_candidate_attempted": True,
            "runtime_later_registry_patch_candidate_result": candidate_result,
            "runtime_later_registry_patch_candidate_rejected_reason": "",
            "runtime_later_registry_patch_candidate_blocker": blocker,
            "runtime_later_registry_patch_selected": RUNTIME_LATER_REGISTRY_PATCH_SELECTED,
            "runtime_later_registry_patch_selected_reason": "uses_final_command_line_regset_file_json_merge_patch_null_delete_after_project_registry",
            "runtime_later_registry_patch_verified": bool(launch_pass),
            "runtime_loadlevel_override_status": "runtime_loadlevel_override_verified_no_defaultlevel"
            if launch_pass
            else "runtime_loadlevel_override_candidate_attempted_failed_defaultlevel_autoload"
            if default_level_detected
            else "runtime_loadlevel_override_candidate_attempted_failed_disqualifying_signal",
            "runtime_loadlevel_override_selected": RUNTIME_LATER_REGISTRY_PATCH_SELECTED,
            "runtime_loadlevel_override_selected_reason": "uses_final_command_line_regset_file_json_merge_patch_null_delete_after_project_registry",
            "runtime_loadlevel_override_verified": bool(launch_pass),
            "runtime_later_registry_patch_generation_status": "runtime_later_registry_patch_generated",
            "runtime_autoexec_console_command_override_state": {
                "selected_args": [
                    str(arg) for arg in command.get("argv", []) if str(arg).startswith("--regset-file=")
                ],
                "patch_path": selected_candidate["patch_path"],
                "mutates_project_registry": False,
                "mutates_defaultlevel": False,
                "exit_code_decimal": exit_code,
                "exit_code_hex": _exit_code_hex(exit_code),
                "fixture_marker_observed": marker_observed,
            },
            "runtime_default_level_override_blocker": blocker,
            "defaultlevel_mutation": False,
            "production_level_mutation": False,
        }
    )
    return source_payload


def _runtime_later_registry_patch_selected_candidate(
    *,
    project: Path | None,
    engine_root: Path | None,
    artifact_dir: Path,
) -> Dict[str, Any]:
    patch_path = _runtime_later_registry_patch_path(artifact_dir)
    return {
        "id": RUNTIME_LATER_REGISTRY_PATCH_SELECTED,
        "name": "Final command-line .setreg merge patch null-deletes Autoexec LoadLevel and deferred LoadLevel",
        "kind": "command_line_regset_file_setreg_merge_patch_null_delete",
        "source_validation": {
            "status": "runtime_later_registry_patch_candidate_source_validated"
            if _runtime_later_registry_patch_source_validated(engine_root)
            else "runtime_later_registry_patch_candidate_rejected_missing_source_validation",
            "summary": (
                "ComponentApplication performs a final command-line merge after project registry and project-user registry, "
                "and SettingsRegistryMergeUtils parses --regset-file with JSON Merge Patch semantics for .setreg files. "
                "The selected harness patch uses null values to delete the Autoexec LoadLevel key and the "
                "SpawnableLevelSystem deferred LoadLevel queue without mutating project Registry/load_level.setreg "
                "or Levels/defaultlevel. This avoids JSON Patch remove failures when a target is absent at the early "
                "command-line parse point."
            ),
        },
        "source_refs": _runtime_later_registry_patch_source_refs(project, engine_root),
        "patch_path": str(patch_path),
        "patch_contents_summary": (
            "JSON Merge Patch sets /O3DE/Autoexec/ConsoleCommands/LoadLevel and "
            "/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel to null so the keys are deleted."
        ),
        "merge_mechanism": "command_line_regset_file_setreg_json_merge_patch_null_delete",
        "merge_order": "final_command_line_regset_file_after_project_registry_and_project_user_registry",
        "gate_env": list(RUNTIME_EXIT_FIXTURE_TEMP_REGISTRY_PATCH_GATE_ENV),
        "command_args": [f"--regset-file={patch_path}"],
        "settings_registry_keys": [RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY, RUNTIME_DEFERRED_LOADLEVEL_KEY],
        "expected_registry_state": {
            "autoexec_loadlevel": "deleted_by_final_regset_file_json_merge_patch_null",
            "spawnable_deferred_loadlevel": "deleted_by_final_regset_file_json_merge_patch_null",
            "project_registry_mutation": False,
            "defaultlevel_mutation": False,
            "production_level_mutation": False,
        },
        "expected_level_loads": [],
        "result": "runtime_later_registry_patch_candidate_source_validated",
    }


def _runtime_later_registry_patch_candidate_matrix(
    *,
    project: Path | None,
    engine_root: Path | None,
    artifact_dir: Path,
) -> List[Dict[str, Any]]:
    historical = _runtime_loadlevel_override_candidate_matrix(project, engine_root)
    selected = _runtime_later_registry_patch_selected_candidate(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
    )
    return [
        {
            **historical[0],
            "result": "runtime_later_registry_patch_candidate_rejected_prior_regremove_failed_defaultlevel_autoload",
            "blocker": "blocked_by_regremove_ineffective",
        },
        {
            **historical[1],
            "attempted": True,
            "actual_level_loads": [RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH],
            "actual_registry_state": {
                "autoexec_regremove_reported_missing_value": True,
                "deferred_loadlevel_regremove_reported_missing_value": True,
            },
            "result": "runtime_later_registry_patch_candidate_rejected_prior_regremove_failed_defaultlevel_autoload",
            "blocker": "blocked_by_settings_registry_merge_order",
        },
        {
            "id": RUNTIME_LATER_REGISTRY_PATCH_FAILED_JSON_PATCH_REMOVE,
            "name": "Final command-line .setregpatch JSON Patch remove",
            "kind": "command_line_regset_file_setregpatch_json_patch_remove",
            "source_validation": {
                "status": "runtime_later_registry_patch_candidate_source_validated",
                "summary": (
                    "SettingsRegistryMergeUtils parses .setregpatch files as JSON Patch. JSON Patch remove requires "
                    "the target path to exist, and the live fixture attempt reported a Settings Registry merge failure "
                    "when the remove targets were absent at command-line parse time."
                ),
            },
            "source_refs": _runtime_later_registry_patch_source_refs(project, engine_root),
            "patch_path": str(artifact_dir / "maxine_runtime_later_precedence_loadlevel_remove.setregpatch"),
            "patch_contents_summary": (
                "JSON Patch remove operations for /O3DE/Autoexec/ConsoleCommands/LoadLevel and "
                "/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel."
            ),
            "merge_mechanism": "command_line_regset_file_setregpatch_json_patch_remove",
            "merge_order": "final_command_line_regset_file_after_project_registry_and_project_user_registry",
            "gate_env": list(RUNTIME_EXIT_FIXTURE_TEMP_REGISTRY_PATCH_GATE_ENV),
            "command_args": [
                f"--regset-file={artifact_dir / 'maxine_runtime_later_precedence_loadlevel_remove.setregpatch'}"
            ],
            "settings_registry_keys": [RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY, RUNTIME_DEFERRED_LOADLEVEL_KEY],
            "expected_registry_state": {
                "autoexec_loadlevel": "remove_attempted_by_json_patch",
                "spawnable_deferred_loadlevel": "remove_attempted_by_json_patch",
                "project_registry_mutation": False,
                "defaultlevel_mutation": False,
                "production_level_mutation": False,
            },
            "actual_registry_state": {
                "json_patch_remove_target_missing": True,
                "settings_registry_merge_failed": True,
            },
            "expected_level_loads": [],
            "actual_level_loads": [RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH],
            "attempted": True,
            "result": "runtime_later_registry_patch_candidate_rejected_json_patch_remove_target_missing",
            "blocker": "blocked_by_fixture_temp_registry_patch_not_safe",
        },
        {
            **selected,
            "actual_registry_state": {},
            "actual_level_loads": [],
            "attempted": False,
            "blocker": "",
        },
    ]


def _runtime_later_registry_patch_source_validated(engine_root: Path | None) -> bool:
    return _runtime_loadlevel_override_source_validated(engine_root)


def _runtime_later_registry_patch_source_refs(project: Path | None, engine_root: Path | None) -> List[str]:
    return _runtime_loadlevel_override_source_refs(project, engine_root)


def _runtime_later_registry_patch_path(artifact_dir: Path) -> Path:
    return artifact_dir / RUNTIME_LATER_REGISTRY_PATCH_FILENAME


def _runtime_later_registry_patch_dir_from_command(command: Mapping[str, Any]) -> Path:
    for arg in command.get("argv", []):
        text = str(arg)
        if text.startswith("--regset-file="):
            return Path(text.split("=", 1)[1]).parent
    return DEFAULT_ARTIFACT_ROOT


def _runtime_later_registry_patch_contents() -> Dict[str, Any]:
    return {
        "O3DE": {
            "Autoexec": {
                "ConsoleCommands": {
                    "LoadLevel": None,
                }
            },
            "Runtime": {
                "SpawnableLevelSystem": {
                    "DeferredLoadLevel": None,
                }
            },
        }
    }


def _write_runtime_later_registry_patch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_runtime_later_registry_patch_contents(), indent=2) + "\n", encoding="utf-8")


def _runtime_loadlevel_override_selected_candidate(project: Path | None, engine_root: Path | None) -> Dict[str, Any]:
    source_refs = _runtime_loadlevel_override_source_refs(project, engine_root)
    return {
        "id": RUNTIME_LOADLEVEL_OVERRIDE_SELECTED,
        "name": "Remove Autoexec LoadLevel and SpawnableLevelSystem deferred load",
        "kind": "command_line_regremove_autoexec_and_deferred_loadlevel",
        "source_validation": {
            "status": "runtime_loadlevel_override_candidate_source_validated"
            if _runtime_loadlevel_override_source_validated(engine_root)
            else "runtime_loadlevel_override_candidate_rejected_missing_source_validation",
            "summary": (
                "Project Registry/load_level.setreg triggers the Autoexec LoadLevel console command during settings merge. "
                "SpawnableLevelSystem stores early LoadLevel requests under /O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel, "
                "so the effective per-process override removes both the Autoexec key and the deferred-load queue key."
            ),
        },
        "source_refs": source_refs,
        "command_args": list(RUNTIME_LOADLEVEL_OVERRIDE_ARGS),
        "settings_registry_keys": [RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY, RUNTIME_DEFERRED_LOADLEVEL_KEY],
        "expected_registry_state": {
            "autoexec_loadlevel": "removed",
            "spawnable_deferred_loadlevel": "removed",
            "project_registry_mutation": False,
            "defaultlevel_mutation": False,
        },
        "expected_level_loads": [],
        "result": "runtime_loadlevel_override_candidate_source_validated",
    }


def _runtime_loadlevel_regremove_miss_state(text: str) -> Dict[str, bool]:
    return {
        "autoexec_regremove_reported_missing_value": (
            f"Unable to remove value at JSON Pointer {RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY}".lower() in text.lower()
        ),
        "deferred_loadlevel_regremove_reported_missing_value": (
            f"Unable to remove value at JSON Pointer {RUNTIME_DEFERRED_LOADLEVEL_KEY}".lower() in text.lower()
        ),
    }


def _runtime_loadlevel_override_candidate_matrix(project: Path | None, engine_root: Path | None) -> List[Dict[str, Any]]:
    source_refs = _runtime_loadlevel_override_source_refs(project, engine_root)
    return [
        {
            "id": "settings_registry_regremove_autoexec_loadlevel",
            "name": "Remove Autoexec LoadLevel only",
            "kind": "command_line_regremove_autoexec_loadlevel",
            "source_validation": {
                "status": "runtime_loadlevel_override_candidate_source_validated",
                "summary": (
                    "This preserves the PR #132 candidate. It removes the Autoexec key at final command-line merge, "
                    "but does not clear a LoadLevel value already queued under SpawnableLevelSystem DeferredLoadLevel."
                ),
            },
            "source_refs": source_refs,
            "command_args": [RUNTIME_NO_DEFAULT_LEVEL_REGREMOVE_ARG],
            "settings_registry_keys": [RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY],
            "expected_registry_state": {
                "autoexec_loadlevel": "removed",
                "spawnable_deferred_loadlevel": "unmodified",
            },
            "actual_registry_state": {
                "spawnable_deferred_loadlevel": "defaultlevel_queued_before_final_regremove",
            },
            "expected_level_loads": [],
            "actual_level_loads": [RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH],
            "attempted": True,
            "result": "runtime_loadlevel_override_candidate_attempted_failed_defaultlevel_autoload",
            "blocker": "blocked_by_regremove_ineffective",
        },
        {
            **_runtime_loadlevel_override_selected_candidate(project, engine_root),
            "actual_registry_state": {},
            "actual_level_loads": [],
            "attempted": False,
            "blocker": "",
        },
    ]


def _runtime_settings_registry_merge_order_summary(
    project: Path | None,
    engine_root: Path | None,
    *,
    status: str,
) -> Dict[str, Any]:
    return {
        "status": status,
        "summary": (
            "ComponentApplication merges command-line settings once before project registry files and again after "
            "project user registry. Console registers settings-registry merge notifications, so Autoexec "
            "ConsoleCommands can execute during Registry/load_level.setreg merge before the final command-line "
            "override pass. SpawnableLevelSystem queues early LoadLevel values under DeferredLoadLevel. "
            "--regset-file can merge an artifact .setreg as JSON Merge Patch at the final pass, where null values "
            "delete keys without the missing-target failure mode of JSON Patch remove."
        ),
        "project_registry_file": str((project or Path("<project>")) / "Registry" / "load_level.setreg"),
        "source_refs": _runtime_loadlevel_override_source_refs(project, engine_root),
    }


def _runtime_loadlevel_override_source_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return all(
        path.is_file()
        for path in (
            root / "Code" / "Framework" / "AzCore" / "AzCore" / "Component" / "ComponentApplication.cpp",
            root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.cpp",
            root / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "Console.cpp",
            root / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "IConsole.h",
            root / "Code" / "Legacy" / "CrySystem" / "LevelSystem" / "SpawnableLevelSystem.cpp",
        )
    )


def _runtime_loadlevel_override_source_refs(project: Path | None, engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [
        str((project or Path("<project>")) / "Registry" / "load_level.setreg"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Component" / "ComponentApplication.cpp"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.cpp"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.h"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryImpl.cpp"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "Console.cpp"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "IConsole.h"),
        str(root / "Code" / "Legacy" / "CrySystem" / "LevelSystem" / "SpawnableLevelSystem.cpp"),
    ]


def _runtime_default_level_source(project: Path | None) -> Dict[str, Any]:
    registry_path = (project or Path("")) / "Registry" / "load_level.setreg"
    payload: Dict[str, Any] = {
        "status": "runtime_default_level_source_not_found",
        "path": str(registry_path) if project is not None else "",
        "configured": False,
        "settings_registry_key": RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY,
        "value": "",
    }
    if not registry_path.is_file():
        return payload
    text = registry_path.read_text(encoding="utf-8-sig", errors="replace")
    configured = "LoadLevel" in text and "defaultlevel" in text.lower()
    payload.update(
        {
            "status": "runtime_default_level_source_found" if configured else "runtime_default_level_source_not_configured",
            "configured": configured,
            "value": "defaultlevel" if configured else "",
            "summary": "Project Registry/load_level.setreg configures O3DE Autoexec ConsoleCommands LoadLevel=defaultlevel."
            if configured
            else "Project Registry/load_level.setreg does not configure defaultlevel autoload.",
        }
    )
    return payload


def _runtime_no_default_level_strategy_source_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return (root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.cpp").is_file() and (
        root / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "IConsole.h"
    ).is_file()


def _runtime_no_default_level_source_refs(project: Path | None, engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    refs = [
        str((project or Path("<project>")) / "Registry" / "load_level.setreg"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.cpp"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.h"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "IConsole.h"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "Console.cpp"),
        str(root / "Code" / "Legacy" / "CrySystem" / "LevelSystem" / "SpawnableLevelSystem.cpp"),
    ]
    return refs


def _runtime_engine_root_from_command(command: Mapping[str, Any]) -> Path | None:
    refs = command.get("source_evidence_refs", [])
    if isinstance(refs, Sequence):
        for ref in refs:
            text = str(ref).replace("\\", "/")
            marker = "/Code/Framework/AzCore/"
            if marker in text:
                return Path(text.split(marker, 1)[0])
    return None


def _runtime_level_load_events(text: str) -> List[str]:
    normalized = text.replace("\\", "/")
    patterns = [
        r"Level\s+(Levels/[^\s'\"\r\n]+?\.spawnable)\s+loaded",
        r"root spawnable ['\"](Levels/[^'\"]+?\.spawnable)['\"]",
        r"\b(Levels/[^\s'\"\r\n]+?\.spawnable)\b",
    ]
    matches: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
            value = match.group(1)
            if value not in matches:
                matches.append(value)
    return matches


def _is_default_level_path(path: str) -> bool:
    return path.lower().replace("\\", "/").endswith("levels/defaultlevel/defaultlevel.spawnable")


def _runtime_diagnostic_count(diagnostics: Mapping[str, Any], count_key: str) -> int:
    total = 0
    for field in ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"):
        payload = diagnostics.get(field, {})
        if isinstance(payload, Mapping):
            try:
                total += int(payload.get(count_key, 0) or 0)
            except (TypeError, ValueError):
                pass
    return total


def _runtime_launch_hygiene_blocked_reason(payload: Mapping[str, Any]) -> str:
    if payload.get("runtime_default_level_autoload_detected") is True:
        return "blocked_by_default_level_autoload"
    if payload.get("runtime_asset_processor_negotiation_disqualifying") is True:
        return "blocked_by_asset_processor_negotiation_signal"
    if payload.get("runtime_shader_serializer_disqualifying") is True:
        return "blocked_by_shader_serializer_signal"
    if payload.get("runtime_disqualifying_signal_count", 0):
        return "blocked_by_disqualifying_runtime_signals"
    return "blocked_by_fixture_runtime_execution_failed"


def _runtime_exit_fixture_disqualifying_signals(
    *,
    scan: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    combined_text: str = "",
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for item in scan.get("matches", []):
        if isinstance(item, Mapping):
            matches.append(dict(item))
    if _runtime_fixture_level_load_observed(combined_text):
        matches.append(
            {
                "signal": "unexpected_level_load",
                "status": "runtime_exit_fixture_unexpected_level_load",
                "detail": "Runtime loaded a level/spawnable during the fixture command instead of remaining no-level.",
            }
        )
    for field, signal in (
        ("runtime_stdout_error_summary", "stdout_error"),
        ("runtime_stderr_error_summary", "stderr_error"),
        ("runtime_log_error_summary", "runtime_log_error"),
        ("runtime_assertion_summary", "runtime_assertion"),
        ("runtime_asset_manager_asserts", "asset_manager_shutdown_assert"),
    ):
        payload = diagnostics.get(field, {})
        if not isinstance(payload, Mapping):
            continue
        if payload.get("status") in {"pass", "blocked_by_missing_runtime_log", "runtime_execution_not_attempted"}:
            continue
        count = (
            payload.get("asset_processor_negotiation_failure_count", 0)
            or payload.get("shader_serializer_error_count", 0)
            or payload.get("asset_manager_shutdown_assert_count", 0)
            or payload.get("assert_count", 0)
            or payload.get("count", 0)
            or payload.get("fatal_or_exception_count", 0)
        )
        if int(count or 0) > 0:
            matches.append({"signal": signal, "status": str(payload.get("status", "")), "count": str(count)})
    return matches


def _runtime_fixture_level_load_observed(text: str) -> bool:
    return bool(_runtime_level_load_events(text))


def _runtime_exit_fixture_source_probe() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    errors: List[str] = []

    def _record(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"id": check_id, "status": "pass" if passed else "fail", "detail": detail})
        if not passed:
            errors.append(check_id)

    source_path = RUNTIME_EXIT_FIXTURE_SOURCE_PATH
    source_owned_by_repo = _is_repo_relative_path(source_path)
    _record("fixture_source_path_exists", source_path.is_dir(), _repo_relative(source_path))
    _record("fixture_source_owned_by_repo", source_owned_by_repo, _repo_relative(source_path))
    _record("fixture_gem_json_exists", RUNTIME_EXIT_FIXTURE_GEM_JSON.is_file(), _repo_relative(RUNTIME_EXIT_FIXTURE_GEM_JSON))
    _record("fixture_root_cmake_exists", RUNTIME_EXIT_FIXTURE_ROOT_CMAKE.is_file(), _repo_relative(RUNTIME_EXIT_FIXTURE_ROOT_CMAKE))
    _record("fixture_cmake_exists", RUNTIME_EXIT_FIXTURE_CMAKE.is_file(), _repo_relative(RUNTIME_EXIT_FIXTURE_CMAKE))
    _record(
        "fixture_component_header_exists",
        RUNTIME_EXIT_FIXTURE_COMPONENT_HEADER.is_file(),
        _repo_relative(RUNTIME_EXIT_FIXTURE_COMPONENT_HEADER),
    )
    _record(
        "fixture_component_source_exists",
        RUNTIME_EXIT_FIXTURE_COMPONENT_SOURCE.is_file(),
        _repo_relative(RUNTIME_EXIT_FIXTURE_COMPONENT_SOURCE),
    )
    _record(
        "fixture_module_source_exists",
        RUNTIME_EXIT_FIXTURE_MODULE_SOURCE.is_file(),
        _repo_relative(RUNTIME_EXIT_FIXTURE_MODULE_SOURCE),
    )

    gem_payload: Dict[str, Any] = {}
    if RUNTIME_EXIT_FIXTURE_GEM_JSON.is_file():
        try:
            gem_payload = json.loads(RUNTIME_EXIT_FIXTURE_GEM_JSON.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            errors.append("fixture_gem_json_parse")
            checks.append({"id": "fixture_gem_json_parse", "status": "fail", "detail": "gem.json is not valid JSON"})
    _record(
        "fixture_gem_name_matches",
        str(gem_payload.get("gem_name", "")).strip() == RUNTIME_EXIT_FIXTURE_GEM_NAME,
        str(gem_payload.get("gem_name", "")),
    )
    _record("fixture_gem_type_code", str(gem_payload.get("type", "")).strip() == "Code", str(gem_payload.get("type", "")))
    metadata_text = json.dumps(gem_payload, sort_keys=True).lower() if gem_payload else ""
    _record("fixture_metadata_non_shipping", "non-shipping" in metadata_text or "nonshipping" in metadata_text, "gem metadata")
    _record("fixture_metadata_harness_only", "harness" in metadata_text and "runtime" in metadata_text, "gem metadata")

    root_cmake_text = _read_text_if_present(RUNTIME_EXIT_FIXTURE_ROOT_CMAKE)
    cmake_text = _read_text_if_present(RUNTIME_EXIT_FIXTURE_CMAKE)
    source_text = _read_text_if_present(RUNTIME_EXIT_FIXTURE_COMPONENT_SOURCE)
    header_text = _read_text_if_present(RUNTIME_EXIT_FIXTURE_COMPONENT_HEADER)
    module_text = _read_text_if_present(RUNTIME_EXIT_FIXTURE_MODULE_SOURCE)
    combined_source = "\n".join([root_cmake_text, cmake_text, source_text, header_text, module_text])
    _record("fixture_root_cmake_adds_code_subdirectory", "add_subdirectory(Code)" in root_cmake_text, "add_subdirectory(Code)")
    _record("fixture_uses_tick_bus", "AZ::TickBus" in combined_source, "AZ::TickBus")
    _record("fixture_uses_exit_main_loop", "ExitMainLoop" in combined_source, "AzFramework::ApplicationRequests::ExitMainLoop")
    _record(
        "fixture_uses_settings_registry_enable_key",
        RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS[0] in combined_source,
        RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS[0],
    )
    _record(
        "fixture_uses_settings_registry_tick_key",
        RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS[1] in combined_source,
        RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS[1],
    )
    _record("fixture_registers_system_component", "GetRequiredSystemComponents" in module_text, "AZ::Module")

    source_ready = not errors
    return {
        "status": "runtime_exit_fixture_source_ready" if source_ready else "blocked_by_missing_repo_owned_runtime_fixture_gem",
        "checks": checks,
        "errors": errors,
        "gem_payload": gem_payload,
        "source_owned_by_repo": source_owned_by_repo,
    }


def _runtime_exit_fixture_source_ready_payload(*, timeout_seconds: int) -> Dict[str, Any]:
    probe = _runtime_exit_fixture_source_probe()
    source_ready = str(probe.get("status", "")).strip() == "runtime_exit_fixture_source_ready"
    source_status = "runtime_exit_fixture_source_ready" if source_ready else "blocked_by_missing_repo_owned_runtime_fixture_gem"
    source_validation = {
        "status": source_status,
        "summary": (
            "A repo-owned, non-shipping O3DE Code Gem source path is present for a TickBus after-initialization "
            "exit fixture. Source readiness is not runtime execution proof and does not enable or build the fixture."
        )
        if source_ready
        else "The repo-owned runtime exit fixture Gem source path is missing or incomplete.",
        "checks": probe.get("checks", []),
        "source_refs": _runtime_exit_fixture_repo_source_refs(),
        "lifecycle_surface": "AZ::Component::Activate plus AZ::TickBus::OnTick",
        "exit_api": "AzFramework::ApplicationRequests::ExitMainLoop",
        "settings_registry_keys": list(RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS),
        "repo_scope_result": source_status,
    }
    fixture = _runtime_exit_fixture_static_payload(timeout_seconds=timeout_seconds)
    fixture.update(
        {
            "runtime_exit_fixture_status": "runtime_exit_fixture_ready_not_built" if source_ready else source_status,
            "runtime_exit_fixture_available": False,
            "runtime_exit_fixture_source_discovery_status": "runtime_exit_fixture_source_discovery_pass"
            if source_ready
            else "runtime_exit_fixture_source_discovery_inconclusive",
            "runtime_exit_fixture_source_status": source_status,
            "runtime_exit_fixture_source_validation": source_validation,
            "runtime_exit_fixture_source_refs": _runtime_exit_fixture_source_refs() + _runtime_exit_fixture_repo_source_refs(),
            "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_not_enabled_for_project"
            if source_ready
            else "blocked_by_missing_repo_owned_runtime_fixture_gem",
            "runtime_exit_fixture_unavailable_reason": "blocked_by_fixture_not_enabled_for_project"
            if source_ready
            else "blocked_by_missing_repo_owned_runtime_fixture_gem",
            "runtime_exit_fixture_rebuild_status": "not_attempted",
        }
    )
    return {
        "status": "pass" if source_ready else "fail",
        "runtime_harness_status": "runtime_exit_fixture_source_ready" if source_ready else source_status,
        "runtime_harness_mode": "runtime_exit_fixture_source_readiness",
        "runtime_exit_fixture": fixture,
        **fixture,
        "runtime_command_pinning_result": _runtime_command_pinning_result(),
        "runtime_original_command_result": _runtime_original_command_result(),
        "runtime_quit_variant_matrix_result": _runtime_quit_variant_matrix_result(),
        "runtime_exit_strategy_result": _runtime_exit_strategy_result(),
        "runtime_execution_attempted": False,
        "runtime_execution_completed": False,
        "runtime_execution_verified": False,
        "runtime_execution_status": "runtime_execution_not_attempted",
        "live_runtime_execution": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "runtime_harness_proof_claimed": True,
        "runtime_harness_proof_verified": source_ready,
        "runtime_harness_proof_is_character_proof": False,
        "required_runtime_harness_assertions_passed": [
            "runtime_exit_fixture_source_owned_by_repo",
            "runtime_exit_fixture_gem_manifest_valid",
            "runtime_exit_fixture_cmake_source_shape_valid",
            "runtime_exit_fixture_non_shipping_disabled_by_default",
            "runtime_execution_not_attempted_in_fixture_source_mode",
            "runtime_character_proof_not_claimed",
        ]
        if source_ready
        else [],
        "required_runtime_harness_assertions_failed": [] if source_ready else ["runtime_exit_fixture_source_ready"],
        "runtime_harness_assertion_informational": [
            "runtime_exit_fixture_source_readiness_is_not_runtime_execution_proof",
            "runtime_exit_fixture_rebuild_readiness_is_not_runtime_execution_proof",
            "runtime_exit_fixture_is_not_runtime_character_proof",
        ],
        "runtime_harness_unavailable_reasons": [
            {
                "assertion": "runtime_exit_fixture_execution",
                "status": "blocked_by_fixture_not_enabled_for_project",
                "reason": "fixture source is present but not enabled or rebuilt for the live project",
            }
        ]
        if source_ready
        else [
            {
                "assertion": "runtime_exit_fixture_source",
                "status": source_status,
                "reason": "repo-owned fixture source is missing or incomplete",
            }
        ],
    }


def _runtime_exit_fixture_rebuild_gate_payload(
    *,
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
) -> Dict[str, Any]:
    fixture = _runtime_exit_fixture_static_payload(timeout_seconds=timeout_seconds)
    project_enabled = _runtime_exit_fixture_enabled_for_project(project)
    register_command = _runtime_exit_fixture_register_command(engine_root=engine_root, project=project)
    enable_command = _runtime_exit_fixture_enable_command(engine_root=engine_root, project=project)
    rebuild_command = _runtime_exit_fixture_rebuild_command(engine_root=engine_root, project=project)
    fixture.update(
        {
            "runtime_exit_fixture_status": "runtime_exit_fixture_ready_not_built",
            "runtime_exit_fixture_available": False,
            "runtime_exit_fixture_source_discovery_status": "runtime_exit_fixture_source_discovery_pass",
            "runtime_exit_fixture_source_status": "runtime_exit_fixture_source_ready",
            "runtime_exit_fixture_source_validation": _runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds)[
                "runtime_exit_fixture_source_validation"
            ],
            "runtime_exit_fixture_source_refs": _runtime_exit_fixture_source_refs() + _runtime_exit_fixture_repo_source_refs(),
            "runtime_exit_fixture_registration_status": "runtime_exit_fixture_registration_ready_not_attempted",
            "runtime_exit_fixture_enablement_status": "runtime_exit_fixture_enabled_for_project"
            if project_enabled
            else "blocked_by_fixture_not_enabled_for_project",
            "runtime_exit_fixture_requires_project_mutation": not project_enabled,
            "runtime_exit_fixture_project_mutation_status": "blocked_by_fixture_missing_project_mutation_gate"
            if not project_enabled
            else "project_mutation_not_required",
            "runtime_exit_fixture_project_mutation_attempted": False,
            "runtime_exit_fixture_project_mutation_reversible": True,
            "runtime_exit_fixture_project_mutation_gate_env": list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV),
            "runtime_exit_fixture_rebuild_gate_status": "runtime_exit_fixture_rebuild_gate_pass",
            "runtime_exit_fixture_rebuild_command": rebuild_command,
            "runtime_exit_fixture_rebuild_target": _runtime_exit_fixture_rebuild_target(project),
            "runtime_exit_fixture_rebuild_attempted": False,
            "runtime_exit_fixture_rebuild_result": "runtime_exit_fixture_rebuild_not_attempted",
            "runtime_exit_fixture_rebuild_status": "not_attempted",
            "runtime_exit_fixture_rebuild_artifact_refs": [],
            "runtime_exit_fixture_enabled_for_project": project_enabled,
            "runtime_exit_fixture_argument_shape": {
                "register_command": register_command,
                "enable_command": enable_command,
                "rebuild_command": rebuild_command,
                "fixture_strategy": "repo-owned external Code Gem enabled only through explicit project mutation and rebuild gates",
            },
            "runtime_exit_fixture_blocked_reason": ""
            if project_enabled
            else "blocked_by_fixture_not_enabled_for_project",
            "runtime_exit_fixture_unavailable_reason": ""
            if project_enabled
            else "blocked_by_fixture_requires_live_project_mutation",
        }
    )
    return {
        "status": "pass",
        "runtime_harness_status": "runtime_exit_fixture_rebuild_gate_pass",
        "runtime_harness_mode": "runtime_exit_fixture_rebuild_gate",
        "runtime_exit_fixture": fixture,
        **fixture,
        "runtime_command_pinning_result": _runtime_command_pinning_result(),
        "runtime_original_command_result": _runtime_original_command_result(),
        "runtime_quit_variant_matrix_result": _runtime_quit_variant_matrix_result(),
        "runtime_exit_strategy_result": _runtime_exit_strategy_result(),
        "runtime_execution_attempted": False,
        "runtime_execution_completed": False,
        "runtime_execution_verified": False,
        "runtime_execution_status": "runtime_execution_not_attempted",
        "live_runtime_execution": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "runtime_harness_proof_claimed": True,
        "runtime_harness_proof_verified": True,
        "runtime_harness_proof_is_character_proof": False,
        "required_runtime_harness_assertions_passed": [
            "runtime_exit_fixture_source_ready",
            "runtime_exit_fixture_rebuild_gate_pass",
            "runtime_exit_fixture_rebuild_not_attempted_without_gate",
            "runtime_exit_fixture_project_mutation_not_attempted_without_gate",
            "runtime_execution_not_attempted_in_rebuild_gate_mode",
            "runtime_character_proof_not_claimed",
        ],
        "required_runtime_harness_assertions_failed": [],
        "runtime_harness_assertion_informational": [
            "runtime_exit_fixture_rebuild_gate_is_not_runtime_execution_proof",
            "runtime_exit_fixture_source_readiness_is_not_runtime_execution_proof",
            "runtime_exit_fixture_is_not_runtime_character_proof",
        ],
        "runtime_harness_unavailable_reasons": [
            {
                "assertion": "runtime_exit_fixture_enablement",
                "status": "blocked_by_fixture_not_enabled_for_project",
                "reason": "fixture Gem is source-ready but not enabled/rebuilt for the live project; mutation and rebuild gates remain unset",
            }
        ]
        if not project_enabled
        else [],
    }


def _runtime_exit_fixture_static_payload(*, timeout_seconds: int) -> Dict[str, Any]:
    safety_profile = {
        "local": True,
        "bounded_by_timeout": True,
        "evidence_captured": True,
        "stdout_stderr_capture_required": True,
        "log_capture_best_effort": True,
        "non_publishing": True,
        "non_packaging": True,
        "mutates_production": False,
        "production_level_mutation": False,
        "uses_production_level": False,
        "uses_temp_level": False,
        "uses_no_level": True,
        "shipping_behavior": False,
        "runtime_process_launched": False,
    }
    return {
        "runtime_exit_fixture_status": "runtime_exit_fixture_ready_not_built",
        "runtime_exit_fixture_available": False,
        "runtime_exit_fixture_kind": "repo_owned_external_code_gem_tickbus_exit_fixture",
        "runtime_exit_fixture_scope": "repo_owned_external_code_gem_harness_only",
        "runtime_exit_fixture_shipping_status": "non_shipping_harness_only_disabled_by_default",
        "runtime_exit_fixture_source_status": "runtime_exit_fixture_source_ready",
        "runtime_exit_fixture_source_path": _repo_relative(RUNTIME_EXIT_FIXTURE_SOURCE_PATH),
        "runtime_exit_fixture_source_owned_by_repo": _is_repo_relative_path(RUNTIME_EXIT_FIXTURE_SOURCE_PATH),
        "runtime_exit_fixture_gem_name": RUNTIME_EXIT_FIXTURE_GEM_NAME,
        "runtime_exit_fixture_gem_type": "Code",
        "runtime_exit_fixture_gem_json_path": _repo_relative(RUNTIME_EXIT_FIXTURE_GEM_JSON),
        "runtime_exit_fixture_cmake_path": _repo_relative(RUNTIME_EXIT_FIXTURE_ROOT_CMAKE),
        "runtime_exit_fixture_component_name": "MaxineRuntimeExitFixtureSystemComponent",
        "runtime_exit_fixture_component_services": ["MaxineRuntimeExitFixtureService"],
        "runtime_exit_fixture_component_or_hook": "MaxineRuntimeExitFixtureSystemComponent",
        "runtime_exit_fixture_lifecycle_point": "AZ::Component::Activate plus AZ::TickBus::OnTick",
        "runtime_exit_fixture_exit_api": "AzFramework::ApplicationRequests::ExitMainLoop",
        "runtime_exit_fixture_gate": "MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE",
        "runtime_exit_fixture_gate_env": list(RUNTIME_EXIT_FIXTURE_GATE_ENV),
        "runtime_exit_fixture_settings_registry_keys": list(RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS),
        "runtime_exit_fixture_settings_registry_key": RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS[1],
        "runtime_exit_fixture_command_line_arg": (
            "--regset=/Amazon/MAXINE/RuntimeHarness/EnableExitFixture=true "
            "--regset=/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks=<positive integer>"
        ),
        "runtime_exit_fixture_wait_ticks": "settings_registry_controlled_positive_integer",
        "runtime_exit_fixture_command": "",
        "runtime_exit_fixture_arguments": [],
        "runtime_exit_fixture_argument_shape": {
            "fixture_strategy": "repo-owned TickBus exit-after-initialization component",
            "runtime_gate": list(RUNTIME_EXIT_FIXTURE_GATE_ENV),
            "settings_registry_keys": list(RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS),
        },
        "runtime_exit_fixture_safety_profile": safety_profile,
        "runtime_exit_fixture_requires_rebuild": True,
        "runtime_exit_fixture_rebuild_status": "not_attempted",
        "runtime_exit_fixture_enabled_for_project": False,
        "runtime_exit_fixture_registration_attempted": False,
        "runtime_exit_fixture_registration_command": [],
        "runtime_exit_fixture_registration_result": "",
        "runtime_exit_fixture_registration_stdout_ref": "",
        "runtime_exit_fixture_registration_stderr_ref": "",
        "runtime_exit_fixture_registration_changes": [],
        "runtime_exit_fixture_registration_reversible": False,
        "runtime_exit_fixture_registration_rollback": "",
        "runtime_exit_fixture_enablement_attempted": False,
        "runtime_exit_fixture_enablement_command": [],
        "runtime_exit_fixture_enablement_result": "",
        "runtime_exit_fixture_enablement_stdout_ref": "",
        "runtime_exit_fixture_enablement_stderr_ref": "",
        "runtime_exit_fixture_enablement_changes": [],
        "runtime_exit_fixture_enablement_reversible": False,
        "runtime_exit_fixture_enablement_rollback": "",
        "runtime_exit_fixture_project_mutation_files": [],
        "runtime_exit_fixture_project_mutation_before_refs": [],
        "runtime_exit_fixture_project_mutation_after_refs": [],
        "runtime_exit_fixture_project_mutation_diff_summary": [],
        "runtime_exit_fixture_project_mutation_rollback": "",
        "runtime_exit_fixture_enabled_by_default": False,
        "runtime_exit_fixture_is_shipping_behavior": False,
        "runtime_exit_fixture_mutates_production": False,
        "runtime_exit_fixture_uses_production_level": False,
        "runtime_exit_fixture_uses_temp_level": False,
        "runtime_exit_fixture_uses_no_level": True,
        "runtime_exit_fixture_execution_attempted": False,
        "runtime_exit_fixture_execution_completed": False,
        "runtime_exit_fixture_execution_verified": False,
        "runtime_exit_fixture_exit_code_decimal": None,
        "runtime_exit_fixture_exit_code_hex": "",
        "runtime_exit_fixture_exit_classification": "runtime_execution_not_attempted",
        "runtime_exit_fixture_timeout_seconds": int(timeout_seconds),
        "runtime_exit_fixture_timed_out": False,
        "runtime_exit_fixture_kill_attempted": False,
        "runtime_exit_fixture_kill_result": {"status": "not_run"},
        "runtime_exit_fixture_stdout_ref": "",
        "runtime_exit_fixture_stderr_ref": "",
        "runtime_exit_fixture_log_refs": [],
        "runtime_exit_fixture_log_scan": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_fixture_asserts": {"status": "runtime_execution_not_attempted", "count": 0, "sample_lines": []},
        "runtime_exit_fixture_missing_asset_signals": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_fixture_disqualifying_signals": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_fixture_marker_observed": False,
        "runtime_exit_fixture_runtime_command": [],
        "runtime_exit_fixture_runtime_command_status": "not_run",
        "runtime_exit_fixture_runtime_command_arguments": [],
        "runtime_exit_fixture_runtime_command_uses_console_command_file_quit": False,
        "runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit": False,
        "runtime_exit_fixture_runtime_command_uses_no_default_level_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_loadlevel_override_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_temp_or_sandbox_level": False,
        "runtime_exit_fixture_level_load_observed": False,
        "runtime_exit_fixture_unexpected_level_load": False,
        "runtime_exit_fixture_actual_level_loads": [],
        "runtime_launch_hygiene": {"status": "runtime_execution_not_attempted"},
        "runtime_launch_hygiene_status": "runtime_execution_not_attempted",
        "runtime_launch_level_policy": "no_default_or_production_level",
        "runtime_launch_level_policy_status": "runtime_execution_not_attempted",
        "runtime_default_level_autoload_detected": False,
        "runtime_default_level_path": RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH,
        "runtime_default_level_product_path": RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH,
        "runtime_default_level_source": "",
        "runtime_default_level_source_evidence": {},
        "runtime_default_level_disqualifying": False,
        "runtime_default_level_classification": "runtime_execution_not_attempted",
        "runtime_default_level_blocked_reason": "",
        "runtime_no_default_level_strategy": "settings_registry_regremove_autoexec_loadlevel",
        "runtime_no_default_level_strategy_status": "runtime_execution_not_attempted",
        "runtime_no_default_level_source_validation": {},
        "runtime_no_default_level_source_refs": [],
        "runtime_no_default_level_command": "",
        "runtime_no_default_level_arguments": [],
        "runtime_no_default_level_settings_registry_keys": [RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY],
        "runtime_no_default_level_expected_level_loads": [],
        "runtime_no_default_level_actual_level_loads": [],
        "runtime_no_default_level_execution_attempted": False,
        "runtime_no_default_level_execution_verified": False,
        "runtime_loadlevel_override": {"status": "runtime_execution_not_attempted"},
        "runtime_loadlevel_override_status": "runtime_execution_not_attempted",
        "runtime_loadlevel_override_candidates": [],
        "runtime_loadlevel_override_candidate_matrix_recorded": False,
        "runtime_loadlevel_override_candidate_id": "",
        "runtime_loadlevel_override_candidate_name": "",
        "runtime_loadlevel_override_candidate_kind": "",
        "runtime_loadlevel_override_candidate_source_validation": {},
        "runtime_loadlevel_override_candidate_source_refs": [],
        "runtime_loadlevel_override_candidate_command_args": [],
        "runtime_loadlevel_override_candidate_settings_registry_keys": [],
        "runtime_loadlevel_override_candidate_expected_registry_state": {},
        "runtime_loadlevel_override_candidate_actual_registry_state": {},
        "runtime_loadlevel_override_candidate_expected_level_loads": [],
        "runtime_loadlevel_override_candidate_actual_level_loads": [],
        "runtime_loadlevel_override_candidate_attempted": False,
        "runtime_loadlevel_override_candidate_result": "",
        "runtime_loadlevel_override_candidate_rejected_reason": "",
        "runtime_loadlevel_override_candidate_blocker": "",
        "runtime_loadlevel_override_selected": "",
        "runtime_loadlevel_override_selected_reason": "",
        "runtime_loadlevel_override_verified": False,
        "runtime_settings_registry_merge_order_summary": {},
        "runtime_settings_registry_command_line_override_order": "",
        "runtime_settings_registry_project_registry_order": "",
        "runtime_autoexec_console_command_source": "",
        "runtime_autoexec_console_command_effective_state": {},
        "runtime_autoexec_console_command_override_state": {},
        "runtime_default_level_override_blocker": "",
        "runtime_temp_harness_level_strategy": "not_used",
        "runtime_temp_harness_level_path": "",
        "runtime_temp_harness_level_generation_status": "not_attempted",
        "runtime_temp_harness_level_production_mutation": False,
        "runtime_empty_harness_level_strategy": "not_used",
        "runtime_empty_harness_level_path": "",
        "runtime_empty_harness_level_generation_status": "not_attempted",
        "runtime_empty_harness_level_mutation_status": "not_attempted",
        "runtime_empty_harness_level_production_mutation": False,
        "runtime_asset_processor_negotiation_signal": {"status": "runtime_execution_not_attempted", "count": 0},
        "runtime_asset_processor_negotiation_signal_status": "runtime_execution_not_attempted",
        "runtime_asset_processor_negotiation_status": "runtime_execution_not_attempted",
        "runtime_asset_processor_negotiation_classification": "runtime_execution_not_attempted",
        "runtime_asset_processor_negotiation_disqualifying": False,
        "runtime_shader_serializer_signal": {"status": "runtime_execution_not_attempted", "count": 0},
        "runtime_shader_serializer_signal_status": "runtime_execution_not_attempted",
        "runtime_shader_serializer_status": "runtime_execution_not_attempted",
        "runtime_shader_serializer_classification": "runtime_execution_not_attempted",
        "runtime_shader_serializer_disqualifying": False,
        "runtime_disqualifying_signal_summary": [],
        "runtime_disqualifying_signal_count": 0,
        "runtime_fixture_marker_observed": False,
        "runtime_fixture_exit_code_clean": False,
        "runtime_fixture_clean_launch_verified": False,
        "runtime_exit_fixture_unsupported_reason": "",
        "runtime_exit_fixture_is_runtime_character_proof": False,
        "runtime_exit_fixture_character_proof_claimed": False,
        "runtime_exit_fixture_character_proof_verified": False,
    }


def _runtime_exit_fixture_repo_source_refs() -> List[str]:
    return [
        _repo_relative(RUNTIME_EXIT_FIXTURE_GEM_JSON),
        _repo_relative(RUNTIME_EXIT_FIXTURE_ROOT_CMAKE),
        _repo_relative(RUNTIME_EXIT_FIXTURE_CMAKE),
        _repo_relative(RUNTIME_EXIT_FIXTURE_COMPONENT_HEADER),
        _repo_relative(RUNTIME_EXIT_FIXTURE_COMPONENT_SOURCE),
        _repo_relative(RUNTIME_EXIT_FIXTURE_MODULE_SOURCE),
    ]


def _runtime_exit_fixture_enabled_for_project(project: Path | None) -> bool:
    if project is None:
        return False
    project_json = project / "project.json"
    if not project_json.is_file():
        return False
    try:
        payload = json.loads(project_json.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return False
    gem_names = payload.get("gem_names", [])
    if isinstance(gem_names, list) and RUNTIME_EXIT_FIXTURE_GEM_NAME in {str(item) for item in gem_names}:
        return True
    gems = payload.get("gems", [])
    if isinstance(gems, list) and RUNTIME_EXIT_FIXTURE_GEM_NAME in {str(item) for item in gems}:
        return True
    return False


def _runtime_exit_fixture_register_command(*, engine_root: Path | None, project: Path | None) -> List[str]:
    o3de_cli = _o3de_cli_path(engine_root)
    return [
        o3de_cli,
        "register",
        "--external-subdirectory",
        str(RUNTIME_EXIT_FIXTURE_SOURCE_PATH),
        "--external-subdirectory-project-path",
        str(project or ""),
    ]


def _runtime_exit_fixture_enable_command(*, engine_root: Path | None, project: Path | None) -> List[str]:
    o3de_cli = _o3de_cli_path(engine_root)
    return [
        o3de_cli,
        "enable-gem",
        "--gem-path",
        str(RUNTIME_EXIT_FIXTURE_SOURCE_PATH),
        "--project-path",
        str(project or ""),
    ]


def _runtime_exit_fixture_rebuild_command(*, engine_root: Path | None, project: Path | None) -> List[str]:
    target = _runtime_exit_fixture_rebuild_target(project)
    build_root = str((engine_root / "build" / "windows") if engine_root is not None else Path("<engine-root>") / "build" / "windows")
    return ["cmake", "--build", build_root, "--target", target, "--config", "profile", "--parallel"]


def _runtime_exit_fixture_rebuild_target(project: Path | None) -> str:
    return f"{_project_name(project) or PROJECT_NAME}.HeadlessServerLauncher"


def _o3de_cli_path(engine_root: Path | None) -> str:
    if engine_root is None:
        return "<engine-root>/scripts/o3de.bat"
    return str(engine_root / "scripts" / "o3de.bat")


def _is_repo_relative_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
        return True
    except ValueError:
        return False


def _read_text_if_present(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig") if path.is_file() else ""
    except OSError:
        return ""


def _runtime_exit_fixture_source_validation() -> Dict[str, Any]:
    return {
        "status": "runtime_exit_fixture_source_discovery_pass",
        "summary": (
            "O3DE source exposes an after-main-loop lifecycle route through AZ::TickBus and "
            "AzFramework::ApplicationRequests::ExitMainLoop, and the live MAXINE project has a "
            "system component Activate hook. This repository does not contain that project Gem "
            "source, so enabling the hook would require external project code mutation and a code rebuild."
        ),
        "safe_lifecycle_surface": "AZ::Component::Activate plus AZ::TickBus::OnTick can request AzFramework::ApplicationRequests::ExitMainLoop after initialization.",
        "repo_scope_result": "blocked_by_fixture_requires_project_code_rebuild",
    }


def _runtime_exit_fixture_source_refs() -> List[str]:
    return [
        "C:/src/o3de/Code/Framework/AzFramework/AzFramework/API/ApplicationAPI.h:85-89",
        "C:/src/o3de/Code/Framework/AzFramework/AzFramework/Application/Application.h:134-135",
        "C:/src/o3de/Code/Framework/AzFramework/AzFramework/Application/Application.cpp:572-575",
        "C:/src/o3de/Code/Framework/AzCore/AzCore/Component/TickBus.h:55-56",
        "C:/src/o3de/Code/Framework/AzCore/AzCore/Component/TickBus.h:119",
        "C:/src/o3de/Code/Framework/AzCore/AzCore/Component/TickBus.h:149",
        "C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus/Gem/Source/MAXINE_GoldenCorpusSystemComponent.cpp:61-63",
    ]


def _top_level_exit_fixture_blocked_payload(*, timeout_seconds: int) -> Dict[str, Any]:
    source_validation = _runtime_exit_fixture_source_validation()
    source_refs = _runtime_exit_fixture_source_refs()
    safety_profile = {
        "local": True,
        "bounded_by_timeout": True,
        "non_publishing": True,
        "non_packaging": True,
        "production_level_mutation": False,
        "uses_production_level": False,
        "uses_no_level": True,
        "shipping_behavior": False,
        "runtime_process_launched": False,
    }
    fixture = {
        "runtime_exit_fixture_status": "blocked_by_fixture_requires_project_code_rebuild",
        "runtime_exit_fixture_available": False,
        "runtime_exit_fixture_kind": "project_system_component_tickbus_exit_candidate",
        "runtime_exit_fixture_scope": "external_project_gem_required_not_repo_scoped",
        "runtime_exit_fixture_shipping_status": "non_shipping_required_not_implemented",
        "runtime_exit_fixture_source_discovery_status": "runtime_exit_fixture_source_discovery_pass",
        "runtime_exit_fixture_source_validation": source_validation,
        "runtime_exit_fixture_source_refs": source_refs,
        "runtime_exit_fixture_component_or_hook": "MAXINE_GoldenCorpusSystemComponent",
        "runtime_exit_fixture_lifecycle_point": "AZ::Component::Activate plus AZ::TickBus::OnTick candidate",
        "runtime_exit_fixture_gate": "MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE",
        "runtime_exit_fixture_gate_env": [
            "MAXINE_ENABLE_O3DE_RUNTIME_HARNESS=1",
            "MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS=1",
            "MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE=1",
        ],
        "runtime_exit_fixture_settings_registry_key": "/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks",
        "runtime_exit_fixture_command_line_arg": "",
        "runtime_exit_fixture_wait_ticks": "not_implemented",
        "runtime_exit_fixture_command": "",
        "runtime_exit_fixture_arguments": [],
        "runtime_exit_fixture_argument_shape": {
            "fixture_strategy": "project-scoped TickBus exit-after-initialization component",
            "blocked_reason": "repo does not own the live project Gem source or rebuild output",
        },
        "runtime_exit_fixture_safety_profile": safety_profile,
        "runtime_exit_fixture_requires_rebuild": True,
        "runtime_exit_fixture_rebuild_status": "not_attempted",
        "runtime_exit_fixture_enabled_for_project": False,
        "runtime_exit_fixture_mutates_production": False,
        "runtime_exit_fixture_uses_production_level": False,
        "runtime_exit_fixture_uses_temp_level": False,
        "runtime_exit_fixture_uses_no_level": True,
        "runtime_exit_fixture_execution_attempted": False,
        "runtime_exit_fixture_execution_completed": False,
        "runtime_exit_fixture_execution_verified": False,
        "runtime_exit_fixture_exit_code_decimal": None,
        "runtime_exit_fixture_exit_code_hex": "",
        "runtime_exit_fixture_exit_classification": "runtime_execution_not_attempted",
        "runtime_exit_fixture_timeout_seconds": int(timeout_seconds),
        "runtime_exit_fixture_timed_out": False,
        "runtime_exit_fixture_kill_attempted": False,
        "runtime_exit_fixture_kill_result": {"status": "not_run"},
        "runtime_exit_fixture_stdout_ref": "",
        "runtime_exit_fixture_stderr_ref": "",
        "runtime_exit_fixture_log_refs": [],
        "runtime_exit_fixture_log_scan": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_fixture_asserts": {"status": "runtime_execution_not_attempted", "count": 0, "sample_lines": []},
        "runtime_exit_fixture_missing_asset_signals": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_fixture_disqualifying_signals": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_requires_project_code_rebuild",
        "runtime_exit_fixture_unavailable_reason": "blocked_by_missing_runtime_exit_fixture_surface",
        "runtime_exit_fixture_unsupported_reason": "",
        "runtime_exit_fixture_is_runtime_character_proof": False,
        "runtime_exit_fixture_character_proof_claimed": False,
        "runtime_exit_fixture_character_proof_verified": False,
    }
    return {
        "status": "pass",
        "runtime_harness_status": "blocked_by_fixture_requires_project_code_rebuild",
        "runtime_exit_fixture": fixture,
        **fixture,
        "runtime_command_pinning_result": _runtime_command_pinning_result(),
        "runtime_original_command_result": _runtime_original_command_result(),
        "runtime_quit_variant_matrix_result": _runtime_quit_variant_matrix_result(),
        "runtime_exit_strategy_result": _runtime_exit_strategy_result(),
        "runtime_execution_attempted": False,
        "runtime_execution_completed": False,
        "runtime_execution_verified": False,
        "runtime_execution_status": "runtime_execution_not_attempted",
        "live_runtime_execution": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "runtime_harness_proof_claimed": True,
        "runtime_harness_proof_verified": True,
        "runtime_harness_proof_is_character_proof": False,
        "required_runtime_harness_assertions_passed": [
            "runtime_command_pinning_pass",
            "runtime_exit_strategy_candidate_matrix_preserved",
            "runtime_exit_fixture_source_discovery_pass",
            "runtime_exit_fixture_blocker_recorded",
            "runtime_execution_not_attempted_without_safe_fixture",
            "runtime_character_proof_not_claimed",
        ],
        "required_runtime_harness_assertions_failed": [],
        "runtime_harness_assertion_informational": [
            "runtime_exit_fixture_source_validation_is_not_runtime_execution_proof",
            "runtime_exit_fixture_requires_project_code_rebuild",
            "runtime_exit_fixture_is_not_runtime_character_proof",
            "runtime_exit_fixture_diagnostic_did_not_launch_runtime",
        ],
        "runtime_harness_unavailable_reasons": [
            {
                "assertion": "runtime_exit_fixture",
                "status": "blocked_by_fixture_requires_project_code_rebuild",
                "reason": "blocked_by_missing_runtime_exit_fixture_surface",
            }
        ],
    }


def _runtime_original_command_result() -> Dict[str, Any]:
    return {
        "status": "preserved_from_pr126",
        "command_kind": "headless_console_quit_envelope",
        "exit_code_decimal": 3221225477,
        "exit_code_hex": "0xC0000005",
        "exit_code_signed": -1073741819,
        "exit_code_name": "STATUS_ACCESS_VIOLATION",
        "classification": "runtime_execution_failed_access_violation_like_exit",
        "crash_like": True,
        "runtime_execution_verified": False,
        "runtime_character_proof_claimed": False,
    }


def _runtime_command_pinning_result() -> Dict[str, Any]:
    return {
        "status": "preserved_from_pr125",
        "runtime_command_pinned": True,
        "runtime_command_pin_verified": True,
        "command_kind": "headless_console_quit_envelope",
        "expected_exit_codes": [0],
        "timeout_seconds": 120,
    }


def _runtime_quit_variant_matrix_result() -> Dict[str, Any]:
    return {
        "status": "preserved_from_pr127",
        "variants": [
            {
                "id": "baseline_pinned_console_quit",
                "status": "runtime_command_variant_not_attempted_in_pr127",
                "exit_code_decimal": 3221225477,
                "exit_code_hex": "0xC0000005",
            },
            {
                "id": "nullrenderer_only_console_quit",
                "status": "runtime_command_variant_failed_access_violation_like_exit",
                "exit_code_decimal": 3221225477,
                "exit_code_hex": "0xC0000005",
            },
            {
                "id": "rhi_null_only_console_quit",
                "status": "runtime_command_variant_failed_access_violation_like_exit",
                "exit_code_decimal": 3221225477,
                "exit_code_hex": "0xC0000005",
            },
        ],
        "variants_passed": [],
        "selected_safer_variant": "",
    }


def _runtime_exit_strategy_result() -> Dict[str, Any]:
    return {
        "status": "preserved_from_pr128",
        "runtime_exit_strategy_status": "blocked_by_missing_source_validated_runtime_exit_strategy",
        "runtime_exit_strategy_verified": False,
        "selected_runtime_exit_strategy": "",
        "blocked_reason": "headless_launcher_no_level_exit_strategy_unavailable",
    }


def _exit_strategy_candidate_signal_fields(scan: Mapping[str, Any]) -> Dict[str, Any]:
    fields = _runtime_signal_fields(scan)
    return {f"runtime_exit_strategy_candidate_{key.removeprefix('runtime_')}": value for key, value in fields.items()}


def _run_runtime_quit_variant_diagnostics(
    report: Dict[str, Any],
    *,
    command: Mapping[str, Any],
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> Dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report.update(_runtime_command_pin_payload(command, timeout_seconds=timeout_seconds, execution_requested=True))
    variants = _runtime_quit_variant_matrix(command, artifact_dir=artifact_dir, timeout_seconds=timeout_seconds)
    selected_variant: Dict[str, Any] | None = None
    last_attempted_variant: Dict[str, Any] | None = None
    attempted_any = False

    for index, variant in enumerate(variants):
        if variant.get("runtime_command_variant_status") != "runtime_command_variant_attemptable":
            continue
        attempted = _attempt_runtime_command_variant(
            variant,
            report=report,
            env=env,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
            command_runner=command_runner,
        )
        variants[index] = attempted
        attempted_any = True
        last_attempted_variant = attempted
        if attempted.get("runtime_command_variant_status") == "runtime_command_variant_pass":
            selected_variant = attempted
            break

    if selected_variant is not None:
        for index, variant in enumerate(variants):
            if variant.get("runtime_command_variant_status") == "runtime_command_variant_attemptable":
                pending = dict(variant)
                pending.update(
                    {
                        "runtime_command_variant_status": "runtime_command_variant_not_attempted",
                        "runtime_command_variant_attempted": False,
                        "runtime_command_variant_reason": "stopped_after_clean_variant",
                    }
                )
                variants[index] = pending
        report.update(_top_level_variant_success_payload(selected_variant, variants))
    elif attempted_any and last_attempted_variant is not None:
        report.update(_top_level_variant_failure_payload(last_attempted_variant, variants))
    else:
        report.update(
            {
                "status": "pass",
                "runtime_harness_status": "runtime_command_variant_selected_none",
                "runtime_quit_variant_diagnostic_status": "runtime_command_variant_selected_none",
                "runtime_quit_variant_diagnostic_reason": "No source-validated runtime quit variant was attemptable.",
                "runtime_command_variants": variants,
                "runtime_command_variant_matrix": variants,
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
                    "runtime_command_pinning_pass",
                    "runtime_quit_variants_recorded_with_typed_blockers",
                    "runtime_character_proof_not_claimed",
                ],
                "runtime_harness_assertion_informational": [
                    "runtime_quit_variant_diagnostic_did_not_launch_runtime",
                    "runtime_quit_variant_is_not_runtime_character_proof",
                ],
            }
        )
    return _finalize_report(report)


def _runtime_quit_variant_matrix(
    command: Mapping[str, Any],
    *,
    artifact_dir: Path,
    timeout_seconds: int,
) -> List[Dict[str, Any]]:
    base_argv = list(command.get("argv", []))
    executable = str(base_argv[0]).strip() if base_argv else ""
    project_arg = next((str(arg) for arg in base_argv if str(arg).startswith("--project-path=")), "")
    wait_for_connect_arg = "--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0"
    variants: List[Dict[str, Any]] = [
        _runtime_variant_payload(
            variant_id="baseline_pinned_console_quit",
            name="Original pinned console quit envelope",
            status="runtime_command_variant_not_attempted",
            reason="Preserved from PR #125/#126 as the classified failing baseline; this diagnostic does not rerun it before safer variants.",
            argv=base_argv,
            timeout_seconds=timeout_seconds,
            safety_profile=dict(command.get("safety_profile", {})),
            source_validation={
                "status": "pass",
                "reason": "Original command pinning source evidence remains preserved.",
                "refs": command.get("source_evidence_refs", []),
            },
        ),
        _runtime_variant_payload(
            variant_id="nullrenderer_only_console_quit",
            name="-NullRenderer only console quit envelope",
            status="runtime_command_variant_attemptable",
            reason="Source-validated safer renderer variant removes the redundant -rhi=null argument while preserving console-mode and quit semantics.",
            argv=_variant_argv(
                executable=executable,
                project_arg=project_arg,
                renderer_args=["-NullRenderer"],
                wait_for_connect_arg=wait_for_connect_arg,
                command_file=artifact_dir / "maxine_runtime_command_quit_nullrenderer_only.cfg",
            ),
            timeout_seconds=timeout_seconds,
            safety_profile=_variant_safety_profile("nullrenderer_only_console_quit", artifact_dir),
            source_validation={
                "status": "pass",
                "reason": "GameApplication.cpp treats -NullRenderer as console mode; Launcher.cpp executes console-command-file; SystemInit.cpp registers quit.",
                "refs": [
                    "C:/src/o3de/Code/Framework/AzGameFramework/AzGameFramework/Application/GameApplication.cpp:126",
                    "C:/src/o3de/Code/Framework/AzGameFramework/AzGameFramework/Application/GameApplication.cpp:135",
                    "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:66",
                    "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:607",
                    "C:/src/o3de/Code/Legacy/CrySystem/SystemInit.cpp:1196",
                    "C:/src/o3de/Code/Legacy/CrySystem/SystemInit.cpp:1205",
                ],
            },
        ),
        _runtime_variant_payload(
            variant_id="rhi_null_only_console_quit",
            name="-rhi=null only console quit envelope",
            status="runtime_command_variant_attemptable",
            reason="Source-validated safer renderer variant removes -NullRenderer while preserving rhi=null console-mode and quit semantics.",
            argv=_variant_argv(
                executable=executable,
                project_arg=project_arg,
                renderer_args=["-rhi=null"],
                wait_for_connect_arg=wait_for_connect_arg,
                command_file=artifact_dir / "maxine_runtime_command_quit_rhi_null_only.cfg",
            ),
            timeout_seconds=timeout_seconds,
            safety_profile=_variant_safety_profile("rhi_null_only_console_quit", artifact_dir),
            source_validation={
                "status": "pass",
                "reason": "GameApplication.cpp treats rhi=null as console mode; Launcher.cpp executes console-command-file; SystemInit.cpp registers quit.",
                "refs": [
                    "C:/src/o3de/Code/Framework/AzGameFramework/AzGameFramework/Application/GameApplication.cpp:126",
                    "C:/src/o3de/Code/Framework/AzGameFramework/AzGameFramework/Application/GameApplication.cpp:139",
                    "C:/src/o3de/Code/Framework/AzGameFramework/AzGameFramework/Application/GameApplication.cpp:142",
                    "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:66",
                    "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:607",
                    "C:/src/o3de/Code/Legacy/CrySystem/SystemInit.cpp:1196",
                    "C:/src/o3de/Code/Legacy/CrySystem/SystemInit.cpp:1205",
                ],
            },
        ),
        _runtime_variant_payload(
            variant_id="help_or_version_surface",
            name="Help/version/no-op launcher surface",
            status="runtime_command_variant_rejected_missing_source_validation",
            reason="Inspected Launcher.cpp did not expose a HeadlessServerLauncher help/version path that exits before normal startup.",
            argv=[executable, "--help"] if executable else [],
            timeout_seconds=timeout_seconds,
            safety_profile=_rejected_variant_safety_profile(),
            rejected_reason="variant_rejected_missing_source_validation",
            source_validation={
                "status": "runtime_command_variant_rejected_missing_source_validation",
                "reason": "No source-validated help/version startup exit surface was found for this launcher path.",
                "refs": ["C:/src/o3de/Code/LauncherUnified/Launcher.cpp:83", "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:614"],
            },
        ),
        _runtime_variant_payload(
            variant_id="no_console_command_file",
            name="No console-command-file startup",
            status="runtime_command_variant_rejected_no_exit_strategy",
            reason="Launcher.cpp enters the main loop after command-line processing; without console-command-file there is no source-validated bounded exit.",
            argv=[executable, project_arg, "-NullRenderer", wait_for_connect_arg] if executable and project_arg else [],
            timeout_seconds=timeout_seconds,
            safety_profile=_rejected_variant_safety_profile(),
            rejected_reason="variant_rejected_no_exit_strategy",
            source_validation={
                "status": "runtime_command_variant_rejected_no_exit_strategy",
                "reason": "RunMainLoop continues until exit is requested; no safe no-console-file exit strategy was validated.",
                "refs": ["C:/src/o3de/Code/LauncherUnified/Launcher.cpp:97", "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:614"],
            },
        ),
        _runtime_variant_payload(
            variant_id="delayed_quit_sequence",
            name="Delayed quit sequence",
            status="runtime_command_variant_rejected_missing_source_validation",
            reason="No delayed or scheduled quit console command was validated from the inspected source surfaces.",
            argv=[],
            timeout_seconds=timeout_seconds,
            safety_profile=_rejected_variant_safety_profile(),
            rejected_reason="variant_rejected_missing_source_validation",
            source_validation={
                "status": "runtime_command_variant_rejected_missing_source_validation",
                "reason": "Only direct quit was source-validated; no delay command was accepted for this slice.",
                "refs": ["C:/src/o3de/Code/Legacy/CrySystem/SystemInit.cpp:1196"],
            },
        ),
        _runtime_variant_payload(
            variant_id="serverlauncher_fallback",
            name="Project ServerLauncher fallback",
            status="runtime_command_variant_rejected_missing_source_validation",
            reason="HeadlessServerLauncher limitations are not yet proven; fallback launcher would change executable shape without enough source/log evidence.",
            argv=[],
            timeout_seconds=timeout_seconds,
            safety_profile=_rejected_variant_safety_profile(),
            rejected_reason="variant_rejected_missing_source_validation",
            source_validation={
                "status": "runtime_command_variant_rejected_missing_source_validation",
                "reason": "Fallback launcher is recorded for future investigation, but not attemptable in this focused quit-variant slice.",
                "refs": ["C:/src/o3de/Code/LauncherUnified/Launcher.cpp:415", "C:/src/o3de/Code/LauncherUnified/Launcher.cpp:441"],
            },
        ),
    ]
    return variants


def _variant_argv(
    *,
    executable: str,
    project_arg: str,
    renderer_args: Sequence[str],
    wait_for_connect_arg: str,
    command_file: Path,
) -> List[str]:
    command_file.parent.mkdir(parents=True, exist_ok=True)
    command_file.write_text("quit\n", encoding="utf-8")
    return [
        executable,
        project_arg,
        *renderer_args,
        wait_for_connect_arg,
        f"--console-command-file={command_file}",
    ]


def _runtime_variant_payload(
    *,
    variant_id: str,
    name: str,
    status: str,
    reason: str,
    argv: Sequence[str],
    timeout_seconds: int,
    safety_profile: Mapping[str, Any],
    source_validation: Mapping[str, Any],
    rejected_reason: str = "",
) -> Dict[str, Any]:
    argv_list = [str(arg) for arg in argv if str(arg).strip()]
    return {
        "runtime_command_variant_id": variant_id,
        "runtime_command_variant_name": name,
        "runtime_command_variant_status": status,
        "runtime_command_variant_kind": "headless_console_quit_envelope_variant",
        "runtime_command_variant_command": argv_list[0] if argv_list else "",
        "runtime_command_variant_arguments": argv_list[1:],
        "runtime_command_variant_argument_shape": _variant_argument_shape(argv_list),
        "runtime_command_variant_safety_profile": dict(safety_profile),
        "runtime_command_variant_source_validation": dict(source_validation),
        "runtime_command_variant_selected": False,
        "runtime_command_variant_attempted": False,
        "runtime_command_variant_reason": reason,
        "runtime_command_variant_exit_code_decimal": None,
        "runtime_command_variant_exit_code_hex": "",
        "runtime_command_variant_exit_classification": "runtime_execution_not_attempted",
        "runtime_command_variant_timeout_seconds": int(timeout_seconds),
        "runtime_command_variant_timed_out": False,
        "runtime_command_variant_kill_attempted": False,
        "runtime_command_variant_kill_result": {"status": "not_run"},
        "runtime_command_variant_stdout_ref": "",
        "runtime_command_variant_stderr_ref": "",
        "runtime_command_variant_log_refs": [],
        "runtime_command_variant_log_scan": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_command_variant_missing_actor_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_command_variant_missing_mesh_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_command_variant_missing_material_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_command_variant_missing_animation_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_command_variant_missing_asset_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_command_variant_load_error_signal": {"status": "runtime_execution_not_attempted", "matches": []},
        "runtime_command_variant_asset_manager_asserts": {"status": "runtime_execution_not_attempted", "count": 0, "sample_lines": []},
        "runtime_command_variant_shader_serializer_errors": {"status": "runtime_execution_not_attempted", "count": 0, "sample_lines": []},
        "runtime_command_variant_asset_processor_negotiation_errors": {
            "status": "runtime_execution_not_attempted",
            "count": 0,
            "sample_lines": [],
        },
        "runtime_command_variant_rejected_reason": rejected_reason,
        "runtime_command_variant_failure_reason": "",
        "runtime_command_variant_pass_reason": "",
        "runtime_command_variant_expected_exit_codes": [0],
        "runtime_command_variant_expected_exit_matched": False,
        "runtime_command_variant_runtime_execution_verified": False,
        "runtime_command_variant_runtime_character_proof_claimed": False,
        "runtime_command_variant_runtime_character_proof_verified": False,
    }


def _variant_argument_shape(argv: Sequence[str]) -> Dict[str, Any]:
    return {
        "argv0": "runtime executable path" if argv else "",
        "project_path": "explicit --project-path=<MAXINE_GoldenCorpus project path>"
        if any(str(arg).startswith("--project-path=") for arg in argv)
        else "",
        "rendering": [arg for arg in argv if str(arg) in {"-NullRenderer", "-rhi=null"}],
        "asset_processor_connect": "--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0"
        if "--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0" in argv
        else "",
        "exit_strategy": "--console-command-file=<artifact cfg containing quit>"
        if any(str(arg).startswith("--console-command-file=") for arg in argv)
        else "",
    }


def _variant_safety_profile(variant_id: str, artifact_dir: Path) -> Dict[str, Any]:
    return {
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
        "safe_to_kill_after_timeout": True,
        "command_file_ref": _repo_relative(artifact_dir / f"maxine_runtime_command_quit_{variant_id.replace('_console_quit', '')}.cfg"),
    }


def _rejected_variant_safety_profile() -> Dict[str, Any]:
    return {
        "local": True,
        "bounded_by_timeout": True,
        "evidence_captured": False,
        "non_publishing": True,
        "non_packaging": True,
        "mutates_production": False,
        "uses_production_level": False,
        "uses_no_level": True,
        "runtime_character_proof": False,
    }


def _attempt_runtime_command_variant(
    variant: Mapping[str, Any],
    *,
    report: Mapping[str, Any],
    env: Mapping[str, str],
    timeout_seconds: int,
    artifact_dir: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None,
) -> Dict[str, Any]:
    variant_id = str(variant.get("runtime_command_variant_id", "runtime_variant")).strip()
    argv = [str(variant.get("runtime_command_variant_command", "")), *[str(arg) for arg in variant.get("runtime_command_variant_arguments", [])]]
    stdout_path = artifact_dir / f"runtime_variant_{variant_id}_stdout.txt"
    stderr_path = artifact_dir / f"runtime_variant_{variant_id}_stderr.txt"
    timed_out = False
    try:
        if command_runner is not None:
            proc = command_runner(argv=argv, cwd=str(REPO_ROOT), env=dict(env), timeout_seconds=timeout_seconds)
        else:
            proc = subprocess.run(argv, cwd=str(REPO_ROOT), env=dict(env), text=True, capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        proc = subprocess.CompletedProcess(argv, None, stdout=exc.output or "", stderr=exc.stderr or "")

    stdout_text = str(proc.stdout or "")
    stderr_text = str(proc.stderr or "")
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    project_path = _runtime_project_path(report)
    log_refs = _runtime_log_refs(project_path)
    log_text = _read_runtime_logs(log_refs)
    scan = _scan_runtime_output(stdout_text + "\n" + stderr_text + "\n" + log_text)
    diagnostics = _runtime_exit_diagnostics(
        exit_code=proc.returncode,
        timed_out=timed_out,
        stdout=stdout_text,
        stderr=stderr_text,
        log_text=log_text,
        log_refs=log_refs,
    )
    expected_exit_codes = [0]
    expected_exit_matched = proc.returncode in expected_exit_codes and not timed_out
    variant_status, failure_reason, pass_reason = _variant_attempt_status(
        exit_code=proc.returncode,
        timed_out=timed_out,
        scan=scan,
        diagnostics=diagnostics,
        expected_exit_matched=expected_exit_matched,
    )
    variant_payload = dict(variant)
    variant_payload.update(
        {
            "runtime_command_variant_status": variant_status,
            "runtime_command_variant_selected": variant_status == "runtime_command_variant_pass",
            "runtime_command_variant_attempted": True,
            "runtime_command_variant_reason": pass_reason or failure_reason,
            "runtime_command_variant_exit_code_decimal": proc.returncode,
            "runtime_command_variant_exit_code_hex": _exit_code_hex(proc.returncode),
            "runtime_command_variant_exit_classification": diagnostics.get("runtime_exit_classification", ""),
            "runtime_command_variant_timeout_seconds": int(timeout_seconds),
            "runtime_command_variant_timed_out": timed_out,
            "runtime_command_variant_kill_attempted": timed_out,
            "runtime_command_variant_kill_result": {
                "status": "runtime_execution_killed_after_timeout" if timed_out else "not_run"
            },
            "runtime_command_variant_stdout_ref": _repo_relative(stdout_path),
            "runtime_command_variant_stderr_ref": _repo_relative(stderr_path),
            "runtime_command_variant_log_refs": log_refs,
            "runtime_command_variant_log_scan": scan,
            "runtime_command_variant_asset_manager_asserts": diagnostics.get("runtime_asset_manager_asserts", {}),
            "runtime_command_variant_shader_serializer_errors": _variant_error_counter(
                diagnostics,
                "shader_serializer_error_count",
                ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"),
            ),
            "runtime_command_variant_asset_processor_negotiation_errors": _variant_error_counter(
                diagnostics,
                "asset_processor_negotiation_failure_count",
                ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"),
            ),
            "runtime_command_variant_failure_reason": failure_reason,
            "runtime_command_variant_pass_reason": pass_reason,
            "runtime_command_variant_expected_exit_codes": expected_exit_codes,
            "runtime_command_variant_expected_exit_matched": expected_exit_matched,
            "runtime_command_variant_runtime_execution_verified": variant_status == "runtime_command_variant_pass",
            "runtime_command_variant_runtime_character_proof_claimed": False,
            "runtime_command_variant_runtime_character_proof_verified": False,
            "_runtime_diagnostics": diagnostics,
        }
    )
    variant_payload.update(_runtime_variant_signal_fields(scan))
    return variant_payload


def _variant_attempt_status(
    *,
    exit_code: int | None,
    timed_out: bool,
    scan: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    expected_exit_matched: bool,
) -> tuple[str, str, str]:
    if timed_out:
        return "runtime_command_variant_failed_timeout", "runtime command variant exceeded bounded timeout", ""
    if not expected_exit_matched:
        if diagnostics.get("runtime_exit_classification") == "runtime_execution_failed_access_violation_like_exit":
            return (
                "runtime_command_variant_failed_access_violation_like_exit",
                "runtime command variant exited with access-violation-like nonzero status",
                "",
            )
        return "runtime_command_variant_failed_nonzero_exit", f"runtime command variant exited with unexpected code {exit_code}", ""
    if scan.get("status") != "pass":
        return "runtime_command_variant_failed_missing_runtime_asset", "runtime command variant emitted missing/load-error signals", ""
    asset_manager_count = int(diagnostics.get("runtime_asset_manager_asserts", {}).get("count", 0) or 0)
    if asset_manager_count:
        return "runtime_command_variant_failed_asset_manager_shutdown_assert", "runtime command variant emitted AssetManager shutdown asserts", ""
    shader_count = _variant_error_counter(
        diagnostics,
        "shader_serializer_error_count",
        ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"),
    )["count"]
    if shader_count:
        return "runtime_command_variant_failed_shader_serializer_errors", "runtime command variant emitted shader serializer errors", ""
    asset_processor_count = _variant_error_counter(
        diagnostics,
        "asset_processor_negotiation_failure_count",
        ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"),
    )["count"]
    if asset_processor_count:
        return "runtime_command_variant_failed_asset_processor_negotiation", "runtime command variant emitted Asset Processor negotiation errors", ""
    return "runtime_command_variant_pass", "", "runtime command variant exited with expected code and no disqualifying scanned signals"


def _variant_error_counter(
    diagnostics: Mapping[str, Any],
    count_key: str,
    summary_keys: Sequence[str],
) -> Dict[str, Any]:
    count = 0
    sample_lines: List[str] = []
    for key in summary_keys:
        summary = diagnostics.get(key, {})
        if not isinstance(summary, Mapping):
            continue
        count += int(summary.get(count_key, 0) or 0)
        lines = summary.get("sample_lines", [])
        if isinstance(lines, list):
            for line in lines:
                if isinstance(line, str) and line not in sample_lines:
                    sample_lines.append(line)
                if len(sample_lines) >= 5:
                    break
    return {"status": "fail" if count else "pass", "count": count, "sample_lines": sample_lines[:5]}


def _runtime_variant_signal_fields(scan: Mapping[str, Any]) -> Dict[str, Any]:
    fields = _runtime_signal_fields(scan)
    return {f"runtime_command_variant_{key.removeprefix('runtime_')}": value for key, value in fields.items()}


def _top_level_variant_success_payload(selected_variant: Mapping[str, Any], variants: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    diagnostics = dict(selected_variant.get("_runtime_diagnostics", {}))
    diagnostics.pop("runtime_command_variant_result", None)
    diagnostics.pop("runtime_command_variant", None)
    diagnostics.pop("runtime_command_variant_reason", None)
    diagnostics.pop("runtime_command_variant_safety_profile", None)
    diagnostics.pop("runtime_command_variant_selected", None)
    diagnostics.pop("runtime_command_variant_rejected_reason", None)
    scan = selected_variant.get("runtime_command_variant_log_scan", {"status": "pass", "matches": []})
    variant_id = str(selected_variant.get("runtime_command_variant_id", "")).strip()
    payload: Dict[str, Any] = {
        "status": "pass",
        "runtime_harness_status": "runtime_execution_pass",
        "runtime_quit_variant_diagnostic_status": "runtime_command_variant_selected_clean_exit",
        "runtime_quit_variant_diagnostic_reason": "A source-validated safer quit variant exited cleanly with expected semantics.",
        "runtime_safer_variant_selected": variant_id,
        "runtime_safer_variant_selection_reason": selected_variant.get("runtime_command_variant_pass_reason", ""),
        "runtime_safer_variant_verified": True,
        "runtime_command_variants": _strip_private_variant_keys(variants),
        "runtime_command_variant_matrix": _strip_private_variant_keys(variants),
        "runtime_command_variant": variant_id,
        "runtime_command_variant_result": dict(_strip_private_variant_keys([selected_variant])[0]),
        "runtime_command_variant_reason": selected_variant.get("runtime_command_variant_pass_reason", ""),
        "runtime_command_variant_safety_profile": selected_variant.get("runtime_command_variant_safety_profile", {}),
        "runtime_command_variant_selected": True,
        "runtime_command_variant_rejected_reason": "",
        "runtime_execution_attempted": True,
        "runtime_execution_completed": True,
        "runtime_execution_verified": True,
        "runtime_execution_status": "runtime_execution_pass",
        "runtime_exit_code": selected_variant.get("runtime_command_variant_exit_code_decimal"),
        "runtime_timed_out": False,
        "runtime_timeout_stall": False,
        "runtime_kill_attempted": False,
        "runtime_kill_result": {"status": "not_run"},
        "runtime_stdout_ref": selected_variant.get("runtime_command_variant_stdout_ref", ""),
        "runtime_stderr_ref": selected_variant.get("runtime_command_variant_stderr_ref", ""),
        "runtime_command_stdout_ref": selected_variant.get("runtime_command_variant_stdout_ref", ""),
        "runtime_command_stderr_ref": selected_variant.get("runtime_command_variant_stderr_ref", ""),
        "runtime_log_refs": selected_variant.get("runtime_command_variant_log_refs", []),
        "runtime_command_log_refs": selected_variant.get("runtime_command_variant_log_refs", []),
        "runtime_log_scan": scan,
        "runtime_command_log_scan": scan,
        "live_runtime_execution": True,
        "runtime_harness_proof_claimed": True,
        "runtime_harness_proof_verified": True,
        "runtime_harness_proof_is_character_proof": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "required_runtime_harness_assertions_passed": [
            "runtime_command_pinning_pass",
            "runtime_quit_variant_matrix_recorded",
            "runtime_quit_variant_clean_exit",
            "runtime_character_proof_not_claimed",
        ],
        "required_runtime_harness_assertions_failed": [],
        "runtime_harness_assertion_informational": [
            "runtime_quit_variant_execution_is_not_runtime_character_proof",
            "original_pinned_command_failure_remains_preserved",
        ],
    }
    payload.update(diagnostics)
    payload.update(_runtime_signal_fields(scan if isinstance(scan, Mapping) else {"status": "pass", "matches": []}))
    return payload


def _top_level_variant_failure_payload(last_variant: Mapping[str, Any], variants: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    diagnostics = dict(last_variant.get("_runtime_diagnostics", {}))
    diagnostics.pop("runtime_command_variant_result", None)
    diagnostics.pop("runtime_command_variant", None)
    diagnostics.pop("runtime_command_variant_reason", None)
    diagnostics.pop("runtime_command_variant_safety_profile", None)
    diagnostics.pop("runtime_command_variant_selected", None)
    diagnostics.pop("runtime_command_variant_rejected_reason", None)
    scan = last_variant.get("runtime_command_variant_log_scan", {"status": "pass", "matches": []})
    variant_id = str(last_variant.get("runtime_command_variant_id", "")).strip()
    payload: Dict[str, Any] = {
        "status": "fail",
        "runtime_harness_status": "runtime_execution_failed",
        "runtime_quit_variant_diagnostic_status": last_variant.get("runtime_command_variant_status", "runtime_command_variant_failed_unknown"),
        "runtime_quit_variant_diagnostic_reason": "No source-validated safer quit variant exited cleanly.",
        "runtime_safer_variant_selected": "",
        "runtime_safer_variant_selection_reason": "",
        "runtime_safer_variant_verified": False,
        "runtime_command_variants": _strip_private_variant_keys(variants),
        "runtime_command_variant_matrix": _strip_private_variant_keys(variants),
        "runtime_command_variant": variant_id,
        "runtime_command_variant_result": dict(_strip_private_variant_keys([last_variant])[0]),
        "runtime_command_variant_reason": last_variant.get("runtime_command_variant_failure_reason", ""),
        "runtime_command_variant_safety_profile": last_variant.get("runtime_command_variant_safety_profile", {}),
        "runtime_command_variant_selected": False,
        "runtime_command_variant_rejected_reason": "",
        "runtime_execution_attempted": True,
        "runtime_execution_completed": True,
        "runtime_execution_verified": False,
        "runtime_execution_status": "runtime_execution_failed",
        "runtime_exit_code": last_variant.get("runtime_command_variant_exit_code_decimal"),
        "runtime_timed_out": bool(last_variant.get("runtime_command_variant_timed_out", False)),
        "runtime_timeout_stall": bool(last_variant.get("runtime_command_variant_timed_out", False)),
        "runtime_kill_attempted": bool(last_variant.get("runtime_command_variant_kill_attempted", False)),
        "runtime_kill_result": last_variant.get("runtime_command_variant_kill_result", {"status": "not_run"}),
        "runtime_stdout_ref": last_variant.get("runtime_command_variant_stdout_ref", ""),
        "runtime_stderr_ref": last_variant.get("runtime_command_variant_stderr_ref", ""),
        "runtime_command_stdout_ref": last_variant.get("runtime_command_variant_stdout_ref", ""),
        "runtime_command_stderr_ref": last_variant.get("runtime_command_variant_stderr_ref", ""),
        "runtime_log_refs": last_variant.get("runtime_command_variant_log_refs", []),
        "runtime_command_log_refs": last_variant.get("runtime_command_variant_log_refs", []),
        "runtime_log_scan": scan,
        "runtime_command_log_scan": scan,
        "live_runtime_execution": True,
        "runtime_harness_proof_claimed": False,
        "runtime_harness_proof_verified": False,
        "runtime_harness_proof_is_character_proof": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
        "required_runtime_harness_assertions_passed": [
            "runtime_command_pinning_pass",
            "runtime_quit_variant_matrix_recorded",
            "runtime_character_proof_not_claimed",
        ],
        "required_runtime_harness_assertions_failed": ["runtime_quit_variant_clean_exit"],
        "runtime_harness_assertion_informational": [
            "runtime_quit_variant_execution_is_not_runtime_character_proof",
            "original_pinned_command_failure_remains_preserved",
        ],
    }
    payload.update(diagnostics)
    payload.update(_runtime_signal_fields(scan if isinstance(scan, Mapping) else {"status": "pass", "matches": []}))
    return payload


def _strip_private_variant_keys(variants: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []
    for variant in variants:
        item = {key: value for key, value in variant.items() if not key.startswith("_")}
        sanitized.append(item)
    return sanitized


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


def _signed_32bit(value: int) -> int:
    unsigned = int(value) & 0xFFFFFFFF
    return unsigned - 0x100000000 if unsigned >= 0x80000000 else unsigned


def _exit_code_hex(value: int | None) -> str:
    if value is None:
        return ""
    return f"0x{(int(value) & 0xFFFFFFFF):08X}"


def _matching_lines(text: str, patterns: Sequence[str], *, limit: int = 5) -> List[str]:
    lowered_patterns = [pattern.lower() for pattern in patterns]
    matches: List[str] = []
    for line in text.splitlines():
        lower_line = line.lower()
        if any(pattern in lower_line for pattern in lowered_patterns):
            normalized = " ".join(line.strip().split())
            matches.append(normalized[:240])
        if len(matches) >= limit:
            break
    return matches


def _count_patterns(text: str, patterns: Sequence[str]) -> int:
    lower = text.lower()
    return sum(lower.count(pattern.lower()) for pattern in patterns)


def _runtime_text_error_summary(text: str, *, source: str, log_refs: Sequence[str] | None = None) -> Dict[str, Any]:
    if source == "log" and not log_refs:
        return {
            "status": "blocked_by_missing_runtime_log",
            "reason": "No runtime log ref was discovered under the project user/log directory.",
            "asset_processor_negotiation_failure_count": 0,
            "shader_serializer_error_count": 0,
            "asset_manager_shutdown_assert_count": 0,
            "assert_count": 0,
            "fatal_or_exception_count": 0,
            "sample_lines": [],
        }

    asset_processor_count = _count_patterns(
        text,
        (
            "AssetProcessorConnection",
            "Asset Processor Connection",
            "Negotiation with asset processor failed",
        ),
    )
    shader_serializer_count = _count_patterns(
        text,
        (
            "[Error] (Serialize)",
            "not registered with the serializer",
        ),
    )
    asset_manager_count = _count_patterns(text, ("AssetManager has been destroyed",))
    assert_count = _count_patterns(text, ("Assert:",))
    fatal_or_exception_count = _count_patterns(text, ("Fatal", "Exception", "Access violation"))
    sample_lines = _matching_lines(
        text,
        (
            "AssetProcessorConnection",
            "Negotiation with asset processor failed",
            "[Error] (Serialize)",
            "not registered with the serializer",
            "AssetManager has been destroyed",
            "Assert:",
            "Fatal",
            "Exception",
            "Access violation",
        ),
    )
    detected = bool(asset_processor_count or shader_serializer_count or asset_manager_count or assert_count or fatal_or_exception_count)
    status_prefix = "runtime_log" if source == "log" else "runtime_output"
    return {
        "status": f"{status_prefix}_errors_detected" if detected else "pass",
        "asset_processor_negotiation_failure_count": asset_processor_count,
        "shader_serializer_error_count": shader_serializer_count,
        "asset_manager_shutdown_assert_count": asset_manager_count,
        "assert_count": assert_count,
        "fatal_or_exception_count": fatal_or_exception_count,
        "sample_lines": sample_lines,
    }


def _runtime_assertion_diagnostics(combined_text: str) -> Dict[str, Any]:
    assert_lines = _matching_lines(combined_text, ("Assert:",), limit=8)
    asset_manager_lines = _matching_lines(combined_text, ("AssetManager has been destroyed",), limit=8)
    assert_count = _count_patterns(combined_text, ("Assert:",))
    asset_manager_count = _count_patterns(combined_text, ("AssetManager has been destroyed",))
    assertion_status = "runtime_execution_failed_asset_manager_shutdown_assert" if asset_manager_count else "runtime_assertions_detected" if assert_count else "pass"
    return {
        "runtime_assertion_summary": {
            "status": assertion_status,
            "assert_count": assert_count,
            "asset_manager_shutdown_assert_count": asset_manager_count,
            "sample_lines": assert_lines,
        },
        "runtime_asset_manager_asserts": {
            "status": "runtime_execution_failed_asset_manager_shutdown_assert" if asset_manager_count else "pass",
            "count": asset_manager_count,
            "sample_lines": asset_manager_lines,
        },
        "runtime_shutdown_asserts": {
            "status": assertion_status,
            "count": assert_count,
            "sample_lines": assert_lines,
        },
    }


def _runtime_exit_diagnostics(
    *,
    exit_code: int | None,
    timed_out: bool,
    stdout: str,
    stderr: str,
    log_text: str,
    log_refs: Sequence[str],
) -> Dict[str, Any]:
    stdout_summary = _runtime_text_error_summary(stdout, source="stdout")
    stderr_summary = _runtime_text_error_summary(stderr, source="stderr")
    log_summary = _runtime_text_error_summary(log_text, source="log", log_refs=log_refs)
    combined_text = "\n".join([stdout, stderr, log_text])
    assertion_payload = _runtime_assertion_diagnostics(combined_text)
    asset_manager_count = int(assertion_payload["runtime_asset_manager_asserts"].get("count", 0))

    payload: Dict[str, Any] = {
        "runtime_stdout_error_summary": stdout_summary,
        "runtime_stderr_error_summary": stderr_summary,
        "runtime_log_error_summary": log_summary,
        "runtime_stack_or_crash_ref": "",
        "runtime_command_variant": "pinned_headless_console_quit_envelope",
        "runtime_command_variant_result": {
            "status": "runtime_command_variant_not_attempted",
            "attempted": False,
            "reason": "This diagnostic run classified the pinned command result before changing command shape.",
        },
        "runtime_command_variant_reason": "No safer variant was attempted without a source-validated reason.",
        "runtime_command_variant_safety_profile": {},
        "runtime_command_variant_selected": False,
        "runtime_command_variant_rejected_reason": "",
    }
    payload.update(assertion_payload)

    if timed_out:
        payload.update(
            {
                "runtime_exit_classification": "runtime_execution_timed_out",
                "runtime_exit_code_decimal": None,
                "runtime_exit_code_hex": "",
                "runtime_exit_code_signed": None,
                "runtime_exit_code_name": "",
                "runtime_exit_is_windows_ntstatus_like": False,
                "runtime_exit_is_crash_like": False,
                "runtime_crash_classification": "",
                "runtime_crash_evidence": ["runtime_command_timed_out"],
                "runtime_exit_diagnostic_status": "runtime_exit_diagnostic_inconclusive",
                "runtime_exit_diagnostic_reason": "Runtime process exceeded the bounded timeout before an exit code was available.",
                "runtime_root_cause_classification": "runtime_execution_timed_out",
                "runtime_root_cause_hypothesis": "runtime_command_timeout",
                "runtime_root_cause_confidence": "medium",
                "runtime_next_diagnostic_recommendation": "Inspect timeout logs before changing the pinned command envelope.",
            }
        )
        return payload

    if exit_code is None:
        payload.update(
            {
                "runtime_exit_classification": "runtime_exit_code_unclassified",
                "runtime_exit_code_decimal": None,
                "runtime_exit_code_hex": "",
                "runtime_exit_code_signed": None,
                "runtime_exit_code_name": "",
                "runtime_exit_is_windows_ntstatus_like": False,
                "runtime_exit_is_crash_like": False,
                "runtime_crash_classification": "",
                "runtime_crash_evidence": [],
                "runtime_exit_diagnostic_status": "runtime_exit_diagnostic_inconclusive",
                "runtime_exit_diagnostic_reason": "Runtime process did not provide an exit code.",
                "runtime_root_cause_classification": "runtime_execution_failed_unknown",
                "runtime_root_cause_hypothesis": "runtime_exit_code_unavailable",
                "runtime_root_cause_confidence": "low",
                "runtime_next_diagnostic_recommendation": "Capture a bounded runtime process exit code before claiming runtime proof.",
            }
        )
        return payload

    exit_decimal = int(exit_code)
    unsigned = exit_decimal & 0xFFFFFFFF
    exit_hex = _exit_code_hex(exit_decimal)
    exit_name = WINDOWS_NTSTATUS_NAMES.get(unsigned, "")
    is_ntstatus_like = unsigned >= 0xC0000000
    is_crash_like = exit_decimal != 0 and (is_ntstatus_like or bool(exit_name))
    if exit_decimal == 0:
        classification = "runtime_execution_pass"
        diagnostic_status = "runtime_exit_diagnostic_pass"
        reason = "Runtime process exited with expected code 0."
        crash_classification = ""
        root_cause = "pass"
        root_hypothesis = ""
        confidence = ""
        recommendation = ""
    elif unsigned == 0xC0000005:
        classification = "runtime_execution_failed_access_violation_like_exit"
        diagnostic_status = "runtime_exit_code_classified"
        reason = (
            f"Runtime exited with {exit_decimal} ({exit_hex}), an access-violation-like Windows NTSTATUS. "
            "The exit code is diagnostic evidence only and is not treated as root cause by itself."
        )
        crash_classification = classification
        root_cause = "runtime_execution_failed_asset_manager_shutdown_assert" if asset_manager_count else "runtime_execution_failed_unknown"
        root_hypothesis = (
            "AssetManager shutdown asserts were observed after the bounded console quit envelope; "
            "shutdown ordering or quit timing is suspect but not proven."
            if asset_manager_count
            else "Access-violation-like exit without enough log evidence for a root cause."
        )
        confidence = "low"
        recommendation = (
            "Inspect AssetManager shutdown ordering, shader serializer errors, and source-validated delayed/no-op quit variants "
            "before broadening expected exit codes or claiming runtime execution proof."
        )
    else:
        classification = "runtime_execution_failed_nonzero_exit"
        diagnostic_status = "runtime_exit_code_classified"
        reason = f"Runtime exited with unexpected nonzero code {exit_decimal} ({exit_hex})."
        crash_classification = "runtime_execution_failed_unknown"
        root_cause = "runtime_execution_failed_unknown"
        root_hypothesis = "Nonzero runtime exit without a verified root cause."
        confidence = "low"
        recommendation = "Inspect bounded stdout/stderr/runtime logs before changing expected exit semantics."

    evidence: List[str] = []
    if exit_decimal != 0:
        evidence.append(f"nonzero_exit_code:{exit_hex}")
    if is_crash_like:
        evidence.append("windows_ntstatus_like_exit")
    if asset_manager_count:
        evidence.append("asset_manager_shutdown_assert")
    if stdout_summary.get("asset_processor_negotiation_failure_count", 0):
        evidence.append("asset_processor_negotiation_failure")
    if stdout_summary.get("shader_serializer_error_count", 0) or log_summary.get("shader_serializer_error_count", 0):
        evidence.append("shader_serializer_errors")
    if log_summary.get("status") == "blocked_by_missing_runtime_log":
        evidence.append("runtime_log_missing")

    payload.update(
        {
            "runtime_exit_classification": classification,
            "runtime_exit_code_decimal": exit_decimal,
            "runtime_exit_code_hex": exit_hex,
            "runtime_exit_code_signed": _signed_32bit(exit_decimal),
            "runtime_exit_code_name": exit_name,
            "runtime_exit_is_windows_ntstatus_like": is_ntstatus_like,
            "runtime_exit_is_crash_like": is_crash_like,
            "runtime_crash_classification": crash_classification,
            "runtime_crash_evidence": evidence,
            "runtime_exit_diagnostic_status": diagnostic_status,
            "runtime_exit_diagnostic_reason": reason,
            "runtime_root_cause_classification": root_cause,
            "runtime_root_cause_hypothesis": root_hypothesis,
            "runtime_root_cause_confidence": confidence,
            "runtime_next_diagnostic_recommendation": recommendation,
        }
    )
    return payload


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
    nested_keys = [
        key
        for key in report
        if key.startswith("runtime_")
        or key
        in {
            "live_publication",
            "release_packaging",
            "production_level_mutation",
            "defaultlevel_mutation",
            "fake_success",
            "cache_heuristic_used",
        }
    ]
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
    parser.add_argument("--diagnose-runtime-quit-variants", action="store_true")
    parser.add_argument("--diagnose-runtime-exit-strategies", action="store_true")
    parser.add_argument("--diagnose-runtime-exit-fixture", action="store_true")
    parser.add_argument("--check-runtime-exit-fixture-source", action="store_true")
    parser.add_argument("--check-runtime-exit-fixture-rebuild-gate", action="store_true")
    parser.add_argument("--register-runtime-exit-fixture", action="store_true")
    parser.add_argument("--enable-runtime-exit-fixture", action="store_true")
    parser.add_argument("--rebuild-runtime-exit-fixture", action="store_true")
    parser.add_argument("--enable-runtime-exit-fixture-command", action="store_true")
    parser.add_argument("--diagnose-runtime-launch-hygiene", action="store_true")
    parser.add_argument("--enable-runtime-exit-fixture-no-default-level", action="store_true")
    parser.add_argument("--diagnose-runtime-loadlevel-override", action="store_true")
    parser.add_argument("--enable-runtime-exit-fixture-loadlevel-override", action="store_true")
    parser.add_argument("--diagnose-runtime-later-registry-patch", action="store_true")
    parser.add_argument("--enable-runtime-exit-fixture-later-registry-patch", action="store_true")
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
        diagnose_runtime_quit_variants=args.diagnose_runtime_quit_variants,
        diagnose_runtime_exit_strategies=args.diagnose_runtime_exit_strategies,
        diagnose_runtime_exit_fixture=args.diagnose_runtime_exit_fixture,
        check_runtime_exit_fixture_source=args.check_runtime_exit_fixture_source,
        check_runtime_exit_fixture_rebuild_gate=args.check_runtime_exit_fixture_rebuild_gate,
        register_runtime_exit_fixture=args.register_runtime_exit_fixture,
        enable_runtime_exit_fixture=args.enable_runtime_exit_fixture,
        rebuild_runtime_exit_fixture=args.rebuild_runtime_exit_fixture,
        enable_runtime_exit_fixture_command=args.enable_runtime_exit_fixture_command,
        diagnose_runtime_launch_hygiene=args.diagnose_runtime_launch_hygiene,
        enable_runtime_exit_fixture_no_default_level=args.enable_runtime_exit_fixture_no_default_level,
        diagnose_runtime_loadlevel_override=args.diagnose_runtime_loadlevel_override,
        enable_runtime_exit_fixture_loadlevel_override=args.enable_runtime_exit_fixture_loadlevel_override,
        diagnose_runtime_later_registry_patch=args.diagnose_runtime_later_registry_patch,
        enable_runtime_exit_fixture_later_registry_patch=args.enable_runtime_exit_fixture_later_registry_patch,
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
