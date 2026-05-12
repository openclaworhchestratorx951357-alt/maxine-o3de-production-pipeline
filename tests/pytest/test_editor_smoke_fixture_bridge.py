import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from tools.o3de.editor_smoke import (
    _exit_code_for_status,
    load_fixture_reports,
    run_editor_smoke_corpus,
    validate_editor_smoke_report,
)
from tools.o3de.editor_python import maxine_package_prefab_smoke as editor_python_smoke
from tools.validation.schema_utils import load_json, schema_validate


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS = REPO_ROOT / "examples" / "editor-smoke"
SCHEMA = REPO_ROOT / "schemas" / "maxine.editor-smoke-report.schema.json"
SCRIPT = REPO_ROOT / "tools" / "o3de" / "editor_smoke.py"
VALIDATE_ALL = REPO_ROOT / "tools" / "validation" / "validate_all.py"


def _project(root: Path) -> Path:
    project = root / "MAXINE_GoldenCorpus"
    project.mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"project_name": "MAXINE_GoldenCorpus", "gem_names": ["EditorPythonBindings"]}),
        encoding="utf-8",
    )
    return project


def _engine(root: Path) -> Path:
    engine = root / "o3de"
    bin_dir = engine / "build" / "windows" / "bin" / "profile"
    bin_dir.mkdir(parents=True)
    (engine / "engine.json").write_text('{"engine_name":"o3de"}\n', encoding="utf-8")
    (bin_dir / "Editor.exe").write_text("editor placeholder", encoding="utf-8")
    (bin_dir / "EditorPythonBindings.Editor.dll").write_text("bindings placeholder", encoding="utf-8")
    return engine


def _live_env(tmp_path: Path, *, allow_editor: bool = True) -> dict:
    engine = _engine(tmp_path)
    project = _project(tmp_path)
    apb_report = tmp_path / "apb-live" / "asset_processor_batch_live_report.json"
    apb_report.parent.mkdir(parents=True)
    source_uuid = "11111111-1111-4111-8111-111111111111"
    products = [
        {
            "product_type": product_type,
            "product_path": f"pc/assets/characters/maxine/release/maxine.{product_type}",
            "platform": "pc",
            "status": "ready",
            "source_uuid": source_uuid,
            "source_sub_id": str(index),
            "produced_by_source_uuid": True,
            "evidence_source": "asset_processor_database",
        }
        for index, product_type in enumerate(
            ["azmodel", "actor", "procprefab", "motion", "motionset", "animgraph", "pxmesh", "azmaterial"],
            start=1,
        )
    ]
    apb_report.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "report_type": "asset_processor_batch_golden_corpus_summary_v1",
                "status": "pass",
                "produced_products": products,
                "missing_products": [],
                "cache_heuristic_used": False,
                "live_asset_processor_batch_execution": True,
                "live_editor_execution": False,
                "live_publication": False,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["O3DE_ENGINE_ROOT"] = str(engine)
    env["O3DE_PROJECT_PATH"] = str(project)
    env["O3DE_EDITOR_EXECUTABLE"] = str(engine / "build" / "windows" / "bin" / "profile" / "Editor.exe")
    env["MAXINE_ENABLE_O3DE_INTEGRATION"] = "1"
    env["MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"] = "1"
    env["MAXINE_ENABLE_O3DE_EDITOR_SMOKE"] = "1"
    env["MAXINE_ALLOW_LIVE_O3DE_COMMANDS"] = "1"
    env["MAXINE_ALLOW_LIVE_EDITOR_COMMANDS"] = "1" if allow_editor else "0"
    env["MAXINE_ALLOW_LIVE_PUBLICATION"] = "0"
    env["MAXINE_ENABLE_RELEASE_PACKAGING"] = "0"
    env["MAXINE_EDITOR_SMOKE_TIMEOUT_SECONDS"] = "5"
    env["MAXINE_APB_BASELINE_REPORT"] = str(apb_report)
    return env


def _write_in_editor_report(env: Mapping[str, str], *, status: str = "pass", exit_code: int = 0) -> subprocess.CompletedProcess[str]:
    report_out = Path(env["MAXINE_EDITOR_SMOKE_REPORT_OUT"])
    payload = json.loads(Path(env["MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE"]).read_text(encoding="utf-8"))
    binding_payload = _binding_contract_payload()
    diagnostic_mode = env.get("MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE", "full")
    if diagnostic_mode in {"actor-binding", "actor-asset-assignment", "full"}:
        binding_payload["actor_binding_checks"] = {
            "status": "pass",
            "product_evidence_status": "pass",
            "actor_product_ref": "pc/assets/characters/maxine/release/jack.actor",
            "component_type_id_status": "pass",
            "component_add_status": "pass",
            "property_path_discovery": {"status": "pass", "properties": ["Actor asset"]},
            "actor_asset_assignment": {
                "status": "pass",
                "property_path": "Actor asset",
                "setter_call": "EditorComponentAPIBus.SetComponentProperty",
                "setter_value_shape": "azlmbr.asset.AssetId",
                "approved_product_ref": "pc/assets/characters/maxine/release/jack.actor",
                "readback": {
                    "status": "pass",
                    "matched_approved_product": True,
                },
            },
        }
    if diagnostic_mode in {
        "prefab-binding",
        "prefab-instantiation",
        "procprefab-product-instantiation",
        "procprefab-content-assertions",
        "procprefab-character-component-assertions",
        "runtime-spawnable-proof-surface",
        "full",
    }:
        binding_payload["prefab_binding_checks"] = {
            "status": "pass",
            "product_evidence_status": "pass",
            "procprefab_product_ref": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "binding_surface_status": "pass",
            "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
            "argument_value_shape": {
                "prefab_path": "project-relative source .prefab path",
                "parent_entity_id": "azlmbr.entity.EntityId",
                "position": "azlmbr.math.Vector3",
            },
            "instantiation": {
                "status": "pass",
                "created_entity_count": 1,
                "container_entity": "EntityId(2)",
            },
        }
        if diagnostic_mode in {
            "procprefab-product-instantiation",
            "procprefab-content-assertions",
            "procprefab-character-component-assertions",
            "runtime-spawnable-proof-surface",
            "full",
        }:
            semantics = _direct_procprefab_semantics_payload()
            semantics.update(_direct_procprefab_verified_product_payload())
            semantics["procprefab_character_assertions"] = _procprefab_character_assertions_payload()
            runtime_proof = _runtime_spawnable_proof_payload()
            semantics["runtime_spawnable_proof"] = runtime_proof
            binding_payload["prefab_binding_checks"]["direct_procprefab_product_semantics"] = semantics
            binding_payload["prefab_binding_checks"]["source_prefab_baseline_result"] = semantics[
                "source_prefab_baseline_result"
            ]
            binding_payload["prefab_binding_checks"]["procprefab_character_assertions"] = semantics[
                "procprefab_character_assertions"
            ]
            binding_payload["prefab_binding_checks"]["runtime_spawnable_proof"] = runtime_proof
            binding_payload["direct_procprefab_product_semantics"] = semantics
            binding_payload["source_prefab_baseline_result"] = semantics["source_prefab_baseline_result"]
            binding_payload["procprefab_character_assertions"] = semantics["procprefab_character_assertions"]
            binding_payload["runtime_spawnable_proof"] = runtime_proof
    payload.update(
        {
            "status": status,
            "live_editor_execution": True,
            "exit_code": exit_code,
            "editor_python_bindings_available": True,
            "temp_level_path_redacted": "Levels/_maxine_smoke/maxine_smoke_test",
            "entity_smoke": {"status": "pass", "entity_id": "EntityId(1)", "name": "maxine_smoke_entity"},
            "prefab_smoke": {"status": "pass"} if diagnostic_mode in {"prefab-binding", "prefab-instantiation", "procprefab-product-instantiation", "procprefab-content-assertions", "procprefab-character-component-assertions", "runtime-spawnable-proof-surface", "full"} else {"status": "unsupported_by_engine_binding", "reason": "prefab instantiation binding not pinned in unit fixture"},
            "actor_smoke": {"status": "pass"} if diagnostic_mode in {"actor-binding", "actor-asset-assignment", "full"} else {"status": "blocked_by_missing_binding", "reason": "actor component type ID not pinned in unit fixture"},
            "component_smoke": {"status": "pass", "components": ["Transform"], "binding_evidence": "EditorComponentAPIBus"},
            "instantiated_entities": [{"name": "maxine_smoke_entity", "components": ["Transform"], "source": "editor_python"}],
            "missing_components": [],
            "errors": [] if status == "pass" else ["MXN_RUNTIME_SMOKE_FAIL"],
            "warnings": [],
            **binding_payload,
        }
    )
    report_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return subprocess.CompletedProcess(args=["Editor.exe"], returncode=exit_code, stdout="editor stdout", stderr="")


