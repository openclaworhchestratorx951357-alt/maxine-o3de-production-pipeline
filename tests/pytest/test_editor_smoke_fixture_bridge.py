import json
import os
import subprocess
import sys
import types
from pathlib import Path
from typing import Mapping

from tools.o3de.editor_smoke import (
    DIAGNOSTIC_EDITOR_SCRIPTS,
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


def _write_non_null_desktop_rhi_source_files(engine: Path) -> None:
    source_files = {
        engine
        / "Code"
        / "Framework"
        / "AzGameFramework"
        / "AzGameFramework"
        / "Application"
        / "GameApplication.cpp": "\n".join(
            [
                "const char* commandSwitchNullRenderer = \"NullRenderer\";",
                "const char* commandSwitchRhi = \"rhi\";",
                'if (rhiValue.compare("null")==0) {}',
            ]
        ),
        engine
        / "Gems"
        / "Atom"
        / "Feature"
        / "Common"
        / "Code"
        / "Include"
        / "Atom"
        / "Feature"
        / "Utils"
        / "FrameCaptureBus.h": "\n".join(
            [
                "class FrameCaptureNotificationBus {};",
                "bool CanCapture();",
                "void CaptureScreenshot();",
                "void CaptureScreenshotForWindow();",
                "void OnFrameCaptureFinished();",
            ]
        ),
        engine
        / "Gems"
        / "Atom"
        / "Feature"
        / "Common"
        / "Code"
        / "Source"
        / "FrameCaptureSystemComponent.cpp": "\n".join(
            [
                'behaviorContext->EBus<FrameCaptureRequestBus>("FrameCaptureRequestBus")',
                '->Event("CaptureScreenshot", &FrameCaptureRequestBus::Events::CaptureScreenshot)',
                'behaviorContext->EBus<FrameCaptureNotificationBus>("FrameCaptureNotificationBus")',
                '->Handler<FrameCaptureNotificationBusHandler>()',
                "bool FrameCaptureSystemComponent::CanCapture() const { return !AZ::RHI::IsNullRHI(); }",
                "return !AZ::RHI::IsNullRHI();",
                "FrameCaptureOutcome FrameCaptureSystemComponent::CaptureScreenshot(const AZStd::string& filePath)",
                "AZ::RPI::ViewportContextRequests::Get()->GetDefaultViewportContext()->GetWindowHandle();",
                'error.m_errorMessage = "No valid window for the capture.";',
                "AZ::RPI::PassSystemInterface::Get()->FindSwapChainPass(windowHandle);",
                'error.m_errorMessage = "Failed to find SwapChainPass for the window.";',
                "FrameCaptureNotificationBus::Event(captureHandle.GetCaptureStateIndex(), &FrameCaptureNotificationBus::Events::OnFrameCaptureFinished, capture->m_result, capture->m_latestCaptureInfo.c_str());",
                'else if (extension == "png")',
                "PngFrameCaptureOutput(capture->m_outputFilePath, readbackResult)",
            ]
        ),
        engine
        / "AutomatedTesting"
        / "Gem"
        / "PythonTests"
        / "Atom"
        / "atom_utils"
        / "screenshot_utils.py": "\n".join(
            [
                "FrameCaptureRequestBus = object()",
                "FrameCaptureNotificationBusHandler = object",
                "FrameCaptureResult_Success = 1",
                "azlmbr.atom.FrameCaptureRequestBus(azlmbr.bus.Broadcast, \"CaptureScreenshot\", f\"{folder_path}/{filename}\")",
                "self.handler.connect(outcome.GetValue())",
                "self.handler.add_callback('OnFrameCaptureFinished', self.on_screenshot_captured)",
                "def capture_screenshot_blocking(): pass",
                "general.get_viewport_size()",
                "general.set_viewport_size(frame_width, frame_height)",
                "general.update_viewport()",
                "def prepare_viewport_for_screenshot(): pass",
            ]
        ),
        engine
        / "Code"
        / "Editor"
        / "ViewPane.cpp": "\n".join(
            [
                'behaviorContext->Method("get_viewport_size", PyGetViewPortSize, nullptr, "Get the width and height of the active viewport.")',
                'behaviorContext->Method("set_viewport_size", PySetViewPortSize, nullptr, "Set the width and height of the active viewport.")',
                'behaviorContext->Method("update_viewport", PyUpdateViewPort, nullptr, "Update all visible SDK viewports.")',
                'behaviorContext->Method("get_viewport_count", PyGetViewportCount, nullptr, "Get the total number of viewports.")',
                'behaviorContext->Method("get_active_viewport", PyGetActiveViewport, nullptr, "Get the active viewport index.")',
                'behaviorContext->Method("set_active_viewport", PySetActiveViewport, nullptr, "Set the active viewport by index.")',
                "SetFocusToViewport();",
            ]
        ),
        engine
        / "Code"
        / "Editor"
        / "Lib"
        / "Tests"
        / "test_ViewPanePythonBindings.cpp": "\n".join(
            [
                'EXPECT_TRUE(behaviorContext->m_methods.find("get_viewport_size") != behaviorContext->m_methods.end());',
                'EXPECT_TRUE(behaviorContext->m_methods.find("get_viewport_count") != behaviorContext->m_methods.end());',
                'EXPECT_TRUE(behaviorContext->m_methods.find("get_active_viewport") != behaviorContext->m_methods.end());',
                'EXPECT_TRUE(behaviorContext->m_methods.find("set_active_viewport") != behaviorContext->m_methods.end());',
            ]
        ),
        engine
        / "Code"
        / "Editor"
        / "CryEditPy.cpp": "\n".join(
            [
                'behaviorContext->Method("open_level_no_prompt", ::PyOpenLevelNoPrompt, nullptr, "Opens a level. Doesn\'t prompt user about saving a modified level.")',
                'behaviorContext->Method("create_level_no_prompt", ::PyCreateLevelNoPrompt, nullptr, "Creates a level with the parameters of \'templateName\',\'levelName\', \'resolution\', \'unitSize\' and \'bUseTerrain\'.")',
                'behaviorContext->Method("get_current_level_name", PyGetCurrentLevelName, nullptr, "Gets the name of the current level.")',
                'behaviorContext->Method("get_current_level_path", PyGetCurrentLevelPath, nullptr, "Gets the fully specified path of the current level.")',
            ]
        ),
        engine
        / "AutomatedTesting"
        / "Gem"
        / "PythonTests"
        / "EditorPythonTestTools"
        / "editor_python_test_tools"
        / "utils.py": "\n".join(
            [
                'template_name = "Prefabs/Default_Level.prefab"',
                "result = general.create_level_no_prompt(template_name, level_name, heightmap_resolution, heightmap_meters_per_pixel, terrain_texture_resolution, use_terrain)",
                "success = general.open_level_no_prompt(os.path.join(directory, level))",
                "general.idle_wait_frames(200)",
            ]
        ),
        engine
        / "Gems"
        / "Atom"
        / "RHI"
        / "DX12"
        / "Code"
        / "atom_rhi_dx12_private_common_files.cmake": "\n".join(
            [
                "Source/RHI/DX12.cpp",
                "Source/RHI/Device.cpp",
            ]
        ),
        engine
        / "Gems"
        / "Atom"
        / "RHI"
        / "Vulkan"
        / "Code"
        / "atom_rhi_vulkan_private_common_files.cmake": "\n".join(
            [
                "Source/RHI/Buffer.cpp",
                "Source/RHI/Device.cpp",
            ]
        ),
    }
    for path, text in source_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")


def _editor_viewport_visual_material_blocked_payload() -> dict:
    return {
        "mode": "local_editor_python",
        "status": "pass",
        "diagnostic_mode": "editor-viewport-visual-material-evidence",
        "live_editor_execution": True,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
        "editor_viewport_visual_material_evidence_attempted": True,
        "editor_viewport_visual_material_evidence_completed": True,
        "editor_viewport_visual_material_evidence_source_validation_status": (
            "editor_viewport_visual_material_evidence_source_validation_pass"
        ),
        "editor_viewport_visual_material_evidence_source_validation_verified": True,
        "editor_viewport_visual_material_evidence_blocker": "blocked_by_editor_viewport_capture_requires_non_null_rhi",
        "editor_viewport_visual_material_evidence_candidate_matrix": [
            {
                "id": "editor_viewport_screenshot_harness",
                "selected": True,
                "result": "selected_but_blocked_by_current_null_rhi_editor_command",
            },
            {
                "id": "nullrenderer_visual_proof",
                "selected": False,
                "result": "rejected_nullrenderer_is_not_visual_proof",
            },
            {
                "id": "apb_material_product_inventory_as_rendered_proof",
                "selected": False,
                "result": "rejected_inventory_is_readiness_only_not_rendered_evidence",
            },
        ],
        "editor_viewport_visual_material_evidence_selected_strategy": (
            "editor_viewport_screenshot_capture_surface_blocked_by_current_null_rhi_envelope"
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
        "editor_visual_material_capture_api_found": True,
        "editor_visual_material_capture_api_used": "AZ::Render::FrameCaptureRequestBus::CaptureScreenshot",
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
        "visual_material_product_inventory_gate_verified": True,
        "visual_material_rendered_evidence_gate_attempted": False,
        "visual_material_rendered_evidence_gate_verified": False,
        "visual_material_gate_claimed": False,
        "visual_material_gate_verified": False,
        "full_runtime_character_visual_material_gate_verified": False,
        "full_runtime_character_proof_contract_pinned": True,
        "full_runtime_character_proof_contract_verified": True,
        "full_runtime_character_proof_satisfied_gates": [
            {"id": "spawn_instantiation", "verified": True},
            {"id": "component_wiring", "verified": True},
            {"id": "simple_motion_playback", "verified": True},
            {"id": "behavior_smoke", "verified": True},
            {"id": "selected_log_scan", "verified": True},
            {"id": "cleanup_recovery", "verified": True},
        ],
        "full_runtime_character_proof_unsatisfied_gates": [
            {
                "id": "visual_material",
                "verified": False,
                "blocker": "blocked_by_editor_viewport_capture_requires_non_null_rhi",
            }
        ],
        "full_runtime_character_proof_deferred_gates": [
            {
                "id": "visual_capture_surface",
                "verified": False,
                "blocker": "blocked_by_visual_material_rendered_evidence_capture_deferred",
            }
        ],
        "runtime_character_behavior_smoke_verified": True,
        "runtime_character_animation_verified": True,
        "runtime_character_animation_component_wiring_verified": True,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _non_null_editor_render_capture_envelope_blocked_payload() -> dict:
    return {
        "mode": "local_editor_python",
        "status": "pass",
        "diagnostic_mode": "non-null-editor-render-capture-envelope",
        "live_editor_execution": True,
        "live_publication": False,
        "release_packaging": False,
        "production_level_mutation": False,
        "defaultlevel_mutation": False,
        "asset_cache_deleted": False,
        "cache_heuristic_used": False,
        "fake_success": False,
        "non_null_editor_render_capture_envelope_attempted": True,
        "non_null_editor_render_capture_envelope_completed": True,
        "non_null_editor_render_capture_envelope_source_validation_status": (
            "non_null_editor_render_capture_envelope_source_validation_pass"
        ),
        "non_null_editor_render_capture_envelope_source_validation_verified": True,
        "non_null_editor_render_capture_envelope_verified": False,
        "non_null_editor_render_capture_envelope_blocker": (
            "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
        ),
        "non_null_editor_render_capture_envelope_candidate_matrix": [
            {
                "id": "non_null_editor_viewport_screenshot_envelope",
                "selected": True,
                "result": "selected_source_validated_live_execution_deferred",
            },
            {
                "id": "atom_frame_capture_under_non_null_rhi",
                "selected": True,
                "result": "selected_source_validated_capture_request_deferred",
            },
            {
                "id": "safe_temp_visual_context_without_defaultlevel_save",
                "selected": True,
                "result": "selected_policy_pinned_scene_creation_deferred",
            },
            {
                "id": "non_null_runtime_renderer_harness",
                "selected": False,
                "result": "deferred",
            },
            {
                "id": "nullrenderer_visual_proof",
                "selected": False,
                "result": "rejected_blocked",
            },
            {
                "id": "apb_material_product_inventory_as_rendered_proof",
                "selected": False,
                "result": "rejected_readiness_only",
            },
            {
                "id": "screenshot_existence_only_as_material_proof",
                "selected": False,
                "result": "rejected_capture_readiness_only",
            },
            {
                "id": "production_defaultlevel_screenshot",
                "selected": False,
                "result": "rejected",
            },
            {
                "id": "understand_anything_graph_as_proof",
                "selected": False,
                "result": "rejected",
            },
            {
                "id": "claim_full_runtime_character_proof_after_capture_envelope_only",
                "selected": False,
                "result": "rejected",
            },
        ],
        "non_null_editor_render_capture_envelope_selected_strategy": (
            "source_validated_non_null_editor_capture_envelope_live_blocked"
        ),
        "non_null_editor_render_capture_rhi_requested": "dx12",
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
        "editor_visual_material_cleanup_verified": True,
        "editor_visual_material_selected_log_scan_passed": True,
        "visual_material_capture_readiness_verified": False,
        "visual_material_product_inventory_gate_verified": True,
        "visual_material_rendered_evidence_gate_attempted": False,
        "visual_material_rendered_evidence_gate_verified": False,
        "visual_material_gate_claimed": False,
        "visual_material_gate_verified": False,
        "full_runtime_character_visual_material_gate_verified": False,
        "full_runtime_character_proof_contract_pinned": True,
        "full_runtime_character_proof_contract_verified": True,
        "full_runtime_character_proof_satisfied_gates": [
            {"id": "spawn_instantiation", "verified": True},
            {"id": "component_wiring", "verified": True},
            {"id": "simple_motion_playback", "verified": True},
            {"id": "behavior_smoke", "verified": True},
            {"id": "selected_log_scan", "verified": True},
            {"id": "cleanup_recovery", "verified": True},
        ],
        "full_runtime_character_proof_unsatisfied_gates": [
            {
                "id": "visual_material",
                "verified": False,
                "blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
            }
        ],
        "full_runtime_character_proof_deferred_gates": [
            {
                "id": "visual_capture_surface",
                "verified": False,
                "blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
            },
            {
                "id": "repeated_behavior_scenario",
                "verified": False,
                "blocker": "blocked_by_full_runtime_character_repeated_behavior_scenario_deferred",
            },
        ],
        "runtime_character_behavior_smoke_verified": True,
        "runtime_character_animation_verified": True,
        "runtime_character_animation_component_wiring_verified": True,
        "runtime_character_proof_claimed": False,
        "runtime_character_proof_verified": False,
    }


def _non_null_visual_runner_readiness_contract_payload() -> dict:
    payload = _non_null_editor_render_capture_envelope_blocked_payload()
    payload.update(
        {
            "diagnostic_mode": "non-null-editor-visual-runner-readiness",
            "live_editor_execution": False,
            "non_null_editor_visual_runner_readiness_attempted": True,
            "non_null_editor_visual_runner_readiness_completed": True,
            "non_null_editor_visual_runner_readiness_source_validation_status": (
                "non_null_editor_visual_runner_readiness_source_validation_pass"
            ),
            "non_null_editor_visual_runner_readiness_source_validation_verified": True,
            "non_null_editor_visual_runner_readiness_verified": False,
            "non_null_editor_visual_runner_readiness_blocker": (
                "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
            ),
            "non_null_editor_visual_runner_readiness_candidate_matrix": [
                {
                    "id": "visible_desktop_session_readiness_check",
                    "selected": True,
                    "result": "selected_blocked_without_runner_verified_visible_session",
                    "blocker": "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session",
                },
                {
                    "id": "gpu_driver_rhi_readiness_check",
                    "selected": True,
                    "result": "selected_rhi_source_ready_gpu_driver_live_deferred",
                },
                {
                    "id": "non_null_editor_launch_without_screenshot",
                    "selected": False,
                    "result": "deferred_until_visible_desktop_and_gpu_readiness_pass",
                },
                {
                    "id": "safe_temp_visual_scene_display_contract",
                    "selected": True,
                    "result": "selected_contract_pinned",
                },
                {
                    "id": "capture_artifact_path_policy",
                    "selected": True,
                    "result": "selected_contract_pinned",
                },
                {
                    "id": "screenshot_capture_request_this_slice",
                    "selected": False,
                    "result": "deferred",
                },
                {
                    "id": "nullrenderer_visual_proof",
                    "selected": False,
                    "result": "rejected_blocked",
                },
                {
                    "id": "apb_material_product_inventory_as_rendered_proof",
                    "selected": False,
                    "result": "rejected_readiness_only",
                },
                {
                    "id": "screenshot_existence_only_as_material_proof",
                    "selected": False,
                    "result": "rejected_full_visual_material_proof",
                },
                {
                    "id": "production_defaultlevel_screenshot",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "understand_anything_graph_as_proof",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "claim_full_runtime_character_proof_after_readiness_only",
                    "selected": False,
                    "result": "rejected",
                },
            ],
            "non_null_editor_visual_runner_readiness_selected_strategy": (
                "source_validated_readiness_and_temp_scene_contract_live_launch_deferred"
            ),
            "visible_desktop_session_check_attempted": True,
            "visible_desktop_session_verified": False,
            "visible_desktop_session_blocker": (
                "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
            ),
            "gpu_or_driver_readiness_check_attempted": True,
            "gpu_or_driver_readiness_verified": False,
            "gpu_or_driver_readiness_blocker": "blocked_by_non_null_editor_render_capture_requires_gpu_or_driver",
            "selected_rhi": "dx12",
            "rhi_readiness_check_attempted": True,
            "rhi_readiness_verified": True,
            "rhi_readiness_blocker": "",
            "non_null_editor_launch_attempted": False,
            "non_null_editor_launch_completed": False,
            "non_null_editor_launch_verified": False,
            "non_null_editor_launch_exit_code": None,
            "non_null_editor_launch_blocker": (
                "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
            ),
            "null_renderer_used": False,
            "existing_nullrenderer_safe_editor_lane_preserved": True,
            "editor_temp_visual_scene_contract_attempted": True,
            "editor_temp_visual_scene_contract_pinned": True,
            "editor_temp_visual_scene_contract_verified": True,
            "editor_temp_visual_scene_contract_blocker": "",
            "editor_temp_visual_scene_approved_root": "Levels/_maxine_visual_smoke",
            "editor_temp_visual_scene_defaultlevel_mutation": False,
            "editor_temp_visual_scene_production_level_mutation": False,
            "editor_temp_visual_scene_cleanup_policy_verified": True,
            "editor_visual_material_capture_artifact_root": "artifacts/o3de-integration/editor-smoke",
            "editor_visual_material_capture_artifact_policy_verified": True,
            "editor_visual_material_capture_requested": False,
            "editor_visual_material_capture_completed": False,
            "editor_visual_material_capture_artifact_exists": False,
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
    return payload


def _non_null_desktop_rhi_readiness_contract_payload() -> dict:
    payload = _non_null_visual_runner_readiness_contract_payload()
    payload.update(
        {
            "diagnostic_mode": "non-null-editor-desktop-rhi-readiness",
            "non_null_editor_desktop_rhi_readiness_attempted": True,
            "non_null_editor_desktop_rhi_readiness_completed": True,
            "non_null_editor_desktop_rhi_readiness_source_validation_status": (
                "non_null_editor_desktop_rhi_readiness_source_validation_pass"
            ),
            "non_null_editor_desktop_rhi_readiness_source_validation_verified": True,
            "non_null_editor_desktop_rhi_readiness_verified": False,
            "non_null_editor_desktop_rhi_readiness_blocker": (
                "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
            ),
            "non_null_editor_desktop_rhi_readiness_candidate_matrix": [
                {
                    "id": "detect_visible_desktop_session_without_launching_editor",
                    "selected": True,
                    "result": "selected_safe_check",
                },
                {
                    "id": "detect_gpu_driver_readiness_without_launching_editor",
                    "selected": True,
                    "result": "selected_safe_check",
                },
                {
                    "id": "validate_selected_rhi_module_source_availability",
                    "selected": True,
                    "result": "selected_source_check",
                },
                {
                    "id": "live_non_null_editor_launch_without_screenshot",
                    "selected": False,
                    "result": "deferred_until_desktop_gpu_rhi_readiness_pass",
                },
                {
                    "id": "screenshot_capture_in_this_slice",
                    "selected": False,
                    "result": "deferred",
                },
                {
                    "id": "temp_visual_scene_creation_in_this_slice",
                    "selected": False,
                    "result": "deferred",
                },
                {
                    "id": "move_visual_capture_to_separate_runner",
                    "selected": False,
                    "result": "deferred_unless_current_runner_blocks",
                },
                {
                    "id": "nullrenderer_visual_proof",
                    "selected": False,
                    "result": "rejected_blocked",
                },
                {
                    "id": "apb_material_product_inventory_as_rendered_proof",
                    "selected": False,
                    "result": "rejected_readiness_only",
                },
                {
                    "id": "screenshot_existence_only_as_material_proof",
                    "selected": False,
                    "result": "rejected_full_visual_material_proof",
                },
                {
                    "id": "production_defaultlevel_screenshot",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "understand_anything_graph_as_proof",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "claim_full_runtime_character_proof_from_readiness_only",
                    "selected": False,
                    "result": "rejected",
                },
            ],
            "non_null_editor_desktop_rhi_readiness_selected_strategy": (
                "safe_desktop_gpu_rhi_readiness_checks_without_editor_launch"
            ),
            "visible_desktop_session_check_method": (
                "ProcessIdToSessionId+WTSGetActiveConsoleSessionId+OpenInputDesktop"
            ),
            "visible_desktop_session_state": "unknown_or_unverified",
            "windows_session_id": None,
            "windows_session_type": "unknown",
            "windows_session_interactive": False,
            "gpu_or_driver_readiness_check_method": "Win32_VideoController",
            "gpu_adapter_count": 0,
            "gpu_adapter_summary": [],
            "rhi_readiness_check_method": "O3DE Atom RHI source module scan",
            "rhi_fallback_considered": True,
            "rhi_fallback_selected": False,
        }
    )
    return payload


def _live_non_null_editor_launch_verified_payload() -> dict:
    payload = _non_null_desktop_rhi_readiness_contract_payload()
    payload.update(
        {
            "diagnostic_mode": "live-non-null-editor-launch",
            "live_editor_execution": True,
            "live_non_null_editor_launch_attempted": True,
            "live_non_null_editor_launch_completed": True,
            "live_non_null_editor_launch_verified": True,
            "live_non_null_editor_launch_blocker": "",
            "live_non_null_editor_launch_candidate_matrix": [
                {
                    "id": "live_non_null_editor_launch_without_screenshot",
                    "selected": True,
                    "result": "selected_launch_only_no_screenshot",
                },
                {
                    "id": "live_non_null_editor_launch_with_screenshot",
                    "selected": False,
                    "result": "deferred_not_this_slice",
                },
                {
                    "id": "temp_visual_scene_creation",
                    "selected": False,
                    "result": "deferred_not_this_slice",
                },
                {
                    "id": "preserve_nullrenderer_safe_editor_lane",
                    "selected": True,
                    "result": "selected_required",
                },
                {
                    "id": "dx12_rhi",
                    "selected": True,
                    "result": "selected_default",
                },
                {
                    "id": "vulkan_fallback",
                    "selected": False,
                    "result": "deferred_unless_dx12_blocks",
                },
                {
                    "id": "use_production_defaultlevel_for_launch_proof",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "infer_visual_proof_from_non_null_launch",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "understand_anything_graph_as_proof",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "claim_full_runtime_character_proof_from_launch_readiness",
                    "selected": False,
                    "result": "rejected",
                },
            ],
            "live_non_null_editor_launch_selected_strategy": "bounded_live_non_null_editor_launch_no_screenshot",
            "live_non_null_editor_launch_source_validation_status": "live_non_null_editor_launch_source_validation_pass",
            "live_non_null_editor_launch_source_validation_verified": True,
            "live_non_null_editor_launch_command": [
                "Editor.exe",
                "-rhi=dx12",
                "--skipWelcomeScreenDialog",
                "--autotest_mode",
                "--project-path",
                "<project>",
                "--runpython",
                "editor_live_non_null_launch_smoke.py",
            ],
            "live_non_null_editor_launch_selected_rhi": "dx12",
            "live_non_null_editor_launch_null_renderer_used": False,
            "live_non_null_editor_launch_editor_executable": "<editor>",
            "live_non_null_editor_launch_project_path": "<project>",
            "live_non_null_editor_launch_wrapper_path": "tools/o3de/editor_python/editor_live_non_null_launch_smoke.py",
            "live_non_null_editor_launch_wrapper_bootstrap_verified": True,
            "live_non_null_editor_launch_python_wrapper_executed": True,
            "live_non_null_editor_launch_exit_code": 0,
            "live_non_null_editor_launch_exit_code_hex": "0x00000000",
            "live_non_null_editor_launch_timeout": False,
            "live_non_null_editor_launch_killed": False,
            "live_non_null_editor_launch_stdout_ref": "artifacts/o3de-integration/editor-smoke/stdout.txt",
            "live_non_null_editor_launch_stderr_ref": "artifacts/o3de-integration/editor-smoke/stderr.txt",
            "live_non_null_editor_launch_log_ref": "",
            "live_non_null_editor_launch_selected_log_scan_passed": True,
            "live_non_null_editor_launch_selected_log_blocking_matches": [],
            "non_null_editor_desktop_rhi_readiness_verified": True,
            "non_null_editor_desktop_rhi_readiness_blocker": "",
            "visible_desktop_session_verified": True,
            "visible_desktop_session_state": "available_console_input_desktop",
            "windows_session_type": "console",
            "windows_session_interactive": True,
            "gpu_or_driver_readiness_verified": True,
            "gpu_adapter_count": 2,
            "gpu_adapter_summary": [{"name": "Adapter A", "driver_version": "1.2.3", "status": "OK"}],
            "rhi_readiness_verified": True,
            "selected_rhi": "dx12",
            "rhi_fallback_considered": True,
            "rhi_fallback_selected": False,
            "non_null_editor_launch_attempted": True,
            "non_null_editor_launch_completed": True,
            "non_null_editor_launch_verified": True,
            "non_null_editor_launch_exit_code": 0,
            "non_null_editor_launch_blocker": "",
            "non_null_editor_render_capture_envelope_blocker": "blocked_by_visual_material_proof_requires_rendered_evidence_capture",
            "non_null_editor_render_capture_editor_launched": True,
            "non_null_editor_render_capture_editor_exited_cleanly": True,
            "editor_temp_visual_scene_contract_pinned": True,
            "editor_temp_visual_scene_contract_verified": True,
            "editor_temp_visual_scene_created": False,
            "editor_visual_material_temp_scene_created": False,
            "editor_visual_material_capture_requested": False,
            "editor_visual_material_capture_completed": False,
            "visual_material_capture_readiness_verified": False,
            "visual_material_rendered_evidence_gate_attempted": False,
            "visual_material_rendered_evidence_gate_verified": False,
            "visual_material_gate_claimed": False,
            "visual_material_gate_verified": False,
            "full_runtime_character_visual_material_gate_verified": False,
            "full_runtime_character_proof_unsatisfied_gates": [
                {
                    "id": "visual_material",
                    "verified": False,
                    "blocker": "blocked_by_visual_material_proof_requires_rendered_evidence_capture",
                }
            ],
            "full_runtime_character_proof_deferred_gates": [
                {
                    "id": "visual_capture_surface",
                    "verified": False,
                    "blocker": "blocked_by_visual_material_proof_requires_rendered_evidence_capture",
                },
                {
                    "id": "repeated_behavior_scenario",
                    "verified": False,
                    "blocker": "blocked_by_full_runtime_character_repeated_behavior_scenario_deferred",
                },
            ],
        }
    )
    return payload


def _editor_screenshot_capture_artifact_readiness_verified_payload() -> dict:
    payload = _live_non_null_editor_launch_verified_payload()
    payload.update(
        {
            "diagnostic_mode": "editor-screenshot-capture-artifact-readiness",
            "editor_screenshot_capture_artifact_readiness_attempted": True,
            "editor_screenshot_capture_artifact_readiness_completed": True,
            "editor_screenshot_capture_artifact_readiness_verified": True,
            "editor_screenshot_capture_artifact_readiness_blocker": "",
            "editor_screenshot_capture_artifact_readiness_candidate_matrix": [
                {
                    "id": "atom_frame_capture_request_bus_screenshot",
                    "candidate": "screenshot capture readiness through Atom FrameCaptureRequestBus",
                    "selected": True,
                    "result": "verified_capture_artifact_readiness",
                },
                {
                    "id": "screenshot_without_temp_visual_scene",
                    "candidate": "screenshot capture without temp visual scene",
                    "selected": True,
                    "result": "verified_active_window_capture_without_scene_mutation",
                },
                {
                    "id": "screenshot_after_temp_visual_scene_creation",
                    "candidate": "screenshot capture after temp visual scene creation",
                    "selected": False,
                    "result": "deferred",
                },
                {
                    "id": "validate_capture_artifact_existence_format_dimensions_size",
                    "candidate": "validate capture artifact existence/format/dimensions/size",
                    "selected": True,
                    "result": "verified",
                },
                {
                    "id": "nonblank_validation",
                    "candidate": "nonblank validation",
                    "selected": False,
                    "result": "deferred",
                },
                {
                    "id": "character_material_presence_validation",
                    "candidate": "character/material presence validation",
                    "selected": False,
                    "result": "deferred",
                },
                {
                    "id": "infer_visual_material_proof_from_screenshot_existence",
                    "candidate": "infer visual/material proof from screenshot existence",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "infer_full_runtime_character_proof_from_screenshot_readiness",
                    "candidate": "infer full runtime character proof from screenshot readiness",
                    "selected": False,
                    "result": "rejected",
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
            ],
            "editor_screenshot_capture_artifact_readiness_selected_strategy": (
                "bounded_live_editor_screenshot_capture_artifact_readiness"
            ),
            "editor_screenshot_capture_artifact_readiness_source_validation_status": (
                "editor_screenshot_capture_artifact_readiness_source_validation_pass"
            ),
            "editor_screenshot_capture_artifact_readiness_source_validation_verified": True,
            "live_non_null_editor_launch_command": [
                "Editor.exe",
                "-rhi=dx12",
                "--skipWelcomeScreenDialog",
                "--autotest_mode",
                "--project-path",
                "<project>",
                "--runpython",
                "editor_screenshot_capture_artifact_readiness_smoke.py",
            ],
            "live_non_null_editor_launch_wrapper_path": (
                "tools/o3de/editor_python/editor_screenshot_capture_artifact_readiness_smoke.py"
            ),
            "editor_visual_material_capture_api_found": True,
            "editor_visual_material_capture_api_available_under_non_null_rhi": True,
            "editor_visual_material_capture_api_used": "azlmbr.atom.FrameCaptureRequestBus.CaptureScreenshot",
            "editor_visual_material_capture_requested": True,
            "editor_visual_material_capture_request_accepted": True,
            "editor_visual_material_capture_completed": True,
            "editor_visual_material_capture_completion_source": "FrameCaptureNotificationBus.OnFrameCaptureFinished",
            "editor_visual_material_capture_artifact_path": (
                "artifacts/o3de-integration/editor-smoke/editor_screenshot_capture_artifact_readiness.png"
            ),
            "editor_visual_material_capture_artifact_exists": True,
            "editor_visual_material_capture_artifact_format": "png",
            "editor_visual_material_capture_artifact_width": 64,
            "editor_visual_material_capture_artifact_height": 32,
            "editor_visual_material_capture_artifact_size_bytes": 512,
            "editor_visual_material_capture_artifact_sha256": "a" * 64,
            "editor_visual_material_capture_content_validation_attempted": False,
            "editor_visual_material_capture_content_validation_verified": False,
            "editor_visual_material_nonblank_validation_attempted": False,
            "editor_visual_material_nonblank_validation_verified": False,
            "editor_visual_material_character_presence_validation_verified": False,
            "editor_visual_material_material_presence_validation_verified": False,
            "editor_visual_material_temp_scene_created": False,
            "editor_temp_visual_scene_created": False,
            "editor_temp_visual_scene_defaultlevel_mutation": False,
            "editor_temp_visual_scene_production_level_mutation": False,
            "editor_visual_material_defaultlevel_mutation": False,
            "editor_visual_material_production_level_mutation": False,
            "editor_visual_material_selected_log_scan_passed": True,
            "visual_material_capture_readiness_verified": True,
            "visual_material_rendered_evidence_gate_attempted": False,
            "visual_material_rendered_evidence_gate_verified": False,
            "visual_material_gate_claimed": False,
            "visual_material_gate_verified": False,
            "full_runtime_character_visual_material_gate_verified": False,
            "full_runtime_character_proof_unsatisfied_gates": [
                {
                    "id": "visual_material",
                    "verified": False,
                    "blocker": "blocked_by_visual_material_content_validation_deferred_after_capture_readiness",
                }
            ],
            "full_runtime_character_proof_deferred_gates": [
                {
                    "id": "visual_capture_surface",
                    "verified": False,
                    "blocker": "blocked_by_visual_material_content_validation_deferred_after_capture_readiness",
                },
                {
                    "id": "repeated_behavior_scenario",
                    "verified": False,
                    "blocker": "blocked_by_full_runtime_character_repeated_behavior_scenario_deferred",
                },
            ],
        }
    )
    return payload


def _active_viewport_temp_scene_readiness_payload() -> dict:
    payload = _live_non_null_editor_launch_verified_payload()
    satisfied_gates = list(payload.get("full_runtime_character_proof_satisfied_gates", []))
    if "visual_capture_surface" not in satisfied_gates:
        satisfied_gates.append("visual_capture_surface")
    payload.update(
        {
            "diagnostic_mode": "editor-active-viewport-temp-scene-readiness",
            "editor_active_viewport_temp_scene_readiness_attempted": True,
            "editor_active_viewport_temp_scene_readiness_completed": True,
            "editor_active_viewport_temp_scene_readiness_verified": True,
            "editor_active_viewport_temp_scene_readiness_blocker": "",
            "editor_active_viewport_temp_scene_readiness_candidate_matrix": [
                {
                    "id": "active_editor_viewport_window_readiness_under_live_non_null_launch",
                    "selected": True,
                    "result": "blocked_window_handle_unverified",
                    "blocker": "blocked_by_editor_active_viewport_window_handle_unavailable",
                },
                {
                    "id": "frame_capture_default_viewport_window_capture_target",
                    "selected": True,
                    "result": "blocked_default_window_handle_unverified",
                    "blocker": "blocked_by_editor_active_viewport_window_handle_unavailable",
                },
                {
                    "id": "temp_visual_scene_display_context_levels_maxine_visual_smoke",
                    "selected": True,
                    "result": "verified_source_validated_contract",
                },
                {
                    "id": "create_temp_visual_scene_this_slice",
                    "selected": False,
                    "result": "deferred_contract_only_no_scene_mutation",
                },
                {
                    "id": "screenshot_capture_request_this_slice",
                    "selected": False,
                    "result": "deferred_until_capture_target_window_handle_ready",
                },
                {
                    "id": "approved_character_display_this_slice",
                    "selected": False,
                    "result": "deferred",
                },
                {
                    "id": "infer_visual_material_proof_from_viewport_readiness",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "infer_visual_material_proof_from_temp_scene_readiness",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "production_defaultlevel_viewport_or_screenshot",
                    "selected": False,
                    "result": "rejected",
                },
                {
                    "id": "understand_anything_graph_as_proof",
                    "selected": False,
                    "result": "rejected",
                },
            ],
            "editor_active_viewport_temp_scene_readiness_selected_strategy": (
                "source_validated_temp_visual_scene_contract_no_capture"
            ),
            "editor_active_viewport_temp_scene_readiness_source_validation_status": (
                "editor_active_viewport_temp_scene_readiness_source_validation_pass"
            ),
            "editor_active_viewport_temp_scene_readiness_source_validation_verified": True,
            "live_non_null_editor_launch_command": [
                "Editor.exe",
                "-rhi=dx12",
                "--skipWelcomeScreenDialog",
                "--autotest_mode",
                "--project-path",
                "<project>",
                "--runpython",
                "editor_active_viewport_temp_scene_readiness_smoke.py",
            ],
            "live_non_null_editor_launch_wrapper_path": (
                "tools/o3de/editor_python/editor_active_viewport_temp_scene_readiness_smoke.py"
            ),
            "editor_active_viewport_readiness_attempted": True,
            "editor_active_viewport_readiness_verified": False,
            "editor_active_viewport_check_method": (
                "azlmbr.legacy.general.get_viewport_count/get_active_viewport/get_viewport_size/update_viewport"
            ),
            "editor_active_viewport_state": "not_verified_no_safe_python_window_handle_probe",
            "editor_active_viewport_blocker": "blocked_by_editor_active_viewport_window_handle_unavailable",
            "editor_active_viewport_window_handle_available": False,
            "editor_active_viewport_render_ready": False,
            "editor_frame_capture_target_readiness_attempted": True,
            "editor_frame_capture_target_readiness_verified": False,
            "editor_frame_capture_target_blocker": "blocked_by_editor_active_viewport_window_handle_unavailable",
            "editor_temp_visual_scene_readiness_attempted": True,
            "editor_temp_visual_scene_readiness_verified": True,
            "editor_temp_visual_scene_contract_pinned": True,
            "editor_temp_visual_scene_contract_verified": True,
            "editor_temp_visual_scene_approved_root": "Levels/_maxine_visual_smoke",
            "editor_temp_visual_scene_path": "Levels/_maxine_visual_smoke/editor_active_viewport_temp_scene_readiness",
            "editor_temp_visual_scene_created": False,
            "editor_temp_visual_scene_cleanup_verified": True,
            "editor_temp_visual_scene_cleanup_policy_verified": True,
            "editor_temp_visual_scene_defaultlevel_mutation": False,
            "editor_temp_visual_scene_production_level_mutation": False,
            "editor_visual_material_capture_target_readiness_verified": True,
            "editor_visual_material_capture_artifact_root": "artifacts/o3de-integration/editor-smoke",
            "editor_visual_material_capture_requested": False,
            "editor_visual_material_capture_request_accepted": False,
            "editor_visual_material_capture_completed": False,
            "visual_material_capture_readiness_verified": False,
            "visual_material_rendered_evidence_gate_attempted": False,
            "visual_material_rendered_evidence_gate_verified": False,
            "visual_material_gate_claimed": False,
            "visual_material_gate_verified": False,
            "full_runtime_character_visual_material_gate_verified": False,
            "full_runtime_character_proof_satisfied_gates": satisfied_gates,
            "full_runtime_character_proof_unsatisfied_gates": [
                {
                    "id": "visual_material",
                    "verified": False,
                    "blocker": "blocked_by_visual_material_proof_requires_rendered_evidence_capture",
                }
            ],
            "full_runtime_character_proof_deferred_gates": [
                {
                    "id": "repeated_behavior_scenario",
                    "verified": False,
                    "blocker": "blocked_by_full_runtime_character_repeated_behavior_scenario_deferred",
                }
            ],
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
    )
    return payload


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
    if diagnostic_mode == "approved-animation-component-wiring-generation":
        binding_payload.update(
            {
                "approved_runtime_animation_component_wiring_editor_generation_attempted": True,
                "approved_runtime_animation_component_wiring_editor_generation_completed": True,
                "approved_runtime_animation_component_wiring_editor_generation_verified": False,
                "approved_runtime_animation_component_wiring_editor_generation_blocker": "blocked_by_editor_generated_prefab_update_save_semantics",
                "approved_runtime_animation_component_wiring_source_prefab_path": "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "approved_runtime_animation_component_wiring_source_prefab_modified": False,
                "approved_runtime_animation_component_wiring_editor_generated_update_used": False,
                "approved_runtime_animation_component_wiring_hand_authored_unknown_json_used": False,
                "approved_runtime_animation_component_wiring_actor_component_added": True,
                "approved_runtime_animation_component_wiring_simple_motion_component_added": True,
                "approved_runtime_animation_component_wiring_anim_graph_component_added": False,
                "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": True,
                "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": True,
                "approved_runtime_animation_component_wiring_actor_asset_id": "{11111111-1111-1111-1111-111111111111}:00000001",
                "approved_runtime_animation_component_wiring_motion_asset_id": "{22222222-2222-2222-2222-222222222222}:00000002",
                "approved_runtime_animation_component_wiring_property_readback_verified": True,
                "approved_runtime_animation_component_wiring_prefab_save_verified": False,
                "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": False,
                "runtime_character_animation_component_wiring_claimed": False,
                "runtime_character_animation_component_wiring_verified": False,
                "runtime_character_animation_claimed": False,
                "runtime_character_animation_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
    if diagnostic_mode == "approved-prefab-save-update-automation-surface":
        binding_payload.update(
            {
                "approved_prefab_save_update_automation_surface_diagnostic_attempted": True,
                "approved_prefab_save_update_automation_surface_diagnostic_completed": True,
                "approved_prefab_save_update_automation_surface_found": False,
                "approved_prefab_save_update_automation_surface_verified": False,
                "approved_prefab_save_update_automation_surface_blocker": "blocked_by_prefab_save_interface_not_available_to_automation",
                "approved_prefab_save_update_source_validation_status": "pass",
                "approved_prefab_save_update_source_validation_verified": True,
                "approved_prefab_save_update_behavior_context_exposed": False,
                "approved_prefab_save_update_behavior_context_observed_events": [
                    "CreatePrefabInMemory",
                    "InstantiatePrefab",
                ],
                "approved_prefab_save_update_behavior_context_missing_events": [
                    "CreatePrefabAndSaveToDisk",
                    "SavePrefab",
                ],
                "approved_prefab_save_update_bridge_added": False,
                "approved_prefab_save_update_bridge_verified": False,
                "approved_prefab_save_update_rejected_defaultlevel_path": True,
                "approved_prefab_save_update_rejected_production_level_path": True,
                "approved_prefab_save_update_scratch_save_attempted": False,
                "approved_prefab_save_update_scratch_save_verified": False,
                "approved_prefab_save_update_scratch_cleanup_verified": True,
                "approved_prefab_save_update_before_hash": "",
                "approved_prefab_save_update_after_hash": "",
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
        )
    if diagnostic_mode == "approved-prefab-save-update-bridge":
        binding_payload.update(
            {
                "approved_prefab_save_update_bridge_diagnostic_attempted": True,
                "approved_prefab_save_update_bridge_diagnostic_completed": True,
                "approved_prefab_save_update_bridge_source_validation_status": "pass",
                "approved_prefab_save_update_bridge_source_validation_verified": True,
                "approved_prefab_save_update_bridge_added": False,
                "approved_prefab_save_update_bridge_verified": False,
                "approved_prefab_save_update_bridge_blocker": "blocked_by_prefab_save_bridge_requires_editor_gem_registration",
                "approved_prefab_save_update_bridge_behavior_context_reflected": False,
                "approved_prefab_save_update_bridge_callable_from_editor_python": False,
                "approved_prefab_save_update_automation_surface_verified": False,
                "approved_prefab_save_update_rejected_defaultlevel_path": True,
                "approved_prefab_save_update_rejected_production_level_path": True,
                "approved_prefab_save_update_rejected_generated_product_path": True,
                "approved_prefab_save_update_scratch_save_attempted": False,
                "approved_prefab_save_update_scratch_save_verified": False,
                "approved_prefab_save_update_scratch_reload_or_parse_verified": False,
                "approved_prefab_save_update_scratch_cleanup_verified": True,
                "approved_prefab_save_update_generated_products_committed": False,
                "approved_runtime_animation_component_wiring_source_prefab_modified": False,
                "runtime_character_animation_component_wiring_claimed": False,
                "runtime_character_animation_component_wiring_verified": False,
                "runtime_character_animation_claimed": False,
                "runtime_character_animation_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
    if diagnostic_mode == "approved-prefab-save-update-bridge-host":
        binding_payload.update(
            {
                "approved_prefab_save_update_bridge_host_diagnostic_attempted": True,
                "approved_prefab_save_update_bridge_host_diagnostic_completed": True,
                "approved_prefab_save_update_bridge_host_source_validation_status": "pass",
                "approved_prefab_save_update_bridge_host_source_validation_verified": True,
                "approved_prefab_save_update_bridge_host_added": True,
                "approved_prefab_save_update_bridge_host_registered": True,
                "approved_prefab_save_update_bridge_host_build_required": True,
                "approved_prefab_save_update_bridge_host_build_verified": True,
                "approved_prefab_save_update_bridge_host_target_name": "MaxineRuntimeExitFixture.Editor",
                "approved_prefab_save_update_bridge_host_module_name": "Gem_MaxineRuntimeExitFixture_Editor",
                "approved_prefab_save_update_bridge_host_aztoolsframework_dependency_present": True,
                "approved_prefab_save_update_bridge_host_behavior_context_reflected": True,
                "approved_prefab_save_update_bridge_host_callable_from_editor_python": True,
                "approved_prefab_save_update_bridge_host_runtime_excluded": True,
                "approved_prefab_save_update_bridge_host_blocker": "",
                "approved_prefab_save_update_bridge_added": True,
                "approved_prefab_save_update_bridge_verified": False,
                "approved_prefab_save_update_bridge_callable_from_editor_python": False,
                "approved_prefab_save_update_automation_surface_verified": False,
                "approved_prefab_save_update_scratch_save_attempted": False,
                "approved_prefab_save_update_scratch_save_verified": False,
                "approved_prefab_save_update_scratch_reload_or_parse_verified": False,
                "approved_prefab_save_update_scratch_cleanup_verified": True,
                "approved_runtime_animation_component_wiring_source_prefab_modified": False,
                "runtime_character_animation_component_wiring_claimed": False,
                "runtime_character_animation_component_wiring_verified": False,
                "runtime_character_animation_claimed": False,
                "runtime_character_animation_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
    if diagnostic_mode == "approved-prefab-save-update-route":
        binding_payload.update(
            {
                "approved_prefab_save_update_route_diagnostic_attempted": True,
                "approved_prefab_save_update_route_diagnostic_completed": True,
                "approved_prefab_save_update_route_source_validation_status": "pass",
                "approved_prefab_save_update_route_source_validation_verified": True,
                "approved_prefab_save_update_route_added": True,
                "approved_prefab_save_update_route_behavior_context_reflected": True,
                "approved_prefab_save_update_route_callable_from_editor_python": True,
                "approved_prefab_save_update_route_blocker": "",
                "approved_prefab_save_update_bridge_host_callable_from_editor_python": True,
                "approved_prefab_save_update_bridge_added": True,
                "approved_prefab_save_update_bridge_verified": True,
                "approved_prefab_save_update_bridge_callable_from_editor_python": True,
                "approved_prefab_save_update_automation_surface_verified": True,
                "approved_prefab_save_update_rejected_defaultlevel_path": True,
                "approved_prefab_save_update_rejected_production_level_path": True,
                "approved_prefab_save_update_rejected_generated_product_path": True,
                "approved_prefab_save_update_rejected_unapproved_absolute_path": True,
                "approved_prefab_save_update_rejected_path_traversal": True,
                "approved_prefab_save_update_scratch_save_attempted": True,
                "approved_prefab_save_update_scratch_save_verified": True,
                "approved_prefab_save_update_scratch_reload_or_parse_verified": True,
                "approved_prefab_save_update_scratch_cleanup_verified": True,
                "approved_prefab_save_update_before_hash": "",
                "approved_prefab_save_update_after_hash": "0" * 64,
                "approved_prefab_save_update_generated_products_committed": False,
                "approved_runtime_animation_component_wiring_source_prefab_modified": False,
                "runtime_character_animation_component_wiring_claimed": False,
                "runtime_character_animation_component_wiring_verified": False,
                "runtime_character_animation_claimed": False,
                "runtime_character_animation_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
    if diagnostic_mode == "approved-source-prefab-actor-simple-motion-wiring":
        binding_payload.update(
            {
                "approved_source_prefab_actor_simple_motion_wiring_attempted": True,
                "approved_source_prefab_actor_simple_motion_wiring_completed": True,
                "approved_source_prefab_actor_simple_motion_wiring_verified": True,
                "approved_source_prefab_actor_simple_motion_wiring_blocker": "",
                "approved_source_prefab_actor_simple_motion_wiring_source_validation_status": "pass",
                "approved_source_prefab_actor_simple_motion_wiring_source_validation_verified": True,
                "approved_source_prefab_actor_simple_motion_wiring_candidate_matrix": [],
                "approved_source_prefab_actor_simple_motion_wiring_selected_strategy": "approved_source_prefab_actor_plus_simple_motion_editor_generated_update",
                "approved_source_prefab_path": "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "approved_source_prefab_project_path_redacted": "%USERPROFILE%/O3DE/Projects/MAXINE_GoldenCorpus/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "approved_source_prefab_before_hash": "1" * 64,
                "approved_source_prefab_after_hash": "2" * 64,
                "approved_source_prefab_project_before_hash": "3" * 64,
                "approved_source_prefab_project_after_hash": "4" * 64,
                "approved_source_prefab_modified": True,
                "approved_source_prefab_changed_this_run": True,
                "approved_source_prefab_persisted_wiring_markers_verified": True,
                "approved_source_prefab_project_persisted_wiring_markers_verified": True,
                "approved_source_prefab_component_overrides_applied": True,
                "approved_source_prefab_component_override_refs": {
                    "actor_component_ref_status": "pass",
                    "simple_motion_component_ref_status": "pass",
                },
                "approved_source_prefab_component_override_apply_status": {
                    "attempted": True,
                    "callable": True,
                    "applied": True,
                },
                "approved_source_prefab_entity_changes_committed": True,
                "approved_source_prefab_entity_change_commit_status": {
                    "attempted": True,
                    "callable": True,
                    "committed": True,
                },
                "approved_source_prefab_update_route_used": "azlmbr.maxine.prefab_bridge.save_approved_source_prefab_wiring",
                "approved_source_prefab_save_verified": True,
                "approved_source_prefab_actor_component_added": True,
                "approved_source_prefab_simple_motion_component_added": True,
                "approved_source_prefab_actor_asset_assignment_verified": True,
                "approved_source_prefab_motion_asset_assignment_verified": True,
                "approved_source_prefab_actor_asset_id": "{11111111-1111-1111-1111-111111111111}:00000001",
                "approved_source_prefab_motion_asset_id": "{22222222-2222-2222-2222-222222222222}:00000002",
                "approved_source_prefab_property_readback_verified": True,
                "approved_source_prefab_defaultlevel_mutation": False,
                "approved_source_prefab_production_level_mutation": False,
                "approved_source_prefab_hand_authored_unknown_json_used": False,
                "approved_spawnable_regenerated_or_found": False,
                "approved_runtime_animation_component_wiring_editor_generation_attempted": True,
                "approved_runtime_animation_component_wiring_editor_generation_completed": True,
                "approved_runtime_animation_component_wiring_editor_generation_verified": True,
                "approved_runtime_animation_component_wiring_editor_generation_blocker": "",
                "approved_runtime_animation_component_wiring_source_prefab_path": "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "approved_runtime_animation_component_wiring_source_prefab_modified": True,
                "approved_runtime_animation_component_wiring_editor_generated_update_used": True,
                "approved_runtime_animation_component_wiring_hand_authored_unknown_json_used": False,
                "approved_runtime_animation_component_wiring_actor_component_added": True,
                "approved_runtime_animation_component_wiring_simple_motion_component_added": True,
                "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": True,
                "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": True,
                "approved_runtime_animation_component_wiring_prefab_save_verified": True,
                "runtime_character_animation_component_wiring_claimed": False,
                "runtime_character_animation_component_wiring_verified": False,
                "runtime_character_animation_claimed": False,
                "runtime_character_animation_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
    if diagnostic_mode == "approved-source-prefab-propagation-apply-step":
        binding_payload.update(
            {
                "approved_source_prefab_propagation_apply_step_attempted": True,
                "approved_source_prefab_propagation_apply_step_completed": True,
                "approved_source_prefab_propagation_apply_step_verified": False,
                "approved_source_prefab_propagation_apply_step_blocker": "blocked_by_prefab_instance_to_template_propagation_requires_parent_link_context",
                "approved_source_prefab_propagation_apply_step_source_validation_status": "pass",
                "approved_source_prefab_propagation_apply_step_source_validation_verified": True,
                "approved_source_prefab_propagation_apply_step_candidate_matrix": [],
                "approved_source_prefab_propagation_apply_step_selected_strategy": "pin_parent_focus_link_override_apply_requirement",
                "approved_source_prefab_propagation_api_used": "source_validation_only",
                "approved_source_prefab_component_overrides_detected": False,
                "approved_source_prefab_component_overrides_applied": False,
                "approved_source_prefab_entity_changes_committed": False,
                "approved_source_prefab_template_dom_updated": False,
                "approved_source_prefab_path": "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "approved_source_prefab_before_hash": "1" * 64,
                "approved_source_prefab_after_hash": "1" * 64,
                "approved_source_prefab_modified": False,
                "approved_source_prefab_update_route_used": "not_run_source_validation_only",
                "approved_source_prefab_save_verified": False,
                "approved_source_prefab_actor_component_added": False,
                "approved_source_prefab_simple_motion_component_added": False,
                "approved_source_prefab_actor_asset_assignment_verified": False,
                "approved_source_prefab_motion_asset_assignment_verified": False,
                "approved_source_prefab_property_readback_verified": False,
                "approved_source_prefab_persisted_actor_asset_marker_verified": False,
                "approved_source_prefab_persisted_motion_asset_marker_verified": False,
                "approved_source_prefab_persisted_wiring_markers_verified": False,
                "approved_source_prefab_defaultlevel_mutation": False,
                "approved_source_prefab_production_level_mutation": False,
                "approved_source_prefab_hand_authored_unknown_json_used": False,
                "approved_spawnable_regenerated_or_found": False,
                "runtime_character_animation_component_wiring_claimed": False,
                "runtime_character_animation_component_wiring_verified": False,
                "runtime_character_animation_claimed": False,
                "runtime_character_animation_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
    if diagnostic_mode == "approved-source-prefab-parent-link-override-apply-route":
        binding_payload.update(
            {
                "approved_source_prefab_parent_link_override_apply_route_attempted": True,
                "approved_source_prefab_parent_link_override_apply_route_completed": True,
                "approved_source_prefab_parent_link_override_apply_route_verified": True,
                "approved_source_prefab_parent_link_override_apply_route_blocker": "",
                "approved_source_prefab_parent_link_override_apply_source_validation_status": "pass",
                "approved_source_prefab_parent_link_override_apply_source_validation_verified": True,
                "approved_source_prefab_parent_link_override_apply_candidate_matrix": [],
                "approved_source_prefab_parent_link_override_apply_selected_strategy": "approved_source_prefab_parent_focus_link_context_component_override_apply",
                "approved_source_prefab_entity_ownership_checked": True,
                "approved_source_prefab_entity_ownership_verified": True,
                "approved_source_prefab_entity_owning_prefab_path": "C:/Users/example/O3DE/Projects/MAXINE_GoldenCorpus/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "approved_source_prefab_entity_owning_prefab_matches_requested_path": True,
                "approved_source_prefab_component_ownership_checked": True,
                "approved_source_prefab_component_ownership_verified": True,
                "approved_source_prefab_entity_ownership_blocker": "",
                "approved_source_prefab_parent_focus_context_required": True,
                "approved_source_prefab_parent_focus_context_available": True,
                "approved_source_prefab_parent_focus_context_applied": True,
                "approved_source_prefab_parent_focus_context_restored": True,
                "approved_source_prefab_link_context_required": True,
                "approved_source_prefab_link_context_available": True,
                "approved_source_prefab_component_override_paths_detected": True,
                "approved_source_prefab_component_overrides_detected": True,
                "approved_source_prefab_component_overrides_applied": True,
                "approved_source_prefab_link_overrides_applied": False,
                "approved_source_prefab_push_overrides_to_prefab_attempted": True,
                "approved_source_prefab_push_overrides_to_prefab_verified": True,
                "approved_source_prefab_template_dom_updated": True,
                "approved_source_prefab_propagation_apply_step_attempted": True,
                "approved_source_prefab_propagation_apply_step_completed": True,
                "approved_source_prefab_propagation_apply_step_verified": True,
                "approved_source_prefab_propagation_apply_step_blocker": "",
                "approved_source_prefab_actor_simple_motion_wiring_attempted": True,
                "approved_source_prefab_actor_simple_motion_wiring_completed": True,
                "approved_source_prefab_actor_simple_motion_wiring_verified": True,
                "approved_source_prefab_actor_simple_motion_wiring_blocker": "",
                "approved_source_prefab_path": "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "approved_source_prefab_before_hash": "1" * 64,
                "approved_source_prefab_after_hash": "2" * 64,
                "approved_source_prefab_modified": True,
                "approved_source_prefab_changed_this_run": True,
                "approved_source_prefab_update_route_used": "azlmbr.maxine.prefab_bridge.apply_approved_source_prefab_parent_link_component_overrides",
                "approved_source_prefab_save_verified": True,
                "approved_source_prefab_actor_component_added": True,
                "approved_source_prefab_simple_motion_component_added": True,
                "approved_source_prefab_actor_asset_assignment_verified": True,
                "approved_source_prefab_motion_asset_assignment_verified": True,
                "approved_source_prefab_actor_asset_id": "{11111111-1111-1111-1111-111111111111}:00000001",
                "approved_source_prefab_motion_asset_id": "{22222222-2222-2222-2222-222222222222}:00000002",
                "approved_source_prefab_property_readback_verified": True,
                "approved_source_prefab_persisted_actor_asset_marker_verified": True,
                "approved_source_prefab_persisted_motion_asset_marker_verified": True,
                "approved_source_prefab_persisted_wiring_markers_verified": True,
                "approved_source_prefab_marker_presence_verified": True,
                "approved_source_prefab_marker_persistence_verified_this_run": True,
                "approved_source_prefab_marker_persistence_blocker": "",
                "approved_source_prefab_defaultlevel_mutation": False,
                "approved_source_prefab_production_level_mutation": False,
                "approved_source_prefab_hand_authored_unknown_json_used": False,
                "approved_spawnable_regenerated_or_found": False,
                "runtime_character_animation_component_wiring_claimed": False,
                "runtime_character_animation_component_wiring_verified": False,
                "runtime_character_animation_claimed": False,
                "runtime_character_animation_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
    if diagnostic_mode == "approved-source-prefab-override-path-generation-template-update":
        binding_payload.update(
            {
                "approved_source_prefab_override_path_generation_template_update_attempted": True,
                "approved_source_prefab_override_path_generation_template_update_completed": True,
                "approved_source_prefab_override_path_generation_template_update_verified": True,
                "approved_source_prefab_override_path_generation_template_update_blocker": "",
                "approved_source_prefab_override_path_generation_template_update_source_validation_status": "pass",
                "approved_source_prefab_override_path_generation_template_update_source_validation_verified": True,
                "approved_source_prefab_override_path_generation_template_update_candidate_matrix": [],
                "approved_source_prefab_override_path_generation_template_update_selected_strategy": "source_backed_serialized_entity_patch_entity_in_template",
                "approved_source_prefab_entity_ownership_checked": True,
                "approved_source_prefab_entity_ownership_verified": True,
                "approved_source_prefab_entity_owning_prefab_path": "C:/Users/example/O3DE/Projects/MAXINE_GoldenCorpus/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "approved_source_prefab_entity_owning_prefab_matches_requested_path": True,
                "approved_source_prefab_component_ownership_checked": True,
                "approved_source_prefab_component_ownership_verified": True,
                "approved_source_prefab_entity_ownership_blocker": "",
                "approved_source_prefab_template_dom_update_route_used": True,
                "approved_source_prefab_template_dom_initial_entity_found": True,
                "approved_source_prefab_serialized_entity_dom_generated": True,
                "approved_source_prefab_entity_patch_generated": True,
                "approved_source_prefab_entity_patch_operation_count": 3,
                "approved_source_prefab_component_override_paths_detected": True,
                "approved_source_prefab_component_override_paths": ["/Entities/MAXINE/Components/ActorAsset"],
                "approved_source_prefab_apply_link_overrides_attempted": False,
                "approved_source_prefab_apply_link_overrides_verified": False,
                "approved_source_prefab_push_overrides_to_template_attempted": True,
                "approved_source_prefab_push_overrides_to_template_verified": True,
                "approved_source_prefab_patch_entity_in_template_attempted": True,
                "approved_source_prefab_patch_entity_in_template_verified": True,
                "approved_source_prefab_template_dom_updated": True,
                "approved_source_prefab_propagation_apply_step_attempted": True,
                "approved_source_prefab_propagation_apply_step_completed": True,
                "approved_source_prefab_propagation_apply_step_verified": True,
                "approved_source_prefab_propagation_apply_step_blocker": "",
                "approved_source_prefab_actor_simple_motion_wiring_attempted": True,
                "approved_source_prefab_actor_simple_motion_wiring_completed": True,
                "approved_source_prefab_actor_simple_motion_wiring_verified": True,
                "approved_source_prefab_actor_simple_motion_wiring_blocker": "",
                "approved_source_prefab_path": "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "approved_source_prefab_before_hash": "1" * 64,
                "approved_source_prefab_after_hash": "2" * 64,
                "approved_source_prefab_modified": True,
                "approved_source_prefab_changed_this_run": True,
                "approved_source_prefab_update_route_used": "azlmbr.maxine.prefab_bridge.apply_approved_source_prefab_override_path_generation_template_update",
                "approved_source_prefab_save_verified": True,
                "approved_source_prefab_actor_component_added": True,
                "approved_source_prefab_simple_motion_component_added": True,
                "approved_source_prefab_actor_asset_assignment_verified": True,
                "approved_source_prefab_motion_asset_assignment_verified": True,
                "approved_source_prefab_actor_asset_id": "{11111111-1111-1111-1111-111111111111}:00000001",
                "approved_source_prefab_motion_asset_id": "{22222222-2222-2222-2222-222222222222}:00000002",
                "approved_source_prefab_property_readback_verified": True,
                "approved_source_prefab_persisted_actor_asset_marker_verified": True,
                "approved_source_prefab_persisted_motion_asset_marker_verified": True,
                "approved_source_prefab_persisted_wiring_markers_verified": True,
                "approved_source_prefab_marker_presence_verified": True,
                "approved_source_prefab_marker_persistence_verified_this_run": True,
                "approved_source_prefab_marker_persistence_blocker": "",
                "approved_source_prefab_template_update_route_rejection_probes_attempted": True,
                "approved_source_prefab_template_update_route_rejection_probes_verified": True,
                "approved_source_prefab_template_update_route_rejected_defaultlevel_path": True,
                "approved_source_prefab_template_update_route_rejected_production_level_path": True,
                "approved_source_prefab_template_update_route_rejected_generated_product_path": True,
                "approved_source_prefab_template_update_route_rejected_cache_path": True,
                "approved_source_prefab_template_update_route_rejected_unapproved_absolute_path": True,
                "approved_source_prefab_template_update_route_rejected_other_project_path": True,
                "approved_source_prefab_template_update_route_rejected_path_traversal": True,
                "approved_source_prefab_template_update_route_rejected_non_prefab_path": True,
                "approved_source_prefab_template_update_route_rejected_wrong_entity_owner": True,
                "approved_source_prefab_defaultlevel_mutation": False,
                "approved_source_prefab_production_level_mutation": False,
                "approved_source_prefab_hand_authored_unknown_json_used": False,
                "approved_spawnable_regenerated_or_found": False,
                "runtime_character_animation_component_wiring_claimed": False,
                "runtime_character_animation_component_wiring_verified": False,
                "runtime_character_animation_claimed": False,
                "runtime_character_animation_verified": False,
                "runtime_character_proof_claimed": False,
                "runtime_character_proof_verified": False,
            }
        )
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


def test_editor_smoke_schema_diagnostic_modes_track_editor_scripts():
    schema = load_json(SCHEMA)
    diagnostic_modes = schema["properties"]["diagnostic_mode"]["enum"]

    for mode in DIAGNOSTIC_EDITOR_SCRIPTS:
        assert mode in diagnostic_modes

    assert "not-a-real-diagnostic-mode" not in diagnostic_modes


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
    assert runtime_harness["runtime_exit_fixture_runtime_command_uses_product_load_probe"] is False
    assert runtime_harness["runtime_character_product_load_status"] == "runtime_character_product_load_not_attempted"
    assert runtime_harness["runtime_character_product_load_verified"] is False
    assert runtime_harness["runtime_character_product_load_claimed"] is False
    assert runtime_harness["runtime_character_product_load_probe_enabled"] is False
    assert runtime_harness["runtime_character_product_load_probe_shipping_behavior"] is False
    assert runtime_harness["runtime_character_product_load_candidate_matrix"] == []
    assert runtime_harness["runtime_character_product_load_products"] == []
    assert runtime_harness["runtime_character_product_load_required_products_complete"] is False
    assert runtime_harness["runtime_character_product_load_all_required_ready"] is False
    assert runtime_harness["runtime_character_product_load_markers_observed"] is False
    assert runtime_harness["runtime_character_product_load_is_instantiation_proof"] is False
    assert runtime_harness["runtime_runtime_character_product_load_is_instantiation_proof"] is False
    assert runtime_harness["runtime_character_instantiation_claimed"] is False
    assert runtime_harness["runtime_character_instantiation_verified"] is False
    assert runtime_harness["runtime_character_animation_claimed"] is False
    assert runtime_harness["runtime_character_animation_verified"] is False
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
        "approved-animation-component-wiring-generation": "editor_approved_animation_component_wiring_generation_smoke.py",
        "approved-prefab-save-update-automation-surface": "editor_approved_prefab_save_update_automation_surface_smoke.py",
        "approved-prefab-save-update-bridge": "editor_approved_prefab_save_update_bridge_smoke.py",
        "approved-prefab-save-update-bridge-host": "editor_approved_prefab_save_update_bridge_host_smoke.py",
        "approved-prefab-save-update-route": "editor_approved_prefab_save_update_route_smoke.py",
        "approved-source-prefab-actor-simple-motion-wiring": "editor_approved_source_prefab_actor_simple_motion_wiring_smoke.py",
        "approved-source-prefab-propagation-apply-step": "editor_approved_source_prefab_propagation_apply_step_smoke.py",
        "approved-source-prefab-parent-link-override-apply-route": (
            "editor_approved_source_prefab_parent_link_override_apply_route_smoke.py"
        ),
        "approved-source-prefab-override-path-generation-template-update": (
            "editor_approved_source_prefab_override_path_generation_template_update_smoke.py"
        ),
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


def test_editor_smoke_generation_diagnostic_records_source_validated_save_blocker(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_approved_animation_component_wiring_generation_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "approved-animation-component-wiring-generation"
        return _write_in_editor_report(env)

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path / "generation"),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "generation" / "editor-smoke-artifacts",
        diagnostic_mode="approved-animation-component-wiring-generation",
    )

    schema_result = schema_validate(result, load_json(SCHEMA))

    assert result["status"] == "pass"
    assert schema_result.status == "pass", schema_result.messages
    assert result["approved_runtime_animation_component_wiring_editor_generation_attempted"] is True
    assert result["approved_runtime_animation_component_wiring_editor_generation_completed"] is True
    assert result["approved_runtime_animation_component_wiring_editor_generation_verified"] is False
    assert (
        result["approved_runtime_animation_component_wiring_editor_generation_blocker"]
        == "blocked_by_editor_generated_prefab_update_save_semantics"
    )
    assert result["approved_runtime_animation_component_wiring_actor_component_added"] is True
    assert result["approved_runtime_animation_component_wiring_simple_motion_component_added"] is True
    assert result["approved_runtime_animation_component_wiring_source_prefab_modified"] is False
    assert result["approved_runtime_animation_component_wiring_hand_authored_unknown_json_used"] is False
    assert result["runtime_character_animation_component_wiring_claimed"] is False
    assert result["runtime_character_animation_component_wiring_verified"] is False
    assert result["runtime_character_animation_claimed"] is False
    assert result["runtime_character_animation_verified"] is False


def test_editor_smoke_prefab_save_update_surface_records_source_validated_automation_blocker(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_approved_prefab_save_update_automation_surface_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "approved-prefab-save-update-automation-surface"
        return _write_in_editor_report(env)

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path / "save-update"),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "save-update" / "editor-smoke-artifacts",
        diagnostic_mode="approved-prefab-save-update-automation-surface",
    )

    schema_result = schema_validate(result, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["approved_prefab_save_update_automation_surface_diagnostic_attempted"] is True
    assert result["approved_prefab_save_update_automation_surface_diagnostic_completed"] is True
    assert result["approved_prefab_save_update_source_validation_status"] == "pass"
    assert result["approved_prefab_save_update_source_validation_verified"] is True
    assert result["approved_prefab_save_update_automation_surface_found"] is False
    assert result["approved_prefab_save_update_automation_surface_verified"] is False
    assert (
        result["approved_prefab_save_update_automation_surface_blocker"]
        == "blocked_by_prefab_save_interface_not_available_to_automation"
    )
    assert result["approved_prefab_save_update_behavior_context_exposed"] is False
    assert result["approved_prefab_save_update_bridge_added"] is False
    assert result["approved_prefab_save_update_scratch_save_attempted"] is False
    assert result["approved_prefab_save_update_scratch_save_verified"] is False
    assert result["approved_prefab_save_update_scratch_cleanup_verified"] is True
    assert result["approved_runtime_animation_component_wiring_source_prefab_modified"] is False
    assert result["runtime_character_animation_component_wiring_claimed"] is False
    assert result["runtime_character_animation_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def _save_update_source_validation_with_observed_events(events, *, absent_symbols=None):
    return {
        "status": "pass",
        "verified": True,
        "refs": [
            {
                "path": "C:/src/o3de/Code/Framework/AzToolsFramework/AzToolsFramework/Prefab/PrefabPublicRequestHandler.cpp",
                "symbols": ["BehaviorContext", "PrefabPublicRequestBus"],
                "absent_symbols": list(absent_symbols or []),
                "status": "pass",
                "exists": True,
                "missing_symbols": [],
                "unexpected_symbols": [],
                "observed_behavior_context_events": list(events),
            }
        ],
    }


def test_prefab_save_update_behavior_exposure_uses_observed_events_for_current_blocker(monkeypatch):
    monkeypatch.setattr(
        editor_python_smoke,
        "_approved_prefab_save_update_source_validation",
        lambda: _save_update_source_validation_with_observed_events(
            ["CreatePrefabInMemory", "InstantiatePrefab"],
            absent_symbols=['Event("CreatePrefabAndSaveToDisk"', 'Event("SavePrefab"'],
        ),
    )

    result = editor_python_smoke._run_approved_prefab_save_update_automation_surface_checks({})

    assert result["approved_prefab_save_update_behavior_context_observed_events"] == [
        "CreatePrefabInMemory",
        "InstantiatePrefab",
    ]
    assert result["approved_prefab_save_update_behavior_context_missing_events"] == [
        "CreatePrefabAndSaveToDisk",
        "SavePrefab",
    ]
    assert result["approved_prefab_save_update_behavior_context_exposed"] is False
    assert (
        result["approved_prefab_save_update_automation_surface_blocker"]
        == "blocked_by_prefab_save_interface_not_available_to_automation"
    )
    assert result["approved_prefab_save_update_automation_surface_verified"] is False


def test_prefab_save_update_behavior_exposure_accepts_future_reflected_events(monkeypatch):
    monkeypatch.setattr(
        editor_python_smoke,
        "_approved_prefab_save_update_source_validation",
        lambda: _save_update_source_validation_with_observed_events(
            ["CreatePrefabInMemory", "InstantiatePrefab", "CreatePrefabAndSaveToDisk", "SavePrefab"],
            absent_symbols=['Event("CreatePrefabAndSaveToDisk"', 'Event("SavePrefab"'],
        ),
    )

    result = editor_python_smoke._run_approved_prefab_save_update_automation_surface_checks({})

    assert result["approved_prefab_save_update_behavior_context_exposed"] is True
    assert result["approved_prefab_save_update_behavior_context_missing_events"] == []
    assert (
        result["approved_prefab_save_update_automation_surface_blocker"]
        != "blocked_by_prefab_save_interface_not_available_to_automation"
    )
    assert result["approved_prefab_save_update_automation_surface_found"] is True
    assert result["approved_prefab_save_update_automation_surface_verified"] is False


def test_prefab_save_update_behavior_exposure_requires_both_save_events(monkeypatch):
    monkeypatch.setattr(
        editor_python_smoke,
        "_approved_prefab_save_update_source_validation",
        lambda: _save_update_source_validation_with_observed_events(
            ["CreatePrefabInMemory", "InstantiatePrefab", "SavePrefab"],
            absent_symbols=[],
        ),
    )

    result = editor_python_smoke._run_approved_prefab_save_update_automation_surface_checks({})

    assert result["approved_prefab_save_update_behavior_context_observed_events"] == [
        "CreatePrefabInMemory",
        "InstantiatePrefab",
        "SavePrefab",
    ]
    assert result["approved_prefab_save_update_behavior_context_missing_events"] == [
        "CreatePrefabAndSaveToDisk"
    ]
    assert result["approved_prefab_save_update_behavior_context_exposed"] is False
    assert result["approved_prefab_save_update_automation_surface_verified"] is False


def test_prefab_save_update_behavior_exposure_does_not_trust_empty_absent_symbols(monkeypatch):
    monkeypatch.setattr(
        editor_python_smoke,
        "_approved_prefab_save_update_source_validation",
        lambda: _save_update_source_validation_with_observed_events([], absent_symbols=[]),
    )

    result = editor_python_smoke._run_approved_prefab_save_update_automation_surface_checks({})

    assert result["approved_prefab_save_update_behavior_context_observed_events"] == []
    assert result["approved_prefab_save_update_behavior_context_exposed"] is False
    assert result["approved_prefab_save_update_automation_surface_verified"] is False


def test_editor_smoke_prefab_save_update_verified_requires_scratch_save_evidence():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-prefab-save-update-automation-surface",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_prefab_save_update_automation_surface_diagnostic_attempted": True,
            "approved_prefab_save_update_automation_surface_diagnostic_completed": True,
            "approved_prefab_save_update_automation_surface_found": True,
            "approved_prefab_save_update_automation_surface_verified": True,
            "approved_prefab_save_update_automation_surface_blocker": "",
            "approved_prefab_save_update_source_validation_status": "pass",
            "approved_prefab_save_update_source_validation_verified": True,
            "approved_prefab_save_update_behavior_context_exposed": True,
            "approved_prefab_save_update_bridge_added": True,
            "approved_prefab_save_update_bridge_verified": True,
            "approved_prefab_save_update_rejected_defaultlevel_path": True,
            "approved_prefab_save_update_rejected_production_level_path": True,
            "approved_prefab_save_update_scratch_save_attempted": True,
            "approved_prefab_save_update_scratch_save_verified": False,
            "approved_prefab_save_update_scratch_cleanup_verified": True,
            "approved_runtime_animation_component_wiring_source_prefab_modified": False,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_prefab_save_update_bridge_records_editor_gem_registration_blocker(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_approved_prefab_save_update_bridge_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "approved-prefab-save-update-bridge"
        return _write_in_editor_report(env)

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path / "save-update-bridge"),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "save-update-bridge" / "editor-smoke-artifacts",
        diagnostic_mode="approved-prefab-save-update-bridge",
    )

    schema_result = schema_validate(result, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["approved_prefab_save_update_bridge_diagnostic_attempted"] is True
    assert result["approved_prefab_save_update_bridge_diagnostic_completed"] is True
    assert result["approved_prefab_save_update_bridge_source_validation_status"] == "pass"
    assert result["approved_prefab_save_update_bridge_source_validation_verified"] is True
    assert result["approved_prefab_save_update_bridge_added"] is False
    assert result["approved_prefab_save_update_bridge_verified"] is False
    assert (
        result["approved_prefab_save_update_bridge_blocker"]
        == "blocked_by_prefab_save_bridge_requires_editor_gem_registration"
    )
    assert result["approved_prefab_save_update_bridge_behavior_context_reflected"] is False
    assert result["approved_prefab_save_update_bridge_callable_from_editor_python"] is False
    assert result["approved_prefab_save_update_scratch_save_attempted"] is False
    assert result["approved_prefab_save_update_scratch_save_verified"] is False
    assert result["approved_prefab_save_update_scratch_reload_or_parse_verified"] is False
    assert result["approved_prefab_save_update_scratch_cleanup_verified"] is True
    assert result["approved_runtime_animation_component_wiring_source_prefab_modified"] is False
    assert result["runtime_character_animation_component_wiring_claimed"] is False
    assert result["runtime_character_animation_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_editor_python_prefab_save_update_bridge_future_host_symbols_do_not_keep_registration_blocker(monkeypatch):
    future_source_validation = {
        "status": "pass",
        "verified": True,
        "refs": [
            {
                "status": "pass",
                "exists": True,
                "missing_symbols": [],
                "unexpected_symbols": [
                    "${gem_name}.Editor",
                    "PAL_TRAIT_BUILD_HOST_TOOLS",
                    "AzToolsFramework",
                    "Source/Tools/",
                    "PrefabSaveUpdateBridge",
                    "_Editor",
                    "BehaviorContext",
                    "PrefabPublicInterface",
                ],
                "observed_behavior_context_events": [
                    "CreatePrefabAndSaveToDisk",
                    "SavePrefab",
                ],
            }
        ],
    }

    monkeypatch.setattr(
        editor_python_smoke,
        "_source_validation_from_refs",
        lambda _refs: future_source_validation,
    )

    result = editor_python_smoke._run_approved_prefab_save_update_bridge_checks({})

    assert result["approved_prefab_save_update_bridge_added"] is True
    assert result["approved_prefab_save_update_bridge_behavior_context_reflected"] is True
    assert result["approved_prefab_save_update_bridge_callable_from_editor_python"] is True
    assert result["approved_prefab_save_update_automation_surface_found"] is True
    assert result["approved_prefab_save_update_bridge_blocker"] == "blocked_by_prefab_save_update_scratch_save_not_verified"
    assert result["approved_prefab_save_update_bridge_blocker"] != (
        "blocked_by_prefab_save_bridge_requires_editor_gem_registration"
    )
    assert result["approved_prefab_save_update_bridge_verified"] is False
    assert result["approved_prefab_save_update_scratch_save_verified"] is False


def test_editor_smoke_prefab_save_update_bridge_verified_requires_scratch_parse_cleanup():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-prefab-save-update-bridge",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_prefab_save_update_bridge_diagnostic_attempted": True,
            "approved_prefab_save_update_bridge_diagnostic_completed": True,
            "approved_prefab_save_update_bridge_source_validation_status": "pass",
            "approved_prefab_save_update_bridge_source_validation_verified": True,
            "approved_prefab_save_update_bridge_added": True,
            "approved_prefab_save_update_bridge_verified": True,
            "approved_prefab_save_update_bridge_blocker": "",
            "approved_prefab_save_update_bridge_behavior_context_reflected": True,
            "approved_prefab_save_update_bridge_callable_from_editor_python": True,
            "approved_prefab_save_update_rejected_defaultlevel_path": True,
            "approved_prefab_save_update_rejected_production_level_path": True,
            "approved_prefab_save_update_rejected_generated_product_path": True,
            "approved_prefab_save_update_scratch_save_attempted": True,
            "approved_prefab_save_update_scratch_save_verified": True,
            "approved_prefab_save_update_scratch_reload_or_parse_verified": False,
            "approved_prefab_save_update_scratch_cleanup_verified": True,
            "approved_prefab_save_update_generated_products_committed": False,
            "approved_runtime_animation_component_wiring_source_prefab_modified": False,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_prefab_save_update_bridge_host_records_registered_callable_host(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_approved_prefab_save_update_bridge_host_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "approved-prefab-save-update-bridge-host"
        return _write_in_editor_report(env)

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path / "save-update-bridge-host"),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "save-update-bridge-host" / "editor-smoke-artifacts",
        diagnostic_mode="approved-prefab-save-update-bridge-host",
    )

    schema_result = schema_validate(result, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["approved_prefab_save_update_bridge_host_diagnostic_attempted"] is True
    assert result["approved_prefab_save_update_bridge_host_diagnostic_completed"] is True
    assert result["approved_prefab_save_update_bridge_host_source_validation_status"] == "pass"
    assert result["approved_prefab_save_update_bridge_host_source_validation_verified"] is True
    assert result["approved_prefab_save_update_bridge_host_added"] is True
    assert result["approved_prefab_save_update_bridge_host_registered"] is True
    assert result["approved_prefab_save_update_bridge_host_build_verified"] is True
    assert result["approved_prefab_save_update_bridge_host_target_name"] == "MaxineRuntimeExitFixture.Editor"
    assert result["approved_prefab_save_update_bridge_host_module_name"] == "Gem_MaxineRuntimeExitFixture_Editor"
    assert result["approved_prefab_save_update_bridge_host_aztoolsframework_dependency_present"] is True
    assert result["approved_prefab_save_update_bridge_host_behavior_context_reflected"] is True
    assert result["approved_prefab_save_update_bridge_host_callable_from_editor_python"] is True
    assert result["approved_prefab_save_update_bridge_host_runtime_excluded"] is True
    assert result["approved_prefab_save_update_bridge_verified"] is False
    assert result["approved_prefab_save_update_scratch_save_attempted"] is False
    assert result["approved_runtime_animation_component_wiring_source_prefab_modified"] is False
    assert result["runtime_character_animation_component_wiring_verified"] is False
    assert result["runtime_character_animation_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_editor_python_prefab_save_update_bridge_host_source_validation_detects_editor_module_shape():
    result = editor_python_smoke._run_approved_prefab_save_update_bridge_host_checks(
        {},
        bridge_host_status={"callable": False, "status": ""},
        build_verified=False,
    )

    assert result["approved_prefab_save_update_bridge_host_source_validation_status"] == "pass"
    assert result["approved_prefab_save_update_bridge_host_source_validation_verified"] is True
    assert result["approved_prefab_save_update_bridge_host_added"] is True
    assert result["approved_prefab_save_update_bridge_host_registered"] is True
    assert result["approved_prefab_save_update_bridge_host_target_name"] == "MaxineRuntimeExitFixture.Editor"
    assert result["approved_prefab_save_update_bridge_host_module_name"] == "Gem_MaxineRuntimeExitFixture_Editor"
    assert result["approved_prefab_save_update_bridge_host_aztoolsframework_dependency_present"] is True
    assert result["approved_prefab_save_update_bridge_host_behavior_context_reflected"] is True
    assert result["approved_prefab_save_update_bridge_host_callable_from_editor_python"] is False
    assert result["approved_prefab_save_update_bridge_host_blocker"] == "blocked_by_editor_bridge_host_not_loaded_in_editor"
    assert result["approved_prefab_save_update_bridge_verified"] is False
    assert result["approved_prefab_save_update_scratch_save_verified"] is False


def test_editor_python_prefab_save_update_bridge_host_validation_does_not_require_c_src_o3de(
    monkeypatch,
):
    original_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        normalized = str(path).replace("\\", "/")
        if normalized.startswith("C:/src/o3de/"):
            return False
        return original_exists(path)

    monkeypatch.delenv("O3DE_ENGINE_ROOT", raising=False)
    monkeypatch.setattr(Path, "exists", fake_exists)

    result = editor_python_smoke._run_approved_prefab_save_update_bridge_host_checks(
        {},
        bridge_host_status={
            "callable": True,
            "status": "maxine_prefab_save_update_bridge_host_registered;save_route_exposed=false",
        },
        build_verified=True,
    )

    assert result["approved_prefab_save_update_bridge_host_source_validation_status"] == "pass"
    assert result["approved_prefab_save_update_bridge_host_source_validation_verified"] is True
    assert result["approved_prefab_save_update_bridge_host_engine_source_refs_status"] == "engine_source_refs_unavailable"
    assert result["approved_prefab_save_update_bridge_host_callable_from_editor_python"] is True
    assert result["approved_prefab_save_update_bridge_verified"] is False
    assert result["approved_prefab_save_update_scratch_save_verified"] is False
    assert result["runtime_character_animation_component_wiring_verified"] is False
    assert result["runtime_character_animation_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_editor_python_prefab_save_update_bridge_host_engine_refs_use_configured_root(
    tmp_path,
    monkeypatch,
):
    engine_root = tmp_path / "custom-o3de"
    prefab_interface = (
        engine_root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "PrefabPublicInterface.h"
    )
    prefab_handler = (
        engine_root / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "PrefabPublicHandler.cpp"
    )
    prefab_request_handler = (
        engine_root
        / "Code"
        / "Framework"
        / "AzToolsFramework"
        / "AzToolsFramework"
        / "Prefab"
        / "PrefabPublicRequestHandler.cpp"
    )
    custom_asset_cmake = engine_root / "Gems" / "CustomAssetExample" / "Code" / "CMakeLists.txt"
    archive_module = engine_root / "Gems" / "Archive" / "Code" / "Source" / "Tools" / "ArchiveEditorModule.cpp"
    python_funcs = engine_root / "Code" / "Editor" / "PythonEditorFuncs.cpp"
    prefab_interface.parent.mkdir(parents=True)
    custom_asset_cmake.parent.mkdir(parents=True)
    archive_module.parent.mkdir(parents=True)
    python_funcs.parent.mkdir(parents=True)
    prefab_interface.write_text(
        "class PrefabPublicInterface { PrefabOperationResult SavePrefab(AZ::IO::Path); "
        "void CreatePrefabAndSaveToDisk(); };\n",
        encoding="utf-8",
    )
    prefab_handler.write_text(
        "PrefabPublicHandler::CreatePrefabAndSaveToDisk filePath.IsAbsolute() CreatePrefabInMemory "
        "SaveTemplateToFile PrefabPublicHandler::SavePrefab GetTemplateIdFromFilePath SaveTemplate\n",
        encoding="utf-8",
    )
    prefab_request_handler.write_text(
        'BehaviorContext PrefabPublicRequestBus Event("CreatePrefabInMemory" Event("InstantiatePrefab"\n',
        encoding="utf-8",
    )
    custom_asset_cmake.write_text(
        "if(PAL_TRAIT_BUILD_HOST_TOOLS)\n"
        "ly_add_target(NAME ${gem_name}.Editor GEM_MODULE)\n"
        "ly_create_alias(NAME ${gem_name}.Tools NAMESPACE Gem TARGETS Gem::${gem_name}.Editor)\n",
        encoding="utf-8",
    )
    archive_module.write_text(
        "class ArchiveEditorModule {};\n"
        "AZ_DECLARE_MODULE_CLASS(AZ_JOIN(Gem_, O3DE_GEM_NAME, _Editor), Archive::ArchiveEditorModule)\n",
        encoding="utf-8",
    )
    python_funcs.write_text(
        "AZ::BehaviorContext* behaviorContext(nullptr);\n"
        "AZ::Script::Attributes::ScopeFlags::Automation;\n"
        "AZ::Script::Attributes::Module;\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("O3DE_ENGINE_ROOT", str(engine_root))

    result = editor_python_smoke._run_approved_prefab_save_update_bridge_host_checks(
        {},
        bridge_host_status={
            "callable": True,
            "status": "maxine_prefab_save_update_bridge_host_registered;save_route_exposed=false",
        },
        build_verified=True,
    )

    assert result["approved_prefab_save_update_bridge_host_source_validation_status"] == "pass"
    assert result["approved_prefab_save_update_bridge_host_engine_source_refs_status"] == "pass"
    engine_ref_paths = {
        str(ref.get("path", "")).replace("\\", "/")
        for ref in result["approved_prefab_save_update_bridge_host_engine_source_refs"]
    }
    assert any(str(engine_root).replace("\\", "/") in path for path in engine_ref_paths)
    assert not any(path.startswith("C:/src/o3de/") for path in engine_ref_paths)
    assert result["approved_prefab_save_update_bridge_host_callable_from_editor_python"] is True


def test_editor_python_prefab_save_update_bridge_host_missing_repo_owned_host_blocks(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("O3DE_ENGINE_ROOT", raising=False)
    missing_host_source = tmp_path / "missing-host.cpp"
    monkeypatch.setattr(
        editor_python_smoke,
        "_approved_prefab_save_update_bridge_host_repo_source_refs",
        lambda: [
            {
                "path": str(missing_host_source),
                "symbols": ["MaxinePrefabSaveUpdateBridgeEditorModule"],
                "absent_symbols": [],
            }
        ],
    )

    result = editor_python_smoke._run_approved_prefab_save_update_bridge_host_checks(
        {},
        bridge_host_status={
            "callable": True,
            "status": "maxine_prefab_save_update_bridge_host_registered;save_route_exposed=false",
        },
        build_verified=True,
    )

    assert result["approved_prefab_save_update_bridge_host_source_validation_status"] == "inconclusive"
    assert result["approved_prefab_save_update_bridge_host_source_validation_verified"] is False
    assert result["approved_prefab_save_update_bridge_host_added"] is False
    assert result["approved_prefab_save_update_bridge_host_registered"] is False
    assert result["approved_prefab_save_update_bridge_host_callable_from_editor_python"] is False
    assert (
        result["approved_prefab_save_update_bridge_host_blocker"]
        == "blocked_by_editor_bridge_host_requires_additional_source_validation"
    )
    assert result["approved_prefab_save_update_bridge_verified"] is False
    assert result["approved_prefab_save_update_scratch_save_verified"] is False


def test_editor_smoke_prefab_save_update_bridge_host_verified_requires_editor_python_callability():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-prefab-save-update-bridge-host",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_prefab_save_update_bridge_host_diagnostic_attempted": True,
            "approved_prefab_save_update_bridge_host_diagnostic_completed": True,
            "approved_prefab_save_update_bridge_host_source_validation_status": "pass",
            "approved_prefab_save_update_bridge_host_source_validation_verified": True,
            "approved_prefab_save_update_bridge_host_added": True,
            "approved_prefab_save_update_bridge_host_registered": True,
            "approved_prefab_save_update_bridge_host_build_required": True,
            "approved_prefab_save_update_bridge_host_build_verified": True,
            "approved_prefab_save_update_bridge_host_target_name": "MaxineRuntimeExitFixture.Editor",
            "approved_prefab_save_update_bridge_host_module_name": "Gem_MaxineRuntimeExitFixture_Editor",
            "approved_prefab_save_update_bridge_host_aztoolsframework_dependency_present": True,
            "approved_prefab_save_update_bridge_host_behavior_context_reflected": True,
            "approved_prefab_save_update_bridge_host_callable_from_editor_python": False,
            "approved_prefab_save_update_bridge_host_runtime_excluded": True,
            "approved_prefab_save_update_bridge_host_blocker": "",
            "approved_prefab_save_update_bridge_added": True,
            "approved_prefab_save_update_bridge_verified": False,
            "approved_prefab_save_update_scratch_save_attempted": False,
            "approved_prefab_save_update_scratch_save_verified": False,
            "approved_prefab_save_update_scratch_reload_or_parse_verified": False,
            "approved_prefab_save_update_scratch_cleanup_verified": True,
            "approved_runtime_animation_component_wiring_source_prefab_modified": False,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def _route_rejections(*, path_traversal: bool = True) -> dict:
    return {
        "defaultlevel": {"rejected": True, "status": "maxine_prefab_save_update_route_rejected;reason=level_or_production_path"},
        "production_level": {
            "rejected": True,
            "status": "maxine_prefab_save_update_route_rejected;reason=level_or_production_path",
        },
        "generated_product": {
            "rejected": True,
            "status": "maxine_prefab_save_update_route_rejected;reason=generated_product_or_cache_path",
        },
        "unapproved_absolute": {
            "rejected": True,
            "status": "maxine_prefab_save_update_route_rejected;reason=unapproved_scratch_root",
        },
        "other_project": {
            "rejected": True,
            "status": "maxine_prefab_save_update_route_rejected;reason=unapproved_scratch_root",
        },
        "path_traversal": {
            "rejected": path_traversal,
            "status": (
                "maxine_prefab_save_update_route_rejected;reason=path_traversal"
                if path_traversal
                else "maxine_prefab_save_update_route_saved"
            ),
        },
    }


def test_editor_python_prefab_save_update_route_verifies_scratch_parse_cleanup(tmp_path):
    scratch = tmp_path / "MAXINE_GoldenCorpus" / "Assets" / "_maxine_smoke" / "prefabs" / "route_probe.prefab"
    scratch.parent.mkdir(parents=True)
    scratch.write_text('{"ContainerEntity": {}, "Entities": {}}\n', encoding="utf-8")

    result = editor_python_smoke._run_approved_prefab_save_update_route_checks(
        {},
        bridge_host_status={"callable": True, "status": "maxine_prefab_save_update_bridge_host_registered"},
        route_status={
            "attempted": True,
            "callable": True,
            "saved": True,
            "status": "maxine_prefab_save_update_route_saved;scratch_save_verified=true",
        },
        rejection_statuses=_route_rejections(),
        scratch_prefab_path=scratch,
    )

    assert result["approved_prefab_save_update_route_source_validation_status"] == "pass"
    assert result["approved_prefab_save_update_route_added"] is True
    assert result["approved_prefab_save_update_route_callable_from_editor_python"] is True
    assert result["approved_prefab_save_update_bridge_host_callable_from_editor_python"] is True
    assert result["approved_prefab_save_update_bridge_verified"] is True
    assert result["approved_prefab_save_update_scratch_save_attempted"] is True
    assert result["approved_prefab_save_update_scratch_save_verified"] is True
    assert result["approved_prefab_save_update_scratch_reload_or_parse_verified"] is True
    assert result["approved_prefab_save_update_scratch_cleanup_verified"] is True
    assert result["approved_prefab_save_update_after_hash"]
    assert not scratch.exists()
    assert result["approved_runtime_animation_component_wiring_source_prefab_modified"] is False
    assert result["runtime_character_animation_component_wiring_claimed"] is False
    assert result["runtime_character_animation_verified"] is False
    assert result["runtime_character_proof_verified"] is False

    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(result)
    report["diagnostic_mode"] = "approved-prefab-save-update-route"
    schema_result = schema_validate(report, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(report, strict=True)

    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages


def test_editor_python_prefab_save_update_route_requires_all_path_rejections(tmp_path):
    scratch = tmp_path / "MAXINE_GoldenCorpus" / "Assets" / "_maxine_smoke" / "prefabs" / "route_probe.prefab"
    scratch.parent.mkdir(parents=True)
    scratch.write_text('{"ContainerEntity": {}, "Entities": {}}\n', encoding="utf-8")

    result = editor_python_smoke._run_approved_prefab_save_update_route_checks(
        {},
        bridge_host_status={"callable": True, "status": "maxine_prefab_save_update_bridge_host_registered"},
        route_status={
            "attempted": True,
            "callable": True,
            "saved": True,
            "status": "maxine_prefab_save_update_route_saved;scratch_save_verified=true",
        },
        rejection_statuses=_route_rejections(path_traversal=False),
        scratch_prefab_path=scratch,
    )

    assert result["approved_prefab_save_update_route_blocker"] == "blocked_by_prefab_save_update_route_path_policy"
    assert result["approved_prefab_save_update_rejected_path_traversal"] is False
    assert result["approved_prefab_save_update_bridge_verified"] is False
    assert result["approved_prefab_save_update_scratch_reload_or_parse_verified"] is True
    assert result["approved_prefab_save_update_scratch_cleanup_verified"] is True


def test_editor_python_prefab_save_update_route_does_not_infer_callability_from_source(tmp_path):
    scratch = tmp_path / "MAXINE_GoldenCorpus" / "Assets" / "_maxine_smoke" / "prefabs" / "route_probe.prefab"

    result = editor_python_smoke._run_approved_prefab_save_update_route_checks(
        {},
        bridge_host_status={"callable": True, "status": "maxine_prefab_save_update_bridge_host_registered"},
        route_status={
            "attempted": True,
            "callable": False,
            "saved": False,
            "status": "",
            "error": "missing reflected route",
        },
        rejection_statuses=_route_rejections(),
        scratch_prefab_path=scratch,
    )

    assert result["approved_prefab_save_update_route_source_validation_status"] == "pass"
    assert result["approved_prefab_save_update_route_added"] is True
    assert result["approved_prefab_save_update_route_behavior_context_reflected"] is True
    assert result["approved_prefab_save_update_route_callable_from_editor_python"] is False
    assert result["approved_prefab_save_update_route_blocker"] == "blocked_by_prefab_save_update_route_editor_call_failed"
    assert result["approved_prefab_save_update_bridge_verified"] is False
    assert result["approved_prefab_save_update_scratch_save_verified"] is False


def test_editor_python_prefab_save_update_route_source_validation_detects_bounded_route():
    result = editor_python_smoke._source_validation_from_refs(
        editor_python_smoke._approved_prefab_save_update_route_repo_source_refs()
    )

    assert result["status"] == "pass"
    assert result["verified"] is True
    route_ref = [
        ref
        for ref in result["refs"]
        if str(ref.get("path", "")).replace("\\", "/").endswith("PrefabSaveUpdateBridgeHostComponent.cpp")
    ][0]
    assert "save_prefab_update_scratch_probe" in route_ref["symbols"]
    assert "SavePrefab(AZ::IO::Path" in route_ref["absent_symbols"]


def test_editor_python_prefab_save_update_route_source_validation_requires_project_root_anchor():
    result = editor_python_smoke._source_validation_from_refs(
        editor_python_smoke._approved_prefab_save_update_route_repo_source_refs()
    )

    route_ref = [
        ref
        for ref in result["refs"]
        if str(ref.get("path", "")).replace("\\", "/").endswith("PrefabSaveUpdateBridgeHostComponent.cpp")
    ][0]

    assert "AZ::Utils::GetProjectPath" in route_ref["symbols"]
    assert "project_root_anchored_scratch_root" in route_ref["symbols"]
    assert 'Contains(normalized, "/assets/_maxine_smoke/prefabs/")' in route_ref["absent_symbols"]


def test_editor_python_prefab_save_update_route_rejection_paths_cover_outside_project_substring(tmp_path, monkeypatch):
    project_root = tmp_path / "MAXINE_GoldenCorpus"
    scratch = project_root / "Assets" / "_maxine_smoke" / "prefabs" / "route_probe.prefab"
    monkeypatch.setenv("O3DE_PROJECT_PATH", str(project_root))

    paths = editor_python_smoke._approved_prefab_save_update_route_rejection_paths(scratch)
    outside_project = paths["unapproved_absolute"]

    assert "Assets" in outside_project.parts
    assert "_maxine_smoke" in outside_project.parts
    assert "prefabs" in outside_project.parts
    assert outside_project.suffix == ".prefab"
    assert project_root not in outside_project.parents
    assert project_root not in paths["other_project"].parents


def test_editor_python_approved_source_prefab_wiring_source_validation_detects_approved_route():
    repo_refs = [
        ref
        for ref in editor_python_smoke._approved_source_prefab_wiring_source_refs()
        if "C:/src/o3de" not in str(ref.get("path", "")).replace("\\", "/")
    ]
    result = editor_python_smoke._source_validation_from_refs(repo_refs)

    assert result["status"] == "pass"
    assert result["verified"] is True
    route_ref = [
        ref
        for ref in result["refs"]
        if str(ref.get("path", "")).replace("\\", "/").endswith("PrefabSaveUpdateBridgeHostComponent.cpp")
    ][0]
    assert "save_approved_source_prefab_wiring" in route_ref["symbols"]
    assert "apply_approved_source_prefab_component_overrides" in route_ref["symbols"]
    assert "commit_approved_source_prefab_entity_changes" in route_ref["symbols"]
    assert "RejectReasonForApprovedSourcePrefabPath" in route_ref["symbols"]
    assert "GenerateRelativePath" in route_ref["symbols"]
    assert "ApplyComponentOverrides" in route_ref["symbols"]
    assert "GenerateUndoNodesForEntityChangeAndUpdateCache" in route_ref["symbols"]
    assert "approved_source_save_verified=true" in route_ref["symbols"]
    assert "hand_authored_unknown_json" in route_ref["absent_symbols"]


def test_editor_python_approved_source_prefab_wiring_rejection_paths_are_project_anchored(tmp_path, monkeypatch):
    project_root = tmp_path / "MAXINE_GoldenCorpus"
    source = (
        project_root
        / "Assets"
        / "Characters"
        / "MAXINE_GoldenCorpus"
        / "prefabs"
        / "release_rigged.prefab"
    )
    monkeypatch.setenv("O3DE_PROJECT_PATH", str(project_root))

    paths = editor_python_smoke._approved_source_prefab_wiring_rejection_paths(source)

    assert paths["defaultlevel"].as_posix().lower().find("/levels/defaultlevel/") >= 0
    assert paths["production_level"].as_posix().lower().find("/levels/production/") >= 0
    assert paths["generated_product"].as_posix().lower().find("/cache/") >= 0
    assert project_root not in paths["unapproved_absolute"].parents
    assert project_root not in paths["other_project"].parents
    assert ".." in paths["path_traversal"].parts
    assert paths["non_prefab"].suffix == ".txt"


def test_editor_smoke_approved_source_prefab_wiring_schema_and_semantics_validate():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-source-prefab-actor-simple-motion-wiring",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_source_prefab_actor_simple_motion_wiring_attempted": True,
            "approved_source_prefab_actor_simple_motion_wiring_completed": True,
            "approved_source_prefab_actor_simple_motion_wiring_verified": True,
            "approved_source_prefab_actor_simple_motion_wiring_blocker": "",
            "approved_source_prefab_actor_simple_motion_wiring_source_validation_status": "pass",
            "approved_source_prefab_actor_simple_motion_wiring_source_validation_verified": True,
            "approved_source_prefab_path": "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
            "approved_source_prefab_before_hash": "1" * 64,
            "approved_source_prefab_after_hash": "2" * 64,
            "approved_source_prefab_project_after_hash": "3" * 64,
            "approved_source_prefab_modified": True,
            "approved_source_prefab_persisted_wiring_markers_verified": True,
            "approved_source_prefab_project_persisted_wiring_markers_verified": True,
            "approved_source_prefab_component_overrides_applied": True,
            "approved_source_prefab_component_override_refs": {
                "actor_component_ref_status": "pass",
                "simple_motion_component_ref_status": "pass",
            },
            "approved_source_prefab_component_override_apply_status": {
                "attempted": True,
                "callable": True,
                "applied": True,
            },
            "approved_source_prefab_entity_changes_committed": True,
            "approved_source_prefab_entity_change_commit_status": {
                "attempted": True,
                "callable": True,
                "committed": True,
            },
            "approved_source_prefab_save_verified": True,
            "approved_source_prefab_actor_component_added": True,
            "approved_source_prefab_simple_motion_component_added": True,
            "approved_source_prefab_actor_asset_assignment_verified": True,
            "approved_source_prefab_motion_asset_assignment_verified": True,
            "approved_source_prefab_actor_asset_id": "{11111111-1111-1111-1111-111111111111}:00000001",
            "approved_source_prefab_motion_asset_id": "{22222222-2222-2222-2222-222222222222}:00000002",
            "approved_source_prefab_property_readback_verified": True,
            "approved_source_prefab_defaultlevel_mutation": False,
            "approved_source_prefab_production_level_mutation": False,
            "approved_source_prefab_hand_authored_unknown_json_used": False,
            "approved_runtime_animation_component_wiring_source_prefab_modified": True,
            "approved_runtime_animation_component_wiring_editor_generated_update_used": True,
            "approved_runtime_animation_component_wiring_prefab_save_verified": True,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_claimed": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_claimed": False,
            "runtime_character_proof_verified": False,
        }
    )

    schema_result = schema_validate(report, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(report, strict=True)

    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages


def test_editor_smoke_approved_source_prefab_wiring_rejects_hand_authored_unknown_json():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-source-prefab-actor-simple-motion-wiring",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_source_prefab_actor_simple_motion_wiring_attempted": True,
            "approved_source_prefab_actor_simple_motion_wiring_completed": True,
            "approved_source_prefab_actor_simple_motion_wiring_verified": False,
            "approved_source_prefab_actor_simple_motion_wiring_blocker": "blocked_by_editor_component_assignment_readback_failure",
            "approved_source_prefab_actor_simple_motion_wiring_source_validation_status": "pass",
            "approved_source_prefab_actor_simple_motion_wiring_source_validation_verified": True,
            "approved_source_prefab_hand_authored_unknown_json_used": True,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_python_source_prefab_propagation_apply_step_pins_parent_link_context():
    result = editor_python_smoke._run_approved_source_prefab_propagation_apply_step_checks({})

    assert result["approved_source_prefab_propagation_apply_step_attempted"] is True
    assert result["approved_source_prefab_propagation_apply_step_completed"] is True
    assert result["approved_source_prefab_propagation_apply_step_source_validation_status"] == "pass"
    assert result["approved_source_prefab_propagation_apply_step_source_validation_verified"] is True
    assert result["approved_source_prefab_propagation_apply_step_verified"] is False
    assert (
        result["approved_source_prefab_propagation_apply_step_blocker"]
        == "blocked_by_prefab_instance_to_template_propagation_requires_parent_link_context"
    )
    assert result["approved_source_prefab_component_overrides_detected"] is False
    assert result["approved_source_prefab_component_overrides_applied"] is False
    assert result["approved_source_prefab_template_dom_updated"] is False
    assert result["approved_source_prefab_modified"] is False
    assert result["approved_source_prefab_persisted_actor_asset_marker_verified"] is False
    assert result["approved_source_prefab_persisted_motion_asset_marker_verified"] is False
    assert result["runtime_character_animation_component_wiring_claimed"] is False
    assert result["runtime_character_animation_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_editor_python_source_prefab_propagation_apply_step_records_engine_refs_separately(monkeypatch, tmp_path):
    monkeypatch.setenv("O3DE_ENGINE_ROOT", str(tmp_path / "missing_engine"))

    result = editor_python_smoke._run_approved_source_prefab_propagation_apply_step_checks({})

    assert result["approved_source_prefab_propagation_apply_step_source_validation_status"] == "pass"
    assert result["approved_source_prefab_propagation_apply_step_source_validation_verified"] is True
    assert result["approved_source_prefab_propagation_apply_step_engine_source_refs_status"] in {
        "engine_source_refs_unavailable",
        "engine_source_refs_not_available_in_this_environment",
    }
    assert result["approved_source_prefab_propagation_apply_step_verified"] is False


def test_editor_python_source_prefab_propagation_apply_step_candidate_matrix_rejects_unknown_json():
    matrix = editor_python_smoke._approved_source_prefab_propagation_apply_step_candidate_matrix()
    by_candidate = {item["candidate"]: item for item in matrix}

    assert by_candidate["GenerateUndoNodesForEntityChangeAndUpdateCache"]["outcome"] == "attempted_preserved_blocked"
    assert by_candidate["PrefabOverridePublicInterface::ApplyComponentOverrides"]["outcome"] == "source_validated_blocked"
    assert by_candidate["direct hand-authored .prefab JSON edit"]["outcome"] == "rejected"
    assert by_candidate["scratch-only route proof"]["outcome"] == "preserved_not_sufficient"


def test_editor_smoke_source_prefab_propagation_apply_step_schema_and_semantics_validate():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(editor_python_smoke._run_approved_source_prefab_propagation_apply_step_checks({}))
    report["mode"] = "local_editor_python"
    report["status"] = "pass"
    report["diagnostic_mode"] = "approved-source-prefab-propagation-apply-step"
    report["live_editor_execution"] = True
    report["no_fake_success"] = True

    schema_result = schema_validate(report, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(report, strict=True)

    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages


def test_editor_smoke_source_prefab_propagation_apply_step_rejects_runtime_overclaim():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(editor_python_smoke._run_approved_source_prefab_propagation_apply_step_checks({}))
    report["mode"] = "local_editor_python"
    report["status"] = "pass"
    report["diagnostic_mode"] = "approved-source-prefab-propagation-apply-step"
    report["runtime_character_animation_component_wiring_verified"] = True

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_python_parent_link_override_apply_route_source_validation_detects_bridge_route():
    result = editor_python_smoke._source_validation_from_refs(
        editor_python_smoke._approved_source_prefab_parent_link_override_apply_repo_source_refs()
    )

    assert result["status"] == "pass"
    assert result["verified"] is True
    route_ref = [
        ref
        for ref in result["refs"]
        if str(ref.get("path", "")).replace("\\", "/").endswith("PrefabSaveUpdateBridgeHostComponent.cpp")
    ][0]
    assert "apply_approved_source_prefab_parent_link_component_overrides" in route_ref["symbols"]
    assert "FocusOnOwningPrefab" in route_ref["symbols"]
    assert "FocusOnParentOfFocusedPrefab" in route_ref["symbols"]
    assert "GetPrefabFocusPathLength" in route_ref["symbols"]
    assert "GetOwningInstancePrefabPath" in route_ref["symbols"]
    assert "GetFullPath" in route_ref["symbols"]
    assert "ComponentApplicationRequests::FindEntity" in route_ref["symbols"]
    assert "FindComponent" in route_ref["symbols"]
    assert "entity_ownership_checked=true" in route_ref["symbols"]
    assert "component_ownership_checked=" in route_ref["symbols"]
    assert "parent_focus_context_applied=true" in route_ref["symbols"]
    assert "parent_focus_context_restored=true" in route_ref["symbols"]
    assert "PushOverridesToPrefab" in route_ref["symbols"]
    assert "hand_authored_unknown_json" in route_ref["absent_symbols"]


def _parent_link_override_status(*, reason: str = "", applied: bool = True, ownership: bool = True) -> str:
    prefix = (
        "maxine_prefab_save_update_route_approved_source_parent_link_override_applied;"
        if applied
        else "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
    )
    reason_text = f"reason={reason};" if reason else ""
    ownership_text = (
        "entity_ownership_checked=true;"
        "entity_ownership_verified=true;"
        "entity_owning_prefab_path=C:/Users/example/O3DE/Projects/MAXINE_GoldenCorpus/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab;"
        "entity_owning_prefab_matches_requested_path=true;"
        "component_ownership_checked=true;"
        "component_ownership_verified=true;"
        if ownership
        else ""
    )
    return (
        prefix
        + reason_text
        + ownership_text
        + "parent_focus_context_required=true;"
        "parent_focus_context_available=true;"
        "parent_focus_context_applied=true;"
        "parent_focus_context_restored=true;"
        "link_context_required=true;"
        "link_context_available=true;"
        "component_override_paths_detected=true;"
        "actor_component_override_present=true;"
        "simple_motion_component_override_present=true;"
        "actor_component_override_applied=true;"
        "simple_motion_component_override_applied=true;"
        "push_overrides_to_prefab_attempted=true;"
        "push_overrides_to_prefab_verified=true"
    )


def test_editor_python_parent_link_override_apply_status_parser_requires_markers():
    result = editor_python_smoke._approved_source_prefab_parent_link_override_apply_report_from_route_status(
        {"attempted": True, "callable": True, "applied": True, "status": _parent_link_override_status()},
        persisted_markers={"actor": False, "motion": False, "both": False},
        source_prefab_changed_this_run=True,
        before_hash="1" * 64,
        after_hash="2" * 64,
    )

    assert result["approved_source_prefab_parent_link_override_apply_route_attempted"] is True
    assert result["approved_source_prefab_parent_link_override_apply_route_completed"] is True
    assert result["approved_source_prefab_parent_link_override_apply_route_verified"] is False
    assert result["approved_source_prefab_entity_ownership_checked"] is True
    assert result["approved_source_prefab_entity_ownership_verified"] is True
    assert result["approved_source_prefab_entity_owning_prefab_matches_requested_path"] is True
    assert result["approved_source_prefab_component_ownership_checked"] is True
    assert result["approved_source_prefab_component_ownership_verified"] is True
    assert result["approved_source_prefab_parent_focus_context_required"] is True
    assert result["approved_source_prefab_parent_focus_context_available"] is True
    assert result["approved_source_prefab_parent_focus_context_applied"] is True
    assert result["approved_source_prefab_parent_focus_context_restored"] is True
    assert result["approved_source_prefab_link_context_required"] is True
    assert result["approved_source_prefab_link_context_available"] is True
    assert result["approved_source_prefab_component_override_paths_detected"] is True
    assert result["approved_source_prefab_component_overrides_detected"] is True
    assert result["approved_source_prefab_component_overrides_applied"] is True
    assert result["approved_source_prefab_push_overrides_to_prefab_attempted"] is True
    assert result["approved_source_prefab_push_overrides_to_prefab_verified"] is True
    assert result["approved_source_prefab_template_dom_updated"] is False
    assert (
        result["approved_source_prefab_parent_link_override_apply_route_blocker"]
        == "blocked_by_prefab_template_dom_update_unavailable"
    )
    assert result["runtime_character_animation_component_wiring_verified"] is False


def test_editor_python_parent_link_override_apply_status_parser_verifies_only_with_markers():
    result = editor_python_smoke._approved_source_prefab_parent_link_override_apply_report_from_route_status(
        {"attempted": True, "callable": True, "applied": True, "status": _parent_link_override_status()},
        persisted_markers={"actor": True, "motion": True, "both": True},
        source_prefab_changed_this_run=True,
        before_hash="1" * 64,
        after_hash="2" * 64,
    )

    assert result["approved_source_prefab_parent_link_override_apply_route_verified"] is True
    assert result["approved_source_prefab_propagation_apply_step_verified"] is True
    assert result["approved_source_prefab_actor_simple_motion_wiring_verified"] is True
    assert result["approved_source_prefab_template_dom_updated"] is True
    assert result["approved_source_prefab_changed_this_run"] is True
    assert result["approved_source_prefab_marker_presence_verified"] is True
    assert result["approved_source_prefab_marker_persistence_verified_this_run"] is True
    assert result["approved_source_prefab_marker_persistence_blocker"] == ""
    assert result["approved_source_prefab_persisted_actor_asset_marker_verified"] is True
    assert result["approved_source_prefab_persisted_motion_asset_marker_verified"] is True
    assert result["approved_source_prefab_persisted_wiring_markers_verified"] is True
    assert result["approved_spawnable_regenerated_or_found"] is False
    assert result["runtime_character_animation_component_wiring_claimed"] is False
    assert result["runtime_character_animation_component_wiring_verified"] is False
    assert result["runtime_character_animation_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_editor_python_parent_link_override_apply_rejects_wrong_prefab_entity():
    status = (
        "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
        "reason=entity_not_owned_by_approved_source_prefab;"
        "entity_ownership_checked=true;"
        "entity_ownership_verified=false;"
        "entity_owning_prefab_path=C:/Users/example/O3DE/Projects/OtherProject/Assets/_maxine_smoke/prefabs/other.prefab;"
        "entity_owning_prefab_matches_requested_path=false;"
        "component_ownership_checked=false;"
        "component_ownership_verified=false"
    )

    result = editor_python_smoke._approved_source_prefab_parent_link_override_apply_report_from_route_status(
        {"attempted": True, "callable": True, "applied": False, "status": status},
        persisted_markers={"actor": False, "motion": False, "both": False},
        source_prefab_changed_this_run=False,
        before_hash="1" * 64,
        after_hash="1" * 64,
    )

    assert result["approved_source_prefab_entity_ownership_checked"] is True
    assert result["approved_source_prefab_entity_ownership_verified"] is False
    assert result["approved_source_prefab_entity_owning_prefab_matches_requested_path"] is False
    assert result["approved_source_prefab_component_ownership_checked"] is False
    assert result["approved_source_prefab_parent_focus_context_applied"] is False
    assert result["approved_source_prefab_component_overrides_applied"] is False
    assert (
        result["approved_source_prefab_parent_link_override_apply_route_blocker"]
        == "blocked_by_entity_not_owned_by_approved_source_prefab"
    )
    assert result["approved_source_prefab_modified"] is False
    assert result["runtime_character_animation_component_wiring_verified"] is False


def test_editor_python_parent_link_override_apply_blocks_when_ownership_unavailable():
    status = (
        "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
        "reason=entity_owning_prefab_unavailable;"
        "entity_ownership_checked=true;"
        "entity_ownership_verified=false;"
        "entity_owning_prefab_path=;"
        "entity_owning_prefab_matches_requested_path=false;"
        "component_ownership_checked=false;"
        "component_ownership_verified=false"
    )

    result = editor_python_smoke._approved_source_prefab_parent_link_override_apply_report_from_route_status(
        {"attempted": True, "callable": True, "applied": False, "status": status},
        persisted_markers={"actor": False, "motion": False, "both": False},
        source_prefab_changed_this_run=False,
        before_hash="1" * 64,
        after_hash="1" * 64,
    )

    assert result["approved_source_prefab_entity_ownership_checked"] is True
    assert result["approved_source_prefab_entity_ownership_verified"] is False
    assert (
        result["approved_source_prefab_parent_link_override_apply_route_blocker"]
        == "blocked_by_entity_owning_prefab_unavailable"
    )


def test_editor_python_parent_link_override_apply_rejects_component_mismatch():
    status = (
        "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
        "reason=component_not_owned_by_approved_source_prefab_entity;"
        "entity_ownership_checked=true;"
        "entity_ownership_verified=true;"
        "entity_owning_prefab_path=C:/Users/example/O3DE/Projects/MAXINE_GoldenCorpus/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab;"
        "entity_owning_prefab_matches_requested_path=true;"
        "component_ownership_checked=true;"
        "component_ownership_verified=false"
    )

    result = editor_python_smoke._approved_source_prefab_parent_link_override_apply_report_from_route_status(
        {"attempted": True, "callable": True, "applied": False, "status": status},
        persisted_markers={"actor": False, "motion": False, "both": False},
        source_prefab_changed_this_run=False,
        before_hash="1" * 64,
        after_hash="1" * 64,
    )

    assert result["approved_source_prefab_entity_ownership_verified"] is True
    assert result["approved_source_prefab_component_ownership_checked"] is True
    assert result["approved_source_prefab_component_ownership_verified"] is False
    assert (
        result["approved_source_prefab_parent_link_override_apply_route_blocker"]
        == "blocked_by_component_not_owned_by_approved_source_prefab_entity"
    )


def test_editor_python_parent_link_override_apply_rejects_stale_markers_without_hash_change():
    result = editor_python_smoke._approved_source_prefab_parent_link_override_apply_report_from_route_status(
        {"attempted": True, "callable": True, "applied": True, "status": _parent_link_override_status()},
        persisted_markers={"actor": True, "motion": True, "both": True},
        source_prefab_changed_this_run=False,
        before_hash="1" * 64,
        after_hash="1" * 64,
    )

    assert result["approved_source_prefab_marker_presence_verified"] is True
    assert result["approved_source_prefab_marker_persistence_verified_this_run"] is False
    assert result["approved_source_prefab_parent_link_override_apply_route_verified"] is False
    assert result["approved_source_prefab_propagation_apply_step_verified"] is False
    assert result["approved_source_prefab_actor_simple_motion_wiring_verified"] is False
    assert result["approved_source_prefab_template_dom_updated"] is False
    assert (
        result["approved_source_prefab_marker_persistence_blocker"]
        == "blocked_by_source_prefab_markers_preexisting_without_this_run_change"
    )
    assert (
        result["approved_source_prefab_parent_link_override_apply_route_blocker"]
        == "blocked_by_source_prefab_markers_preexisting_without_this_run_change"
    )
    assert result["approved_spawnable_regenerated_or_found"] is False
    assert result["runtime_character_animation_component_wiring_verified"] is False


def test_editor_smoke_parent_link_override_apply_route_schema_and_semantics_validate():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        editor_python_smoke._approved_source_prefab_parent_link_override_apply_report_from_route_status(
            {
                "attempted": True,
                "callable": True,
                "applied": True,
                "status": _parent_link_override_status(),
            },
            persisted_markers={"actor": True, "motion": True, "both": True},
            source_prefab_changed_this_run=True,
            before_hash="1" * 64,
            after_hash="2" * 64,
        )
    )
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-source-prefab-parent-link-override-apply-route",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_source_prefab_parent_link_override_apply_source_validation_status": "pass",
            "approved_source_prefab_parent_link_override_apply_source_validation_verified": True,
            "approved_source_prefab_modified": True,
            "approved_source_prefab_changed_this_run": True,
            "approved_source_prefab_save_verified": True,
            "approved_source_prefab_actor_component_added": True,
            "approved_source_prefab_simple_motion_component_added": True,
            "approved_source_prefab_actor_asset_assignment_verified": True,
            "approved_source_prefab_motion_asset_assignment_verified": True,
            "approved_source_prefab_property_readback_verified": True,
            "approved_source_prefab_before_hash": "1" * 64,
            "approved_source_prefab_after_hash": "2" * 64,
            "approved_source_prefab_actor_asset_id": "{11111111-1111-1111-1111-111111111111}:00000001",
            "approved_source_prefab_motion_asset_id": "{22222222-2222-2222-2222-222222222222}:00000002",
            "approved_source_prefab_defaultlevel_mutation": False,
            "approved_source_prefab_production_level_mutation": False,
            "approved_source_prefab_hand_authored_unknown_json_used": False,
        }
    )

    schema_result = schema_validate(report, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(report, strict=True)

    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages


def test_editor_smoke_parent_link_override_apply_route_rejects_stale_marker_hash_overclaim():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-source-prefab-parent-link-override-apply-route",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_source_prefab_parent_link_override_apply_route_attempted": True,
            "approved_source_prefab_parent_link_override_apply_route_completed": True,
            "approved_source_prefab_parent_link_override_apply_route_verified": True,
            "approved_source_prefab_parent_link_override_apply_route_blocker": "",
            "approved_source_prefab_parent_link_override_apply_source_validation_status": "pass",
            "approved_source_prefab_parent_link_override_apply_source_validation_verified": True,
            "approved_source_prefab_entity_ownership_checked": True,
            "approved_source_prefab_entity_ownership_verified": True,
            "approved_source_prefab_entity_owning_prefab_matches_requested_path": True,
            "approved_source_prefab_component_ownership_checked": True,
            "approved_source_prefab_component_ownership_verified": True,
            "approved_source_prefab_parent_focus_context_required": True,
            "approved_source_prefab_parent_focus_context_available": True,
            "approved_source_prefab_parent_focus_context_applied": True,
            "approved_source_prefab_parent_focus_context_restored": True,
            "approved_source_prefab_link_context_required": True,
            "approved_source_prefab_link_context_available": True,
            "approved_source_prefab_component_override_paths_detected": True,
            "approved_source_prefab_component_overrides_detected": True,
            "approved_source_prefab_component_overrides_applied": True,
            "approved_source_prefab_push_overrides_to_prefab_attempted": True,
            "approved_source_prefab_push_overrides_to_prefab_verified": True,
            "approved_source_prefab_template_dom_updated": True,
            "approved_source_prefab_modified": True,
            "approved_source_prefab_changed_this_run": False,
            "approved_source_prefab_marker_presence_verified": True,
            "approved_source_prefab_marker_persistence_verified_this_run": False,
            "approved_source_prefab_marker_persistence_blocker": (
                "blocked_by_source_prefab_markers_preexisting_without_this_run_change"
            ),
            "approved_source_prefab_save_verified": True,
            "approved_source_prefab_actor_component_added": True,
            "approved_source_prefab_simple_motion_component_added": True,
            "approved_source_prefab_actor_asset_assignment_verified": True,
            "approved_source_prefab_motion_asset_assignment_verified": True,
            "approved_source_prefab_property_readback_verified": True,
            "approved_source_prefab_before_hash": "1" * 64,
            "approved_source_prefab_after_hash": "1" * 64,
            "approved_source_prefab_persisted_actor_asset_marker_verified": True,
            "approved_source_prefab_persisted_motion_asset_marker_verified": True,
            "approved_source_prefab_persisted_wiring_markers_verified": True,
            "approved_source_prefab_defaultlevel_mutation": False,
            "approved_source_prefab_production_level_mutation": False,
            "approved_source_prefab_hand_authored_unknown_json_used": False,
            "approved_spawnable_regenerated_or_found": False,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_verified": False,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_parent_link_override_apply_route_rejects_marker_overclaim():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-source-prefab-parent-link-override-apply-route",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_source_prefab_parent_link_override_apply_route_attempted": True,
            "approved_source_prefab_parent_link_override_apply_route_completed": True,
            "approved_source_prefab_parent_link_override_apply_route_verified": True,
            "approved_source_prefab_parent_link_override_apply_route_blocker": "",
            "approved_source_prefab_parent_link_override_apply_source_validation_status": "pass",
            "approved_source_prefab_parent_link_override_apply_source_validation_verified": True,
            "approved_source_prefab_parent_focus_context_required": True,
            "approved_source_prefab_parent_focus_context_available": True,
            "approved_source_prefab_parent_focus_context_applied": True,
            "approved_source_prefab_parent_focus_context_restored": True,
            "approved_source_prefab_link_context_required": True,
            "approved_source_prefab_link_context_available": True,
            "approved_source_prefab_component_override_paths_detected": True,
            "approved_source_prefab_component_overrides_detected": True,
            "approved_source_prefab_component_overrides_applied": True,
            "approved_source_prefab_push_overrides_to_prefab_attempted": True,
            "approved_source_prefab_push_overrides_to_prefab_verified": True,
            "approved_source_prefab_template_dom_updated": True,
            "approved_source_prefab_modified": True,
            "approved_source_prefab_save_verified": True,
            "approved_source_prefab_actor_component_added": True,
            "approved_source_prefab_simple_motion_component_added": True,
            "approved_source_prefab_actor_asset_assignment_verified": True,
            "approved_source_prefab_motion_asset_assignment_verified": True,
            "approved_source_prefab_property_readback_verified": True,
            "approved_source_prefab_persisted_actor_asset_marker_verified": True,
            "approved_source_prefab_persisted_motion_asset_marker_verified": False,
            "approved_source_prefab_persisted_wiring_markers_verified": False,
            "approved_source_prefab_defaultlevel_mutation": False,
            "approved_source_prefab_production_level_mutation": False,
            "approved_source_prefab_hand_authored_unknown_json_used": False,
            "approved_spawnable_regenerated_or_found": False,
            "runtime_character_animation_component_wiring_claimed": False,
            "runtime_character_animation_component_wiring_verified": False,
            "runtime_character_animation_verified": False,
            "runtime_character_proof_verified": False,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_python_override_path_template_update_source_validation_detects_source_backed_route():
    result = editor_python_smoke._source_validation_from_refs(
        editor_python_smoke._approved_source_prefab_override_path_generation_template_update_repo_source_refs()
    )

    assert result["status"] == "pass"
    assert result["verified"] is True
    route_ref = [
        ref
        for ref in result["refs"]
        if str(ref.get("path", "")).replace("\\", "/").endswith("PrefabSaveUpdateBridgeHostComponent.cpp")
    ][0]
    assert "apply_approved_source_prefab_override_path_generation_template_update" in route_ref["symbols"]
    assert "ApplyApprovedSourcePrefabOverridePathGenerationTemplateUpdate" in route_ref["symbols"]
    assert "InstanceEntityMapperInterface" in route_ref["symbols"]
    assert "InstanceToTemplateInterface" in route_ref["symbols"]
    assert "GenerateEntityDomBySerializing" in route_ref["symbols"]
    assert "GeneratePatch" in route_ref["symbols"]
    assert "PatchEntityInTemplate" in route_ref["symbols"]
    assert "FindTemplateDom" in route_ref["symbols"]
    assert "entity_ownership_checked=true" in route_ref["symbols"]
    assert "component_ownership_checked=" in route_ref["symbols"]
    assert "hand_authored_unknown_json" in route_ref["absent_symbols"]


def _template_update_status(*, reason: str = "", applied: bool = True) -> str:
    prefix = (
        "maxine_prefab_save_update_route_approved_source_template_update_applied;"
        if applied
        else "maxine_prefab_save_update_route_approved_source_template_update_failed;"
    )
    reason_text = f"reason={reason};" if reason else ""
    return (
        prefix
        + reason_text
        + "entity_ownership_checked=true;"
        "entity_ownership_verified=true;"
        "entity_owning_prefab_path=C:/Users/example/O3DE/Projects/MAXINE_GoldenCorpus/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab;"
        "entity_owning_prefab_matches_requested_path=true;"
        "component_ownership_checked=true;"
        "component_ownership_verified=true;"
        "source_backed_template_update_route_used=true;"
        "template_dom_initial_entity_found=true;"
        "serialized_entity_dom_generated=true;"
        "entity_patch_generated=true;"
        "entity_patch_operation_count=3;"
        "patch_entity_in_template_attempted=true;"
        "patch_entity_in_template_verified=true;"
        "template_dom_updated=true;"
        "approved_source_save_verified=true"
    )


def test_editor_python_override_path_template_update_requires_fresh_markers():
    result = editor_python_smoke._approved_source_prefab_override_path_generation_template_update_report_from_route_status(
        {"attempted": True, "callable": True, "applied": True, "status": _template_update_status()},
        persisted_markers={"actor": False, "motion": False, "both": False},
        source_prefab_changed_this_run=True,
        before_hash="1" * 64,
        after_hash="2" * 64,
        template_update_route_rejection_probes_verified=True,
    )

    assert result["approved_source_prefab_override_path_generation_template_update_attempted"] is True
    assert result["approved_source_prefab_override_path_generation_template_update_completed"] is True
    assert result["approved_source_prefab_override_path_generation_template_update_verified"] is False
    assert result["approved_source_prefab_entity_ownership_verified"] is True
    assert result["approved_source_prefab_component_ownership_verified"] is True
    assert result["approved_source_prefab_template_dom_update_route_used"] is True
    assert result["approved_source_prefab_serialized_entity_dom_generated"] is True
    assert result["approved_source_prefab_entity_patch_generated"] is True
    assert result["approved_source_prefab_patch_entity_in_template_verified"] is True
    assert result["approved_source_prefab_template_dom_updated"] is False
    assert (
        result["approved_source_prefab_override_path_generation_template_update_blocker"]
        == "blocked_by_prefab_template_dom_update_unavailable"
    )
    assert result["runtime_character_animation_component_wiring_verified"] is False


def test_editor_python_override_path_template_update_verifies_only_with_fresh_hash_and_markers():
    result = editor_python_smoke._approved_source_prefab_override_path_generation_template_update_report_from_route_status(
        {"attempted": True, "callable": True, "applied": True, "status": _template_update_status()},
        persisted_markers={"actor": True, "motion": True, "both": True},
        source_prefab_changed_this_run=True,
        before_hash="1" * 64,
        after_hash="2" * 64,
        template_update_route_rejection_probes_verified=True,
    )

    assert result["approved_source_prefab_override_path_generation_template_update_verified"] is True
    assert result["approved_source_prefab_propagation_apply_step_verified"] is True
    assert result["approved_source_prefab_actor_simple_motion_wiring_verified"] is True
    assert result["approved_source_prefab_modified"] is True
    assert result["approved_source_prefab_changed_this_run"] is True
    assert result["approved_source_prefab_marker_persistence_verified_this_run"] is True
    assert result["approved_source_prefab_persisted_actor_asset_marker_verified"] is True
    assert result["approved_source_prefab_persisted_motion_asset_marker_verified"] is True
    assert result["approved_spawnable_regenerated_or_found"] is False
    assert result["runtime_character_animation_component_wiring_claimed"] is False
    assert result["runtime_character_animation_component_wiring_verified"] is False
    assert result["runtime_character_animation_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_editor_python_override_path_template_update_rejects_stale_markers_without_hash_change():
    result = editor_python_smoke._approved_source_prefab_override_path_generation_template_update_report_from_route_status(
        {"attempted": True, "callable": True, "applied": True, "status": _template_update_status()},
        persisted_markers={"actor": True, "motion": True, "both": True},
        source_prefab_changed_this_run=False,
        before_hash="1" * 64,
        after_hash="1" * 64,
    )

    assert result["approved_source_prefab_marker_presence_verified"] is True
    assert result["approved_source_prefab_marker_persistence_verified_this_run"] is False
    assert result["approved_source_prefab_override_path_generation_template_update_verified"] is False
    assert result["approved_source_prefab_propagation_apply_step_verified"] is False
    assert result["approved_source_prefab_actor_simple_motion_wiring_verified"] is False
    assert (
        result["approved_source_prefab_override_path_generation_template_update_blocker"]
        == "blocked_by_source_prefab_markers_preexisting_without_this_run_change"
    )
    assert result["approved_source_prefab_modified"] is False
    assert result["runtime_character_animation_component_wiring_verified"] is False


def test_editor_python_template_update_rejection_probes_call_new_route(tmp_path, monkeypatch):
    project_root = tmp_path / "MAXINE_GoldenCorpus"
    source = (
        project_root
        / "Assets"
        / "Characters"
        / "MAXINE_GoldenCorpus"
        / "prefabs"
        / "release_rigged.prefab"
    )
    monkeypatch.setenv("O3DE_PROJECT_PATH", str(project_root))
    calls = []
    bridge = types.ModuleType("azlmbr.maxine.prefab_bridge")

    def apply_template_update(path, entity_id, actor_component_ref, simple_motion_component_ref):
        calls.append(("new", path, entity_id, actor_component_ref, simple_motion_component_ref))
        if str(path) == str(source):
            return (
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=entity_not_owned_by_approved_source_prefab;"
                "entity_ownership_checked=true;"
                "entity_ownership_verified=false;"
                "entity_owning_prefab_path=C:/OtherProject/Assets/other.prefab;"
                "entity_owning_prefab_matches_requested_path=false;"
                "component_ownership_checked=false;"
                "component_ownership_verified=false"
            )
        return "maxine_prefab_save_update_route_approved_source_template_update_rejected;reason=path_policy_probe"

    def legacy_save(path):
        calls.append(("legacy", path))
        return "maxine_prefab_save_update_route_approved_source_rejected;reason=path_policy_probe"

    bridge.apply_approved_source_prefab_override_path_generation_template_update = apply_template_update
    bridge.save_approved_source_prefab_wiring = legacy_save
    monkeypatch.setitem(sys.modules, "azlmbr", types.ModuleType("azlmbr"))
    monkeypatch.setitem(sys.modules, "azlmbr.maxine", types.ModuleType("azlmbr.maxine"))
    monkeypatch.setitem(sys.modules, "azlmbr.maxine.prefab_bridge", bridge)

    results = editor_python_smoke._call_approved_source_prefab_template_update_route_rejection_probes(
        source,
        entity_id="approved-entity",
        actor_component_ref="actor-component",
        simple_motion_component_ref="simple-motion-component",
    )

    assert results["defaultlevel"]["method"] == "apply_approved_source_prefab_override_path_generation_template_update"
    assert results["wrong_entity_owner"]["rejected"] is True
    assert all(call[0] == "new" for call in calls)
    assert not any(call[0] == "legacy" for call in calls)


def test_editor_python_template_update_legacy_rejection_probes_are_separate(tmp_path, monkeypatch):
    project_root = tmp_path / "MAXINE_GoldenCorpus"
    source = (
        project_root
        / "Assets"
        / "Characters"
        / "MAXINE_GoldenCorpus"
        / "prefabs"
        / "release_rigged.prefab"
    )
    monkeypatch.setenv("O3DE_PROJECT_PATH", str(project_root))
    calls = []
    bridge = types.ModuleType("azlmbr.maxine.prefab_bridge")

    def apply_template_update(path, entity_id, actor_component_ref, simple_motion_component_ref):
        calls.append(("new", path))
        return "maxine_prefab_save_update_route_approved_source_template_update_rejected;reason=path_policy_probe"

    def legacy_save(path):
        calls.append(("legacy", path))
        return "maxine_prefab_save_update_route_approved_source_rejected;reason=path_policy_probe"

    bridge.apply_approved_source_prefab_override_path_generation_template_update = apply_template_update
    bridge.save_approved_source_prefab_wiring = legacy_save
    monkeypatch.setitem(sys.modules, "azlmbr", types.ModuleType("azlmbr"))
    monkeypatch.setitem(sys.modules, "azlmbr.maxine", types.ModuleType("azlmbr.maxine"))
    monkeypatch.setitem(sys.modules, "azlmbr.maxine.prefab_bridge", bridge)

    legacy = editor_python_smoke._call_approved_source_prefab_wiring_rejection_probes(source)
    result = editor_python_smoke._approved_source_prefab_override_path_generation_template_update_report_from_route_status(
        {"attempted": True, "callable": True, "applied": True, "status": _template_update_status()},
        persisted_markers={"actor": True, "motion": True, "both": True},
        source_prefab_changed_this_run=True,
        before_hash="1" * 64,
        after_hash="2" * 64,
        template_update_route_rejection_probes_verified=False,
    )

    assert editor_python_smoke._route_rejection_verified(legacy, "defaultlevel") is True
    assert any(call[0] == "legacy" for call in calls)
    assert not any(call[0] == "new" for call in calls)
    assert result["approved_source_prefab_template_update_route_rejection_probes_verified"] is False
    assert result["approved_source_prefab_override_path_generation_template_update_verified"] is False
    assert (
        result["approved_source_prefab_override_path_generation_template_update_blocker"]
        == "blocked_by_template_update_route_rejection_probes_unverified"
    )


def test_editor_python_template_update_rejection_probe_summary_requires_new_route_results():
    results = {
        "defaultlevel": {"rejected": True},
        "production_level": {"rejected": True},
        "generated_product": {"rejected": True},
        "cache_path": {"rejected": True},
        "unapproved_absolute": {"rejected": True},
        "other_project": {"rejected": True},
        "path_traversal": {"rejected": True},
        "non_prefab": {"rejected": True},
        "wrong_entity_owner": {"rejected": True},
    }

    summary = editor_python_smoke._approved_source_prefab_template_update_route_rejection_probe_summary(results)

    assert summary["approved_source_prefab_template_update_route_rejection_probes_attempted"] is True
    assert summary["approved_source_prefab_template_update_route_rejection_probes_verified"] is True
    assert summary["approved_source_prefab_template_update_route_rejected_defaultlevel_path"] is True
    assert summary["approved_source_prefab_template_update_route_rejected_production_level_path"] is True
    assert summary["approved_source_prefab_template_update_route_rejected_generated_product_path"] is True
    assert summary["approved_source_prefab_template_update_route_rejected_cache_path"] is True
    assert summary["approved_source_prefab_template_update_route_rejected_unapproved_absolute_path"] is True
    assert summary["approved_source_prefab_template_update_route_rejected_other_project_path"] is True
    assert summary["approved_source_prefab_template_update_route_rejected_path_traversal"] is True
    assert summary["approved_source_prefab_template_update_route_rejected_non_prefab_path"] is True
    assert summary["approved_source_prefab_template_update_route_rejected_wrong_entity_owner"] is True


def test_editor_python_override_path_template_update_requires_new_route_safety_probes():
    result = editor_python_smoke._approved_source_prefab_override_path_generation_template_update_report_from_route_status(
        {"attempted": True, "callable": True, "applied": True, "status": _template_update_status()},
        persisted_markers={"actor": True, "motion": True, "both": True},
        source_prefab_changed_this_run=True,
        before_hash="1" * 64,
        after_hash="2" * 64,
        template_update_route_rejection_probes_verified=False,
    )

    assert result["approved_source_prefab_marker_persistence_verified_this_run"] is True
    assert result["approved_source_prefab_override_path_generation_template_update_verified"] is False
    assert (
        result["approved_source_prefab_override_path_generation_template_update_blocker"]
        == "blocked_by_template_update_route_rejection_probes_unverified"
    )
    assert result["approved_source_prefab_modified"] is False


def test_editor_smoke_override_path_template_update_schema_and_semantics_validate():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        editor_python_smoke._approved_source_prefab_override_path_generation_template_update_report_from_route_status(
            {"attempted": True, "callable": True, "applied": True, "status": _template_update_status()},
            persisted_markers={"actor": True, "motion": True, "both": True},
            source_prefab_changed_this_run=True,
            before_hash="1" * 64,
            after_hash="2" * 64,
            template_update_route_rejection_probes_verified=True,
        )
    )
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-source-prefab-override-path-generation-template-update",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_source_prefab_override_path_generation_template_update_source_validation_status": "pass",
            "approved_source_prefab_override_path_generation_template_update_source_validation_verified": True,
            "approved_source_prefab_save_verified": True,
            "approved_source_prefab_actor_component_added": True,
            "approved_source_prefab_simple_motion_component_added": True,
            "approved_source_prefab_actor_asset_assignment_verified": True,
            "approved_source_prefab_motion_asset_assignment_verified": True,
            "approved_source_prefab_property_readback_verified": True,
            "approved_source_prefab_before_hash": "1" * 64,
            "approved_source_prefab_after_hash": "2" * 64,
            "approved_source_prefab_actor_asset_id": "{11111111-1111-1111-1111-111111111111}:00000001",
            "approved_source_prefab_motion_asset_id": "{22222222-2222-2222-2222-222222222222}:00000002",
            "approved_source_prefab_defaultlevel_mutation": False,
            "approved_source_prefab_production_level_mutation": False,
            "approved_source_prefab_hand_authored_unknown_json_used": False,
            "approved_source_prefab_template_update_route_rejection_probes_attempted": True,
            "approved_source_prefab_template_update_route_rejection_probes_verified": True,
            "approved_source_prefab_template_update_route_rejected_defaultlevel_path": True,
            "approved_source_prefab_template_update_route_rejected_production_level_path": True,
            "approved_source_prefab_template_update_route_rejected_generated_product_path": True,
            "approved_source_prefab_template_update_route_rejected_cache_path": True,
            "approved_source_prefab_template_update_route_rejected_unapproved_absolute_path": True,
            "approved_source_prefab_template_update_route_rejected_other_project_path": True,
            "approved_source_prefab_template_update_route_rejected_path_traversal": True,
            "approved_source_prefab_template_update_route_rejected_non_prefab_path": True,
            "approved_source_prefab_template_update_route_rejected_wrong_entity_owner": True,
        }
    )

    schema_result = schema_validate(report, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(report, strict=True)

    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages


def test_editor_smoke_override_path_template_update_rejects_runtime_overclaim():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        editor_python_smoke._approved_source_prefab_override_path_generation_template_update_report_from_route_status(
            {"attempted": True, "callable": True, "applied": True, "status": _template_update_status()},
            persisted_markers={"actor": True, "motion": True, "both": True},
        source_prefab_changed_this_run=True,
        before_hash="1" * 64,
        after_hash="2" * 64,
        template_update_route_rejection_probes_verified=True,
    )
    )
    report["mode"] = "local_editor_python"
    report["status"] = "pass"
    report["diagnostic_mode"] = "approved-source-prefab-override-path-generation-template-update"
    report["approved_source_prefab_override_path_generation_template_update_source_validation_status"] = "pass"
    report["approved_source_prefab_override_path_generation_template_update_source_validation_verified"] = True
    report["approved_source_prefab_save_verified"] = True
    report["approved_source_prefab_actor_component_added"] = True
    report["approved_source_prefab_simple_motion_component_added"] = True
    report["approved_source_prefab_actor_asset_assignment_verified"] = True
    report["approved_source_prefab_motion_asset_assignment_verified"] = True
    report["approved_source_prefab_property_readback_verified"] = True
    report["approved_source_prefab_actor_asset_id"] = "{11111111-1111-1111-1111-111111111111}:00000001"
    report["approved_source_prefab_motion_asset_id"] = "{22222222-2222-2222-2222-222222222222}:00000002"
    report["approved_source_prefab_defaultlevel_mutation"] = False
    report["approved_source_prefab_production_level_mutation"] = False
    report["approved_source_prefab_hand_authored_unknown_json_used"] = False
    report["approved_source_prefab_template_update_route_rejection_probes_attempted"] = True
    report["approved_source_prefab_template_update_route_rejection_probes_verified"] = True
    report["approved_source_prefab_template_update_route_rejected_defaultlevel_path"] = True
    report["approved_source_prefab_template_update_route_rejected_production_level_path"] = True
    report["approved_source_prefab_template_update_route_rejected_generated_product_path"] = True
    report["approved_source_prefab_template_update_route_rejected_cache_path"] = True
    report["approved_source_prefab_template_update_route_rejected_unapproved_absolute_path"] = True
    report["approved_source_prefab_template_update_route_rejected_other_project_path"] = True
    report["approved_source_prefab_template_update_route_rejected_path_traversal"] = True
    report["approved_source_prefab_template_update_route_rejected_non_prefab_path"] = True
    report["approved_source_prefab_template_update_route_rejected_wrong_entity_owner"] = True
    report["runtime_character_animation_component_wiring_verified"] = True

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


def test_editor_smoke_generation_verified_requires_source_prefab_and_spawnable_evidence():
    report = load_json(CORPUS / "editor-smoke-live.release-rigged.pass.example.json")
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "approved-animation-component-wiring-generation",
            "live_editor_execution": True,
            "no_fake_success": True,
            "approved_runtime_animation_component_wiring_editor_generation_attempted": True,
            "approved_runtime_animation_component_wiring_editor_generation_completed": True,
            "approved_runtime_animation_component_wiring_editor_generation_verified": True,
            "approved_runtime_animation_component_wiring_editor_generation_blocker": "",
            "approved_runtime_animation_component_wiring_source_prefab_modified": False,
            "approved_runtime_animation_component_wiring_editor_generated_update_used": True,
            "approved_runtime_animation_component_wiring_hand_authored_unknown_json_used": False,
            "approved_runtime_animation_component_wiring_actor_component_added": True,
            "approved_runtime_animation_component_wiring_simple_motion_component_added": True,
            "approved_runtime_animation_component_wiring_actor_asset_assignment_verified": True,
            "approved_runtime_animation_component_wiring_motion_asset_assignment_verified": True,
            "approved_runtime_animation_component_wiring_property_readback_verified": True,
            "approved_runtime_animation_component_wiring_prefab_save_verified": True,
            "approved_runtime_animation_component_wiring_spawnable_regenerated_or_found": False,
            "runtime_character_animation_component_wiring_claimed": True,
            "runtime_character_animation_component_wiring_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes


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


def test_editor_viewport_visual_material_mode_blocks_capture_under_null_renderer(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_viewport_visual_material_evidence_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "editor-viewport-visual-material-evidence"
        assert "-NullRenderer" in argv
        assert "-rhi=Null" in argv
        payload = json.loads(Path(env["MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE"]).read_text(encoding="utf-8"))
        payload.update(_editor_viewport_visual_material_blocked_payload())
        Path(env["MAXINE_EDITOR_SMOKE_REPORT_OUT"]).write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="editor-viewport-visual-material-evidence",
    )

    assert result["status"] == "pass"
    assert result["diagnostic_mode"] == "editor-viewport-visual-material-evidence"
    assert result["editor_viewport_visual_material_evidence_source_validation_verified"] is True
    assert result["editor_visual_material_capture_api_found"] is True
    assert result["editor_visual_material_capture_requested"] is False
    assert result["editor_visual_material_capture_completed"] is False
    assert result["editor_viewport_visual_material_evidence_blocker"] == (
        "blocked_by_editor_viewport_capture_requires_non_null_rhi"
    )
    assert result["visual_material_rendered_evidence_gate_verified"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_editor_visual_material_verified_requires_rendered_content_and_material_evidence():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_editor_viewport_visual_material_blocked_payload())
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "editor-viewport-visual-material-evidence",
            "live_editor_execution": True,
            "editor_visual_material_capture_requested": True,
            "editor_visual_material_capture_completed": True,
            "editor_visual_material_capture_artifact_exists": True,
            "editor_visual_material_capture_content_validation_attempted": True,
            "editor_visual_material_capture_content_validation_verified": False,
            "editor_visual_material_nonblank_validation_verified": False,
            "editor_visual_material_character_presence_validation_verified": False,
            "editor_visual_material_material_presence_validation_verified": False,
            "visual_material_rendered_evidence_gate_attempted": True,
            "visual_material_rendered_evidence_gate_verified": False,
            "visual_material_gate_claimed": True,
            "visual_material_gate_verified": True,
            "full_runtime_character_visual_material_gate_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "rendered visual/material evidence" in " ".join(result.messages)


def test_non_null_editor_render_capture_mode_uses_non_null_rhi_without_nullrenderer(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_non_null_render_capture_envelope_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "non-null-editor-render-capture-envelope"
        assert env["MAXINE_ENABLE_NON_NULL_EDITOR_RENDER_CAPTURE_ENVELOPE"] == "1"
        assert env["MAXINE_ALLOW_NON_NULL_EDITOR_RENDER_CAPTURE_ENVELOPE"] == "1"
        assert env["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] == "dx12"
        command = " ".join(argv)
        assert "-NullRenderer" not in command
        assert "-rhi=Null" not in command
        assert "-rhi=dx12" in command
        payload = json.loads(Path(env["MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE"]).read_text(encoding="utf-8"))
        payload.update(_non_null_editor_render_capture_envelope_blocked_payload())
        Path(env["MAXINE_EDITOR_SMOKE_REPORT_OUT"]).write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="non-null-editor-render-capture-envelope",
    )

    assert result["status"] == "pass"
    assert result["diagnostic_mode"] == "non-null-editor-render-capture-envelope"
    assert result["non_null_editor_render_capture_envelope_source_validation_verified"] is True
    assert result["non_null_editor_render_capture_null_renderer_used"] is False
    assert result["non_null_editor_render_capture_rhi_requested"] == "dx12"
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_non_null_editor_render_capture_validation_rejects_nullrenderer_envelope():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_non_null_editor_render_capture_envelope_blocked_payload())
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "non-null-editor-render-capture-envelope",
            "non_null_editor_render_capture_envelope_verified": True,
            "non_null_editor_render_capture_envelope_blocker": "",
            "non_null_editor_render_capture_null_renderer_used": True,
            "non_null_editor_render_capture_editor_launched": True,
            "non_null_editor_render_capture_editor_exited_cleanly": True,
            "editor_visual_material_capture_api_available_under_non_null_rhi": True,
            "editor_visual_material_cleanup_verified": True,
            "editor_visual_material_selected_log_scan_passed": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "non_null_editor_render_capture_null_renderer_used" in " ".join(result.messages)


def test_non_null_editor_capture_readiness_does_not_verify_visual_material_gate():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_non_null_editor_render_capture_envelope_blocked_payload())
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "diagnostic_mode": "non-null-editor-render-capture-envelope",
            "non_null_editor_render_capture_envelope_verified": True,
            "non_null_editor_render_capture_envelope_blocker": "",
            "non_null_editor_render_capture_editor_launched": True,
            "non_null_editor_render_capture_editor_exited_cleanly": True,
            "editor_visual_material_capture_api_available_under_non_null_rhi": True,
            "editor_visual_material_capture_requested": True,
            "editor_visual_material_capture_completed": True,
            "editor_visual_material_capture_artifact_path": "artifacts/o3de-integration/editor-smoke/capture.png",
            "editor_visual_material_capture_artifact_exists": True,
            "editor_visual_material_capture_artifact_format": "png",
            "editor_visual_material_capture_artifact_width": 1280,
            "editor_visual_material_capture_artifact_height": 720,
            "editor_visual_material_capture_artifact_size_bytes": 4096,
            "visual_material_capture_readiness_verified": True,
            "visual_material_rendered_evidence_gate_attempted": True,
            "visual_material_rendered_evidence_gate_verified": False,
            "visual_material_gate_claimed": True,
            "visual_material_gate_verified": True,
            "full_runtime_character_visual_material_gate_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "visual_material_gate_verified" in " ".join(result.messages)


def test_non_null_visual_runner_readiness_mode_pins_contract_without_launching_editor(tmp_path):
    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        raise AssertionError("readiness/temp-scene contract diagnostic must not launch Editor")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=_live_env(tmp_path),
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="non-null-editor-visual-runner-readiness",
    )

    assert result["status"] == "pass"
    assert result["diagnostic_mode"] == "non-null-editor-visual-runner-readiness"
    assert result["non_null_editor_visual_runner_readiness_source_validation_verified"] is True
    assert result["non_null_editor_visual_runner_readiness_verified"] is False
    assert result["visible_desktop_session_check_attempted"] is True
    assert result["visible_desktop_session_verified"] is False
    assert result["rhi_readiness_check_attempted"] is True
    assert result["rhi_readiness_verified"] is True
    assert result["selected_rhi"] == "dx12"
    assert result["non_null_editor_launch_attempted"] is False
    assert result["editor_temp_visual_scene_contract_pinned"] is True
    assert result["editor_temp_visual_scene_contract_verified"] is True
    assert result["editor_temp_visual_scene_approved_root"] == "Levels/_maxine_visual_smoke"
    assert result["editor_visual_material_capture_artifact_policy_verified"] is True
    assert result["editor_visual_material_capture_requested"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_non_null_visual_runner_readiness_validation_rejects_launch_without_visible_desktop():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_non_null_visual_runner_readiness_contract_payload())
    report.update(
        {
            "status": "pass",
            "non_null_editor_visual_runner_readiness_verified": True,
            "non_null_editor_visual_runner_readiness_blocker": "",
            "visible_desktop_session_verified": False,
            "gpu_or_driver_readiness_verified": True,
            "non_null_editor_launch_attempted": True,
            "non_null_editor_launch_completed": True,
            "non_null_editor_launch_verified": True,
            "non_null_editor_launch_exit_code": 0,
            "non_null_editor_launch_blocker": "",
            "editor_visual_material_capture_api_available_under_non_null_rhi": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "visible_desktop_session_verified" in " ".join(result.messages)


def test_non_null_visual_runner_readiness_rejects_unsafe_temp_scene_contract():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_non_null_visual_runner_readiness_contract_payload())
    report.update(
        {
            "status": "pass",
            "editor_temp_visual_scene_contract_verified": True,
            "editor_temp_visual_scene_approved_root": "Levels/defaultlevel",
            "editor_temp_visual_scene_defaultlevel_mutation": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_PATH_UNSAFE" in result.error_codes
    assert "temp visual scene" in " ".join(result.messages)


def test_non_null_visual_runner_readiness_contract_does_not_verify_visual_gate():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_non_null_visual_runner_readiness_contract_payload())
    report.update(
        {
            "status": "pass",
            "visual_material_gate_claimed": True,
            "visual_material_gate_verified": True,
            "full_runtime_character_visual_material_gate_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "visual_material_gate_verified" in " ".join(result.messages)


def test_non_null_desktop_rhi_readiness_mode_runs_safe_checks_without_launching_editor(tmp_path):
    env = _live_env(tmp_path)
    _write_non_null_desktop_rhi_source_files(Path(env["O3DE_ENGINE_ROOT"]))

    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        raise AssertionError("desktop/RHI readiness diagnostic must not launch Editor")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=env,
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="non-null-editor-desktop-rhi-readiness",
    )

    schema_result = schema_validate(result, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert result["diagnostic_mode"] == "non-null-editor-desktop-rhi-readiness"
    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["non_null_editor_desktop_rhi_readiness_attempted"] is True
    assert result["non_null_editor_desktop_rhi_readiness_completed"] is True
    assert result["non_null_editor_desktop_rhi_readiness_source_validation_verified"] is True
    assert result["visible_desktop_session_check_attempted"] is True
    assert result["visible_desktop_session_check_method"]
    assert "visible_desktop_session_state" in result
    assert "windows_session_type" in result
    assert "windows_session_interactive" in result
    assert result["gpu_or_driver_readiness_check_attempted"] is True
    assert result["gpu_or_driver_readiness_check_method"]
    assert "gpu_adapter_count" in result
    assert isinstance(result["gpu_adapter_summary"], list)
    assert result["rhi_readiness_check_attempted"] is True
    assert result["rhi_readiness_check_method"]
    assert result["rhi_readiness_verified"] is True
    assert result["selected_rhi"] == "dx12"
    assert result["rhi_fallback_considered"] is True
    assert result["rhi_fallback_selected"] is False
    assert result["non_null_editor_launch_attempted"] is False
    assert result["editor_visual_material_capture_requested"] is False
    assert result["editor_visual_material_capture_completed"] is False
    assert result["visual_material_capture_readiness_verified"] is False
    assert result["visual_material_rendered_evidence_gate_verified"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_non_null_desktop_rhi_readiness_validation_requires_all_readiness_gates():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_non_null_desktop_rhi_readiness_contract_payload())
    report.update(
        {
            "status": "pass",
            "non_null_editor_desktop_rhi_readiness_verified": True,
            "non_null_editor_desktop_rhi_readiness_blocker": "",
            "visible_desktop_session_verified": True,
            "gpu_or_driver_readiness_verified": False,
            "rhi_readiness_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "gpu_or_driver_readiness_verified" in " ".join(result.messages)


def test_non_null_desktop_rhi_readiness_validation_rejects_launch_without_verified_readiness():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_non_null_desktop_rhi_readiness_contract_payload())
    report.update(
        {
            "status": "pass",
            "non_null_editor_launch_attempted": True,
            "non_null_editor_launch_completed": True,
            "non_null_editor_launch_verified": True,
            "non_null_editor_launch_exit_code": 0,
            "visible_desktop_session_verified": False,
            "gpu_or_driver_readiness_verified": True,
            "rhi_readiness_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "non_null_editor_launch_attempted=true requires visible_desktop_session_verified=true" in " ".join(
        result.messages
    )


def test_non_null_desktop_rhi_readiness_contract_does_not_verify_visual_gate():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_non_null_desktop_rhi_readiness_contract_payload())
    report.update(
        {
            "status": "pass",
            "visual_material_gate_claimed": True,
            "visual_material_gate_verified": True,
            "visual_material_rendered_evidence_gate_verified": True,
            "full_runtime_character_visual_material_gate_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "visual_material_gate_verified" in " ".join(result.messages)


def test_live_non_null_editor_launch_mode_uses_non_null_rhi_without_screenshot_or_temp_scene(tmp_path):
    env = _live_env(tmp_path)
    _write_non_null_desktop_rhi_source_files(Path(env["O3DE_ENGINE_ROOT"]))

    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_live_non_null_launch_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "live-non-null-editor-launch"
        assert env["MAXINE_ENABLE_LIVE_NON_NULL_EDITOR_LAUNCH"] == "1"
        assert env["MAXINE_ALLOW_LIVE_NON_NULL_EDITOR_LAUNCH"] == "1"
        assert env["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] == "dx12"
        command = " ".join(argv)
        assert "-NullRenderer" not in command
        assert "-rhi=Null" not in command
        assert "-rhi=dx12" in command
        assert "--runpython" in argv
        payload = json.loads(Path(env["MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE"]).read_text(encoding="utf-8"))
        payload.update(_live_non_null_editor_launch_verified_payload())
        Path(env["MAXINE_EDITOR_SMOKE_REPORT_OUT"]).write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=env,
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="live-non-null-editor-launch",
    )

    schema_result = schema_validate(result, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert result["diagnostic_mode"] == "live-non-null-editor-launch"
    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["live_non_null_editor_launch_source_validation_verified"] is True
    assert result["visible_desktop_session_verified"] is True
    assert result["gpu_or_driver_readiness_verified"] is True
    assert result["rhi_readiness_verified"] is True
    assert result["live_non_null_editor_launch_attempted"] is True
    assert result["live_non_null_editor_launch_completed"] is True
    assert result["live_non_null_editor_launch_verified"] is True
    assert result["non_null_editor_launch_attempted"] is True
    assert result["non_null_editor_launch_completed"] is True
    assert result["non_null_editor_launch_verified"] is True
    assert result["live_non_null_editor_launch_selected_rhi"] == "dx12"
    assert result["live_non_null_editor_launch_null_renderer_used"] is False
    assert result["live_non_null_editor_launch_python_wrapper_executed"] is True
    assert result["live_non_null_editor_launch_exit_code"] == 0
    assert result["live_non_null_editor_launch_timeout"] is False
    assert result["live_non_null_editor_launch_killed"] is False
    assert result["live_non_null_editor_launch_selected_log_scan_passed"] is True
    assert result["existing_nullrenderer_safe_editor_lane_preserved"] is True
    assert result["editor_temp_visual_scene_contract_pinned"] is True
    assert result["editor_temp_visual_scene_created"] is False
    assert result["editor_visual_material_temp_scene_created"] is False
    assert result["editor_visual_material_capture_requested"] is False
    assert result["editor_visual_material_capture_completed"] is False
    assert result["visual_material_capture_readiness_verified"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_live_non_null_editor_launch_source_validation_failure_blocks_before_process(tmp_path, monkeypatch):
    env = _live_env(tmp_path)
    _write_non_null_desktop_rhi_source_files(Path(env["O3DE_ENGINE_ROOT"]))

    def fail_launch_source_validation(engine_root):
        return {
            "status": "live_non_null_editor_launch_source_validation_inconclusive",
            "blocker": "blocked_by_live_non_null_editor_launch_required_symbol_missing",
            "files": [
                {
                    "path": "tools/o3de/editor_python/editor_live_non_null_launch_smoke.py",
                    "status": "fail",
                    "missing_symbols": ["from tools.o3de.editor_python import maxine_package_prefab_smoke"],
                }
            ],
            "missing": [
                {
                    "path": "tools/o3de/editor_python/editor_live_non_null_launch_smoke.py",
                    "status": "fail",
                }
            ],
        }

    monkeypatch.setattr(editor_python_smoke, "_live_non_null_editor_launch_source_validation", fail_launch_source_validation)

    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        raise AssertionError("launch source-validation failure must block before spawning Editor")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=env,
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="live-non-null-editor-launch",
    )

    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["non_null_editor_desktop_rhi_readiness_verified"] is True
    assert result["live_non_null_editor_launch_source_validation_verified"] is False
    assert result["live_non_null_editor_launch_blocker"] == (
        "blocked_by_live_non_null_editor_launch_required_symbol_missing"
    )
    assert result["live_editor_execution"] is False
    assert result["live_non_null_editor_launch_attempted"] is False
    assert result["live_non_null_editor_launch_completed"] is False
    assert result["live_non_null_editor_launch_verified"] is False
    assert result["non_null_editor_launch_attempted"] is False
    assert result["non_null_editor_launch_completed"] is False
    assert result["non_null_editor_launch_verified"] is False
    assert result["editor_visual_material_capture_requested"] is False
    assert result["editor_visual_material_capture_completed"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_live_non_null_editor_launch_readiness_failure_still_blocks_before_process(tmp_path, monkeypatch):
    env = _live_env(tmp_path)
    _write_non_null_desktop_rhi_source_files(Path(env["O3DE_ENGINE_ROOT"]))

    def fail_visible_desktop():
        return {
            "visible_desktop_session_check_attempted": True,
            "visible_desktop_session_check_method": (
                "ProcessIdToSessionId+WTSGetActiveConsoleSessionId+OpenInputDesktop"
            ),
            "visible_desktop_session_verified": False,
            "visible_desktop_session_state": "service_session",
            "visible_desktop_session_blocker": (
                "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
            ),
            "windows_session_id": 0,
            "windows_session_type": "service",
            "windows_session_interactive": False,
        }

    monkeypatch.setattr(editor_python_smoke, "_detect_visible_desktop_session_readiness", fail_visible_desktop)

    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        raise AssertionError("desktop/session readiness failure must block before spawning Editor")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=env,
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="live-non-null-editor-launch",
    )

    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["non_null_editor_desktop_rhi_readiness_verified"] is False
    assert result["live_non_null_editor_launch_source_validation_verified"] is True
    assert result["live_non_null_editor_launch_blocker"] == (
        "blocked_by_non_null_editor_render_capture_requires_visible_desktop_session"
    )
    assert result["live_editor_execution"] is False
    assert result["live_non_null_editor_launch_attempted"] is False
    assert result["live_non_null_editor_launch_completed"] is False
    assert result["live_non_null_editor_launch_verified"] is False
    assert result["editor_visual_material_capture_requested"] is False
    assert result["runtime_character_proof_verified"] is False


def test_live_non_null_editor_launch_validation_rejects_nullrenderer_command():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_live_non_null_editor_launch_verified_payload())
    report.update(
        {
            "command_argv_redacted": [
                "Editor.exe",
                "-NullRenderer",
                "-rhi=Null",
                "--runpython",
                "editor_live_non_null_launch_smoke.py",
            ],
            "live_non_null_editor_launch_command": [
                "Editor.exe",
                "-NullRenderer",
                "-rhi=Null",
                "--runpython",
                "editor_live_non_null_launch_smoke.py",
            ],
            "live_non_null_editor_launch_null_renderer_used": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "live_non_null_editor_launch_null_renderer_used" in " ".join(result.messages)


def test_live_non_null_editor_launch_does_not_verify_visual_gate():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_live_non_null_editor_launch_verified_payload())
    report.update(
        {
            "visual_material_gate_claimed": True,
            "visual_material_gate_verified": True,
            "visual_material_rendered_evidence_gate_verified": True,
            "full_runtime_character_visual_material_gate_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "visual_material_gate_verified" in " ".join(result.messages)


def test_editor_screenshot_capture_artifact_readiness_mode_records_artifact_without_visual_gate(tmp_path):
    env = _live_env(tmp_path)
    _write_non_null_desktop_rhi_source_files(Path(env["O3DE_ENGINE_ROOT"]))

    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_screenshot_capture_artifact_readiness_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "editor-screenshot-capture-artifact-readiness"
        assert env["MAXINE_ENABLE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_READINESS"] == "1"
        assert env["MAXINE_ALLOW_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_READINESS"] == "1"
        assert env["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] == "dx12"
        assert env["MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_PATH"].endswith(".png")
        command = " ".join(argv)
        assert "-NullRenderer" not in command
        assert "-rhi=Null" not in command
        assert "-rhi=dx12" in command
        payload = json.loads(Path(env["MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE"]).read_text(encoding="utf-8"))
        payload.update(_editor_screenshot_capture_artifact_readiness_verified_payload())
        payload["editor_visual_material_capture_artifact_path"] = env["MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_PATH"]
        Path(env["MAXINE_EDITOR_SMOKE_REPORT_OUT"]).write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=env,
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="editor-screenshot-capture-artifact-readiness",
    )

    schema_result = schema_validate(result, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert result["diagnostic_mode"] == "editor-screenshot-capture-artifact-readiness"
    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["editor_screenshot_capture_artifact_readiness_source_validation_verified"] is True
    assert result["visible_desktop_session_verified"] is True
    assert result["gpu_or_driver_readiness_verified"] is True
    assert result["rhi_readiness_verified"] is True
    assert result["live_non_null_editor_launch_verified"] is True
    assert result["live_non_null_editor_launch_null_renderer_used"] is False
    assert result["live_non_null_editor_launch_python_wrapper_executed"] is True
    assert result["editor_visual_material_capture_api_available_under_non_null_rhi"] is True
    assert result["editor_visual_material_capture_requested"] is True
    assert result["editor_visual_material_capture_request_accepted"] is True
    assert result["editor_visual_material_capture_completed"] is True
    assert result["editor_visual_material_capture_artifact_exists"] is True
    assert result["editor_visual_material_capture_artifact_format"] == "png"
    assert result["editor_visual_material_capture_artifact_width"] > 0
    assert result["editor_visual_material_capture_artifact_height"] > 0
    assert result["editor_visual_material_capture_artifact_size_bytes"] > 0
    assert result["editor_visual_material_capture_artifact_sha256"]
    assert result["visual_material_capture_readiness_verified"] is True
    assert result["editor_visual_material_capture_content_validation_verified"] is False
    assert result["editor_visual_material_nonblank_validation_verified"] is False
    assert result["editor_visual_material_character_presence_validation_verified"] is False
    assert result["editor_visual_material_material_presence_validation_verified"] is False
    assert result["editor_visual_material_temp_scene_created"] is False
    assert result["visual_material_rendered_evidence_gate_verified"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_editor_screenshot_capture_artifact_source_validation_failure_blocks_before_process(tmp_path, monkeypatch):
    env = _live_env(tmp_path)
    _write_non_null_desktop_rhi_source_files(Path(env["O3DE_ENGINE_ROOT"]))

    def fail_capture_source_validation(engine_root):
        return {
            "status": "editor_screenshot_capture_artifact_readiness_source_validation_inconclusive",
            "blocker": "blocked_by_editor_screenshot_capture_requires_additional_source_validation",
            "files": [
                {
                    "path": "tools/o3de/editor_python/editor_screenshot_capture_artifact_readiness_smoke.py",
                    "status": "missing_symbols",
                    "missing_symbols": ["editor-screenshot-capture-artifact-readiness"],
                }
            ],
            "missing": [{"path": "tools/o3de/editor_python/editor_screenshot_capture_artifact_readiness_smoke.py"}],
        }

    monkeypatch.setattr(
        editor_python_smoke,
        "_editor_screenshot_capture_artifact_readiness_source_validation",
        fail_capture_source_validation,
    )

    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        raise AssertionError("screenshot capture source-validation failure must block before spawning Editor")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=env,
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="editor-screenshot-capture-artifact-readiness",
    )

    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["live_editor_execution"] is False
    assert result["non_null_editor_desktop_rhi_readiness_verified"] is True
    assert result["live_non_null_editor_launch_source_validation_verified"] is True
    assert result["editor_screenshot_capture_artifact_readiness_source_validation_verified"] is False
    assert result["editor_screenshot_capture_artifact_readiness_blocker"] == (
        "blocked_by_editor_screenshot_capture_requires_additional_source_validation"
    )
    assert result["editor_screenshot_capture_artifact_readiness_attempted"] is False
    assert result["editor_screenshot_capture_artifact_readiness_completed"] is False
    assert result["editor_screenshot_capture_artifact_readiness_verified"] is False
    assert result["editor_visual_material_capture_requested"] is False
    assert result["editor_visual_material_capture_completed"] is False
    assert result["visual_material_capture_readiness_verified"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_editor_screenshot_capture_artifact_readiness_requires_artifact_metadata():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_editor_screenshot_capture_artifact_readiness_verified_payload())
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "editor_visual_material_capture_artifact_width": 0,
            "editor_visual_material_capture_artifact_size_bytes": 0,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "artifact" in " ".join(result.messages)


def test_editor_screenshot_capture_artifact_readiness_does_not_verify_visual_gate():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_editor_screenshot_capture_artifact_readiness_verified_payload())
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "visual_material_gate_claimed": True,
            "visual_material_gate_verified": True,
            "visual_material_rendered_evidence_gate_attempted": True,
            "visual_material_rendered_evidence_gate_verified": True,
            "full_runtime_character_visual_material_gate_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "visual_material_gate_verified" in " ".join(result.messages)


def test_active_viewport_temp_scene_readiness_mode_keeps_capture_off(tmp_path):
    env = _live_env(tmp_path)
    _write_non_null_desktop_rhi_source_files(Path(env["O3DE_ENGINE_ROOT"]))

    def fake_editor_runner(*, argv, cwd, env, timeout_seconds):
        assert "editor_active_viewport_temp_scene_readiness_smoke.py" in argv[-1].replace("\\", "/")
        assert env["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] == "editor-active-viewport-temp-scene-readiness"
        assert env["MAXINE_ENABLE_EDITOR_ACTIVE_VIEWPORT_TEMP_SCENE_READINESS"] == "1"
        assert env["MAXINE_ALLOW_EDITOR_ACTIVE_VIEWPORT_TEMP_SCENE_READINESS"] == "1"
        assert env["MAXINE_EDITOR_RENDER_CAPTURE_RHI"] == "dx12"
        assert "MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_PATH" not in env
        command = " ".join(argv)
        assert "-NullRenderer" not in command
        assert "-rhi=Null" not in command
        assert "-rhi=dx12" in command
        payload = json.loads(Path(env["MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE"]).read_text(encoding="utf-8"))
        payload.update(_active_viewport_temp_scene_readiness_payload())
        Path(env["MAXINE_EDITOR_SMOKE_REPORT_OUT"]).write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    result = run_editor_smoke_corpus(
        CORPUS,
        enable_editor_smoke=True,
        strict_integration=True,
        env=env,
        command_runner=fake_editor_runner,
        artifact_root=tmp_path / "editor-smoke-artifacts",
        diagnostic_mode="editor-active-viewport-temp-scene-readiness",
    )

    schema_result = schema_validate(result, load_json(SCHEMA))
    semantic_result = validate_editor_smoke_report(result, strict=True)

    assert result["status"] == "pass"
    assert result["diagnostic_mode"] == "editor-active-viewport-temp-scene-readiness"
    assert schema_result.status == "pass", schema_result.messages
    assert semantic_result.status == "pass", semantic_result.messages
    assert result["editor_active_viewport_temp_scene_readiness_source_validation_verified"] is True
    assert result["visible_desktop_session_verified"] is True
    assert result["gpu_or_driver_readiness_verified"] is True
    assert result["rhi_readiness_verified"] is True
    assert result["live_non_null_editor_launch_verified"] is True
    assert result["live_non_null_editor_launch_null_renderer_used"] is False
    assert result["live_non_null_editor_launch_python_wrapper_executed"] is True
    assert result["editor_active_viewport_readiness_attempted"] is True
    assert result["editor_active_viewport_readiness_verified"] is False
    assert result["editor_active_viewport_window_handle_available"] is False
    assert result["editor_frame_capture_target_readiness_attempted"] is True
    assert result["editor_frame_capture_target_readiness_verified"] is False
    assert result["editor_temp_visual_scene_readiness_attempted"] is True
    assert result["editor_temp_visual_scene_readiness_verified"] is True
    assert result["editor_temp_visual_scene_approved_root"] == "Levels/_maxine_visual_smoke"
    assert result["editor_temp_visual_scene_created"] is False
    assert result["editor_temp_visual_scene_cleanup_verified"] is True
    assert result["editor_temp_visual_scene_defaultlevel_mutation"] is False
    assert result["editor_temp_visual_scene_production_level_mutation"] is False
    assert result["editor_visual_material_capture_target_readiness_verified"] is True
    assert result["editor_visual_material_capture_requested"] is False
    assert result["editor_visual_material_capture_completed"] is False
    assert result["visual_material_capture_readiness_verified"] is False
    assert result["visual_material_rendered_evidence_gate_verified"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_active_viewport_temp_scene_readiness_records_blocker_without_capture(monkeypatch):
    monkeypatch.setenv("O3DE_ENGINE_ROOT", "")
    monkeypatch.setattr(
        editor_python_smoke,
        "_editor_active_viewport_temp_scene_readiness_source_validation",
        lambda _engine_root: {
            "status": "editor_active_viewport_temp_scene_readiness_source_validation_pass",
            "blocker": "",
        },
    )
    monkeypatch.setattr(
        editor_python_smoke,
        "_live_non_null_editor_launch_source_validation",
        lambda _engine_root: {"status": "live_non_null_editor_launch_source_validation_pass"},
    )

    result = editor_python_smoke._run_editor_active_viewport_temp_scene_readiness_checks(
        _live_non_null_editor_launch_verified_payload(),
        progress_log=None,
        general=None,
    )

    assert result["editor_active_viewport_temp_scene_readiness_source_validation_verified"] is True
    assert result["live_non_null_editor_launch_verified"] is True
    assert result["editor_active_viewport_readiness_attempted"] is True
    assert result["editor_active_viewport_readiness_verified"] is False
    assert result["editor_active_viewport_blocker"] == "blocked_by_editor_active_viewport_api_unavailable"
    assert result["editor_frame_capture_target_readiness_verified"] is False
    assert result["editor_temp_visual_scene_readiness_verified"] is True
    assert result["editor_visual_material_capture_target_readiness_verified"] is True
    assert result["editor_visual_material_capture_requested"] is False
    assert result["editor_visual_material_capture_completed"] is False
    assert result["visual_material_capture_readiness_verified"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_active_viewport_temp_scene_readiness_does_not_verify_visual_gate():
    report = _fixture("release_rigged.fixture.report.json")
    report.update(_active_viewport_temp_scene_readiness_payload())
    report.update(
        {
            "mode": "local_editor_python",
            "status": "pass",
            "visual_material_gate_claimed": True,
            "visual_material_gate_verified": True,
            "visual_material_rendered_evidence_gate_verified": True,
            "full_runtime_character_visual_material_gate_verified": True,
        }
    )

    result = validate_editor_smoke_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in result.error_codes
    assert "visual_material_gate_verified" in " ".join(result.messages)


def _install_fake_frame_capture_modules(monkeypatch, *, callback_parameters, success_value="success"):
    azlmbr_module = types.ModuleType("azlmbr")
    azlmbr_module.__path__ = []
    atom_module = types.ModuleType("azlmbr.atom")
    bus_module = types.ModuleType("azlmbr.bus")
    bus_module.Broadcast = object()
    atom_module.FrameCaptureResult_Success = success_value

    class FakeOutcome:
        def IsSuccess(self):
            return True

        def GetValue(self):
            return "capture-id"

    class FakeFrameCaptureNotificationBusHandler:
        def connect(self, capture_id):
            assert capture_id == "capture-id"

        def add_callback(self, callback_name, callback):
            assert callback_name == "OnFrameCaptureFinished"
            callback(callback_parameters)

        def disconnect(self):
            return None

    atom_module.FrameCaptureRequestBus = lambda *_args: FakeOutcome()
    atom_module.FrameCaptureNotificationBusHandler = FakeFrameCaptureNotificationBusHandler
    azlmbr_module.atom = atom_module
    azlmbr_module.bus = bus_module

    monkeypatch.setitem(sys.modules, "azlmbr", azlmbr_module)
    monkeypatch.setitem(sys.modules, "azlmbr.atom", atom_module)
    monkeypatch.setitem(sys.modules, "azlmbr.bus", bus_module)
    return atom_module


def test_screenshot_completion_callback_parameter_helper_handles_common_shapes():
    assert editor_python_smoke._as_list(None) == []
    assert editor_python_smoke._as_list(("success", "done")) == ["success", "done"]
    assert editor_python_smoke._as_list(["success", "done"]) == ["success", "done"]
    assert editor_python_smoke._as_list({"result": "success", "info": "done"}) == [
        {"result": "success", "info": "done"}
    ]
    assert editor_python_smoke._as_list("success") == ["success"]


def test_screenshot_completion_callback_marks_success_without_nameerror(tmp_path, monkeypatch):
    _install_fake_frame_capture_modules(monkeypatch, callback_parameters=("success", "frame complete"))

    class FakeGeneral:
        def idle_wait_frames(self, _frames):
            raise AssertionError("callback should complete before polling waits")

    result = editor_python_smoke._attempt_editor_screenshot_capture(
        capture_path=tmp_path / "missing.png",
        progress_log=None,
        general=FakeGeneral(),
    )

    assert result["request_accepted"] is True
    assert result["completed"] is True
    assert result["completion_source"] == "FrameCaptureNotificationBus.OnFrameCaptureFinished"
    assert result["completion_info"] == "frame complete"
    assert result["completion_result"] == "success"
    assert result["blocker"] == "blocked_by_editor_screenshot_capture_artifact_missing"
    assert result["artifact"]["exists"] is False


def test_screenshot_completion_callback_rejects_unrecognized_parameters(tmp_path, monkeypatch):
    _install_fake_frame_capture_modules(monkeypatch, callback_parameters=None)

    class FakeGeneral:
        def idle_wait_frames(self, _frames):
            return None

    result = editor_python_smoke._attempt_editor_screenshot_capture(
        capture_path=tmp_path / "missing.png",
        progress_log=None,
        general=FakeGeneral(),
    )

    assert result["request_accepted"] is True
    assert result["completed"] is False
    assert result["blocker"] == "blocked_by_editor_screenshot_capture_callback_parameters_unrecognized"
    assert result["artifact"]["exists"] is False


def test_screenshot_readiness_keeps_no_active_viewport_gate_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("O3DE_ENGINE_ROOT", str(tmp_path / "o3de"))
    monkeypatch.setenv("MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setenv("MAXINE_EDITOR_SCREENSHOT_CAPTURE_ARTIFACT_PATH", str(tmp_path / "capture.png"))
    monkeypatch.delenv("MAXINE_ALLOW_EDITOR_SCREENSHOT_CAPTURE_REQUEST", raising=False)
    monkeypatch.delenv("MAXINE_EDITOR_SCREENSHOT_CAPTURE_ACTIVE_VIEWPORT_VERIFIED", raising=False)

    monkeypatch.setattr(
        editor_python_smoke,
        "_editor_screenshot_capture_artifact_readiness_source_validation",
        lambda _engine_root: {"status": "editor_screenshot_capture_artifact_readiness_source_validation_pass"},
    )
    monkeypatch.setattr(
        editor_python_smoke,
        "_live_non_null_editor_launch_source_validation",
        lambda _engine_root: {"status": "live_non_null_editor_launch_source_validation_pass"},
    )

    result = editor_python_smoke._run_editor_screenshot_capture_artifact_readiness_checks(
        _live_non_null_editor_launch_verified_payload(),
        progress_log=None,
        general=object(),
    )

    assert result["editor_screenshot_capture_artifact_readiness_source_validation_verified"] is True
    assert result["live_non_null_editor_launch_verified"] is True
    assert result["editor_visual_material_capture_requested"] is False
    assert result["editor_visual_material_capture_completed"] is False
    assert result["visual_material_capture_readiness_verified"] is False
    assert result["editor_screenshot_capture_artifact_readiness_blocker"] == (
        "blocked_by_editor_screenshot_capture_requires_active_viewport"
    )
    assert result["editor_visual_material_temp_scene_created"] is False
    assert result["editor_temp_visual_scene_created"] is False
    assert result["visual_material_gate_verified"] is False
    assert result["runtime_character_proof_verified"] is False


def test_screenshot_artifact_validation_records_precise_metadata_blockers(tmp_path):
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    assert editor_python_smoke._capture_artifact_validation(empty)["blocker"] == (
        "blocked_by_editor_screenshot_capture_artifact_empty"
    )

    text_file = tmp_path / "not-png.png"
    text_file.write_text("not a png", encoding="utf-8")
    assert editor_python_smoke._capture_artifact_validation(text_file)["blocker"] == (
        "blocked_by_editor_screenshot_capture_artifact_format_unrecognized"
    )

    invalid_dimensions = tmp_path / "invalid-dimensions.png"
    invalid_dimensions.write_bytes(b"\x89PNG\r\n\x1a\n" + (b"\x00" * 16))
    assert editor_python_smoke._capture_artifact_validation(invalid_dimensions)["blocker"] == (
        "blocked_by_editor_screenshot_capture_artifact_dimensions_invalid"
    )


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


def test_non_null_visual_runner_wrapper_bootstraps_repo_root_before_package_import():
    wrapper = REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_non_null_visual_runner_readiness_smoke.py"

    text = wrapper.read_text(encoding="utf-8-sig")

    assert "import sys" in text
    assert "from pathlib import Path" in text
    assert "REPO_ROOT = Path(__file__).resolve().parents[3]" in text
    assert "sys.path.insert(0, str(REPO_ROOT))" in text
    assert "from tools.o3de.editor_python import maxine_package_prefab_smoke" in text
    assert "import maxine_package_prefab_smoke" not in {line.strip() for line in text.splitlines()}
    assert text.index("sys.path.insert(0, str(REPO_ROOT))") < text.index(
        "from tools.o3de.editor_python import maxine_package_prefab_smoke"
    )


def test_non_null_desktop_rhi_wrapper_bootstraps_repo_root_before_package_import():
    wrapper = REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_non_null_desktop_rhi_readiness_smoke.py"

    text = wrapper.read_text(encoding="utf-8-sig")

    assert "import sys" in text
    assert "from pathlib import Path" in text
    assert "REPO_ROOT = Path(__file__).resolve().parents[3]" in text
    assert "sys.path.insert(0, str(REPO_ROOT))" in text
    assert "from tools.o3de.editor_python import maxine_package_prefab_smoke" in text
    assert "import maxine_package_prefab_smoke" not in {line.strip() for line in text.splitlines()}
    assert text.index("sys.path.insert(0, str(REPO_ROOT))") < text.index(
        "from tools.o3de.editor_python import maxine_package_prefab_smoke"
    )


def test_live_non_null_editor_launch_wrapper_bootstraps_repo_root_before_package_import():
    wrapper = REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_live_non_null_launch_smoke.py"

    text = wrapper.read_text(encoding="utf-8-sig")

    assert "import sys" in text
    assert "from pathlib import Path" in text
    assert "REPO_ROOT = Path(__file__).resolve().parents[3]" in text
    assert "sys.path.insert(0, str(REPO_ROOT))" in text
    assert "from tools.o3de.editor_python import maxine_package_prefab_smoke" in text
    assert "import maxine_package_prefab_smoke" not in {line.strip() for line in text.splitlines()}
    assert text.index("sys.path.insert(0, str(REPO_ROOT))") < text.index(
        "from tools.o3de.editor_python import maxine_package_prefab_smoke"
    )


def test_editor_screenshot_capture_artifact_wrapper_bootstraps_repo_root_before_package_import():
    wrapper = REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_screenshot_capture_artifact_readiness_smoke.py"

    text = wrapper.read_text(encoding="utf-8-sig")

    assert "import sys" in text
    assert "from pathlib import Path" in text
    assert "REPO_ROOT = Path(__file__).resolve().parents[3]" in text
    assert "sys.path.insert(0, str(REPO_ROOT))" in text
    assert "from tools.o3de.editor_python import maxine_package_prefab_smoke" in text
    assert "import maxine_package_prefab_smoke" not in {line.strip() for line in text.splitlines()}
    assert text.index("sys.path.insert(0, str(REPO_ROOT))") < text.index(
        "from tools.o3de.editor_python import maxine_package_prefab_smoke"
    )


def test_active_viewport_temp_scene_readiness_wrapper_bootstraps_repo_root_before_package_import():
    wrapper = REPO_ROOT / "tools" / "o3de" / "editor_python" / "editor_active_viewport_temp_scene_readiness_smoke.py"

    text = wrapper.read_text(encoding="utf-8-sig")

    assert "import sys" in text
    assert "from pathlib import Path" in text
    assert "REPO_ROOT = Path(__file__).resolve().parents[3]" in text
    assert "sys.path.insert(0, str(REPO_ROOT))" in text
    assert "from tools.o3de.editor_python import maxine_package_prefab_smoke" in text
    assert "import maxine_package_prefab_smoke" not in {line.strip() for line in text.splitlines()}
    assert text.index("sys.path.insert(0, str(REPO_ROOT))") < text.index(
        "from tools.o3de.editor_python import maxine_package_prefab_smoke"
    )


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
