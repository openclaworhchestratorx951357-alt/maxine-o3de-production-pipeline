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
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence
from uuid import UUID

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
RUNTIME_CHARACTER_PRODUCT_LOAD_NORMAL_PRODUCTS = (
    "azmodel",
    "actor",
    "motion",
    "motionset",
    "animgraph",
    "pxmesh",
    "azmaterial",
)
RUNTIME_CHARACTER_PRODUCT_LOAD_APPROVED_SURFACE_KIND = "approved_character_spawnable"
RUNTIME_CHARACTER_PRODUCT_LOAD_UPDATED_REQUIRED_PRODUCTS = (
    *RUNTIME_CHARACTER_PRODUCT_LOAD_NORMAL_PRODUCTS,
    RUNTIME_CHARACTER_PRODUCT_LOAD_APPROVED_SURFACE_KIND,
)
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
RUNTIME_CHARACTER_PRODUCT_LOAD_SETTINGS_KEYS = (
    "/Amazon/MAXINE/RuntimeHarness/EnableCharacterProductLoadProbe",
    "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductCount",
    "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductSpecs",
    "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductSpecsHex",
    "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/TimeoutTicks",
    "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/RequireAllProductsReady",
    "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/<index>/Kind",
    "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/<index>/ProductPath",
    "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/<index>/CatalogPath",
    "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/<index>/ExpectedCategory",
)
RUNTIME_EXIT_FIXTURE_GATE_ENV = (
    "MAXINE_ENABLE_O3DE_RUNTIME_HARNESS=1",
    "MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS=1",
    "MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE=1",
)
RUNTIME_CHARACTER_PRODUCT_LOAD_GATE_ENV = ("MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE=1",)
RUNTIME_PROCPREFAB_HANDLER_OR_SURFACE_GATE_ENV = (
    "MAXINE_ENABLE_RUNTIME_PROCPREFAB_HANDLER_OR_SPAWNABLE_SURFACE=1",
)
RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV = ("MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE=1",)
RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV = (
    "MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION=1",
    "MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION=1",
)
RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_GATE_ENV = (
    "MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE=1",
    "MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE=1",
)
RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_GATE_ENV = (
    "MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE=1",
    "MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE=1",
)
RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV = ("MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION=1",)
RUNTIME_EXIT_FIXTURE_REBUILD_GATE_ENV = ("MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD=1",)
RUNTIME_EXIT_FIXTURE_TEMP_REGISTRY_PATCH_GATE_ENV = ("MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH=1",)
RUNTIME_EXIT_FIXTURE_CACHE_BOOTSTRAP_REFRESH_GATE_ENV = ("MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_REFRESH=1",)
RUNTIME_EXIT_FIXTURE_CACHE_BOOTSTRAP_MUTATION_GATE_ENV = ("MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION=1",)
RUNTIME_EXIT_FIXTURE_ASSET_PROCESSOR_SESSION_GATE_ENV = (
    "MAXINE_ALLOW_RUNTIME_FIXTURE_ASSET_PROCESSOR_SESSION=1",
)
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
RUNTIME_CHARACTER_PRODUCT_LOAD_PATCH_FILENAME = "maxine_runtime_character_product_load_probe.setreg"
RUNTIME_CHARACTER_SPAWN_INSTANTIATION_PATCH_FILENAME = "maxine_runtime_character_spawn_instantiation_probe.setreg"
RUNTIME_PRE_AUTOEXEC_SUPPRESSION_SELECTED = "project_registry_load_level_setreg_temporarily_disabled_pre_autoexec"
RUNTIME_PRE_AUTOEXEC_SUPPRESSION_DISABLED_FILENAME = "load_level.setreg.maxine_pre_autoexec_disabled"
RUNTIME_PRE_AUTOEXEC_SUPPRESSION_BACKUP_FILENAME = "maxine_runtime_pre_autoexec_load_level_setreg_backup.txt"
RUNTIME_PRE_AUTOEXEC_CACHE_BOOTSTRAP_BLOCKER = "blocked_by_project_cache_bootstrap_defaultlevel_autoload"
RUNTIME_CACHE_BOOTSTRAP_SELECTED = "cache_bootstrap_setreg_temporarily_neutralized_with_project_source_suppression"
RUNTIME_CACHE_BOOTSTRAP_BACKUP_DIRNAME = "maxine_runtime_cache_bootstrap_backups"
RUNTIME_SIGNAL_CLASSIFICATION_SELECTED = "ap_shader_no_defaultlevel_cache_bootstrap_fixture_rerun"
RUNTIME_CHARACTER_PRODUCT_LOAD_SELECTED = "runtime_character_product_load_generic_assetmanager_load"
RUNTIME_PROCPREFAB_HANDLER_SURFACE_SELECTED = "runtime_procprefab_handler_surface_source_diagnostic"
RUNTIME_CHARACTER_SPAWN_INSTANTIATION_SELECTED = "runtime_spawnable_entities_interface_spawn_all_entities_no_level_fixture"
RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_SELECTED = "runtime_emotionfx_animation_component_surface_on_approved_spawnable"
RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_MISSING_BLOCKER = (
    "runtime_animation_playback_surface_missing_on_approved_spawned_character"
)
RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_SELECTED = (
    "approved_prefab_animation_component_wiring_requires_source_validated_editor_generation"
)
RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_BLOCKER = (
    "blocked_by_approved_prefab_animation_component_wiring_requires_source_validated_editor_generation"
)
RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ASSET_ASSIGNMENT_BLOCKER = (
    "blocked_by_runtime_animation_component_asset_assignment_unverified"
)
RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ACTOR_ASSET_BLOCKER = (
    "blocked_by_runtime_actor_asset_assignment_unverified"
)
RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_MOTION_ASSET_BLOCKER = (
    "blocked_by_runtime_motion_asset_assignment_unverified"
)
RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ANIM_GRAPH_ASSET_BLOCKER = (
    "blocked_by_runtime_anim_graph_asset_assignment_unverified"
)
RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_MOTION_SET_ASSET_BLOCKER = (
    "blocked_by_runtime_motion_set_asset_assignment_unverified"
)
RUNTIME_ACTOR_SIMPLE_MOTION_AFTER_APB_GATE_ENV = (
    "MAXINE_ENABLE_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB=1",
    "MAXINE_ALLOW_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB=1",
)
RUNTIME_ANIMATION_PLAYBACK_EXECUTION_GATE_ENV = (
    "MAXINE_ENABLE_RUNTIME_ANIMATION_PLAYBACK_EXECUTION=1",
    "MAXINE_ALLOW_RUNTIME_ANIMATION_PLAYBACK_EXECUTION=1",
)
RUNTIME_ANIMATION_PLAYBACK_EXECUTION_SELECTED = (
    "runtime_simple_motion_request_bus_play_motion_and_get_play_time"
)
RUNTIME_ANIMATION_PLAYBACK_EXECUTION_OBSERVATION_BLOCKER = (
    "blocked_by_runtime_animation_playback_observation_unavailable"
)
RUNTIME_ANIMATION_PLAYBACK_TIME_NOT_ADVANCED_BLOCKER = (
    "blocked_by_runtime_motion_playback_time_not_advanced"
)
RUNTIME_PROCPREFAB_ASSET_TYPE = "{9B7C8459-471E-4EAD-A363-7990CC4065A9}"
RUNTIME_PROCPREFAB_ASSET_CLASS = "AZ::Prefab::ProceduralPrefabAsset"
RUNTIME_PROCPREFAB_HANDLER_MODULE = "Gem::PrefabBuilder.Builders"
RUNTIME_SPAWNABLE_ASSET_TYPE = "{855E3021-D305-4845-B284-20C3F7FDF16B}"
RUNTIME_SPAWNABLE_ASSET_CLASS = "AzFramework::Spawnable"
RUNTIME_SPAWNABLE_HANDLER = "AzFramework::SpawnableAssetHandler"
RUNTIME_SPAWNABLE_HANDLER_MODULE = "AzFramework::SpawnableSystemComponent"
RUNTIME_TRANSFORM_COMPONENT_TYPE_ID = "{22B10178-39B6-4C12-BB37-77DB45FDD3B6}"
RUNTIME_EMOTIONFX_ACTOR_COMPONENT_TYPE_ID = "{BDC97E7F-A054-448B-A26F-EA2B5D78E377}"
RUNTIME_EMOTIONFX_ANIM_GRAPH_COMPONENT_TYPE_ID = "{77624349-D5C4-4902-9F08-665814520999}"
RUNTIME_EMOTIONFX_SIMPLE_MOTION_COMPONENT_TYPE_ID = "{DBE3C105-6FC1-418F-A8B1-D0F29FE8D5BD}"
EDITOR_EMOTIONFX_ACTOR_COMPONENT_TYPE_ID = "{A863EE1B-8CFD-4EDD-BA0D-1CEC2879AD44}"
EDITOR_EMOTIONFX_ANIM_GRAPH_COMPONENT_TYPE_ID = "{770F0A71-59EA-413B-8DAB-235FB0FF1384}"
EDITOR_EMOTIONFX_SIMPLE_MOTION_COMPONENT_TYPE_ID = "{0CF1ADF7-DA51-4183-89EC-BDD7D2E17D36}"
RUNTIME_EMOTIONFX_ACTOR_ASSET_TYPE_ID = "{F67CC648-EA51-464C-9F5D-4A9CE41A7F86}"
RUNTIME_EMOTIONFX_MOTION_ASSET_TYPE_ID = "{00494B8E-7578-4BA2-8B28-272E90680787}"
RUNTIME_EMOTIONFX_MOTION_SET_ASSET_TYPE_ID = "{1DA936A0-F766-4B2F-B89C-9F4C8E1310F9}"
RUNTIME_EMOTIONFX_ANIM_GRAPH_ASSET_TYPE_ID = "{28003359-4A29-41AE-8198-0AEFE9FF5263}"
RUNTIME_CHARACTER_PREFAB_SOURCE_REPO_REF = (
    "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
)
RUNTIME_CHARACTER_PREFAB_SOURCE_PROJECT_REF = "Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
RUNTIME_CHARACTER_PREFAB_APPROVED_DEPENDENCY = "assets/characters/maxine/release/maxine_idle_fbx.procprefab"
RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_PRODUCT = (
    "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable"
)
RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_CATALOG = (
    "assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable"
)
RUNTIME_CHARACTER_APPROVED_ACTOR_ASSET_ID = "{7E3BE43C-A0C7-512B-9F3E-FA6C2A4DBDAC}:914f19b7"
RUNTIME_CHARACTER_APPROVED_MOTION_ASSET_ID = "{794D1588-3C41-5795-8A9A-EEBD6A663A60}:ddcbe0"
APPROVED_MOTION_PRODUCT_HANDLER_SIGNAL_CLASSIFICATION = (
    "harmless_shutdown_handler_unregister_after_verified_motion_load"
)
APPROVED_MOTION_PRODUCT_HANDLER_SIGNAL_BLOCKER = (
    "blocked_by_runtime_motion_product_load_handler_unregistered"
)
APPROVED_MOTION_PRODUCT_HANDLER_SIGNAL_READBACK_BLOCKER = (
    "blocked_by_runtime_motion_assignment_readback_unverified"
)
RUNTIME_SHUTDOWN_POOLALLOCATOR_SIGNAL_CLASSIFICATION = "real_runtime_shutdown_poolallocator_assertion"
RUNTIME_SHUTDOWN_POOLALLOCATOR_SIGNAL_BLOCKER = "blocked_by_runtime_shutdown_poolallocator_assertion"
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
    diagnose_runtime_pre_autoexec_loadlevel_suppression: bool = False,
    enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression: bool = False,
    diagnose_runtime_cache_bootstrap_loadlevel_source: bool = False,
    enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source: bool = False,
    diagnose_runtime_ap_shader_signals: bool = False,
    enable_runtime_exit_fixture_ap_shader_signal_classification: bool = False,
    diagnose_runtime_character_product_load: bool = False,
    enable_runtime_character_product_load_fixture: bool = False,
    diagnose_runtime_procprefab_handler_or_spawnable_surface: bool = False,
    diagnose_runtime_character_spawnable_surface: bool = False,
    diagnose_runtime_character_prefab_source: bool = False,
    diagnose_runtime_character_spawn_instantiation: bool = False,
    enable_runtime_character_spawn_instantiation_fixture: bool = False,
    diagnose_runtime_character_animation_playback_surface: bool = False,
    enable_runtime_character_animation_playback_surface_fixture: bool = False,
    diagnose_runtime_character_animation_component_wiring_surface: bool = False,
    enable_runtime_character_animation_component_wiring_surface_fixture: bool = False,
    diagnose_runtime_actor_simple_motion_component_wiring_after_apb: bool = False,
    enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture: bool = False,
    diagnose_approved_motion_product_handler_unregistered_signal: bool = False,
    diagnose_runtime_shutdown_poolallocator_assertions: bool = False,
    enable_runtime_poolallocator_signal_classification_fixture: bool = False,
    diagnose_runtime_animation_playback_execution_api: bool = False,
    enable_runtime_animation_playback_execution_fixture: bool = False,
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
        and not diagnose_runtime_pre_autoexec_loadlevel_suppression
        and not enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression
        and not diagnose_runtime_cache_bootstrap_loadlevel_source
        and not enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source
        and not diagnose_runtime_ap_shader_signals
        and not enable_runtime_exit_fixture_ap_shader_signal_classification
        and not diagnose_runtime_character_product_load
        and not enable_runtime_character_product_load_fixture
        and not diagnose_runtime_procprefab_handler_or_spawnable_surface
        and not diagnose_runtime_character_spawnable_surface
        and not diagnose_runtime_character_prefab_source
        and not diagnose_runtime_character_spawn_instantiation
        and not enable_runtime_character_spawn_instantiation_fixture
        and not diagnose_runtime_character_animation_playback_surface
        and not enable_runtime_character_animation_playback_surface_fixture
        and not diagnose_runtime_character_animation_component_wiring_surface
        and not enable_runtime_character_animation_component_wiring_surface_fixture
        and not diagnose_runtime_actor_simple_motion_component_wiring_after_apb
        and not enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
        and not diagnose_approved_motion_product_handler_unregistered_signal
        and not diagnose_runtime_shutdown_poolallocator_assertions
        and not enable_runtime_poolallocator_signal_classification_fixture
        and not diagnose_runtime_animation_playback_execution_api
        and not enable_runtime_animation_playback_execution_fixture
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
            and not diagnose_runtime_pre_autoexec_loadlevel_suppression
            and not enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression
            and not diagnose_runtime_cache_bootstrap_loadlevel_source
            and not enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source
            and not diagnose_runtime_ap_shader_signals
            and not enable_runtime_exit_fixture_ap_shader_signal_classification
            and not diagnose_runtime_character_product_load
            and not enable_runtime_character_product_load_fixture
            and not diagnose_runtime_procprefab_handler_or_spawnable_surface
            and not diagnose_runtime_character_spawnable_surface
            and not diagnose_runtime_character_prefab_source
            and not diagnose_runtime_character_spawn_instantiation
            and not enable_runtime_character_spawn_instantiation_fixture
            and not diagnose_runtime_character_animation_playback_surface
            and not enable_runtime_character_animation_playback_surface_fixture
            and not diagnose_runtime_character_animation_component_wiring_surface
            and not enable_runtime_character_animation_component_wiring_surface_fixture
            and not diagnose_runtime_actor_simple_motion_component_wiring_after_apb
            and not enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
            and not diagnose_approved_motion_product_handler_unregistered_signal
            and not diagnose_runtime_shutdown_poolallocator_assertions
            and not enable_runtime_poolallocator_signal_classification_fixture
            and not diagnose_runtime_animation_playback_execution_api
            and not enable_runtime_animation_playback_execution_fixture
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
            else "runtime_pre_autoexec_loadlevel_suppression_diagnostic"
            if diagnose_runtime_pre_autoexec_loadlevel_suppression
            else "runtime_exit_fixture_pre_autoexec_loadlevel_suppression_command"
            if enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression
            else "runtime_cache_bootstrap_loadlevel_source_diagnostic"
            if diagnose_runtime_cache_bootstrap_loadlevel_source
            else "runtime_exit_fixture_cache_bootstrap_loadlevel_source_command"
            if enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source
            else "runtime_ap_shader_signal_classification_diagnostic"
            if diagnose_runtime_ap_shader_signals
            else "runtime_exit_fixture_ap_shader_signal_classification_command"
            if enable_runtime_exit_fixture_ap_shader_signal_classification
            else "runtime_character_product_load_diagnostic"
            if diagnose_runtime_character_product_load
            else "runtime_character_product_load_fixture_command"
            if enable_runtime_character_product_load_fixture
            else "runtime_procprefab_handler_or_surface_diagnostic"
            if diagnose_runtime_procprefab_handler_or_spawnable_surface
            else "runtime_character_spawnable_surface_diagnostic"
            if diagnose_runtime_character_spawnable_surface
            else "runtime_character_prefab_source_diagnostic"
            if diagnose_runtime_character_prefab_source
            else "runtime_character_spawn_instantiation_diagnostic"
            if diagnose_runtime_character_spawn_instantiation
            else "runtime_character_spawn_instantiation_fixture_command"
            if enable_runtime_character_spawn_instantiation_fixture
            else "runtime_character_animation_playback_surface_diagnostic"
            if diagnose_runtime_character_animation_playback_surface
            else "runtime_character_animation_playback_surface_fixture_command"
            if enable_runtime_character_animation_playback_surface_fixture
            else "runtime_character_animation_component_wiring_surface_diagnostic"
            if diagnose_runtime_character_animation_component_wiring_surface
            else "runtime_character_animation_component_wiring_surface_fixture_command"
            if enable_runtime_character_animation_component_wiring_surface_fixture
            else "runtime_actor_simple_motion_component_wiring_after_apb_diagnostic"
            if diagnose_runtime_actor_simple_motion_component_wiring_after_apb
            else "runtime_actor_simple_motion_component_wiring_after_apb_fixture_command"
            if enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
            else "approved_motion_product_handler_unregistered_signal_diagnostic"
            if diagnose_approved_motion_product_handler_unregistered_signal
            else "runtime_shutdown_poolallocator_assertions_diagnostic"
            if diagnose_runtime_shutdown_poolallocator_assertions
            else "runtime_poolallocator_signal_classification_fixture_command"
            if enable_runtime_poolallocator_signal_classification_fixture
            else "runtime_animation_playback_execution_api_diagnostic"
            if diagnose_runtime_animation_playback_execution_api
            else "runtime_animation_playback_execution_fixture_command"
            if enable_runtime_animation_playback_execution_fixture
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
        and not diagnose_runtime_pre_autoexec_loadlevel_suppression
        and not enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression
        and not diagnose_runtime_cache_bootstrap_loadlevel_source
        and not enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source
        and not diagnose_runtime_ap_shader_signals
        and not enable_runtime_exit_fixture_ap_shader_signal_classification
        and not diagnose_runtime_character_product_load
        and not enable_runtime_character_product_load_fixture
        and not diagnose_runtime_procprefab_handler_or_spawnable_surface
        and not diagnose_runtime_character_spawnable_surface
        and not diagnose_runtime_character_prefab_source
        and not diagnose_runtime_character_spawn_instantiation
        and not enable_runtime_character_spawn_instantiation_fixture
        and not diagnose_runtime_character_animation_playback_surface
        and not enable_runtime_character_animation_playback_surface_fixture
        and not diagnose_runtime_character_animation_component_wiring_surface
        and not enable_runtime_character_animation_component_wiring_surface_fixture
        and not diagnose_runtime_actor_simple_motion_component_wiring_after_apb
        and not enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
        and not diagnose_approved_motion_product_handler_unregistered_signal
        and not diagnose_runtime_shutdown_poolallocator_assertions
        and not enable_runtime_poolallocator_signal_classification_fixture
        and not diagnose_runtime_animation_playback_execution_api
        and not enable_runtime_animation_playback_execution_fixture
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

    if diagnose_runtime_pre_autoexec_loadlevel_suppression:
        return _run_runtime_pre_autoexec_suppression_diagnostic(
            report,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_cache_bootstrap_loadlevel_source:
        return _run_runtime_cache_bootstrap_diagnostic(
            report,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_ap_shader_signals:
        return _run_runtime_ap_shader_signal_diagnostic(
            report,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_character_product_load:
        return _run_runtime_character_product_load_diagnostic(
            report,
            product_evidence=product_evidence,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_procprefab_handler_or_spawnable_surface:
        return _run_runtime_procprefab_handler_or_surface_diagnostic(
            report,
            product_evidence=product_evidence,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_character_spawnable_surface:
        return _run_runtime_character_spawnable_surface_diagnostic(
            report,
            product_evidence=product_evidence,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_character_prefab_source:
        return _run_runtime_character_prefab_source_diagnostic(
            report,
            product_evidence=product_evidence,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_character_spawn_instantiation:
        return _run_runtime_character_spawn_instantiation_diagnostic(
            report,
            product_evidence=product_evidence,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_character_animation_playback_surface:
        return _run_runtime_character_animation_playback_surface_diagnostic(
            report,
            product_evidence=product_evidence,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_character_animation_component_wiring_surface:
        return _run_runtime_character_animation_component_wiring_surface_diagnostic(
            report,
            product_evidence=product_evidence,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_actor_simple_motion_component_wiring_after_apb:
        return _run_runtime_actor_simple_motion_component_wiring_after_apb_diagnostic(
            report,
            product_evidence=product_evidence,
            engine_root=selected_engine,
            project=selected_project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

    if diagnose_approved_motion_product_handler_unregistered_signal:
        return _run_approved_motion_product_handler_signal_diagnostic(
            report,
            engine_root=selected_engine,
            project=selected_project,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_shutdown_poolallocator_assertions:
        return _run_runtime_shutdown_poolallocator_signal_diagnostic(
            report,
            engine_root=selected_engine,
            project=selected_project,
            artifact_dir=artifact_dir,
        )

    if diagnose_runtime_animation_playback_execution_api:
        return _run_runtime_animation_playback_execution_api_diagnostic(
            report,
            product_evidence=product_evidence,
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
        or enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression
        or enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source
        or enable_runtime_exit_fixture_ap_shader_signal_classification
        or enable_runtime_character_product_load_fixture
        or enable_runtime_character_spawn_instantiation_fixture
        or enable_runtime_character_animation_playback_surface_fixture
        or enable_runtime_character_animation_component_wiring_surface_fixture
        or enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
        or enable_runtime_poolallocator_signal_classification_fixture
        or enable_runtime_animation_playback_execution_fixture
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
            pre_autoexec_suppression=enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression,
            cache_bootstrap_strategy=(
                enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source
                or enable_runtime_exit_fixture_ap_shader_signal_classification
                or enable_runtime_character_product_load_fixture
                or enable_runtime_character_spawn_instantiation_fixture
                or enable_runtime_character_animation_playback_surface_fixture
                or enable_runtime_character_animation_component_wiring_surface_fixture
                or enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
                or enable_runtime_poolallocator_signal_classification_fixture
                or enable_runtime_animation_playback_execution_fixture
            ),
            ap_shader_signal_classification=(
                enable_runtime_exit_fixture_ap_shader_signal_classification
                or enable_runtime_character_product_load_fixture
                or enable_runtime_character_spawn_instantiation_fixture
                or enable_runtime_character_animation_playback_surface_fixture
                or enable_runtime_character_animation_component_wiring_surface_fixture
                or enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
                or enable_runtime_poolallocator_signal_classification_fixture
                or enable_runtime_animation_playback_execution_fixture
            ),
            character_product_load=enable_runtime_character_product_load_fixture
            or enable_runtime_character_spawn_instantiation_fixture
            or enable_runtime_character_animation_playback_surface_fixture
            or enable_runtime_character_animation_component_wiring_surface_fixture
            or enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
            or enable_runtime_poolallocator_signal_classification_fixture
            or enable_runtime_animation_playback_execution_fixture,
            character_spawn_instantiation=enable_runtime_character_spawn_instantiation_fixture
            or enable_runtime_character_animation_playback_surface_fixture
            or enable_runtime_character_animation_component_wiring_surface_fixture
            or enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
            or enable_runtime_poolallocator_signal_classification_fixture
            or enable_runtime_animation_playback_execution_fixture,
            character_animation_playback_surface=enable_runtime_character_animation_playback_surface_fixture
            or enable_runtime_character_animation_component_wiring_surface_fixture
            or enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
            or enable_runtime_poolallocator_signal_classification_fixture
            or enable_runtime_animation_playback_execution_fixture,
            character_animation_component_wiring_surface=enable_runtime_character_animation_component_wiring_surface_fixture
            or enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
            or enable_runtime_poolallocator_signal_classification_fixture
            or enable_runtime_animation_playback_execution_fixture,
            actor_simple_motion_component_wiring_after_apb=enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
            or enable_runtime_poolallocator_signal_classification_fixture
            or enable_runtime_animation_playback_execution_fixture,
            poolallocator_signal_classification=enable_runtime_poolallocator_signal_classification_fixture,
            animation_playback_execution=enable_runtime_animation_playback_execution_fixture,
            product_evidence=product_evidence,
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
    if report.get("asset_cache_deleted") is True:
        result.add_error(MXN_PATH_UNSAFE, "Runtime harness must not delete Asset Cache.")

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
    if report.get("runtime_pre_autoexec_suppression_verified") is True:
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_pre_autoexec_suppression_verified=true requires verified runtime execution.")
        if str(report.get("runtime_launch_hygiene_status", "")).strip() != "runtime_launch_hygiene_pass":
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_pre_autoexec_suppression_verified=true requires runtime_launch_hygiene_pass.")
        if report.get("runtime_default_level_autoload_detected") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_pre_autoexec_suppression_verified=true cannot allow defaultlevel autoload.")
        if not str(report.get("runtime_pre_autoexec_selected", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_pre_autoexec_suppression_verified=true requires a selected pre-autoexec suppression.")
        if report.get("runtime_pre_autoexec_candidate_reversible") is not True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_pre_autoexec_suppression_verified=true requires a reversible suppression candidate.")
        if report.get("runtime_pre_autoexec_candidate_mutation_restored") is not True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_pre_autoexec_suppression_verified=true requires restored project registry mutation.")
    if report.get("runtime_cache_bootstrap_verified") is True:
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_cache_bootstrap_verified=true requires verified runtime execution.")
        if str(report.get("runtime_launch_hygiene_status", "")).strip() != "runtime_launch_hygiene_pass":
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_cache_bootstrap_verified=true requires runtime_launch_hygiene_pass.")
        if report.get("runtime_default_level_autoload_detected") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_cache_bootstrap_verified=true cannot allow defaultlevel autoload.")
        if not str(report.get("runtime_cache_bootstrap_selected", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_cache_bootstrap_verified=true requires a selected cache-bootstrap strategy.")
        if report.get("runtime_cache_bootstrap_candidate_reversible") is not True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_cache_bootstrap_verified=true requires a reversible cache-bootstrap candidate.")
        if str(report.get("runtime_cache_bootstrap_candidate_restore_status", "")).strip() != "runtime_cache_bootstrap_restore_pass":
            result.add_error(MXN_PATH_UNSAFE, "runtime_cache_bootstrap_verified=true requires restored cache/bootstrap mutation.")
        if report.get("runtime_cache_bootstrap_candidate_hash_verified") is not True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_cache_bootstrap_verified=true requires cache/bootstrap hash verification.")
    if report.get("runtime_signal_classification_verified") is True:
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_signal_classification_verified=true requires verified runtime execution.")
        if str(report.get("runtime_launch_hygiene_status", "")).strip() != "runtime_launch_hygiene_pass":
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_signal_classification_verified=true requires runtime_launch_hygiene_pass.")
        if not str(report.get("runtime_signal_classification_selected", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_signal_classification_verified=true requires a selected AP/shader strategy.")
        ap_refs = report.get("runtime_asset_processor_negotiation_source_refs", [])
        shader_refs = report.get("runtime_shader_serializer_source_refs", [])
        ap_conditions = report.get("runtime_asset_processor_negotiation_harmless_only_if", [])
        shader_conditions = report.get("runtime_shader_serializer_harmless_only_if", [])
        ap_present = report.get("runtime_asset_processor_negotiation_signal_present") is True
        shader_present = report.get("runtime_shader_serializer_signal_present") is True
        if not ap_refs or not shader_refs or (ap_present and not ap_conditions) or (shader_present and not shader_conditions):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_signal_classification_verified=true requires AP and shader source refs plus harmless-only constraints.",
            )
        if report.get("runtime_asset_processor_negotiation_disqualifying") is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_signal_classification_verified=true cannot allow disqualifying AP signals.")
        if report.get("runtime_shader_serializer_disqualifying") is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_signal_classification_verified=true cannot allow disqualifying shader signals.")
    if report.get("runtime_character_product_load_claimed") is True and report.get("runtime_character_product_load_verified") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime character product-load proof cannot be claimed without verified product-load evidence.")
    if report.get("runtime_procprefab_direct_load_claimed") is True and report.get("runtime_procprefab_direct_load_verified") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime direct .procprefab load proof cannot be claimed without verified direct-load evidence.")
    if report.get("runtime_procprefab_direct_load_verified") is True:
        if str(report.get("runtime_procprefab_direct_load_handler_status", "")).strip() != "runtime_procprefab_direct_load_handler_registered":
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_procprefab_direct_load_verified=true requires a registered runtime handler.",
            )
        if report.get("runtime_procprefab_direct_load_supported") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_procprefab_direct_load_verified=true requires direct runtime load support.")
        if not str(report.get("runtime_procprefab_direct_load_asset_id", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_procprefab_direct_load_verified=true requires .procprefab AssetId evidence.")
        if not str(report.get("runtime_procprefab_direct_load_asset_type", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_procprefab_direct_load_verified=true requires .procprefab AssetType evidence.")
    if report.get("runtime_procprefab_runtime_equivalent_surface_claimed") is True and report.get(
        "runtime_procprefab_runtime_equivalent_surface_verified"
    ) is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime equivalent prefab/spawnable surface proof cannot be claimed without verified surface evidence.",
        )
    if report.get("runtime_character_spawnable_surface_claimed") is True and report.get(
        "runtime_character_spawnable_surface_verified"
    ) is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "runtime_character_spawnable_surface_claimed=true requires verified approved surface.",
        )
    if report.get("runtime_character_spawnable_surface_verified") is True:
        selected_surface = str(report.get("runtime_character_spawnable_surface_selected", "")).strip().lower().replace("\\", "/")
        if not selected_surface:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_spawnable_surface_verified=true requires selected surface evidence.")
        if selected_surface.startswith("pc/levels/") or selected_surface.startswith("levels/") or "defaultlevel" in selected_surface:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_spawnable_surface_verified=true cannot use level/defaultlevel spawnables.")
        if report.get("runtime_character_spawnable_surface_found") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_spawnable_surface_verified=true requires found approved character surface.")
    if report.get("runtime_character_prefab_source_is_approved") is True:
        source_path = str(report.get("runtime_character_prefab_source_path", "")).strip().lower().replace("\\", "/")
        if not source_path:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_prefab_source_is_approved=true requires source path evidence.")
        if report.get("runtime_character_prefab_source_owned_by_repo") is not True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_prefab_source_is_approved=true requires repo-owned source evidence.")
        if report.get("runtime_character_prefab_source_is_defaultlevel") is True or "defaultlevel" in source_path:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_prefab_source_is_approved=true cannot use defaultlevel content.")
        if report.get("runtime_character_prefab_source_is_production_level") is True or "/production/" in source_path:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_prefab_source_is_approved=true cannot use production level content.")
        if report.get("runtime_character_prefab_source_is_temp") is True or "_maxine_smoke" in source_path:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_prefab_source_is_approved=true cannot use temp-only source content.")
        if report.get("runtime_character_prefab_source_is_generic_transform_only") is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_prefab_source_is_approved=true cannot be generic Transform-only content.",
            )
        if report.get("runtime_character_prefab_source_is_character_specific") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_prefab_source_is_approved=true requires character-specific approved product references.",
            )
    if report.get("runtime_character_product_load_verified") is True:
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true requires verified command-envelope runtime execution.")
        if report.get("runtime_exit_fixture_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true requires verified runtime exit fixture execution.")
        if str(report.get("runtime_launch_hygiene_status", "")).strip() != "runtime_launch_hygiene_pass":
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true requires runtime_launch_hygiene_pass.")
        if report.get("runtime_signal_classification_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true requires PR #137 AP/shader signal classification.")
        if report.get("runtime_cache_bootstrap_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true requires verified cache-bootstrap no-defaultlevel strategy.")
        if report.get("runtime_default_level_autoload_detected") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_product_load_verified=true cannot allow defaultlevel autoload.")
        if report.get("runtime_production_level_loaded") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_product_load_verified=true cannot allow production level loads.")
        if not str(report.get("runtime_character_product_load_selected_strategy", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true requires a selected product-load strategy.")
        if not report.get("runtime_character_product_load_source_refs", []):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true requires source validation refs.")
        if report.get("runtime_character_product_load_required_products_complete") is not True:
            result.add_error(MXN_ASSET_PRODUCT_MISSING, "runtime_character_product_load_verified=true requires complete APB product evidence for required products.")
        if report.get("runtime_character_product_load_all_required_ready") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_product_load_verified=true requires every required selected product ready.",
            )
        if report.get("runtime_character_product_load_missing_products"):
            result.add_error(MXN_ASSET_PRODUCT_MISSING, "runtime_character_product_load_verified=true cannot have missing selected products.")
        if report.get("runtime_character_product_load_timed_out_products"):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true cannot have timed-out selected products.")
        if report.get("runtime_character_product_load_failed_products"):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true cannot have failed selected products.")
        products = report.get("runtime_character_product_load_products", [])
        if not isinstance(products, list) or not products:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true requires per-product evidence.")
        elif any(not isinstance(product, Mapping) or product.get("ready") is not True for product in products):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_product_load_verified=true requires every required selected product ready.",
            )
        elif any(not str(product.get("asset_id", "")).strip() for product in products if isinstance(product, Mapping)):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_product_load_verified=true requires per-product AssetId evidence.")
        if (
            report.get("runtime_character_product_load_contract_updated") is True
            and report.get("runtime_character_product_load_runtime_equivalent_required") is True
            and report.get("runtime_procprefab_runtime_equivalent_surface_verified") is not True
        ):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_product_load_verified=true under updated product-load contract requires verified runtime-equivalent prefab/spawnable surface.",
            )
        if (
            report.get("runtime_character_product_load_contract_updated") is True
            and report.get("runtime_character_product_load_runtime_equivalent_required") is True
            and str(report.get("runtime_character_product_load_runtime_equivalent_surface_kind", "")).strip()
            == "approved_character_spawnable"
            and report.get("runtime_character_spawnable_surface_verified") is not True
        ):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_product_load_verified=true requires verified approved runtime character spawnable surface.",
            )
    if report.get("runtime_character_product_load_is_instantiation_proof") is True and report.get("runtime_character_instantiation_verified") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime product-load proof is not runtime instantiation proof.")
    if report.get("runtime_runtime_character_product_load_is_instantiation_proof") is True and report.get("runtime_character_instantiation_verified") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime product-load proof is not runtime instantiation proof.")
    if report.get("runtime_character_spawn_instantiation_claimed") is True and report.get(
        "runtime_character_spawn_instantiation_verified"
    ) is not True:
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "Runtime character spawn-instantiation proof cannot be claimed without verified spawn evidence.",
        )
    if report.get("runtime_character_spawn_instantiation_verified") is True:
        if report.get("runtime_character_product_load_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_spawn_instantiation_verified=true requires verified approved spawnable product-load prerequisite.",
            )
        if report.get("runtime_character_spawnable_surface_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_spawn_instantiation_verified=true requires verified approved runtime character spawnable surface.",
            )
        if not str(report.get("runtime_character_spawn_instantiation_api", "")).strip():
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_spawn_instantiation_verified=true requires source-validated spawn API evidence.")
        if not report.get("runtime_character_spawn_instantiation_source_refs", []):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_spawn_instantiation_verified=true requires spawn API source refs.")
        if report.get("runtime_character_spawn_instantiation_spawn_request_issued") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_spawn_instantiation_verified=true requires spawn request evidence.")
        if report.get("runtime_character_spawn_instantiation_spawn_completion_observed") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_spawn_instantiation_verified=true requires spawn completion evidence.")
        if _int_or_zero(report.get("runtime_character_spawn_instantiation_spawned_entity_count", 0)) <= 0:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_spawn_instantiation_verified=true requires positive spawned entity evidence.",
            )
        if report.get("runtime_character_spawn_instantiation_timeout") is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_spawn_instantiation_verified=true cannot have spawn timeout.")
        if report.get("runtime_character_spawn_instantiation_log_errors"):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_spawn_instantiation_verified=true cannot have selected spawnable spawn/load errors.")
        cleanup_status = str(report.get("runtime_character_spawn_instantiation_cleanup_status", "")).strip()
        if cleanup_status not in {
            "runtime_character_spawn_instantiation_cleanup_complete",
            "runtime_character_spawn_instantiation_cleanup_not_required",
        }:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_spawn_instantiation_verified=true requires cleanup/despawn completion or not-required status.")
        if report.get("runtime_default_level_autoload_detected") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_spawn_instantiation_verified=true cannot allow defaultlevel autoload.")
        if report.get("runtime_production_level_loaded") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_spawn_instantiation_verified=true cannot allow production level loads.")
        if report.get("runtime_character_spawn_instantiation_is_animation_proof") is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime spawn-instantiation proof is not runtime animation proof.")
    if report.get("runtime_character_instantiation_claimed") is True and report.get("runtime_character_instantiation_verified") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime character instantiation proof cannot be claimed without verified instantiation evidence.")
    if report.get("runtime_character_animation_claimed") is True and report.get("runtime_character_animation_verified") is not True:
        result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime character animation proof cannot be claimed without verified animation evidence.")
    if (
        report.get("runtime_exit_fixture_runtime_command_uses_animation_playback_surface_probe") is True
        and report.get("runtime_execution_status") == "runtime_execution_pass"
        and not _runtime_character_animation_source_validation_passed(report)
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "runtime animation playback surface fixture cannot pass without positive source validation.",
        )
    if (
        report.get("runtime_exit_fixture_runtime_command_uses_animation_component_wiring_surface_probe") is True
        and report.get("runtime_execution_status") == "runtime_execution_pass"
        and not _runtime_character_animation_component_wiring_source_validation_passed(report)
    ):
        result.add_error(
            MXN_RUNTIME_SMOKE_FAIL,
            "runtime animation component wiring surface fixture cannot pass without positive source validation.",
        )
    if report.get("runtime_character_animation_verified") is True:
        if report.get("runtime_execution_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires verified runtime execution.")
        if report.get("runtime_character_animation_playback_surface_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_animation_verified=true requires verified runtime animation playback surface.",
            )
        if not report.get("runtime_character_animation_source_refs", []):
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires source-validated animation API refs.")
        if report.get("runtime_character_animation_spawn_prerequisite_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires verified spawn prerequisite.")
        if report.get("runtime_character_animation_product_load_prerequisite_verified") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires verified product-load prerequisite.")
        if report.get("runtime_character_animation_actor_component_found") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires a runtime Actor component surface.")
        if not (
            report.get("runtime_character_animation_anim_graph_component_found") is True
            or report.get("runtime_character_animation_simple_motion_component_found") is True
        ):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_animation_verified=true requires Anim Graph or Simple Motion runtime component surface.",
            )
        if report.get("runtime_character_animation_playback_attempted") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires playback attempt evidence.")
        if report.get("runtime_character_animation_playback_request_issued") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires observed playback evidence.")
        if report.get("runtime_character_animation_playback_started") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires observed playback evidence.")
        if report.get("runtime_character_animation_playback_observed") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires observed playback evidence.")
        if _int_or_zero(report.get("runtime_character_animation_playback_tick_count", 0)) <= 0:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires bounded tick evidence.")
        if report.get("runtime_character_animation_playback_cleanup_complete") is not True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "runtime_character_animation_verified=true requires cleanup/despawn completion.")
        if report.get("runtime_default_level_autoload_detected") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_animation_verified=true cannot allow defaultlevel autoload.")
        if report.get("runtime_production_level_loaded") is True:
            result.add_error(MXN_PATH_UNSAFE, "runtime_character_animation_verified=true cannot allow production level loads.")
        if report.get("runtime_character_animation_is_full_character_proof") is True:
            result.add_error(MXN_RUNTIME_SMOKE_FAIL, "Runtime animation playback proof is not full runtime character proof.")
    if report.get("runtime_character_animation_component_wiring_verified") is True:
        if report.get("runtime_character_animation_component_wiring_claimed") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_animation_component_wiring_verified=true requires runtime_character_animation_component_wiring_claimed=true.",
            )
        if report.get("runtime_character_animation_component_wiring_source_validation_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_animation_component_wiring_verified=true requires positive source validation.",
            )
        if report.get("runtime_character_animation_component_wiring_product_load_prerequisite_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_animation_component_wiring_verified=true requires product-load prerequisite verification.",
            )
        if report.get("runtime_character_animation_component_wiring_spawn_prerequisite_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_animation_component_wiring_verified=true requires spawn prerequisite verification.",
            )
        if not report.get("runtime_character_animation_component_wiring_runtime_component_inventory", []):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_animation_component_wiring_verified=true requires runtime component inventory.",
            )
        has_actor = report.get("runtime_character_animation_component_wiring_runtime_actor_component_found") is True
        has_playback_component = (
            report.get("runtime_character_animation_component_wiring_runtime_simple_motion_component_found") is True
            or report.get("runtime_character_animation_component_wiring_runtime_anim_graph_component_found") is True
        )
        if not (has_actor and has_playback_component):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_character_animation_component_wiring_verified=true requires runtime Actor plus Simple Motion or Anim Graph components.",
            )
        actor_asset_assignment_verified = (
            report.get("runtime_character_animation_component_wiring_actor_asset_assignment_verified") is True
        )
        motion_asset_assignment_verified = (
            report.get("runtime_character_animation_component_wiring_motion_asset_assignment_verified") is True
        )
        anim_graph_asset_assignment_verified = (
            report.get("runtime_character_animation_component_wiring_anim_graph_asset_assignment_verified") is True
        )
        motion_set_asset_assignment_verified = (
            report.get("runtime_character_animation_component_wiring_motion_set_asset_assignment_verified") is True
        )
        has_simple_motion = report.get("runtime_character_animation_component_wiring_runtime_simple_motion_component_found") is True
        has_anim_graph = report.get("runtime_character_animation_component_wiring_runtime_anim_graph_component_found") is True
        simple_motion_wiring_ready = bool(
            has_actor and has_simple_motion and actor_asset_assignment_verified and motion_asset_assignment_verified
        )
        anim_graph_wiring_ready = bool(
            has_actor
            and has_anim_graph
            and actor_asset_assignment_verified
            and anim_graph_asset_assignment_verified
            and motion_set_asset_assignment_verified
        )
        if has_actor and has_playback_component and not (simple_motion_wiring_ready or anim_graph_wiring_ready):
            if not actor_asset_assignment_verified:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    "runtime_character_animation_component_wiring_verified=true requires runtime Actor asset assignment evidence.",
                )
            if has_simple_motion and not motion_asset_assignment_verified:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    "runtime_character_animation_component_wiring_verified=true requires runtime Motion asset assignment evidence.",
                )
            if has_anim_graph and not anim_graph_asset_assignment_verified:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    "runtime_character_animation_component_wiring_verified=true requires runtime Anim Graph asset assignment evidence.",
                )
            if has_anim_graph and not motion_set_asset_assignment_verified:
                result.add_error(
                    MXN_RUNTIME_SMOKE_FAIL,
                    "runtime_character_animation_component_wiring_verified=true requires runtime Motion Set asset assignment evidence.",
                )
        if report.get("production_level_mutation") is True or report.get("defaultlevel_mutation") is True:
            result.add_error(
                MXN_PATH_UNSAFE,
                "runtime_character_animation_component_wiring_verified=true cannot rely on production/defaultlevel mutation.",
            )
        if report.get("runtime_character_proof_claimed") is True or report.get("runtime_character_proof_verified") is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime animation component wiring proof is not full runtime character proof.",
            )
    if report.get("runtime_actor_simple_motion_component_wiring_after_apb_verified") is True:
        if report.get("runtime_actor_simple_motion_component_wiring_after_apb_attempted") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires attempted=true.",
            )
        if report.get("runtime_actor_simple_motion_component_wiring_after_apb_completed") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires completed=true.",
            )
        if report.get("apb_after_source_prefab_update_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires verified APB evidence.",
            )
        if report.get("approved_spawnable_regenerated_or_found") is not True:
            result.add_error(
                MXN_ASSET_PRODUCT_MISSING,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires approved spawnable evidence.",
            )
        if report.get("product_matrix_complete_after_source_prefab_update") is not True:
            result.add_error(
                MXN_ASSET_PRODUCT_MISSING,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires complete product matrix evidence.",
            )
        if report.get("runtime_character_animation_component_wiring_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires verified runtime component wiring.",
            )
        if report.get("runtime_character_animation_component_wiring_runtime_actor_component_found") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires runtime Actor component TypeId.",
            )
        if report.get("runtime_character_animation_component_wiring_runtime_simple_motion_component_found") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires runtime Simple Motion component TypeId.",
            )
        if report.get("runtime_character_animation_component_wiring_runtime_actor_asset_assignment_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires runtime Actor asset assignment evidence.",
            )
        if report.get("runtime_character_animation_component_wiring_runtime_motion_asset_assignment_verified") is not True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime_actor_simple_motion_component_wiring_after_apb_verified=true requires runtime Motion asset assignment evidence.",
            )
        if report.get("runtime_character_animation_verified") is True and not _runtime_animation_playback_execution_fixture_passed(report):
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime Actor + Simple Motion component wiring after APB is not animation playback without bounded playback execution proof.",
            )
        if report.get("runtime_character_proof_verified") is True:
            result.add_error(
                MXN_RUNTIME_SMOKE_FAIL,
                "runtime Actor + Simple Motion component wiring after APB is not full character proof.",
            )
    if (
        report.get("runtime_cache_bootstrap_candidate_attempted") is True
        and report.get("runtime_cache_bootstrap_candidate_mutates_cache") is True
    ):
        if str(report.get("runtime_cache_bootstrap_candidate_restore_status", "")).strip() != "runtime_cache_bootstrap_restore_pass":
            result.add_error(MXN_PATH_UNSAFE, "Cache/bootstrap mutation attempts must restore generated bootstrap files.")
        if report.get("runtime_cache_bootstrap_candidate_hash_verified") is not True:
            result.add_error(MXN_PATH_UNSAFE, "Cache/bootstrap mutation attempts must hash-verify restored bootstrap files.")
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
    if report.get("runtime_pre_autoexec_loadlevel_suppression_status") not in {None, "", "not_run", "runtime_execution_not_attempted"}:
        print(f"runtime_pre_autoexec_loadlevel_suppression_status: {report.get('runtime_pre_autoexec_loadlevel_suppression_status', '')}")
        print(f"runtime_pre_autoexec_suppression_verified: {str(report.get('runtime_pre_autoexec_suppression_verified', False)).lower()}")
    if report.get("runtime_cache_bootstrap_loadlevel_source_status") not in {None, "", "not_run", "runtime_execution_not_attempted"}:
        print(f"runtime_cache_bootstrap_loadlevel_source_status: {report.get('runtime_cache_bootstrap_loadlevel_source_status', '')}")
        print(f"runtime_cache_bootstrap_verified: {str(report.get('runtime_cache_bootstrap_verified', False)).lower()}")
    if report.get("runtime_character_product_load_status") not in {None, "", "not_run", "runtime_character_product_load_not_attempted"}:
        print(f"runtime_character_product_load_status: {report.get('runtime_character_product_load_status', '')}")
        print(f"runtime_character_product_load_verified: {str(report.get('runtime_character_product_load_verified', False)).lower()}")
    if report.get("runtime_procprefab_handler_or_surface_status") not in {
        None,
        "",
        "not_run",
        "runtime_procprefab_handler_or_surface_not_attempted",
    }:
        print(f"runtime_procprefab_handler_or_surface_status: {report.get('runtime_procprefab_handler_or_surface_status', '')}")
        print(f"runtime_procprefab_direct_load_supported: {str(report.get('runtime_procprefab_direct_load_supported', False)).lower()}")
        print(
            "runtime_procprefab_runtime_equivalent_surface_verified: "
            f"{str(report.get('runtime_procprefab_runtime_equivalent_surface_verified', False)).lower()}"
        )
    if report.get("runtime_character_spawnable_surface_status") not in {
        None,
        "",
        "not_run",
        "runtime_character_spawnable_surface_not_attempted",
    }:
        print(f"runtime_character_spawnable_surface_status: {report.get('runtime_character_spawnable_surface_status', '')}")
        print(f"runtime_character_spawnable_surface_found: {str(report.get('runtime_character_spawnable_surface_found', False)).lower()}")
        print(f"runtime_character_spawnable_surface_verified: {str(report.get('runtime_character_spawnable_surface_verified', False)).lower()}")
    if report.get("runtime_character_prefab_source_status") not in {
        None,
        "",
        "not_run",
        "runtime_character_prefab_source_not_attempted",
    }:
        print(f"runtime_character_prefab_source_status: {report.get('runtime_character_prefab_source_status', '')}")
        print(f"runtime_character_prefab_source_path: {report.get('runtime_character_prefab_source_path', '')}")
        print(f"runtime_character_prefab_source_apb_product_found: {str(report.get('runtime_character_prefab_source_apb_product_found', False)).lower()}")
    if report.get("runtime_character_animation_playback_surface_status") not in {
        None,
        "",
        "not_run",
        "runtime_character_animation_playback_surface_not_attempted",
    }:
        print(
            "runtime_character_animation_playback_surface_status: "
            f"{report.get('runtime_character_animation_playback_surface_status', '')}"
        )
        print(
            "runtime_character_animation_playback_surface_found: "
            f"{str(report.get('runtime_character_animation_playback_surface_found', False)).lower()}"
        )
        print(f"runtime_character_animation_verified: {str(report.get('runtime_character_animation_verified', False)).lower()}")
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
        "runtime_exit_fixture_runtime_command_uses_pre_autoexec_suppression_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_cache_bootstrap_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_ap_shader_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_product_load_probe": False,
        "runtime_exit_fixture_runtime_command_uses_spawn_instantiation_probe": False,
        "runtime_exit_fixture_runtime_command_uses_animation_playback_surface_probe": False,
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
        "runtime_pre_autoexec_loadlevel_suppression": {"status": "runtime_execution_not_attempted"},
        "runtime_pre_autoexec_loadlevel_suppression_status": "runtime_execution_not_attempted",
        "runtime_pre_autoexec_loadlevel_suppression_candidates": [],
        "runtime_pre_autoexec_candidate_matrix_recorded": False,
        "runtime_pre_autoexec_candidate_id": "",
        "runtime_pre_autoexec_candidate_name": "",
        "runtime_pre_autoexec_candidate_kind": "",
        "runtime_pre_autoexec_candidate_source_validation": {},
        "runtime_pre_autoexec_candidate_source_refs": [],
        "runtime_pre_autoexec_candidate_surface": "",
        "runtime_pre_autoexec_candidate_merge_order": "",
        "runtime_pre_autoexec_candidate_pre_autoexec_verified": False,
        "runtime_pre_autoexec_candidate_patch_path": "",
        "runtime_pre_autoexec_candidate_patch_contents_summary": "",
        "runtime_pre_autoexec_candidate_mutates_project": False,
        "runtime_pre_autoexec_candidate_mutates_project_user": False,
        "runtime_pre_autoexec_candidate_mutates_defaultlevel": False,
        "runtime_pre_autoexec_candidate_mutates_production_level": False,
        "runtime_pre_autoexec_candidate_reversible": False,
        "runtime_pre_autoexec_candidate_rollback": "",
        "runtime_pre_autoexec_candidate_gate_env": [],
        "runtime_pre_autoexec_candidate_command_args": [],
        "runtime_pre_autoexec_candidate_settings_registry_keys": [],
        "runtime_pre_autoexec_candidate_expected_registry_state": {},
        "runtime_pre_autoexec_candidate_actual_registry_state": {},
        "runtime_pre_autoexec_candidate_expected_level_loads": [],
        "runtime_pre_autoexec_candidate_actual_level_loads": [],
        "runtime_pre_autoexec_candidate_attempted": False,
        "runtime_pre_autoexec_candidate_result": "",
        "runtime_pre_autoexec_candidate_rejected_reason": "",
        "runtime_pre_autoexec_candidate_blocker": "",
        "runtime_pre_autoexec_candidate_mutation_path": "",
        "runtime_pre_autoexec_candidate_mutation_disabled_path": "",
        "runtime_pre_autoexec_candidate_mutation_backup_path": "",
        "runtime_pre_autoexec_candidate_mutation_pre_refs": [],
        "runtime_pre_autoexec_candidate_mutation_post_refs": [],
        "runtime_pre_autoexec_candidate_mutation_restored": False,
        "runtime_pre_autoexec_cache_bootstrap_loadlevel_sources": [],
        "runtime_pre_autoexec_cache_bootstrap_loadlevel_source_count": 0,
        "runtime_pre_autoexec_cache_bootstrap_loadlevel_blocker": "",
        "runtime_pre_autoexec_selected": "",
        "runtime_pre_autoexec_selected_reason": "",
        "runtime_pre_autoexec_suppression_verified": False,
        "runtime_cache_bootstrap_loadlevel_source": {"status": "runtime_execution_not_attempted"},
        "runtime_cache_bootstrap_loadlevel_source_status": "runtime_execution_not_attempted",
        "runtime_cache_bootstrap_source_discovery_status": "runtime_execution_not_attempted",
        "runtime_cache_bootstrap_files": [],
        "runtime_cache_bootstrap_generation_source": "",
        "runtime_cache_bootstrap_generation_source_refs": [],
        "runtime_cache_bootstrap_generation_timing": "",
        "runtime_cache_bootstrap_runtime_load_timing": "",
        "runtime_cache_bootstrap_autoload_correlation": "",
        "runtime_cache_bootstrap_candidate_matrix": [],
        "runtime_cache_bootstrap_candidate_matrix_recorded": False,
        "runtime_cache_bootstrap_candidate_id": "",
        "runtime_cache_bootstrap_candidate_name": "",
        "runtime_cache_bootstrap_candidate_kind": "",
        "runtime_cache_bootstrap_candidate_source_validation": {},
        "runtime_cache_bootstrap_candidate_source_refs": [],
        "runtime_cache_bootstrap_candidate_expected_files": [],
        "runtime_cache_bootstrap_candidate_actual_files": [],
        "runtime_cache_bootstrap_candidate_expected_level_loads": [],
        "runtime_cache_bootstrap_candidate_actual_level_loads": [],
        "runtime_cache_bootstrap_candidate_mutates_cache": False,
        "runtime_cache_bootstrap_candidate_mutates_project": False,
        "runtime_cache_bootstrap_candidate_mutates_defaultlevel": False,
        "runtime_cache_bootstrap_candidate_mutates_production_level": False,
        "runtime_cache_bootstrap_candidate_reversible": False,
        "runtime_cache_bootstrap_candidate_backup_refs": [],
        "runtime_cache_bootstrap_candidate_restore_status": "not_attempted",
        "runtime_cache_bootstrap_candidate_hash_verified": False,
        "runtime_cache_bootstrap_candidate_gate_env": [],
        "runtime_cache_bootstrap_candidate_attempted": False,
        "runtime_cache_bootstrap_candidate_result": "",
        "runtime_cache_bootstrap_candidate_blocker": "",
        "runtime_cache_bootstrap_selected": "",
        "runtime_cache_bootstrap_selected_reason": "",
        "runtime_cache_bootstrap_verified": False,
        "runtime_cache_bootstrap_refresh_required": False,
        "runtime_cache_bootstrap_refresh_attempted": False,
        "runtime_cache_bootstrap_refresh_command": [],
        "runtime_cache_bootstrap_refresh_result": "runtime_cache_bootstrap_refresh_not_attempted",
        "runtime_cache_bootstrap_refresh_stdout_ref": "",
        "runtime_cache_bootstrap_refresh_stderr_ref": "",
        "runtime_cache_bootstrap_refresh_log_refs": [],
        "runtime_signal_classification": {"status": "runtime_execution_not_attempted"},
        "runtime_signal_classification_status": "runtime_execution_not_attempted",
        "runtime_signal_classification_candidates": [],
        "runtime_signal_classification_candidate_matrix_recorded": False,
        "runtime_signal_classification_candidate_id": "",
        "runtime_signal_classification_candidate_name": "",
        "runtime_signal_classification_candidate_kind": "",
        "runtime_signal_classification_candidate_source_validation": {},
        "runtime_signal_classification_candidate_source_refs": [],
        "runtime_signal_classification_candidate_expected_signals": {},
        "runtime_signal_classification_candidate_actual_signals": {},
        "runtime_signal_classification_candidate_expected_level_loads": [],
        "runtime_signal_classification_candidate_actual_level_loads": [],
        "runtime_signal_classification_candidate_attempted": False,
        "runtime_signal_classification_candidate_result": "",
        "runtime_signal_classification_candidate_blocker": "",
        "runtime_signal_classification_selected": "",
        "runtime_signal_classification_selected_reason": "",
        "runtime_signal_classification_verified": False,
        "runtime_settings_registry_project_user_registry_order": "",
        "runtime_console_autoexec_notification_timing": "",
        "runtime_spawnable_level_deferred_load_timing": "",
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
        "runtime_asset_processor_negotiation_signal_present": False,
        "runtime_asset_processor_negotiation_signal_lines": [],
        "runtime_asset_processor_negotiation_signal_sources": [],
        "runtime_asset_processor_negotiation_source_file": "",
        "runtime_asset_processor_negotiation_source_function": "",
        "runtime_asset_processor_negotiation_source_refs": [],
        "runtime_asset_processor_negotiation_status": "not_run",
        "runtime_asset_processor_negotiation_classification": "",
        "runtime_asset_processor_negotiation_classification_reason": "",
        "runtime_asset_processor_negotiation_disqualifying": False,
        "runtime_asset_processor_negotiation_requires_ap_running": False,
        "runtime_asset_processor_negotiation_wait_for_connect_value": "",
        "runtime_asset_processor_negotiation_ap_session_status": "not_used",
        "runtime_asset_processor_negotiation_harmless_only_if": [],
        "runtime_asset_processor_negotiation_blocker": "",
        "runtime_shader_serializer_signal": {"status": "not_run", "count": 0},
        "runtime_shader_serializer_signal_status": "not_run",
        "runtime_shader_serializer_signal_present": False,
        "runtime_shader_serializer_signal_lines": [],
        "runtime_shader_serializer_signal_sources": [],
        "runtime_shader_serializer_source_file": "",
        "runtime_shader_serializer_source_function": "",
        "runtime_shader_serializer_source_refs": [],
        "runtime_shader_serializer_status": "not_run",
        "runtime_shader_serializer_classification": "",
        "runtime_shader_serializer_classification_reason": "",
        "runtime_shader_serializer_disqualifying": False,
        "runtime_shader_serializer_related_products": [],
        "runtime_shader_serializer_related_assets": [],
        "runtime_shader_serializer_null_headless_context": False,
        "runtime_shader_serializer_harmless_only_if": [],
        "runtime_shader_serializer_blocker": "",
        "runtime_character_product_load": {"status": "runtime_character_product_load_not_attempted"},
        "runtime_character_product_load_status": "runtime_character_product_load_not_attempted",
        "runtime_character_product_load_verified": False,
        "runtime_character_product_load_claimed": False,
        "runtime_character_product_load_probe_enabled": False,
        "runtime_character_product_load_probe_shipping_behavior": False,
        "runtime_character_product_load_source_refs": [],
        "runtime_character_product_load_source_validation": {},
        "runtime_character_product_load_asset_catalog_api": "",
        "runtime_character_product_load_asset_manager_api": "",
        "runtime_character_product_load_candidate_matrix": [],
        "runtime_character_product_load_candidate_matrix_recorded": False,
        "runtime_character_product_load_candidate_id": "",
        "runtime_character_product_load_candidate_name": "",
        "runtime_character_product_load_candidate_kind": "",
        "runtime_character_product_load_candidate_source_validation": {},
        "runtime_character_product_load_candidate_source_refs": [],
        "runtime_character_product_load_candidate_attempted": False,
        "runtime_character_product_load_candidate_result": "",
        "runtime_character_product_load_candidate_blocker": "",
        "runtime_character_product_load_selected_strategy": "",
        "runtime_character_product_load_selected_reason": "",
        "runtime_character_product_load_products": [],
        "runtime_character_product_load_required_products": list(EXPECTED_PRODUCTS),
        "runtime_character_product_load_required_products_complete": False,
        "runtime_character_product_load_missing_products": [],
        "runtime_character_product_load_timed_out_products": [],
        "runtime_character_product_load_failed_products": [],
        "runtime_character_product_load_informational_products": [],
        "runtime_character_product_load_all_required_ready": False,
        "runtime_character_product_load_timeout_seconds": 0,
        "runtime_character_product_load_tick_budget": 0,
        "runtime_character_product_load_markers_observed": False,
        "runtime_character_product_load_marker_summary": {},
        "runtime_character_product_load_log_scan_summary": {"status": "runtime_character_product_load_not_attempted"},
        "runtime_character_product_load_selected_product_log_scan": [],
        "runtime_character_product_load_selected_product_missing_error_scan": {"status": "runtime_character_product_load_not_attempted", "matches": []},
        "runtime_character_product_load_is_instantiation_proof": False,
        "runtime_runtime_character_product_load_is_instantiation_proof": False,
        "runtime_procprefab_handler_or_surface": {"status": "runtime_procprefab_handler_or_surface_not_attempted"},
        "runtime_procprefab_handler_or_surface_status": "runtime_procprefab_handler_or_surface_not_attempted",
        "runtime_procprefab_direct_load_status": "runtime_procprefab_direct_load_not_attempted",
        "runtime_procprefab_direct_load_product_path": "",
        "runtime_procprefab_direct_load_catalog_path": "",
        "runtime_procprefab_direct_load_asset_id": "",
        "runtime_procprefab_direct_load_asset_type": "",
        "runtime_procprefab_direct_load_asset_class": "",
        "runtime_procprefab_direct_load_handler_status": "",
        "runtime_procprefab_direct_load_handler_module": "",
        "runtime_procprefab_direct_load_handler_source_refs": [],
        "runtime_procprefab_direct_load_supported": False,
        "runtime_procprefab_direct_load_supported_reason": "",
        "runtime_procprefab_direct_load_blocker": "",
        "runtime_procprefab_direct_load_claimed": False,
        "runtime_procprefab_direct_load_verified": False,
        "runtime_procprefab_surface_candidate_matrix": [],
        "runtime_procprefab_surface_candidate_matrix_recorded": False,
        "runtime_procprefab_surface_selected": "",
        "runtime_procprefab_surface_selected_reason": "",
        "runtime_procprefab_surface_remaining_blocker": "",
        "runtime_procprefab_runtime_equivalent_surface_claimed": False,
        "runtime_procprefab_runtime_equivalent_surface_verified": False,
        "runtime_character_spawnable_surface": {"status": "runtime_character_spawnable_surface_not_attempted"},
        "runtime_character_spawnable_surface_status": "runtime_character_spawnable_surface_not_attempted",
        "runtime_character_spawnable_surface_source_validation": "runtime_character_spawnable_surface_not_attempted",
        "runtime_character_spawnable_surface_source_refs": [],
        "runtime_character_spawnable_surface_search_status": "runtime_character_spawnable_surface_not_attempted",
        "runtime_character_spawnable_surface_candidates": [],
        "runtime_character_spawnable_surface_candidate_matrix_recorded": False,
        "runtime_character_spawnable_surface_selected": "",
        "runtime_character_spawnable_surface_selected_reason": "",
        "runtime_character_spawnable_surface_found": False,
        "runtime_character_spawnable_surface_claimed": False,
        "runtime_character_spawnable_surface_verified": False,
        "runtime_character_spawnable_surface_load_status": "runtime_character_spawnable_surface_load_not_attempted",
        "runtime_character_spawnable_surface_load_ready": False,
        "runtime_character_spawnable_surface_load_timeout": False,
        "runtime_character_spawnable_surface_log_errors": [],
        "runtime_character_spawnable_surface_missing_reason": "",
        "runtime_character_spawnable_surface_generation_required": False,
        "runtime_character_spawnable_surface_generation_strategy": "",
        "runtime_character_spawnable_surface_generation_source_changes": [],
        "runtime_character_spawnable_surface_generation_blocker": "",
        "runtime_character_spawnable_surface_remaining_blocker": "",
        "runtime_character_spawnable_surface_generation_completed": False,
        "runtime_character_prefab_source": {"status": "runtime_character_prefab_source_not_attempted"},
        "runtime_character_prefab_source_status": "runtime_character_prefab_source_not_attempted",
        "runtime_character_prefab_source_path": "",
        "runtime_character_prefab_source_kind": "",
        "runtime_character_prefab_source_owned_by_repo": False,
        "runtime_character_prefab_source_is_defaultlevel": False,
        "runtime_character_prefab_source_is_production_level": False,
        "runtime_character_prefab_source_is_temp": False,
        "runtime_character_prefab_source_is_generic_transform_only": False,
        "runtime_character_prefab_source_is_character_specific": False,
        "runtime_character_prefab_source_is_approved": False,
        "runtime_character_prefab_source_generation_strategy": "",
        "runtime_character_prefab_source_generation_source_validation": "runtime_character_prefab_source_not_attempted",
        "runtime_character_prefab_source_generation_source_refs": [],
        "runtime_character_prefab_source_committed": False,
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
        "runtime_character_spawn_instantiation_candidate_id": "",
        "runtime_character_spawn_instantiation_candidate_name": "",
        "runtime_character_spawn_instantiation_candidate_kind": "",
        "runtime_character_spawn_instantiation_candidate_source_validation": {},
        "runtime_character_spawn_instantiation_candidate_source_refs": [],
        "runtime_character_spawn_instantiation_candidate_attempted": False,
        "runtime_character_spawn_instantiation_candidate_result": "",
        "runtime_character_spawn_instantiation_candidate_blocker": "",
        "runtime_character_spawn_instantiation_selected_strategy": "",
        "runtime_character_spawn_instantiation_selected_reason": "",
        "runtime_character_spawn_instantiation_api": "",
        "runtime_character_spawn_instantiation_api_argument_shape": {},
        "runtime_character_spawn_instantiation_context_status": "",
        "runtime_character_spawn_instantiation_context_id": "",
        "runtime_character_spawn_instantiation_context_source_refs": [],
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
        "runtime_character_spawn_instantiation_root_entity_count": 0,
        "runtime_character_spawn_instantiation_container_entity": "",
        "runtime_character_spawn_instantiation_timeout": False,
        "runtime_character_spawn_instantiation_timeout_ticks": 0,
        "runtime_character_spawn_instantiation_log_errors": [],
        "runtime_character_spawn_instantiation_selected_surface_log_scan": {
            "status": "runtime_character_spawn_instantiation_not_attempted",
            "matches": [],
        },
        "runtime_character_spawn_instantiation_cleanup_attempted": False,
        "runtime_character_spawn_instantiation_cleanup_status": "runtime_character_spawn_instantiation_cleanup_not_attempted",
        "runtime_character_spawn_instantiation_cleanup_source_refs": [],
        "runtime_character_spawn_instantiation_is_animation_proof": False,
        "runtime_character_spawn_instantiation_remaining_blocker": "",
        "runtime_character_animation_playback_surface": {"status": "runtime_character_animation_playback_surface_not_attempted"},
        "runtime_character_animation_playback_surface_status": "runtime_character_animation_playback_surface_not_attempted",
        "runtime_character_animation_playback_surface_diagnostic_attempted": False,
        "runtime_character_animation_playback_surface_diagnostic_completed": False,
        "runtime_character_animation_playback_surface_found": False,
        "runtime_character_animation_playback_surface_verified": False,
        "runtime_character_animation_playback_surface_blocker": "",
        "runtime_character_animation_playback_candidate_matrix": [],
        "runtime_character_animation_source_validation": {
            "status": "runtime_character_animation_playback_surface_not_attempted"
        },
        "runtime_character_animation_source_refs": [],
        "runtime_character_animation_component_type_map": {},
        "runtime_character_animation_asset_type_map": {},
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
        "runtime_character_animation_playback_selected_api": "",
        "runtime_character_animation_playback_selected_assets": [],
        "runtime_character_animation_playback_started": False,
        "runtime_character_animation_playback_observed": False,
        "runtime_character_animation_playback_time_before": None,
        "runtime_character_animation_playback_time_after": None,
        "runtime_character_animation_playback_time_advanced": False,
        "runtime_character_animation_playback_active_state_observed": False,
        "runtime_character_animation_playback_tick_count": 0,
        "runtime_character_animation_playback_tick_duration_seconds": 0,
        "runtime_character_animation_playback_cleanup_complete": False,
        "runtime_character_animation_is_full_character_proof": False,
        "runtime_animation_playback_execution_api_diagnostic_attempted": False,
        "runtime_animation_playback_execution_api_diagnostic_completed": False,
        "runtime_animation_playback_execution_api_source_validation_status": "",
        "runtime_animation_playback_execution_api_source_validation_verified": False,
        "runtime_animation_playback_execution_api_found": False,
        "runtime_animation_playback_execution_api_selected": "",
        "runtime_animation_playback_execution_api_blocker": "",
        "runtime_animation_playback_execution_candidate_matrix": [],
        "runtime_animation_playback_execution_selected_strategy": "",
        "runtime_animation_playback_preconditions_verified": False,
        "runtime_animation_playback_component_wiring_verified_prerequisite": False,
        "runtime_animation_playback_actor_component_found": False,
        "runtime_animation_playback_simple_motion_component_found": False,
        "runtime_animation_playback_actor_asset_assignment_verified": False,
        "runtime_animation_playback_motion_asset_assignment_verified": False,
        "runtime_animation_playback_motion_asset_id": "",
        "runtime_animation_playback_request_attempted": False,
        "runtime_animation_playback_request_succeeded": False,
        "runtime_animation_playback_started": False,
        "runtime_animation_playback_observed": False,
        "runtime_animation_playback_time_before": None,
        "runtime_animation_playback_time_after": None,
        "runtime_animation_playback_time_advanced": False,
        "runtime_animation_playback_active_state_observed": False,
        "runtime_animation_playback_tick_count": 0,
        "runtime_animation_playback_cleanup_verified": False,
        "runtime_animation_playback_execution_verified": False,
        "runtime_animation_playback_selected_log_blocking_matches": [],
        "runtime_character_animation_component_wiring_surface": {
                "status": "runtime_character_animation_component_wiring_surface_not_attempted"
            },
        "runtime_character_animation_component_wiring_surface_status": "runtime_character_animation_component_wiring_surface_not_attempted",
        "runtime_character_animation_component_wiring_surface_diagnostic_attempted": False,
        "runtime_character_animation_component_wiring_surface_diagnostic_completed": False,
        "runtime_character_animation_component_wiring_source_validation_status": "runtime_character_animation_component_wiring_surface_not_attempted",
        "runtime_character_animation_component_wiring_source_validation_verified": False,
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_surface_verified": False,
        "runtime_character_animation_component_wiring_surface_blocker": "",
        "runtime_character_animation_component_wiring_blocker": "",
        "runtime_character_animation_component_wiring_candidate_matrix": [],
        "runtime_character_animation_component_wiring_selected_strategy": "",
        "runtime_character_animation_component_wiring_editor_api": {},
        "runtime_character_animation_component_wiring_prefab_api": {},
        "runtime_character_animation_component_wiring_source_prefab_path": "",
        "runtime_character_animation_component_wiring_source_prefab_modified": False,
        "runtime_character_animation_component_wiring_uses_hand_authored_unknown_serialization": False,
        "runtime_character_animation_component_wiring_actor_component_type_id": "",
        "runtime_character_animation_component_wiring_simple_motion_component_type_id": "",
        "runtime_character_animation_component_wiring_anim_graph_component_type_id": "",
        "runtime_character_animation_component_wiring_actor_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_motion_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_motion_set_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_anim_graph_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_runtime_actor_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_runtime_motion_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_runtime_actor_asset_id": "",
        "runtime_character_animation_component_wiring_runtime_motion_asset_id": "",
        "runtime_character_animation_component_wiring_spawnable_regenerated_or_found": False,
        "runtime_character_animation_component_wiring_spawn_prerequisite_verified": False,
        "runtime_character_animation_component_wiring_product_load_prerequisite_verified": False,
        "runtime_character_animation_component_wiring_surface_before_component_inventory": [],
        "runtime_character_animation_component_wiring_surface_before_actor_component_found": False,
        "runtime_character_animation_component_wiring_surface_before_anim_graph_component_found": False,
        "runtime_character_animation_component_wiring_surface_before_simple_motion_component_found": False,
        "runtime_character_animation_component_wiring_surface_before_blocker": "",
        "runtime_character_animation_component_wiring_runtime_component_inventory": [],
        "runtime_character_animation_component_wiring_runtime_actor_component_found": False,
        "runtime_character_animation_component_wiring_runtime_simple_motion_component_found": False,
        "runtime_character_animation_component_wiring_runtime_anim_graph_component_found": False,
        "runtime_character_animation_component_wiring_claimed": False,
        "runtime_character_animation_component_wiring_verified": False,
        "apb_after_source_prefab_update_attempted": False,
        "apb_after_source_prefab_update_completed": False,
        "apb_after_source_prefab_update_verified": False,
        "apb_after_source_prefab_update_blocker": "",
        "approved_spawnable_regenerated_or_found": False,
        "approved_spawnable_asset_id": "",
        "approved_spawnable_asset_type": "",
        "approved_spawnable_catalog_path": "",
        "approved_spawnable_product_path": "",
        "product_matrix_complete_after_source_prefab_update": False,
        "runtime_actor_simple_motion_component_wiring_after_apb_attempted": False,
        "runtime_actor_simple_motion_component_wiring_after_apb_completed": False,
        "runtime_actor_simple_motion_component_wiring_after_apb_verified": False,
        "runtime_actor_simple_motion_component_wiring_after_apb_blocker": "",
        "runtime_actor_simple_motion_component_wiring_candidate_matrix": [],
        "runtime_actor_simple_motion_component_wiring_selected_strategy": "",
        "approved_motion_product_handler_signal_diagnostic_attempted": False,
        "approved_motion_product_handler_signal_diagnostic_completed": False,
        "approved_motion_product_handler_signal_source_validation_status": "",
        "approved_motion_product_handler_signal_source_validation_verified": False,
        "approved_motion_product_handler_signal_found": False,
        "approved_motion_product_handler_signal_asset_type": "",
        "approved_motion_product_handler_signal_asset_id": "",
        "approved_motion_product_handler_signal_classification": "",
        "approved_motion_product_handler_signal_classification_verified": False,
        "approved_motion_product_handler_signal_harmless_under_strict_fixture": False,
        "approved_motion_product_handler_signal_blocker": "",
        "approved_motion_product_handler_signal_source_files": [],
        "approved_motion_product_handler_signal_candidate_matrix": [],
        "approved_motion_product_handler_signal_selected_strategy": "",
        "approved_motion_product_handler_registered_in_runtime": False,
        "approved_motion_product_handler_expected_runtime_registration": False,
        "runtime_shutdown_poolallocator_signal_diagnostic_attempted": False,
        "runtime_shutdown_poolallocator_signal_diagnostic_completed": False,
        "runtime_shutdown_poolallocator_signal_source_validation_status": "",
        "runtime_shutdown_poolallocator_signal_source_validation_verified": False,
        "runtime_shutdown_poolallocator_signal_found": False,
        "runtime_shutdown_poolallocator_signal_line": "",
        "runtime_shutdown_poolallocator_signal_classification": "",
        "runtime_shutdown_poolallocator_signal_classification_verified": False,
        "runtime_shutdown_poolallocator_signal_harmless_under_strict_fixture": False,
        "runtime_shutdown_poolallocator_signal_blocker": "",
        "runtime_shutdown_poolallocator_signal_source_files": [],
        "runtime_shutdown_poolallocator_signal_candidate_matrix": [],
        "runtime_shutdown_poolallocator_signal_after_fixture_marker": False,
        "runtime_shutdown_poolallocator_signal_after_cleanup": False,
        "runtime_shutdown_poolallocator_signal_invalidates_wiring": False,
        "runtime_shutdown_poolallocator_signal_invalidates_playback": False,
        "runtime_selected_log_scan_blocking_matches": [],
        "runtime_selected_log_scan_classified_harmless_matches": [],
        "runtime_motion_assignment_id_readback_verified": False,
        "runtime_motion_assignment_load_verified": False,
        "runtime_character_product_load_contract_updated": False,
        "runtime_character_product_load_direct_procprefab_required": True,
        "runtime_character_product_load_runtime_equivalent_required": False,
        "runtime_character_product_load_runtime_equivalent_surface_kind": "",
        "runtime_character_product_load_contract_blocker": "",
        "runtime_character_instantiation_claimed": False,
        "runtime_character_instantiation_verified": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_production_level_loaded": False,
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
        "asset_cache_deleted": False,
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


def _run_runtime_pre_autoexec_suppression_diagnostic(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(_runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds))
    report["runtime_harness_mode"] = "runtime_pre_autoexec_loadlevel_suppression_diagnostic"
    payload = _runtime_pre_autoexec_suppression_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
    )
    source_validated = (
        payload["runtime_pre_autoexec_loadlevel_suppression_status"]
        == "runtime_pre_autoexec_suppression_source_discovery_pass"
    )
    report.update(payload)
    report.update(
        {
            "status": "pass" if source_validated else "fail",
            "runtime_harness_status": payload["runtime_pre_autoexec_loadlevel_suppression_status"],
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
                "runtime_pre_autoexec_suppression_source_validated",
                "runtime_pre_autoexec_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_pre_autoexec_diagnostic",
                "runtime_character_proof_not_claimed",
            ]
            if source_validated
            else [],
            "required_runtime_harness_assertions_failed": []
            if source_validated
            else ["runtime_pre_autoexec_suppression_source_validation"],
            "runtime_harness_assertion_informational": [
                "pre_autoexec_suppression_diagnostic_does_not_launch_runtime",
                "pre_autoexec_source_validation_is_not_runtime_execution_proof",
                "project_registry_mutation_requires_explicit_gate",
            ],
        }
    )
    return _finalize_report(report)


def _run_runtime_cache_bootstrap_diagnostic(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(_runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds))
    report["runtime_harness_mode"] = "runtime_cache_bootstrap_loadlevel_source_diagnostic"
    payload = _runtime_cache_bootstrap_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
    )
    source_validated = (
        payload["runtime_cache_bootstrap_loadlevel_source_status"]
        == "runtime_cache_bootstrap_source_discovery_pass"
    )
    report.update(payload)
    report.update(
        {
            "status": "pass" if source_validated else "fail",
            "runtime_harness_status": payload["runtime_cache_bootstrap_loadlevel_source_status"],
            "runtime_execution_status": "runtime_execution_not_attempted",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "live_runtime_execution": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "defaultlevel_mutation": False,
            "production_level_mutation": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_exit_fixture_source_ready",
                "runtime_cache_bootstrap_source_validated",
                "runtime_cache_bootstrap_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_cache_bootstrap_diagnostic",
                "runtime_character_proof_not_claimed",
                "asset_cache_not_deleted",
            ]
            if source_validated
            else [],
            "required_runtime_harness_assertions_failed": []
            if source_validated
            else ["runtime_cache_bootstrap_source_validation"],
            "runtime_harness_assertion_informational": [
                "cache_bootstrap_diagnostic_does_not_launch_runtime",
                "cache_bootstrap_source_validation_is_not_runtime_execution_proof",
                "cache_bootstrap_mutation_requires_explicit_gate",
                "asset_cache_deletion_forbidden",
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
    pre_autoexec_suppression: bool = False,
    cache_bootstrap_strategy: bool = False,
    ap_shader_signal_classification: bool = False,
    character_product_load: bool = False,
    character_spawn_instantiation: bool = False,
    character_animation_playback_surface: bool = False,
    character_animation_component_wiring_surface: bool = False,
    actor_simple_motion_component_wiring_after_apb: bool = False,
    poolallocator_signal_classification: bool = False,
    animation_playback_execution: bool = False,
    product_evidence: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    report.update(_runtime_exit_fixture_source_ready_payload(timeout_seconds=timeout_seconds))
    report["runtime_harness_mode"] = (
        "runtime_animation_playback_execution_fixture_command"
        if animation_playback_execution
        else "runtime_poolallocator_signal_classification_fixture_command"
        if poolallocator_signal_classification
        else "runtime_actor_simple_motion_component_wiring_after_apb_fixture_command"
        if actor_simple_motion_component_wiring_after_apb
        else "runtime_character_animation_component_wiring_surface_fixture_command"
        if character_animation_component_wiring_surface
        else "runtime_character_animation_playback_surface_fixture_command"
        if character_animation_playback_surface
        else "runtime_character_spawn_instantiation_fixture_command"
        if character_spawn_instantiation
        else "runtime_character_product_load_fixture_command"
        if character_product_load
        else "runtime_exit_fixture_ap_shader_signal_classification_command"
        if ap_shader_signal_classification
        else "runtime_exit_fixture_cache_bootstrap_loadlevel_source_command"
        if cache_bootstrap_strategy
        else "runtime_exit_fixture_later_registry_patch_command"
        if later_registry_patch
        else "runtime_exit_fixture_pre_autoexec_loadlevel_suppression_command"
        if pre_autoexec_suppression
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
    if character_product_load:
        product_gate = _runtime_character_product_load_probe_gate_status(env)
        if product_gate["status"] != "pass":
            payload = _runtime_character_product_load_source_payload(
                product_evidence=product_evidence or report.get("product_evidence_summary", {}),
                engine_root=_runtime_engine_root_from_report(report),
                project=project,
                timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir,
            )
            payload.update(
                {
                    "runtime_character_product_load_status": product_gate["status"],
                    "runtime_character_product_load_candidate_attempted": False,
                    "runtime_character_product_load_candidate_result": "runtime_character_product_load_candidate_rejected_unsafe",
                    "runtime_character_product_load_candidate_blocker": product_gate["status"],
                    "runtime_character_product_load_probe_enabled": False,
                    "runtime_character_product_load_verified": False,
                    "runtime_character_product_load_claimed": False,
                }
            )
            report.update(payload)
            report.update(
                {
                    "status": "fail",
                    "runtime_harness_status": product_gate["status"],
                    "runtime_harness_blocked_reason": product_gate["status"],
                    "runtime_exit_fixture_status": product_gate["status"],
                    "runtime_exit_fixture_blocked_reason": product_gate["status"],
                    "runtime_execution_status": "runtime_execution_not_attempted",
                    "runtime_execution_attempted": False,
                    "runtime_execution_completed": False,
                    "runtime_execution_verified": False,
                    "runtime_exit_fixture_execution_attempted": False,
                    "runtime_exit_fixture_execution_completed": False,
                    "runtime_exit_fixture_execution_verified": False,
                    "live_runtime_execution": False,
                    "required_runtime_harness_assertions_failed": ["runtime_character_product_load_probe_gate"],
                }
            )
            return _finalize_report(report)
        product_patch_gate = _runtime_temp_registry_patch_gate_status(env)
        report["runtime_character_product_load_temp_registry_patch_gate_env"] = list(
            RUNTIME_EXIT_FIXTURE_TEMP_REGISTRY_PATCH_GATE_ENV
        )
        report["runtime_character_product_load_temp_registry_patch_gate_status"] = product_patch_gate
        if product_patch_gate["status"] != "pass":
            payload = _runtime_character_product_load_source_payload(
                product_evidence=product_evidence or report.get("product_evidence_summary", {}),
                engine_root=_runtime_engine_root_from_report(report),
                project=project,
                timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir,
            )
            payload.update(
                {
                    "runtime_character_product_load_status": product_patch_gate["status"],
                    "runtime_character_product_load_candidate_attempted": False,
                    "runtime_character_product_load_candidate_result": "runtime_character_product_load_candidate_rejected_unsafe",
                    "runtime_character_product_load_candidate_blocker": product_patch_gate["status"],
                    "runtime_character_product_load_verified": False,
                    "runtime_character_product_load_claimed": False,
                }
            )
            report.update(payload)
            report.update(
                {
                    "status": "fail",
                    "runtime_harness_status": product_patch_gate["status"],
                    "runtime_harness_blocked_reason": product_patch_gate["status"],
                    "runtime_exit_fixture_status": product_patch_gate["status"],
                    "runtime_exit_fixture_blocked_reason": product_patch_gate["status"],
                    "runtime_execution_status": "runtime_execution_not_attempted",
                    "runtime_execution_attempted": False,
                    "runtime_execution_completed": False,
                    "runtime_execution_verified": False,
                    "runtime_exit_fixture_execution_attempted": False,
                    "runtime_exit_fixture_execution_completed": False,
                    "runtime_exit_fixture_execution_verified": False,
                    "live_runtime_execution": False,
                    "required_runtime_harness_assertions_failed": ["runtime_character_product_load_temp_registry_patch_gate"],
                }
            )
            return _finalize_report(report)
    if character_spawn_instantiation:
        spawn_gate = _runtime_character_spawn_instantiation_gate_status(env)
        report["runtime_character_spawn_instantiation_gate_env"] = list(
            tuple(RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV)
            + tuple(RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV)
        )
        report["runtime_character_spawn_instantiation_gate_status"] = spawn_gate
        if spawn_gate["status"] != "pass":
            payload = _runtime_character_spawn_instantiation_source_payload(
                product_evidence=product_evidence or report.get("product_evidence_summary", {}),
                engine_root=_runtime_engine_root_from_report(report),
                project=project,
                timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir,
            )
            payload.update(
                {
                    "runtime_character_spawn_instantiation_status": spawn_gate["status"],
                    "runtime_character_spawn_instantiation_candidate_attempted": False,
                    "runtime_character_spawn_instantiation_candidate_result": "runtime_character_spawn_candidate_rejected_unsafe",
                    "runtime_character_spawn_instantiation_candidate_blocker": spawn_gate["status"],
                    "runtime_character_spawn_instantiation_probe_enabled": False,
                    "runtime_character_spawn_instantiation_claimed": False,
                    "runtime_character_spawn_instantiation_verified": False,
                    "runtime_character_instantiation_claimed": False,
                    "runtime_character_instantiation_verified": False,
                }
            )
            report.update(payload)
            report.update(
                {
                    "status": "fail",
                    "runtime_harness_status": spawn_gate["status"],
                    "runtime_harness_blocked_reason": spawn_gate["status"],
                    "runtime_exit_fixture_status": spawn_gate["status"],
                    "runtime_exit_fixture_blocked_reason": spawn_gate["status"],
                    "runtime_execution_status": "runtime_execution_not_attempted",
                    "runtime_execution_attempted": False,
                    "runtime_execution_completed": False,
                    "runtime_execution_verified": False,
                    "runtime_exit_fixture_execution_attempted": False,
                    "runtime_exit_fixture_execution_completed": False,
                    "runtime_exit_fixture_execution_verified": False,
                    "live_runtime_execution": False,
                    "required_runtime_harness_assertions_failed": ["runtime_character_spawn_instantiation_gate"],
                }
            )
            return _finalize_report(report)
    if character_animation_playback_surface:
        animation_gate = _runtime_character_animation_playback_surface_gate_status(env)
        report["runtime_character_animation_playback_surface_gate_env"] = list(
            tuple(RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV)
            + tuple(RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV)
            + tuple(RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_GATE_ENV)
        )
        report["runtime_character_animation_playback_surface_gate_status"] = animation_gate
        if animation_gate["status"] != "pass":
            payload = _runtime_character_animation_playback_surface_source_payload(
                product_evidence=product_evidence or report.get("product_evidence_summary", {}),
                engine_root=_runtime_engine_root_from_report(report),
                project=project,
                timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir,
            )
            payload.update(
                {
                    "runtime_character_animation_playback_surface_status": animation_gate["status"],
                    "runtime_character_animation_playback_surface_blocker": animation_gate["status"],
                    "runtime_character_animation_playback_surface_found": False,
                    "runtime_character_animation_playback_surface_verified": False,
                    "runtime_character_animation_claimed": False,
                    "runtime_character_animation_verified": False,
                }
            )
            report.update(payload)
            report.update(
                {
                    "status": "fail",
                    "runtime_harness_status": animation_gate["status"],
                    "runtime_harness_blocked_reason": animation_gate["status"],
                    "runtime_exit_fixture_status": animation_gate["status"],
                    "runtime_exit_fixture_blocked_reason": animation_gate["status"],
                    "runtime_execution_status": "runtime_execution_not_attempted",
                    "runtime_execution_attempted": False,
                    "runtime_execution_completed": False,
                    "runtime_execution_verified": False,
                    "runtime_exit_fixture_execution_attempted": False,
                    "runtime_exit_fixture_execution_completed": False,
                    "runtime_exit_fixture_execution_verified": False,
                    "live_runtime_execution": False,
                    "required_runtime_harness_assertions_failed": ["runtime_character_animation_playback_surface_gate"],
                }
            )
            return _finalize_report(report)
    if character_animation_component_wiring_surface:
        wiring_gate = (
            _runtime_animation_playback_execution_gate_status(env)
            if animation_playback_execution
            else _runtime_actor_simple_motion_component_wiring_after_apb_gate_status(env)
            if actor_simple_motion_component_wiring_after_apb
            else _runtime_character_animation_component_wiring_surface_gate_status(env)
        )
        report["runtime_character_animation_component_wiring_surface_gate_env"] = list(
            tuple(RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV)
            + tuple(RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV)
            + tuple(RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_GATE_ENV)
            + tuple(RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_GATE_ENV)
            + (
                tuple(RUNTIME_ACTOR_SIMPLE_MOTION_AFTER_APB_GATE_ENV)
                if actor_simple_motion_component_wiring_after_apb
                else tuple()
            )
            + (
                tuple(RUNTIME_ANIMATION_PLAYBACK_EXECUTION_GATE_ENV)
                if animation_playback_execution
                else tuple()
            )
        )
        report["runtime_character_animation_component_wiring_surface_gate_status"] = wiring_gate
        if wiring_gate["status"] != "pass":
            payload = _runtime_character_animation_component_wiring_surface_source_payload(
                product_evidence=product_evidence or report.get("product_evidence_summary", {}),
                engine_root=_runtime_engine_root_from_report(report),
                project=project,
                timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir,
            )
            payload.update(
                {
                    "runtime_character_animation_component_wiring_surface_status": wiring_gate["status"],
                    "runtime_character_animation_component_wiring_surface_blocker": wiring_gate["status"],
                    "runtime_character_animation_component_wiring_surface_found": False,
                    "runtime_character_animation_component_wiring_surface_verified": False,
                    "runtime_character_animation_component_wiring_claimed": False,
                    "runtime_character_animation_component_wiring_verified": False,
                }
            )
            report.update(payload)
            report.update(
                {
                    "status": "fail",
                    "runtime_harness_status": wiring_gate["status"],
                    "runtime_harness_blocked_reason": wiring_gate["status"],
                    "runtime_exit_fixture_status": wiring_gate["status"],
                    "runtime_exit_fixture_blocked_reason": wiring_gate["status"],
                    "runtime_execution_status": "runtime_execution_not_attempted",
                    "runtime_execution_attempted": False,
                    "runtime_execution_completed": False,
                    "runtime_execution_verified": False,
                    "runtime_exit_fixture_execution_attempted": False,
                    "runtime_exit_fixture_execution_completed": False,
                    "runtime_exit_fixture_execution_verified": False,
                    "live_runtime_execution": False,
                    "required_runtime_harness_assertions_failed": [
                        "runtime_character_animation_component_wiring_surface_gate"
                    ],
                }
            )
            return _finalize_report(report)
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

    if cache_bootstrap_strategy:
        cache_gate = _runtime_cache_bootstrap_mutation_gate_status(env)
        report["runtime_cache_bootstrap_candidate_gate_env"] = (
            list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV)
            + list(RUNTIME_EXIT_FIXTURE_CACHE_BOOTSTRAP_MUTATION_GATE_ENV)
        )
        readiness_payload = report.get("runtime_harness_readiness", {})
        source_engine_root = (
            Path(str(readiness_payload.get("engine_root", "")))
            if isinstance(readiness_payload, Mapping) and str(readiness_payload.get("engine_root", "")).strip()
            else None
        )
        if cache_gate["status"] != "pass":
            payload = _runtime_cache_bootstrap_source_payload(
                project=project,
                engine_root=source_engine_root,
                timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir,
            )
            payload.update(
                {
                    "runtime_cache_bootstrap_loadlevel_source_status": cache_gate["status"],
                    "runtime_cache_bootstrap_candidate_result": "runtime_cache_bootstrap_candidate_rejected_unsafe",
                    "runtime_cache_bootstrap_candidate_attempted": False,
                    "runtime_cache_bootstrap_candidate_blocker": cache_gate["status"],
                    "runtime_cache_bootstrap_verified": False,
                    "runtime_default_level_override_blocker": cache_gate["status"],
                }
            )
            report.update(payload)
            report.update(
                {
                    "status": "fail",
                    "runtime_harness_status": cache_gate["status"],
                    "runtime_exit_fixture_status": cache_gate["status"],
                    "runtime_exit_fixture_blocked_reason": cache_gate["status"],
                    "runtime_harness_blocked_reason": cache_gate["status"],
                    "runtime_exit_fixture_execution_attempted": False,
                    "runtime_execution_status": "runtime_execution_not_attempted",
                    "runtime_execution_attempted": False,
                    "runtime_execution_completed": False,
                    "runtime_execution_verified": False,
                    "live_runtime_execution": False,
                    "asset_cache_deleted": False,
                    "required_runtime_harness_assertions_failed": ["runtime_fixture_cache_bootstrap_mutation_gate"],
                }
            )
            return _finalize_report(report)

    if pre_autoexec_suppression:
        mutation_gate = _runtime_project_mutation_gate_status()
        mutation_gate["missing"] = [
            name for name in mutation_gate["required"] if not _gate_enabled(env, name)
        ]
        mutation_gate["status"] = (
            "pass" if not mutation_gate["missing"] else "blocked_by_fixture_project_mutation_gate_missing"
        )
        report["runtime_pre_autoexec_candidate_gate_env"] = list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV)
        report["runtime_exit_fixture_project_mutation_gate_env"] = list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV)
        readiness_payload = report.get("runtime_harness_readiness", {})
        source_engine_root = (
            Path(str(readiness_payload.get("engine_root", "")))
            if isinstance(readiness_payload, Mapping) and str(readiness_payload.get("engine_root", "")).strip()
            else None
        )
        if mutation_gate["status"] != "pass":
            payload = _runtime_pre_autoexec_suppression_source_payload(
                project=project,
                engine_root=source_engine_root,
                timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir,
            )
            payload.update(
                {
                    "runtime_pre_autoexec_loadlevel_suppression_status": "blocked_by_fixture_project_mutation_gate_missing",
                    "runtime_pre_autoexec_candidate_result": "runtime_pre_autoexec_candidate_rejected_unsafe",
                    "runtime_pre_autoexec_candidate_attempted": False,
                    "runtime_pre_autoexec_candidate_blocker": "blocked_by_fixture_project_mutation_gate_missing",
                    "runtime_pre_autoexec_suppression_verified": False,
                    "runtime_default_level_override_blocker": "blocked_by_fixture_project_mutation_gate_missing",
                }
            )
            report.update(payload)
            report.update(
                {
                    "status": "fail",
                    "runtime_harness_status": "blocked_by_fixture_project_mutation_gate_missing",
                    "runtime_exit_fixture_status": "blocked_by_fixture_project_mutation_gate_missing",
                    "runtime_exit_fixture_blocked_reason": "blocked_by_fixture_project_mutation_gate_missing",
                    "runtime_harness_blocked_reason": "blocked_by_fixture_project_mutation_gate_missing",
                    "runtime_exit_fixture_project_mutation_status": "blocked_by_fixture_project_mutation_gate_missing",
                    "runtime_exit_fixture_project_mutation_attempted": False,
                    "runtime_execution_status": "runtime_execution_not_attempted",
                    "runtime_execution_attempted": False,
                    "runtime_execution_completed": False,
                    "runtime_execution_verified": False,
                    "runtime_exit_fixture_execution_attempted": False,
                    "runtime_exit_fixture_execution_completed": False,
                    "runtime_exit_fixture_execution_verified": False,
                    "live_runtime_execution": False,
                    "required_runtime_harness_assertions_failed": ["runtime_fixture_project_mutation_gate"],
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
        pre_autoexec_suppression=pre_autoexec_suppression,
        cache_bootstrap_strategy=cache_bootstrap_strategy,
        artifact_dir=artifact_dir,
        character_product_load=character_product_load,
        character_spawn_instantiation=character_spawn_instantiation,
        character_animation_playback_surface=character_animation_playback_surface,
        character_animation_component_wiring_surface=character_animation_component_wiring_surface,
        animation_playback_execution=animation_playback_execution,
        product_evidence=product_evidence or report.get("product_evidence_summary", {}),
    )
    if not command.get("selected"):
        report.update(_unpinned_runtime_command_payload(command))
        report["runtime_exit_fixture_status"] = command.get("blocked_reason", "blocked_by_missing_runtime_readiness")
        return _finalize_report(report)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    if later_registry_patch:
        _write_runtime_later_registry_patch(_runtime_later_registry_patch_path(artifact_dir))
    if character_product_load:
        _write_runtime_character_product_load_patch(
            _runtime_character_product_load_patch_path(artifact_dir),
            _runtime_character_product_load_products_from_apb(
                product_evidence or report.get("product_evidence_summary", {}),
                project=project,
                engine_root=_runtime_engine_root_from_report(report),
            ),
            timeout_seconds=timeout_seconds,
        )
    if character_spawn_instantiation:
        _write_runtime_character_spawn_instantiation_patch(
            _runtime_character_spawn_instantiation_patch_path(artifact_dir),
            product_evidence=product_evidence or report.get("product_evidence_summary", {}),
            project=project,
            engine_root=_runtime_engine_root_from_report(report),
            timeout_seconds=timeout_seconds,
        )
    pre_autoexec_mutation = (
        _apply_runtime_pre_autoexec_suppression(project=project, artifact_dir=artifact_dir)
        if pre_autoexec_suppression or cache_bootstrap_strategy
        else {}
    )
    if (pre_autoexec_suppression or cache_bootstrap_strategy) and pre_autoexec_mutation.get("status") != "runtime_pre_autoexec_project_registry_mutation_applied":
        payload = _runtime_pre_autoexec_suppression_source_payload(
            project=project,
            engine_root=_runtime_engine_root_from_command(command),
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
        payload.update(
            {
                "runtime_pre_autoexec_loadlevel_suppression_status": "blocked_by_project_registry_override_not_safe",
                "runtime_pre_autoexec_candidate_result": "runtime_pre_autoexec_candidate_rejected_unsafe",
                "runtime_pre_autoexec_candidate_attempted": False,
                "runtime_pre_autoexec_candidate_blocker": "blocked_by_project_registry_override_not_safe",
                "runtime_pre_autoexec_candidate_actual_registry_state": dict(pre_autoexec_mutation),
                "runtime_pre_autoexec_suppression_verified": False,
                "runtime_default_level_override_blocker": "blocked_by_project_registry_override_not_safe",
            }
        )
        report.update(payload)
        report.update(
            {
                "status": "fail",
                "runtime_harness_status": "blocked_by_project_registry_override_not_safe",
                "runtime_exit_fixture_status": "blocked_by_project_registry_override_not_safe",
                "runtime_exit_fixture_execution_attempted": False,
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "live_runtime_execution": False,
                "required_runtime_harness_assertions_failed": ["runtime_pre_autoexec_project_registry_mutation"],
            }
        )
        return _finalize_report(report)
    cache_bootstrap_mutation = (
        _apply_runtime_cache_bootstrap_neutralization(project=project, artifact_dir=artifact_dir)
        if cache_bootstrap_strategy
        else {}
    )
    if cache_bootstrap_strategy and cache_bootstrap_mutation.get("status") != "runtime_cache_bootstrap_mutation_applied":
        _restore_runtime_pre_autoexec_suppression(pre_autoexec_mutation)
        payload = _runtime_cache_bootstrap_source_payload(
            project=project,
            engine_root=_runtime_engine_root_from_command(command),
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
        payload.update(
            {
                "runtime_cache_bootstrap_loadlevel_source_status": "blocked_by_cache_bootstrap_mutation_not_safely_scoped",
                "runtime_cache_bootstrap_candidate_result": "runtime_cache_bootstrap_candidate_rejected_unsafe",
                "runtime_cache_bootstrap_candidate_attempted": False,
                "runtime_cache_bootstrap_candidate_blocker": "blocked_by_cache_bootstrap_mutation_not_safely_scoped",
                "runtime_cache_bootstrap_candidate_actual_files": list(cache_bootstrap_mutation.get("files", [])),
                "runtime_cache_bootstrap_verified": False,
                "runtime_default_level_override_blocker": "blocked_by_cache_bootstrap_mutation_not_safely_scoped",
            }
        )
        report.update(payload)
        report.update(
            {
                "status": "fail",
                "runtime_harness_status": "blocked_by_cache_bootstrap_mutation_not_safely_scoped",
                "runtime_exit_fixture_status": "blocked_by_cache_bootstrap_mutation_not_safely_scoped",
                "runtime_exit_fixture_execution_attempted": False,
                "runtime_execution_attempted": False,
                "runtime_execution_completed": False,
                "runtime_execution_verified": False,
                "live_runtime_execution": False,
                "asset_cache_deleted": False,
                "required_runtime_harness_assertions_failed": ["runtime_cache_bootstrap_mutation"],
            }
        )
        return _finalize_report(report)
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
            "runtime_exit_fixture_runtime_command_uses_no_default_level_strategy": (
                no_default_level
                or loadlevel_override
                or later_registry_patch
                or pre_autoexec_suppression
                or cache_bootstrap_strategy
            ),
            "runtime_exit_fixture_runtime_command_uses_loadlevel_override_strategy": (
                loadlevel_override or later_registry_patch or pre_autoexec_suppression
            ),
            "runtime_exit_fixture_runtime_command_uses_later_registry_patch_strategy": later_registry_patch,
            "runtime_exit_fixture_runtime_command_uses_pre_autoexec_suppression_strategy": (
                pre_autoexec_suppression or cache_bootstrap_strategy
            ),
            "runtime_exit_fixture_runtime_command_uses_cache_bootstrap_strategy": cache_bootstrap_strategy,
            "runtime_exit_fixture_runtime_command_uses_ap_shader_strategy": ap_shader_signal_classification,
            "runtime_exit_fixture_runtime_command_uses_product_load_probe": character_product_load,
            "runtime_exit_fixture_runtime_command_uses_spawn_instantiation_probe": character_spawn_instantiation,
            "runtime_exit_fixture_runtime_command_uses_animation_playback_surface_probe": character_animation_playback_surface,
            "runtime_exit_fixture_runtime_command_uses_animation_component_wiring_surface_probe": character_animation_component_wiring_surface,
            "runtime_exit_fixture_runtime_command_uses_actor_simple_motion_component_wiring_after_apb_probe": actor_simple_motion_component_wiring_after_apb,
            "runtime_exit_fixture_runtime_command_uses_poolallocator_signal_classification_probe": poolallocator_signal_classification,
            "runtime_exit_fixture_runtime_command_uses_animation_playback_execution_probe": animation_playback_execution,
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
    finally:
        if cache_bootstrap_strategy:
            _restore_runtime_cache_bootstrap_neutralization(cache_bootstrap_mutation)
        if pre_autoexec_suppression or cache_bootstrap_strategy:
            _restore_runtime_pre_autoexec_suppression(pre_autoexec_mutation)

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
    poolallocator_payload = (
        _runtime_shutdown_poolallocator_signal_payload(
            combined_text,
            _runtime_engine_root_from_command(command),
        )
        if poolallocator_signal_classification
        else {}
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
    signal_classification_payload = (
        _runtime_signal_classification_execution_payload(
            project=project,
            command=command,
            diagnostics=diagnostics,
            actual_level_loads=level_loads,
            combined_text=combined_text,
            exit_code=proc.returncode,
            marker_observed=marker_observed,
            cache_bootstrap_strategy=cache_bootstrap_strategy,
            mutation_state=cache_bootstrap_mutation,
        )
        if ap_shader_signal_classification
        else {}
    )
    effective_disqualifying = (
        _runtime_filter_classified_signal_disqualifiers(disqualifying, diagnostics, signal_classification_payload)
        if ap_shader_signal_classification
        else [dict(item) for item in disqualifying if isinstance(item, Mapping)]
    )
    if (
        poolallocator_signal_classification
        and poolallocator_payload.get("runtime_shutdown_poolallocator_signal_invalidates_wiring") is True
    ):
        effective_disqualifying.append(
            {
                "signal": "runtime_shutdown_poolallocator_assertion",
                "status": RUNTIME_SHUTDOWN_POOLALLOCATOR_SIGNAL_BLOCKER,
                "detail": str(poolallocator_payload.get("runtime_shutdown_poolallocator_signal_line", "")),
            }
        )
    launch_hygiene = _runtime_launch_hygiene_execution_payload(
        project=project,
        command=command,
        diagnostics=diagnostics,
        actual_level_loads=level_loads,
        disqualifying=effective_disqualifying,
        no_default_level=(
            no_default_level
            or loadlevel_override
            or later_registry_patch
            or pre_autoexec_suppression
            or cache_bootstrap_strategy
        ),
        signal_classification=signal_classification_payload if ap_shader_signal_classification else None,
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
    pre_autoexec_payload = _runtime_pre_autoexec_suppression_execution_payload(
        project=project,
        command=command,
        diagnostics=diagnostics,
        actual_level_loads=level_loads,
        pre_autoexec_suppression=pre_autoexec_suppression or cache_bootstrap_strategy,
        launch_hygiene=launch_hygiene,
        exit_code=proc.returncode,
        marker_observed=marker_observed,
        artifact_dir=artifact_dir,
        mutation_state=pre_autoexec_mutation,
    )
    cache_bootstrap_payload = _runtime_cache_bootstrap_execution_payload(
        project=project,
        command=command,
        diagnostics=diagnostics,
        actual_level_loads=level_loads,
        cache_bootstrap_strategy=cache_bootstrap_strategy,
        launch_hygiene=launch_hygiene,
        exit_code=proc.returncode,
        marker_observed=marker_observed,
        artifact_dir=artifact_dir,
        mutation_state=cache_bootstrap_mutation,
    )
    character_product_load_payload = (
        _runtime_character_product_load_execution_payload(
            product_evidence=product_evidence or report.get("product_evidence_summary", {}),
            command=command,
            project=project,
            combined_text=combined_text,
            actual_level_loads=level_loads,
            launch_hygiene=launch_hygiene,
            signal_classification=signal_classification_payload,
            cache_bootstrap=cache_bootstrap_payload,
            exit_code=proc.returncode,
            marker_observed=marker_observed,
        )
        if character_product_load
        else {}
    )
    character_spawn_instantiation_payload = (
        _runtime_character_spawn_instantiation_execution_payload(
            product_evidence=product_evidence or report.get("product_evidence_summary", {}),
            command=command,
            project=project,
            combined_text=combined_text,
            actual_level_loads=level_loads,
            launch_hygiene=launch_hygiene,
            signal_classification=signal_classification_payload,
            cache_bootstrap=cache_bootstrap_payload,
            product_load=character_product_load_payload,
            exit_code=proc.returncode,
            marker_observed=marker_observed,
        )
        if character_spawn_instantiation
        else {}
    )
    character_animation_playback_surface_payload = (
        _runtime_character_animation_playback_surface_execution_payload(
            product_evidence=product_evidence or report.get("product_evidence_summary", {}),
            command=command,
            project=project,
            actual_level_loads=level_loads,
            launch_hygiene=launch_hygiene,
            product_load=character_product_load_payload,
            spawn_instantiation=character_spawn_instantiation_payload,
            exit_code=proc.returncode,
            marker_observed=marker_observed,
        )
        if character_animation_playback_surface
        else {}
    )
    character_animation_component_wiring_surface_payload = (
        _runtime_character_animation_component_wiring_surface_execution_payload(
            product_evidence=product_evidence or report.get("product_evidence_summary", {}),
            command=command,
            project=project,
            product_load=character_product_load_payload,
            spawn_instantiation=character_spawn_instantiation_payload,
            animation_playback_surface=character_animation_playback_surface_payload,
            actor_simple_motion_component_wiring_after_apb=actor_simple_motion_component_wiring_after_apb,
        )
        if character_animation_component_wiring_surface
        else {}
    )
    runtime_animation_playback_execution_payload = (
        _runtime_animation_playback_execution_payload(
            product_evidence=product_evidence or report.get("product_evidence_summary", {}),
            command=command,
            project=project,
            actual_level_loads=level_loads,
            launch_hygiene=launch_hygiene,
            product_load=character_product_load_payload,
            spawn_instantiation=character_spawn_instantiation_payload,
            animation_playback_surface=character_animation_playback_surface_payload,
            component_wiring=character_animation_component_wiring_surface_payload,
            exit_code=proc.returncode,
            marker_observed=marker_observed,
            combined_text=combined_text,
        )
        if animation_playback_execution
        else {}
    )
    launch_hygiene_pass = launch_hygiene.get("runtime_launch_hygiene_status") == "runtime_launch_hygiene_pass"
    character_product_load_pass = (
        character_product_load_payload.get("runtime_character_product_load_verified") is True
        if character_product_load
        else True
    )
    character_spawn_instantiation_pass = (
        character_spawn_instantiation_payload.get("runtime_character_spawn_instantiation_verified") is True
        if character_spawn_instantiation
        else True
    )
    character_animation_playback_surface_pass = (
        True
        if animation_playback_execution
        else
        _runtime_character_animation_playback_surface_fixture_passed(
            character_animation_playback_surface_payload
        )
        if character_animation_playback_surface
        else True
    )
    character_animation_component_wiring_surface_pass = (
        _runtime_character_animation_component_wiring_surface_fixture_passed(
            character_animation_component_wiring_surface_payload
        )
        if character_animation_component_wiring_surface
        else True
    )
    runtime_animation_playback_execution_pass = (
        _runtime_animation_playback_execution_fixture_passed(runtime_animation_playback_execution_payload)
        if animation_playback_execution
        else True
    )
    passed = (
        proc.returncode in expected_exit_codes
        and not timed_out
        and scan.get("status") == "pass"
        and not effective_disqualifying
        and marker_observed
        and launch_hygiene_pass
        and character_product_load_pass
        and character_spawn_instantiation_pass
        and character_animation_playback_surface_pass
        and character_animation_component_wiring_surface_pass
        and runtime_animation_playback_execution_pass
    )
    if passed:
        fixture_status = "runtime_exit_fixture_verified_clean_exit"
    elif timed_out:
        fixture_status = "runtime_exit_fixture_execution_failed_timeout"
    elif (
        poolallocator_signal_classification
        and poolallocator_payload.get("runtime_shutdown_poolallocator_signal_invalidates_wiring") is True
    ):
        fixture_status = "runtime_exit_fixture_execution_failed_runtime_shutdown_poolallocator_assertion"
    elif diagnostics.get("runtime_exit_is_crash_like") is True:
        fixture_status = "runtime_exit_fixture_execution_failed_access_violation_like_exit"
    elif proc.returncode not in expected_exit_codes:
        fixture_status = "runtime_exit_fixture_execution_failed_nonzero_exit"
    elif launch_hygiene.get("runtime_default_level_autoload_detected") is True:
        fixture_status = "runtime_fixture_execution_failed_default_level_autoload"
    elif character_product_load and not character_product_load_pass:
        fixture_status = "runtime_exit_fixture_execution_failed_character_product_load"
    elif character_spawn_instantiation and not character_spawn_instantiation_pass:
        fixture_status = "runtime_exit_fixture_execution_failed_character_spawn_instantiation"
    elif character_animation_playback_surface and not character_animation_playback_surface_pass:
        fixture_status = "runtime_exit_fixture_execution_failed_character_animation_playback_surface"
    elif character_animation_component_wiring_surface and not character_animation_component_wiring_surface_pass:
        fixture_status = "runtime_exit_fixture_execution_failed_character_animation_component_wiring_surface"
    elif animation_playback_execution and not runtime_animation_playback_execution_pass:
        fixture_status = "runtime_exit_fixture_execution_failed_runtime_animation_playback_execution"
    else:
        fixture_status = "runtime_exit_fixture_execution_failed_disqualifying_log_signal"

    report.update(diagnostics)
    report.update(poolallocator_payload)
    report.update(_runtime_signal_fields(scan))
    report.update(loadlevel_override_payload)
    report.update(later_registry_patch_payload)
    report.update(pre_autoexec_payload)
    report.update(cache_bootstrap_payload)
    report.update(launch_hygiene)
    report.update(signal_classification_payload)
    report.update(character_product_load_payload)
    report.update(character_spawn_instantiation_payload)
    report.update(character_animation_playback_surface_payload)
    report.update(character_animation_component_wiring_surface_payload)
    report.update(runtime_animation_playback_execution_payload)
    blocked_reason = _runtime_launch_hygiene_blocked_reason(launch_hygiene)
    if pre_autoexec_suppression and str(pre_autoexec_payload.get("runtime_pre_autoexec_candidate_blocker", "")).strip():
        blocked_reason = str(pre_autoexec_payload.get("runtime_pre_autoexec_candidate_blocker", "")).strip()
    if cache_bootstrap_strategy and str(cache_bootstrap_payload.get("runtime_cache_bootstrap_candidate_blocker", "")).strip():
        blocked_reason = str(cache_bootstrap_payload.get("runtime_cache_bootstrap_candidate_blocker", "")).strip()
    if ap_shader_signal_classification and str(
        signal_classification_payload.get("runtime_signal_classification_candidate_blocker", "")
    ).strip():
        blocked_reason = str(signal_classification_payload.get("runtime_signal_classification_candidate_blocker", "")).strip()
    if character_product_load and str(
        character_product_load_payload.get("runtime_character_product_load_candidate_blocker", "")
    ).strip():
        blocked_reason = str(character_product_load_payload.get("runtime_character_product_load_candidate_blocker", "")).strip()
    if character_spawn_instantiation and str(
        character_spawn_instantiation_payload.get("runtime_character_spawn_instantiation_candidate_blocker", "")
    ).strip():
        blocked_reason = str(
            character_spawn_instantiation_payload.get("runtime_character_spawn_instantiation_candidate_blocker", "")
        ).strip()
    if character_animation_playback_surface and str(
        character_animation_playback_surface_payload.get("runtime_character_animation_playback_surface_blocker", "")
    ).strip():
        blocked_reason = str(
            character_animation_playback_surface_payload.get("runtime_character_animation_playback_surface_blocker", "")
        ).strip()
    if character_animation_component_wiring_surface and str(
        character_animation_component_wiring_surface_payload.get(
            "runtime_character_animation_component_wiring_surface_blocker", ""
        )
    ).strip():
        blocked_reason = str(
            character_animation_component_wiring_surface_payload.get(
                "runtime_character_animation_component_wiring_surface_blocker", ""
            )
        ).strip()
    if animation_playback_execution and str(
        runtime_animation_playback_execution_payload.get("runtime_animation_playback_execution_api_blocker", "")
    ).strip():
        blocked_reason = str(
            runtime_animation_playback_execution_payload.get("runtime_animation_playback_execution_api_blocker", "")
        ).strip()
    if poolallocator_signal_classification and str(
        poolallocator_payload.get("runtime_shutdown_poolallocator_signal_blocker", "")
    ).strip():
        blocked_reason = str(poolallocator_payload.get("runtime_shutdown_poolallocator_signal_blocker", "")).strip()
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
                "status": "fail" if effective_disqualifying else "pass",
                "matches": effective_disqualifying,
            },
            "runtime_exit_fixture_marker_observed": marker_observed,
            "runtime_fixture_marker_observed": marker_observed,
            "runtime_fixture_exit_code_clean": proc.returncode in expected_exit_codes and not timed_out,
            "runtime_exit_fixture_level_load_observed": level_load_observed,
            "runtime_exit_fixture_unexpected_level_load": level_load_observed,
            "runtime_exit_fixture_uses_no_level": not level_load_observed,
            "runtime_exit_fixture_uses_production_level": level_load_observed,
            "runtime_exit_fixture_actual_level_loads": level_loads,
            "runtime_production_level_loaded": level_load_observed,
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
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_exit_fixture_source_ready",
                "runtime_exit_fixture_enabled_for_project",
                "runtime_fixture_settings_registry_command_pinned",
                "runtime_fixture_bounded_command_executed",
                "runtime_exit_fixture_marker_observed",
                "runtime_launch_hygiene_pass",
                "runtime_exit_fixture_clean_exit",
                "runtime_signal_classification_verified" if ap_shader_signal_classification else "runtime_signal_classification_not_required",
                "runtime_character_product_load_verified" if character_product_load else "runtime_character_product_load_not_required",
                "runtime_character_spawn_instantiation_verified"
                if character_spawn_instantiation
                else "runtime_character_spawn_instantiation_not_required",
                "runtime_character_animation_playback_surface_diagnostic_completed"
                if character_animation_playback_surface
                else "runtime_character_animation_playback_surface_not_required",
                "runtime_character_animation_source_validation_passed"
                if character_animation_playback_surface
                else "runtime_character_animation_source_validation_not_required",
                "runtime_character_animation_component_wiring_surface_diagnostic_completed"
                if character_animation_component_wiring_surface
                else "runtime_character_animation_component_wiring_surface_not_required",
                "runtime_animation_playback_execution_verified"
                if animation_playback_execution
                else "runtime_animation_playback_execution_not_required",
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


def _runtime_project_mutation_gate_status() -> Dict[str, Any]:
    required = ("MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION",)
    return {
        "status": "not_run",
        "required": list(required),
        "missing": list(required),
    }


def _runtime_cache_bootstrap_mutation_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    required = (
        "MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION",
        "MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION",
    )
    missing = [name for name in required if not _gate_enabled(env, name)]
    if not missing:
        status = "pass"
    elif "MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION" in missing:
        status = "blocked_by_fixture_cache_bootstrap_mutation_gate_missing"
    else:
        status = "blocked_by_fixture_project_mutation_gate_missing"
    return {"status": status, "required": list(required), "missing": missing}


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
    pre_autoexec_suppression: bool = False,
    cache_bootstrap_strategy: bool = False,
    artifact_dir: Path | None = None,
    character_product_load: bool = False,
    character_spawn_instantiation: bool = False,
    character_animation_playback_surface: bool = False,
    character_animation_component_wiring_surface: bool = False,
    animation_playback_execution: bool = False,
    product_evidence: Mapping[str, Any] | None = None,
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
    project_for_products = Path(project_path) if project_path else None
    product_load_products = (
        _runtime_character_product_load_products_from_apb(
            product_evidence or {},
            project=project_for_products,
            engine_root=engine_root,
        )
        if character_product_load
        else []
    )
    product_load_patch_path = _runtime_character_product_load_patch_path(artifact_dir or DEFAULT_ARTIFACT_ROOT)
    product_load_args = [f"--regset-file={product_load_patch_path}"] if character_product_load else []
    spawn_instantiation_patch_path = _runtime_character_spawn_instantiation_patch_path(
        artifact_dir or DEFAULT_ARTIFACT_ROOT
    )
    spawn_instantiation_args = (
        [f"--regset-file={spawn_instantiation_patch_path}"] if character_spawn_instantiation else []
    )
    animation_playback_execution_args = (
        [
            "--regset=/Amazon/MAXINE/RuntimeHarness/EnableCharacterAnimationPlaybackExecutionProbe=true",
            "--regset=/Amazon/MAXINE/RuntimeHarness/CharacterAnimationPlaybackExecutionProbe/ObservationTicks=8",
            f"--regset=/Amazon/MAXINE/RuntimeHarness/CharacterAnimationPlaybackExecutionProbe/ExpectedMotionAssetId={RUNTIME_CHARACTER_APPROVED_MOTION_ASSET_ID}",
        ]
        if animation_playback_execution
        else []
    )
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
        *product_load_args,
        *spawn_instantiation_args,
        *animation_playback_execution_args,
    ]
    selected_reason = (
        "repo_owned_fixture_runtime_animation_playback_execution_cache_bootstrap_ap_shader_envelope"
        if animation_playback_execution
        else "repo_owned_fixture_character_animation_component_wiring_surface_cache_bootstrap_ap_shader_envelope"
        if character_animation_component_wiring_surface
        else "repo_owned_fixture_character_animation_playback_surface_cache_bootstrap_ap_shader_envelope"
        if character_animation_playback_surface
        else "repo_owned_fixture_character_spawn_instantiation_cache_bootstrap_ap_shader_envelope"
        if character_spawn_instantiation
        else "repo_owned_fixture_character_product_load_cache_bootstrap_ap_shader_envelope"
        if character_product_load
        else "repo_owned_fixture_tickbus_exit_main_loop_cache_bootstrap_loadlevel_source_envelope"
        if cache_bootstrap_strategy
        else "repo_owned_fixture_tickbus_exit_main_loop_later_registry_patch_envelope"
        if later_registry_patch
        else "repo_owned_fixture_tickbus_exit_main_loop_pre_autoexec_loadlevel_suppression_envelope"
        if pre_autoexec_suppression
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
    elif pre_autoexec_suppression:
        safety_flags.extend(
            [
                "pre_autoexec_loadlevel_suppression",
                "project_registry_load_level_setreg_temporarily_disabled",
                "project_mutation_gate_required",
                "project_registry_mutation_reversible",
                "defaultlevel_content_not_mutated",
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
    if character_product_load:
        safety_flags.extend(
            [
                "runtime_character_product_load_probe_enabled",
                "runtime_character_product_load_probe_gate_required",
                "runtime_character_product_load_temp_registry_patch_gate_required",
                "assetcatalog_resolution",
                "assetmanager_generic_load",
                "product_load_is_not_instantiation_proof",
            ]
        )
    if character_spawn_instantiation:
        safety_flags.extend(
            [
                "runtime_character_spawn_instantiation_probe_enabled",
                "runtime_character_spawn_instantiation_probe_gate_required",
                "runtime_character_spawn_instantiation_temp_registry_patch_gate_required",
                "spawn_instantiation_requires_product_load_ready",
                "spawn_instantiation_is_not_animation_proof",
            ]
        )
    if character_animation_playback_surface:
        safety_flags.extend(
            [
                "runtime_character_animation_playback_surface_probe_enabled",
                "runtime_character_animation_playback_surface_gate_required",
                "animation_surface_requires_spawn_prerequisite",
                "animation_surface_diagnostic_is_not_full_character_proof",
            ]
        )
    if character_animation_component_wiring_surface:
        safety_flags.extend(
            [
                "runtime_character_animation_component_wiring_surface_probe_enabled",
                "runtime_character_animation_component_wiring_surface_gate_required",
                "component_wiring_surface_requires_spawn_inventory",
                "component_wiring_surface_diagnostic_is_not_full_character_proof",
            ]
        )
    if animation_playback_execution:
        safety_flags.extend(
            [
                "runtime_animation_playback_execution_probe_enabled",
                "runtime_animation_playback_execution_gate_required",
                "playback_execution_requires_verified_runtime_component_wiring",
                "playback_execution_is_not_full_character_proof",
            ]
        )
    return {
        "selected": True,
        "argv": argv,
        "kind": "headless_settings_registry_runtime_exit_fixture_later_registry_patch_envelope"
        if later_registry_patch
        else "headless_settings_registry_runtime_exit_fixture_pre_autoexec_suppression_envelope"
        if pre_autoexec_suppression
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
            else ["temporary_project_registry_load_level_setreg_disable"]
            if pre_autoexec_suppression
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
            "product_load_probe": product_load_args,
            "spawn_instantiation_probe": spawn_instantiation_args,
            "animation_playback_surface_probe": (
                "python_report_probe_consumes_spawned_entity_component_inventory"
                if character_animation_playback_surface
                else ""
            ),
            "animation_component_wiring_surface_probe": (
                "python_report_probe_consumes_source_validated_editor_prefab_surface_and_spawn_inventory"
                if character_animation_component_wiring_surface
                else ""
            ),
            "animation_playback_execution_probe": animation_playback_execution_args,
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
            "loads_character_content": bool(character_product_load or character_spawn_instantiation),
            "loads_character_products_only": bool(character_product_load),
            "runtime_character_product_load_proof": bool(character_product_load),
            "runtime_character_spawn_instantiation_probe": bool(character_spawn_instantiation),
            "runtime_character_instantiation_proof": bool(character_spawn_instantiation),
            "runtime_character_animation_playback_surface_probe": bool(character_animation_playback_surface),
            "runtime_character_animation_component_wiring_surface_probe": bool(
                character_animation_component_wiring_surface
            ),
            "runtime_character_animation_playback_execution_probe": bool(animation_playback_execution),
            "runtime_character_proof": False,
            "headless_launcher": True,
            "null_renderer_requested": True,
            "safe_to_kill_after_timeout": True,
            "uses_console_command_file_quit": False,
            "uses_settings_registry_fixture_exit": True,
            "uses_no_default_level_strategy": no_default_level or loadlevel_override or later_registry_patch or pre_autoexec_suppression,
            "uses_loadlevel_override_strategy": loadlevel_override or later_registry_patch or pre_autoexec_suppression,
            "uses_later_registry_patch_strategy": later_registry_patch,
            "uses_pre_autoexec_suppression_strategy": pre_autoexec_suppression,
            "temp_registry_patch_path": str(later_patch_path)
            if later_registry_patch
            else str(spawn_instantiation_patch_path)
            if character_spawn_instantiation
            else str(product_load_patch_path)
            if character_product_load
            else "",
            "temp_registry_patch_gate_required": later_registry_patch or character_product_load or character_spawn_instantiation,
            "project_registry_mutation_gate_required": pre_autoexec_suppression,
            "project_registry_mutation_reversible": pre_autoexec_suppression,
            "uses_character_product_load_probe": bool(character_product_load),
            "character_product_load_probe_gate_required": bool(character_product_load),
            "character_product_load_temp_registry_patch_path": str(product_load_patch_path) if character_product_load else "",
            "character_product_load_temp_registry_patch_gate_required": bool(character_product_load),
            "uses_character_spawn_instantiation_probe": bool(character_spawn_instantiation),
            "character_spawn_instantiation_probe_gate_required": bool(character_spawn_instantiation),
            "character_spawn_instantiation_temp_registry_patch_path": str(spawn_instantiation_patch_path)
            if character_spawn_instantiation
            else "",
            "character_spawn_instantiation_temp_registry_patch_gate_required": bool(character_spawn_instantiation),
            "uses_character_animation_playback_surface_probe": bool(character_animation_playback_surface),
            "character_animation_playback_surface_probe_gate_required": bool(character_animation_playback_surface),
            "uses_character_animation_component_wiring_surface_probe": bool(
                character_animation_component_wiring_surface
            ),
            "uses_character_animation_playback_execution_probe": bool(animation_playback_execution),
            "character_animation_component_wiring_surface_probe_gate_required": bool(
                character_animation_component_wiring_surface
            ),
            "character_animation_playback_execution_probe_gate_required": bool(animation_playback_execution),
            "runtime_character_animation_proof": False,
            "runtime_full_character_proof": False,
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
    signal_classification: Mapping[str, Any] | None = None,
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
    classification = signal_classification or {}
    ap_classification = str(
        classification.get(
            "runtime_asset_processor_negotiation_classification",
            "blocked_by_asset_processor_negotiation_signal" if ap_count else "runtime_asset_processor_negotiation_signal_absent",
        )
    )
    shader_classification = str(
        classification.get(
            "runtime_shader_serializer_classification",
            "blocked_by_shader_serializer_signal" if shader_count else "runtime_shader_serializer_signal_absent",
        )
    )
    ap_disqualifying = bool(
        classification.get("runtime_asset_processor_negotiation_disqualifying", bool(ap_count))
    )
    shader_disqualifying = bool(classification.get("runtime_shader_serializer_disqualifying", bool(shader_count)))
    signal_summary = [dict(item) for item in disqualifying if isinstance(item, Mapping)]
    launch_pass = not default_level_detected and not ap_disqualifying and not shader_disqualifying and not signal_summary
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
            "runtime_asset_processor_negotiation_signal_present": bool(ap_count),
            "runtime_asset_processor_negotiation_classification": ap_classification,
            "runtime_asset_processor_negotiation_disqualifying": ap_disqualifying,
            "runtime_shader_serializer_signal": {"status": shader_status, "count": shader_count},
            "runtime_shader_serializer_signal_status": shader_status,
            "runtime_shader_serializer_status": shader_status,
            "runtime_shader_serializer_signal_present": bool(shader_count),
            "runtime_shader_serializer_classification": shader_classification,
            "runtime_shader_serializer_disqualifying": shader_disqualifying,
            "runtime_disqualifying_signal_summary": signal_summary,
            "runtime_disqualifying_signal_count": len(signal_summary),
            "runtime_production_level_loaded": bool(actual_level_loads),
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


def _runtime_character_product_load_patch_path(artifact_dir: Path) -> Path:
    return artifact_dir / RUNTIME_CHARACTER_PRODUCT_LOAD_PATCH_FILENAME


def _runtime_character_spawn_instantiation_patch_path(artifact_dir: Path) -> Path:
    return artifact_dir / RUNTIME_CHARACTER_SPAWN_INSTANTIATION_PATCH_FILENAME


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


def _write_runtime_character_product_load_patch(
    path: Path,
    products: Sequence[Mapping[str, Any]],
    *,
    timeout_seconds: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Amazon": {
            "MAXINE": {
                "RuntimeHarness": {
                    "EnableCharacterProductLoadProbe": True,
                    "CharacterProductLoadProbe": {
                        "ProductCount": len(products),
                        "TimeoutTicks": _runtime_character_product_load_timeout_ticks(timeout_seconds),
                        "RequireAllProductsReady": True,
                        "Products": {
                            str(index): {
                                "Kind": str(product.get("product_kind", "")),
                                "ProductPath": str(product.get("product_path", "")),
                                "CatalogPath": str(product.get("catalog_path", "")),
                                "ExpectedCategory": str(product.get("expected_category", "")),
                            }
                            for index, product in enumerate(products)
                        },
                    },
                }
            }
        }
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_runtime_character_spawn_instantiation_patch(
    path: Path,
    *,
    product_evidence: Mapping[str, Any],
    project: Path | None,
    engine_root: Path | None,
    timeout_seconds: int,
) -> None:
    selected = _runtime_character_spawn_instantiation_approved_spawnable(
        product_evidence=product_evidence,
        project=project,
        engine_root=engine_root,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Amazon": {
            "MAXINE": {
                "RuntimeHarness": {
                    "EnableCharacterSpawnInstantiationProbe": True,
                    "CharacterSpawnInstantiationProbe": {
                        "SpawnableProductPath": str(
                            selected.get("product_path", RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_PRODUCT)
                        ),
                        "SpawnableCatalogPath": str(
                            selected.get("catalog_path", RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_CATALOG)
                        ),
                        "SpawnableAssetId": str(selected.get("asset_id", "")),
                        "SpawnableAssetType": str(selected.get("asset_type", RUNTIME_SPAWNABLE_ASSET_TYPE)),
                        "TimeoutTicks": _runtime_character_product_load_timeout_ticks(timeout_seconds),
                        "RequirePositiveEntityCount": True,
                        "CleanupSpawnedEntities": True,
                    },
                }
            }
        }
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _runtime_pre_autoexec_suppression_source_payload(
    *,
    project: Path | None,
    engine_root: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    later_payload = _runtime_later_registry_patch_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
    )
    source_validated = _runtime_pre_autoexec_source_validated(engine_root)
    status = (
        "runtime_pre_autoexec_suppression_source_discovery_pass"
        if source_validated
        else "runtime_pre_autoexec_suppression_source_discovery_inconclusive"
    )
    selected_candidate = _runtime_pre_autoexec_selected_candidate(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
    )
    cache_bootstrap_sources = _runtime_cache_bootstrap_default_level_sources(project)
    candidates = _runtime_pre_autoexec_candidate_matrix(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
    )
    later_payload.update(
        {
            "runtime_pre_autoexec_loadlevel_suppression": {
                "status": status,
                "selected": RUNTIME_PRE_AUTOEXEC_SUPPRESSION_SELECTED if source_validated else "",
                "candidate_count": len(candidates),
            },
            "runtime_pre_autoexec_loadlevel_suppression_status": status,
            "runtime_pre_autoexec_loadlevel_suppression_candidates": candidates,
            "runtime_pre_autoexec_candidate_matrix_recorded": bool(candidates),
            "runtime_pre_autoexec_candidate_id": selected_candidate["id"] if source_validated else "",
            "runtime_pre_autoexec_candidate_name": selected_candidate["name"] if source_validated else "",
            "runtime_pre_autoexec_candidate_kind": selected_candidate["kind"] if source_validated else "",
            "runtime_pre_autoexec_candidate_source_validation": selected_candidate["source_validation"]
            if source_validated
            else {},
            "runtime_pre_autoexec_candidate_source_refs": selected_candidate["source_refs"] if source_validated else [],
            "runtime_pre_autoexec_candidate_surface": selected_candidate["surface"] if source_validated else "",
            "runtime_pre_autoexec_candidate_merge_order": selected_candidate["merge_order"] if source_validated else "",
            "runtime_pre_autoexec_candidate_pre_autoexec_verified": bool(source_validated),
            "runtime_pre_autoexec_candidate_patch_path": selected_candidate["patch_path"] if source_validated else "",
            "runtime_pre_autoexec_candidate_patch_contents_summary": selected_candidate["patch_contents_summary"]
            if source_validated
            else "",
            "runtime_pre_autoexec_candidate_mutates_project": selected_candidate["mutates_project"]
            if source_validated
            else False,
            "runtime_pre_autoexec_candidate_mutates_project_user": selected_candidate["mutates_project_user"]
            if source_validated
            else False,
            "runtime_pre_autoexec_candidate_mutates_defaultlevel": False,
            "runtime_pre_autoexec_candidate_mutates_production_level": False,
            "runtime_pre_autoexec_candidate_reversible": selected_candidate["reversible"] if source_validated else False,
            "runtime_pre_autoexec_candidate_rollback": selected_candidate["rollback"] if source_validated else "",
            "runtime_pre_autoexec_candidate_gate_env": selected_candidate["gate_env"] if source_validated else [],
            "runtime_pre_autoexec_candidate_command_args": [],
            "runtime_pre_autoexec_candidate_settings_registry_keys": selected_candidate["settings_registry_keys"]
            if source_validated
            else [],
            "runtime_pre_autoexec_candidate_expected_registry_state": selected_candidate["expected_registry_state"]
            if source_validated
            else {},
            "runtime_pre_autoexec_candidate_actual_registry_state": {},
            "runtime_pre_autoexec_candidate_expected_level_loads": [],
            "runtime_pre_autoexec_candidate_actual_level_loads": [],
            "runtime_pre_autoexec_candidate_attempted": False,
            "runtime_pre_autoexec_candidate_result": selected_candidate["result"] if source_validated else "",
            "runtime_pre_autoexec_candidate_rejected_reason": "",
            "runtime_pre_autoexec_candidate_blocker": "",
            "runtime_pre_autoexec_candidate_mutation_path": selected_candidate["mutation_path"] if source_validated else "",
            "runtime_pre_autoexec_candidate_mutation_disabled_path": selected_candidate["disabled_path"]
            if source_validated
            else "",
            "runtime_pre_autoexec_candidate_mutation_backup_path": selected_candidate["backup_path"]
            if source_validated
            else "",
            "runtime_pre_autoexec_candidate_mutation_pre_refs": [],
            "runtime_pre_autoexec_candidate_mutation_post_refs": [],
            "runtime_pre_autoexec_candidate_mutation_restored": False,
            "runtime_pre_autoexec_cache_bootstrap_loadlevel_sources": cache_bootstrap_sources,
            "runtime_pre_autoexec_cache_bootstrap_loadlevel_source_count": len(cache_bootstrap_sources),
            "runtime_pre_autoexec_cache_bootstrap_loadlevel_blocker": (
                RUNTIME_PRE_AUTOEXEC_CACHE_BOOTSTRAP_BLOCKER if cache_bootstrap_sources else ""
            ),
            "runtime_pre_autoexec_selected": RUNTIME_PRE_AUTOEXEC_SUPPRESSION_SELECTED if source_validated else "",
            "runtime_pre_autoexec_selected_reason": "temporarily_disables_project_registry_load_level_setreg_before_autoexec"
            if source_validated
            else "",
            "runtime_pre_autoexec_suppression_verified": False,
            "runtime_settings_registry_project_user_registry_order": (
                "project_user_registry_merges_before_project_registry_in_shared_settings_and_again_after_project_registry_in_user_settings"
            )
            if source_validated
            else "",
            "runtime_console_autoexec_notification_timing": (
                "console_registers_settings_registry_notifier_before_project_registry_merge_and_executes_autoexec_on_each_merged_key"
            )
            if source_validated
            else "",
            "runtime_spawnable_level_deferred_load_timing": (
                "LoadLevel_before_level_system_queues_deferred_key_and_spawnable_level_system_consumes_it_in_constructor"
            )
            if source_validated
            else "",
            "runtime_default_level_override_blocker": ""
            if source_validated
            else "blocked_by_missing_pre_autoexec_loadlevel_suppression",
            "defaultlevel_mutation": False,
            "production_level_mutation": False,
        }
    )
    return later_payload


def _runtime_pre_autoexec_suppression_execution_payload(
    *,
    project: Path | None,
    command: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    actual_level_loads: Sequence[str],
    pre_autoexec_suppression: bool,
    launch_hygiene: Mapping[str, Any],
    exit_code: int | None,
    marker_observed: bool,
    artifact_dir: Path,
    mutation_state: Mapping[str, Any],
) -> Dict[str, Any]:
    if not pre_autoexec_suppression:
        return {}
    source_payload = _runtime_pre_autoexec_suppression_source_payload(
        project=project,
        engine_root=_runtime_engine_root_from_command(command),
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        artifact_dir=artifact_dir,
    )
    selected_candidate = _runtime_pre_autoexec_selected_candidate(
        project=project,
        engine_root=_runtime_engine_root_from_command(command),
        artifact_dir=artifact_dir,
    )
    cache_bootstrap_sources = _runtime_cache_bootstrap_default_level_sources(project)
    default_level_detected = bool(launch_hygiene.get("runtime_default_level_autoload_detected"))
    launch_pass = str(launch_hygiene.get("runtime_launch_hygiene_status", "")).strip() == "runtime_launch_hygiene_pass"
    ap_status = str(
        launch_hygiene.get("runtime_asset_processor_negotiation_signal_status", "runtime_execution_not_attempted")
    )
    shader_status = str(launch_hygiene.get("runtime_shader_serializer_signal_status", "runtime_execution_not_attempted"))
    if launch_pass:
        suppression_status = "runtime_pre_autoexec_suppression_verified_no_defaultlevel"
        candidate_result = "runtime_pre_autoexec_candidate_attempted_pass"
        blocker = ""
    elif default_level_detected:
        suppression_status = "runtime_pre_autoexec_candidate_attempted_failed_defaultlevel_autoload"
        candidate_result = suppression_status
        blocker = RUNTIME_PRE_AUTOEXEC_CACHE_BOOTSTRAP_BLOCKER if cache_bootstrap_sources else "blocked_by_default_level_autoload"
    elif launch_hygiene.get("runtime_asset_processor_negotiation_disqualifying") is True or launch_hygiene.get(
        "runtime_shader_serializer_disqualifying"
    ) is True:
        suppression_status = "runtime_pre_autoexec_candidate_attempted_failed_disqualifying_signal"
        candidate_result = suppression_status
        blocker = "blocked_by_disqualifying_runtime_signals"
    else:
        suppression_status = "runtime_pre_autoexec_candidate_attempted_failed_disqualifying_signal"
        candidate_result = suppression_status
        blocker = "blocked_by_disqualifying_runtime_signals"

    source_payload.update(
        {
            "runtime_pre_autoexec_loadlevel_suppression": {
                "status": suppression_status,
                "selected": RUNTIME_PRE_AUTOEXEC_SUPPRESSION_SELECTED,
                "attempted": True,
                "actual_level_loads": list(actual_level_loads),
            },
            "runtime_pre_autoexec_loadlevel_suppression_status": suppression_status,
            "runtime_pre_autoexec_candidate_id": selected_candidate["id"],
            "runtime_pre_autoexec_candidate_name": selected_candidate["name"],
            "runtime_pre_autoexec_candidate_kind": selected_candidate["kind"],
            "runtime_pre_autoexec_candidate_source_validation": selected_candidate["source_validation"],
            "runtime_pre_autoexec_candidate_source_refs": selected_candidate["source_refs"],
            "runtime_pre_autoexec_candidate_surface": selected_candidate["surface"],
            "runtime_pre_autoexec_candidate_merge_order": selected_candidate["merge_order"],
            "runtime_pre_autoexec_candidate_pre_autoexec_verified": True,
            "runtime_pre_autoexec_candidate_patch_path": "",
            "runtime_pre_autoexec_candidate_patch_contents_summary": "",
            "runtime_pre_autoexec_candidate_mutates_project": True,
            "runtime_pre_autoexec_candidate_mutates_project_user": False,
            "runtime_pre_autoexec_candidate_mutates_defaultlevel": False,
            "runtime_pre_autoexec_candidate_mutates_production_level": False,
            "runtime_pre_autoexec_candidate_reversible": True,
            "runtime_pre_autoexec_candidate_rollback": selected_candidate["rollback"],
            "runtime_pre_autoexec_candidate_gate_env": selected_candidate["gate_env"],
            "runtime_pre_autoexec_candidate_command_args": [],
            "runtime_pre_autoexec_candidate_settings_registry_keys": selected_candidate["settings_registry_keys"],
            "runtime_pre_autoexec_candidate_expected_registry_state": selected_candidate["expected_registry_state"],
            "runtime_pre_autoexec_candidate_actual_registry_state": {
                "defaultlevel_autoload_detected": default_level_detected,
                "load_level_setreg_temporarily_disabled": mutation_state.get("applied", False),
                "load_level_setreg_restored_after_run": mutation_state.get("restored", False),
                "asset_processor_negotiation_status": ap_status,
                "shader_serializer_status": shader_status,
            },
            "runtime_pre_autoexec_candidate_expected_level_loads": [],
            "runtime_pre_autoexec_candidate_actual_level_loads": list(actual_level_loads),
            "runtime_pre_autoexec_candidate_attempted": True,
            "runtime_pre_autoexec_candidate_result": candidate_result,
            "runtime_pre_autoexec_candidate_rejected_reason": "",
            "runtime_pre_autoexec_candidate_blocker": blocker,
            "runtime_pre_autoexec_candidate_mutation_path": _path_text(str(mutation_state.get("source_path", ""))),
            "runtime_pre_autoexec_candidate_mutation_disabled_path": _path_text(
                str(mutation_state.get("disabled_path", ""))
            ),
            "runtime_pre_autoexec_candidate_mutation_backup_path": _path_text(str(mutation_state.get("backup_path", ""))),
            "runtime_pre_autoexec_candidate_mutation_pre_refs": list(mutation_state.get("pre_refs", [])),
            "runtime_pre_autoexec_candidate_mutation_post_refs": list(mutation_state.get("post_refs", [])),
            "runtime_pre_autoexec_candidate_mutation_restored": bool(mutation_state.get("restored", False)),
            "runtime_pre_autoexec_cache_bootstrap_loadlevel_sources": cache_bootstrap_sources,
            "runtime_pre_autoexec_cache_bootstrap_loadlevel_source_count": len(cache_bootstrap_sources),
            "runtime_pre_autoexec_cache_bootstrap_loadlevel_blocker": (
                RUNTIME_PRE_AUTOEXEC_CACHE_BOOTSTRAP_BLOCKER if cache_bootstrap_sources else ""
            ),
            "runtime_pre_autoexec_selected": RUNTIME_PRE_AUTOEXEC_SUPPRESSION_SELECTED,
            "runtime_pre_autoexec_selected_reason": "temporarily_disables_project_registry_load_level_setreg_before_autoexec",
            "runtime_pre_autoexec_suppression_verified": bool(launch_pass),
            "runtime_loadlevel_override_status": "runtime_loadlevel_override_verified_no_defaultlevel"
            if launch_pass
            else "runtime_loadlevel_override_candidate_attempted_failed_defaultlevel_autoload"
            if default_level_detected
            else "runtime_loadlevel_override_candidate_attempted_failed_disqualifying_signal",
            "runtime_loadlevel_override_selected": RUNTIME_PRE_AUTOEXEC_SUPPRESSION_SELECTED,
            "runtime_loadlevel_override_selected_reason": "pre_autoexec_project_registry_load_level_suppression",
            "runtime_loadlevel_override_verified": bool(launch_pass),
            "runtime_autoexec_console_command_override_state": {
                "selected_args": [],
                "mutates_project_registry": True,
                "mutates_project_user_registry": False,
                "mutates_defaultlevel": False,
                "mutation_path": _path_text(str(mutation_state.get("source_path", ""))),
                "mutation_restored": bool(mutation_state.get("restored", False)),
                "exit_code_decimal": exit_code,
                "exit_code_hex": _exit_code_hex(exit_code),
                "fixture_marker_observed": marker_observed,
            },
            "runtime_default_level_override_blocker": blocker,
            "defaultlevel_mutation": False,
            "production_level_mutation": False,
            "runtime_exit_fixture_project_mutation_status": "runtime_exit_fixture_project_mutation_gate_pass",
            "runtime_exit_fixture_project_mutation_attempted": True,
            "runtime_exit_fixture_project_mutation_files": [_path_text(str(mutation_state.get("source_path", "")))],
            "runtime_exit_fixture_project_mutation_before_refs": list(mutation_state.get("pre_refs", [])),
            "runtime_exit_fixture_project_mutation_after_refs": list(mutation_state.get("post_refs", [])),
            "runtime_exit_fixture_project_mutation_diff_summary": [
                "temporarily_renamed_project_registry_load_level_setreg",
                "restored_project_registry_load_level_setreg_after_runtime_command",
            ],
            "runtime_exit_fixture_project_mutation_reversible": True,
            "runtime_exit_fixture_project_mutation_rollback": selected_candidate["rollback"],
            "runtime_exit_fixture_project_mutation_gate_env": list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV),
        }
    )
    return source_payload


def _runtime_pre_autoexec_selected_candidate(
    *,
    project: Path | None,
    engine_root: Path | None,
    artifact_dir: Path,
) -> Dict[str, Any]:
    source_path = _runtime_default_level_source_path(project)
    disabled_path = _runtime_pre_autoexec_disabled_path(project)
    backup_path = artifact_dir / RUNTIME_PRE_AUTOEXEC_SUPPRESSION_BACKUP_FILENAME
    return {
        "id": RUNTIME_PRE_AUTOEXEC_SUPPRESSION_SELECTED,
        "name": "Temporarily disable project Registry/load_level.setreg before console autoexec",
        "kind": "gated_reversible_project_registry_file_suppression",
        "source_validation": {
            "status": "runtime_pre_autoexec_candidate_source_validated"
            if _runtime_pre_autoexec_source_validated(engine_root)
            else "runtime_pre_autoexec_candidate_rejected_missing_source_validation",
            "summary": (
                "ComponentApplication creates the console and registers settings-registry notifications before "
                "MergeSettingsToRegistry loads project Registry files. MergeSettingsFolder applies project files one by one "
                "and notifies merged keys immediately, so Registry/load_level.setreg executes LoadLevel before project-user "
                "or final command-line overrides can clear it. The selected safe harness strategy temporarily renames the "
                "project load_level.setreg file before launch and restores it after the bounded fixture process exits."
            ),
        },
        "source_refs": _runtime_pre_autoexec_source_refs(project, engine_root),
        "surface": _path_text(source_path),
        "merge_order": "suppresses_project_registry_file_before_project_registry_merge_and_before_console_autoexec_notification",
        "patch_path": "",
        "patch_contents_summary": "",
        "mutates_project": True,
        "mutates_project_user": False,
        "reversible": True,
        "rollback": _runtime_pre_autoexec_rollback(project),
        "gate_env": list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV),
        "mutation_path": _path_text(source_path),
        "disabled_path": _path_text(disabled_path),
        "backup_path": _path_text(backup_path),
        "settings_registry_keys": [RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY, RUNTIME_DEFERRED_LOADLEVEL_KEY],
        "expected_registry_state": {
            "project_registry_load_level_file": "temporarily_absent_during_runtime_launch",
            "autoexec_loadlevel": "not_merged_from_project_load_level_setreg",
            "spawnable_deferred_loadlevel": "not_queued_from_project_load_level_setreg",
            "project_registry_mutation": "temporary_rename_with_backup_and_restore",
            "defaultlevel_mutation": False,
            "production_level_mutation": False,
        },
        "expected_level_loads": [],
        "result": "runtime_pre_autoexec_candidate_source_validated",
    }


def _runtime_pre_autoexec_candidate_matrix(
    *,
    project: Path | None,
    engine_root: Path | None,
    artifact_dir: Path,
) -> List[Dict[str, Any]]:
    loadlevel = _runtime_loadlevel_override_candidate_matrix(project, engine_root)
    later = _runtime_later_registry_patch_selected_candidate(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
    )
    selected = _runtime_pre_autoexec_selected_candidate(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
    )
    return [
        {
            **loadlevel[0],
            "result": "runtime_pre_autoexec_candidate_rejected_prior_regremove_failed_defaultlevel_autoload",
            "blocker": "blocked_by_regremove_ineffective",
        },
        {
            **loadlevel[1],
            "attempted": True,
            "actual_level_loads": [RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH],
            "result": "runtime_pre_autoexec_candidate_rejected_prior_regremove_failed_defaultlevel_autoload",
            "blocker": "blocked_by_settings_registry_merge_order",
        },
        {
            **later,
            "attempted": True,
            "actual_level_loads": [RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH],
            "actual_registry_state": {
                "final_regset_file_merge_failed": False,
                "autoexec_notification_already_executed_before_final_regset_file": True,
            },
            "result": "runtime_pre_autoexec_candidate_rejected_late_command_line_registry_merge",
            "blocker": "blocked_by_late_command_line_registry_merge",
        },
        {
            "id": "project_user_registry_null_delete_loadlevel",
            "name": "Project-user registry null-deletes Autoexec LoadLevel",
            "kind": "project_user_registry_json_merge_patch_null_delete",
            "source_validation": {
                "status": "runtime_pre_autoexec_candidate_source_validated",
                "summary": (
                    "Project-user registry is merged before project registry in shared settings and again after "
                    "project registry in user settings. The early pass is overwritten by Registry/load_level.setreg, "
                    "and the late pass occurs after the project registry notification has already executed LoadLevel."
                ),
            },
            "source_refs": _runtime_pre_autoexec_source_refs(project, engine_root),
            "surface": _path_text((project or Path("<project>")) / "user" / "Registry"),
            "merge_order": "project_user_registry_before_project_registry_then_after_autoexec_notification",
            "gate_env": list(RUNTIME_EXIT_FIXTURE_TEMP_REGISTRY_PATCH_GATE_ENV),
            "settings_registry_keys": [RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY, RUNTIME_DEFERRED_LOADLEVEL_KEY],
            "expected_registry_state": {
                "autoexec_loadlevel": "not_reliably_suppressed_before_project_registry_notification",
                "project_registry_mutation": False,
                "defaultlevel_mutation": False,
                "production_level_mutation": False,
            },
            "expected_level_loads": [],
            "actual_level_loads": [RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH],
            "attempted": False,
            "result": "runtime_pre_autoexec_candidate_rejected_project_user_precedes_project_registry",
            "blocker": "blocked_by_project_user_registry_override_not_safe",
        },
        {
            "id": "project_cache_bootstrap_setreg_defaultlevel_suppression",
            "name": "Project Cache bootstrap setreg defaultlevel suppression",
            "kind": "generated_project_cache_bootstrap_registry_mutation",
            "source_validation": {
                "status": "runtime_pre_autoexec_candidate_source_validated",
                "summary": (
                    "Read-only live evidence shows generated project Cache/pc/bootstrap*.setreg files can embed "
                    "O3DE Autoexec ConsoleCommands LoadLevel=defaultlevel. Mutating those generated cache products "
                    "would touch Asset Cache/build products, so this slice records the source as a blocker instead "
                    "of editing or deleting cache content."
                ),
            },
            "source_refs": _runtime_cache_bootstrap_default_level_sources(project),
            "surface": _path_text((project or Path("<project>")) / "Cache" / "pc" / "bootstrap*.setreg"),
            "merge_order": "cache_bootstrap_registry_is_available_before_project_registry_source_suppression",
            "gate_env": [],
            "settings_registry_keys": [RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY, RUNTIME_DEFERRED_LOADLEVEL_KEY],
            "expected_registry_state": {
                "autoexec_loadlevel": "would_require_generated_cache_bootstrap_mutation",
                "asset_cache_mutation": True,
                "defaultlevel_mutation": False,
                "production_level_mutation": False,
            },
            "expected_level_loads": [],
            "actual_level_loads": [RUNTIME_DEFAULT_LEVEL_PRODUCT_PATH],
            "attempted": False,
            "result": "runtime_pre_autoexec_candidate_rejected_requires_asset_cache_mutation",
            "blocker": RUNTIME_PRE_AUTOEXEC_CACHE_BOOTSTRAP_BLOCKER,
        },
        {
            **selected,
            "actual_registry_state": {},
            "actual_level_loads": [],
            "attempted": False,
            "blocker": "",
        },
    ]


def _runtime_pre_autoexec_source_validated(engine_root: Path | None) -> bool:
    return _runtime_loadlevel_override_source_validated(engine_root)


def _runtime_pre_autoexec_source_refs(project: Path | None, engine_root: Path | None) -> List[str]:
    return _runtime_loadlevel_override_source_refs(project, engine_root)


def _runtime_default_level_source_path(project: Path | None) -> Path:
    return (project or Path("<project>")) / "Registry" / "load_level.setreg"


def _runtime_pre_autoexec_disabled_path(project: Path | None) -> Path:
    return (project or Path("<project>")) / "Registry" / RUNTIME_PRE_AUTOEXEC_SUPPRESSION_DISABLED_FILENAME


def _runtime_cache_bootstrap_default_level_sources(project: Path | None) -> List[str]:
    if project is None:
        return []
    cache_dir = project / "Cache" / "pc"
    if not cache_dir.is_dir():
        return []
    sources: List[str] = []
    for path in sorted(cache_dir.glob("bootstrap*.setreg")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if "LoadLevel" in text and "defaultlevel" in text.lower():
            sources.append(_path_text(path))
    return sources


def _runtime_pre_autoexec_rollback(project: Path | None) -> str:
    source_path = _runtime_default_level_source_path(project)
    disabled_path = _runtime_pre_autoexec_disabled_path(project)
    return (
        f"If interrupted, move {disabled_path} back to {source_path}; the harness also writes a backup under "
        f"{DEFAULT_ARTIFACT_ROOT / RUNTIME_PRE_AUTOEXEC_SUPPRESSION_BACKUP_FILENAME}."
    )


def _apply_runtime_pre_autoexec_suppression(*, project: Path | None, artifact_dir: Path) -> Dict[str, Any]:
    source_path = _runtime_default_level_source_path(project)
    disabled_path = _runtime_pre_autoexec_disabled_path(project)
    backup_path = artifact_dir / RUNTIME_PRE_AUTOEXEC_SUPPRESSION_BACKUP_FILENAME
    state: Dict[str, Any] = {
        "status": "runtime_pre_autoexec_project_registry_mutation_not_attempted",
        "source_path": _path_text(source_path),
        "disabled_path": _path_text(disabled_path),
        "backup_path": _path_text(backup_path),
        "applied": False,
        "restored": False,
        "pre_refs": [_path_text(source_path)],
        "post_refs": [],
    }
    if project is None or not source_path.is_file():
        state["status"] = "blocked_by_missing_project_load_level_setreg"
        return state
    if disabled_path.exists():
        state["status"] = "blocked_by_existing_pre_autoexec_disabled_file"
        return state
    artifact_dir.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(source_path.read_text(encoding="utf-8-sig", errors="replace"), encoding="utf-8")
    source_path.replace(disabled_path)
    state.update(
        {
            "status": "runtime_pre_autoexec_project_registry_mutation_applied",
            "applied": True,
            "pre_refs": [_path_text(source_path), _path_text(backup_path)],
            "post_refs": [_path_text(disabled_path), _path_text(backup_path)],
        }
    )
    return state


def _restore_runtime_pre_autoexec_suppression(state: Dict[str, Any]) -> None:
    if not state or not state.get("applied"):
        return
    source_path = Path(str(state.get("source_path", "")))
    disabled_path = Path(str(state.get("disabled_path", "")))
    if disabled_path.is_file() and not source_path.exists():
        disabled_path.replace(source_path)
        state["restored"] = True
        state["status"] = "runtime_pre_autoexec_project_registry_mutation_restored"
        state["post_refs"] = [_path_text(source_path), _path_text(str(state.get("backup_path", "")))]
    else:
        state["restored"] = source_path.is_file() and not disabled_path.exists()
        if state["restored"]:
            state["status"] = "runtime_pre_autoexec_project_registry_mutation_restored"


def _runtime_cache_bootstrap_source_payload(
    *,
    project: Path | None,
    engine_root: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    pre_autoexec_payload = _runtime_pre_autoexec_suppression_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
    )
    source_validated = _runtime_cache_bootstrap_source_validated(engine_root)
    files = _runtime_cache_bootstrap_files(project)
    loadlevel_files = [entry for entry in files if entry.get("contains_loadlevel")]
    status = (
        "runtime_cache_bootstrap_source_discovery_pass"
        if source_validated
        else "runtime_cache_bootstrap_source_discovery_inconclusive"
    )
    discovery_status = (
        "runtime_cache_bootstrap_loadlevel_source_detected"
        if loadlevel_files
        else "runtime_cache_bootstrap_loadlevel_source_absent"
    )
    candidates = _runtime_cache_bootstrap_candidate_matrix(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
        files=files,
    )
    selected = _runtime_cache_bootstrap_selected_candidate(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
        files=files,
    )
    pre_autoexec_payload.update(
        {
            "runtime_cache_bootstrap_loadlevel_source": {
                "status": status,
                "source_discovery_status": discovery_status,
                "file_count": len(files),
                "loadlevel_file_count": len(loadlevel_files),
            },
            "runtime_cache_bootstrap_loadlevel_source_status": status,
            "runtime_cache_bootstrap_source_discovery_status": discovery_status,
            "runtime_cache_bootstrap_files": files,
            "runtime_cache_bootstrap_generation_source": "AssetProcessor_SettingsRegistryBuilder",
            "runtime_cache_bootstrap_generation_source_refs": _runtime_cache_bootstrap_source_refs(project, engine_root),
            "runtime_cache_bootstrap_generation_timing": (
                "AssetProcessor_internal_SettingsRegistryBuilder_generates_bootstrap_launcher_config_setreg_products_from_engine_gem_project_registry"
            ),
            "runtime_cache_bootstrap_runtime_load_timing": (
                "GameApplication_MergeSettingsToRegistry_merges_bootstrap_launcher_config_setreg_from_cache_root_after_shared_settings_before_user_settings"
            ),
            "runtime_cache_bootstrap_autoload_correlation": (
                "cache_bootstrap_files_contain_autoexec_loadlevel_defaultlevel"
                if loadlevel_files
                else "cache_bootstrap_files_do_not_contain_autoexec_loadlevel_defaultlevel"
            ),
            "runtime_cache_bootstrap_candidate_matrix": candidates,
            "runtime_cache_bootstrap_candidate_matrix_recorded": bool(candidates),
            "runtime_cache_bootstrap_candidate_id": selected["id"] if source_validated else "",
            "runtime_cache_bootstrap_candidate_name": selected["name"] if source_validated else "",
            "runtime_cache_bootstrap_candidate_kind": selected["kind"] if source_validated else "",
            "runtime_cache_bootstrap_candidate_source_validation": selected["source_validation"] if source_validated else {},
            "runtime_cache_bootstrap_candidate_source_refs": selected["source_refs"] if source_validated else [],
            "runtime_cache_bootstrap_candidate_expected_files": selected["expected_files"] if source_validated else [],
            "runtime_cache_bootstrap_candidate_actual_files": files,
            "runtime_cache_bootstrap_candidate_expected_level_loads": [],
            "runtime_cache_bootstrap_candidate_actual_level_loads": [],
            "runtime_cache_bootstrap_candidate_mutates_cache": selected["mutates_cache"] if source_validated else False,
            "runtime_cache_bootstrap_candidate_mutates_project": selected["mutates_project"] if source_validated else False,
            "runtime_cache_bootstrap_candidate_mutates_defaultlevel": False,
            "runtime_cache_bootstrap_candidate_mutates_production_level": False,
            "runtime_cache_bootstrap_candidate_reversible": selected["reversible"] if source_validated else False,
            "runtime_cache_bootstrap_candidate_backup_refs": [],
            "runtime_cache_bootstrap_candidate_restore_status": "not_attempted",
            "runtime_cache_bootstrap_candidate_hash_verified": False,
            "runtime_cache_bootstrap_candidate_gate_env": selected["gate_env"] if source_validated else [],
            "runtime_cache_bootstrap_candidate_attempted": False,
            "runtime_cache_bootstrap_candidate_result": selected["result"] if source_validated else "",
            "runtime_cache_bootstrap_candidate_blocker": "",
            "runtime_cache_bootstrap_selected": RUNTIME_CACHE_BOOTSTRAP_SELECTED if source_validated else "",
            "runtime_cache_bootstrap_selected_reason": "temporarily_neutralizes_generated_cache_bootstrap_loadlevel_with_backup_restore_hash_verification"
            if source_validated
            else "",
            "runtime_cache_bootstrap_verified": False,
            "runtime_cache_bootstrap_refresh_required": False,
            "runtime_cache_bootstrap_refresh_attempted": False,
            "runtime_cache_bootstrap_refresh_command": [],
            "runtime_cache_bootstrap_refresh_result": "runtime_cache_bootstrap_refresh_not_attempted",
            "runtime_cache_bootstrap_refresh_stdout_ref": "",
            "runtime_cache_bootstrap_refresh_stderr_ref": "",
            "runtime_cache_bootstrap_refresh_log_refs": [],
            "asset_cache_deleted": False,
            "runtime_default_level_override_blocker": ""
            if source_validated
            else "blocked_by_cache_bootstrap_loadlevel_source",
        }
    )
    return pre_autoexec_payload


def _runtime_cache_bootstrap_execution_payload(
    *,
    project: Path | None,
    command: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    actual_level_loads: Sequence[str],
    cache_bootstrap_strategy: bool,
    launch_hygiene: Mapping[str, Any],
    exit_code: int | None,
    marker_observed: bool,
    artifact_dir: Path,
    mutation_state: Mapping[str, Any],
) -> Dict[str, Any]:
    if not cache_bootstrap_strategy:
        return {}
    source_payload = _runtime_cache_bootstrap_source_payload(
        project=project,
        engine_root=_runtime_engine_root_from_command(command),
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        artifact_dir=artifact_dir,
    )
    selected = _runtime_cache_bootstrap_selected_candidate(
        project=project,
        engine_root=_runtime_engine_root_from_command(command),
        artifact_dir=artifact_dir,
        files=_runtime_cache_bootstrap_files(project),
    )
    default_level_detected = bool(launch_hygiene.get("runtime_default_level_autoload_detected"))
    launch_pass = str(launch_hygiene.get("runtime_launch_hygiene_status", "")).strip() == "runtime_launch_hygiene_pass"
    ap_status = str(
        launch_hygiene.get("runtime_asset_processor_negotiation_signal_status", "runtime_execution_not_attempted")
    )
    shader_status = str(launch_hygiene.get("runtime_shader_serializer_signal_status", "runtime_execution_not_attempted"))
    if launch_pass:
        cache_status = "runtime_cache_bootstrap_verified_no_defaultlevel"
        candidate_result = "runtime_cache_bootstrap_candidate_attempted_pass"
        blocker = ""
    elif default_level_detected:
        cache_status = "runtime_cache_bootstrap_candidate_attempted_failed_defaultlevel_autoload"
        candidate_result = cache_status
        blocker = "blocked_by_default_level_autoload"
    elif launch_hygiene.get("runtime_asset_processor_negotiation_disqualifying") is True or launch_hygiene.get(
        "runtime_shader_serializer_disqualifying"
    ) is True:
        cache_status = "runtime_cache_bootstrap_candidate_attempted_failed_disqualifying_signal"
        candidate_result = cache_status
        blocker = "blocked_by_disqualifying_runtime_signals"
    else:
        cache_status = "runtime_cache_bootstrap_candidate_attempted_failed_disqualifying_signal"
        candidate_result = cache_status
        blocker = "blocked_by_disqualifying_runtime_signals"

    source_payload.update(
        {
            "runtime_cache_bootstrap_loadlevel_source": {
                "status": cache_status,
                "selected": RUNTIME_CACHE_BOOTSTRAP_SELECTED,
                "attempted": True,
                "actual_level_loads": list(actual_level_loads),
            },
            "runtime_cache_bootstrap_loadlevel_source_status": cache_status,
            "runtime_cache_bootstrap_candidate_id": selected["id"],
            "runtime_cache_bootstrap_candidate_name": selected["name"],
            "runtime_cache_bootstrap_candidate_kind": selected["kind"],
            "runtime_cache_bootstrap_candidate_source_validation": selected["source_validation"],
            "runtime_cache_bootstrap_candidate_source_refs": selected["source_refs"],
            "runtime_cache_bootstrap_candidate_expected_files": selected["expected_files"],
            "runtime_cache_bootstrap_candidate_actual_files": list(mutation_state.get("files", [])),
            "runtime_cache_bootstrap_candidate_expected_level_loads": [],
            "runtime_cache_bootstrap_candidate_actual_level_loads": list(actual_level_loads),
            "runtime_cache_bootstrap_candidate_mutates_cache": True,
            "runtime_cache_bootstrap_candidate_mutates_project": True,
            "runtime_cache_bootstrap_candidate_mutates_defaultlevel": False,
            "runtime_cache_bootstrap_candidate_mutates_production_level": False,
            "runtime_cache_bootstrap_candidate_reversible": True,
            "runtime_cache_bootstrap_candidate_backup_refs": list(mutation_state.get("backup_refs", [])),
            "runtime_cache_bootstrap_candidate_restore_status": str(
                mutation_state.get("restore_status", "runtime_cache_bootstrap_restore_not_attempted")
            ),
            "runtime_cache_bootstrap_candidate_hash_verified": bool(mutation_state.get("hash_verified", False)),
            "runtime_cache_bootstrap_candidate_gate_env": selected["gate_env"],
            "runtime_cache_bootstrap_candidate_attempted": True,
            "runtime_cache_bootstrap_candidate_result": candidate_result,
            "runtime_cache_bootstrap_candidate_blocker": blocker,
            "runtime_cache_bootstrap_selected": RUNTIME_CACHE_BOOTSTRAP_SELECTED,
            "runtime_cache_bootstrap_selected_reason": "temporarily_neutralizes_generated_cache_bootstrap_loadlevel_with_backup_restore_hash_verification",
            "runtime_cache_bootstrap_verified": bool(launch_pass),
            "runtime_cache_bootstrap_refresh_required": False,
            "runtime_cache_bootstrap_refresh_attempted": False,
            "runtime_cache_bootstrap_refresh_result": "runtime_cache_bootstrap_refresh_not_attempted",
            "runtime_autoexec_console_command_override_state": {
                "selected_args": [],
                "mutates_project_registry": True,
                "mutates_cache_bootstrap": True,
                "mutates_defaultlevel": False,
                "cache_bootstrap_restore_status": mutation_state.get("restore_status", ""),
                "cache_bootstrap_hash_verified": bool(mutation_state.get("hash_verified", False)),
                "exit_code_decimal": exit_code,
                "exit_code_hex": _exit_code_hex(exit_code),
                "fixture_marker_observed": marker_observed,
            },
            "runtime_default_level_override_blocker": blocker,
            "asset_cache_deleted": False,
            "defaultlevel_mutation": False,
            "production_level_mutation": False,
        }
    )
    return source_payload


def _runtime_cache_bootstrap_selected_candidate(
    *,
    project: Path | None,
    engine_root: Path | None,
    artifact_dir: Path,
    files: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    return {
        "id": RUNTIME_CACHE_BOOTSTRAP_SELECTED,
        "name": "Temporarily neutralize generated Cache/pc/bootstrap*.setreg LoadLevel entries with project source suppression",
        "kind": "gated_reversible_cache_bootstrap_registry_mutation",
        "source_validation": {
            "status": "runtime_cache_bootstrap_candidate_source_validated"
            if _runtime_cache_bootstrap_source_validated(engine_root)
            else "runtime_cache_bootstrap_candidate_rejected_missing_source_validation",
            "summary": (
                "AssetProcessor SettingsRegistryBuilder creates bootstrap.<launcher-type>.<configuration>.setreg products "
                "from engine, gem, and project Registry folders. GameApplication then merges the matching cache bootstrap "
                "file from the project cache root before user settings. The selected diagnostic strategy combines the "
                "PR #135 project source-registry suppression with a gated temporary neutralization of generated bootstrap "
                "LoadLevel and DeferredLoadLevel entries, then restores every generated file and verifies hashes."
            ),
        },
        "source_refs": _runtime_cache_bootstrap_source_refs(project, engine_root),
        "expected_files": [dict(entry) for entry in files if entry.get("contains_loadlevel") or entry.get("contains_deferred_loadlevel")],
        "mutates_cache": True,
        "mutates_project": True,
        "reversible": True,
        "gate_env": list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV)
        + list(RUNTIME_EXIT_FIXTURE_CACHE_BOOTSTRAP_MUTATION_GATE_ENV),
        "result": "runtime_cache_bootstrap_candidate_source_validated",
    }


def _runtime_cache_bootstrap_candidate_matrix(
    *,
    project: Path | None,
    engine_root: Path | None,
    artifact_dir: Path,
    files: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    selected = _runtime_cache_bootstrap_selected_candidate(
        project=project,
        engine_root=engine_root,
        artifact_dir=artifact_dir,
        files=files,
    )
    source_refs = _runtime_cache_bootstrap_source_refs(project, engine_root)
    return [
        {
            "id": "cache_bootstrap_read_only_inventory",
            "name": "Read-only Cache/pc/bootstrap*.setreg inventory",
            "kind": "read_only_cache_bootstrap_inventory",
            "source_validation": {
                "status": "runtime_cache_bootstrap_candidate_source_validated",
                "summary": "Inventory records path, hash, mtime, and LoadLevel/DeferredLoadLevel keys without mutating Asset Cache.",
            },
            "source_refs": source_refs,
            "expected_files": [dict(entry) for entry in files],
            "actual_files": [dict(entry) for entry in files],
            "mutates_cache": False,
            "mutates_project": False,
            "reversible": True,
            "gate_env": [],
            "attempted": False,
            "result": "runtime_cache_bootstrap_loadlevel_source_detected"
            if any(entry.get("contains_loadlevel") for entry in files)
            else "runtime_cache_bootstrap_loadlevel_source_absent",
            "blocker": RUNTIME_PRE_AUTOEXEC_CACHE_BOOTSTRAP_BLOCKER
            if any(entry.get("contains_loadlevel") for entry in files)
            else "",
        },
        {
            "id": "cache_bootstrap_scoped_apb_refresh_after_source_suppression",
            "name": "Scoped APB/bootstrap refresh after source suppression",
            "kind": "asset_processor_settings_registry_builder_refresh",
            "source_validation": {
                "status": "runtime_cache_bootstrap_candidate_source_validated",
                "summary": (
                    "SettingsRegistryBuilder is the source-validated generator, but this harness has not found a "
                    "single-product bootstrap-only refresh command that avoids broader Asset Cache writes."
                ),
            },
            "source_refs": source_refs,
            "expected_files": [],
            "actual_files": [dict(entry) for entry in files],
            "mutates_cache": True,
            "mutates_project": True,
            "reversible": False,
            "gate_env": list(RUNTIME_EXIT_FIXTURE_CACHE_BOOTSTRAP_REFRESH_GATE_ENV)
            + list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV),
            "attempted": False,
            "result": "runtime_cache_bootstrap_candidate_rejected_regeneration_not_safely_scoped",
            "blocker": "blocked_by_cache_bootstrap_regeneration_not_safely_scoped",
        },
        {
            "id": "cache_bootstrap_generated_registry_overlay_before_autoexec",
            "name": "Generated registry overlay loaded before cache bootstrap autoexec",
            "kind": "pre_autoexec_cache_bootstrap_overlay",
            "source_validation": {
                "status": "runtime_cache_bootstrap_candidate_rejected_missing_source_validation",
                "summary": "No source-supported command-line or artifact overlay was found that merges before GameApplication cache bootstrap load.",
            },
            "source_refs": source_refs,
            "expected_files": [],
            "actual_files": [dict(entry) for entry in files],
            "mutates_cache": False,
            "mutates_project": False,
            "reversible": True,
            "gate_env": list(RUNTIME_EXIT_FIXTURE_TEMP_REGISTRY_PATCH_GATE_ENV),
            "attempted": False,
            "result": "runtime_cache_bootstrap_candidate_rejected_missing_source_validation",
            "blocker": "blocked_by_cache_bootstrap_loadlevel_source",
        },
        {
            **selected,
            "actual_files": [],
            "attempted": False,
            "blocker": "",
        },
        {
            "id": "cache_bootstrap_requires_asset_cache_deletion",
            "name": "Delete Asset Cache to force bootstrap regeneration",
            "kind": "asset_cache_deletion",
            "source_validation": {
                "status": "runtime_cache_bootstrap_candidate_rejected_unsafe",
                "summary": "Asset Cache deletion is explicitly forbidden for this production harness slice.",
            },
            "source_refs": source_refs,
            "expected_files": [],
            "actual_files": [dict(entry) for entry in files],
            "mutates_cache": True,
            "deletes_asset_cache": True,
            "mutates_project": False,
            "reversible": False,
            "gate_env": [],
            "attempted": False,
            "result": "runtime_cache_bootstrap_candidate_rejected_requires_asset_cache_deletion",
            "blocker": "blocked_by_asset_cache_deletion_required",
        },
    ]


def _runtime_cache_bootstrap_source_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return all(
        path.is_file()
        for path in (
            root / "Code" / "Tools" / "AssetProcessor" / "native" / "InternalBuilders" / "SettingsRegistryBuilder.cpp",
            root / "Code" / "Framework" / "AzGameFramework" / "AzGameFramework" / "Application" / "GameApplication.cpp",
            root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.cpp",
        )
    )


def _runtime_cache_bootstrap_source_refs(project: Path | None, engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [
        str(root / "Code" / "Tools" / "AssetProcessor" / "native" / "InternalBuilders" / "SettingsRegistryBuilder.cpp"),
        str(root / "Code" / "Framework" / "AzGameFramework" / "AzGameFramework" / "Application" / "GameApplication.cpp"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.cpp"),
        str(root / "Assets" / "Engine" / "SeedAssetList.seed"),
        str((project or Path("<project>")) / "Cache" / "pc" / "bootstrap*.setreg"),
        str((project or Path("<project>")) / "Registry" / "load_level.setreg"),
    ]


def _runtime_cache_bootstrap_files(project: Path | None) -> List[Dict[str, Any]]:
    if project is None:
        return []
    cache_dir = project / "Cache" / "pc"
    if not cache_dir.is_dir():
        return []
    entries: List[Dict[str, Any]] = []
    for path in sorted(cache_dir.glob("bootstrap*.setreg")):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig", errors="replace")
        data: Any = {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        loadlevel_value = _json_pointer_get(data, RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY)
        deferred_value = _json_pointer_get(data, RUNTIME_DEFERRED_LOADLEVEL_KEY)
        stat = path.stat()
        contains_loadlevel = loadlevel_value is not None or "LoadLevel" in text
        contains_deferred = deferred_value is not None or "DeferredLoadLevel" in text
        entries.append(
            {
                "path": _path_text(path),
                "exists": True,
                "hash": _sha256_bytes(raw),
                "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "contains_loadlevel": bool(contains_loadlevel),
                "contains_deferred_loadlevel": bool(contains_deferred),
                "loadlevel_value": "" if loadlevel_value is None else str(loadlevel_value),
                "deferred_loadlevel_value": "" if deferred_value is None else str(deferred_value),
                "source_candidate": "project_registry_load_level_setreg"
                if str(loadlevel_value).lower() == "defaultlevel"
                else "",
            }
        )
    return entries


def _runtime_cache_bootstrap_default_level_sources(project: Path | None) -> List[str]:
    return [
        str(entry.get("path", ""))
        for entry in _runtime_cache_bootstrap_files(project)
        if str(entry.get("loadlevel_value", "")).lower() == "defaultlevel"
    ]


def _apply_runtime_cache_bootstrap_neutralization(*, project: Path | None, artifact_dir: Path) -> Dict[str, Any]:
    backup_dir = artifact_dir / RUNTIME_CACHE_BOOTSTRAP_BACKUP_DIRNAME
    state: Dict[str, Any] = {
        "status": "runtime_cache_bootstrap_mutation_not_attempted",
        "applied": False,
        "restored": False,
        "hash_verified": False,
        "restore_status": "runtime_cache_bootstrap_restore_not_attempted",
        "files": [],
        "backup_refs": [],
        "asset_cache_deleted": False,
    }
    if project is None:
        state["status"] = "blocked_by_missing_project_path"
        return state
    targets = [
        Path(str(entry.get("path", "")))
        for entry in _runtime_cache_bootstrap_files(project)
        if entry.get("contains_loadlevel") or entry.get("contains_deferred_loadlevel")
    ]
    if not targets:
        state.update(
            {
                "status": "runtime_cache_bootstrap_mutation_applied",
                "applied": True,
                "restored": True,
                "hash_verified": True,
                "restore_status": "runtime_cache_bootstrap_restore_pass",
            }
        )
        return state
    artifact_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, Any]] = []
    try:
        for path in targets:
            if not path.is_file():
                continue
            raw = path.read_bytes()
            pre_hash = _sha256_bytes(raw)
            backup_path = backup_dir / path.name
            backup_path.write_bytes(raw)
            data = json.loads(raw.decode("utf-8-sig", errors="replace"))
            _json_pointer_delete(data, RUNTIME_DEFAULT_LEVEL_AUTOEXEC_KEY)
            _json_pointer_delete(data, RUNTIME_DEFERRED_LOADLEVEL_KEY)
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            files.append(
                {
                    "path": _path_text(path),
                    "backup_path": _path_text(backup_path),
                    "pre_hash": pre_hash,
                    "mutated_hash": _sha256_bytes(path.read_bytes()),
                    "contains_loadlevel_after_mutation": "LoadLevel" in path.read_text(encoding="utf-8-sig", errors="replace"),
                }
            )
        state.update(
            {
                "status": "runtime_cache_bootstrap_mutation_applied",
                "applied": True,
                "files": files,
                "backup_refs": [_path_text(item["backup_path"]) for item in files],
            }
        )
    except Exception as exc:
        state["applied"] = bool(files)
        _restore_runtime_cache_bootstrap_neutralization(state)
        state["status"] = "blocked_by_cache_bootstrap_mutation_not_safely_scoped"
        state["error"] = str(exc)
    return state


def _restore_runtime_cache_bootstrap_neutralization(state: Dict[str, Any]) -> None:
    if not state or not state.get("applied"):
        return
    restored = True
    for item in state.get("files", []):
        if not isinstance(item, Mapping):
            continue
        path = Path(str(item.get("path", "")))
        backup_path = Path(str(item.get("backup_path", "")))
        if backup_path.is_file():
            path.write_bytes(backup_path.read_bytes())
        post_hash = _sha256_bytes(path.read_bytes()) if path.is_file() else ""
        item["post_restore_hash"] = post_hash
        item["hash_verified"] = bool(post_hash and post_hash == str(item.get("pre_hash", "")))
        restored = restored and bool(item["hash_verified"])
    state["restored"] = restored
    state["hash_verified"] = restored
    state["restore_status"] = "runtime_cache_bootstrap_restore_pass" if restored else "blocked_by_cache_bootstrap_restore_failed"
    state["status"] = state["restore_status"]


def _run_runtime_character_product_load_diagnostic(
    report: Dict[str, Any],
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_character_product_load_source_payload(
            product_evidence=product_evidence,
            engine_root=engine_root,
            project=project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": report.get("runtime_character_product_load_status", ""),
            "runtime_harness_mode": "runtime_character_product_load_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_product_load_claimed": False,
            "runtime_character_product_load_verified": False,
            "runtime_character_instantiation_claimed": False,
            "runtime_character_instantiation_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_character_product_load_source_discovery",
                "runtime_character_product_load_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_product_load_diagnostic_mode",
                "runtime_character_product_load_not_claimed_without_runtime_markers",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "product_load_source_discovery_is_not_runtime_product_load_proof",
                "product_load_proof_is_not_instantiation_proof",
                "product_load_proof_is_not_animation_proof",
            ],
        }
    )
    return _finalize_report(report)


def _run_runtime_procprefab_handler_or_surface_diagnostic(
    report: Dict[str, Any],
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_procprefab_handler_or_surface_payload(
            product_evidence=product_evidence,
            engine_root=engine_root,
            project=project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": report.get("runtime_procprefab_handler_or_surface_status", ""),
            "runtime_harness_mode": "runtime_procprefab_handler_or_surface_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_procprefab_direct_load_claimed": False,
            "runtime_procprefab_direct_load_verified": False,
            "runtime_procprefab_runtime_equivalent_surface_claimed": False,
            "runtime_procprefab_runtime_equivalent_surface_verified": False,
            "runtime_character_product_load_claimed": False,
            "runtime_character_product_load_verified": False,
            "runtime_character_instantiation_claimed": False,
            "runtime_character_instantiation_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_procprefab_handler_surface_source_discovery",
                "runtime_procprefab_direct_load_blocker_preserved",
                "runtime_spawnable_surface_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_handler_surface_diagnostic_mode",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "editor_direct_procprefab_instantiation_is_not_runtime_direct_load_proof",
                "direct_procprefab_asset_id_resolution_is_not_runtime_load_proof",
                "spawnable_surface_discovery_is_not_spawn_instantiation_proof",
            ],
        }
    )
    return _finalize_report(report)


def _runtime_procprefab_handler_or_surface_payload(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    _ = project
    _ = artifact_dir
    _ = timeout_seconds
    source_validated = _runtime_procprefab_handler_source_validated(engine_root)
    procprefab = _runtime_procprefab_product(product_evidence)
    spawnable_candidates = _runtime_procprefab_spawnable_surface_candidates(product_evidence)
    source_refs = _runtime_procprefab_handler_source_refs(engine_root)
    candidate_matrix = _runtime_procprefab_surface_candidate_matrix(
        engine_root=engine_root,
        procprefab=procprefab,
        spawnable_candidates=spawnable_candidates,
    )
    has_runtime_equivalent = bool(spawnable_candidates)
    status = (
        "runtime_procprefab_surface_source_discovery_pass"
        if source_validated
        else "runtime_procprefab_surface_source_discovery_inconclusive"
    )
    direct_status = (
        "runtime_procprefab_direct_load_unsupported_builder_only"
        if source_validated
        else "runtime_procprefab_direct_load_handler_missing"
    )
    surface_blocker = "" if has_runtime_equivalent else "blocked_by_missing_runtime_equivalent_spawnable_surface"
    contract_blocker = "" if has_runtime_equivalent else "blocked_by_missing_runtime_equivalent_spawnable_surface"
    procprefab_asset_type = str(procprefab.get("asset_type_id", "")).strip() or RUNTIME_PROCPREFAB_ASSET_TYPE
    return {
        "runtime_procprefab_handler_or_surface": {
            "status": status,
            "selected": "",
            "direct_load_supported": False,
            "runtime_equivalent_candidates": len(spawnable_candidates),
        },
        "runtime_procprefab_handler_or_surface_status": status,
        "runtime_procprefab_direct_load_status": direct_status,
        "runtime_procprefab_direct_load_product_path": str(procprefab.get("product_path", "")),
        "runtime_procprefab_direct_load_catalog_path": str(procprefab.get("catalog_path", "")),
        "runtime_procprefab_direct_load_asset_id": str(procprefab.get("asset_id", "")),
        "runtime_procprefab_direct_load_asset_type": procprefab_asset_type,
        "runtime_procprefab_direct_load_asset_class": RUNTIME_PROCPREFAB_ASSET_CLASS if source_validated else "",
        "runtime_procprefab_direct_load_handler_status": "runtime_procprefab_direct_load_handler_missing",
        "runtime_procprefab_direct_load_handler_module": RUNTIME_PROCPREFAB_HANDLER_MODULE if source_validated else "",
        "runtime_procprefab_direct_load_handler_source_refs": source_refs,
        "runtime_procprefab_direct_load_supported": False,
        "runtime_procprefab_direct_load_supported_reason": direct_status,
        "runtime_procprefab_direct_load_blocker": "blocked_by_runtime_procprefab_direct_load_unsupported"
        if source_validated
        else "blocked_by_runtime_procprefab_asset_handler_missing",
        "runtime_procprefab_direct_load_claimed": False,
        "runtime_procprefab_direct_load_verified": False,
        "runtime_procprefab_surface_candidate_matrix": candidate_matrix,
        "runtime_procprefab_surface_candidate_matrix_recorded": bool(candidate_matrix),
        "runtime_procprefab_surface_selected": "",
        "runtime_procprefab_surface_selected_reason": "",
        "runtime_procprefab_surface_remaining_blocker": surface_blocker,
        "runtime_procprefab_runtime_equivalent_surface_claimed": False,
        "runtime_procprefab_runtime_equivalent_surface_verified": False,
        "runtime_character_product_load_contract_updated": bool(source_validated),
        "runtime_character_product_load_direct_procprefab_required": False if source_validated else True,
        "runtime_character_product_load_runtime_equivalent_required": bool(source_validated),
        "runtime_character_product_load_runtime_equivalent_surface_kind": "runtime_equivalent_spawnable_or_prefab_surface"
        if source_validated
        else "",
        "runtime_character_product_load_contract_blocker": contract_blocker,
        "runtime_character_product_load_verified": False,
        "runtime_character_product_load_claimed": False,
        "runtime_character_instantiation_claimed": False,
        "runtime_character_instantiation_verified": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _runtime_procprefab_product(product_evidence: Mapping[str, Any]) -> Dict[str, Any]:
    for product in _runtime_character_product_load_products_from_apb(product_evidence):
        if product.get("product_kind") == "procprefab":
            return dict(product)
    return {
        "product_kind": "procprefab",
        "product_path": "",
        "catalog_path": "",
        "asset_id": "",
        "asset_type_id": RUNTIME_PROCPREFAB_ASSET_TYPE,
        "asset_type_name": RUNTIME_PROCPREFAB_ASSET_CLASS,
    }


def _runtime_procprefab_spawnable_surface_candidates(product_evidence: Mapping[str, Any]) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    for product in product_evidence.get("produced_products", []):
        if not isinstance(product, Mapping):
            continue
        product_type = str(product.get("product_type", "")).strip().lower()
        product_path = str(product.get("product_path", product.get("path", ""))).strip().replace("\\", "/")
        if product_type != "spawnable" and not product_path.lower().endswith(".spawnable"):
            continue
        lower_path = product_path.lower()
        if "characters/maxine" not in lower_path and "characters\\maxine" not in lower_path and "maxine" not in lower_path:
            continue
        candidates.append(
            {
                "product_path": product_path,
                "catalog_path": _runtime_character_product_catalog_path(product_path),
                "asset_id": str(product.get("asset_id", product.get("assetId", ""))).strip(),
                "asset_type_id": str(product.get("asset_type_id", product.get("assetTypeId", RUNTIME_SPAWNABLE_ASSET_TYPE))).strip(),
            }
        )
    return candidates


def _runtime_procprefab_surface_candidate_matrix(
    *,
    engine_root: Path | None,
    procprefab: Mapping[str, Any],
    spawnable_candidates: Sequence[Mapping[str, str]],
) -> List[Dict[str, Any]]:
    source_refs = _runtime_procprefab_handler_source_refs(engine_root)
    spawnable_refs = _runtime_procprefab_spawnable_source_refs(engine_root)
    first_spawnable = dict(spawnable_candidates[0]) if spawnable_candidates else {}
    return [
        {
            "id": "runtime_procprefab_direct_assetmanager_load",
            "name": "Direct .procprefab AssetManager load",
            "kind": "runtime_direct_procprefab_assetmanager_load",
            "source_validation": {
                "status": "runtime_procprefab_surface_candidate_source_validated"
                if _runtime_procprefab_handler_source_validated(engine_root)
                else "runtime_procprefab_surface_candidate_rejected_missing_source_validation",
                "summary": (
                    ".procprefab uses AZ::Prefab::ProceduralPrefabAsset and PrefabGroupAssetHandler, "
                    "but that handler is built in PrefabBuilder.Builders/Tools, not in the runtime launcher envelope."
                ),
            },
            "source_refs": source_refs,
            "product_path": str(procprefab.get("product_path", "")),
            "catalog_path": str(procprefab.get("catalog_path", "")),
            "asset_id": str(procprefab.get("asset_id", "")),
            "asset_type": str(procprefab.get("asset_type_id", RUNTIME_PROCPREFAB_ASSET_TYPE)) or RUNTIME_PROCPREFAB_ASSET_TYPE,
            "handler_status": "runtime_procprefab_direct_load_handler_missing",
            "runtime_api": "AZ::Data::AssetManager::GetAsset",
            "attempted": False,
            "result": "runtime_procprefab_direct_load_unsupported_builder_only",
            "blocker": "blocked_by_runtime_procprefab_direct_load_unsupported",
        },
        {
            "id": "runtime_spawnable_asset_load_surface",
            "name": "Runtime spawnable AssetManager load surface",
            "kind": "runtime_spawnable_asset_load",
            "source_validation": {
                "status": "runtime_procprefab_surface_candidate_source_validated"
                if _runtime_spawnable_source_validated(engine_root)
                else "runtime_procprefab_surface_candidate_rejected_missing_source_validation",
                "summary": "AzFramework registers SpawnableSystemComponent and SpawnableAssetHandler as the runtime prefab/entity asset surface.",
            },
            "source_refs": spawnable_refs,
            "product_path": str(first_spawnable.get("product_path", "")),
            "catalog_path": str(first_spawnable.get("catalog_path", "")),
            "asset_id": str(first_spawnable.get("asset_id", "")),
            "asset_type": str(first_spawnable.get("asset_type_id", RUNTIME_SPAWNABLE_ASSET_TYPE)),
            "handler_status": "runtime_spawnable_handler_source_validated"
            if _runtime_spawnable_source_validated(engine_root)
            else "runtime_spawnable_handler_source_inconclusive",
            "runtime_api": "AZ::Data::AssetManager::GetAsset<AzFramework::Spawnable>",
            "attempted": False,
            "result": "runtime_procprefab_surface_candidate_source_validated"
            if spawnable_candidates
            else "blocked_by_missing_runtime_equivalent_spawnable_surface",
            "blocker": "" if spawnable_candidates else "blocked_by_missing_runtime_equivalent_spawnable_surface",
        },
        {
            "id": "runtime_spawnable_instantiation_surface",
            "name": "Runtime SpawnableEntitiesInterface instantiation surface",
            "kind": "runtime_spawnable_instantiation",
            "source_validation": {
                "status": "runtime_procprefab_surface_candidate_source_validated"
                if _runtime_spawnable_source_validated(engine_root)
                else "runtime_procprefab_surface_candidate_rejected_missing_source_validation",
                "summary": "SpawnableEntitiesInterface can create tickets and spawn entities, but this slice does not instantiate or claim spawn proof.",
            },
            "source_refs": spawnable_refs,
            "product_path": str(first_spawnable.get("product_path", "")),
            "catalog_path": str(first_spawnable.get("catalog_path", "")),
            "asset_id": str(first_spawnable.get("asset_id", "")),
            "asset_type": str(first_spawnable.get("asset_type_id", RUNTIME_SPAWNABLE_ASSET_TYPE)),
            "handler_status": "runtime_spawnable_handler_source_validated"
            if _runtime_spawnable_source_validated(engine_root)
            else "runtime_spawnable_handler_source_inconclusive",
            "runtime_api": "AzFramework::SpawnableEntitiesInterface",
            "attempted": False,
            "result": "runtime_procprefab_surface_candidate_rejected_unsafe",
            "blocker": "blocked_by_runtime_spawn_requires_level_context",
        },
        {
            "id": "runtime_procprefab_keep_blocked_without_runtime_surface",
            "name": "Keep product-load proof blocked without a verified runtime-equivalent surface",
            "kind": "typed_blocker",
            "source_validation": {
                "status": "runtime_procprefab_surface_candidate_source_validated",
                "summary": "Preserves the PR #138 .procprefab asset_handler_missing blocker until a runtime surface is resolved and exercised.",
            },
            "source_refs": source_refs + spawnable_refs,
            "attempted": False,
            "result": "blocked_by_missing_runtime_equivalent_spawnable_surface"
            if not spawnable_candidates
            else "runtime_procprefab_surface_candidate_rejected_load_not_attempted",
            "blocker": "blocked_by_missing_runtime_equivalent_spawnable_surface" if not spawnable_candidates else "",
        },
    ]


def _runtime_procprefab_handler_source_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return all(path.is_file() for path in _runtime_procprefab_handler_source_paths(root))


def _runtime_spawnable_source_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return all(path.is_file() for path in _runtime_procprefab_spawnable_source_paths(root))


def _runtime_procprefab_handler_source_paths(root: Path) -> List[Path]:
    return [
        root
        / "Code"
        / "Framework"
        / "AzToolsFramework"
        / "AzToolsFramework"
        / "Prefab"
        / "Procedural"
        / "ProceduralPrefabAsset.h",
        root
        / "Code"
        / "Framework"
        / "AzToolsFramework"
        / "AzToolsFramework"
        / "Prefab"
        / "Procedural"
        / "ProceduralPrefabAsset.cpp",
        root / "Gems" / "Prefab" / "PrefabBuilder" / "CMakeLists.txt",
        root / "Gems" / "Prefab" / "PrefabBuilder" / "PrefabBuilderModule.cpp",
        root / "Gems" / "Prefab" / "PrefabBuilder" / "PrefabGroup" / "ProceduralAssetHandler.cpp",
        root / "Gems" / "Prefab" / "PrefabBuilder" / "PrefabGroup" / "ProceduralAssetHandler.h",
    ]


def _runtime_procprefab_spawnable_source_paths(root: Path) -> List[Path]:
    return [
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "Spawnable.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableAssetHandler.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableAssetHandler.cpp",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableSystemComponent.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableSystemComponent.cpp",
        root
        / "Code"
        / "Framework"
        / "AzFramework"
        / "AzFramework"
        / "Spawnable"
        / "SpawnableEntitiesInterface.h",
        root
        / "Code"
        / "Framework"
        / "AzFramework"
        / "AzFramework"
        / "Spawnable"
        / "SpawnableEntitiesManager.cpp",
    ]


def _runtime_procprefab_handler_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [str(path) for path in _runtime_procprefab_handler_source_paths(root)]


def _runtime_procprefab_spawnable_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [str(path) for path in _runtime_procprefab_spawnable_source_paths(root)]


def _run_runtime_character_spawnable_surface_diagnostic(
    report: Dict[str, Any],
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_character_spawnable_surface_payload(
            product_evidence=product_evidence,
            engine_root=engine_root,
            project=project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": report.get("runtime_character_spawnable_surface_status", ""),
            "runtime_harness_mode": "runtime_character_spawnable_surface_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_spawnable_surface_claimed": False,
            "runtime_character_spawnable_surface_verified": False,
            "runtime_character_product_load_claimed": False,
            "runtime_character_product_load_verified": False,
            "runtime_character_instantiation_claimed": False,
            "runtime_character_instantiation_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_character_spawnable_surface_source_discovery",
                "runtime_character_spawnable_surface_candidate_search_recorded",
                "level_and_defaultlevel_spawnables_do_not_count_as_character_surface",
                "runtime_execution_not_attempted_in_character_spawnable_surface_diagnostic_mode",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "spawnable_surface_discovery_is_not_runtime_load_proof",
                "spawnable_surface_load_is_not_spawn_instantiation_proof",
                "runtime_character_product_load_remains_blocked_until_approved_spawnable_surface_is_verified",
            ],
        }
    )
    return _finalize_report(report)


def _runtime_character_spawnable_surface_payload(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    _ = timeout_seconds
    _ = artifact_dir
    source_validated = _runtime_character_spawnable_surface_source_validated(engine_root)
    source_refs = _runtime_character_spawnable_surface_source_refs(engine_root)
    candidates = _runtime_character_spawnable_surface_candidates(product_evidence=product_evidence, project=project, engine_root=engine_root)
    approved_candidates = [candidate for candidate in candidates if candidate.get("is_approved") is True]
    selected = approved_candidates[0] if approved_candidates else {}
    found = bool(selected)
    status = (
        "runtime_character_spawnable_surface_found"
        if found
        else "runtime_character_spawnable_surface_generation_required"
        if source_validated
        else "runtime_character_spawnable_surface_source_discovery_inconclusive"
    )
    source_validation_status = (
        "runtime_character_spawnable_surface_source_discovery_pass"
        if source_validated
        else "runtime_character_spawnable_surface_source_discovery_inconclusive"
    )
    search_status = (
        "approved_character_runtime_spawnable_surface_found"
        if found
        else "approved_character_runtime_spawnable_surface_missing"
    )
    missing_reason = "" if found else "approved_character_runtime_spawnable_surface_missing"
    generation_required = not found
    generation_blocker = "blocked_by_runtime_character_spawnable_generation_required" if generation_required else ""
    generation_strategy = (
        "source_validate_and_add_reviewed_character_prefab_source_that_processes_through_the_Prefabs_builder"
        if generation_required
        else ""
    )
    return {
        "runtime_character_spawnable_surface": {
            "status": status,
            "selected": str(selected.get("product_path", "")),
            "candidate_count": len(candidates),
            "approved_candidate_count": len(approved_candidates),
        },
        "runtime_character_spawnable_surface_status": status,
        "runtime_character_spawnable_surface_source_validation": source_validation_status,
        "runtime_character_spawnable_surface_source_refs": source_refs,
        "runtime_character_spawnable_surface_search_status": search_status,
        "runtime_character_spawnable_surface_candidates": candidates,
        "runtime_character_spawnable_surface_candidate_matrix_recorded": True,
        "runtime_character_spawnable_surface_selected": str(selected.get("product_path", "")),
        "runtime_character_spawnable_surface_selected_reason": (
            "approved_character_specific_spawnable_surface_found_in_product_evidence"
            if found
            else ""
        ),
        "runtime_character_spawnable_surface_found": found,
        "runtime_character_spawnable_surface_claimed": False,
        "runtime_character_spawnable_surface_verified": False,
        "runtime_character_spawnable_surface_load_status": (
            "runtime_character_spawnable_surface_found_load_not_attempted"
            if found
            else "runtime_character_spawnable_surface_load_not_attempted"
        ),
        "runtime_character_spawnable_surface_load_ready": False,
        "runtime_character_spawnable_surface_load_timeout": False,
        "runtime_character_spawnable_surface_log_errors": [],
        "runtime_character_spawnable_surface_missing_reason": missing_reason,
        "runtime_character_spawnable_surface_generation_required": generation_required,
        "runtime_character_spawnable_surface_generation_strategy": generation_strategy,
        "runtime_character_spawnable_surface_generation_source_changes": [],
        "runtime_character_spawnable_surface_generation_blocker": generation_blocker,
        "runtime_character_spawnable_surface_remaining_blocker": generation_blocker,
        "runtime_character_product_load_contract_updated": True,
        "runtime_character_product_load_direct_procprefab_required": False,
        "runtime_character_product_load_runtime_equivalent_required": True,
        "runtime_character_product_load_runtime_equivalent_surface_kind": "approved_character_spawnable",
        "runtime_character_product_load_contract_blocker": generation_blocker
        or "blocked_by_runtime_character_spawnable_load_not_attempted",
        "runtime_character_product_load_verified": False,
        "runtime_character_product_load_claimed": False,
        "runtime_character_instantiation_claimed": False,
        "runtime_character_instantiation_verified": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _runtime_character_spawnable_surface_candidates(
    *,
    product_evidence: Mapping[str, Any],
    project: Path | None,
    engine_root: Path | None,
) -> List[Dict[str, Any]]:
    raw_candidates: List[Dict[str, Any]] = []
    for product in product_evidence.get("produced_products", []):
        if not isinstance(product, Mapping):
            continue
        product_type = str(product.get("product_type", "")).strip().lower()
        product_path = _runtime_spawnable_candidate_path(product)
        if product_type != "spawnable" and not product_path.lower().endswith(".spawnable"):
            continue
        raw_candidates.append(dict(product, evidence_source=str(product.get("evidence_source", "apb_report")) or "apb_report"))
    raw_candidates.extend(_runtime_character_spawnable_surface_candidates_from_ap_db(project))

    seen: set[tuple[str, str, str]] = set()
    candidates: List[Dict[str, Any]] = []
    for raw in raw_candidates:
        product_path = _runtime_spawnable_candidate_path(raw)
        key = (
            product_path.lower(),
            str(raw.get("source_uuid", raw.get("source_guid", ""))).lower(),
            str(raw.get("source_sub_id", raw.get("sub_id", ""))).lower(),
        )
        if not product_path or key in seen:
            continue
        seen.add(key)
        candidates.append(
            _runtime_character_spawnable_surface_candidate(
                raw,
                index=len(candidates),
                engine_root=engine_root,
            )
        )
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.get("is_approved") is not True,
            candidate.get("is_defaultlevel") is True,
            candidate.get("is_level") is True,
            str(candidate.get("product_path", "")).lower(),
        ),
    )


def _runtime_character_spawnable_surface_candidates_from_ap_db(project: Path | None) -> List[Dict[str, Any]]:
    if project is None:
        return []
    db_path = project / "Cache" / "assetdb.sqlite"
    if not db_path.is_file():
        return []
    query = """
        SELECT
            p.ProductName,
            p.SubID,
            p.AssetType,
            j.JobKey,
            j.BuilderGuid,
            s.SourceName,
            hex(s.SourceGuid) AS SourceGuid
        FROM Products p
        JOIN Jobs j ON j.JobID = p.JobPK
        JOIN Sources s ON s.SourceID = j.SourcePK
        WHERE lower(p.ProductName) LIKE '%.spawnable'
        ORDER BY p.ProductName
    """
    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query).fetchall()
    except sqlite3.Error:
        return []
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        source_uuid = _normalize_guid(str(row["SourceGuid"] or ""))
        product = {
            "product_type": "spawnable",
            "product_path": str(row["ProductName"] or "").replace("\\", "/"),
            "source_path": str(row["SourceName"] or "").replace("\\", "/"),
            "source_uuid": source_uuid.strip("{}"),
            "source_sub_id": str(row["SubID"] or ""),
            "asset_type_id": _normalize_guid(row["AssetType"] or "") or RUNTIME_SPAWNABLE_ASSET_TYPE,
            "builder": str(row["JobKey"] or ""),
            "builder_guid": str(row["BuilderGuid"] or ""),
            "evidence_source": "asset_processor_database",
        }
        candidates.append(product)
    return candidates


def _runtime_character_spawnable_surface_candidate(
    product: Mapping[str, Any],
    *,
    index: int,
    engine_root: Path | None,
) -> Dict[str, Any]:
    product_path = _runtime_spawnable_candidate_path(product)
    catalog_path = str(product.get("catalog_path", "")).strip().replace("\\", "/") or _runtime_character_product_catalog_path(product_path)
    source_path = str(product.get("source_path", product.get("source", ""))).strip().replace("\\", "/")
    lower_product = product_path.lower()
    lower_catalog = catalog_path.lower()
    lower_source = source_path.lower()
    is_defaultlevel = "defaultlevel" in lower_product or "defaultlevel" in lower_catalog or "defaultlevel" in lower_source
    is_level = lower_product.startswith("pc/levels/") or lower_catalog.startswith("levels/") or lower_source.startswith("levels/")
    is_temp = "levels/_maxine_smoke" in lower_product or "levels/_maxine_smoke" in lower_catalog or "levels/_maxine_smoke" in lower_source
    is_character_specific = any(token in lower_product or token in lower_catalog or token in lower_source for token in ("characters/maxine", "characters\\maxine"))
    is_release_surface = "release" in lower_product or "release" in lower_catalog or "release" in lower_source
    is_approved = is_character_specific and is_release_surface and not is_level and not is_defaultlevel and not is_temp
    rejected_reason = ""
    if is_defaultlevel:
        rejected_reason = "runtime_character_spawnable_surface_candidate_rejected_defaultlevel_spawnable"
    elif is_level:
        rejected_reason = "runtime_character_spawnable_surface_candidate_rejected_level_spawnable"
    elif is_temp:
        rejected_reason = "runtime_character_spawnable_surface_candidate_rejected_unsafe"
    elif not is_character_specific:
        rejected_reason = "runtime_character_spawnable_surface_candidate_rejected_not_character_specific"
    elif not is_approved:
        rejected_reason = "runtime_character_spawnable_surface_candidate_rejected_missing_source_validation"

    source_validated = _runtime_character_spawnable_surface_source_validated(engine_root)
    source_uuid = str(product.get("source_uuid", product.get("source_guid", ""))).strip()
    asset_type = _normalize_guid(str(product.get("asset_type_id", product.get("assetTypeId", ""))).strip()) or RUNTIME_SPAWNABLE_ASSET_TYPE
    candidate = {
        "id": f"runtime_character_spawnable_surface_candidate_{index}",
        "name": product_path,
        "kind": "runtime_character_spawnable_surface",
        "product_path": product_path,
        "catalog_path": catalog_path,
        "asset_id": _runtime_product_asset_id(product),
        "asset_type": asset_type,
        "source_uuid": source_uuid,
        "source_path": source_path,
        "builder": str(product.get("builder", product.get("job_key", ""))).strip(),
        "handler_status": "runtime_character_spawnable_asset_handler_source_validated"
        if source_validated
        else "runtime_character_spawnable_asset_handler_source_inconclusive",
        "runtime_api": "AZ::Data::AssetManager::GetAsset<AzFramework::Spawnable>",
        "is_level": is_level,
        "is_defaultlevel": is_defaultlevel,
        "is_character_specific": is_character_specific,
        "is_approved": is_approved,
        "rejected_reason": rejected_reason,
        "source_validation": (
            "runtime_character_spawnable_surface_candidate_source_validated"
            if source_validated and is_approved
            else rejected_reason
            if rejected_reason
            else "runtime_character_spawnable_surface_candidate_rejected_missing_source_validation"
        ),
        "source_refs": _runtime_character_spawnable_surface_source_refs(engine_root),
        "attempted": False,
        "result": "runtime_character_spawnable_surface_found_load_not_attempted"
        if is_approved
        else rejected_reason,
        "blocker": ""
        if is_approved
        else rejected_reason,
        "evidence_source": str(product.get("evidence_source", "")).strip(),
    }
    return candidate


def _runtime_spawnable_candidate_path(product: Mapping[str, Any]) -> str:
    return str(product.get("product_path", product.get("path", product.get("ProductName", "")))).strip().replace("\\", "/")


def _runtime_character_spawnable_surface_source_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return all(path.is_file() for path in _runtime_character_spawnable_surface_source_paths(root))


def _runtime_character_spawnable_surface_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [str(path) for path in _runtime_character_spawnable_surface_source_paths(root)]


def _runtime_character_spawnable_surface_source_paths(root: Path) -> List[Path]:
    return [
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "Spawnable.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableAssetHandler.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableAssetHandler.cpp",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableSystemComponent.cpp",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableEntitiesInterface.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableEntitiesManager.cpp",
        root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Spawnable" / "PrefabProcessor.h",
        root
        / "Code"
        / "Framework"
        / "AzToolsFramework"
        / "AzToolsFramework"
        / "Prefab"
        / "Spawnable"
        / "PrefabInMemorySpawnableConverter.cpp",
        root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Spawnable" / "SpawnableUtils.cpp",
        root / "Gems" / "Prefab" / "PrefabBuilder" / "PrefabBuilderComponent.cpp",
    ]


def _run_runtime_character_spawn_instantiation_diagnostic(
    report: Dict[str, Any],
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_character_spawn_instantiation_source_payload(
            product_evidence=product_evidence,
            engine_root=engine_root,
            project=project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": report.get("runtime_character_spawn_instantiation_status", ""),
            "runtime_harness_mode": "runtime_character_spawn_instantiation_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_spawn_instantiation_probe_enabled": False,
            "runtime_character_spawn_instantiation_probe_shipping_behavior": False,
            "runtime_character_spawn_instantiation_claimed": False,
            "runtime_character_spawn_instantiation_verified": False,
            "runtime_character_instantiation_claimed": False,
            "runtime_character_instantiation_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_character_spawn_source_discovery",
                "runtime_character_spawn_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_character_spawn_instantiation_diagnostic_mode",
                "runtime_character_spawn_instantiation_not_claimed_without_runtime_execution",
                "runtime_character_animation_not_claimed",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "spawn_api_source_discovery_is_not_spawn_instantiation_proof",
                "product_load_proof_is_not_spawn_instantiation_proof",
                "spawn_instantiation_proof_is_not_animation_proof",
            ],
        }
    )
    return _finalize_report(report)


def _runtime_character_spawn_instantiation_source_payload(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    source_validated = _runtime_character_spawn_instantiation_source_validated(engine_root)
    source_refs = _runtime_character_spawn_instantiation_source_refs(engine_root)
    context_refs = _runtime_character_spawn_context_source_refs(engine_root)
    approved = _runtime_character_spawn_instantiation_approved_spawnable(
        product_evidence=product_evidence,
        project=project,
        engine_root=engine_root,
    )
    selected_product_path = str(approved.get("product_path", ""))
    selected_catalog_path = str(approved.get("catalog_path", ""))
    selected_asset_id = str(approved.get("asset_id", ""))
    selected_asset_type = str(approved.get("asset_type", RUNTIME_SPAWNABLE_ASSET_TYPE)) if approved else ""
    candidate = _runtime_character_spawn_instantiation_selected_candidate(
        source_validated=source_validated,
        source_refs=source_refs,
        context_refs=context_refs,
        approved=approved,
        timeout_seconds=timeout_seconds,
        attempted=False,
    )
    blocker = ""
    if not source_validated:
        blocker = "blocked_by_runtime_character_spawn_source_validation"
    elif not approved:
        blocker = "blocked_by_missing_runtime_equivalent_spawnable_surface"
    status = "runtime_character_spawn_source_discovery_pass" if not blocker else "runtime_character_spawn_instantiation_blocked"
    return {
        "runtime_character_spawn_instantiation": {
            "status": status,
            "selected": RUNTIME_CHARACTER_SPAWN_INSTANTIATION_SELECTED if not blocker else "",
            "attempted": False,
        },
        "runtime_character_spawn_instantiation_status": status,
        "runtime_character_spawn_instantiation_claimed": False,
        "runtime_character_spawn_instantiation_verified": False,
        "runtime_character_spawn_instantiation_source_validation": (
            "runtime_character_spawn_source_discovery_pass"
            if source_validated
            else "runtime_character_spawn_source_discovery_inconclusive"
        ),
        "runtime_character_spawn_instantiation_source_refs": source_refs,
        "runtime_character_spawn_instantiation_probe_enabled": False,
        "runtime_character_spawn_instantiation_probe_shipping_behavior": False,
        "runtime_character_spawn_instantiation_candidate_matrix": _runtime_character_spawn_instantiation_candidate_matrix(
            source_validated=source_validated,
            source_refs=source_refs,
            context_refs=context_refs,
            approved=approved,
            timeout_seconds=timeout_seconds,
        ),
        "runtime_character_spawn_instantiation_candidate_matrix_recorded": True,
        "runtime_character_spawn_instantiation_candidate_id": candidate["id"],
        "runtime_character_spawn_instantiation_candidate_name": candidate["name"],
        "runtime_character_spawn_instantiation_candidate_kind": candidate["kind"],
        "runtime_character_spawn_instantiation_candidate_source_validation": candidate["source_validation"],
        "runtime_character_spawn_instantiation_candidate_source_refs": candidate["source_refs"],
        "runtime_character_spawn_instantiation_candidate_attempted": False,
        "runtime_character_spawn_instantiation_candidate_result": candidate["result"],
        "runtime_character_spawn_instantiation_candidate_blocker": blocker,
        "runtime_character_spawn_instantiation_selected_strategy": "" if blocker else RUNTIME_CHARACTER_SPAWN_INSTANTIATION_SELECTED,
        "runtime_character_spawn_instantiation_selected_reason": (
            "source_validated_spawnable_entities_interface_spawn_all_entities_no_level_fixture"
            if not blocker
            else ""
        ),
        "runtime_character_spawn_instantiation_api": "AzFramework::SpawnableEntitiesInterface::SpawnAllEntities",
        "runtime_character_spawn_instantiation_api_argument_shape": _runtime_character_spawn_instantiation_argument_shape(),
        "runtime_character_spawn_instantiation_context_status": (
            "runtime_character_spawn_context_source_validated"
            if source_validated
            else "runtime_character_spawn_context_source_inconclusive"
        ),
        "runtime_character_spawn_instantiation_context_id": "",
        "runtime_character_spawn_instantiation_context_source_refs": context_refs,
        "runtime_character_spawn_instantiation_spawnable_product_path": selected_product_path,
        "runtime_character_spawn_instantiation_spawnable_catalog_path": selected_catalog_path,
        "runtime_character_spawn_instantiation_spawnable_asset_id": selected_asset_id,
        "runtime_character_spawn_instantiation_spawnable_asset_type": selected_asset_type,
        "runtime_character_spawn_instantiation_spawnable_loaded_ready": False,
        "runtime_character_spawn_instantiation_spawn_request_issued": False,
        "runtime_character_spawn_instantiation_spawn_ticket": "",
        "runtime_character_spawn_instantiation_spawn_completion_observed": False,
        "runtime_character_spawn_instantiation_spawn_result": "",
        "runtime_character_spawn_instantiation_spawned_entity_count": 0,
        "runtime_character_spawn_instantiation_spawned_entity_ids": [],
        "runtime_character_spawn_instantiation_spawned_entity_names": [],
        "runtime_character_spawn_instantiation_spawned_entity_component_inventory": [],
        "runtime_character_spawn_instantiation_root_entity_count": 0,
        "runtime_character_spawn_instantiation_container_entity": "",
        "runtime_character_spawn_instantiation_timeout": False,
        "runtime_character_spawn_instantiation_timeout_ticks": _runtime_character_product_load_timeout_ticks(timeout_seconds),
        "runtime_character_spawn_instantiation_log_errors": [],
        "runtime_character_spawn_instantiation_selected_surface_log_scan": {
            "status": "runtime_execution_not_attempted",
            "matches": [],
        },
        "runtime_character_spawn_instantiation_cleanup_attempted": False,
        "runtime_character_spawn_instantiation_cleanup_status": "runtime_character_spawn_instantiation_cleanup_not_attempted",
        "runtime_character_spawn_instantiation_cleanup_source_refs": source_refs,
        "runtime_character_spawn_instantiation_is_animation_proof": False,
        "runtime_character_spawn_instantiation_remaining_blocker": blocker,
    }


def _runtime_character_spawn_instantiation_approved_spawnable(
    *,
    product_evidence: Mapping[str, Any],
    project: Path | None,
    engine_root: Path | None,
) -> Dict[str, Any]:
    if project is None:
        return {}
    candidates = _runtime_character_spawnable_surface_candidates(
        product_evidence=product_evidence,
        project=project,
        engine_root=engine_root,
    )
    return dict(next((candidate for candidate in candidates if candidate.get("is_approved") is True), {}))


def _runtime_character_spawn_instantiation_argument_shape() -> Dict[str, str]:
    return {
        "asset_resolution": "AZ::Data::AssetCatalogRequestBus::GetAssetIdByPath(<approved spawnable catalog path>)",
        "asset_load": "AZ::Data::AssetManager::GetAsset<AzFramework::Spawnable>(AssetId, AssetLoadBehavior::Default)",
        "ticket": "AzFramework::EntitySpawnTicket(AZ::Data::Asset<AzFramework::Spawnable>)",
        "spawn_request": "AzFramework::SpawnableEntitiesInterface::Get()->SpawnAllEntities(ticket, SpawnAllEntitiesOptionalArgs)",
        "completion": "SpawnAllEntitiesOptionalArgs.m_completionCallback(ticketId, SpawnableConstEntityContainerView)",
        "cleanup": "AzFramework::SpawnableEntitiesInterface::Get()->DespawnAllEntities(ticket, DespawnAllEntitiesOptionalArgs)",
    }


def _runtime_character_spawn_instantiation_selected_candidate(
    *,
    source_validated: bool,
    source_refs: Sequence[str],
    context_refs: Sequence[str],
    approved: Mapping[str, Any],
    timeout_seconds: int,
    attempted: bool,
) -> Dict[str, Any]:
    has_surface = bool(approved)
    result = (
        "runtime_character_spawn_candidate_source_validated"
        if source_validated and has_surface and not attempted
        else "runtime_character_spawn_candidate_rejected_missing_source_validation"
        if not source_validated
        else "blocked_by_missing_runtime_equivalent_spawnable_surface"
        if not has_surface
        else "runtime_character_spawn_candidate_attempted_pass"
    )
    return {
        "id": RUNTIME_CHARACTER_SPAWN_INSTANTIATION_SELECTED,
        "name": "Spawn approved character spawnable through SpawnableEntitiesInterface",
        "kind": "runtime_spawnable_entities_interface_spawn_all_entities",
        "source_validation": {
            "status": "runtime_character_spawn_candidate_source_validated"
            if source_validated and has_surface
            else "runtime_character_spawn_candidate_rejected_missing_source_validation",
            "summary": (
                "EntitySpawnTicket is constructed from the loaded AzFramework::Spawnable asset and "
                "SpawnableEntitiesInterface::SpawnAllEntities issues the runtime spawn request. "
                "The completion callback returns a SpawnableConstEntityContainerView for positive entity evidence."
            ),
        },
        "source_refs": list(source_refs) + list(context_refs),
        "product_path": str(approved.get("product_path", "")),
        "catalog_path": str(approved.get("catalog_path", "")),
        "asset_id": str(approved.get("asset_id", "")),
        "asset_type": str(approved.get("asset_type", RUNTIME_SPAWNABLE_ASSET_TYPE)) if approved else "",
        "runtime_api": "AzFramework::SpawnableEntitiesInterface::SpawnAllEntities",
        "argument_shape": _runtime_character_spawn_instantiation_argument_shape(),
        "loads_level": False,
        "uses_defaultlevel": False,
        "uses_production_level": False,
        "gate_env": list(RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV)
        + list(RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV),
        "timeout_seconds": int(timeout_seconds),
        "attempted": bool(attempted),
        "result": result,
        "blocker": "" if source_validated and has_surface else result,
    }


def _runtime_character_spawn_instantiation_candidate_matrix(
    *,
    source_validated: bool,
    source_refs: Sequence[str],
    context_refs: Sequence[str],
    approved: Mapping[str, Any],
    timeout_seconds: int,
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "runtime_character_spawn_source_api_discovery",
            "name": "Read-only SpawnableEntitiesInterface source discovery",
            "kind": "read_only_source_discovery",
            "source_validation": {
                "status": "runtime_character_spawn_candidate_source_validated"
                if source_validated
                else "runtime_character_spawn_candidate_rejected_missing_source_validation",
                "summary": "Records source refs for EntitySpawnTicket, SpawnAllEntities, completion callbacks, GameEntityContext insertion, and cleanup.",
            },
            "source_refs": list(source_refs) + list(context_refs),
            "attempted": False,
            "result": "runtime_character_spawn_source_discovery_pass"
            if source_validated
            else "runtime_character_spawn_source_discovery_inconclusive",
            "blocker": "" if source_validated else "blocked_by_runtime_character_spawn_source_validation",
        },
        _runtime_character_spawn_instantiation_selected_candidate(
            source_validated=source_validated,
            source_refs=source_refs,
            context_refs=context_refs,
            approved=approved,
            timeout_seconds=timeout_seconds,
            attempted=False,
        ),
        {
            "id": "runtime_character_spawn_temp_level_context",
            "name": "Temp/sandbox level context spawn fallback",
            "kind": "runtime_temp_level_context_spawn",
            "source_validation": {
                "status": "runtime_character_spawn_candidate_rejected_unsafe",
                "summary": "A temp level fallback remains out of scope while the no-level fixture context can be source-validated.",
            },
            "source_refs": list(context_refs),
            "attempted": False,
            "result": "runtime_character_spawn_candidate_rejected_unsafe",
            "blocker": "blocked_by_runtime_character_spawn_requires_temp_level_not_safely_scoped",
        },
        {
            "id": "runtime_character_spawn_keep_blocked_without_positive_entities",
            "name": "Keep spawn proof blocked without completion and entity evidence",
            "kind": "typed_blocker",
            "source_validation": {
                "status": "runtime_character_spawn_candidate_source_validated"
                if source_validated
                else "runtime_character_spawn_candidate_rejected_missing_source_validation",
                "summary": "Product-load or surface proof cannot be converted into spawn proof without request, completion, and positive entity evidence.",
            },
            "source_refs": list(source_refs),
            "attempted": False,
            "result": "blocked_by_runtime_character_spawn_no_entities",
            "blocker": "blocked_by_runtime_character_spawn_no_entities",
        },
    ]


def _runtime_character_spawn_instantiation_source_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return all(path.is_file() for path in _runtime_character_spawn_instantiation_source_paths(root))


def _runtime_character_spawn_instantiation_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [str(path) for path in _runtime_character_spawn_instantiation_source_paths(root)]


def _runtime_character_spawn_instantiation_source_paths(root: Path) -> List[Path]:
    return [
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "Spawnable.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableEntitiesInterface.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableEntitiesInterface.cpp",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableEntitiesManager.cpp",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableSystemComponent.cpp",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "Script" / "SpawnableScriptMediator.cpp",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Entity" / "GameEntityContextBus.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Entity" / "GameEntityContextComponent.cpp",
    ]


def _runtime_character_spawn_context_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [
        str(root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Entity" / "GameEntityContextBus.h"),
        str(root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Entity" / "GameEntityContextComponent.cpp"),
        str(root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableEntitiesManager.cpp"),
    ]


def _run_runtime_character_animation_playback_surface_diagnostic(
    report: Dict[str, Any],
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_character_animation_playback_surface_source_payload(
            product_evidence=product_evidence,
            engine_root=engine_root,
            project=project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": report.get("runtime_character_animation_playback_surface_status", ""),
            "runtime_harness_mode": "runtime_character_animation_playback_surface_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_character_animation_source_discovery",
                "runtime_character_animation_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_character_animation_playback_surface_diagnostic_mode",
                "runtime_character_animation_not_claimed",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "animation_api_source_discovery_is_not_animation_playback_proof",
                "spawn_instantiation_proof_is_not_animation_playback_proof",
                "runtime_character_animation_playback_requires_bounded_spawn_inventory",
            ],
        }
    )
    return _finalize_report(report)


def _runtime_character_animation_playback_surface_source_payload(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    del artifact_dir
    source_validation = _runtime_character_animation_source_validation(engine_root)
    source_refs = _runtime_character_animation_source_refs(engine_root)
    source_validated = source_validation.get("status") == "runtime_character_animation_source_validation_pass"
    approved = _runtime_character_spawn_instantiation_approved_spawnable(
        product_evidence=product_evidence,
        project=project,
        engine_root=engine_root,
    )
    blocker = ""
    if not source_validated:
        blocker = "blocked_by_runtime_animation_source_validation"
    elif not approved:
        blocker = "blocked_by_missing_runtime_equivalent_spawnable_surface"
    else:
        blocker = "blocked_by_runtime_animation_playback_requires_bounded_spawn_fixture"
    status = (
        "runtime_character_animation_playback_surface_source_discovery_pass"
        if source_validated and approved
        else "runtime_character_animation_playback_surface_blocked"
    )
    return {
        "runtime_character_animation_playback_surface": {
            "status": status,
            "selected": RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_SELECTED if source_validated and approved else "",
            "attempted": False,
        },
        "runtime_character_animation_playback_surface_status": status,
        "runtime_character_animation_playback_surface_diagnostic_attempted": True,
        "runtime_character_animation_playback_surface_diagnostic_completed": True,
        "runtime_character_animation_playback_surface_found": False,
        "runtime_character_animation_playback_surface_verified": False,
        "runtime_character_animation_playback_surface_blocker": blocker,
        "runtime_character_animation_playback_candidate_matrix": _runtime_character_animation_candidate_matrix(
            source_validated=source_validated,
            component_inventory=[],
            surface_found=False,
            blocker=blocker,
            playback_attempted=False,
        ),
        "runtime_character_animation_source_validation": source_validation,
        "runtime_character_animation_source_validation_status": source_validation.get("status", ""),
        "runtime_character_animation_source_validation_verified": source_validated,
        "runtime_character_animation_source_refs": source_refs,
        "runtime_character_animation_component_type_map": _runtime_character_animation_component_type_map(),
        "runtime_character_animation_asset_type_map": _runtime_character_animation_asset_type_map(),
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
        "runtime_character_animation_playback_selected_api": "",
        "runtime_character_animation_playback_selected_assets": [],
        "runtime_character_animation_playback_started": False,
        "runtime_character_animation_playback_observed": False,
        "runtime_character_animation_playback_time_before": None,
        "runtime_character_animation_playback_time_after": None,
        "runtime_character_animation_playback_tick_count": 0,
        "runtime_character_animation_playback_tick_duration_seconds": 0,
        "runtime_character_animation_playback_cleanup_complete": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_animation_is_full_character_proof": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _runtime_character_animation_playback_surface_execution_payload(
    *,
    product_evidence: Mapping[str, Any],
    command: Mapping[str, Any],
    project: Path | None,
    actual_level_loads: Sequence[str],
    launch_hygiene: Mapping[str, Any],
    product_load: Mapping[str, Any],
    spawn_instantiation: Mapping[str, Any],
    exit_code: int | None,
    marker_observed: bool,
) -> Dict[str, Any]:
    source_payload = _runtime_character_animation_playback_surface_source_payload(
        product_evidence=product_evidence,
        engine_root=_runtime_engine_root_from_command(command),
        project=project,
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        artifact_dir=DEFAULT_ARTIFACT_ROOT,
    )
    inventory = _runtime_character_animation_component_inventory(
        spawn_instantiation.get("runtime_character_spawn_instantiation_spawned_entity_component_inventory", [])
    )
    actor_found = any(
        component.get("role") == "emotionfx_actor"
        for entity in inventory
        for component in entity.get("components", [])
        if isinstance(component, Mapping)
    )
    anim_graph_found = any(
        component.get("role") == "emotionfx_anim_graph"
        for entity in inventory
        for component in entity.get("components", [])
        if isinstance(component, Mapping)
    )
    simple_motion_found = any(
        component.get("role") == "emotionfx_simple_motion"
        for entity in inventory
        for component in entity.get("components", [])
        if isinstance(component, Mapping)
    )
    source_validated = (
        source_payload.get("runtime_character_animation_source_validation", {}).get("status")
        == "runtime_character_animation_source_validation_pass"
    )
    product_prerequisite = product_load.get("runtime_character_product_load_verified") is True
    spawn_prerequisite = spawn_instantiation.get("runtime_character_spawn_instantiation_verified") is True
    launch_pass = str(launch_hygiene.get("runtime_launch_hygiene_status", "")).strip() == "runtime_launch_hygiene_pass"
    cleanup_complete = str(
        spawn_instantiation.get("runtime_character_spawn_instantiation_cleanup_status", "")
    ).strip() in {
        "runtime_character_spawn_instantiation_cleanup_complete",
        "runtime_character_spawn_instantiation_cleanup_not_required",
    }
    defaultlevel = bool(launch_hygiene.get("runtime_default_level_autoload_detected"))
    production_level = bool(actual_level_loads)
    surface_found = bool(
        source_validated
        and product_prerequisite
        and spawn_prerequisite
        and actor_found
        and (anim_graph_found or simple_motion_found)
    )
    playback_attempted = False
    playback_request_issued = False
    playback_started = False
    playback_observed = False
    blocker = ""
    if not source_validated:
        blocker = "blocked_by_runtime_animation_source_validation"
    elif not product_prerequisite:
        blocker = "blocked_by_runtime_animation_product_load_prerequisite"
    elif not spawn_prerequisite:
        blocker = "blocked_by_runtime_animation_spawn_prerequisite"
    elif defaultlevel:
        blocker = "blocked_by_default_level_autoload"
    elif production_level:
        blocker = "blocked_by_production_level_load"
    elif not actor_found or not (anim_graph_found or simple_motion_found):
        blocker = RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_MISSING_BLOCKER
    else:
        blocker = "blocked_by_runtime_animation_playback_probe_requires_playback_execution_api"
    status = (
        "runtime_character_animation_playback_verified"
        if playback_observed
        else "runtime_character_animation_playback_surface_found_playback_not_verified"
        if surface_found
        else "runtime_character_animation_playback_surface_blocked_missing_runtime_component_surface"
        if blocker == RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_MISSING_BLOCKER
        else "runtime_character_animation_playback_surface_blocked"
    )
    selected_assets = [
        {
            "product_kind": product.get("product_kind", ""),
            "product_path": product.get("product_path", ""),
            "catalog_path": product.get("catalog_path", ""),
            "asset_id": product.get("asset_id", ""),
        }
        for product in product_load.get("runtime_character_product_load_products", [])
        if isinstance(product, Mapping)
        and str(product.get("product_kind", "")) in {"actor", "motion", "motionset", "animgraph"}
    ]
    source_payload.update(
        {
            "runtime_character_animation_playback_surface": {
                "status": status,
                "selected": RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_SELECTED,
                "attempted": True,
                "surface_found": surface_found,
                "blocker": blocker,
            },
            "runtime_character_animation_playback_surface_status": status,
            "runtime_character_animation_playback_surface_diagnostic_attempted": True,
            "runtime_character_animation_playback_surface_diagnostic_completed": True,
            "runtime_character_animation_playback_surface_found": surface_found,
            "runtime_character_animation_playback_surface_verified": False,
            "runtime_character_animation_playback_surface_blocker": blocker,
            "runtime_character_animation_playback_candidate_matrix": _runtime_character_animation_candidate_matrix(
                source_validated=source_validated,
                component_inventory=inventory,
                surface_found=surface_found,
                blocker=blocker,
                playback_attempted=playback_attempted,
            ),
            "runtime_character_animation_spawn_prerequisite_verified": spawn_prerequisite,
            "runtime_character_animation_product_load_prerequisite_verified": product_prerequisite,
            "runtime_character_animation_component_inventory": inventory,
            "runtime_character_animation_actor_component_found": actor_found,
            "runtime_character_animation_anim_graph_component_found": anim_graph_found,
            "runtime_character_animation_simple_motion_component_found": simple_motion_found,
            "runtime_character_animation_actor_instance_found": False,
            "runtime_character_animation_motion_set_found": False,
            "runtime_character_animation_anim_graph_instance_found": False,
            "runtime_character_animation_playback_attempted": playback_attempted,
            "runtime_character_animation_playback_request_issued": playback_request_issued,
            "runtime_character_animation_playback_selected_api": "",
            "runtime_character_animation_playback_selected_assets": selected_assets,
            "runtime_character_animation_playback_started": playback_started,
            "runtime_character_animation_playback_observed": playback_observed,
            "runtime_character_animation_playback_time_before": None,
            "runtime_character_animation_playback_time_after": None,
            "runtime_character_animation_playback_tick_count": 0,
            "runtime_character_animation_playback_tick_duration_seconds": 0,
            "runtime_character_animation_playback_cleanup_complete": cleanup_complete and exit_code == 0 and marker_observed,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_animation_is_full_character_proof": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    )
    return source_payload


def _runtime_character_animation_source_validation_passed(report: Mapping[str, Any]) -> bool:
    source_validation = report.get("runtime_character_animation_source_validation")
    if not isinstance(source_validation, Mapping):
        return False
    if str(source_validation.get("status", "")).strip() != "runtime_character_animation_source_validation_pass":
        return False
    if report.get("runtime_character_animation_source_validation_verified") is False:
        return False
    if str(report.get("runtime_character_animation_playback_surface_blocker", "")).strip() == (
        "blocked_by_runtime_animation_source_validation"
    ):
        return False
    files = source_validation.get("files", [])
    if not isinstance(files, Sequence) or isinstance(files, (str, bytes)) or not files:
        return False
    if any(not isinstance(item, Mapping) or item.get("status") != "pass" for item in files):
        return False
    if source_validation.get("missing"):
        return False
    source_refs = report.get("runtime_character_animation_source_refs", [])
    if (
        not isinstance(source_refs, Sequence)
        or isinstance(source_refs, (str, bytes))
        or len(source_refs) < len(_runtime_character_animation_source_specs(Path("<engine-root>")))
    ):
        return False
    surfaces = source_validation.get("runtime_component_surfaces", {})
    if not isinstance(surfaces, Mapping):
        return False
    required_surface_keys = {
        "actor_component_type_id",
        "anim_graph_component_type_id",
        "simple_motion_component_type_id",
        "actor_request_bus",
        "anim_graph_request_bus",
        "simple_motion_request_bus",
    }
    return all(str(surfaces.get(key, "")).strip() for key in required_surface_keys)


def _runtime_character_animation_playback_surface_fixture_passed(report: Mapping[str, Any]) -> bool:
    if report.get("runtime_character_animation_playback_surface_diagnostic_attempted") is not True:
        return False
    if report.get("runtime_character_animation_playback_surface_diagnostic_completed") is not True:
        return False
    if not _runtime_character_animation_source_validation_passed(report):
        return False

    blocker = str(report.get("runtime_character_animation_playback_surface_blocker", "")).strip()
    missing_surface_blocker = blocker == RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_MISSING_BLOCKER
    if missing_surface_blocker:
        return (
            report.get("runtime_character_animation_product_load_prerequisite_verified") is True
            and report.get("runtime_character_animation_spawn_prerequisite_verified") is True
            and bool(report.get("runtime_character_animation_component_inventory", []))
            and report.get("runtime_character_animation_playback_surface_found") is False
            and report.get("runtime_character_animation_playback_surface_verified") is False
            and not (
                report.get("runtime_character_animation_actor_component_found") is True
                and (
                    report.get("runtime_character_animation_anim_graph_component_found") is True
                    or report.get("runtime_character_animation_simple_motion_component_found") is True
                )
            )
            and report.get("runtime_character_animation_claimed") is False
            and report.get("runtime_character_animation_verified") is False
            and report.get("runtime_character_proof_claimed") is False
            and report.get("runtime_character_proof_verified") is False
        )

    if report.get("runtime_character_animation_verified") is True:
        return (
            report.get("runtime_character_animation_playback_surface_found") is True
            and report.get("runtime_character_animation_playback_surface_verified") is True
            and report.get("runtime_character_animation_playback_attempted") is True
            and report.get("runtime_character_animation_playback_request_issued") is True
            and report.get("runtime_character_animation_playback_started") is True
            and report.get("runtime_character_animation_playback_observed") is True
            and _int_or_zero(report.get("runtime_character_animation_playback_tick_count", 0)) > 0
            and report.get("runtime_character_animation_playback_cleanup_complete") is True
            and report.get("runtime_character_proof_claimed") is False
            and report.get("runtime_character_proof_verified") is False
        )

    return False


def _run_runtime_character_animation_component_wiring_surface_diagnostic(
    report: Dict[str, Any],
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_character_animation_component_wiring_surface_source_payload(
            product_evidence=product_evidence,
            engine_root=engine_root,
            project=project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": report.get("runtime_character_animation_component_wiring_surface_status", ""),
            "runtime_harness_mode": "runtime_character_animation_component_wiring_surface_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_character_animation_component_wiring_source_discovery",
                "runtime_character_animation_component_wiring_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_character_animation_component_wiring_surface_diagnostic_mode",
                "runtime_character_animation_component_wiring_not_claimed",
                "runtime_character_animation_not_claimed",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "editor_component_api_source_discovery_is_not_prefab_mutation_proof",
                "source_validated_component_wiring_surface_is_not_runtime_playback_proof",
                "hand_authored_unknown_o3de_component_serialization_rejected",
            ],
        }
    )
    return _finalize_report(report)


def _run_runtime_actor_simple_motion_component_wiring_after_apb_diagnostic(
    report: Dict[str, Any],
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_character_animation_component_wiring_surface_source_payload(
            product_evidence=product_evidence,
            engine_root=engine_root,
            project=project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    report.update(
        _runtime_actor_simple_motion_component_wiring_after_apb_payload(
            product_evidence=product_evidence,
            project=project,
            engine_root=engine_root,
            actor_found=False,
            simple_motion_found=False,
            actor_assignment_verified=False,
            motion_assignment_verified=False,
            runtime_wiring_verified=False,
            wiring_blocker="runtime_execution_not_attempted_in_after_apb_diagnostic_mode",
        )
    )
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": "runtime_actor_simple_motion_component_wiring_after_apb_source_discovery",
            "runtime_harness_mode": "runtime_actor_simple_motion_component_wiring_after_apb_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "apb_after_source_prefab_update_candidate_matrix_recorded",
                "runtime_execution_not_attempted_in_after_apb_diagnostic_mode",
                "runtime_component_wiring_not_claimed_without_runtime_execution",
                "runtime_animation_not_claimed",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "apb_product_evidence_is_not_runtime_component_wiring_proof",
                "runtime_typeids_without_asset_assignments_are_not_wiring_proof",
            ],
        }
    )
    return _finalize_report(report)


def _run_approved_motion_product_handler_signal_diagnostic(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    artifact_dir: Path,
) -> Dict[str, Any]:
    del project, artifact_dir
    payload = _approved_motion_product_handler_signal_base_payload(engine_root)
    source_validated = payload.get("approved_motion_product_handler_signal_source_validation_verified") is True
    report.update(payload)
    report.update(
        {
            "status": "pass" if source_validated else "fail",
            "runtime_harness_status": (
                "approved_motion_product_handler_signal_source_discovery"
                if source_validated
                else "blocked_by_approved_motion_product_handler_signal_source_validation"
            ),
            "runtime_harness_mode": "approved_motion_product_handler_unregistered_signal_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_playback_attempted": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "approved_motion_product_handler_signal_source_discovery",
                "runtime_execution_not_attempted_in_motion_handler_signal_diagnostic_mode",
                "runtime_component_wiring_not_claimed_without_live_after_apb_fixture",
                "runtime_animation_not_claimed",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "motion_handler_signal_source_diagnostic_is_not_runtime_wiring_proof",
                "motion_handler_signal_classification_requires_live_after_apb_fixture_evidence",
            ],
        }
    )
    return _finalize_report(report)


def _run_runtime_shutdown_poolallocator_signal_diagnostic(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    artifact_dir: Path,
) -> Dict[str, Any]:
    del project, artifact_dir
    payload = _runtime_shutdown_poolallocator_signal_payload("", engine_root)
    source_validated = payload.get("runtime_shutdown_poolallocator_signal_source_validation_verified") is True
    report.update(payload)
    report.update(
        {
            "status": "pass" if source_validated else "fail",
            "runtime_harness_status": (
                "runtime_shutdown_poolallocator_signal_source_discovery"
                if source_validated
                else "blocked_by_runtime_shutdown_poolallocator_signal_source_validation"
            ),
            "runtime_harness_mode": "runtime_shutdown_poolallocator_assertions_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_playback_attempted": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_shutdown_poolallocator_signal_source_discovery",
                "runtime_execution_not_attempted_in_poolallocator_signal_diagnostic_mode",
                "runtime_component_wiring_not_claimed_without_live_after_apb_fixture",
                "runtime_animation_not_claimed",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "poolallocator_signal_source_diagnostic_is_not_runtime_wiring_proof",
                "poolallocator_signal_is_real_blocker_if_observed_in_selected_runtime_output",
            ],
        }
    )
    return _finalize_report(report)


def _runtime_character_animation_component_wiring_surface_source_payload(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    del artifact_dir
    source_validation = _runtime_character_animation_component_wiring_source_validation(engine_root)
    source_validated = source_validation.get("status") == "runtime_character_animation_component_wiring_source_validation_pass"
    approved = _runtime_character_spawn_instantiation_approved_spawnable(
        product_evidence=product_evidence,
        project=project,
        engine_root=engine_root,
    )
    product_found = bool(approved)
    blocker = (
        RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_BLOCKER
        if source_validated and product_found
        else "blocked_by_runtime_animation_component_wiring_source_validation"
        if not source_validated
        else "blocked_by_missing_runtime_equivalent_spawnable_surface"
    )
    status = (
        "runtime_character_animation_component_wiring_surface_source_discovery_pass"
        if source_validated and product_found
        else "runtime_character_animation_component_wiring_surface_blocked"
    )
    return {
        "runtime_character_animation_component_wiring_surface": {
            "status": status,
            "selected": RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_SELECTED
            if source_validated and product_found
            else "",
            "attempted": False,
        },
        "runtime_character_animation_component_wiring_surface_status": status,
        "runtime_character_animation_component_wiring_surface_diagnostic_attempted": True,
        "runtime_character_animation_component_wiring_surface_diagnostic_completed": True,
        "runtime_character_animation_component_wiring_source_validation": source_validation,
        "runtime_character_animation_component_wiring_source_validation_status": source_validation.get("status", ""),
        "runtime_character_animation_component_wiring_source_validation_verified": source_validated,
        "runtime_character_animation_component_wiring_source_refs": _runtime_character_animation_component_wiring_source_refs(
            engine_root
        ),
        "runtime_character_animation_component_wiring_surface_found": False,
        "runtime_character_animation_component_wiring_surface_verified": False,
        "runtime_character_animation_component_wiring_surface_blocker": blocker,
        "runtime_character_animation_component_wiring_blocker": blocker,
        "runtime_character_animation_component_wiring_candidate_matrix": _runtime_character_animation_component_wiring_candidate_matrix(
            source_validated=source_validated,
            product_found=product_found,
            runtime_inventory=[],
            runtime_actor_found=False,
            runtime_simple_motion_found=False,
            runtime_anim_graph_found=False,
            runtime_surface_found=False,
            runtime_wiring_verified=False,
            blocker=blocker,
        ),
        "runtime_character_animation_component_wiring_selected_strategy": (
            RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_SELECTED
            if source_validated and product_found
            else ""
        ),
        "runtime_character_animation_component_wiring_editor_api": {
            "component_add": "EditorComponentAPIBus.AddComponentsOfType",
            "property_discovery": "EditorComponentAPIBus.BuildComponentPropertyList",
            "property_get": "EditorComponentAPIBus.GetComponentProperty",
            "property_set": "EditorComponentAPIBus.SetComponentProperty",
            "asset_value_shape": "AZ::Data::AssetId / azlmbr.asset.AssetId",
        },
        "runtime_character_animation_component_wiring_prefab_api": {
            "instantiate": "PrefabPublicRequestBus.InstantiatePrefab",
            "create_in_memory": "PrefabPublicRequestBus.CreatePrefabInMemory",
            "create_and_save": "PrefabPublicHandler.CreatePrefabAndSaveToDisk",
            "save": "PrefabPublicRequestBus.SavePrefab",
        },
        "runtime_character_animation_component_wiring_source_prefab_path": RUNTIME_CHARACTER_PREFAB_SOURCE_REPO_REF,
        "runtime_character_animation_component_wiring_source_prefab_modified": False,
        "runtime_character_animation_component_wiring_uses_hand_authored_unknown_serialization": False,
        "runtime_character_animation_component_wiring_actor_component_type_id": EDITOR_EMOTIONFX_ACTOR_COMPONENT_TYPE_ID,
        "runtime_character_animation_component_wiring_simple_motion_component_type_id": EDITOR_EMOTIONFX_SIMPLE_MOTION_COMPONENT_TYPE_ID,
        "runtime_character_animation_component_wiring_anim_graph_component_type_id": EDITOR_EMOTIONFX_ANIM_GRAPH_COMPONENT_TYPE_ID,
        "runtime_character_animation_component_wiring_actor_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_motion_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_motion_set_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_anim_graph_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_runtime_actor_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_runtime_motion_asset_assignment_verified": False,
        "runtime_character_animation_component_wiring_runtime_actor_asset_id": "",
        "runtime_character_animation_component_wiring_runtime_motion_asset_id": "",
        "runtime_character_animation_component_wiring_spawnable_regenerated_or_found": product_found,
        "runtime_character_animation_component_wiring_spawn_prerequisite_verified": False,
        "runtime_character_animation_component_wiring_product_load_prerequisite_verified": False,
        "runtime_character_animation_component_wiring_surface_before_component_inventory": [],
        "runtime_character_animation_component_wiring_surface_before_actor_component_found": False,
        "runtime_character_animation_component_wiring_surface_before_anim_graph_component_found": False,
        "runtime_character_animation_component_wiring_surface_before_simple_motion_component_found": False,
        "runtime_character_animation_component_wiring_surface_before_blocker": "",
        "runtime_character_animation_component_wiring_runtime_component_inventory": [],
        "runtime_character_animation_component_wiring_runtime_actor_component_found": False,
        "runtime_character_animation_component_wiring_runtime_simple_motion_component_found": False,
        "runtime_character_animation_component_wiring_runtime_anim_graph_component_found": False,
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


def _runtime_character_animation_component_wiring_assignment_blocker(
    *,
    actor_found: bool,
    simple_motion_found: bool,
    anim_graph_found: bool,
    actor_asset_assignment_verified: bool,
    motion_asset_assignment_verified: bool,
    anim_graph_asset_assignment_verified: bool,
    motion_set_asset_assignment_verified: bool,
) -> str:
    if not actor_found or not (simple_motion_found or anim_graph_found):
        return ""
    simple_motion_ready = bool(actor_found and simple_motion_found and actor_asset_assignment_verified and motion_asset_assignment_verified)
    anim_graph_ready = bool(
        actor_found
        and anim_graph_found
        and actor_asset_assignment_verified
        and anim_graph_asset_assignment_verified
        and motion_set_asset_assignment_verified
    )
    if simple_motion_ready or anim_graph_ready:
        return ""
    if not actor_asset_assignment_verified:
        return RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ACTOR_ASSET_BLOCKER
    if simple_motion_found and not motion_asset_assignment_verified:
        return RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_MOTION_ASSET_BLOCKER
    if anim_graph_found and not anim_graph_asset_assignment_verified:
        return RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ANIM_GRAPH_ASSET_BLOCKER
    if anim_graph_found and not motion_set_asset_assignment_verified:
        return RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_MOTION_SET_ASSET_BLOCKER
    return RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ASSET_ASSIGNMENT_BLOCKER


def _runtime_asset_id_matches(actual: Any, expected: str) -> bool:
    return str(actual or "").strip().lower() == expected.strip().lower()


def _runtime_character_animation_component_wiring_runtime_assignment_ids(
    inventory: Sequence[Mapping[str, Any]],
) -> Dict[str, str]:
    actor_asset_id = ""
    motion_asset_id = ""
    for entity in inventory:
        if not isinstance(entity, Mapping):
            continue
        has_actor = any(
            isinstance(component, Mapping) and component.get("role") == "emotionfx_actor"
            for component in entity.get("components", [])
        )
        has_simple_motion = any(
            isinstance(component, Mapping) and component.get("role") == "emotionfx_simple_motion"
            for component in entity.get("components", [])
        )
        if has_actor and not actor_asset_id:
            actor_asset_id = str(entity.get("actor_asset_id", "")).strip()
        if has_simple_motion and not motion_asset_id:
            motion_asset_id = str(entity.get("motion_asset_id", "")).strip()
    return {"actor_asset_id": actor_asset_id, "motion_asset_id": motion_asset_id}


def _runtime_actor_simple_motion_component_wiring_after_apb_candidate_matrix(
    *,
    apb_verified: bool,
    approved_spawnable_found: bool,
    product_matrix_complete: bool,
    actor_found: bool,
    simple_motion_found: bool,
    actor_assignment_verified: bool,
    motion_assignment_verified: bool,
    runtime_wiring_verified: bool,
    blocker: str,
) -> List[Dict[str, Any]]:
    runtime_surface_found = bool(actor_found and simple_motion_found)
    return [
        {
            "id": "apb_regenerate_found_approved_spawnable",
            "candidate": "APB regenerate/found approved spawnable from modified approved source prefab",
            "kind": "asset_processor_batch_product_evidence",
            "attempted": True,
            "selected": apb_verified,
            "result": "runtime_actor_simple_motion_after_apb_candidate_apb_verified"
            if apb_verified
            else "runtime_actor_simple_motion_after_apb_candidate_blocked_apb_or_spawnable",
            "blocker": "" if apb_verified else blocker,
        },
        {
            "id": "runtime_spawn_post_mutation_spawnable_inspect_typeids",
            "candidate": "runtime spawn approved post-mutation spawnable and inspect TypeIds",
            "kind": "runtime_spawned_component_inventory",
            "attempted": apb_verified,
            "selected": runtime_surface_found,
            "result": "runtime_actor_simple_motion_after_apb_candidate_typeids_found"
            if runtime_surface_found
            else "runtime_actor_simple_motion_after_apb_candidate_blocked_missing_typeids",
            "blocker": "" if runtime_surface_found else blocker,
        },
        {
            "id": "runtime_actor_simple_motion_typeids_plus_assignments",
            "candidate": "runtime Actor + Simple Motion TypeIds plus runtime asset assignments",
            "kind": "runtime_wiring_verification",
            "attempted": apb_verified and runtime_surface_found,
            "selected": runtime_wiring_verified,
            "result": "runtime_actor_simple_motion_after_apb_candidate_verified_typeids_and_assignments"
            if runtime_wiring_verified
            else "runtime_actor_simple_motion_after_apb_candidate_blocked_asset_assignment_unverified"
            if runtime_surface_found and (not actor_assignment_verified or not motion_assignment_verified)
            else "runtime_actor_simple_motion_after_apb_candidate_blocked_runtime_prerequisite"
            if runtime_surface_found
            else "runtime_actor_simple_motion_after_apb_candidate_blocked_missing_typeids",
            "blocker": "" if runtime_wiring_verified else blocker,
        },
        {
            "id": "runtime_typeids_only",
            "candidate": "runtime TypeIds only",
            "kind": "runtime_component_surface_only",
            "attempted": runtime_surface_found,
            "selected": False,
            "result": "runtime_actor_simple_motion_after_apb_candidate_rejected_typeids_only_insufficient",
            "blocker": "runtime_typeids_without_asset_assignment_are_not_wiring_proof",
        },
        {
            "id": "product_load_only",
            "candidate": "product-load only",
            "kind": "runtime_asset_product_load_only",
            "attempted": product_matrix_complete,
            "selected": False,
            "result": "runtime_actor_simple_motion_after_apb_candidate_rejected_product_load_only_insufficient",
            "blocker": "product_load_is_not_runtime_component_wiring_proof",
        },
        {
            "id": "editor_only_source_template_markers",
            "candidate": "Editor-only source-template ActorAsset/MotionAsset markers",
            "kind": "editor_prefab_source_evidence",
            "attempted": False,
            "selected": False,
            "result": "runtime_actor_simple_motion_after_apb_candidate_rejected_editor_only_insufficient",
            "blocker": "editor_only_source_template_markers_are_not_runtime_wiring_proof",
        },
        {
            "id": "direct_runtime_procprefab_load",
            "candidate": "direct runtime .procprefab load",
            "kind": "runtime_procprefab_direct_load",
            "attempted": False,
            "selected": False,
            "result": "runtime_actor_simple_motion_after_apb_candidate_rejected_builder_only_surface",
            "blocker": "direct_procprefab_runtime_load_unsupported_builder_only",
        },
        {
            "id": "animation_playback",
            "candidate": "animation playback",
            "kind": "runtime_animation_playback",
            "attempted": False,
            "selected": False,
            "result": "runtime_actor_simple_motion_after_apb_candidate_deferred_until_wiring_verified",
            "blocker": "animation_playback_deferred_for_later_bounded_slice",
        },
        {
            "id": "defaultlevel_or_production_level_runtime_proof",
            "candidate": "defaultlevel or production-level runtime proof",
            "kind": "unsafe_level_runtime_context",
            "attempted": False,
            "selected": False,
            "result": "runtime_actor_simple_motion_after_apb_candidate_rejected_unsafe_scope",
            "blocker": "defaultlevel_or_production_level_runtime_evidence_disallowed",
        },
    ]


def _runtime_actor_simple_motion_component_wiring_after_apb_payload(
    *,
    product_evidence: Mapping[str, Any],
    project: Path | None,
    engine_root: Path | None,
    actor_found: bool,
    simple_motion_found: bool,
    actor_assignment_verified: bool,
    motion_assignment_verified: bool,
    runtime_wiring_verified: bool,
    wiring_blocker: str,
) -> Dict[str, Any]:
    approved = _runtime_character_spawn_instantiation_approved_spawnable(
        product_evidence=product_evidence,
        project=project,
        engine_root=engine_root,
    )
    products = _runtime_character_product_load_products_from_apb(
        product_evidence,
        project=project,
        engine_root=engine_root,
    )
    product_matrix_complete = _runtime_character_product_load_required_complete(
        products,
        product_evidence,
        required_products=RUNTIME_CHARACTER_PRODUCT_LOAD_UPDATED_REQUIRED_PRODUCTS,
    )
    approved_found = bool(approved)
    apb_verified = bool(product_matrix_complete and approved_found)
    blocker = ""
    if not apb_verified:
        blocker = (
            "blocked_by_approved_spawnable_not_found_after_source_prefab_update"
            if not approved_found
            else "blocked_by_product_matrix_incomplete_after_source_prefab_update"
        )
    elif not actor_found:
        blocker = "blocked_by_runtime_actor_component_missing_after_spawn"
    elif not simple_motion_found:
        blocker = "blocked_by_runtime_simple_motion_component_missing_after_spawn"
    elif not actor_assignment_verified or not motion_assignment_verified:
        blocker = wiring_blocker or RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ASSET_ASSIGNMENT_BLOCKER
    elif not runtime_wiring_verified:
        blocker = wiring_blocker or "blocked_by_runtime_animation_component_wiring_prerequisite_unverified"

    verified = bool(apb_verified and runtime_wiring_verified and actor_found and simple_motion_found)
    return {
        "apb_after_source_prefab_update_attempted": True,
        "apb_after_source_prefab_update_completed": product_evidence.get("status") != "blocked_by_missing_product_evidence",
        "apb_after_source_prefab_update_verified": apb_verified,
        "apb_after_source_prefab_update_blocker": "" if apb_verified else blocker,
        "approved_spawnable_regenerated_or_found": approved_found,
        "approved_spawnable_asset_id": str(approved.get("asset_id", "")),
        "approved_spawnable_asset_type": str(approved.get("asset_type", RUNTIME_SPAWNABLE_ASSET_TYPE)) if approved else "",
        "approved_spawnable_catalog_path": str(approved.get("catalog_path", "")),
        "approved_spawnable_product_path": str(approved.get("product_path", "")),
        "product_matrix_complete_after_source_prefab_update": product_matrix_complete,
        "runtime_actor_simple_motion_component_wiring_after_apb_attempted": True,
        "runtime_actor_simple_motion_component_wiring_after_apb_completed": True,
        "runtime_actor_simple_motion_component_wiring_after_apb_verified": verified,
        "runtime_actor_simple_motion_component_wiring_after_apb_blocker": "" if verified else blocker,
        "runtime_actor_simple_motion_component_wiring_candidate_matrix": _runtime_actor_simple_motion_component_wiring_after_apb_candidate_matrix(
            apb_verified=apb_verified,
            approved_spawnable_found=approved_found,
            product_matrix_complete=product_matrix_complete,
            actor_found=actor_found,
            simple_motion_found=simple_motion_found,
            actor_assignment_verified=actor_assignment_verified,
            motion_assignment_verified=motion_assignment_verified,
            runtime_wiring_verified=verified,
            blocker=blocker,
        ),
        "runtime_actor_simple_motion_component_wiring_selected_strategy": (
            "apb_post_source_prefab_update_runtime_actor_simple_motion_typeids_and_assignments"
            if verified
            else ""
        ),
    }


def _runtime_character_animation_component_wiring_surface_execution_payload(
    *,
    product_evidence: Mapping[str, Any],
    command: Mapping[str, Any],
    project: Path | None,
    product_load: Mapping[str, Any],
    spawn_instantiation: Mapping[str, Any],
    animation_playback_surface: Mapping[str, Any],
    actor_simple_motion_component_wiring_after_apb: bool = False,
) -> Dict[str, Any]:
    source_payload = _runtime_character_animation_component_wiring_surface_source_payload(
        product_evidence=product_evidence,
        engine_root=_runtime_engine_root_from_command(command),
        project=project,
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        artifact_dir=DEFAULT_ARTIFACT_ROOT,
    )
    inventory = list(animation_playback_surface.get("runtime_character_animation_component_inventory", []))
    actor_found = animation_playback_surface.get("runtime_character_animation_actor_component_found") is True
    simple_motion_found = animation_playback_surface.get("runtime_character_animation_simple_motion_component_found") is True
    anim_graph_found = animation_playback_surface.get("runtime_character_animation_anim_graph_component_found") is True
    runtime_assignment_ids = _runtime_character_animation_component_wiring_runtime_assignment_ids(inventory)
    runtime_actor_asset_id = runtime_assignment_ids["actor_asset_id"]
    runtime_motion_asset_id = runtime_assignment_ids["motion_asset_id"]
    source_validated = (
        source_payload.get("runtime_character_animation_component_wiring_source_validation_status")
        == "runtime_character_animation_component_wiring_source_validation_pass"
    )
    product_prerequisite = product_load.get("runtime_character_product_load_verified") is True
    spawn_prerequisite = spawn_instantiation.get("runtime_character_spawn_instantiation_verified") is True
    runtime_surface_found = bool(actor_found and (simple_motion_found or anim_graph_found))
    surface_blocker = (
        "blocked_by_runtime_animation_component_wiring_source_validation"
        if not source_validated
        else "blocked_by_runtime_animation_component_wiring_product_load_prerequisite"
        if not product_prerequisite
        else "blocked_by_runtime_animation_component_wiring_spawn_prerequisite"
        if not spawn_prerequisite
        else RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_BLOCKER
        if not runtime_surface_found
        else ""
    )
    actor_asset_assignment_verified = (
        animation_playback_surface.get("runtime_character_animation_component_wiring_actor_asset_assignment_verified") is True
        or _runtime_asset_id_matches(runtime_actor_asset_id, RUNTIME_CHARACTER_APPROVED_ACTOR_ASSET_ID)
    )
    motion_asset_assignment_verified = (
        animation_playback_surface.get("runtime_character_animation_component_wiring_motion_asset_assignment_verified") is True
        or _runtime_asset_id_matches(runtime_motion_asset_id, RUNTIME_CHARACTER_APPROVED_MOTION_ASSET_ID)
    )
    anim_graph_asset_assignment_verified = (
        animation_playback_surface.get("runtime_character_animation_component_wiring_anim_graph_asset_assignment_verified") is True
    )
    motion_set_asset_assignment_verified = (
        animation_playback_surface.get("runtime_character_animation_component_wiring_motion_set_asset_assignment_verified") is True
    )
    assignment_blocker = (
        _runtime_character_animation_component_wiring_assignment_blocker(
            actor_found=actor_found,
            simple_motion_found=simple_motion_found,
            anim_graph_found=anim_graph_found,
            actor_asset_assignment_verified=actor_asset_assignment_verified,
            motion_asset_assignment_verified=motion_asset_assignment_verified,
            anim_graph_asset_assignment_verified=anim_graph_asset_assignment_verified,
            motion_set_asset_assignment_verified=motion_set_asset_assignment_verified,
        )
        if not surface_blocker and runtime_surface_found
        else ""
    )
    wiring_blocker = surface_blocker or assignment_blocker
    runtime_wiring_verified = bool(runtime_surface_found and not wiring_blocker)
    status = (
        "runtime_character_animation_component_wiring_surface_verified"
        if not surface_blocker and runtime_surface_found
        else
        "runtime_character_animation_component_wiring_surface_blocked_missing_runtime_components"
        if surface_blocker == RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_BLOCKER
        else "runtime_character_animation_component_wiring_surface_blocked"
    )
    update_payload = {
            "runtime_character_animation_component_wiring_surface": {
                "status": status,
                "selected": RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_SELECTED,
                "attempted": True,
                "surface_found": runtime_surface_found,
                "blocker": surface_blocker,
                "wiring_blocker": wiring_blocker,
            },
            "runtime_character_animation_component_wiring_surface_status": status,
            "runtime_character_animation_component_wiring_surface_diagnostic_attempted": True,
            "runtime_character_animation_component_wiring_surface_diagnostic_completed": True,
            "runtime_character_animation_component_wiring_surface_found": runtime_surface_found,
            "runtime_character_animation_component_wiring_surface_verified": not surface_blocker and runtime_surface_found,
            "runtime_character_animation_component_wiring_surface_blocker": surface_blocker,
            "runtime_character_animation_component_wiring_blocker": wiring_blocker,
            "runtime_character_animation_component_wiring_candidate_matrix": _runtime_character_animation_component_wiring_candidate_matrix(
                source_validated=source_validated,
                product_found=source_payload.get("runtime_character_animation_component_wiring_spawnable_regenerated_or_found")
                is True,
                runtime_inventory=inventory,
                runtime_actor_found=actor_found,
                runtime_simple_motion_found=simple_motion_found,
                runtime_anim_graph_found=anim_graph_found,
                runtime_surface_found=runtime_surface_found,
                runtime_wiring_verified=runtime_wiring_verified,
                blocker=wiring_blocker,
            ),
            "runtime_character_animation_component_wiring_product_load_prerequisite_verified": product_prerequisite,
            "runtime_character_animation_component_wiring_spawn_prerequisite_verified": spawn_prerequisite,
            "runtime_character_animation_component_wiring_surface_before_component_inventory": inventory,
            "runtime_character_animation_component_wiring_surface_before_actor_component_found": actor_found,
            "runtime_character_animation_component_wiring_surface_before_simple_motion_component_found": simple_motion_found,
            "runtime_character_animation_component_wiring_surface_before_anim_graph_component_found": anim_graph_found,
            "runtime_character_animation_component_wiring_surface_before_blocker": animation_playback_surface.get(
                "runtime_character_animation_playback_surface_blocker", ""
            ),
            "runtime_character_animation_component_wiring_runtime_component_inventory": inventory,
            "runtime_character_animation_component_wiring_runtime_actor_component_found": actor_found,
            "runtime_character_animation_component_wiring_runtime_simple_motion_component_found": simple_motion_found,
            "runtime_character_animation_component_wiring_runtime_anim_graph_component_found": anim_graph_found,
            "runtime_character_animation_component_wiring_actor_asset_assignment_verified": actor_asset_assignment_verified,
            "runtime_character_animation_component_wiring_motion_asset_assignment_verified": motion_asset_assignment_verified,
            "runtime_character_animation_component_wiring_motion_set_asset_assignment_verified": motion_set_asset_assignment_verified,
            "runtime_character_animation_component_wiring_anim_graph_asset_assignment_verified": anim_graph_asset_assignment_verified,
            "runtime_character_animation_component_wiring_runtime_actor_asset_assignment_verified": actor_asset_assignment_verified,
            "runtime_character_animation_component_wiring_runtime_motion_asset_assignment_verified": motion_asset_assignment_verified,
            "runtime_character_animation_component_wiring_runtime_actor_asset_id": runtime_actor_asset_id,
            "runtime_character_animation_component_wiring_runtime_motion_asset_id": runtime_motion_asset_id,
            "runtime_motion_assignment_id_readback_verified": motion_asset_assignment_verified,
            "runtime_motion_assignment_load_verified": bool(
                motion_asset_assignment_verified and product_prerequisite
            ),
            "runtime_character_animation_component_wiring_claimed": runtime_wiring_verified,
            "runtime_character_animation_component_wiring_verified": runtime_wiring_verified,
            "runtime_character_animation_playback_attempted": False,
            "runtime_character_animation_playback_started": False,
            "runtime_character_animation_playback_observed": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    if actor_simple_motion_component_wiring_after_apb:
        update_payload.update(
            _runtime_actor_simple_motion_component_wiring_after_apb_payload(
                product_evidence=product_evidence,
                project=project,
                engine_root=_runtime_engine_root_from_command(command),
                actor_found=actor_found,
                simple_motion_found=simple_motion_found,
                actor_assignment_verified=actor_asset_assignment_verified,
                motion_assignment_verified=motion_asset_assignment_verified,
                runtime_wiring_verified=runtime_wiring_verified,
                wiring_blocker=wiring_blocker,
            )
        )
    source_payload.update(update_payload)
    return source_payload


def _runtime_character_animation_component_wiring_source_validation_passed(report: Mapping[str, Any]) -> bool:
    source_validation = report.get("runtime_character_animation_component_wiring_source_validation")
    if not isinstance(source_validation, Mapping):
        return False
    if str(source_validation.get("status", "")).strip() != "runtime_character_animation_component_wiring_source_validation_pass":
        return False
    if report.get("runtime_character_animation_component_wiring_source_validation_verified") is False:
        return False
    if str(report.get("runtime_character_animation_component_wiring_surface_blocker", "")).strip() == (
        "blocked_by_runtime_animation_component_wiring_source_validation"
    ):
        return False
    files = source_validation.get("files", [])
    if not isinstance(files, Sequence) or isinstance(files, (str, bytes)) or not files:
        return False
    if any(not isinstance(item, Mapping) or item.get("status") != "pass" for item in files):
        return False
    if source_validation.get("missing"):
        return False
    source_refs = report.get("runtime_character_animation_component_wiring_source_refs", [])
    if (
        not isinstance(source_refs, Sequence)
        or isinstance(source_refs, (str, bytes))
        or len(source_refs) < len(_runtime_character_animation_component_wiring_source_specs(Path("<engine-root>")))
    ):
        return False
    editor_surfaces = source_validation.get("editor_component_surfaces", {})
    editor_api = source_validation.get("editor_component_api", {})
    prefab_api = source_validation.get("prefab_api", {})
    if not isinstance(editor_surfaces, Mapping) or not isinstance(editor_api, Mapping) or not isinstance(prefab_api, Mapping):
        return False
    required_editor_keys = {
        "actor_component_type_id",
        "simple_motion_component_type_id",
        "anim_graph_component_type_id",
        "actor_asset_property",
        "simple_motion_asset_property",
        "anim_graph_asset_property",
        "motion_set_asset_property",
    }
    required_api_keys = {"AddComponentsOfType", "BuildComponentPropertyList", "GetComponentProperty", "SetComponentProperty"}
    required_prefab_keys = {"CreatePrefabInMemory", "InstantiatePrefab", "SavePrefab"}
    return (
        all(str(editor_surfaces.get(key, "")).strip() for key in required_editor_keys)
        and all(str(editor_api.get(key, "")).strip() for key in required_api_keys)
        and all(str(prefab_api.get(key, "")).strip() for key in required_prefab_keys)
    )


def _runtime_character_animation_component_wiring_surface_fixture_passed(report: Mapping[str, Any]) -> bool:
    if report.get("runtime_character_animation_component_wiring_surface_diagnostic_attempted") is not True:
        return False
    if report.get("runtime_character_animation_component_wiring_surface_diagnostic_completed") is not True:
        return False
    if not _runtime_character_animation_component_wiring_source_validation_passed(report):
        return False
    blocker = str(report.get("runtime_character_animation_component_wiring_surface_blocker", "")).strip()
    if blocker == RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_BLOCKER:
        return (
            report.get("runtime_character_animation_component_wiring_product_load_prerequisite_verified") is True
            and report.get("runtime_character_animation_component_wiring_spawn_prerequisite_verified") is True
            and report.get("runtime_character_animation_component_wiring_spawnable_regenerated_or_found") is True
            and bool(report.get("runtime_character_animation_component_wiring_runtime_component_inventory", []))
            and report.get("runtime_character_animation_component_wiring_runtime_actor_component_found") is False
            and report.get("runtime_character_animation_component_wiring_runtime_simple_motion_component_found") is False
            and report.get("runtime_character_animation_component_wiring_runtime_anim_graph_component_found") is False
            and report.get("runtime_character_animation_component_wiring_claimed") is False
            and report.get("runtime_character_animation_component_wiring_verified") is False
            and report.get("runtime_character_animation_claimed") is False
            and report.get("runtime_character_animation_verified") is False
            and report.get("runtime_character_proof_claimed") is False
            and report.get("runtime_character_proof_verified") is False
        )
    assignment_blocked = str(report.get("runtime_character_animation_component_wiring_blocker", "")).strip() in {
        RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ASSET_ASSIGNMENT_BLOCKER,
        RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ACTOR_ASSET_BLOCKER,
        RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_MOTION_ASSET_BLOCKER,
        RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_ANIM_GRAPH_ASSET_BLOCKER,
        RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_MOTION_SET_ASSET_BLOCKER,
    }
    if assignment_blocked:
        return (
            report.get("runtime_character_animation_component_wiring_product_load_prerequisite_verified") is True
            and report.get("runtime_character_animation_component_wiring_spawn_prerequisite_verified") is True
            and report.get("runtime_character_animation_component_wiring_spawnable_regenerated_or_found") is True
            and bool(report.get("runtime_character_animation_component_wiring_runtime_component_inventory", []))
            and report.get("runtime_character_animation_component_wiring_surface_found") is True
            and report.get("runtime_character_animation_component_wiring_surface_verified") is True
            and report.get("runtime_character_animation_component_wiring_claimed") is False
            and report.get("runtime_character_animation_component_wiring_verified") is False
            and report.get("runtime_character_animation_claimed") is False
            and report.get("runtime_character_animation_verified") is False
            and report.get("runtime_character_proof_claimed") is False
            and report.get("runtime_character_proof_verified") is False
        )
    return report.get("runtime_character_animation_component_wiring_verified") is True


def _runtime_animation_playback_execution_source_specs(root: Path) -> List[Dict[str, Any]]:
    return _runtime_character_animation_source_specs(root) + [
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "EMotionFX" / "Source" / "MotionInstance.h",
            "symbols": ["GetCurrentTime", "GetDuration", "GetIsPlaying", "GetActorInstance"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "EMotionFX" / "Source" / "MotionSystem.h",
            "symbols": ["PlayMotion", "Update", "UpdateMotionInstances"],
        },
        {
            "path": RUNTIME_EXIT_FIXTURE_COMPONENT_SOURCE,
            "symbols": [
                "MAXINE_RUNTIME_ANIMATION_PLAYBACK_SOURCE_VALIDATED",
                "MAXINE_RUNTIME_ANIMATION_PLAYBACK_REQUEST",
                "MAXINE_RUNTIME_ANIMATION_PLAYBACK_OBSERVE",
                "MAXINE_RUNTIME_ANIMATION_PLAYBACK_SUMMARY",
                "SimpleMotionComponentRequestBus::Event",
                "SimpleMotionComponentRequestBus::EventResult",
                "PlayMotion",
                "GetPlayTime",
                "GetMotionInstance",
                "GetIsPlaying",
            ],
        },
    ]


def _runtime_animation_playback_execution_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [str(spec["path"]) for spec in _runtime_animation_playback_execution_source_specs(root)]


def _runtime_animation_playback_execution_source_validation(engine_root: Path | None) -> Dict[str, Any]:
    specs = _runtime_animation_playback_execution_source_specs(engine_root or Path(""))
    file_results = [_source_file_symbol_validation(spec["path"], spec["symbols"]) for spec in specs]
    missing = [result for result in file_results if result["status"] != "pass"]
    return {
        "status": "runtime_animation_playback_execution_api_source_validation_pass"
        if not missing
        else "runtime_animation_playback_execution_api_source_validation_inconclusive",
        "files": file_results,
        "runtime_playback_surfaces": {
            "simple_motion_request_bus": "EMotionFX::Integration::SimpleMotionComponentRequestBus",
            "simple_motion_play_api": "SimpleMotionComponentRequests::PlayMotion",
            "simple_motion_time_api": "SimpleMotionComponentRequests::GetPlayTime",
            "simple_motion_duration_api": "SimpleMotionComponentRequests::GetDuration",
            "simple_motion_motion_asset_api": "SimpleMotionComponentRequests::GetMotion",
            "simple_motion_motion_instance_api": "EMotionFX::Integration::SimpleMotionComponent::GetMotionInstance",
            "motion_instance_time_api": "EMotionFX::MotionInstance::GetCurrentTime",
            "motion_instance_playing_api": "EMotionFX::MotionInstance::GetIsPlaying",
            "motion_system_play_api": "EMotionFX::MotionSystem::PlayMotion",
            "fixture_marker_surface": "MAXINE_RUNTIME_ANIMATION_PLAYBACK_*",
        },
        "approved_motion_asset_id": RUNTIME_CHARACTER_APPROVED_MOTION_ASSET_ID,
        "missing": missing,
    }


def _runtime_animation_playback_execution_source_validated(report: Mapping[str, Any]) -> bool:
    return (
        str(report.get("runtime_animation_playback_execution_api_source_validation_status", "")).strip()
        == "runtime_animation_playback_execution_api_source_validation_pass"
        and report.get("runtime_animation_playback_execution_api_source_validation_verified") is True
        and bool(report.get("runtime_animation_playback_execution_api_source_files", []))
    )


def _runtime_animation_playback_execution_candidate_matrix(
    *,
    source_validated: bool,
    component_wiring_verified: bool,
    request_attempted: bool,
    request_succeeded: bool,
    playback_observed: bool,
    time_advanced: bool,
    blocker: str,
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "simple_motion_request_bus_play_motion",
            "candidate": "Simple Motion runtime request bus or equivalent explicit PlayMotion API",
            "kind": "runtime_playback_api",
            "attempted": request_attempted,
            "selected": bool(source_validated),
            "result": "runtime_animation_playback_execution_candidate_verified"
            if playback_observed and time_advanced
            else "runtime_animation_playback_execution_candidate_request_issued_observation_blocked"
            if request_succeeded
            else "runtime_animation_playback_execution_candidate_source_validated"
            if source_validated and not request_attempted
            else "runtime_animation_playback_execution_candidate_blocked_source_validation",
            "blocker": "" if playback_observed and time_advanced else blocker,
        },
        {
            "id": "simple_motion_component_auto_start_on_activation",
            "candidate": "Simple Motion component auto-start on activation",
            "kind": "runtime_component_activation_behavior",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_execution_candidate_deferred_explicit_request_selected",
            "blocker": "explicit_request_bus_playback_path_selected",
        },
        {
            "id": "actor_motion_instance_active_state",
            "candidate": "Actor instance / motion instance active playback state",
            "kind": "runtime_motion_instance_observation",
            "attempted": request_attempted,
            "selected": bool(source_validated and request_attempted),
            "result": "runtime_animation_playback_execution_candidate_observed"
            if playback_observed
            else "runtime_animation_playback_execution_candidate_blocked_observation",
            "blocker": "" if playback_observed else blocker,
        },
        {
            "id": "motion_asset_assignment_readback_only",
            "candidate": "motion AssetId assignment readback only",
            "kind": "runtime_assignment_reference",
            "attempted": component_wiring_verified,
            "selected": False,
            "result": "runtime_animation_playback_execution_candidate_rejected_assignment_only_insufficient",
            "blocker": "motion_assignment_is_not_playback_proof",
        },
        {
            "id": "runtime_actor_simple_motion_typeids_only",
            "candidate": "runtime Actor + Simple Motion TypeIds only",
            "kind": "runtime_component_inventory",
            "attempted": component_wiring_verified,
            "selected": False,
            "result": "runtime_animation_playback_execution_candidate_rejected_typeids_only_insufficient",
            "blocker": "runtime_typeids_are_not_playback_proof",
        },
        {
            "id": "product_load_apb_only",
            "candidate": "product-load/APB evidence only",
            "kind": "product_evidence",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_execution_candidate_rejected_product_load_only_insufficient",
            "blocker": "product_load_is_not_animation_playback_proof",
        },
        {
            "id": "animation_graph_playback",
            "candidate": "animation graph playback",
            "kind": "runtime_anim_graph_playback",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_execution_candidate_deferred_simple_motion_path_selected",
            "blocker": "anim_graph_playback_deferred_until_simple_motion_path_exhausted",
        },
        {
            "id": "defaultlevel_or_production_level_playback",
            "candidate": "defaultlevel or production-level playback proof",
            "kind": "unsafe_runtime_scope",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_execution_candidate_rejected_unsafe_scope",
            "blocker": "defaultlevel_or_production_level_runtime_evidence_disallowed",
        },
    ]


def _runtime_animation_playback_execution_source_payload(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    del timeout_seconds
    del artifact_dir
    source_validation = _runtime_animation_playback_execution_source_validation(engine_root)
    source_refs = _runtime_animation_playback_execution_source_refs(engine_root)
    source_validated = (
        source_validation.get("status")
        == "runtime_animation_playback_execution_api_source_validation_pass"
    )
    approved = _runtime_character_spawn_instantiation_approved_spawnable(
        product_evidence=product_evidence,
        project=project,
        engine_root=engine_root,
    )
    blocker = ""
    if not source_validated:
        blocker = "blocked_by_runtime_animation_playback_requires_additional_source_validation"
    elif not approved:
        blocker = "blocked_by_missing_runtime_equivalent_spawnable_surface"
    return {
        "runtime_animation_playback_execution_api_diagnostic_attempted": True,
        "runtime_animation_playback_execution_api_diagnostic_completed": True,
        "runtime_animation_playback_execution_api_source_validation_status": source_validation.get("status", ""),
        "runtime_animation_playback_execution_api_source_validation_verified": source_validated,
        "runtime_animation_playback_execution_api_found": source_validated,
        "runtime_animation_playback_execution_api_selected": (
            "EMotionFX::Integration::SimpleMotionComponentRequestBus::PlayMotion"
            if source_validated
            else ""
        ),
        "runtime_animation_playback_execution_api_blocker": blocker,
        "runtime_animation_playback_execution_api_source_validation": source_validation,
        "runtime_animation_playback_execution_api_source_files": source_refs,
        "runtime_animation_playback_execution_candidate_matrix": _runtime_animation_playback_execution_candidate_matrix(
            source_validated=source_validated,
            component_wiring_verified=False,
            request_attempted=False,
            request_succeeded=False,
            playback_observed=False,
            time_advanced=False,
            blocker=blocker,
        ),
        "runtime_animation_playback_execution_selected_strategy": (
            RUNTIME_ANIMATION_PLAYBACK_EXECUTION_SELECTED if source_validated else ""
        ),
        "runtime_animation_playback_preconditions_verified": False,
        "runtime_animation_playback_component_wiring_verified_prerequisite": False,
        "runtime_animation_playback_actor_component_found": False,
        "runtime_animation_playback_simple_motion_component_found": False,
        "runtime_animation_playback_actor_asset_assignment_verified": False,
        "runtime_animation_playback_motion_asset_assignment_verified": False,
        "runtime_animation_playback_motion_asset_id": "",
        "runtime_animation_playback_request_attempted": False,
        "runtime_animation_playback_request_succeeded": False,
        "runtime_animation_playback_started": False,
        "runtime_animation_playback_observed": False,
        "runtime_animation_playback_time_before": None,
        "runtime_animation_playback_time_after": None,
        "runtime_animation_playback_time_advanced": False,
        "runtime_animation_playback_active_state_observed": False,
        "runtime_animation_playback_tick_count": 0,
        "runtime_animation_playback_cleanup_verified": False,
        "runtime_character_animation_playback_attempted": False,
        "runtime_character_animation_playback_request_issued": False,
        "runtime_character_animation_playback_selected_api": "",
        "runtime_character_animation_playback_started": False,
        "runtime_character_animation_playback_observed": False,
        "runtime_character_animation_playback_time_before": None,
        "runtime_character_animation_playback_time_after": None,
        "runtime_character_animation_playback_time_advanced": False,
        "runtime_character_animation_playback_active_state_observed": False,
        "runtime_character_animation_playback_tick_count": 0,
        "runtime_character_animation_playback_cleanup_complete": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _run_runtime_animation_playback_execution_api_diagnostic(
    report: Dict[str, Any],
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_animation_playback_execution_source_payload(
            product_evidence=product_evidence,
            engine_root=engine_root,
            project=project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    source_validated = report.get("runtime_animation_playback_execution_api_source_validation_verified") is True
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": "runtime_animation_playback_execution_api_source_discovery"
            if source_validated
            else "blocked_by_runtime_animation_playback_requires_additional_source_validation",
            "runtime_harness_mode": "runtime_animation_playback_execution_api_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_animation_playback_attempted": False,
            "runtime_character_animation_playback_started": False,
            "runtime_character_animation_playback_observed": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_animation_playback_execution_api_source_discovery",
                "runtime_execution_not_attempted_in_animation_playback_execution_api_diagnostic_mode",
                "runtime_animation_playback_not_claimed_without_live_fixture",
                "runtime_character_proof_not_claimed",
            ]
            if source_validated
            else [],
            "required_runtime_harness_assertions_failed": []
            if source_validated
            else ["runtime_animation_playback_execution_api_source_validation"],
            "runtime_harness_assertion_informational": [
                "playback_api_source_discovery_is_not_runtime_animation_playback_proof",
                "runtime_component_wiring_is_not_animation_playback_proof",
                "full_runtime_character_proof_remains_out_of_scope",
            ],
        }
    )
    return _finalize_report(report)


def _runtime_animation_playback_parse_markers(combined_text: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "source_validated_marker": False,
        "request_attempted": False,
        "request_succeeded": False,
        "started": False,
        "observed": False,
        "time_before": None,
        "time_after": None,
        "duration": None,
        "time_advanced": False,
        "active_state_observed": False,
        "tick_count": 0,
        "motion_asset_id": "",
        "selected_api": "",
        "blocker": "",
        "summary": {},
    }
    for raw_line in combined_text.splitlines():
        marker_index = raw_line.find("MAXINE_RUNTIME_ANIMATION_PLAYBACK_")
        if marker_index < 0:
            continue
        line = raw_line[marker_index:].strip()
        fields = _runtime_marker_fields(line)
        if line.startswith("MAXINE_RUNTIME_ANIMATION_PLAYBACK_SOURCE_VALIDATED"):
            payload["source_validated_marker"] = str(fields.get("status", "")).strip() == "pass"
        elif line.startswith("MAXINE_RUNTIME_ANIMATION_PLAYBACK_REQUEST"):
            payload["request_attempted"] = True
            payload["request_succeeded"] = str(fields.get("request_succeeded", "1")).strip() in {
                "1",
                "true",
                "True",
                "pass",
            }
            payload["selected_api"] = fields.get("api", "")
            payload["motion_asset_id"] = fields.get("motion_asset_id", "")
            payload["time_before"] = _float_or_none(fields.get("play_time_before"))
            payload["duration"] = _float_or_none(fields.get("duration"))
        elif line.startswith("MAXINE_RUNTIME_ANIMATION_PLAYBACK_OBSERVE"):
            payload["started"] = str(fields.get("started", "0")).strip() in {"1", "true", "True"}
            payload["observed"] = str(fields.get("observed", "0")).strip() in {"1", "true", "True"}
            payload["time_before"] = _float_or_none(fields.get("play_time_before", payload.get("time_before")))
            payload["time_after"] = _float_or_none(fields.get("play_time_after"))
            payload["time_advanced"] = str(fields.get("time_advanced", "0")).strip() in {"1", "true", "True"}
            payload["active_state_observed"] = str(fields.get("active_state_observed", "0")).strip() in {
                "1",
                "true",
                "True",
            }
            payload["tick_count"] = _int_or_zero(fields.get("tick_count", 0))
            if str(fields.get("blocker", "")).strip():
                payload["blocker"] = str(fields.get("blocker", "")).strip()
        elif line.startswith("MAXINE_RUNTIME_ANIMATION_PLAYBACK_SUMMARY"):
            payload["summary"] = dict(fields)
            payload["started"] = payload["started"] or str(fields.get("started", "")).strip() in {"1", "true", "True"}
            payload["observed"] = payload["observed"] or str(fields.get("observed", "")).strip() in {"1", "true", "True"}
            payload["time_advanced"] = payload["time_advanced"] or str(fields.get("time_advanced", "")).strip() in {
                "1",
                "true",
                "True",
            }
            payload["active_state_observed"] = payload["active_state_observed"] or str(
                fields.get("active_state_observed", "")
            ).strip() in {"1", "true", "True"}
            payload["tick_count"] = max(
                _int_or_zero(payload.get("tick_count", 0)),
                _int_or_zero(fields.get("tick_count", 0)),
            )
            if str(fields.get("blocker", "")).strip():
                payload["blocker"] = str(fields.get("blocker", "")).strip()
    return payload


def _runtime_animation_playback_execution_payload(
    *,
    product_evidence: Mapping[str, Any],
    command: Mapping[str, Any],
    project: Path | None,
    actual_level_loads: Sequence[str],
    launch_hygiene: Mapping[str, Any],
    product_load: Mapping[str, Any],
    spawn_instantiation: Mapping[str, Any],
    animation_playback_surface: Mapping[str, Any],
    component_wiring: Mapping[str, Any],
    exit_code: int | None,
    marker_observed: bool,
    combined_text: str,
) -> Dict[str, Any]:
    del animation_playback_surface
    source_payload = _runtime_animation_playback_execution_source_payload(
        product_evidence=product_evidence,
        engine_root=_runtime_engine_root_from_command(command),
        project=project,
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        artifact_dir=DEFAULT_ARTIFACT_ROOT,
    )
    markers = _runtime_animation_playback_parse_markers(combined_text)
    source_validated = source_payload.get("runtime_animation_playback_execution_api_source_validation_verified") is True
    product_prerequisite = product_load.get("runtime_character_product_load_verified") is True
    spawn_prerequisite = spawn_instantiation.get("runtime_character_spawn_instantiation_verified") is True
    component_wiring_verified = component_wiring.get("runtime_character_animation_component_wiring_verified") is True
    launch_pass = str(launch_hygiene.get("runtime_launch_hygiene_status", "")).strip() == "runtime_launch_hygiene_pass"
    defaultlevel = bool(launch_hygiene.get("runtime_default_level_autoload_detected"))
    production_level = bool(actual_level_loads)
    cleanup_complete = str(
        spawn_instantiation.get("runtime_character_spawn_instantiation_cleanup_status", "")
    ).strip() in {
        "runtime_character_spawn_instantiation_cleanup_complete",
        "runtime_character_spawn_instantiation_cleanup_not_required",
    }
    actor_found = component_wiring.get("runtime_character_animation_component_wiring_runtime_actor_component_found") is True
    simple_motion_found = (
        component_wiring.get("runtime_character_animation_component_wiring_runtime_simple_motion_component_found") is True
    )
    actor_assignment_verified = (
        component_wiring.get("runtime_character_animation_component_wiring_runtime_actor_asset_assignment_verified") is True
    )
    motion_assignment_verified = (
        component_wiring.get("runtime_character_animation_component_wiring_runtime_motion_asset_assignment_verified") is True
    )
    motion_asset_id = str(
        markers.get("motion_asset_id")
        or component_wiring.get("runtime_character_animation_component_wiring_runtime_motion_asset_id", "")
    )
    motion_asset_matches = _runtime_asset_id_matches(motion_asset_id, RUNTIME_CHARACTER_APPROVED_MOTION_ASSET_ID)
    poolallocator_blocking_lines = _runtime_shutdown_poolallocator_signal_lines(combined_text)
    selected_log_blocks_playback = bool(poolallocator_blocking_lines)
    request_attempted = bool(markers.get("request_attempted"))
    request_succeeded = bool(markers.get("request_succeeded"))
    playback_started = bool(markers.get("started"))
    playback_observed = bool(markers.get("observed"))
    time_advanced = bool(markers.get("time_advanced"))
    active_state_observed = bool(markers.get("active_state_observed"))
    tick_count = _int_or_zero(markers.get("tick_count", 0))
    preconditions_verified = bool(
        source_validated
        and product_prerequisite
        and spawn_prerequisite
        and component_wiring_verified
        and actor_found
        and simple_motion_found
        and actor_assignment_verified
        and motion_assignment_verified
        and motion_asset_matches
        and launch_pass
        and not selected_log_blocks_playback
        and not defaultlevel
        and not production_level
    )
    playback_verified = bool(
        preconditions_verified
        and bool(markers.get("source_validated_marker"))
        and request_attempted
        and request_succeeded
        and playback_started
        and playback_observed
        and time_advanced
        and tick_count > 0
        and cleanup_complete
        and exit_code == 0
        and marker_observed
    )
    blocker = ""
    if defaultlevel:
        blocker = "blocked_by_default_level_autoload"
    elif production_level:
        blocker = "blocked_by_production_level_load"
    elif not source_validated:
        blocker = "blocked_by_runtime_animation_playback_requires_additional_source_validation"
    elif selected_log_blocks_playback:
        blocker = RUNTIME_SHUTDOWN_POOLALLOCATOR_SIGNAL_BLOCKER
    elif not product_prerequisite:
        blocker = "blocked_by_runtime_animation_product_load_prerequisite"
    elif not spawn_prerequisite:
        blocker = "blocked_by_runtime_animation_spawn_prerequisite"
    elif not component_wiring_verified:
        blocker = "blocked_by_runtime_animation_component_wiring_prerequisite_unverified"
    elif not motion_assignment_verified or not motion_asset_matches:
        blocker = "blocked_by_runtime_motion_asset_assignment_unverified"
    elif not request_attempted:
        blocker = RUNTIME_ANIMATION_PLAYBACK_EXECUTION_OBSERVATION_BLOCKER
    elif not request_succeeded:
        blocker = "blocked_by_runtime_animation_playback_request_failed"
    elif not playback_started:
        blocker = "blocked_by_runtime_simple_motion_active_state_unobserved"
    elif not playback_observed:
        blocker = str(markers.get("blocker", "")) or "blocked_by_runtime_animation_playback_observation_unavailable"
    elif not time_advanced:
        blocker = str(markers.get("blocker", "")) or RUNTIME_ANIMATION_PLAYBACK_TIME_NOT_ADVANCED_BLOCKER
    elif not cleanup_complete:
        blocker = "blocked_by_runtime_character_spawn_cleanup_failed"
    source_payload.update(
        {
            "runtime_animation_playback_execution_api_blocker": "" if playback_verified else blocker,
            "runtime_animation_playback_execution_verified": playback_verified,
            "runtime_animation_playback_execution_candidate_matrix": _runtime_animation_playback_execution_candidate_matrix(
                source_validated=source_validated,
                component_wiring_verified=component_wiring_verified,
                request_attempted=request_attempted,
                request_succeeded=request_succeeded,
                playback_observed=playback_observed,
                time_advanced=time_advanced,
                blocker=blocker,
            ),
            "runtime_animation_playback_execution_selected_strategy": (
                RUNTIME_ANIMATION_PLAYBACK_EXECUTION_SELECTED if source_validated else ""
            ),
            "runtime_animation_playback_preconditions_verified": preconditions_verified,
            "runtime_animation_playback_component_wiring_verified_prerequisite": component_wiring_verified,
            "runtime_animation_playback_actor_component_found": actor_found,
            "runtime_animation_playback_simple_motion_component_found": simple_motion_found,
            "runtime_animation_playback_actor_asset_assignment_verified": actor_assignment_verified,
            "runtime_animation_playback_motion_asset_assignment_verified": motion_assignment_verified,
            "runtime_animation_playback_motion_asset_id": motion_asset_id,
            "runtime_animation_playback_request_attempted": request_attempted,
            "runtime_animation_playback_request_succeeded": request_succeeded,
            "runtime_animation_playback_started": playback_started,
            "runtime_animation_playback_observed": playback_observed,
            "runtime_animation_playback_time_before": markers.get("time_before"),
            "runtime_animation_playback_time_after": markers.get("time_after"),
            "runtime_animation_playback_time_advanced": time_advanced,
            "runtime_animation_playback_active_state_observed": active_state_observed,
            "runtime_animation_playback_tick_count": tick_count,
            "runtime_animation_playback_cleanup_verified": cleanup_complete,
            "runtime_animation_playback_selected_log_blocking_matches": poolallocator_blocking_lines,
            "runtime_character_animation_playback_surface": {
                "status": "runtime_character_animation_playback_execution_verified"
                if playback_verified
                else "runtime_character_animation_playback_execution_blocked",
                "selected_strategy": RUNTIME_ANIMATION_PLAYBACK_EXECUTION_SELECTED if source_validated else "",
                "playback_request_attempted": request_attempted,
                "playback_request_succeeded": request_succeeded,
                "playback_started": playback_started,
                "playback_observed": playback_observed,
                "playback_time_advanced": time_advanced,
                "blocker": "" if playback_verified else blocker,
            },
            "runtime_character_animation_playback_surface_status": "runtime_character_animation_playback_execution_verified"
            if playback_verified
            else "runtime_character_animation_playback_execution_blocked",
            "runtime_character_animation_playback_surface_found": actor_found and simple_motion_found,
            "runtime_character_animation_playback_surface_verified": playback_verified,
            "runtime_character_animation_playback_surface_blocker": "" if playback_verified else blocker,
            "runtime_character_animation_playback_attempted": request_attempted,
            "runtime_character_animation_playback_request_issued": request_attempted,
            "runtime_character_animation_playback_selected_api": (
                "EMotionFX::Integration::SimpleMotionComponentRequestBus::PlayMotion"
                if source_validated
                else ""
            ),
            "runtime_character_animation_playback_started": playback_started,
            "runtime_character_animation_playback_observed": playback_observed,
            "runtime_character_animation_playback_time_before": markers.get("time_before"),
            "runtime_character_animation_playback_time_after": markers.get("time_after"),
            "runtime_character_animation_playback_time_advanced": time_advanced,
            "runtime_character_animation_playback_active_state_observed": active_state_observed,
            "runtime_character_animation_playback_tick_count": tick_count,
            "runtime_character_animation_playback_tick_duration_seconds": 0,
            "runtime_character_animation_playback_cleanup_complete": cleanup_complete,
            "runtime_character_animation_claimed": playback_verified,
            "runtime_character_animation_verified": playback_verified,
            "runtime_character_animation_is_full_character_proof": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    )
    return source_payload


def _runtime_animation_playback_execution_fixture_passed(report: Mapping[str, Any]) -> bool:
    return (
        _runtime_animation_playback_execution_source_validated(report)
        and report.get("runtime_animation_playback_preconditions_verified") is True
        and report.get("runtime_animation_playback_component_wiring_verified_prerequisite") is True
        and report.get("runtime_animation_playback_request_attempted") is True
        and report.get("runtime_animation_playback_request_succeeded") is True
        and report.get("runtime_character_animation_playback_started") is True
        and report.get("runtime_character_animation_playback_observed") is True
        and report.get("runtime_animation_playback_time_advanced") is True
        and _int_or_zero(report.get("runtime_character_animation_playback_tick_count", 0)) > 0
        and report.get("runtime_animation_playback_cleanup_verified") is True
        and report.get("runtime_character_animation_claimed") is True
        and report.get("runtime_character_animation_verified") is True
        and report.get("runtime_character_proof_claimed") is False
        and report.get("runtime_character_proof_verified") is False
    )


def _runtime_character_animation_component_wiring_candidate_matrix(
    *,
    source_validated: bool,
    product_found: bool,
    runtime_inventory: Sequence[Mapping[str, Any]],
    runtime_actor_found: bool,
    runtime_simple_motion_found: bool,
    runtime_anim_graph_found: bool,
    runtime_surface_found: bool,
    runtime_wiring_verified: bool,
    blocker: str,
) -> List[Dict[str, Any]]:
    has_inventory = bool(runtime_inventory)
    source_status = (
        "runtime_animation_component_wiring_candidate_source_validated"
        if source_validated
        else "runtime_animation_component_wiring_candidate_rejected_missing_source_validation"
    )
    return [
        {
            "id": "update_approved_source_prefab_through_editor_prefab_api",
            "candidate": "update approved repo-owned source prefab through source-backed Editor/prefab APIs",
            "kind": "editor_prefab_api_wiring",
            "attempted": False,
            "selected": False,
            "source_validation": {"status": source_status},
            "result": "runtime_animation_component_wiring_candidate_not_attempted_runtime_inventory_only"
            if runtime_surface_found
            else "runtime_animation_component_wiring_candidate_blocked_requires_editor_generated_prefab_update"
            if source_validated and product_found
            else "runtime_animation_component_wiring_candidate_rejected_missing_source_validation",
            "blocker": blocker,
        },
        {
            "id": "actor_plus_simple_motion_component_surface",
            "candidate": "add Actor + Simple Motion component surface",
            "kind": "minimal_runtime_playback_capable_editor_components",
            "attempted": bool(runtime_actor_found and runtime_simple_motion_found),
            "selected": bool(runtime_actor_found and runtime_simple_motion_found),
            "source_validation": {"status": source_status},
            "result": "runtime_animation_component_wiring_candidate_verified_runtime_typeids"
            if runtime_actor_found and runtime_simple_motion_found
            else "runtime_animation_component_wiring_candidate_preferred_minimal_surface_deferred",
            "blocker": blocker,
        },
        {
            "id": "actor_plus_anim_graph_motion_set_component_surface",
            "candidate": "add Actor + Anim Graph + Motion Set component surface",
            "kind": "animgraph_runtime_component_surface",
            "attempted": bool(runtime_actor_found and runtime_anim_graph_found),
            "selected": bool(runtime_actor_found and runtime_anim_graph_found),
            "source_validation": {"status": source_status},
            "result": "runtime_animation_component_wiring_candidate_verified_runtime_typeids"
            if runtime_actor_found and runtime_anim_graph_found
            else "runtime_animation_component_wiring_candidate_deferred_until_asset_assignment_surface_is_live_discovered",
            "blocker": blocker if runtime_actor_found and runtime_anim_graph_found else "animgraph_motion_set_wiring_deferred_for_smaller_safe_slice",
        },
        {
            "id": "hand_author_unknown_component_json",
            "candidate": "hand-author unknown component JSON in .prefab",
            "kind": "unknown_component_serialization",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_component_wiring_candidate_rejected_unvalidated_serialization",
            "blocker": "hand_authored_unknown_o3de_component_serialization_forbidden",
        },
        {
            "id": "direct_runtime_procprefab_load",
            "candidate": "direct runtime .procprefab load",
            "kind": "runtime_procprefab_direct_load",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_component_wiring_candidate_rejected_builder_only_surface",
            "blocker": "direct_procprefab_runtime_load_unsupported_builder_only",
        },
        {
            "id": "direct_product_load_actor_motion_motionset_animgraph",
            "candidate": "direct product-load of actor/motion/motionset/animgraph",
            "kind": "runtime_asset_product_load_only",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_component_wiring_candidate_rejected_insufficient_for_component_wiring_proof",
            "blocker": "product_load_is_not_runtime_component_wiring_proof",
        },
        {
            "id": "defaultlevel_or_production_level_wiring_playback",
            "candidate": "defaultlevel or production-level wiring/playback",
            "kind": "level_runtime_playback",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_component_wiring_candidate_rejected_unsafe_scope",
            "blocker": "defaultlevel_or_production_level_runtime_evidence_disallowed",
        },
        {
            "id": "temp_or_sandbox_level",
            "candidate": "temp/sandbox level",
            "kind": "temp_level_runtime_context",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_component_wiring_candidate_rejected_no_level_fixture_preferred",
            "blocker": "temp_or_sandbox_level_not_required_for_this_slice",
        },
        {
            "id": "current_approved_spawned_runtime_inventory",
            "candidate": "existing approved spawned runtime entities expose EMotionFX runtime component TypeIds",
            "kind": "runtime_spawned_component_inventory",
            "attempted": has_inventory,
            "selected": runtime_surface_found,
            "result": "runtime_animation_component_wiring_candidate_runtime_surface_found"
            if runtime_surface_found
            else "runtime_animation_component_wiring_candidate_blocked_missing_runtime_components"
            if has_inventory
            else "runtime_animation_component_wiring_candidate_requires_runtime_spawn_inventory",
            "blocker": "" if runtime_surface_found else blocker,
        },
        {
            "id": "runtime_typeids_and_asset_assignments",
            "candidate": "runtime TypeIds plus source-validated asset-assignment evidence",
            "kind": "runtime_wiring_verification",
            "attempted": has_inventory,
            "selected": runtime_surface_found,
            "source_validation": {"status": source_status},
            "result": "runtime_animation_component_wiring_candidate_verified_runtime_typeids_and_asset_assignments"
            if runtime_wiring_verified
            else "runtime_animation_component_wiring_candidate_blocked_asset_assignment_unverified"
            if runtime_surface_found
            else "runtime_animation_component_wiring_candidate_blocked_missing_runtime_components"
            if has_inventory
            else "runtime_animation_component_wiring_candidate_requires_runtime_spawn_inventory",
            "blocker": "" if runtime_wiring_verified else blocker,
        },
    ]


def _runtime_character_animation_component_wiring_source_refs(engine_root: Path | None) -> List[str]:
    return [
        str(spec["path"])
        for spec in _runtime_character_animation_component_wiring_source_specs(engine_root or Path("<engine-root>"))
    ]


def _runtime_character_animation_component_wiring_source_validation(engine_root: Path | None) -> Dict[str, Any]:
    specs = _runtime_character_animation_component_wiring_source_specs(engine_root or Path(""))
    file_results = [_source_file_symbol_validation(spec["path"], spec["symbols"]) for spec in specs]
    missing = [result for result in file_results if result["status"] != "pass"]
    runtime_validation = _runtime_character_animation_source_validation(engine_root)
    if runtime_validation.get("status") != "runtime_character_animation_source_validation_pass":
        missing.extend(runtime_validation.get("missing", []))
    return {
        "status": "runtime_character_animation_component_wiring_source_validation_pass"
        if not missing
        else "runtime_character_animation_component_wiring_source_validation_inconclusive",
        "files": file_results,
        "runtime_source_validation": runtime_validation,
        "editor_component_surfaces": {
            "actor_component": "EMotionFX::Integration::EditorActorComponent",
            "actor_component_type_id": EDITOR_EMOTIONFX_ACTOR_COMPONENT_TYPE_ID,
            "actor_asset_property": "Actor asset",
            "actor_serialized_field": "ActorAsset",
            "actor_runtime_component": "EMotionFX::Integration::ActorComponent",
            "simple_motion_component": "EMotionFX::Integration::EditorSimpleMotionComponent",
            "simple_motion_component_type_id": EDITOR_EMOTIONFX_SIMPLE_MOTION_COMPONENT_TYPE_ID,
            "simple_motion_asset_property": "Configuration|Motion",
            "simple_motion_serialized_field": "Configuration|MotionAsset",
            "simple_motion_runtime_component": "EMotionFX::Integration::SimpleMotionComponent",
            "anim_graph_component": "EMotionFX::Integration::EditorAnimGraphComponent",
            "anim_graph_component_type_id": EDITOR_EMOTIONFX_ANIM_GRAPH_COMPONENT_TYPE_ID,
            "anim_graph_asset_property": "Anim graph",
            "motion_set_asset_property": "Motion set asset",
            "anim_graph_serialized_field": "AnimGraphAsset",
            "motion_set_serialized_field": "MotionSetAsset",
            "anim_graph_runtime_component": "EMotionFX::Integration::AnimGraphComponent",
        },
        "editor_component_api": {
            "AddComponentsOfType": "AzToolsFramework::EditorComponentAPIRequests::AddComponentsOfType",
            "BuildComponentPropertyList": "AzToolsFramework::EditorComponentAPIRequests::BuildComponentPropertyList",
            "GetComponentProperty": "AzToolsFramework::EditorComponentAPIRequests::GetComponentProperty",
            "SetComponentProperty": "AzToolsFramework::EditorComponentAPIRequests::SetComponentProperty",
        },
        "prefab_api": {
            "CreatePrefabInMemory": "AzToolsFramework::Prefab::PrefabPublicRequests::CreatePrefabInMemory",
            "InstantiatePrefab": "AzToolsFramework::Prefab::PrefabPublicRequests::InstantiatePrefab",
            "SavePrefab": "AzToolsFramework::Prefab::PrefabPublicHandler::SavePrefab",
            "CreatePrefabAndSaveToDisk": "AzToolsFramework::Prefab::PrefabPublicHandler::CreatePrefabAndSaveToDisk",
        },
        "spawnable_generation_surface": {
            "source_prefab": RUNTIME_CHARACTER_PREFAB_SOURCE_REPO_REF,
            "runtime_product": RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_PRODUCT,
            "conversion": "AzToolsFramework::Prefab::PrefabConversionUtils::CreateSpawnable",
            "hand_authored_unknown_serialization_allowed": False,
        },
        "missing": missing,
    }


def _runtime_character_animation_component_wiring_source_specs(root: Path) -> List[Dict[str, Any]]:
    return _runtime_character_animation_source_specs(root) + [
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Editor" / "Components" / "EditorActorComponent.h",
            "symbols": [EDITOR_EMOTIONFX_ACTOR_COMPONENT_TYPE_ID, "BuildGameEntity", "GetActorAssetId"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Editor" / "Components" / "EditorActorComponent.cpp",
            "symbols": ["Field(\"ActorAsset\"", "Actor asset", "cfg.m_actorAsset = m_actorAsset", "AddComponent(aznew ActorComponent"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Editor" / "Components" / "EditorSimpleMotionComponent.h",
            "symbols": [EDITOR_EMOTIONFX_SIMPLE_MOTION_COMPONENT_TYPE_ID, "Motion(AZ::Data::AssetId", "BuildGameEntity"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Editor" / "Components" / "EditorSimpleMotionComponent.cpp",
            "symbols": ["Field(\"Configuration\"", "Simple Motion", "gameEntity->AddComponent(aznew SimpleMotionComponent"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Editor" / "Components" / "EditorAnimGraphComponent.h",
            "symbols": [EDITOR_EMOTIONFX_ANIM_GRAPH_COMPONENT_TYPE_ID, "SetAnimGraphAssetId", "SetMotionSetAssetId", "BuildGameEntity"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Editor" / "Components" / "EditorAnimGraphComponent.cpp",
            "symbols": [
                "Field(\"AnimGraphAsset\"",
                "Field(\"MotionSetAsset\"",
                "Motion set asset",
                "Anim graph",
                "AZ::Data::Asset<AnimGraphAsset>(assetId",
                "AZ::Data::Asset<MotionSetAsset>(assetId",
                "cfg.m_animGraphAsset = m_animGraphAsset",
                "cfg.m_motionSetAsset = m_motionSetAsset",
                "AddComponent(aznew AnimGraphComponent",
            ],
        },
        {
            "path": root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Component" / "EditorComponentAPIBus.h",
            "symbols": ["AddComponentsOfType", "GetComponentProperty", "SetComponentProperty", "BuildComponentPropertyList", "EditorComponentAPIBus"],
        },
        {
            "path": root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Component" / "EditorComponentAPIComponent.cpp",
            "symbols": [
                "Event(\"AddComponentsOfType\"",
                "Event(\"GetComponentProperty\"",
                "Event(\"SetComponentProperty\"",
                "Event(\"BuildComponentPropertyList\"",
            ],
        },
        {
            "path": root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "PrefabPublicRequestBus.h",
            "symbols": ["CreatePrefabInMemory", "InstantiatePrefab"],
        },
        {
            "path": root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "PrefabPublicHandler.cpp",
            "symbols": ["CreatePrefabAndSaveToDisk", "CreatePrefabInMemory", "SaveTemplateToFile", "InstantiatePrefab", "SavePrefab"],
        },
        {
            "path": root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Spawnable" / "SpawnableUtils.cpp",
            "symbols": ["CreateSpawnable", "AzFramework::Spawnable", "spawnable.GetEntities()"],
        },
    ]


def _runtime_character_animation_component_type_map() -> Dict[str, Dict[str, str]]:
    return {
        _runtime_type_id_key(RUNTIME_TRANSFORM_COMPONENT_TYPE_ID): {
            "type_id": RUNTIME_TRANSFORM_COMPONENT_TYPE_ID,
            "runtime_name": "AZ::TransformComponent",
            "role": "transform",
            "source": "runtime entity component inventory TypeId",
        },
        _runtime_type_id_key(RUNTIME_EMOTIONFX_ACTOR_COMPONENT_TYPE_ID): {
            "type_id": RUNTIME_EMOTIONFX_ACTOR_COMPONENT_TYPE_ID,
            "runtime_name": "EMotionFX::Integration::ActorComponent",
            "role": "emotionfx_actor",
            "source": "ActorComponent.h AZ_COMPONENT",
        },
        _runtime_type_id_key(RUNTIME_EMOTIONFX_ANIM_GRAPH_COMPONENT_TYPE_ID): {
            "type_id": RUNTIME_EMOTIONFX_ANIM_GRAPH_COMPONENT_TYPE_ID,
            "runtime_name": "EMotionFX::Integration::AnimGraphComponent",
            "role": "emotionfx_anim_graph",
            "source": "AnimGraphComponent.h AZ_COMPONENT",
        },
        _runtime_type_id_key(RUNTIME_EMOTIONFX_SIMPLE_MOTION_COMPONENT_TYPE_ID): {
            "type_id": RUNTIME_EMOTIONFX_SIMPLE_MOTION_COMPONENT_TYPE_ID,
            "runtime_name": "EMotionFX::Integration::SimpleMotionComponent",
            "role": "emotionfx_simple_motion",
            "source": "SimpleMotionComponent.h AZ_COMPONENT",
        },
    }


def _runtime_character_animation_asset_type_map() -> Dict[str, Dict[str, str]]:
    return {
        "actor": {
            "asset_type_id": RUNTIME_EMOTIONFX_ACTOR_ASSET_TYPE_ID,
            "asset_class": "EMotionFX::Integration::ActorAsset",
            "extension": "actor",
        },
        "motion": {
            "asset_type_id": RUNTIME_EMOTIONFX_MOTION_ASSET_TYPE_ID,
            "asset_class": "EMotionFX::Integration::MotionAsset",
            "extension": "motion",
        },
        "motionset": {
            "asset_type_id": RUNTIME_EMOTIONFX_MOTION_SET_ASSET_TYPE_ID,
            "asset_class": "EMotionFX::Integration::MotionSetAsset",
            "extension": "motionset",
        },
        "animgraph": {
            "asset_type_id": RUNTIME_EMOTIONFX_ANIM_GRAPH_ASSET_TYPE_ID,
            "asset_class": "EMotionFX::Integration::AnimGraphAsset",
            "extension": "animgraph",
        },
    }


def _runtime_character_animation_component_inventory(raw_inventory: Any) -> List[Dict[str, Any]]:
    component_map = _runtime_character_animation_component_type_map()
    inventory: List[Dict[str, Any]] = []
    if not isinstance(raw_inventory, Sequence) or isinstance(raw_inventory, (str, bytes)):
        return inventory
    for raw_entity in raw_inventory:
        if not isinstance(raw_entity, Mapping):
            continue
        components: List[Dict[str, str]] = []
        for raw_component in raw_entity.get("components", []):
            type_id = str(raw_component).strip()
            type_key = _runtime_type_id_key(type_id)
            known = component_map.get(type_key, {})
            components.append(
                {
                    "type_id": type_id,
                    "type_id_normalized": type_key,
                    "runtime_name": str(known.get("runtime_name", "")),
                    "role": str(known.get("role", "unknown")),
                    "source_validated_name": str(known.get("source", "")),
                }
            )
        inventory.append(
            {
                "entity_id": str(raw_entity.get("entity_id", "")),
                "entity_name": str(raw_entity.get("entity_name", "")),
                "component_count": _int_or_zero(raw_entity.get("component_count", len(components))),
                "actor_asset_id": str(raw_entity.get("actor_asset_id", "")),
                "motion_asset_id": str(raw_entity.get("motion_asset_id", "")),
                "components": components,
            }
        )
    return inventory


def _runtime_character_animation_candidate_matrix(
    *,
    source_validated: bool,
    component_inventory: Sequence[Mapping[str, Any]],
    surface_found: bool,
    blocker: str,
    playback_attempted: bool,
) -> List[Dict[str, Any]]:
    has_runtime_inventory = bool(component_inventory)
    return [
        {
            "id": "approved_spawnable_runtime_emotionfx_surface",
            "candidate": "existing approved spawnable exposes runtime EMotionFX animation component surface",
            "kind": "runtime_spawned_component_inventory",
            "attempted": has_runtime_inventory,
            "selected": bool(surface_found),
            "result": "runtime_animation_playback_candidate_selected"
            if surface_found
            else "runtime_animation_playback_candidate_blocked_missing_runtime_component_surface"
            if has_runtime_inventory
            else "runtime_animation_playback_candidate_requires_spawn_inventory",
            "blocker": "" if surface_found else blocker,
        },
        {
            "id": "direct_product_load_actor_motion_motionset_animgraph",
            "candidate": "direct product-load of actor/motion/motionset/animgraph only",
            "kind": "runtime_asset_product_load_only",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_candidate_rejected_insufficient_for_playback_proof",
            "blocker": "product_load_is_not_animation_playback_proof",
        },
        {
            "id": "direct_runtime_procprefab_load",
            "candidate": "direct runtime .procprefab load",
            "kind": "runtime_procprefab_direct_load",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_candidate_rejected_builder_only_surface",
            "blocker": "direct_procprefab_runtime_load_unsupported_builder_only",
        },
        {
            "id": "editor_only_direct_procprefab_component_evidence",
            "candidate": "Editor-only direct .procprefab component evidence",
            "kind": "editor_component_inventory",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_candidate_rejected_not_runtime_playback_proof",
            "blocker": "editor_only_evidence_is_not_runtime_animation_playback_proof",
        },
        {
            "id": "defaultlevel_or_production_level_playback",
            "candidate": "defaultlevel or production-level playback",
            "kind": "level_runtime_playback",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_candidate_rejected_unsafe_scope",
            "blocker": "defaultlevel_or_production_level_runtime_evidence_disallowed",
        },
        {
            "id": "hand_authored_unknown_runtime_component_json",
            "candidate": "hand-authored unknown runtime component JSON",
            "kind": "unknown_component_serialization",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_candidate_rejected_unvalidated_serialization",
            "blocker": "unknown_component_serialization_not_source_validated",
        },
        {
            "id": "approved_source_prefab_component_wiring_required",
            "candidate": "approved source-prefab component wiring required",
            "kind": "typed_blocker",
            "attempted": False,
            "selected": False,
            "result": "runtime_animation_playback_candidate_blocked_prefab_wiring_required"
            if blocker == RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_MISSING_BLOCKER
            else "runtime_animation_playback_candidate_not_selected",
            "blocker": blocker if blocker == RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_MISSING_BLOCKER else "",
        },
        {
            "id": "source_validated_runtime_playback_api",
            "candidate": "source-validated Simple Motion or Anim Graph playback API",
            "kind": "runtime_playback_api",
            "attempted": bool(playback_attempted),
            "selected": bool(surface_found),
            "result": "runtime_animation_playback_candidate_not_attempted_without_component_surface"
            if not surface_found
            else "runtime_animation_playback_candidate_blocked_until_playback_observed",
            "blocker": "" if surface_found else blocker,
        },
    ]


def _runtime_character_animation_source_refs(engine_root: Path | None) -> List[str]:
    return [str(spec["path"]) for spec in _runtime_character_animation_source_specs(engine_root or Path("<engine-root>"))]


def _runtime_character_animation_source_validation(engine_root: Path | None) -> Dict[str, Any]:
    specs = _runtime_character_animation_source_specs(engine_root or Path(""))
    file_results = [_source_file_symbol_validation(spec["path"], spec["symbols"]) for spec in specs]
    missing = [result for result in file_results if result["status"] != "pass"]
    return {
        "status": "runtime_character_animation_source_validation_pass"
        if not missing
        else "runtime_character_animation_source_validation_inconclusive",
        "files": file_results,
        "runtime_component_surfaces": {
            "actor_component": "EMotionFX::Integration::ActorComponent",
            "actor_component_type_id": RUNTIME_EMOTIONFX_ACTOR_COMPONENT_TYPE_ID,
            "actor_request_bus": "EMotionFX::Integration::ActorComponentRequestBus",
            "actor_instance_api": "ActorComponentRequests::GetActorInstance",
            "anim_graph_component": "EMotionFX::Integration::AnimGraphComponent",
            "anim_graph_component_type_id": RUNTIME_EMOTIONFX_ANIM_GRAPH_COMPONENT_TYPE_ID,
            "anim_graph_request_bus": "EMotionFX::Integration::AnimGraphComponentRequestBus",
            "anim_graph_instance_api": "AnimGraphComponentRequests::GetAnimGraphInstance",
            "anim_graph_start_api": "AnimGraphComponentRequests::StartAnimGraph",
            "motion_set_api": "AnimGraphComponentRequests::SetActiveMotionSet",
            "simple_motion_component": "EMotionFX::Integration::SimpleMotionComponent",
            "simple_motion_component_type_id": RUNTIME_EMOTIONFX_SIMPLE_MOTION_COMPONENT_TYPE_ID,
            "simple_motion_request_bus": "EMotionFX::Integration::SimpleMotionComponentRequestBus",
            "simple_motion_play_api": "SimpleMotionComponentRequests::PlayMotion",
            "simple_motion_time_api": "SimpleMotionComponentRequests::GetPlayTime",
        },
        "runtime_asset_handlers": {
            "actor": "ActorAssetHandler / ActorAsset .actor",
            "motion": "MotionAssetHandler / MotionAsset .motion",
            "motionset": "MotionSetAssetHandler / MotionSetAsset .motionset",
            "animgraph": "AnimGraphAssetHandler / AnimGraphAsset .animgraph",
        },
        "component_inventory_surface": {
            "entity_components": "AZ::Entity::GetComponents",
            "type_ids": "AZ::Component::RTTI_GetType",
            "fixture_marker": "MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY components=<TypeId;...> actor_asset_id=<AssetId> motion_asset_id=<AssetId>",
        },
        "runtime_assignment_surfaces": {
            "actor_asset_readback": "EMotionFX::Integration::ActorComponent::GetActorAsset",
            "simple_motion_asset_readback": "EMotionFX::Integration::SimpleMotionComponent::GetMotion / SimpleMotionComponentRequestBus::GetMotion",
            "approved_actor_asset_id": RUNTIME_CHARACTER_APPROVED_ACTOR_ASSET_ID,
            "approved_motion_asset_id": RUNTIME_CHARACTER_APPROVED_MOTION_ASSET_ID,
        },
        "missing": missing,
    }


def _runtime_character_animation_source_specs(root: Path) -> List[Dict[str, Any]]:
    return [
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Components" / "ActorComponent.h",
            "symbols": ["AZ_COMPONENT(ActorComponent", RUNTIME_EMOTIONFX_ACTOR_COMPONENT_TYPE_ID, "GetActorInstance", "GetActorAsset"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Components" / "ActorComponent.cpp",
            "symbols": ["ActorComponentRequestBus", "m_actorInstance"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Include" / "Integration" / "ActorComponentBus.h",
            "symbols": ["ActorComponentRequests", "ActorComponentRequestBus", "GetActorInstance"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Components" / "AnimGraphComponent.h",
            "symbols": [
                "AZ_COMPONENT(AnimGraphComponent",
                RUNTIME_EMOTIONFX_ANIM_GRAPH_COMPONENT_TYPE_ID,
                "GetAnimGraphInstance",
                "SetActiveMotionSet",
                "StartAnimGraph",
            ],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Components" / "AnimGraphComponent.cpp",
            "symbols": ["AnimGraphComponentRequestBus", "SetAnimGraphAssetId", "SetMotionSetAssetId", "StartAnimGraph"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Include" / "Integration" / "AnimGraphComponentBus.h",
            "symbols": ["AnimGraphComponentRequests", "AnimGraphComponentRequestBus", "GetAnimGraphInstance", "StartAnimGraph"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Components" / "SimpleMotionComponent.h",
            "symbols": [
                "AZ_COMPONENT(SimpleMotionComponent",
                RUNTIME_EMOTIONFX_SIMPLE_MOTION_COMPONENT_TYPE_ID,
                "GetPlayTime",
                "GetDuration",
                "PlayMotion",
                "GetMotion",
            ],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Components" / "SimpleMotionComponent.cpp",
            "symbols": [
                "SimpleMotionComponentRequestBus",
                "Field(\"MotionAsset\"",
                "\"Motion\", \"EMotion FX motion",
                "SetMotionAssetId",
                "PlayMotionInternal",
                "GetMotionSystem()->PlayMotion",
            ],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Include" / "Integration" / "SimpleMotionComponentBus.h",
            "symbols": ["SimpleMotionComponentRequests", "SimpleMotionComponentRequestBus", "GetPlayTime", "Motion", "GetMotion", "PlayMotion"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "ActorAsset.h",
            "symbols": ["ActorAsset", RUNTIME_EMOTIONFX_ACTOR_ASSET_TYPE_ID],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionAsset.h",
            "symbols": ["MotionAsset", RUNTIME_EMOTIONFX_MOTION_ASSET_TYPE_ID],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionSetAsset.h",
            "symbols": ["MotionSetAsset", RUNTIME_EMOTIONFX_MOTION_SET_ASSET_TYPE_ID],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "AnimGraphAsset.h",
            "symbols": ["AnimGraphAsset", RUNTIME_EMOTIONFX_ANIM_GRAPH_ASSET_TYPE_ID],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "ActorAsset.cpp",
            "symbols": ["azrtti_typeid<ActorAsset>", "actor"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionAsset.cpp",
            "symbols": ["azrtti_typeid<MotionAsset>", "motion"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionSetAsset.cpp",
            "symbols": ["azrtti_typeid<MotionSetAsset>", "motionset"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "AnimGraphAsset.cpp",
            "symbols": ["azrtti_typeid<AnimGraphAsset>", "animgraph"],
        },
        {
            "path": root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "System" / "SystemComponent.cpp",
            "symbols": ["ActorAssetHandler", "MotionAssetHandler", "MotionSetAssetHandler", "AnimGraphAssetHandler"],
        },
    ]


def _source_file_symbol_validation(path: Path, symbols: Sequence[str]) -> Dict[str, Any]:
    if not path.is_file():
        return {
            "path": str(path),
            "status": "missing",
            "symbols": list(symbols),
            "missing_symbols": list(symbols),
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [symbol for symbol in symbols if symbol not in text]
    return {
        "path": str(path),
        "status": "pass" if not missing else "missing_symbols",
        "symbols": list(symbols),
        "missing_symbols": missing,
    }


def _runtime_type_id_key(type_id: Any) -> str:
    return str(type_id).strip().upper()


def _run_runtime_character_prefab_source_diagnostic(
    report: Dict[str, Any],
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_character_prefab_source_payload(
            product_evidence=product_evidence,
            engine_root=engine_root,
            project=project,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": report.get("runtime_character_prefab_source_status", ""),
            "runtime_harness_mode": "runtime_character_prefab_source_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_spawnable_surface_claimed": False,
            "runtime_character_spawnable_surface_verified": False,
            "runtime_character_product_load_claimed": False,
            "runtime_character_product_load_verified": False,
            "runtime_character_instantiation_claimed": False,
            "runtime_character_instantiation_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_character_prefab_source_source_discovery",
                "runtime_character_prefab_source_repo_owned",
                "runtime_character_prefab_source_not_defaultlevel_or_production",
                "runtime_character_spawnable_surface_candidate_search_recorded",
                "runtime_execution_not_attempted_in_character_prefab_source_diagnostic_mode",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "approved_prefab_source_generation_is_not_runtime_load_proof",
                "spawnable_surface_generation_is_not_spawn_instantiation_proof",
                "runtime_character_product_load_remains_blocked_until_approved_spawnable_surface_is_verified",
            ],
        }
    )
    return _finalize_report(report)


def _runtime_character_prefab_source_payload(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    source_path = REPO_ROOT / RUNTIME_CHARACTER_PREFAB_SOURCE_REPO_REF
    source_ref = _repo_relative(source_path)
    source_info = _runtime_character_prefab_source_info(source_path)
    source_refs = _runtime_character_prefab_source_refs(engine_root, source_path)
    engine_source_validated = _runtime_character_prefab_source_engine_validated(engine_root)
    source_validated = engine_source_validated and bool(source_info["is_approved"])
    source_validation_status = (
        "runtime_character_prefab_source_source_discovery_pass"
        if source_validated
        else "runtime_character_prefab_source_source_discovery_inconclusive"
    )

    surface_payload = _runtime_character_spawnable_surface_payload(
        product_evidence=product_evidence,
        engine_root=engine_root,
        project=project,
        timeout_seconds=timeout_seconds,
        artifact_dir=artifact_dir,
    )
    candidates = surface_payload.get("runtime_character_spawnable_surface_candidates", [])
    selected_product = _runtime_character_prefab_source_expected_product(candidates)
    product_found = bool(selected_product)
    product_status = (
        "runtime_character_prefab_source_apb_product_found"
        if product_found
        else "runtime_character_prefab_source_apb_product_missing"
    )
    status = (
        product_status
        if source_validated
        else "blocked_by_runtime_character_prefab_source_shape_not_validated"
    )
    generation_blocker = "" if source_validated else "blocked_by_runtime_character_prefab_source_shape_not_validated"
    source_changes = [source_ref] if source_validated else []

    surface_payload.update(
        {
            "runtime_character_spawnable_surface_generation_completed": product_found,
            "runtime_character_spawnable_surface_generation_source_changes": source_changes,
            "runtime_character_spawnable_surface_generation_strategy": (
                "repo_owned_reviewed_prefab_source_processed_by_Prefabs_builder"
                if source_validated
                else surface_payload.get("runtime_character_spawnable_surface_generation_strategy", "")
            ),
            "runtime_character_product_load_contract_updated": True,
            "runtime_character_product_load_direct_procprefab_required": False,
            "runtime_character_product_load_runtime_equivalent_required": True,
            "runtime_character_product_load_runtime_equivalent_surface_kind": "approved_character_spawnable",
            "runtime_character_product_load_verified": False,
            "runtime_character_product_load_claimed": False,
        }
    )
    if product_found:
        surface_payload["runtime_character_spawnable_surface_generation_required"] = False
        surface_payload["runtime_character_spawnable_surface_generation_blocker"] = ""
        surface_payload["runtime_character_spawnable_surface_remaining_blocker"] = "blocked_by_runtime_character_spawnable_load_not_attempted"
        surface_payload["runtime_character_product_load_contract_blocker"] = "blocked_by_runtime_character_spawnable_load_not_attempted"
    elif source_validated:
        surface_payload["runtime_character_spawnable_surface_generation_required"] = True
        surface_payload["runtime_character_spawnable_surface_generation_blocker"] = "blocked_by_missing_runtime_equivalent_spawnable_surface"
        surface_payload["runtime_character_spawnable_surface_remaining_blocker"] = "blocked_by_missing_runtime_equivalent_spawnable_surface"
        surface_payload["runtime_character_product_load_contract_blocker"] = "blocked_by_missing_runtime_equivalent_spawnable_surface"

    selected_asset_id = str(selected_product.get("asset_id", "")) if product_found else ""
    selected_asset_type = str(selected_product.get("asset_type", "")) if product_found else ""
    selected_builder = str(selected_product.get("builder", "")) if product_found else ""
    selected_path = str(selected_product.get("product_path", "")) if product_found else ""
    payload = {
        "runtime_character_prefab_source": {
            "status": status,
            "path": source_ref,
            "expected_spawnable_product": RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_PRODUCT,
            "apb_product_found": product_found,
        },
        "runtime_character_prefab_source_status": status,
        "runtime_character_prefab_source_path": source_ref,
        "runtime_character_prefab_source_kind": "reviewed_character_prefab_source",
        "runtime_character_prefab_source_owned_by_repo": bool(source_info["owned_by_repo"]),
        "runtime_character_prefab_source_committed": bool(source_info["exists"] and source_info["owned_by_repo"]),
        "runtime_character_prefab_source_is_defaultlevel": bool(source_info["is_defaultlevel"]),
        "runtime_character_prefab_source_is_production_level": bool(source_info["is_production_level"]),
        "runtime_character_prefab_source_is_temp": bool(source_info["is_temp"]),
        "runtime_character_prefab_source_is_generic_transform_only": bool(source_info["is_generic_transform_only"]),
        "runtime_character_prefab_source_is_character_specific": bool(source_info["is_character_specific"]),
        "runtime_character_prefab_source_is_approved": bool(source_info["is_approved"]),
        "runtime_character_prefab_source_generation_strategy": "repo_owned_reviewed_prefab_source_referencing_approved_release_procprefab",
        "runtime_character_prefab_source_generation_source_validation": source_validation_status,
        "runtime_character_prefab_source_generation_source_refs": source_refs,
        "runtime_character_prefab_source_manifest_refs": [
            "examples/o3de-golden-project/maxine-golden-project.fixture.json",
            "examples/manifests/release_rigged.pass.example.json",
        ],
        "runtime_character_prefab_source_approved_product_refs": list(source_info["approved_product_refs"]),
        "runtime_character_prefab_source_apb_expected_product": RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_PRODUCT,
        "runtime_character_prefab_source_apb_product_found": product_found,
        "runtime_character_prefab_source_apb_product_path": selected_path,
        "runtime_character_prefab_source_apb_product_asset_id": selected_asset_id,
        "runtime_character_prefab_source_apb_product_asset_type": selected_asset_type,
        "runtime_character_prefab_source_apb_product_builder": selected_builder,
        "runtime_character_prefab_source_apb_product_status": product_status if source_validated else status,
        "runtime_character_prefab_source_generation_completed": bool(source_validated),
        "runtime_character_prefab_source_generation_blocker": generation_blocker,
    }
    surface_payload.update(payload)
    return surface_payload


def _runtime_character_prefab_source_info(source_path: Path) -> Dict[str, Any]:
    relative = _repo_relative(source_path)
    normalized = relative.lower().replace("\\", "/")
    owned_by_repo = False
    try:
        source_path.resolve().relative_to(REPO_ROOT.resolve())
        owned_by_repo = True
    except Exception:
        owned_by_repo = False
    exists = source_path.is_file()
    approved_refs: List[str] = []
    instance_sources: List[str] = []
    has_transform = False
    if exists:
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        serialized = json.dumps(payload, sort_keys=True).lower() if isinstance(payload, Mapping) else ""
        has_transform = "transformcomponent" in serialized
        instances = payload.get("Instances", {}) if isinstance(payload, Mapping) else {}
        if isinstance(instances, Mapping):
            for instance in instances.values():
                if not isinstance(instance, Mapping):
                    continue
                source = str(instance.get("Source", "")).strip().replace("\\", "/")
                if not source:
                    continue
                instance_sources.append(source)
                if source.lower() == RUNTIME_CHARACTER_PREFAB_APPROVED_DEPENDENCY:
                    approved_refs.append(source)
    is_defaultlevel = "defaultlevel" in normalized
    is_production_level = normalized.startswith("levels/production/") or "/levels/production/" in normalized or "/assets/production/" in normalized
    is_temp = "_maxine_smoke" in normalized or "/temp/" in normalized
    is_character_specific = "characters/maxine" in normalized or any(
        "characters/maxine" in source.lower().replace("\\", "/") for source in instance_sources
    )
    is_generic_transform_only = has_transform and not approved_refs
    is_approved = (
        exists
        and owned_by_repo
        and not is_defaultlevel
        and not is_production_level
        and not is_temp
        and is_character_specific
        and not is_generic_transform_only
        and bool(approved_refs)
    )
    return {
        "exists": exists,
        "owned_by_repo": owned_by_repo,
        "is_defaultlevel": is_defaultlevel,
        "is_production_level": is_production_level,
        "is_temp": is_temp,
        "is_character_specific": is_character_specific,
        "is_generic_transform_only": is_generic_transform_only,
        "is_approved": is_approved,
        "approved_product_refs": approved_refs,
    }


def _runtime_character_prefab_source_expected_product(candidates: Any) -> Dict[str, Any]:
    if not isinstance(candidates, list):
        return {}
    expected_product = RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_PRODUCT.lower()
    expected_source = RUNTIME_CHARACTER_PREFAB_SOURCE_PROJECT_REF.lower()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        product_path = str(candidate.get("product_path", "")).strip().lower().replace("\\", "/")
        source_path = str(candidate.get("source_path", "")).strip().lower().replace("\\", "/")
        if product_path == expected_product or source_path == expected_source:
            return dict(candidate)
    return {}


def _runtime_character_prefab_source_engine_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return all(path.is_file() for path in _runtime_character_prefab_source_source_paths(root))


def _runtime_character_prefab_source_refs(engine_root: Path | None, source_path: Path) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [str(path) for path in _runtime_character_prefab_source_source_paths(root)] + [_repo_relative(source_path)]


def _runtime_character_prefab_source_source_paths(root: Path) -> List[Path]:
    return [
        root / "Gems" / "Prefab" / "PrefabBuilder" / "PrefabBuilderComponent.cpp",
        root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Spawnable" / "SpawnableUtils.cpp",
        root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Spawnable" / "PrefabProcessor.h",
        root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "Spawnable.h",
    ]


def _normalize_guid(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            return f"{{{str(UUID(bytes=value)).upper()}}}"
        except (TypeError, ValueError):
            return ""
    cleaned = str(value).strip().strip("{}")
    if not cleaned:
        return ""
    try:
        return f"{{{str(UUID(cleaned)).upper()}}}"
    except (TypeError, ValueError):
        return ""


def _runtime_character_product_load_source_payload(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    _ = artifact_dir
    source_validated = _runtime_character_product_load_source_validated(engine_root)
    products = _runtime_character_product_load_products_from_apb(product_evidence, project=project, engine_root=engine_root)
    required_products = _runtime_character_product_load_required_product_kinds(products, project=project)
    required_complete = _runtime_character_product_load_required_complete(
        products,
        product_evidence,
        required_products=required_products,
    )
    status = (
        "runtime_character_product_load_source_discovery_pass"
        if source_validated and required_complete
        else "blocked_by_missing_runtime_character_products"
        if not required_complete
        else "runtime_character_product_load_source_discovery_inconclusive"
    )
    selected = _runtime_character_product_load_selected_candidate(
        product_evidence=product_evidence,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
    )
    candidates = _runtime_character_product_load_candidate_matrix(
        product_evidence=product_evidence,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
    )
    source_refs = _runtime_character_product_load_source_refs(engine_root)
    approved_surface_present = any(
        str(product.get("product_kind", "")).strip() == RUNTIME_CHARACTER_PRODUCT_LOAD_APPROVED_SURFACE_KIND
        for product in products
        if isinstance(product, Mapping)
    )
    contract_blocker = "" if approved_surface_present else "blocked_by_missing_runtime_equivalent_spawnable_surface"
    return {
        "runtime_character_product_load": {
            "status": status,
            "selected": RUNTIME_CHARACTER_PRODUCT_LOAD_SELECTED if source_validated and required_complete else "",
            "product_count": len(products),
        },
        "runtime_character_product_load_status": status,
        "runtime_character_product_load_verified": False,
        "runtime_character_product_load_claimed": False,
        "runtime_character_product_load_probe_enabled": False,
        "runtime_character_product_load_probe_shipping_behavior": False,
        "runtime_character_product_load_source_refs": source_refs,
        "runtime_character_product_load_source_validation": {
            "status": "runtime_character_product_load_source_discovery_pass"
            if source_validated
            else "runtime_character_product_load_source_discovery_inconclusive",
            "summary": (
                "The runtime fixture can resolve product-relative catalog paths with "
                "AZ::Data::AssetCatalogRequestBus::GetAssetIdByPath/GetAssetInfoById, then request loads through "
                "AZ::Data::AssetManager::GetAsset using the catalog AssetInfo type and verify readiness with "
                "AZ::Data::Asset::IsReady/IsError or BlockUntilLoadComplete. APB evidence remains the source of the "
                "approved product list; the runtime probe is disabled unless its explicit Settings Registry gate is set."
            ),
        },
        "runtime_character_product_load_asset_catalog_api": "AZ::Data::AssetCatalogRequestBus::GetAssetIdByPath",
        "runtime_character_product_load_asset_manager_api": "AZ::Data::AssetManager::GetAsset",
        "runtime_character_product_load_candidate_matrix": candidates,
        "runtime_character_product_load_candidate_matrix_recorded": bool(candidates),
        "runtime_character_product_load_candidate_id": selected["id"] if source_validated and required_complete else "",
        "runtime_character_product_load_candidate_name": selected["name"] if source_validated and required_complete else "",
        "runtime_character_product_load_candidate_kind": selected["kind"] if source_validated and required_complete else "",
        "runtime_character_product_load_candidate_source_validation": selected["source_validation"]
        if source_validated and required_complete
        else {},
        "runtime_character_product_load_candidate_source_refs": selected["source_refs"]
        if source_validated and required_complete
        else [],
        "runtime_character_product_load_candidate_attempted": False,
        "runtime_character_product_load_candidate_result": selected["result"] if source_validated and required_complete else "",
        "runtime_character_product_load_candidate_blocker": "" if source_validated and required_complete else status,
        "runtime_character_product_load_selected_strategy": RUNTIME_CHARACTER_PRODUCT_LOAD_SELECTED
        if source_validated and required_complete
        else "",
        "runtime_character_product_load_selected_reason": (
            "resolve_catalog_paths_and_load_generic_assetdata_with_runtime_assetinfo_types"
            if source_validated and required_complete
            else ""
        ),
        "runtime_character_product_load_products": products,
        "runtime_character_product_load_required_products": list(required_products),
        "runtime_character_product_load_contract_updated": True,
        "runtime_character_product_load_direct_procprefab_required": False,
        "runtime_character_product_load_runtime_equivalent_required": True,
        "runtime_character_product_load_runtime_equivalent_surface_kind": "approved_character_spawnable",
        "runtime_character_product_load_contract_blocker": contract_blocker,
        "runtime_character_product_load_required_products_complete": required_complete,
        "runtime_character_product_load_missing_products": [
            product_type for product_type in required_products if product_type not in {item["product_kind"] for item in products}
        ],
        "runtime_character_product_load_timed_out_products": [],
        "runtime_character_product_load_failed_products": [],
        "runtime_character_product_load_informational_products": [],
        "runtime_character_product_load_all_required_ready": False,
        "runtime_character_product_load_timeout_seconds": int(timeout_seconds),
        "runtime_character_product_load_tick_budget": _runtime_character_product_load_timeout_ticks(timeout_seconds),
        "runtime_character_product_load_log_scan_summary": {"status": "runtime_execution_not_attempted"},
        "runtime_character_product_load_selected_product_log_scan": [],
        "runtime_character_product_load_selected_product_missing_error_scan": {
            "status": "runtime_execution_not_attempted",
            "matches": [],
        },
        "runtime_character_product_load_is_instantiation_proof": False,
        "runtime_runtime_character_product_load_is_instantiation_proof": False,
        "runtime_character_instantiation_claimed": False,
        "runtime_character_instantiation_verified": False,
        "runtime_character_animation_claimed": False,
        "runtime_character_animation_verified": False,
    }


def _runtime_character_product_load_products_from_apb(
    product_evidence: Mapping[str, Any],
    *,
    project: Path | None = None,
    engine_root: Path | None = None,
) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    seen: set[str] = set()
    approved_spawnable = (
        _runtime_character_product_load_approved_spawnable_product(
            product_evidence=product_evidence,
            project=project,
            engine_root=engine_root,
        )
        if project is not None
        else {}
    )
    use_updated_contract = project is not None
    required_normal_products = RUNTIME_CHARACTER_PRODUCT_LOAD_NORMAL_PRODUCTS if use_updated_contract else EXPECTED_PRODUCTS
    for product in product_evidence.get("produced_products", []):
        if not isinstance(product, Mapping):
            continue
        kind = str(product.get("product_type", "")).strip()
        if kind not in required_normal_products or kind in seen:
            continue
        product_path = str(product.get("product_path", product.get("path", ""))).strip().replace("\\", "/")
        if not product_path:
            continue
        seen.add(kind)
        asset_type_id = str(product.get("asset_type_id", product.get("assetTypeId", ""))).strip()
        asset_type_name = str(product.get("asset_type_name", "")).strip()
        if kind == "procprefab" and not asset_type_id:
            asset_type_id = RUNTIME_PROCPREFAB_ASSET_TYPE
        if kind == "procprefab" and not asset_type_name:
            asset_type_name = RUNTIME_PROCPREFAB_ASSET_CLASS
        products.append(
            {
                "product_kind": kind,
                "product_path": product_path,
                "catalog_path": _runtime_character_product_catalog_path(product_path),
                "expected_category": kind,
                "expected_type": _runtime_character_product_expected_type(kind),
                "asset_id": _runtime_product_asset_id(product),
                "asset_type_id": asset_type_id,
                "asset_type_name": asset_type_name,
                "resolution_status": "runtime_character_product_load_not_attempted",
                "load_requested": False,
                "load_method": "AZ::Data::AssetManager::GetAsset",
                "load_status": "runtime_character_product_load_not_attempted",
                "ready": False,
                "timeout": False,
                "error": "",
                "selected_product_log_errors": [],
                "release_status": "runtime_character_product_load_release_not_required",
            }
        )
    if approved_spawnable:
        products.append(approved_spawnable)
    order = list(_runtime_character_product_load_required_product_kinds(products, project=project))
    products.sort(key=lambda item: order.index(item["product_kind"]) if item["product_kind"] in order else len(order))
    return products


def _runtime_character_product_load_approved_spawnable_product(
    *,
    product_evidence: Mapping[str, Any],
    project: Path,
    engine_root: Path | None,
) -> Dict[str, Any]:
    candidates = _runtime_character_spawnable_surface_candidates(
        product_evidence=product_evidence,
        project=project,
        engine_root=engine_root,
    )
    approved = next((candidate for candidate in candidates if candidate.get("is_approved") is True), None)
    if not approved:
        return {}
    return {
        "product_kind": RUNTIME_CHARACTER_PRODUCT_LOAD_APPROVED_SURFACE_KIND,
        "product_path": str(approved.get("product_path", "")),
        "catalog_path": str(approved.get("catalog_path", "")),
        "expected_category": RUNTIME_CHARACTER_PRODUCT_LOAD_APPROVED_SURFACE_KIND,
        "expected_type": "AzFramework::Spawnable",
        "asset_id": str(approved.get("asset_id", "")),
        "asset_type_id": str(approved.get("asset_type", RUNTIME_SPAWNABLE_ASSET_TYPE)),
        "asset_type_name": "AzFramework::Spawnable",
        "resolution_status": "runtime_character_product_load_not_attempted",
        "load_requested": False,
        "load_method": "AZ::Data::AssetManager::GetAsset",
        "load_status": "runtime_character_product_load_not_attempted",
        "ready": False,
        "timeout": False,
        "error": "",
        "selected_product_log_errors": [],
        "release_status": "runtime_character_product_load_release_not_required",
    }


def _runtime_product_asset_id(product: Mapping[str, Any]) -> str:
    explicit = str(product.get("asset_id", product.get("assetId", ""))).strip()
    if explicit:
        return explicit
    source_uuid = str(product.get("source_uuid", product.get("source_guid", ""))).strip()
    source_sub_id = str(product.get("source_sub_id", product.get("sub_id", ""))).strip()
    if not source_uuid or not source_sub_id:
        return ""
    try:
        guid = UUID(source_uuid)
        sub_id = int(source_sub_id, 0)
    except (TypeError, ValueError):
        return ""
    return f"{{{str(guid).upper()}}}:{sub_id & 0xFFFFFFFF:08x}"


def _runtime_character_product_catalog_path(product_path: str) -> str:
    normalized = str(product_path).replace("\\", "/").strip()
    if normalized.lower().startswith("pc/"):
        return normalized[3:]
    return normalized


def _runtime_character_product_expected_type(kind: str) -> str:
    return {
        "azmodel": "AZ::RPI::ModelAsset",
        "actor": "EMotionFX::Integration::ActorAsset",
        "procprefab": "AssetCatalog AssetInfo type for .procprefab",
        "motion": "EMotionFX::Integration::MotionAsset",
        "motionset": "EMotionFX::Integration::MotionSetAsset",
        "animgraph": "EMotionFX::Integration::AnimGraphAsset",
        "pxmesh": "PhysX mesh asset catalog type",
        "azmaterial": "AZ::RPI::MaterialAsset",
        RUNTIME_CHARACTER_PRODUCT_LOAD_APPROVED_SURFACE_KIND: "AzFramework::Spawnable",
    }.get(kind, "AssetCatalog AssetInfo type")


def _runtime_character_product_load_regset_args(
    products: Sequence[Mapping[str, Any]],
    *,
    timeout_seconds: int,
) -> List[str]:
    if not products:
        return []
    args = [
        "--regset=/Amazon/MAXINE/RuntimeHarness/EnableCharacterProductLoadProbe=true",
        f"--regset=/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductCount={len(products)}",
        "--regset=/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductSpecsHex="
        + _runtime_character_product_load_product_specs_hex(products),
        f"--regset=/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/TimeoutTicks={_runtime_character_product_load_timeout_ticks(timeout_seconds)}",
        "--regset=/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/RequireAllProductsReady=true",
    ]
    return args


def _runtime_character_product_load_product_specs(products: Sequence[Mapping[str, Any]]) -> str:
    specs: List[str] = []
    for product in products:
        fields = [
            str(product.get("product_kind", "")),
            str(product.get("product_path", "")),
            str(product.get("catalog_path", "")),
            str(product.get("expected_category", "")),
        ]
        if any("|" in field or "," in field for field in fields):
            raise ValueError("runtime product-load probe product fields cannot contain '|' or ','")
        specs.append("|".join(fields))
    return ",".join(specs)


def _runtime_character_product_load_timeout_ticks(timeout_seconds: int) -> int:
    return max(1, int(timeout_seconds) * 20)


def _runtime_character_product_load_product_specs_hex(products: Sequence[Mapping[str, Any]]) -> str:
    return _runtime_character_product_load_product_specs(products).encode("utf-8").hex()


def _runtime_character_product_load_required_complete(
    products: Sequence[Mapping[str, Any]],
    product_evidence: Mapping[str, Any],
    *,
    required_products: Sequence[str] | None = None,
) -> bool:
    required = tuple(required_products or EXPECTED_PRODUCTS)
    kinds = {str(product.get("product_kind", "")).strip() for product in products if isinstance(product, Mapping)}
    return (
        all(kind in kinds for kind in required)
        and bool(product_evidence.get("product_evidence_complete", False))
        and not product_evidence.get("missing_products", [])
        and not product_evidence.get("pending_products", [])
        and not product_evidence.get("cache_heuristic_used", False)
    )


def _runtime_character_product_load_required_product_kinds(
    products: Sequence[Mapping[str, Any]],
    *,
    project: Path | None,
) -> Sequence[str]:
    if project is not None:
        return RUNTIME_CHARACTER_PRODUCT_LOAD_UPDATED_REQUIRED_PRODUCTS
    return EXPECTED_PRODUCTS


def _runtime_character_product_load_selected_candidate(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    timeout_seconds: int,
) -> Dict[str, Any]:
    source_validated = _runtime_character_product_load_source_validated(engine_root)
    required_complete = _runtime_character_product_load_required_complete(
        _runtime_character_product_load_products_from_apb(product_evidence),
        product_evidence,
    )
    return {
        "id": RUNTIME_CHARACTER_PRODUCT_LOAD_SELECTED,
        "name": "Runtime AssetCatalog resolution plus generic AssetManager load",
        "kind": "runtime_assetcatalog_resolution_generic_assetmanager_load",
        "source_validation": {
            "status": "runtime_character_product_load_candidate_source_validated"
            if source_validated and required_complete
            else "runtime_character_product_load_candidate_rejected_missing_source_validation",
            "summary": (
                "Resolve each APB-approved product catalog path through AssetCatalogRequestBus, read AssetInfo for the "
                "runtime asset type, then load with AssetManager::GetAsset using AssetLoadBehavior::Default and verify "
                "ready/error status within a bounded fixture tick budget."
            ),
        },
        "source_refs": _runtime_character_product_load_source_refs(engine_root),
        "required_products": list(EXPECTED_PRODUCTS),
        "timeout_seconds": int(timeout_seconds),
        "gate_env": list(RUNTIME_CHARACTER_PRODUCT_LOAD_GATE_ENV),
        "mutates_cache": False,
        "deletes_asset_cache": False,
        "mutates_project": False,
        "mutates_defaultlevel": False,
        "mutates_production_level": False,
        "loads_level": False,
        "result": "runtime_character_product_load_candidate_source_validated"
        if source_validated and required_complete
        else "runtime_character_product_load_candidate_rejected_missing_source_validation",
    }


def _runtime_character_product_load_candidate_matrix(
    *,
    product_evidence: Mapping[str, Any],
    engine_root: Path | None,
    timeout_seconds: int,
) -> List[Dict[str, Any]]:
    source_refs = _runtime_character_product_load_source_refs(engine_root)
    selected = _runtime_character_product_load_selected_candidate(
        product_evidence=product_evidence,
        engine_root=engine_root,
        timeout_seconds=timeout_seconds,
    )
    return [
        {
            "id": "runtime_character_product_load_source_api_discovery",
            "name": "Read-only runtime AssetCatalog/AssetManager API discovery",
            "kind": "read_only_source_discovery",
            "source_validation": {
                "status": "runtime_character_product_load_candidate_source_validated"
                if _runtime_character_product_load_source_validated(engine_root)
                else "runtime_character_product_load_candidate_rejected_missing_source_validation",
                "summary": "Records source refs for runtime AssetCatalog resolution and AssetManager load/ready APIs.",
            },
            "source_refs": source_refs,
            "attempted": False,
            "result": "runtime_character_product_load_source_discovery_pass"
            if _runtime_character_product_load_source_validated(engine_root)
            else "runtime_character_product_load_source_discovery_inconclusive",
            "blocker": "",
        },
        {
            "id": "runtime_character_product_load_assetcatalog_resolution_only",
            "name": "Runtime AssetCatalog resolution only",
            "kind": "runtime_assetcatalog_resolution_only",
            "source_validation": {
                "status": "runtime_character_product_load_candidate_source_validated",
                "summary": "Safe fallback that proves AssetId resolution but is intentionally not sufficient product-load evidence.",
            },
            "source_refs": source_refs,
            "attempted": False,
            "result": "runtime_character_product_load_candidate_rejected_resolution_only_not_load_proof",
            "blocker": "blocked_by_runtime_character_product_load_source_validation",
        },
        {
            **selected,
            "attempted": False,
            "blocker": "",
        },
        {
            "id": "runtime_character_product_load_type_specific_assetmanager_load",
            "name": "Type-specific AssetManager load for each character product class",
            "kind": "runtime_type_specific_assetmanager_load",
            "source_validation": {
                "status": "runtime_character_product_load_candidate_source_validated",
                "summary": (
                    "Several concrete product asset classes are source-visible, but the generic AssetInfo type path is "
                    "less brittle for mixed product categories and avoids hard-linking extra type headers into this fixture."
                ),
            },
            "source_refs": source_refs,
            "attempted": False,
            "result": "runtime_character_product_load_candidate_rejected_generic_assetinfo_preferred",
            "blocker": "",
        },
        {
            "id": "runtime_character_product_load_keep_blocked_without_source_validation",
            "name": "Keep runtime product-load proof blocked if source validation or APB evidence is incomplete",
            "kind": "typed_blocker",
            "source_validation": {
                "status": "runtime_character_product_load_candidate_source_validated",
                "summary": "Selected product-load proof remains blocked instead of inferred from APB evidence or fixture marker alone.",
            },
            "source_refs": source_refs,
            "attempted": False,
            "result": "blocked_by_runtime_character_product_load_source_validation",
            "blocker": "blocked_by_runtime_character_product_load_source_validation",
        },
    ]


def _runtime_character_product_load_source_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return all(
        path.is_file()
        for path in (
            root / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetManagerBus.h",
            root / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetManager.h",
            root / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetCommon.h",
        )
    )


def _runtime_character_product_load_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetManagerBus.h"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetManager.h"),
        str(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetCommon.h"),
        str(root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "ActorAsset.h"),
        str(root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionAsset.h"),
        str(root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionSetAsset.h"),
        str(root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "AnimGraphAsset.h"),
        str(root / "Gems" / "Atom" / "RPI" / "Code" / "Include" / "Atom" / "RPI.Reflect" / "Model" / "ModelAsset.h"),
        str(root / "Gems" / "Atom" / "RPI" / "Code" / "Include" / "Atom" / "RPI.Reflect" / "Material" / "MaterialAsset.h"),
        str(root / "Gems" / "PhysX" / "Core" / "Code" / "Include" / "PhysX" / "MeshAsset.h"),
        str(root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableAssetHandler.h"),
    ]


def _approved_motion_product_handler_signal_source_paths(engine_root: Path | None) -> List[Path]:
    root = engine_root or Path("")
    return [
        root / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetManager.cpp",
        root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "AssetCommon.h",
        root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionAsset.h",
        root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionAsset.cpp",
        root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "System" / "SystemComponent.cpp",
        root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "System" / "AnimationModule.cpp",
        root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Components" / "SimpleMotionComponent.h",
        root / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Components" / "SimpleMotionComponent.cpp",
    ]


def _approved_motion_product_handler_signal_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [str(path).replace("\\", "/") for path in _approved_motion_product_handler_signal_source_paths(root)]


def _approved_motion_product_handler_signal_source_validated(engine_root: Path | None) -> bool:
    return all(path.is_file() for path in _approved_motion_product_handler_signal_source_paths(engine_root))


def _approved_motion_product_handler_signal_candidate_matrix(
    *,
    source_validated: bool,
    signal_found: bool,
    classification_verified: bool,
    blocker: str,
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "classify_handler_unregistered_motion_signal_harmless_under_strict_fixture",
            "candidate": "classify handler-unregistered motion signal as harmless warning under strict after-APB runtime fixture",
            "kind": "runtime_motion_signal_classification",
            "attempted": bool(signal_found),
            "selected": bool(classification_verified),
            "result": (
                "approved_motion_product_handler_signal_classified_harmless"
                if classification_verified
                else "approved_motion_product_handler_signal_candidate_source_validated_waiting_for_runtime_signal"
                if source_validated and not signal_found
                else "approved_motion_product_handler_signal_candidate_blocked"
            ),
            "blocker": "" if classification_verified or (source_validated and not signal_found) else blocker,
        },
        {
            "id": "treat_signal_as_real_runtime_motion_asset_handler_blocker",
            "candidate": "treat signal as real runtime motion asset handler blocker",
            "kind": "runtime_motion_asset_handler_blocker",
            "attempted": bool(signal_found),
            "selected": bool(signal_found and not classification_verified),
            "result": (
                "approved_motion_product_handler_signal_candidate_selected_blocker"
                if signal_found and not classification_verified
                else "approved_motion_product_handler_signal_candidate_not_selected"
            ),
            "blocker": blocker if signal_found and not classification_verified else "",
        },
        {
            "id": "runtime_typeids_and_assignment_ids_only",
            "candidate": "runtime TypeIds plus runtime asset assignment IDs only",
            "kind": "insufficient_runtime_reference_evidence",
            "attempted": False,
            "selected": False,
            "result": "approved_motion_product_handler_signal_candidate_rejected_log_scan_unclassified",
            "blocker": "runtime_typeids_and_assignment_ids_are_insufficient_without_handler_signal_classification",
        },
        {
            "id": "product_load_only",
            "candidate": "product-load only",
            "kind": "insufficient_product_evidence",
            "attempted": False,
            "selected": False,
            "result": "approved_motion_product_handler_signal_candidate_rejected_runtime_wiring_requires_component_evidence",
            "blocker": "product_load_only_is_not_runtime_component_wiring_proof",
        },
        {
            "id": "animation_playback",
            "candidate": "animation playback",
            "kind": "runtime_animation_playback",
            "attempted": False,
            "selected": False,
            "result": "approved_motion_product_handler_signal_candidate_deferred",
            "blocker": "animation_playback_deferred_for_later_bounded_slice",
        },
        {
            "id": "defaultlevel_or_production_level_validation",
            "candidate": "defaultlevel or production-level validation",
            "kind": "unsafe_level_runtime_context",
            "attempted": False,
            "selected": False,
            "result": "approved_motion_product_handler_signal_candidate_rejected_unsafe_scope",
            "blocker": "defaultlevel_or_production_level_evidence_disallowed",
        },
    ]


def _approved_motion_product_handler_signal_base_payload(engine_root: Path | None) -> Dict[str, Any]:
    source_validated = _approved_motion_product_handler_signal_source_validated(engine_root)
    source_refs = _approved_motion_product_handler_signal_source_refs(engine_root)
    return {
        "approved_motion_product_handler_signal_diagnostic_attempted": True,
        "approved_motion_product_handler_signal_diagnostic_completed": True,
        "approved_motion_product_handler_signal_source_validation_status": (
            "approved_motion_product_handler_signal_source_validation_pass"
            if source_validated
            else "approved_motion_product_handler_signal_source_validation_inconclusive"
        ),
        "approved_motion_product_handler_signal_source_validation_verified": source_validated,
        "approved_motion_product_handler_signal_found": False,
        "approved_motion_product_handler_signal_asset_type": "",
        "approved_motion_product_handler_signal_asset_id": "",
        "approved_motion_product_handler_signal_classification": "",
        "approved_motion_product_handler_signal_classification_verified": False,
        "approved_motion_product_handler_signal_harmless_under_strict_fixture": False,
        "approved_motion_product_handler_signal_blocker": "",
        "approved_motion_product_handler_signal_source_files": source_refs,
        "approved_motion_product_handler_signal_candidate_matrix": _approved_motion_product_handler_signal_candidate_matrix(
            source_validated=source_validated,
            signal_found=False,
            classification_verified=False,
            blocker="",
        ),
        "approved_motion_product_handler_signal_selected_strategy": "",
        "approved_motion_product_handler_registered_in_runtime": False,
        "approved_motion_product_handler_expected_runtime_registration": source_validated,
        "approved_motion_product_handler_signal_log_lines": [],
        "approved_motion_product_handler_signal_classified_log_lines": [],
    }


def _approved_motion_product_handler_signal_has_unregistered_after_load_line(
    *,
    combined_text: str,
    asset_id: str,
    asset_type: str,
) -> bool:
    lowered = combined_text.lower()
    return (
        "asset handler for" in lowered
        and asset_type.lower() in lowered
        and asset_id.lower() in lowered
        and "is being removed" in lowered
        and "is still loaded" in lowered
    )


def _approved_motion_product_handler_signal_payload(
    *,
    products: Sequence[Mapping[str, Any]],
    selected_product_errors: Sequence[Mapping[str, str]],
    combined_text: str,
    engine_root: Path | None,
    motion_assignment_readback_verified: bool,
) -> Dict[str, Any]:
    payload = _approved_motion_product_handler_signal_base_payload(engine_root)
    handler_errors = [
        dict(error)
        for error in selected_product_errors
        if "no handler was registered" in str(error.get("line", "")).lower()
        and RUNTIME_EMOTIONFX_MOTION_ASSET_TYPE_ID.lower() in str(error.get("line", "")).lower()
    ]
    if not handler_errors:
        return payload

    selected_error = handler_errors[0]
    selected_kind = str(selected_error.get("product_kind", ""))
    motion_product = next(
        (
            product
            for product in products
            if isinstance(product, Mapping)
            and str(product.get("product_kind", "")) == selected_kind
            and selected_kind == "motion"
        ),
        {},
    )
    asset_id = str(motion_product.get("asset_id", "")).strip()
    asset_type = str(motion_product.get("asset_type_id", motion_product.get("asset_type", ""))).strip()
    signal_lines = [str(error.get("line", "")) for error in handler_errors if str(error.get("line", "")).strip()]
    payload.update(
        {
            "approved_motion_product_handler_signal_found": True,
            "approved_motion_product_handler_signal_asset_type": asset_type,
            "approved_motion_product_handler_signal_asset_id": asset_id,
            "approved_motion_product_handler_signal_log_lines": signal_lines,
            "approved_motion_product_handler_registered_in_runtime": motion_product.get("ready") is True
            and not str(motion_product.get("error", "")).strip(),
        }
    )

    source_validated = payload["approved_motion_product_handler_signal_source_validation_verified"] is True
    approved_asset = _runtime_asset_id_matches(asset_id, RUNTIME_CHARACTER_APPROVED_MOTION_ASSET_ID)
    approved_type = asset_type.lower() == RUNTIME_EMOTIONFX_MOTION_ASSET_TYPE_ID.lower()
    product_ready = motion_product.get("ready") is True
    product_released = (
        str(motion_product.get("release_status", "")).strip()
        == "runtime_character_product_load_product_released"
    )
    unregister_after_load = _approved_motion_product_handler_signal_has_unregistered_after_load_line(
        combined_text=combined_text,
        asset_id=asset_id,
        asset_type=asset_type,
    )
    harmless = bool(
        source_validated
        and approved_asset
        and approved_type
        and product_ready
        and product_released
        and unregister_after_load
        and motion_assignment_readback_verified
    )
    missing_readback_gate = bool(
        source_validated
        and approved_asset
        and approved_type
        and product_ready
        and product_released
        and unregister_after_load
        and not motion_assignment_readback_verified
    )
    blocker = (
        ""
        if harmless
        else APPROVED_MOTION_PRODUCT_HANDLER_SIGNAL_READBACK_BLOCKER
        if missing_readback_gate
        else APPROVED_MOTION_PRODUCT_HANDLER_SIGNAL_BLOCKER
    )
    payload.update(
        {
            "approved_motion_product_handler_signal_classification": (
                APPROVED_MOTION_PRODUCT_HANDLER_SIGNAL_CLASSIFICATION
                if harmless
                else "runtime_motion_product_handler_unregistered_blocking"
            ),
            "approved_motion_product_handler_signal_classification_verified": harmless,
            "approved_motion_product_handler_signal_harmless_under_strict_fixture": harmless,
            "approved_motion_product_handler_signal_blocker": blocker,
            "approved_motion_product_handler_signal_candidate_matrix": _approved_motion_product_handler_signal_candidate_matrix(
                source_validated=source_validated,
                signal_found=True,
                classification_verified=harmless,
                blocker=blocker,
            ),
            "approved_motion_product_handler_signal_selected_strategy": (
                "classify_handler_unregistered_motion_signal_harmless_under_strict_fixture"
                if harmless
                else "wait_for_runtime_motion_assignment_readback_before_handler_signal_classification"
                if missing_readback_gate
                else "treat_signal_as_real_runtime_motion_asset_handler_blocker"
            ),
            "approved_motion_product_handler_signal_classified_log_lines": signal_lines if harmless else [],
        }
    )
    return payload


def _runtime_motion_assignment_readback_verified_from_combined_text(combined_text: str) -> bool:
    spawn_markers = _runtime_character_spawn_instantiation_parse_markers(combined_text)
    inventory = _runtime_character_animation_component_inventory(spawn_markers.get("component_inventory", []))
    assignment_ids = _runtime_character_animation_component_wiring_runtime_assignment_ids(inventory)
    return _runtime_asset_id_matches(
        assignment_ids.get("motion_asset_id", ""),
        RUNTIME_CHARACTER_APPROVED_MOTION_ASSET_ID,
    )


def _runtime_shutdown_poolallocator_signal_source_paths(engine_root: Path | None) -> List[Path]:
    root = engine_root or Path("")
    return [
        root / "Code" / "Framework" / "AzCore" / "AzCore" / "Memory" / "PoolAllocator.cpp",
        root / "Code" / "Framework" / "AzCore" / "AzCore" / "Memory" / "PoolAllocator.h",
        REPO_ROOT
        / "o3de"
        / "gems"
        / "MaxineRuntimeExitFixture"
        / "Code"
        / "Source"
        / "Clients"
        / "MaxineRuntimeExitFixtureSystemComponent.cpp",
    ]


def _runtime_shutdown_poolallocator_signal_source_refs(engine_root: Path | None) -> List[str]:
    return [str(path).replace("\\", "/") for path in _runtime_shutdown_poolallocator_signal_source_paths(engine_root)]


def _runtime_shutdown_poolallocator_signal_source_validated(engine_root: Path | None) -> bool:
    paths = _runtime_shutdown_poolallocator_signal_source_paths(engine_root)
    if not all(path.is_file() for path in paths):
        return False
    try:
        pool_text = paths[0].read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    required_tokens = (
        "PoolAllocation<Allocator>::~PoolAllocation()",
        "AZ_Assert(bucket.m_pages.empty()",
        "Found page for bucket %p",
        "GarbageCollect();",
    )
    return all(token in pool_text for token in required_tokens)


def _runtime_shutdown_poolallocator_signal_lines(combined_text: str) -> List[str]:
    matches: List[str] = []
    for line in combined_text.splitlines():
        normalized = " ".join(line.strip().split())
        lowered = normalized.lower()
        if (
            "poolallocator.cpp" in lowered
            and ("poolallocator.cpp(470)" in lowered or "poolallocator.cpp:470" in lowered)
            and "found page for bucket" in lowered
        ):
            matches.append(normalized[:240])
        if len(matches) >= 8:
            break
    return matches


def _runtime_shutdown_poolallocator_signal_after_marker(
    combined_text: str,
    signal_line: str,
    marker: str,
) -> bool:
    if not signal_line:
        return False
    lowered = combined_text.lower()
    signal_index = lowered.find(signal_line.lower())
    marker_index = lowered.rfind(marker.lower())
    return signal_index >= 0 and marker_index >= 0 and signal_index > marker_index


def _runtime_shutdown_poolallocator_signal_candidate_matrix(
    *,
    source_validated: bool,
    signal_found: bool,
    classification_verified: bool,
    blocker: str,
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "classify_poolallocator_470_harmless_under_strict_fixture",
            "candidate": "classify PoolAllocator.cpp:470 as harmless shutdown assertion under strict after-APB runtime fixture",
            "kind": "runtime_shutdown_signal_classification",
            "attempted": bool(signal_found),
            "selected": False,
            "result": "runtime_shutdown_poolallocator_candidate_rejected_real_assertion",
            "blocker": "PoolAllocation teardown asserts bucket pages are empty; matching line-470 signals are not harmless.",
        },
        {
            "id": "treat_poolallocator_470_as_real_runtime_cleanup_blocker",
            "candidate": "treat PoolAllocator.cpp:470 as real runtime cleanup/memory blocker",
            "kind": "runtime_shutdown_memory_blocker",
            "attempted": bool(signal_found),
            "selected": bool(classification_verified),
            "result": (
                "runtime_shutdown_poolallocator_candidate_selected_real_blocker"
                if classification_verified
                else "runtime_shutdown_poolallocator_candidate_waiting_for_runtime_signal"
                if source_validated and not signal_found
                else "runtime_shutdown_poolallocator_candidate_blocked_source_validation"
            ),
            "blocker": blocker if signal_found else "",
        },
        {
            "id": "runtime_typeids_and_assignment_ids_only",
            "candidate": "runtime TypeIds plus runtime asset assignment IDs only",
            "kind": "insufficient_runtime_reference_evidence",
            "attempted": False,
            "selected": False,
            "result": "runtime_shutdown_poolallocator_candidate_rejected_selected_log_scan_unclassified",
            "blocker": "runtime_typeids_and_assignment_ids_are_insufficient_without_selected_log_scan_classification",
        },
        {
            "id": "product_load_only",
            "candidate": "product-load only",
            "kind": "insufficient_product_evidence",
            "attempted": False,
            "selected": False,
            "result": "runtime_shutdown_poolallocator_candidate_rejected_runtime_wiring_requires_component_evidence",
            "blocker": "product_load_only_is_not_runtime_component_wiring_proof",
        },
        {
            "id": "animation_playback",
            "candidate": "animation playback",
            "kind": "runtime_animation_playback",
            "attempted": False,
            "selected": False,
            "result": "runtime_shutdown_poolallocator_candidate_deferred",
            "blocker": "animation_playback_deferred_for_later_bounded_slice",
        },
        {
            "id": "defaultlevel_or_production_level_validation",
            "candidate": "defaultlevel or production-level validation",
            "kind": "unsafe_level_runtime_context",
            "attempted": False,
            "selected": False,
            "result": "runtime_shutdown_poolallocator_candidate_rejected_unsafe_scope",
            "blocker": "defaultlevel_or_production_level_evidence_disallowed",
        },
    ]


def _runtime_shutdown_poolallocator_signal_payload(
    combined_text: str,
    engine_root: Path | None,
) -> Dict[str, Any]:
    source_validated = _runtime_shutdown_poolallocator_signal_source_validated(engine_root)
    source_refs = _runtime_shutdown_poolallocator_signal_source_refs(engine_root)
    signal_lines = _runtime_shutdown_poolallocator_signal_lines(combined_text)
    signal_found = bool(signal_lines)
    first_line = signal_lines[0] if signal_lines else ""
    classification_verified = bool(source_validated and signal_found)
    blocker = RUNTIME_SHUTDOWN_POOLALLOCATOR_SIGNAL_BLOCKER if classification_verified else ""
    return {
        "runtime_shutdown_poolallocator_signal_diagnostic_attempted": True,
        "runtime_shutdown_poolallocator_signal_diagnostic_completed": True,
        "runtime_shutdown_poolallocator_signal_source_validation_status": (
            "runtime_shutdown_poolallocator_signal_source_validation_pass"
            if source_validated
            else "runtime_shutdown_poolallocator_signal_source_validation_inconclusive"
        ),
        "runtime_shutdown_poolallocator_signal_source_validation_verified": source_validated,
        "runtime_shutdown_poolallocator_signal_found": signal_found,
        "runtime_shutdown_poolallocator_signal_line": first_line,
        "runtime_shutdown_poolallocator_signal_classification": (
            RUNTIME_SHUTDOWN_POOLALLOCATOR_SIGNAL_CLASSIFICATION
            if classification_verified
            else "runtime_shutdown_poolallocator_signal_not_observed"
            if source_validated and not signal_found
            else "runtime_shutdown_poolallocator_signal_source_validation_inconclusive"
        ),
        "runtime_shutdown_poolallocator_signal_classification_verified": classification_verified,
        "runtime_shutdown_poolallocator_signal_harmless_under_strict_fixture": False,
        "runtime_shutdown_poolallocator_signal_blocker": blocker,
        "runtime_shutdown_poolallocator_signal_source_files": source_refs,
        "runtime_shutdown_poolallocator_signal_candidate_matrix": _runtime_shutdown_poolallocator_signal_candidate_matrix(
            source_validated=source_validated,
            signal_found=signal_found,
            classification_verified=classification_verified,
            blocker=blocker,
        ),
        "runtime_shutdown_poolallocator_signal_after_fixture_marker": _runtime_shutdown_poolallocator_signal_after_marker(
            combined_text,
            first_line,
            "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT",
        ),
        "runtime_shutdown_poolallocator_signal_after_cleanup": _runtime_shutdown_poolallocator_signal_after_marker(
            combined_text,
            first_line,
            "MAXINE_RUNTIME_CHARACTER_SPAWN_CLEANUP",
        ),
        "runtime_shutdown_poolallocator_signal_invalidates_wiring": classification_verified,
        "runtime_shutdown_poolallocator_signal_invalidates_playback": classification_verified,
        "runtime_selected_log_scan_blocking_matches": signal_lines if classification_verified else [],
        "runtime_selected_log_scan_classified_harmless_matches": [],
    }


def _runtime_character_product_load_execution_payload(
    *,
    product_evidence: Mapping[str, Any],
    command: Mapping[str, Any],
    project: Path | None,
    combined_text: str,
    actual_level_loads: Sequence[str],
    launch_hygiene: Mapping[str, Any],
    signal_classification: Mapping[str, Any],
    cache_bootstrap: Mapping[str, Any],
    exit_code: int | None,
    marker_observed: bool,
) -> Dict[str, Any]:
    engine_root = _runtime_engine_root_from_command(command)
    products = _runtime_character_product_load_products_from_apb(product_evidence, project=project, engine_root=engine_root)
    required_products = tuple(_runtime_character_product_load_required_product_kinds(products, project=project))
    source_payload = _runtime_character_product_load_source_payload(
        product_evidence=product_evidence,
        engine_root=engine_root,
        project=project,
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        artifact_dir=DEFAULT_ARTIFACT_ROOT,
    )
    marker_products, marker_summary, markers_observed = _runtime_character_product_load_parse_markers(
        products=products,
        combined_text=combined_text,
    )
    selected_product_errors = _runtime_character_product_selected_product_errors(marker_products, combined_text)
    motion_assignment_readback_verified = _runtime_motion_assignment_readback_verified_from_combined_text(combined_text)
    motion_handler_signal = _approved_motion_product_handler_signal_payload(
        products=marker_products,
        selected_product_errors=selected_product_errors,
        combined_text=combined_text,
        engine_root=engine_root,
        motion_assignment_readback_verified=motion_assignment_readback_verified,
    )
    classified_lines = {
        str(line)
        for line in motion_handler_signal.get("approved_motion_product_handler_signal_classified_log_lines", [])
    }
    blocking_selected_product_errors = [
        item for item in selected_product_errors if str(item.get("line", "")) not in classified_lines
    ]
    classified_selected_product_errors = [
        item for item in selected_product_errors if str(item.get("line", "")) in classified_lines
    ]
    for product in marker_products:
        product_errors = [
            item for item in selected_product_errors if item.get("product_kind") == product.get("product_kind")
        ]
        product["selected_product_log_errors_raw"] = product_errors
        product["selected_product_log_errors_classified"] = [
            item for item in product_errors if str(item.get("line", "")) in classified_lines
        ]
        product["selected_product_log_errors"] = [
            item for item in product_errors if str(item.get("line", "")) not in classified_lines
        ]
        if product["selected_product_log_errors"] and not product.get("error"):
            product["error"] = "selected_product_log_error"
            product["load_status"] = "runtime_character_product_load_product_error"

    ready_kinds = [str(product.get("product_kind", "")) for product in marker_products if product.get("ready") is True]
    missing_kinds = [
        str(product.get("product_kind", ""))
        for product in marker_products
        if str(product.get("resolution_status", "")).strip() in {"runtime_character_product_load_product_missing", "runtime_character_product_load_not_attempted"}
    ]
    timed_out_kinds = [str(product.get("product_kind", "")) for product in marker_products if product.get("timeout") is True]
    failed_kinds = [
        str(product.get("product_kind", ""))
        for product in marker_products
        if str(product.get("load_status", "")).strip() == "runtime_character_product_load_product_error"
        or bool(product.get("selected_product_log_errors"))
    ]
    required_complete = _runtime_character_product_load_required_complete(
        marker_products,
        product_evidence,
        required_products=required_products,
    )
    all_required_ready = (
        required_complete
        and set(ready_kinds) == set(required_products)
        and not missing_kinds
        and not timed_out_kinds
        and not failed_kinds
    )
    launch_pass = str(launch_hygiene.get("runtime_launch_hygiene_status", "")).strip() == "runtime_launch_hygiene_pass"
    signal_pass = signal_classification.get("runtime_signal_classification_verified") is True
    cache_pass = cache_bootstrap.get("runtime_cache_bootstrap_verified") is True
    default_level_detected = bool(launch_hygiene.get("runtime_default_level_autoload_detected"))
    production_level_loaded = bool(actual_level_loads)
    exit_clean = exit_code == 0
    summary_pass = str(marker_summary.get("status", "")).strip() == "pass"
    spawnable_product = next(
        (
            product
            for product in marker_products
            if str(product.get("product_kind", "")).strip() == RUNTIME_CHARACTER_PRODUCT_LOAD_APPROVED_SURFACE_KIND
        ),
        {},
    )
    spawnable_required = RUNTIME_CHARACTER_PRODUCT_LOAD_APPROVED_SURFACE_KIND in set(required_products)
    spawnable_ready = bool(spawnable_product) and spawnable_product.get("ready") is True and not spawnable_product.get("error")
    verified = (
        markers_observed
        and summary_pass
        and all_required_ready
        and (spawnable_ready if spawnable_required else True)
        and launch_pass
        and signal_pass
        and cache_pass
        and not default_level_detected
        and not production_level_loaded
        and exit_clean
        and marker_observed
    )
    blocker = ""
    if default_level_detected:
        blocker = "blocked_by_default_level_autoload"
    elif production_level_loaded:
        blocker = "blocked_by_production_level_load"
    elif not signal_pass:
        blocker = "blocked_by_unclassified_runtime_product_load_signal"
    elif not cache_pass:
        blocker = "blocked_by_cache_bootstrap_restore_failed"
    elif missing_kinds:
        blocker = "blocked_by_missing_runtime_character_products"
    elif timed_out_kinds:
        blocker = "blocked_by_runtime_character_product_load_timeout"
    elif failed_kinds or blocking_selected_product_errors:
        blocker = "blocked_by_runtime_character_product_load_error"
    elif spawnable_required and not spawnable_ready:
        blocker = "blocked_by_runtime_character_spawnable_load_error"
    elif not markers_observed:
        blocker = "blocked_by_runtime_character_product_load_error"

    status = (
        "runtime_character_product_load_verified_all_required_products_ready"
        if verified
        else "runtime_character_product_load_candidate_attempted_failed_timeout"
        if timed_out_kinds
        else "runtime_character_product_load_candidate_attempted_failed_missing_product"
        if missing_kinds
        else "runtime_character_product_load_candidate_attempted_failed_load_error"
    )
    selected = _runtime_character_product_load_selected_candidate(
        product_evidence=product_evidence,
        engine_root=engine_root,
        timeout_seconds=int(command.get("timeout_seconds", 120)),
    )
    source_payload.update(
        {
            "runtime_character_product_load": {
                "status": status,
                "selected": RUNTIME_CHARACTER_PRODUCT_LOAD_SELECTED,
                "attempted": True,
                "summary": marker_summary,
            },
            "runtime_character_product_load_status": status,
            "runtime_character_product_load_verified": bool(verified),
            "runtime_character_product_load_claimed": bool(verified),
            "runtime_character_product_load_probe_enabled": True,
            "runtime_character_product_load_probe_shipping_behavior": False,
            "runtime_character_product_load_candidate_id": selected["id"],
            "runtime_character_product_load_candidate_name": selected["name"],
            "runtime_character_product_load_candidate_kind": selected["kind"],
            "runtime_character_product_load_candidate_source_validation": selected["source_validation"],
            "runtime_character_product_load_candidate_source_refs": selected["source_refs"],
            "runtime_character_product_load_candidate_attempted": True,
            "runtime_character_product_load_candidate_result": "runtime_character_product_load_candidate_attempted_pass"
            if verified
            else status,
            "runtime_character_product_load_candidate_blocker": blocker,
            "runtime_character_product_load_contract_blocker": "" if verified else blocker,
            "runtime_character_product_load_selected_strategy": RUNTIME_CHARACTER_PRODUCT_LOAD_SELECTED,
            "runtime_character_product_load_selected_reason": "runtime_fixture_resolved_and_loaded_apb_approved_character_products",
            "runtime_character_product_load_products": marker_products,
            "runtime_character_product_load_required_products_complete": required_complete,
            "runtime_character_product_load_required_products": list(required_products),
            "runtime_character_product_load_missing_products": missing_kinds,
            "runtime_character_product_load_timed_out_products": timed_out_kinds,
            "runtime_character_product_load_failed_products": failed_kinds,
            "runtime_character_product_load_informational_products": [],
            "runtime_character_product_load_all_required_ready": bool(all_required_ready),
            "runtime_character_product_load_timeout_seconds": int(command.get("timeout_seconds", 120)),
            "runtime_character_product_load_tick_budget": _runtime_character_product_load_timeout_ticks(
                int(command.get("timeout_seconds", 120))
            ),
            "runtime_character_product_load_markers_observed": bool(markers_observed),
            "runtime_character_product_load_marker_summary": marker_summary,
            "runtime_character_product_load_log_scan_summary": {
                "status": "fail" if blocking_selected_product_errors else "pass",
                "match_count": len(blocking_selected_product_errors),
                "classified_match_count": len(classified_selected_product_errors),
            },
            "runtime_character_product_load_selected_product_log_scan": blocking_selected_product_errors,
            "runtime_character_product_load_selected_product_log_scan_raw": selected_product_errors,
            "runtime_character_product_load_selected_product_log_scan_classified": classified_selected_product_errors,
            "runtime_character_product_load_selected_product_missing_error_scan": {
                "status": "fail" if blocking_selected_product_errors else "pass",
                "matches": blocking_selected_product_errors,
            },
            **motion_handler_signal,
            "runtime_character_product_load_is_instantiation_proof": False,
            "runtime_runtime_character_product_load_is_instantiation_proof": False,
            "runtime_procprefab_runtime_equivalent_surface_claimed": bool(verified and spawnable_required),
            "runtime_procprefab_runtime_equivalent_surface_verified": bool(verified and spawnable_required),
            "runtime_character_spawnable_surface_found": bool(spawnable_product),
            "runtime_character_spawnable_surface_claimed": bool(verified and spawnable_required),
            "runtime_character_spawnable_surface_verified": bool(verified and spawnable_required),
            "runtime_character_spawnable_surface_selected": str(spawnable_product.get("product_path", "")),
            "runtime_character_spawnable_surface_selected_reason": (
                "approved_character_spawnable_loaded_ready_in_product_load_fixture" if verified and spawnable_required else ""
            ),
            "runtime_character_spawnable_surface_load_status": str(
                spawnable_product.get("load_status", "runtime_character_spawnable_surface_load_not_attempted")
            ),
            "runtime_character_spawnable_surface_load_ready": bool(spawnable_ready),
            "runtime_character_spawnable_surface_load_timeout": bool(spawnable_product.get("timeout", False)),
            "runtime_character_spawnable_surface_log_errors": list(spawnable_product.get("selected_product_log_errors", [])),
            "runtime_character_spawnable_surface_remaining_blocker": "" if verified else blocker,
            "runtime_character_instantiation_claimed": False,
            "runtime_character_instantiation_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    )
    return source_payload


def _runtime_character_spawn_instantiation_execution_payload(
    *,
    product_evidence: Mapping[str, Any],
    command: Mapping[str, Any],
    project: Path | None,
    combined_text: str,
    actual_level_loads: Sequence[str],
    launch_hygiene: Mapping[str, Any],
    signal_classification: Mapping[str, Any],
    cache_bootstrap: Mapping[str, Any],
    product_load: Mapping[str, Any],
    exit_code: int | None,
    marker_observed: bool,
) -> Dict[str, Any]:
    engine_root = _runtime_engine_root_from_command(command)
    source_payload = _runtime_character_spawn_instantiation_source_payload(
        product_evidence=product_evidence,
        engine_root=engine_root,
        project=project,
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        artifact_dir=DEFAULT_ARTIFACT_ROOT,
    )
    markers = _runtime_character_spawn_instantiation_parse_markers(combined_text)
    approved = _runtime_character_spawn_instantiation_approved_spawnable(
        product_evidence=product_evidence,
        project=project,
        engine_root=engine_root,
    )
    selected_product = {
        "product_kind": RUNTIME_CHARACTER_PRODUCT_LOAD_APPROVED_SURFACE_KIND,
        "product_path": str(approved.get("product_path", RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_PRODUCT)),
        "catalog_path": str(approved.get("catalog_path", RUNTIME_CHARACTER_PREFAB_EXPECTED_SPAWNABLE_CATALOG)),
        "asset_id": str(approved.get("asset_id", "")),
    }
    selected_surface_errors = _runtime_character_product_selected_product_errors([selected_product], combined_text)
    marker_errors = list(markers.get("errors", []))
    log_errors = selected_surface_errors + marker_errors
    summary = markers.get("summary", {}) if isinstance(markers.get("summary", {}), Mapping) else {}
    product_load_ready = bool(product_load.get("runtime_character_product_load_verified"))
    spawnable_ready = bool(product_load.get("runtime_character_spawnable_surface_verified")) and bool(
        product_load.get("runtime_character_spawnable_surface_load_ready")
    )
    source_validated = (
        str(source_payload.get("runtime_character_spawn_instantiation_source_validation", "")).strip()
        == "runtime_character_spawn_source_discovery_pass"
    )
    launch_pass = str(launch_hygiene.get("runtime_launch_hygiene_status", "")).strip() == "runtime_launch_hygiene_pass"
    signal_pass = signal_classification.get("runtime_signal_classification_verified") is True
    cache_pass = cache_bootstrap.get("runtime_cache_bootstrap_verified") is True
    default_level_detected = bool(launch_hygiene.get("runtime_default_level_autoload_detected"))
    production_level_loaded = bool(actual_level_loads)
    exit_clean = exit_code == 0
    request_issued = bool(markers.get("request_issued"))
    completion_observed = bool(markers.get("completion_observed"))
    entity_count = int(markers.get("entity_count", 0) or 0)
    timed_out = bool(markers.get("timed_out")) or str(summary.get("timed_out", "")).strip() in {"1", "true", "True"}
    cleanup_status = str(markers.get("cleanup_status", "")).strip()
    cleanup_ok = cleanup_status in {"runtime_character_spawn_instantiation_cleanup_complete", "runtime_character_spawn_instantiation_cleanup_not_required"}
    summary_pass = str(summary.get("status", "")).strip() == "pass"
    verified = (
        bool(markers.get("markers_observed"))
        and summary_pass
        and product_load_ready
        and spawnable_ready
        and source_validated
        and launch_pass
        and signal_pass
        and cache_pass
        and not default_level_detected
        and not production_level_loaded
        and exit_clean
        and marker_observed
        and request_issued
        and completion_observed
        and entity_count > 0
        and not timed_out
        and not log_errors
        and cleanup_ok
    )
    blocker = ""
    if default_level_detected:
        blocker = "blocked_by_default_level_autoload"
    elif production_level_loaded:
        blocker = "blocked_by_production_level_load"
    elif not product_load_ready or not spawnable_ready:
        blocker = "blocked_by_runtime_character_spawnable_load_error"
    elif not signal_pass:
        blocker = "blocked_by_unclassified_runtime_product_load_signal"
    elif not cache_pass:
        blocker = "blocked_by_cache_bootstrap_restore_failed"
    elif not source_validated:
        blocker = "blocked_by_runtime_character_spawn_source_validation"
    elif timed_out:
        blocker = "blocked_by_runtime_character_spawn_timeout"
    elif log_errors:
        blocker = "blocked_by_runtime_character_spawn_error"
    elif not request_issued or not completion_observed:
        blocker = "blocked_by_runtime_character_spawn_error"
    elif entity_count <= 0:
        blocker = "blocked_by_runtime_character_spawn_no_entities"
    elif not cleanup_ok:
        blocker = "blocked_by_runtime_character_spawn_cleanup_failed"
    elif not markers.get("markers_observed"):
        blocker = "blocked_by_runtime_character_spawn_error"

    if verified:
        status = "runtime_character_spawn_instantiation_verified"
        candidate_result = "runtime_character_spawn_candidate_attempted_pass"
    elif timed_out:
        status = "runtime_character_spawn_candidate_attempted_failed_timeout"
        candidate_result = status
    elif default_level_detected:
        status = "runtime_character_spawn_candidate_attempted_failed_defaultlevel_autoload"
        candidate_result = status
    elif production_level_loaded:
        status = "runtime_character_spawn_candidate_attempted_failed_production_level_load"
        candidate_result = status
    elif entity_count <= 0 and completion_observed:
        status = "runtime_character_spawn_candidate_attempted_failed_no_spawned_entities"
        candidate_result = status
    else:
        status = "runtime_character_spawn_candidate_attempted_failed_spawn_error"
        candidate_result = status

    candidate = _runtime_character_spawn_instantiation_selected_candidate(
        source_validated=source_validated,
        source_refs=source_payload.get("runtime_character_spawn_instantiation_source_refs", []),
        context_refs=source_payload.get("runtime_character_spawn_instantiation_context_source_refs", []),
        approved=approved,
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        attempted=True,
    )
    candidate.update(
        {
            "attempted": True,
            "result": candidate_result,
            "blocker": blocker,
            "actual_level_loads": list(actual_level_loads),
            "spawn_request_issued": request_issued,
            "spawn_completion_observed": completion_observed,
            "spawned_entity_count": entity_count,
            "cleanup_status": cleanup_status,
            "exit_code_decimal": exit_code,
            "exit_code_hex": _exit_code_hex(exit_code),
            "fixture_marker_observed": marker_observed,
        }
    )
    source_payload.update(
        {
            "runtime_character_spawn_instantiation": {
                "status": status,
                "selected": RUNTIME_CHARACTER_SPAWN_INSTANTIATION_SELECTED,
                "attempted": True,
                "summary": dict(summary),
            },
            "runtime_character_spawn_instantiation_status": status,
            "runtime_character_spawn_instantiation_claimed": bool(verified),
            "runtime_character_spawn_instantiation_verified": bool(verified),
            "runtime_character_spawn_instantiation_probe_enabled": True,
            "runtime_character_spawn_instantiation_probe_shipping_behavior": False,
            "runtime_character_spawn_instantiation_candidate_matrix": [
                *source_payload.get("runtime_character_spawn_instantiation_candidate_matrix", []),
                candidate,
            ],
            "runtime_character_spawn_instantiation_candidate_matrix_recorded": True,
            "runtime_character_spawn_instantiation_candidate_id": candidate["id"],
            "runtime_character_spawn_instantiation_candidate_name": candidate["name"],
            "runtime_character_spawn_instantiation_candidate_kind": candidate["kind"],
            "runtime_character_spawn_instantiation_candidate_source_validation": candidate["source_validation"],
            "runtime_character_spawn_instantiation_candidate_source_refs": candidate["source_refs"],
            "runtime_character_spawn_instantiation_candidate_attempted": True,
            "runtime_character_spawn_instantiation_candidate_result": candidate_result,
            "runtime_character_spawn_instantiation_candidate_blocker": blocker,
            "runtime_character_spawn_instantiation_selected_strategy": RUNTIME_CHARACTER_SPAWN_INSTANTIATION_SELECTED,
            "runtime_character_spawn_instantiation_selected_reason": "runtime_fixture_loaded_approved_spawnable_and_spawned_entities"
            if verified
            else "runtime_fixture_spawn_attempt_recorded_with_typed_blocker",
            "runtime_character_spawn_instantiation_context_status": str(
                markers.get("context_status", source_payload.get("runtime_character_spawn_instantiation_context_status", ""))
            ),
            "runtime_character_spawn_instantiation_context_id": str(markers.get("context_id", "")),
            "runtime_character_spawn_instantiation_spawnable_product_path": str(
                markers.get("product_path", selected_product["product_path"])
            ),
            "runtime_character_spawn_instantiation_spawnable_catalog_path": str(
                markers.get("catalog_path", selected_product["catalog_path"])
            ),
            "runtime_character_spawn_instantiation_spawnable_asset_id": str(
                markers.get("asset_id", selected_product["asset_id"])
            ),
            "runtime_character_spawn_instantiation_spawnable_asset_type": str(
                markers.get("asset_type", approved.get("asset_type", RUNTIME_SPAWNABLE_ASSET_TYPE))
            ),
            "runtime_character_spawn_instantiation_spawnable_loaded_ready": bool(spawnable_ready),
            "runtime_character_spawn_instantiation_spawn_request_issued": request_issued,
            "runtime_character_spawn_instantiation_spawn_ticket": str(markers.get("ticket", "")),
            "runtime_character_spawn_instantiation_spawn_completion_observed": completion_observed,
            "runtime_character_spawn_instantiation_spawn_result": str(
                markers.get("spawn_result", summary.get("status", ""))
            ),
            "runtime_character_spawn_instantiation_spawned_entity_count": entity_count,
            "runtime_character_spawn_instantiation_spawned_entity_ids": list(markers.get("entity_ids", [])),
            "runtime_character_spawn_instantiation_spawned_entity_names": list(markers.get("entity_names", [])),
            "runtime_character_spawn_instantiation_spawned_entity_component_inventory": list(
                markers.get("component_inventory", [])
            ),
            "runtime_character_spawn_instantiation_root_entity_count": entity_count,
            "runtime_character_spawn_instantiation_container_entity": str(markers.get("container_entity", "")),
            "runtime_character_spawn_instantiation_timeout": timed_out,
            "runtime_character_spawn_instantiation_timeout_ticks": int(
                markers.get(
                    "timeout_ticks",
                    _runtime_character_product_load_timeout_ticks(int(command.get("timeout_seconds", 120))),
                )
                or 0
            ),
            "runtime_character_spawn_instantiation_log_errors": log_errors,
            "runtime_character_spawn_instantiation_selected_surface_log_scan": {
                "status": "fail" if log_errors else "pass",
                "matches": log_errors,
            },
            "runtime_character_spawn_instantiation_cleanup_attempted": bool(markers.get("cleanup_attempted")),
            "runtime_character_spawn_instantiation_cleanup_status": cleanup_status
            or "runtime_character_spawn_instantiation_cleanup_not_attempted",
            "runtime_character_spawn_instantiation_is_animation_proof": False,
            "runtime_character_spawn_instantiation_remaining_blocker": "" if verified else blocker,
            "runtime_character_instantiation_claimed": bool(verified),
            "runtime_character_instantiation_verified": bool(verified),
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    )
    return source_payload


def _runtime_character_spawn_instantiation_parse_markers(combined_text: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "markers_observed": False,
        "request_issued": False,
        "completion_observed": False,
        "entity_count": 0,
        "entity_ids": [],
        "entity_names": [],
        "component_inventory": [],
        "cleanup_attempted": False,
        "cleanup_status": "runtime_character_spawn_instantiation_cleanup_not_attempted",
        "errors": [],
        "timed_out": False,
        "summary": {},
    }
    for raw_line in combined_text.splitlines():
        marker_index = raw_line.find("MAXINE_RUNTIME_CHARACTER_SPAWN_")
        if marker_index < 0:
            continue
        line = raw_line[marker_index:].strip()
        payload["markers_observed"] = True
        fields = _runtime_marker_fields(line)
        if line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_START"):
            payload["product_path"] = fields.get("product_path", "")
            payload["catalog_path"] = fields.get("catalog_path", "")
            payload["asset_id"] = fields.get("asset_id", "")
            payload["asset_type"] = fields.get("asset_type", "")
            payload["timeout_ticks"] = _int_or_zero(fields.get("timeout_ticks", 0))
        elif line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_CONTEXT"):
            payload["context_status"] = fields.get("status", "")
            payload["context_id"] = fields.get("context_id", "")
        elif line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_TICKET"):
            payload["ticket"] = fields.get("ticket", "")
        elif line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_REQUESTED"):
            payload["request_issued"] = True
            payload["ticket"] = fields.get("ticket", payload.get("ticket", ""))
        elif line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_COMPLETED"):
            payload["completion_observed"] = True
            payload["ticket"] = fields.get("ticket", payload.get("ticket", ""))
            payload["spawn_result"] = fields.get("result", "")
            payload["entity_count"] = _int_or_zero(fields.get("entity_count", payload.get("entity_count", 0)))
        elif line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY"):
            payload["entity_ids"].append(fields.get("entity_id", ""))
            payload["entity_names"].append(fields.get("name", ""))
            components = [item for item in str(fields.get("components", "")).split(";") if item]
            payload["component_inventory"].append(
                {
                    "entity_id": fields.get("entity_id", ""),
                    "entity_name": fields.get("name", ""),
                    "component_count": _int_or_zero(fields.get("component_count", len(components))),
                    "actor_asset_id": fields.get("actor_asset_id", ""),
                    "motion_asset_id": fields.get("motion_asset_id", ""),
                    "components": components,
                }
            )
            payload["entity_count"] = max(int(payload.get("entity_count", 0) or 0), len(payload["entity_ids"]))
        elif line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_CLEANUP"):
            payload["cleanup_attempted"] = True
            cleanup = fields.get("status", "")
            payload["cleanup_status"] = (
                "runtime_character_spawn_instantiation_cleanup_complete"
                if cleanup == "complete"
                else "runtime_character_spawn_instantiation_cleanup_not_required"
                if cleanup == "not_required"
                else "runtime_character_spawn_instantiation_cleanup_failed"
            )
        elif line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_TIMEOUT"):
            payload["timed_out"] = True
            payload["errors"].append({"line": " ".join(line.split())[:240], "reason": "timeout"})
        elif line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR"):
            payload["errors"].append({"line": " ".join(line.split())[:240], "reason": fields.get("error", "spawn_error")})
        elif line.startswith("MAXINE_RUNTIME_CHARACTER_SPAWN_SUMMARY"):
            payload["summary"] = dict(fields)
            payload["timed_out"] = payload["timed_out"] or str(fields.get("timed_out", "")).strip() in {"1", "true", "True"}
            payload["entity_count"] = max(
                int(payload.get("entity_count", 0) or 0),
                _int_or_zero(fields.get("spawned", payload.get("entity_count", 0))),
            )
            cleanup = str(fields.get("cleanup", "")).strip()
            if cleanup and not payload.get("cleanup_attempted"):
                payload["cleanup_status"] = (
                    "runtime_character_spawn_instantiation_cleanup_complete"
                    if cleanup == "complete"
                    else "runtime_character_spawn_instantiation_cleanup_not_required"
                    if cleanup == "not_required"
                    else "runtime_character_spawn_instantiation_cleanup_failed"
                )
    return payload


def _int_or_zero(value: Any) -> int:
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: Any) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _runtime_character_product_load_parse_markers(
    *,
    products: Sequence[Mapping[str, Any]],
    combined_text: str,
) -> tuple[List[Dict[str, Any]], Dict[str, Any], bool]:
    by_kind = {str(product.get("product_kind", "")): dict(product) for product in products}
    summary: Dict[str, Any] = {}
    markers_observed = False
    for line in combined_text.splitlines():
        line = line.strip()
        marker_index = line.find("MAXINE_RUNTIME_PRODUCT_LOAD_")
        if marker_index < 0:
            continue
        line = line[marker_index:].strip()
        markers_observed = True
        fields = _runtime_marker_fields(line)
        kind = str(fields.get("kind", "")).strip()
        if line.startswith("MAXINE_RUNTIME_PRODUCT_LOAD_SUMMARY"):
            summary = dict(fields)
            continue
        if line.startswith("MAXINE_RUNTIME_PRODUCT_LOAD_START"):
            summary.setdefault("start", dict(fields))
            continue
        if not kind or kind not in by_kind:
            continue
        product = by_kind[kind]
        if "path" in fields:
            product["product_path"] = str(fields["path"])
        if "catalog_path" in fields:
            product["catalog_path"] = str(fields["catalog_path"])
        if line.startswith("MAXINE_RUNTIME_PRODUCT_LOAD_RESOLVED"):
            product["asset_id"] = str(fields.get("asset_id", product.get("asset_id", "")))
            product["asset_type_id"] = str(fields.get("asset_type", product.get("asset_type_id", "")))
            product["asset_type_name"] = str(fields.get("asset_type_name", product.get("asset_type_name", "")))
            product["resolution_status"] = "runtime_character_product_load_product_resolved"
            product["load_requested"] = True
            product["load_status"] = "runtime_character_product_load_product_load_requested"
        elif line.startswith("MAXINE_RUNTIME_PRODUCT_LOAD_READY"):
            product["ready"] = True
            product["load_requested"] = True
            product["load_status"] = "runtime_character_product_load_product_ready"
        elif line.startswith("MAXINE_RUNTIME_PRODUCT_LOAD_ERROR"):
            product["ready"] = False
            if "asset_id" in fields:
                product["asset_id"] = str(fields.get("asset_id", product.get("asset_id", "")))
                product["resolution_status"] = "runtime_character_product_load_product_resolved"
            if "asset_type" in fields:
                product["asset_type_id"] = str(fields.get("asset_type", product.get("asset_type_id", "")))
            if "asset_type_name" in fields:
                product["asset_type_name"] = str(fields.get("asset_type_name", product.get("asset_type_name", "")))
            product["error"] = str(fields.get("error", fields.get("status", "runtime_product_load_error")))
            product["load_status"] = "runtime_character_product_load_product_error"
        elif line.startswith("MAXINE_RUNTIME_PRODUCT_LOAD_TIMEOUT"):
            product["ready"] = False
            product["timeout"] = True
            product["load_status"] = "runtime_character_product_load_product_timeout"
        elif line.startswith("MAXINE_RUNTIME_PRODUCT_LOAD_RELEASED"):
            product["release_status"] = "runtime_character_product_load_product_released"
    for product in by_kind.values():
        if str(product.get("resolution_status", "")).strip() == "runtime_character_product_load_not_attempted":
            product["resolution_status"] = "runtime_character_product_load_product_missing"
        if product.get("ready") is True and str(product.get("release_status", "")).strip() == "runtime_character_product_load_release_not_required":
            product["release_status"] = "runtime_character_product_load_product_released"
    order = [str(product.get("product_kind", "")) for product in products if str(product.get("product_kind", ""))]
    return [by_kind[kind] for kind in order if kind in by_kind], summary, markers_observed


def _runtime_marker_fields(line: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def _runtime_character_product_selected_product_errors(
    products: Sequence[Mapping[str, Any]],
    combined_text: str,
) -> List[Dict[str, str]]:
    error_terms = (
        "failed to load",
        "asset load failed",
        "load error",
        "not found",
        "missing product",
        "no handler was registered",
    )
    matches: List[Dict[str, str]] = []
    for line in combined_text.splitlines():
        lower_line = line.lower()
        if not any(term in lower_line for term in error_terms):
            continue
        normalized = " ".join(line.strip().split())[:240]
        for product in products:
            if not isinstance(product, Mapping):
                continue
            product_path = str(product.get("product_path", "")).lower()
            catalog_path = str(product.get("catalog_path", "")).lower()
            asset_id = str(product.get("asset_id", "")).lower()
            if (
                (product_path and product_path in lower_line)
                or (catalog_path and catalog_path in lower_line)
                or (asset_id and asset_id in lower_line)
            ):
                matches.append(
                    {
                        "product_kind": str(product.get("product_kind", "")),
                        "product_path": str(product.get("product_path", "")),
                        "catalog_path": str(product.get("catalog_path", "")),
                        "line": normalized,
                    }
                )
    return matches


def _run_runtime_ap_shader_signal_diagnostic(
    report: Dict[str, Any],
    *,
    engine_root: Path | None,
    project: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    report.update(
        _runtime_signal_classification_source_payload(
            project=project,
            engine_root=engine_root,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )
    )
    report.update(
        {
            "status": "pass",
            "runtime_harness_status": "runtime_signal_classification_source_discovery_pass",
            "runtime_harness_mode": "runtime_ap_shader_signal_classification_diagnostic",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
            "asset_cache_deleted": False,
            "required_runtime_harness_assertions_passed": [
                "runtime_signal_classification_source_discovery",
                "runtime_execution_not_attempted_in_signal_diagnostic_mode",
                "runtime_character_proof_not_claimed",
            ],
            "runtime_harness_assertion_informational": [
                "ap_shader_source_classification_is_not_runtime_execution_proof",
                "ap_shader_source_classification_is_not_runtime_character_proof",
            ],
        }
    )
    return _finalize_report(report)


def _runtime_signal_classification_source_payload(
    *,
    project: Path | None,
    engine_root: Path | None,
    timeout_seconds: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    _ = timeout_seconds
    _ = artifact_dir
    source_validated = _runtime_signal_classification_source_validated(engine_root)
    status = (
        "runtime_signal_classification_source_discovery_pass"
        if source_validated
        else "runtime_signal_classification_source_discovery_inconclusive"
    )
    candidates = _runtime_signal_classification_candidate_matrix(project=project, engine_root=engine_root)
    selected = _runtime_signal_classification_selected_candidate(project=project, engine_root=engine_root)
    return {
        "runtime_signal_classification": {
            "status": status,
            "selected": RUNTIME_SIGNAL_CLASSIFICATION_SELECTED if source_validated else "",
            "candidate_count": len(candidates),
        },
        "runtime_signal_classification_status": status,
        "runtime_signal_classification_candidates": candidates,
        "runtime_signal_classification_candidate_matrix_recorded": bool(candidates),
        "runtime_signal_classification_candidate_id": selected["id"] if source_validated else "",
        "runtime_signal_classification_candidate_name": selected["name"] if source_validated else "",
        "runtime_signal_classification_candidate_kind": selected["kind"] if source_validated else "",
        "runtime_signal_classification_candidate_source_validation": selected["source_validation"]
        if source_validated
        else {},
        "runtime_signal_classification_candidate_source_refs": selected["source_refs"] if source_validated else [],
        "runtime_signal_classification_candidate_expected_signals": selected["expected_signals"]
        if source_validated
        else {},
        "runtime_signal_classification_candidate_actual_signals": {},
        "runtime_signal_classification_candidate_expected_level_loads": [],
        "runtime_signal_classification_candidate_actual_level_loads": [],
        "runtime_signal_classification_candidate_attempted": False,
        "runtime_signal_classification_candidate_result": selected["result"] if source_validated else "",
        "runtime_signal_classification_candidate_blocker": "",
        "runtime_signal_classification_selected": RUNTIME_SIGNAL_CLASSIFICATION_SELECTED if source_validated else "",
        "runtime_signal_classification_selected_reason": (
            "rerun_pr136_no_defaultlevel_cache_bootstrap_fixture_and_classify_known_ap_shader_signals"
            if source_validated
            else ""
        ),
        "runtime_signal_classification_verified": False,
        **_runtime_ap_signal_source_fields(engine_root=engine_root, signal_lines=[], present=False),
        **_runtime_shader_signal_source_fields(engine_root=engine_root, signal_lines=[], present=False),
    }


def _runtime_signal_classification_execution_payload(
    *,
    project: Path | None,
    command: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    actual_level_loads: Sequence[str],
    combined_text: str,
    exit_code: int | None,
    marker_observed: bool,
    cache_bootstrap_strategy: bool,
    mutation_state: Mapping[str, Any],
) -> Dict[str, Any]:
    engine_root = _runtime_engine_root_from_command(command)
    source_payload = _runtime_signal_classification_source_payload(
        project=project,
        engine_root=engine_root,
        timeout_seconds=int(command.get("timeout_seconds", 120)),
        artifact_dir=DEFAULT_ARTIFACT_ROOT,
    )
    ap_count = _runtime_diagnostic_count(diagnostics, "asset_processor_negotiation_failure_count")
    shader_count = _runtime_diagnostic_count(diagnostics, "shader_serializer_error_count")
    ap_lines = _runtime_ap_signal_lines(combined_text)
    shader_lines = _runtime_shader_signal_lines(combined_text)
    default_level_detected = any(_is_default_level_path(path) for path in actual_level_loads)
    production_level_loaded = bool(actual_level_loads)
    source_validated = _runtime_signal_classification_source_validated(engine_root)
    wait_for_connect_value = _runtime_wait_for_connect_value(command)
    exit_clean = exit_code == 0
    cache_restored = str(mutation_state.get("restore_status", "")).strip() == "runtime_cache_bootstrap_restore_pass"
    cache_hash_verified = bool(mutation_state.get("hash_verified", False))
    no_missing_load_errors = not _scan_runtime_output(combined_text).get("matches")
    ap_harmless = (
        bool(ap_count)
        and source_validated
        and wait_for_connect_value == "0"
        and exit_clean
        and marker_observed
        and not default_level_detected
        and not production_level_loaded
        and cache_bootstrap_strategy
        and cache_restored
        and cache_hash_verified
        and no_missing_load_errors
    )
    shader_harmless = (
        bool(shader_count)
        and source_validated
        and _runtime_command_uses_null_headless(command)
        and _shader_lines_match_known_rhi_reflection_gap(shader_lines)
        and exit_clean
        and marker_observed
        and not default_level_detected
        and not production_level_loaded
        and cache_bootstrap_strategy
        and cache_restored
        and cache_hash_verified
        and no_missing_load_errors
    )
    ap_absent = ap_count == 0
    shader_absent = shader_count == 0
    classification_verified = (ap_absent or ap_harmless) and (shader_absent or shader_harmless)
    blocker = ""
    if default_level_detected:
        blocker = "blocked_by_default_level_autoload"
    elif production_level_loaded:
        blocker = "blocked_by_production_level_load"
    elif not source_validated:
        blocker = "blocked_by_ap_shader_signal_unclassified"
    elif ap_count and not ap_harmless:
        blocker = "blocked_by_asset_processor_negotiation_signal"
    elif shader_count and not shader_harmless:
        blocker = "blocked_by_shader_serializer_signal"

    actual_signals = {
        "asset_processor_negotiation_count": ap_count,
        "shader_serializer_count": shader_count,
        "asset_processor_negotiation_lines": ap_lines,
        "shader_serializer_lines": shader_lines,
    }
    source_payload.update(
        {
            "runtime_signal_classification": {
                "status": "runtime_signal_classification_verified"
                if classification_verified
                else "runtime_signal_classification_candidate_attempted_failed_disqualifying_signal",
                "selected": RUNTIME_SIGNAL_CLASSIFICATION_SELECTED,
                "attempted": True,
                "actual_signals": actual_signals,
            },
            "runtime_signal_classification_status": "runtime_signal_classification_verified"
            if classification_verified
            else "runtime_signal_classification_candidate_attempted_failed_disqualifying_signal",
            "runtime_signal_classification_candidate_actual_signals": actual_signals,
            "runtime_signal_classification_candidate_actual_level_loads": list(actual_level_loads),
            "runtime_signal_classification_candidate_attempted": True,
            "runtime_signal_classification_candidate_result": "runtime_signal_classification_candidate_attempted_pass"
            if classification_verified
            else "runtime_signal_classification_candidate_attempted_failed_disqualifying_signal",
            "runtime_signal_classification_candidate_blocker": blocker,
            "runtime_signal_classification_verified": bool(classification_verified),
            **_runtime_ap_signal_source_fields(
                engine_root=engine_root,
                signal_lines=ap_lines,
                present=bool(ap_count),
                classification="runtime_asset_processor_negotiation_classified_harmless"
                if ap_harmless
                else "runtime_asset_processor_negotiation_signal_absent"
                if ap_absent
                else "runtime_asset_processor_negotiation_unclassified",
                disqualifying=bool(ap_count and not ap_harmless),
                wait_for_connect_value=wait_for_connect_value,
                blocker="" if (ap_absent or ap_harmless) else "blocked_by_asset_processor_negotiation_signal",
            ),
            **_runtime_shader_signal_source_fields(
                engine_root=engine_root,
                signal_lines=shader_lines,
                present=bool(shader_count),
                classification="runtime_shader_serializer_classified_harmless"
                if shader_harmless
                else "runtime_shader_serializer_signal_absent"
                if shader_absent
                else "runtime_shader_serializer_unclassified",
                disqualifying=bool(shader_count and not shader_harmless),
                blocker="" if (shader_absent or shader_harmless) else "blocked_by_shader_serializer_signal",
            ),
        }
    )
    return source_payload


def _runtime_signal_classification_selected_candidate(*, project: Path | None, engine_root: Path | None) -> Dict[str, Any]:
    source_refs = _runtime_signal_classification_source_refs(engine_root)
    return {
        "id": RUNTIME_SIGNAL_CLASSIFICATION_SELECTED,
        "name": "Rerun PR #136 no-defaultlevel cache-bootstrap fixture and classify AP/shader signals",
        "kind": "bounded_no_defaultlevel_fixture_signal_classification",
        "source_validation": {
            "status": "runtime_signal_classification_candidate_source_validated"
            if _runtime_signal_classification_source_validated(engine_root)
            else "runtime_signal_classification_candidate_rejected_missing_source_validation",
            "summary": (
                "Launcher.cpp treats failed AP connection as nonfatal when wait_for_connect=0; "
                "ObjectStream.cpp reports unknown serialized classes as non-strict droppable data, while Atom Null RHI "
                "reflects only Null platform shader classes. The selected strategy reruns the PR #136 no-defaultlevel "
                "fixture envelope and classifies only those exact signatures under null/headless/no-level constraints."
            ),
        },
        "source_refs": source_refs,
        "expected_signals": {
            "asset_processor_negotiation": "absent_or_wait_for_connect_zero_nonfatal_warning",
            "shader_serializer": "absent_or_known_non_selected_rhi_reflection_gap",
        },
        "result": "runtime_signal_classification_candidate_source_validated",
        "gate_env": list(RUNTIME_EXIT_FIXTURE_PROJECT_MUTATION_GATE_ENV)
        + list(RUNTIME_EXIT_FIXTURE_CACHE_BOOTSTRAP_MUTATION_GATE_ENV),
        "mutates_project": True,
        "mutates_cache_bootstrap": True,
        "mutates_defaultlevel": False,
        "mutates_production_level": False,
    }


def _runtime_signal_classification_candidate_matrix(*, project: Path | None, engine_root: Path | None) -> List[Dict[str, Any]]:
    _ = project
    selected = _runtime_signal_classification_selected_candidate(project=project, engine_root=engine_root)
    source_refs = _runtime_signal_classification_source_refs(engine_root)
    return [
        {
            "id": "ap_shader_read_only_existing_log_classification",
            "name": "Read-only AP/shader classification from existing logs",
            "kind": "read_only_log_source_classification",
            "source_validation": {
                "status": "runtime_signal_classification_candidate_source_validated",
                "summary": "Existing logs can identify signal signatures but cannot by themselves prove a fresh clean fixture envelope.",
            },
            "source_refs": source_refs,
            "attempted": False,
            "result": "informational_only",
            "blocker": "",
        },
        {
            **selected,
            "attempted": False,
            "blocker": "",
        },
        {
            "id": "ap_shader_controlled_asset_processor_session_comparison",
            "name": "Controlled local Asset Processor session comparison",
            "kind": "bounded_local_asset_processor_session",
            "source_validation": {
                "status": "runtime_signal_classification_candidate_rejected_unsafe",
                "summary": (
                    "A local AP comparison is reserved behind MAXINE_ALLOW_RUNTIME_FIXTURE_ASSET_PROCESSOR_SESSION=1; "
                    "this slice does not need to start a persistent AP session if wait_for_connect=0 source classification is sufficient."
                ),
            },
            "source_refs": source_refs,
            "gate_env": list(RUNTIME_EXIT_FIXTURE_ASSET_PROCESSOR_SESSION_GATE_ENV),
            "attempted": False,
            "result": "runtime_signal_classification_candidate_rejected_unsafe",
            "blocker": "blocked_by_asset_processor_session_not_safely_scoped",
        },
        {
            "id": "ap_shader_shader_product_completeness_audit",
            "name": "Shader product completeness audit",
            "kind": "read_only_shader_product_audit",
            "source_validation": {
                "status": "runtime_signal_classification_candidate_source_validated",
                "summary": "Trusted APB product evidence remains the prerequisite; shader serializer classification still requires source/log constraints.",
            },
            "source_refs": source_refs,
            "attempted": False,
            "result": "informational_only",
            "blocker": "",
        },
        {
            "id": "ap_shader_keep_disqualifying_if_unclassified",
            "name": "Keep AP/shader signals disqualifying if unclassified",
            "kind": "typed_blocker",
            "source_validation": {
                "status": "runtime_signal_classification_candidate_source_validated",
                "summary": "If source/log evidence does not match the constrained harmless signatures, runtime proof remains blocked.",
            },
            "source_refs": source_refs,
            "attempted": False,
            "result": "blocked_by_ap_shader_signal_unclassified",
            "blocker": "blocked_by_ap_shader_signal_unclassified",
        },
    ]


def _runtime_signal_classification_source_validated(engine_root: Path | None) -> bool:
    root = engine_root or Path("")
    return all(
        path.is_file()
        for path in (
            root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Network" / "AssetProcessorConnection.cpp",
            root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Asset" / "AssetSystemComponent.cpp",
            root / "Code" / "LauncherUnified" / "Launcher.cpp",
            root / "Code" / "Framework" / "AzCore" / "AzCore" / "Serialization" / "ObjectStream.cpp",
            root / "Gems" / "Atom" / "RHI" / "Null" / "Code" / "Source" / "RHI.Reflect" / "ReflectSystemComponent.cpp",
            root / "Gems" / "Atom" / "RHI" / "DX12" / "Code" / "Include" / "Atom" / "RHI.Reflect" / "DX12" / "ShaderStageFunction.h",
            root / "Gems" / "Atom" / "RHI" / "Vulkan" / "Code" / "Include" / "Atom" / "RHI.Reflect" / "Vulkan" / "ShaderStageFunction.h",
        )
    )


def _runtime_signal_classification_source_refs(engine_root: Path | None) -> List[str]:
    return _runtime_ap_source_refs(engine_root) + _runtime_shader_source_refs(engine_root)


def _runtime_ap_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [
        _portable_source_ref(root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Network" / "AssetProcessorConnection.cpp"),
        _portable_source_ref(root / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Asset" / "AssetSystemComponent.cpp"),
        _portable_source_ref(root / "Code" / "LauncherUnified" / "Launcher.cpp"),
    ]


def _runtime_shader_source_refs(engine_root: Path | None) -> List[str]:
    root = engine_root or Path("<engine-root>")
    return [
        _portable_source_ref(root / "Code" / "Framework" / "AzCore" / "AzCore" / "Serialization" / "ObjectStream.cpp"),
        _portable_source_ref(root / "Gems" / "Atom" / "RHI" / "Null" / "Code" / "Source" / "RHI.Reflect" / "ReflectSystemComponent.cpp"),
        _portable_source_ref(root / "Gems" / "Atom" / "RHI" / "DX12" / "Code" / "Include" / "Atom" / "RHI.Reflect" / "DX12" / "ShaderStageFunction.h"),
        _portable_source_ref(root / "Gems" / "Atom" / "RHI" / "DX12" / "Code" / "Include" / "Atom" / "RHI.Reflect" / "DX12" / "PipelineLayoutDescriptor.h"),
        _portable_source_ref(root / "Gems" / "Atom" / "RHI" / "Vulkan" / "Code" / "Include" / "Atom" / "RHI.Reflect" / "Vulkan" / "ShaderStageFunction.h"),
    ]


def _portable_source_ref(path: Path) -> str:
    return str(path).replace("\\", "/")


def _runtime_ap_signal_source_fields(
    *,
    engine_root: Path | None,
    signal_lines: Sequence[str],
    present: bool,
    classification: str | None = None,
    disqualifying: bool = False,
    wait_for_connect_value: str = "0",
    blocker: str = "",
) -> Dict[str, Any]:
    source_refs = _runtime_ap_source_refs(engine_root)
    classified = classification or ("runtime_asset_processor_negotiation_signal_present" if present else "runtime_asset_processor_negotiation_signal_absent")
    return {
        "runtime_asset_processor_negotiation_signal": {
            "status": "runtime_asset_processor_negotiation_signal_present"
            if present
            else "runtime_asset_processor_negotiation_signal_absent",
            "count": len(signal_lines),
            "sample_lines": list(signal_lines[:8]),
        },
        "runtime_asset_processor_negotiation_signal_status": "runtime_asset_processor_negotiation_signal_present"
        if present
        else "runtime_asset_processor_negotiation_signal_absent",
        "runtime_asset_processor_negotiation_signal_present": bool(present),
        "runtime_asset_processor_negotiation_signal_lines": list(signal_lines[:12]),
        "runtime_asset_processor_negotiation_signal_sources": ["stdout", "Server.log"] if present else [],
        "runtime_asset_processor_negotiation_source_file": "; ".join(source_refs),
        "runtime_asset_processor_negotiation_source_function": (
            "AzFramework::AssetSystem::AssetProcessorConnection::ConnectThread; "
            "AssetSystemComponent::EstablishAssetProcessorConnection; Launcher::ConnectToAssetProcessor"
        ),
        "runtime_asset_processor_negotiation_source_refs": source_refs,
        "runtime_asset_processor_negotiation_status": "runtime_asset_processor_negotiation_signal_present"
        if present
        else "runtime_asset_processor_negotiation_signal_absent",
        "runtime_asset_processor_negotiation_classification": classified,
        "runtime_asset_processor_negotiation_classification_reason": (
            "wait_for_connect=0 is source-validated in Launcher.cpp as the nonfatal AP connection path; "
            "the fixture uses trusted APB product evidence, loads no level, observes the fixture marker, and exits 0."
            if classified == "runtime_asset_processor_negotiation_classified_harmless"
            else "AP negotiation was absent."
            if not present
            else "AP negotiation signal remains unclassified."
        ),
        "runtime_asset_processor_negotiation_disqualifying": bool(disqualifying),
        "runtime_asset_processor_negotiation_requires_ap_running": False,
        "runtime_asset_processor_negotiation_wait_for_connect_value": wait_for_connect_value,
        "runtime_asset_processor_negotiation_ap_session_status": "not_used",
        "runtime_asset_processor_negotiation_harmless_only_if": [
            "wait_for_connect=0",
            "trusted_apb_product_evidence_complete",
            "no_defaultlevel_autoload",
            "no_production_level_load",
            "fixture_marker_observed",
            "exit_code_0",
        ]
        if classified == "runtime_asset_processor_negotiation_classified_harmless"
        else [],
        "runtime_asset_processor_negotiation_blocker": blocker,
    }


def _runtime_shader_signal_source_fields(
    *,
    engine_root: Path | None,
    signal_lines: Sequence[str],
    present: bool,
    classification: str | None = None,
    disqualifying: bool = False,
    blocker: str = "",
) -> Dict[str, Any]:
    source_refs = _runtime_shader_source_refs(engine_root)
    classified = classification or ("runtime_shader_serializer_signal_present" if present else "runtime_shader_serializer_signal_absent")
    return {
        "runtime_shader_serializer_signal": {
            "status": "runtime_shader_serializer_signal_present" if present else "runtime_shader_serializer_signal_absent",
            "count": len(signal_lines),
            "sample_lines": list(signal_lines[:8]),
        },
        "runtime_shader_serializer_signal_status": "runtime_shader_serializer_signal_present"
        if present
        else "runtime_shader_serializer_signal_absent",
        "runtime_shader_serializer_signal_present": bool(present),
        "runtime_shader_serializer_signal_lines": list(signal_lines[:12]),
        "runtime_shader_serializer_signal_sources": ["stdout", "Server.log"] if present else [],
        "runtime_shader_serializer_source_file": "; ".join(source_refs),
        "runtime_shader_serializer_source_function": (
            "AZ::ObjectStreamImpl unknown-class handling; Atom RHI platform ReflectSystemComponent::Reflect"
        ),
        "runtime_shader_serializer_source_refs": source_refs,
        "runtime_shader_serializer_status": "runtime_shader_serializer_signal_present"
        if present
        else "runtime_shader_serializer_signal_absent",
        "runtime_shader_serializer_classification": classified,
        "runtime_shader_serializer_classification_reason": (
            "The observed class IDs map to DX12/Vulkan shader reflection types while the command selects Null RHI; "
            "ObjectStream.cpp treats unknown non-strict serialized classes as droppable/stale data and the no-level fixture exits cleanly."
            if classified == "runtime_shader_serializer_classified_harmless"
            else "Shader serializer signal was absent."
            if not present
            else "Shader serializer signal remains unclassified."
        ),
        "runtime_shader_serializer_disqualifying": bool(disqualifying),
        "runtime_shader_serializer_related_products": [],
        "runtime_shader_serializer_related_assets": [
            "DX12 ShaderStageFunction {1BAEE536-96CA-4AEB-BA73-D5D72EE35B45}",
            "Vulkan ShaderStageFunction {A606478A-97E9-402D-A776-88EE72DAC6F9}",
            "DX12 PipelineLayoutDescriptor {A10B0F03-F43D-4462-9306-66195B4EFC46}",
        ]
        if present
        else [],
        "runtime_shader_serializer_null_headless_context": classified
        == "runtime_shader_serializer_classified_harmless",
        "runtime_shader_serializer_harmless_only_if": [
            "-NullRenderer",
            "-rhi=null",
            "no_defaultlevel_autoload",
            "no_production_level_load",
            "no_selected_product_load_failure",
            "fixture_marker_observed",
            "exit_code_0",
        ]
        if classified == "runtime_shader_serializer_classified_harmless"
        else [],
        "runtime_shader_serializer_blocker": blocker,
    }


def _runtime_ap_signal_lines(text: str) -> List[str]:
    return _matching_lines(
        text,
        (
            "AssetProcessorConnection::ConnectThread",
            "Network connection attempt failure, negotiation",
            "Negotiation with asset processor failed",
            "Asset Processor Connection",
        ),
        limit=12,
    )


def _runtime_shader_signal_lines(text: str) -> List[str]:
    return _matching_lines(
        text,
        (
            "[Error] (Serialize)",
            "not registered with the serializer",
            "ShaderStageFunction",
            "PipelineLayoutDescriptor",
        ),
        limit=12,
    )


def _runtime_wait_for_connect_value(command: Mapping[str, Any]) -> str:
    for arg in command.get("argv", []):
        text = str(arg)
        if "/Amazon/AzCore/Bootstrap/wait_for_connect=0" in text:
            return "0"
        if "/Amazon/AzCore/Bootstrap/wait_for_connect=1" in text:
            return "1"
    return ""


def _runtime_command_uses_null_headless(command: Mapping[str, Any]) -> bool:
    argv = [str(arg).lower() for arg in command.get("argv", [])]
    return "-nullrenderer" in argv and "-rhi=null" in argv


def _shader_lines_match_known_rhi_reflection_gap(lines: Sequence[str]) -> bool:
    if not lines:
        return False
    joined = "\n".join(lines)
    known_tokens = (
        "{1BAEE536-96CA-4AEB-BA73-D5D72EE35B45}",
        "{A606478A-97E9-402D-A776-88EE72DAC6F9}",
        "{A10B0F03-F43D-4462-9306-66195B4EFC46}",
        "ShaderStageFunction",
        "PipelineLayoutDescriptor",
    )
    return "not registered with the serializer" in joined and any(token in joined for token in known_tokens)


def _runtime_filter_classified_signal_disqualifiers(
    disqualifying: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Any],
    classification: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    if classification.get("runtime_signal_classification_verified") is not True:
        return [dict(item) for item in disqualifying if isinstance(item, Mapping)]
    if diagnostics.get("runtime_asset_manager_asserts", {}).get("count", 0):
        return [dict(item) for item in disqualifying if isinstance(item, Mapping)]
    if diagnostics.get("runtime_assertion_summary", {}).get("assert_count", 0):
        return [dict(item) for item in disqualifying if isinstance(item, Mapping)]
    for field in ("runtime_stdout_error_summary", "runtime_stderr_error_summary", "runtime_log_error_summary"):
        payload = diagnostics.get(field, {})
        if not isinstance(payload, Mapping):
            continue
        if int(payload.get("fatal_or_exception_count", 0) or 0) > 0:
            return [dict(item) for item in disqualifying if isinstance(item, Mapping)]
        non_signal_count = (
            int(payload.get("asset_manager_shutdown_assert_count", 0) or 0)
            + int(payload.get("assert_count", 0) or 0)
            + int(payload.get("fatal_or_exception_count", 0) or 0)
        )
        if non_signal_count:
            return [dict(item) for item in disqualifying if isinstance(item, Mapping)]
    return []


def _sha256_bytes(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _json_pointer_get(data: Any, pointer: str) -> Any:
    current = data
    for part in pointer.strip("/").split("/"):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _json_pointer_delete(data: Any, pointer: str) -> None:
    parts = pointer.strip("/").split("/")
    current = data
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


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


def _runtime_engine_root_from_report(report: Mapping[str, Any]) -> Path | None:
    readiness = report.get("runtime_harness_readiness", {})
    if isinstance(readiness, Mapping):
        value = str(readiness.get("engine_root", "")).strip()
        if value:
            return Path(value)
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
    _record(
        "fixture_uses_character_product_load_probe_key",
        RUNTIME_CHARACTER_PRODUCT_LOAD_SETTINGS_KEYS[0] in combined_source,
        RUNTIME_CHARACTER_PRODUCT_LOAD_SETTINGS_KEYS[0],
    )
    _record(
        "fixture_uses_assetcatalog_product_resolution",
        "GetAssetIdByPath" in combined_source and "GetAssetInfoById" in combined_source,
        "AZ::Data::AssetCatalogRequestBus",
    )
    _record(
        "fixture_uses_assetmanager_product_load",
        "AssetManager::Instance().GetAsset" in combined_source and "IsReady()" in combined_source,
        "AZ::Data::AssetManager::GetAsset",
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
        "settings_registry_keys": list(RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS)
        + list(RUNTIME_CHARACTER_PRODUCT_LOAD_SETTINGS_KEYS),
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
        "runtime_exit_fixture_settings_registry_keys": list(RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS)
        + list(RUNTIME_CHARACTER_PRODUCT_LOAD_SETTINGS_KEYS),
        "runtime_exit_fixture_product_load_settings_registry_keys": list(RUNTIME_CHARACTER_PRODUCT_LOAD_SETTINGS_KEYS),
        "runtime_exit_fixture_settings_registry_key": RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS[1],
        "runtime_exit_fixture_command_line_arg": (
            "--regset=/Amazon/MAXINE/RuntimeHarness/EnableExitFixture=true "
            "--regset=/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks=<positive integer> "
            "--regset=/Amazon/MAXINE/RuntimeHarness/EnableCharacterProductLoadProbe=<false unless gated>"
        ),
        "runtime_exit_fixture_wait_ticks": "settings_registry_controlled_positive_integer",
        "runtime_exit_fixture_command": "",
        "runtime_exit_fixture_arguments": [],
        "runtime_exit_fixture_argument_shape": {
            "fixture_strategy": "repo-owned TickBus exit-after-initialization component",
            "runtime_gate": list(RUNTIME_EXIT_FIXTURE_GATE_ENV),
            "settings_registry_keys": list(RUNTIME_EXIT_FIXTURE_SETTINGS_KEYS),
            "product_load_settings_registry_keys": list(RUNTIME_CHARACTER_PRODUCT_LOAD_SETTINGS_KEYS),
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
        "runtime_exit_fixture_runtime_command_uses_pre_autoexec_suppression_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_cache_bootstrap_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_ap_shader_strategy": False,
        "runtime_exit_fixture_runtime_command_uses_product_load_probe": False,
        "runtime_exit_fixture_runtime_command_uses_spawn_instantiation_probe": False,
        "runtime_exit_fixture_runtime_command_uses_animation_playback_surface_probe": False,
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


def _runtime_character_product_load_probe_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    missing = [
        item.split("=", 1)[0]
        for item in RUNTIME_CHARACTER_PRODUCT_LOAD_GATE_ENV
        if str(env.get(item.split("=", 1)[0], "")).strip() != "1"
    ]
    return {
        "status": "pass" if not missing else "blocked_by_runtime_character_product_load_probe_gate_missing",
        "required": [item.split("=", 1)[0] for item in RUNTIME_CHARACTER_PRODUCT_LOAD_GATE_ENV],
        "missing": missing,
    }


def _runtime_character_spawn_instantiation_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    required = tuple(RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV) + tuple(
        RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV
    )
    missing = [
        item.split("=", 1)[0]
        for item in required
        if str(env.get(item.split("=", 1)[0], "")).strip() != "1"
    ]
    return {
        "status": "pass" if not missing else "blocked_by_runtime_character_spawn_instantiation_gate_missing",
        "required": [item.split("=", 1)[0] for item in required],
        "missing": missing,
    }


def _runtime_character_animation_playback_surface_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    required = (
        tuple(RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_GATE_ENV)
    )
    missing = [
        item.split("=", 1)[0]
        for item in required
        if str(env.get(item.split("=", 1)[0], "")).strip() != "1"
    ]
    return {
        "status": "pass" if not missing else "blocked_by_runtime_character_animation_playback_surface_gate_missing",
        "required": [item.split("=", 1)[0] for item in required],
        "missing": missing,
    }


def _runtime_character_animation_component_wiring_surface_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    required = (
        tuple(RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_GATE_ENV)
    )
    missing = [
        item.split("=", 1)[0]
        for item in required
        if str(env.get(item.split("=", 1)[0], "")).strip() != "1"
    ]
    return {
        "status": "pass" if not missing else "blocked_by_runtime_character_animation_component_wiring_surface_gate_missing",
        "required": [item.split("=", 1)[0] for item in required],
        "missing": missing,
    }


def _runtime_actor_simple_motion_component_wiring_after_apb_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    required = (
        tuple(RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_GATE_ENV)
        + tuple(RUNTIME_ACTOR_SIMPLE_MOTION_AFTER_APB_GATE_ENV)
    )
    missing = [
        item.split("=", 1)[0]
        for item in required
        if str(env.get(item.split("=", 1)[0], "")).strip() != "1"
    ]
    return {
        "status": "pass" if not missing else "blocked_by_runtime_actor_simple_motion_component_wiring_after_apb_gate_missing",
        "required": [item.split("=", 1)[0] for item in required],
        "missing": missing,
    }


def _runtime_animation_playback_execution_gate_status(env: Mapping[str, str]) -> Dict[str, Any]:
    required = (
        tuple(RUNTIME_CHARACTER_SPAWNABLE_SURFACE_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_SPAWN_INSTANTIATION_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE_GATE_ENV)
        + tuple(RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE_GATE_ENV)
        + tuple(RUNTIME_ACTOR_SIMPLE_MOTION_AFTER_APB_GATE_ENV)
        + tuple(RUNTIME_ANIMATION_PLAYBACK_EXECUTION_GATE_ENV)
    )
    missing = [
        item.split("=", 1)[0]
        for item in required
        if str(env.get(item.split("=", 1)[0], "")).strip() != "1"
    ]
    return {
        "status": "pass" if not missing else "blocked_by_runtime_animation_playback_execution_gate_missing",
        "required": [item.split("=", 1)[0] for item in required],
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


def _path_text(path: Path | str) -> str:
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
    parser.add_argument("--diagnose-runtime-pre-autoexec-loadlevel-suppression", action="store_true")
    parser.add_argument("--enable-runtime-exit-fixture-pre-autoexec-loadlevel-suppression", action="store_true")
    parser.add_argument("--diagnose-runtime-cache-bootstrap-loadlevel-source", action="store_true")
    parser.add_argument("--enable-runtime-exit-fixture-cache-bootstrap-loadlevel-source", action="store_true")
    parser.add_argument("--diagnose-runtime-ap-shader-signals", action="store_true")
    parser.add_argument("--enable-runtime-exit-fixture-ap-shader-signal-classification", action="store_true")
    parser.add_argument("--diagnose-runtime-character-product-load", action="store_true")
    parser.add_argument("--enable-runtime-character-product-load-fixture", action="store_true")
    parser.add_argument("--diagnose-runtime-procprefab-handler-or-spawnable-surface", action="store_true")
    parser.add_argument("--diagnose-runtime-character-spawnable-surface", action="store_true")
    parser.add_argument("--diagnose-runtime-character-prefab-source", action="store_true")
    parser.add_argument("--diagnose-runtime-character-spawn-instantiation", action="store_true")
    parser.add_argument("--enable-runtime-character-spawn-instantiation-fixture", action="store_true")
    parser.add_argument("--diagnose-runtime-character-animation-playback-surface", action="store_true")
    parser.add_argument("--enable-runtime-character-animation-playback-surface-fixture", action="store_true")
    parser.add_argument("--diagnose-runtime-character-animation-component-wiring-surface", action="store_true")
    parser.add_argument("--enable-runtime-character-animation-component-wiring-surface-fixture", action="store_true")
    parser.add_argument("--diagnose-runtime-actor-simple-motion-component-wiring-after-apb", action="store_true")
    parser.add_argument("--enable-runtime-actor-simple-motion-component-wiring-after-apb-fixture", action="store_true")
    parser.add_argument("--diagnose-approved-motion-product-handler-unregistered-signal", action="store_true")
    parser.add_argument("--diagnose-runtime-shutdown-poolallocator-assertions", action="store_true")
    parser.add_argument("--enable-runtime-poolallocator-signal-classification-fixture", action="store_true")
    parser.add_argument("--diagnose-runtime-animation-playback-execution-api", action="store_true")
    parser.add_argument("--enable-runtime-animation-playback-execution-fixture", action="store_true")
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
        diagnose_runtime_pre_autoexec_loadlevel_suppression=args.diagnose_runtime_pre_autoexec_loadlevel_suppression,
        enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression=(
            args.enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression
        ),
        diagnose_runtime_cache_bootstrap_loadlevel_source=args.diagnose_runtime_cache_bootstrap_loadlevel_source,
        enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source=(
            args.enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source
        ),
        diagnose_runtime_ap_shader_signals=args.diagnose_runtime_ap_shader_signals,
        enable_runtime_exit_fixture_ap_shader_signal_classification=(
            args.enable_runtime_exit_fixture_ap_shader_signal_classification
        ),
        diagnose_runtime_character_product_load=args.diagnose_runtime_character_product_load,
        enable_runtime_character_product_load_fixture=args.enable_runtime_character_product_load_fixture,
        diagnose_runtime_procprefab_handler_or_spawnable_surface=(
            args.diagnose_runtime_procprefab_handler_or_spawnable_surface
        ),
        diagnose_runtime_character_spawnable_surface=args.diagnose_runtime_character_spawnable_surface,
        diagnose_runtime_character_prefab_source=args.diagnose_runtime_character_prefab_source,
        diagnose_runtime_character_spawn_instantiation=args.diagnose_runtime_character_spawn_instantiation,
        enable_runtime_character_spawn_instantiation_fixture=args.enable_runtime_character_spawn_instantiation_fixture,
        diagnose_runtime_character_animation_playback_surface=(
            args.diagnose_runtime_character_animation_playback_surface
        ),
        enable_runtime_character_animation_playback_surface_fixture=(
            args.enable_runtime_character_animation_playback_surface_fixture
        ),
        diagnose_runtime_character_animation_component_wiring_surface=(
            args.diagnose_runtime_character_animation_component_wiring_surface
        ),
        enable_runtime_character_animation_component_wiring_surface_fixture=(
            args.enable_runtime_character_animation_component_wiring_surface_fixture
        ),
        diagnose_runtime_actor_simple_motion_component_wiring_after_apb=(
            args.diagnose_runtime_actor_simple_motion_component_wiring_after_apb
        ),
        enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture=(
            args.enable_runtime_actor_simple_motion_component_wiring_after_apb_fixture
        ),
        diagnose_approved_motion_product_handler_unregistered_signal=(
            args.diagnose_approved_motion_product_handler_unregistered_signal
        ),
        diagnose_runtime_shutdown_poolallocator_assertions=args.diagnose_runtime_shutdown_poolallocator_assertions,
        enable_runtime_poolallocator_signal_classification_fixture=(
            args.enable_runtime_poolallocator_signal_classification_fixture
        ),
        diagnose_runtime_animation_playback_execution_api=(
            args.diagnose_runtime_animation_playback_execution_api
        ),
        enable_runtime_animation_playback_execution_fixture=(
            args.enable_runtime_animation_playback_execution_fixture
        ),
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