def _binding_contract_payload() -> dict:
    return {
        "component_type_registry": {
            "Transform": {
                "status": "pass",
                "discovery_source": "default_entity_component",
                "safe_for_unattended_temp_level_smoke": True,
            },
            "Tag": {
                "status": "unavailable_with_verified_reason",
                "unavailable_reason": "unsupported_by_engine_binding",
                "safe_for_unattended_temp_level_smoke": False,
            },
            "Actor": {
                "status": "unavailable_with_verified_reason",
                "unavailable_reason": "blocked_by_missing_binding",
                "safe_for_unattended_temp_level_smoke": False,
            },
        },
        "binding_call_surface": {
            "EditorComponentAPIBus": {
                "status": "pass",
                "validated_calls": ["FindComponentTypeIdsByEntityType", "BuildComponentPropertyList"],
                "blocked_calls": [],
            }
        },
        "safe_call_results": [
            {"call": "EditorComponentAPIBus.FindComponentTypeIdsByEntityType", "status": "pass"},
            {"call": "EditorComponentAPIBus.BuildComponentPropertyList", "status": "pass"},
        ],
        "component_binding_checks": {
            "status": "pass",
            "entity_name_verified": True,
            "default_transform_verified": True,
            "added_component": {
                "status": "unavailable_with_verified_reason",
                "unavailable_reason": "unsupported_by_engine_binding",
            },
            "property_list_summary": {
                "status": "pass",
                "properties": ["Transform"],
            },
        },
        "actor_binding_checks": {
            "status": "blocked_by_missing_binding",
            "product_evidence_status": "pass",
            "actor_product_ref": "pc/assets/characters/maxine/release/jack.actor",
            "component_type_id_status": "blocked_by_missing_binding",
            "property_path_discovery": {
                "status": "blocked_by_missing_binding",
                "blocked_reason": "actor_component_type_id_not_discovered",
            },
        },
        "prefab_binding_checks": {
            "status": "unsupported_by_engine_binding",
            "product_evidence_status": "pass",
            "procprefab_product_ref": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "binding_surface_status": "unsupported_by_engine_binding",
        },
        "property_access_summary": {
            "Transform": {
                "status": "pass",
                "reads": [{"property_path": "Values|Translate", "status": "pass"}],
            }
        },
        "no_fake_success": True,
    }


def _direct_procprefab_semantics_payload() -> dict:
    return {
        "status": "procprefab_product_not_editor_instantiable_with_current_binding",
        "procprefab_product_evidence": {
            "status": "pass",
            "product_path": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
        },
        "procprefab_product_path": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
        "procprefab_asset_id_resolution": {
            "status": "pass",
            "selected_asset_catalog_path": "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "asset_id": "{11111111-1111-4111-8111-111111111111}:3",
        },
        "procprefab_asset_id": "{11111111-1111-4111-8111-111111111111}:3",
        "procprefab_asset_hint": "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
        "procprefab_binding_surface": {
            "status": "pass",
            "candidate_calls": ["PrefabPublicRequestBus", "PrefabLoaderScriptingBus"],
        },
        "procprefab_selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
        "procprefab_argument_shape": {
            "prefab_path": "APB procprefab product path or AssetCatalog-selected product path",
            "parent_entity_id": "azlmbr.entity.EntityId",
            "position": "azlmbr.math.Vector3",
        },
        "procprefab_direct_product_load_result": {
            "status": "unsupported_by_engine_binding",
            "selected_call": "PrefabLoaderScriptingBus.LoadTemplate",
            "reason": "No verified direct product template-load result in fixture.",
        },
        "procprefab_direct_product_instantiation_result": {
            "status": "procprefab_product_not_editor_instantiable_with_current_binding",
            "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
            "attempted_product_paths": [
                "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
                "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            ],
            "created_entity_count": 0,
            "reason": "Fixture pins the typed unsupported contract without claiming direct product instantiation.",
        },
        "procprefab_created_entity_evidence": {
            "status": "not_created",
            "created_entity_count": 0,
        },
        "source_prefab_baseline_result": {
            "status": "pass",
            "selected_call": "PrefabPublicRequestBus.CreatePrefabInMemory + PrefabPublicRequestBus.InstantiatePrefab",
            "created_entity_count": 1,
            "container_entity": "EntityId(2)",
        },
        "direct_product_instantiation_claimed": False,
        "direct_product_instantiation_supported": False,
        "direct_product_instantiation_verified": False,
        "unsupported_reason": "procprefab_product_not_editor_instantiable_with_current_binding",
        "fake_success": False,
    }


def _direct_procprefab_content_assertions_payload() -> dict:
    return {
        "status": "pass",
        "direct_product_assertion_status": "pass",
        "required_assertions_status": "pass",
        "created_container_entity_id": "EntityId(42)",
        "created_container_valid": True,
        "container_entity_valid": {
            "status": "pass",
            "entity_id": "EntityId(42)",
            "binding": "azlmbr.editor.EditorEntityInfoRequestBus.GetName",
        },
        "owning_prefab_path": "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
        "owning_prefab_path_matches_expected": True,
        "created_entity_ids": ["EntityId(42)"],
        "created_entity_count": 1,
        "created_entity_count_status": "pass",
        "child_entity_ids": [],
        "child_entity_count": 0,
        "child_entity_count_status": "informational_only",
        "entity_name_summary": {
            "status": "pass",
            "container": "maxine_idle_fbx",
            "children": [],
        },
        "component_inventory": {
            "status": "pass",
            "component_count_by_entity": [
                {
                    "entity_id": "EntityId(42)",
                    "components_detected": ["Transform"],
                    "component_checks": [{"component": "Transform", "status": "pass"}],
                }
            ],
            "required_or_expected_components": ["Transform"],
            "missing_required_components": [],
        },
        "component_inventory_status": "pass",
        "asset_reference_summary": {
            "status": "informational_only",
            "reason": "Direct procprefab product asset references are covered by APB product evidence in fixture.",
        },
        "missing_asset_log_signals": {"status": "pass", "matches": []},
        "editor_log_error_scan": {"status": "pass", "matches": []},
        "required_assertions_passed": [
            "created_container_valid",
            "owning_prefab_path_matches_expected",
            "created_entity_count_positive",
            "component_inventory_collected",
            "no_missing_asset_or_load_error_signals",
        ],
        "required_assertions_failed": [],
        "informational_assertions": ["child_entity_structure"],
        "unavailable_assertions": [],
        "assertion_failures": [],
        "assertion_warnings": [],
    }


def _procprefab_character_assertions_payload() -> dict:
    return {
        "status": "unavailable_with_verified_reason",
        "character_assertion_status": "unavailable_with_verified_reason",
        "required_character_assertions_status": "pass",
        "character_component_inventory_status": "unavailable_with_verified_reason",
        "character_component_inventory": {
            "status": "unavailable_with_verified_reason",
            "reason": "direct_procprefab_character_components_not_exposed_in_editor_product_instance",
            "component_presence": {
                "Actor": {"status": "component_not_present", "required": False},
                "Mesh": {"status": "component_not_present", "required": False},
                "Skinned Mesh": {"status": "component_not_present", "required": False},
                "Material": {"status": "component_not_present", "required": False},
                "Animation": {"status": "component_not_present", "required": False},
                "PhysX": {"status": "component_not_present", "required": False},
            },
        },
        "character_component_presence": {
            "Actor": {"status": "component_not_present", "required": False},
            "Mesh": {"status": "component_not_present", "required": False},
            "Skinned Mesh": {"status": "component_not_present", "required": False},
            "Material": {"status": "component_not_present", "required": False},
            "Animation": {"status": "component_not_present", "required": False},
            "PhysX": {"status": "component_not_present", "required": False},
        },
        "character_asset_reference_summary": {
            "status": "unavailable_with_verified_reason",
            "matched_product_evidence": [],
            "reason": "direct_procprefab_character_components_not_exposed_in_editor_product_instance",
        },
        "matched_product_evidence": [],
        "editor_log_character_error_scan": {"status": "pass", "matches": []},
        "editor_log_missing_actor_signal": {"status": "pass", "matches": []},
        "editor_log_missing_mesh_signal": {"status": "pass", "matches": []},
        "editor_log_missing_material_signal": {"status": "pass", "matches": []},
        "editor_log_missing_animation_signal": {"status": "pass", "matches": []},
        "required_character_assertions_passed": ["no_missing_character_load_error_signals"],
        "required_character_assertions_failed": [],
        "character_assertion_failures": [],
        "character_assertion_warnings": [],
        "character_assertion_informational": ["character_components_not_exposed"],
        "character_unavailable_reasons": [
            {
                "assertion": "character_component_presence",
                "reason": "direct_procprefab_character_components_not_exposed_in_editor_product_instance",
            }
        ],
        "unsupported_assertions": [],
    }


def _runtime_spawnable_proof_payload() -> dict:
    return {
        "status": "unavailable_with_verified_reason",
        "runtime_spawnable_proof_status": "unavailable_with_verified_reason",
        "runtime_spawnable_surface_discovery": {
            "status": "runtime_surface_discovery_pass",
            "surface_type": "asset_catalog_product_dependencies_and_spawnable_source_surface",
            "candidate_surfaces": [
                "AssetCatalogRequestBus.GetAllProductDependencies",
                "AssetCatalogRequestBus.GetDirectProductDependencies",
                "AzFramework::Spawnable",
                "AzFramework::Scripts::SpawnableScriptMediator",
            ],
        },
        "runtime_spawnable_surface_available": True,
        "runtime_spawnable_surface_type": "asset_catalog_product_dependencies_and_spawnable_source_surface",
        "runtime_spawnable_selected_call": "",
        "runtime_spawnable_argument_shape": {},
        "runtime_spawnable_execution_attempted": False,
        "runtime_spawnable_execution_result": {
            "status": "runtime_execution_not_attempted",
            "reason": "runtime_spawnable_proof_requires_dedicated_runtime_harness",
        },
        "runtime_spawnable_execution_supported": False,
        "runtime_spawnable_execution_verified": False,
        "runtime_spawnable_product_path": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
        "runtime_spawnable_asset_id": "{11111111-1111-4111-8111-111111111111}:3",
        "product_dependency_proof": {
            "status": "product_dependency_proof_unavailable",
            "product_dependency_count": 0,
            "missing_dependency_count": 0,
            "matches_apb_evidence": False,
            "reason": "direct_procprefab_product_dependency_graph_empty_for_character_products",
        },
        "product_dependency_proof_status": "product_dependency_proof_unavailable",
        "product_dependency_matches_apb_evidence": False,
        "runtime_spawnable_dependency_graph": {
            "status": "product_dependency_proof_unavailable",
            "dependencies": [],
        },
        "runtime_spawnable_product_dependencies": [],
        "runtime_spawnable_character_product_references": [],
        "runtime_spawnable_actor_reference": {"status": "unavailable_with_verified_reason", "product_type": "actor"},
        "runtime_spawnable_azmodel_reference": {"status": "unavailable_with_verified_reason", "product_type": "azmodel"},
        "runtime_spawnable_pxmesh_reference": {"status": "unavailable_with_verified_reason", "product_type": "pxmesh"},
        "runtime_spawnable_azmaterial_reference": {
            "status": "unavailable_with_verified_reason",
            "product_type": "azmaterial",
        },
        "runtime_spawnable_motion_reference": {"status": "unavailable_with_verified_reason", "product_type": "motion"},
        "runtime_spawnable_motionset_reference": {
            "status": "unavailable_with_verified_reason",
            "product_type": "motionset",
        },
        "runtime_spawnable_animgraph_reference": {
            "status": "unavailable_with_verified_reason",
            "product_type": "animgraph",
        },
        "runtime_spawnable_missing_asset_signals": {"status": "pass", "matches": []},
        "runtime_spawnable_missing_character_signals": {"status": "pass", "matches": []},
        "runtime_spawnable_blocked_reason": "runtime_spawnable_proof_requires_dedicated_runtime_harness",
        "runtime_spawnable_unsupported_reason": "",
        "product_dependency_proof_result": {
            "status": "product_dependency_proof_unavailable",
            "reason": "direct_procprefab_product_dependency_graph_empty_for_character_products",
        },
        "editor_component_inventory_character_assertion_result": {
            "status": "unavailable_with_verified_reason",
            "reason": "direct_procprefab_character_components_not_exposed_in_editor_product_instance",
        },
        "direct_product_instantiation_result": {"status": "pass"},
        "direct_product_content_assertion_result": {"status": "pass"},
        "source_prefab_baseline_result": {"status": "pass"},
        "actor_assignment_result": {"status": "pass"},
        "required_runtime_spawnable_assertions_passed": [
            "apb_product_evidence_complete",
            "runtime_execution_not_attempted_with_typed_reason",
            "product_dependency_graph_checked",
        ],
        "required_runtime_spawnable_assertions_failed": [],
        "runtime_spawnable_assertion_failures": [],
        "runtime_spawnable_assertion_informational": [
            "product_dependency_proof_is_not_runtime_execution_proof",
            "spawnable_source_surface_discovered",
        ],
        "runtime_spawnable_unavailable_reasons": [
            {
                "assertion": "runtime_spawnable_execution",
                "status": "runtime_execution_not_attempted",
                "reason": "runtime_spawnable_proof_requires_dedicated_runtime_harness",
            }
        ],
        "runtime_spawnable_unsupported_reasons": [],
        "fake_success": False,
        "cache_heuristic_used": False,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
    }


def _direct_procprefab_verified_product_payload() -> dict:
    content_assertions = _direct_procprefab_content_assertions_payload()
    character_assertions = _procprefab_character_assertions_payload()
    return {
        "status": "pass",
        "procprefab_direct_product_instantiation_result": {
            "status": "pass",
            "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
            "selected_product_path": "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "created_entity_count": 1,
            "container_entity": "EntityId(42)",
            "created_entity_id": "EntityId(42)",
            "owning_instance_prefab_path": "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "owning_instance_prefab_path_status": "pass",
        },
        "procprefab_created_entity_evidence": {
            "status": "pass",
            "created_entity_count": 1,
            "container_entity": "EntityId(42)",
            "owning_instance_prefab_path": "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
        },
        "direct_procprefab_content_assertions": content_assertions,
        "direct_product_assertions": content_assertions,
        "procprefab_character_assertions": character_assertions,
        "direct_product_instantiation_claimed": True,
        "direct_product_instantiation_supported": True,
        "direct_product_instantiation_verified": True,
        "unsupported_reason": "",
        "blocked_reason": "",
    }


def _fixture(name: str) -> dict:
    return load_json(CORPUS / name)


def test_editor_smoke_report_schema_validates():
    schema = load_json(SCHEMA)
    reports = load_fixture_reports(CORPUS)

    assert reports
    for _, report in reports:
        result = schema_validate(report, schema)
        assert result.status == "pass", result.messages


def test_editor_smoke_live_pass_example_schema_and_semantics_validate():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    schema_result = schema_validate(report, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(report, strict=True)

    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages
    assert report["diagnostic_mode"] == "full"
    assert report["progress_log_ref"].endswith("progress.jsonl")
    assert report["entity_smoke"]["status"] == "pass"
    assert report["live_publication"] is False
    assert report["release_packaging"] is False
    assert report["production_level_mutation"] is False
    assert report["no_fake_success"] is True
    assert report["component_binding_checks"]["status"] == "pass"
    assert report["actor_binding_checks"]["status"] == "pass"
    assert report["actor_binding_checks"]["actor_asset_assignment"]["status"] == "pass"
    assert report["actor_binding_checks"]["actor_asset_assignment"]["readback"]["matched_approved_product"] is True
    assert report["prefab_binding_checks"]["status"] == "pass"
    assert report["prefab_binding_checks"]["instantiation"]["status"] in {"pass", "template_load_pass"}
    direct_semantics = report["direct_procprefab_product_semantics"]
    assert direct_semantics["procprefab_product_evidence"]["status"] == "pass"
    assert direct_semantics["source_prefab_baseline_result"]["status"] == "pass"
    assert direct_semantics["direct_product_instantiation_claimed"] is True
    assert direct_semantics["direct_product_instantiation_supported"] is True
    assert direct_semantics["direct_product_instantiation_verified"] is True
    assert direct_semantics["procprefab_direct_product_instantiation_result"]["status"] == "pass"
    assert direct_semantics["procprefab_direct_product_instantiation_result"]["created_entity_count"] > 0
    content_assertions = direct_semantics["direct_procprefab_content_assertions"]
    assert content_assertions["status"] == "pass"
    assert content_assertions["required_assertions_status"] == "pass"
    assert content_assertions["container_entity_valid"]["status"] == "pass"
    assert content_assertions["owning_prefab_path_matches_expected"] is True
    assert content_assertions["created_entity_count_status"] == "pass"
    assert content_assertions["component_inventory_status"] in {"pass", "informational_only"}
    assert content_assertions["missing_asset_log_signals"]["status"] == "pass"
    assert content_assertions["editor_log_error_scan"]["status"] == "pass"
    assert content_assertions["required_assertions_failed"] == []
    character_assertions = direct_semantics["procprefab_character_assertions"]
    assert character_assertions["required_character_assertions_status"] == "pass"
    assert character_assertions["character_component_inventory_status"] in {
        "pass",
        "informational_only",
        "unavailable_with_verified_reason",
    }
    assert character_assertions["editor_log_character_error_scan"]["status"] == "pass"
    assert character_assertions["required_character_assertions_failed"] == []
    assert "Transform" not in character_assertions.get("required_character_assertions_passed", [])
    runtime_proof = report["runtime_spawnable_proof"]
    assert runtime_proof["runtime_spawnable_surface_discovery"]["status"] == "runtime_surface_discovery_pass"
    assert runtime_proof["runtime_spawnable_execution_attempted"] is False
    assert runtime_proof["runtime_spawnable_execution_verified"] is False
    assert runtime_proof["runtime_spawnable_execution_result"]["status"] == "runtime_execution_not_attempted"
    assert runtime_proof["product_dependency_proof_status"] in {
        "product_dependency_proof_pass",
        "product_dependency_proof_unavailable",
    }
    assert runtime_proof["product_dependency_proof"]["status"] == runtime_proof["product_dependency_proof_status"]
    assert runtime_proof["runtime_spawnable_character_product_references"] == []
    assert runtime_proof["required_runtime_spawnable_assertions_failed"] == []
    assert "product_dependency_proof_is_not_runtime_execution_proof" in runtime_proof[
        "runtime_spawnable_assertion_informational"
    ]


def test_editor_smoke_rejects_actor_or_prefab_pass_without_binding_evidence():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["actor_smoke"] = {"status": "pass"}
    report.pop("actor_binding_checks", None)

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_rejects_actor_assignment_pass_without_verified_readback():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["actor_binding_checks"] = {
        "status": "pass",
        "actor_asset_assignment": {
            "status": "pass",
            "property_path": "Actor asset",
            "setter_call": "EditorComponentAPIBus.SetComponentProperty",
            "setter_value_shape": "azlmbr.asset.AssetId",
            "approved_product_ref": "pc/assets/characters/maxine/release/jack.actor",
            "readback": {"status": "pass", "matched_approved_product": False},
        },
    }
    report["actor_smoke"] = {"status": "pass"}

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_rejects_prefab_instantiation_pass_without_created_or_loaded_evidence():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["prefab_binding_checks"] = {
        "status": "pass",
        "product_evidence_status": "pass",
        "procprefab_product_ref": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
        "binding_surface_status": "pass",
        "selected_call": "PrefabPublicRequestBus.InstantiatePrefab",
        "instantiation": {
            "status": "pass",
            "created_entity_count": 0,
        },
    }
    report["prefab_smoke"] = {"status": "pass"}

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_allows_typed_direct_procprefab_unsupported_with_source_prefab_baseline():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["diagnostic_mode"] = "procprefab-product-instantiation"
    report["direct_procprefab_product_semantics"] = _direct_procprefab_semantics_payload()
    report["source_prefab_baseline_result"] = report["direct_procprefab_product_semantics"][
        "source_prefab_baseline_result"
    ]
    report["prefab_binding_checks"]["direct_procprefab_product_semantics"] = report[
        "direct_procprefab_product_semantics"
    ]
    report["prefab_binding_checks"]["source_prefab_baseline_result"] = report["source_prefab_baseline_result"]

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "pass", result.messages


def test_editor_smoke_rejects_direct_procprefab_claim_without_verified_product_instance():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["diagnostic_mode"] = "procprefab-product-instantiation"
    semantics = _direct_procprefab_semantics_payload()
    semantics["direct_product_instantiation_claimed"] = True
    semantics["direct_product_instantiation_verified"] = False
    semantics["procprefab_direct_product_instantiation_result"]["created_entity_count"] = 0
    report["direct_procprefab_product_semantics"] = semantics
    report["source_prefab_baseline_result"] = semantics["source_prefab_baseline_result"]
    report["prefab_binding_checks"]["direct_procprefab_product_semantics"] = semantics
    report["prefab_binding_checks"]["source_prefab_baseline_result"] = semantics["source_prefab_baseline_result"]

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_rejects_verified_direct_procprefab_without_content_assertions():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["diagnostic_mode"] = "procprefab-content-assertions"
    semantics = dict(report["direct_procprefab_product_semantics"])
    semantics.pop("direct_procprefab_content_assertions", None)
    semantics.pop("direct_product_assertions", None)
    report["direct_procprefab_product_semantics"] = semantics
    report["prefab_binding_checks"]["direct_procprefab_product_semantics"] = semantics
    report.pop("direct_procprefab_content_assertions", None)
    report["prefab_binding_checks"].pop("direct_procprefab_content_assertions", None)

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_rejects_direct_procprefab_required_content_assertion_failure():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    semantics = dict(report["direct_procprefab_product_semantics"])
    content_assertions = _direct_procprefab_content_assertions_payload()
    content_assertions["status"] = "fail"
    content_assertions["direct_product_assertion_status"] = "fail"
    content_assertions["required_assertions_status"] = "fail"
    content_assertions["owning_prefab_path_matches_expected"] = False
    content_assertions["required_assertions_failed"] = ["owning_prefab_path_matches_expected"]
    content_assertions["assertion_failures"] = ["assertion_failed_unexpected_owning_path"]
    semantics["direct_procprefab_content_assertions"] = content_assertions
    semantics["direct_product_assertions"] = content_assertions
    report["direct_procprefab_product_semantics"] = semantics
    report["prefab_binding_checks"]["direct_procprefab_product_semantics"] = semantics

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_rejects_verified_direct_procprefab_without_character_assertions():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["diagnostic_mode"] = "procprefab-character-component-assertions"
    semantics = dict(report["direct_procprefab_product_semantics"])
    semantics.pop("procprefab_character_assertions", None)
    report["direct_procprefab_product_semantics"] = semantics
    report["prefab_binding_checks"]["direct_procprefab_product_semantics"] = semantics
    report.pop("procprefab_character_assertions", None)
    report["prefab_binding_checks"].pop("procprefab_character_assertions", None)

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_rejects_required_character_assertion_failure():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["diagnostic_mode"] = "procprefab-character-component-assertions"
    semantics = dict(report["direct_procprefab_product_semantics"])
    character_assertions = _procprefab_character_assertions_payload()
    character_assertions["status"] = "fail"
    character_assertions["character_assertion_status"] = "fail"
    character_assertions["required_character_assertions_status"] = "fail"
    character_assertions["required_character_assertions_failed"] = ["no_missing_character_load_error_signals"]
    character_assertions["character_assertion_failures"] = ["assertion_failed_editor_log_missing_actor"]
    character_assertions["editor_log_missing_actor_signal"] = {"status": "fail", "matches": [{"line": "missing actor"}]}
    semantics["procprefab_character_assertions"] = character_assertions
    report["direct_procprefab_product_semantics"] = semantics
    report["prefab_binding_checks"]["direct_procprefab_product_semantics"] = semantics
    report["prefab_binding_checks"]["procprefab_character_assertions"] = character_assertions
    report["procprefab_character_assertions"] = character_assertions

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_rejects_runtime_spawnable_verified_without_attempted_runtime_execution():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["diagnostic_mode"] = "runtime-spawnable-proof-surface"
    runtime_proof = _runtime_spawnable_proof_payload()
    runtime_proof["runtime_spawnable_execution_verified"] = True
    runtime_proof["runtime_spawnable_execution_attempted"] = False
    runtime_proof["runtime_spawnable_execution_result"] = {"status": "pass"}
    report["runtime_spawnable_proof"] = runtime_proof
    report["direct_procprefab_product_semantics"]["runtime_spawnable_proof"] = runtime_proof
    report["prefab_binding_checks"]["runtime_spawnable_proof"] = runtime_proof
    report["prefab_binding_checks"]["direct_procprefab_product_semantics"] = report[
        "direct_procprefab_product_semantics"
    ]

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_rejects_product_dependency_proof_counted_as_runtime_execution():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report["diagnostic_mode"] = "runtime-spawnable-proof-surface"
    runtime_proof = _runtime_spawnable_proof_payload()
    runtime_proof["product_dependency_proof"]["status"] = "product_dependency_proof_pass"
    runtime_proof["product_dependency_proof_status"] = "product_dependency_proof_pass"
    runtime_proof["runtime_spawnable_execution_attempted"] = False
    runtime_proof["runtime_spawnable_execution_verified"] = True
    report["runtime_spawnable_proof"] = runtime_proof
    report["direct_procprefab_product_semantics"]["runtime_spawnable_proof"] = runtime_proof
    report["prefab_binding_checks"]["runtime_spawnable_proof"] = runtime_proof
    report["prefab_binding_checks"]["direct_procprefab_product_semantics"] = report[
        "direct_procprefab_product_semantics"
    ]

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_full_report_records_runtime_harness_without_character_overclaim():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    runtime_harness = report["runtime_harness"]

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "pass", result.messages
    assert runtime_harness["runtime_harness_readiness_status"] == "runtime_harness_readiness_pass"
    assert runtime_harness["runtime_harness_status"] == "runtime_command_pinning_pass"
    assert runtime_harness["runtime_command_pinning_status"] == "runtime_command_pinning_pass"
    assert runtime_harness["runtime_command_pinned"] is True
    assert runtime_harness["runtime_command_pin_verified"] is True
    assert runtime_harness["runtime_execution_attempted"] is False
    assert runtime_harness["runtime_execution_verified"] is False
    assert runtime_harness["runtime_exit_diagnostic_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_exit_is_crash_like"] is False
    assert runtime_harness["runtime_command_variant_result"]["status"] == "runtime_command_variant_not_attempted"
    assert runtime_harness["runtime_command_variant_matrix"] == []
    assert runtime_harness["runtime_safer_variant_verified"] is False
    assert runtime_harness["runtime_quit_variant_diagnostic_status"] == "not_run"
    assert runtime_harness["runtime_exit_strategy_status"] == "not_run"
    assert runtime_harness["runtime_exit_strategy_candidate_matrix"] == []
    assert runtime_harness["runtime_exit_strategy_verified"] is False
    assert runtime_harness["runtime_exit_fixture_status"] == "not_run"
    assert runtime_harness["runtime_exit_fixture_available"] is False
    assert runtime_harness["runtime_exit_fixture_source_status"] == "not_run"
    assert runtime_harness["runtime_exit_fixture_source_owned_by_repo"] is False
    assert runtime_harness["runtime_exit_fixture_rebuild_gate_status"] == "not_run"
    assert runtime_harness["runtime_exit_fixture_rebuild_attempted"] is False
    assert runtime_harness["runtime_exit_fixture_rebuild_exit_code"] is None
    assert runtime_harness["runtime_exit_fixture_registration_attempted"] is False
    assert runtime_harness["runtime_exit_fixture_registration_command"] == []
    assert runtime_harness["runtime_exit_fixture_enablement_attempted"] is False
    assert runtime_harness["runtime_exit_fixture_enablement_command"] == []
    assert runtime_harness["runtime_exit_fixture_project_mutation_attempted"] is False
    assert runtime_harness["runtime_exit_fixture_project_mutation_files"] == []
    assert runtime_harness["runtime_exit_fixture_project_mutation_diff_summary"] == []
    assert runtime_harness["runtime_exit_fixture_is_shipping_behavior"] is False
    assert runtime_harness["runtime_exit_fixture_execution_verified"] is False
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_console_command_file_quit"] is False
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit"] is False
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_no_default_level_strategy"] is False
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_loadlevel_override_strategy"] is False
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_pre_autoexec_suppression_strategy"] is False
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_temp_or_sandbox_level"] is False
    assert runtime_harness["runtime_exit_fixture_marker_observed"] is False
    assert runtime_harness["runtime_exit_fixture_level_load_observed"] is False
    assert runtime_harness["runtime_exit_fixture_unexpected_level_load"] is False
    assert runtime_harness["runtime_exit_fixture_actual_level_loads"] == []
    assert runtime_harness["runtime_launch_hygiene_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_default_level_autoload_detected"] is False
    assert runtime_harness["runtime_default_level_path"] == "Levels/defaultlevel/defaultlevel.spawnable"
    assert runtime_harness["runtime_default_level_disqualifying"] is False
    assert runtime_harness["runtime_no_default_level_strategy"] == "settings_registry_regremove_autoexec_loadlevel"
    assert runtime_harness["runtime_no_default_level_strategy_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_no_default_level_execution_attempted"] is False
    assert runtime_harness["runtime_no_default_level_execution_verified"] is False
    assert runtime_harness["runtime_loadlevel_override_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_loadlevel_override_candidate_matrix_recorded"] is False
    assert runtime_harness["runtime_loadlevel_override_candidates"] == []
    assert runtime_harness["runtime_loadlevel_override_verified"] is False
    assert runtime_harness["runtime_later_registry_patch_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_later_registry_patch_candidate_matrix_recorded"] is False
    assert runtime_harness["runtime_later_registry_patch_candidates"] == []
    assert runtime_harness["runtime_later_registry_patch_candidate_gate_env"] == []
    assert runtime_harness["runtime_later_registry_patch_verified"] is False
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_later_registry_patch_strategy"] is False
    assert runtime_harness["runtime_pre_autoexec_loadlevel_suppression_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_cache_bootstrap_strategy"] is False
    assert runtime_harness["runtime_pre_autoexec_candidate_matrix_recorded"] is False
    assert runtime_harness["runtime_pre_autoexec_loadlevel_suppression_candidates"] == []
    assert runtime_harness["runtime_pre_autoexec_candidate_gate_env"] == []
    assert runtime_harness["runtime_pre_autoexec_suppression_verified"] is False
    assert runtime_harness["runtime_pre_autoexec_cache_bootstrap_loadlevel_sources"] == []
    assert runtime_harness["runtime_pre_autoexec_cache_bootstrap_loadlevel_source_count"] == 0
    assert runtime_harness["runtime_pre_autoexec_cache_bootstrap_loadlevel_blocker"] == ""
    assert runtime_harness["runtime_cache_bootstrap_loadlevel_source_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_ap_shader_strategy"] is False
    assert runtime_harness["runtime_cache_bootstrap_source_discovery_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_cache_bootstrap_candidate_matrix_recorded"] is False
    assert runtime_harness["runtime_cache_bootstrap_files"] == []
    assert runtime_harness["runtime_cache_bootstrap_verified"] is False
    assert runtime_harness["asset_cache_deleted"] is False
    assert runtime_harness["runtime_signal_classification_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_signal_classification_candidate_matrix_recorded"] is False
    assert runtime_harness["runtime_signal_classification_candidates"] == []
    assert runtime_harness["runtime_signal_classification_verified"] is False
    assert runtime_harness["runtime_settings_registry_merge_order_summary"] == {}
    assert runtime_harness["runtime_settings_registry_project_user_registry_order"] == ""
    assert runtime_harness["runtime_console_autoexec_notification_timing"] == ""
    assert runtime_harness["runtime_spawnable_level_deferred_load_timing"] == ""
    assert runtime_harness["runtime_autoexec_console_command_effective_state"] == {}
    assert runtime_harness["runtime_asset_processor_negotiation_signal_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_asset_processor_negotiation_signal_present"] is False
    assert runtime_harness["runtime_asset_processor_negotiation_source_refs"] == []
    assert runtime_harness["runtime_asset_processor_negotiation_disqualifying"] is False
    assert runtime_harness["runtime_shader_serializer_signal_status"] == "runtime_execution_not_attempted"
    assert runtime_harness["runtime_shader_serializer_signal_present"] is False
    assert runtime_harness["runtime_shader_serializer_source_refs"] == []
    assert runtime_harness["runtime_shader_serializer_disqualifying"] is False
    assert runtime_harness["runtime_production_level_loaded"] is False
    assert runtime_harness["runtime_exit_fixture_is_runtime_character_proof"] is False
    assert runtime_harness["runtime_exit_fixture_character_proof_claimed"] is False
    assert runtime_harness["runtime_harness_proof_is_character_proof"] is False
    assert runtime_harness["runtime_character_proof_claimed"] is False


def test_editor_smoke_rejects_runtime_harness_verified_without_attempted_runtime_execution():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    runtime_harness = dict(report["runtime_harness"])
    runtime_harness["runtime_execution_verified"] = True
    runtime_harness["runtime_execution_attempted"] = False
    runtime_harness["runtime_execution_status"] = "runtime_execution_pass"
    report["runtime_harness"] = runtime_harness

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_character_log_scan_fails_selected_product_missing_actor_signal(tmp_path, monkeypatch):
    project = tmp_path / "MAXINE_GoldenCorpus"
    log_dir = project / "user" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "Editor.log").write_text(
        "<20:07:26> [Error] (Character) - Missing actor for "
        "'assets/characters/maxine/release/maxine_idle_fbx.procprefab'.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("O3DE_PROJECT_PATH", str(project))

    result = editor_python_smoke._scan_editor_log_for_procprefab_character_signals(
        "assets/characters/maxine/release/maxine_idle_fbx.procprefab"
    )

    assert result["status"] == "fail"
    assert result["missing_actor"]["status"] == "fail"
    assert result["log_ref"] == "%USERPROFILE%/O3DE/Projects/MAXINE_GoldenCorpus/user/log/Editor.log"


def test_direct_procprefab_log_scan_ignores_recorded_pc_path_probe_failure(tmp_path, monkeypatch):
    project = tmp_path / "MAXINE_GoldenCorpus"
    log_dir = project / "user" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "Editor.log").write_text(
        "<20:07:26> [Error] (Prefab) - PrefabLoader::LoadTemplate - Failed to load Prefab file from "
        "'pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab'."
        "Error message: 'Failed to open pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab'.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("O3DE_PROJECT_PATH", str(project))

    result = editor_python_smoke._scan_editor_log_for_direct_procprefab_signals(
        "assets/characters/maxine/release/maxine_idle_fbx.procprefab"
    )

    assert result["status"] == "pass"
    assert result["log_ref"] == "%USERPROFILE%/O3DE/Projects/MAXINE_GoldenCorpus/user/log/Editor.log"
    assert str(project).replace("\\", "/") not in result["log_ref"]
    assert result["matches"] == []


def test_direct_procprefab_log_scan_fails_selected_product_path_load_error(tmp_path, monkeypatch):
    project = tmp_path / "MAXINE_GoldenCorpus"
    log_dir = project / "user" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "Editor.log").write_text(
        "<20:07:26> [Error] (Prefab) - PrefabLoader::LoadTemplate - Failed to load Prefab file from "
        "'assets/characters/maxine/release/maxine_idle_fbx.procprefab'.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("O3DE_PROJECT_PATH", str(project))

    result = editor_python_smoke._scan_editor_log_for_direct_procprefab_signals(
        "assets/characters/maxine/release/maxine_idle_fbx.procprefab"
    )

    assert result["status"] == "fail"
    assert result["matches"]
    assert result["log_ref"] == "%USERPROFILE%/O3DE/Projects/MAXINE_GoldenCorpus/user/log/Editor.log"
    assert str(project).replace("\\", "/") not in result["log_ref"]


def test_editor_smoke_live_pass_requires_no_fake_success_marker():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.pop("no_fake_success", None)

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_binding_diagnostic_modes_route_to_target_scripts(tmp_path):
    expected_scripts = {
        "component-binding": "editor_component_binding_smoke.py",
        "actor-binding": "editor_actor_binding_smoke.py",
        "prefab-binding": "editor_prefab_binding_smoke.py",
        "actor-asset-assignment": "editor_actor_asset_assignment_smoke.py",
        "prefab-instantiation": "editor_prefab_instantiation_smoke.py",
        "procprefab-product-instantiation": "editor_procprefab_product_instantiation_smoke.py",
        "procprefab-content-assertions": "editor_procprefab_content_assertions_smoke.py",
        "procprefab-character-component-assertions": "editor_procprefab_character_component_assertions_smoke.py",
        "runtime-spawnable-proof-surface": "editor_runtime_spawnable_proof_surface_smoke.py",
    }

    for mode, script_name in expected_scripts.items():
        def fake_editor_runner(*, argv, cwd, env, timeout_seconds, _mode=mode, _script_name=script_name):
            assert _script_name in argv[-1].replace("\\", "/")
            assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == _mode
            return _write_in_editor_report(env)

        result = run_editor_smoke_corpus(
            CORPUS,
            enable_editor_smoke=True,
            strict_integration=True,
            env=_live_env(tmp_path / mode),
            command_runner=fake_editor_runner,
            artifact_root=tmp_path / mode / "editor-smoke-artifacts",
            diagnostic_mode=mode,
        )

        assert result["status"] == "pass"
        assert result["diagnostic_mode"] == mode


def test_editor_smoke_cli_accepts_explicit_apb_report(tmp_path):
    apb_report = tmp_path / "apb.json"
    apb_report.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            "examples/manifests/release_rigged.pass.example.json",
            "--mode",
            "fixture",
            "--apb-report",
            str(apb_report),
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_editor_smoke_fixture_corpus_passes():
    result = run_editor_smoke_corpus(CORPUS, mode="fixture")

    assert result["status"] == "pass"
    assert result["mode"] == "fixture"
    assert result["integration_enabled"] is False
    assert result["live_editor_execution"] is False
    observed = {case["case_id"]: case["observed_status"] for case in result["cases"]}
    assert observed["release_rigged"] == "pass"
    assert observed["release_rigged_missing_prefab"] == "fail"
    assert observed["release_rigged_cache_heuristic"] == "fail"


def test_editor_smoke_release_missing_prefab_fails():
    report = _fixture("release_rigged.missing_prefab.fail.report.json")
    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_ASSET_PRODUCT_MISSING" in result.error_codes
    assert "prefab" in " ".join(result.messages).lower()


def test_editor_smoke_release_missing_actor_or_motion_fails():
    report = _fixture("release_rigged.missing_actor_motion.fail.report.json")
    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_ASSET_PRODUCT_MISSING" in result.error_codes
    joined = " ".join(result.messages).lower()
    assert "actor" in joined
    assert "motion" in joined


def test_editor_smoke_cache_heuristic_release_fails():
    report = _fixture("release_rigged.cache_heuristic.fail.report.json")
    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" in result.error_codes


def test_editor_smoke_integration_gate_off_uses_fixture(monkeypatch):
    monkeypatch.delenv("MAXINE_ENABLE_O3DE_INTEGRATION", raising=False)
    monkeypatch.delenv("MAXINE_ENABLE_O3DE_EDITOR_SMOKE", raising=False)

    result = run_editor_smoke_corpus(CORPUS)

    assert result["mode"] == "fixture"
    assert result["status"] == "pass"
    assert result["integration_enabled"] is False
    assert result["live_editor_execution"] is False


def test_editor_smoke_integration_unavailable_skips_non_strict(tmp_path):
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env.pop("O3DE_EDITOR_EXECUTABLE", None)
    env["MAXINE_ENABLE_O3DE_EDITOR_SMOKE"] = "1"

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=False,
        env=env,
    )

    assert result["mode"] == "unavailable"
    assert result["status"] == "skipped"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result["warnings"]
    assert result["live_editor_execution"] is False


def test_editor_smoke_integration_unavailable_fails_strict(tmp_path):
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env.pop("O3DE_EDITOR_EXECUTABLE", None)
    env["MAXINE_ENABLE_O3DE_EDITOR_SMOKE"] = "1"

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=env,
    )

    assert result["mode"] == "unavailable"
    assert result["status"] == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result["errors"]
    assert result["live_editor_execution"] is False


def test_editor_smoke_live_requires_explicit_editor_gate(tmp_path):
    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path, allow_editor=False),
    )

    assert result["mode"] == "unavailable"
    assert result["status"] == "fail"
    assert "MAXINE_ALLOW_LIVE_EDITOR_COMMANDS" in " ".join(result["messages"])
    assert result["live_editor_execution"] is False


def test_local_editor_python_pass_requires_live_execution_evidence():
    report = _fixture("release_rigged.fixture.report.json")
    report["mode"] = "local_editor_python"
    report["status"] = "pass"
    report["live_editor_execution"] = False

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_live_runs_bounded_editor_and_consumes_smoke_report(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert timeout_seconds == 5
        assert "--autotest_mode" in argv
        assert "-NullRenderer" in argv
        assert "-rhi=Null" in argv
        assert "--skipWelcomeScreenDialog" in argv
        assert "--runpython" in argv
        assert cwd == env["O3DE_PROJECT_PATH"]
        return _write_in_editor_report(env)

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
    )

    assert result["mode"] == "local_editor_python"
    assert result["status"] == "pass"
    assert result["live_editor_execution"] is True
    assert result["live_publication"] is False
    assert result["release_packaging"] is False
    assert result["production_level_mutation"] is False
    assert result["temp_level_policy"]["valid"] is True
    assert result["entity_smoke"]["status"] == "pass"
    assert result["apb_baseline_ref"]
    assert result["stdout_log_ref"]
    assert result["stderr_log_ref"]


def test_editor_smoke_diagnostic_hello_uses_hello_script_and_progress_log(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_hello_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "hello"
        assert env["MAXINE_EDITOR_SMOKE_PROGRESS_LOG"].endswith("progress.jsonl")
        return _write_in_editor_report(env)

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="hello",
    )

    assert result["status"] == "pass"
    assert result["diagnostic_mode"] == "hello"
    assert result["progress_log_ref"].endswith("progress.jsonl")


def test_editor_smoke_timeout_classifies_last_script_progress_marker(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        progress_path = Path(env["MAXINE_EDITOR_SMOKE_PROGRESS_LOG"])
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-05-10T00:00:00Z",
                    "phase": "script",
                    "step": "create_level_started",
                    "status": "started",
                    "elapsed_seconds": 1.0,
                    "temp_level_path": "Levels/_maxine_smoke/maxine_smoke_test",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout_seconds)

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="temp-level",
    )

    assert result["status"] == "stalled"
    assert result["stall_phase"] == "temp_level_create_stall"
    assert result["last_progress_marker"]["step"] == "create_level_started"


def test_editor_smoke_success_requires_runtime_report(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="hello",
    )

    assert result["status"] == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result["errors"]


def test_editor_smoke_cli_fixture_passes():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", "examples/manifests/release_rigged.pass.example.json", "--mode", "fixture"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Editor smoke fixture bridge: pass" in result.stdout
    assert "live_editor_execution: false" in result.stdout


def test_editor_smoke_cli_strict_integration_fails_when_unavailable(tmp_path):
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env.pop("O3DE_EDITOR_EXECUTABLE", None)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            "examples/manifests/release_rigged.pass.example.json",
            "--enable-editor-smoke",
            "--strict-integration",
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode != 0
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout
    assert "live_editor_execution: false" in result.stdout


def test_editor_python_bridge_script_is_integration_ready_not_executed():
    script = REPO_ROOT / "tools" / "o3de" / "editor_python" / "maxine_package_prefab_smoke.py"

    assert script.exists()
    text = script.read_text(encoding="utf-8-sig")
    assert "integration-ready" in text
    assert "No live publication" in text


def test_editor_python_bridge_script_writes_safe_failure_report_outside_editor(tmp_path):
    script = REPO_ROOT / "tools" / "o3de" / "editor_python" / "maxine_package_prefab_smoke.py"
    template = _fixture("release_rigged.fixture.report.json")
    template.update(
        {
            "mode": "local_editor_python",
            "status": "fail",
            "integration_enabled": True,
            "live_editor_execution": False,
            "live_publication": False,
            "release_packaging": False,
            "production_level_mutation": False,
            "temp_level_path_redacted": "Levels/_maxine_smoke/maxine_smoke_test",
            "temp_level_policy": {"valid": True, "level_root": "Levels/_maxine_smoke"},
            "entity_smoke": {"status": "not_run"},
            "prefab_smoke": {"status": "not_run"},
            "actor_smoke": {"status": "not_run"},
            "component_smoke": {"status": "not_run"},
        }
    )
    template_path = tmp_path / "template.json"
    report_path = tmp_path / "report.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    env = os.environ.copy()
    env["MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE"] = str(template_path)
    env["MAXINE_EDITOR_SMOKE_REPORT_OUT"] = str(report_path)
    env["MAXINE_EDITOR_SMOKE_TEMP_LEVEL_NAME"] = "_maxine_smoke/maxine_smoke_test"
    env["MAXINE_EDITOR_SMOKE_TEMP_LEVEL_PATH"] = str(tmp_path / "MAXINE_GoldenCorpus" / "Levels" / "_maxine_smoke" / "maxine_smoke_test")
    env["MAXINE_ALLOW_LIVE_PUBLICATION"] = "0"
    env["MAXINE_ENABLE_RELEASE_PACKAGING"] = "0"

    result = subprocess.run(
        [sys.executable, str(script), "--allow-temp-sandbox-level"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode != 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["live_editor_execution"] is False
    assert payload["live_publication"] is False
    assert payload["release_packaging"] is False
    assert payload["production_level_mutation"] is False
    assert payload["temp_level_path_redacted"].startswith("Levels/_maxine_smoke/")
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in payload["errors"]


def test_editor_python_create_temp_level_uses_o3de_no_prompt_template(tmp_path):
    calls = []

    class General:
        def create_level_no_prompt(self, *args):
            calls.append(args)
            return 0

        def idle_wait_frames(self, frames):
            calls.append(("idle", frames))

    editor_python_smoke._create_temp_level(
        General(),
        "_maxine_smoke/maxine_smoke_test",
        str(tmp_path / "MAXINE_GoldenCorpus" / "Levels" / "_maxine_smoke" / "maxine_smoke_test"),
    )

    assert calls[0] == ("Prefabs/Default_Level.prefab", "_maxine_smoke/maxine_smoke_test", 1024, 1, 4096, False)
    assert ("idle", 5) not in calls


def test_editor_smoke_stalled_status_exits_nonzero():
    assert _exit_code_for_status({"status": "stalled"}) == 1
    assert _exit_code_for_status({"status": "fail"}) == 1
    assert _exit_code_for_status({"status": "pass"}) == 0


def test_validate_all_includes_fixture_editor_smoke():
    result = subprocess.run(
        [sys.executable, str(VALIDATE_ALL)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Editor smoke fixture bridge" in result.stdout
