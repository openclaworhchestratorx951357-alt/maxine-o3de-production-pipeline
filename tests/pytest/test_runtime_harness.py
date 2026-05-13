import json
import os
import subprocess
from pathlib import Path

from tools.o3de import runtime_harness


def _project(root: Path) -> Path:
    project = root / "MAXINE_GoldenCorpus"
    project.mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"project_name": "MAXINE_GoldenCorpus", "gem_names": ["EditorPythonBindings"]}),
        encoding="utf-8",
    )
    return project


def _engine(root: Path, *, launcher: bool = True) -> Path:
    engine = root / "o3de"
    bin_dir = engine / "build" / "windows" / "bin" / "profile"
    bin_dir.mkdir(parents=True)
    (engine / "engine.json").write_text('{"engine_name":"o3de"}\n', encoding="utf-8")
    for source_path in (
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.cpp",
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Settings" / "SettingsRegistryMergeUtils.h",
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Component" / "ComponentApplication.cpp",
        engine / "Code" / "Framework" / "AzGameFramework" / "AzGameFramework" / "Application" / "GameApplication.cpp",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Network" / "AssetProcessorConnection.cpp",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Asset" / "AssetSystemComponent.cpp",
        engine / "Code" / "LauncherUnified" / "Launcher.cpp",
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Serialization" / "ObjectStream.cpp",
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetManagerBus.h",
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetManager.h",
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Asset" / "AssetCommon.h",
        engine / "Gems" / "Atom" / "RHI" / "Null" / "Code" / "Source" / "RHI.Reflect" / "ReflectSystemComponent.cpp",
        engine / "Gems" / "Atom" / "RHI" / "DX12" / "Code" / "Include" / "Atom" / "RHI.Reflect" / "DX12" / "ShaderStageFunction.h",
        engine / "Gems" / "Atom" / "RHI" / "DX12" / "Code" / "Include" / "Atom" / "RHI.Reflect" / "DX12" / "PipelineLayoutDescriptor.h",
        engine / "Gems" / "Atom" / "RHI" / "Vulkan" / "Code" / "Include" / "Atom" / "RHI.Reflect" / "Vulkan" / "ShaderStageFunction.h",
        engine / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "ActorAsset.h",
        engine / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionAsset.h",
        engine / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "MotionSetAsset.h",
        engine / "Gems" / "EMotionFX" / "Code" / "Source" / "Integration" / "Assets" / "AnimGraphAsset.h",
        engine / "Gems" / "Atom" / "RPI" / "Code" / "Include" / "Atom" / "RPI.Reflect" / "Model" / "ModelAsset.h",
        engine / "Gems" / "Atom" / "RPI" / "Code" / "Include" / "Atom" / "RPI.Reflect" / "Material" / "MaterialAsset.h",
        engine / "Gems" / "PhysX" / "Core" / "Code" / "Include" / "PhysX" / "MeshAsset.h",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableAssetHandler.h",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableAssetHandler.cpp",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableEntitiesInterface.h",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableEntitiesInterface.cpp",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableEntitiesManager.cpp",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableSystemComponent.cpp",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "SpawnableSystemComponent.h",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "Spawnable.h",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Entity" / "GameEntityContextBus.h",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Entity" / "GameEntityContextComponent.cpp",
        engine / "Code" / "Framework" / "AzFramework" / "AzFramework" / "Spawnable" / "Script" / "SpawnableScriptMediator.cpp",
        engine / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Spawnable" / "PrefabInMemorySpawnableConverter.cpp",
        engine / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Spawnable" / "PrefabProcessor.h",
        engine / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Spawnable" / "PrefabProcessorContext.cpp",
        engine / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Spawnable" / "SpawnableUtils.cpp",
        engine / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Procedural" / "ProceduralPrefabAsset.h",
        engine / "Code" / "Framework" / "AzToolsFramework" / "AzToolsFramework" / "Prefab" / "Procedural" / "ProceduralPrefabAsset.cpp",
        engine / "Gems" / "Prefab" / "PrefabBuilder" / "CMakeLists.txt",
        engine / "Gems" / "Prefab" / "PrefabBuilder" / "PrefabBuilderComponent.cpp",
        engine / "Gems" / "Prefab" / "PrefabBuilder" / "PrefabBuilderModule.cpp",
        engine / "Gems" / "Prefab" / "PrefabBuilder" / "PrefabGroup" / "ProceduralAssetHandler.cpp",
        engine / "Gems" / "Prefab" / "PrefabBuilder" / "PrefabGroup" / "ProceduralAssetHandler.h",
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "IConsole.h",
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "Console.cpp",
        engine / "Code" / "Tools" / "AssetProcessor" / "native" / "InternalBuilders" / "SettingsRegistryBuilder.cpp",
        engine / "Code" / "Legacy" / "CrySystem" / "LevelSystem" / "SpawnableLevelSystem.cpp",
        engine / "Assets" / "Engine" / "SeedAssetList.seed",
    ):
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("source validation fixture\n", encoding="utf-8")
    if launcher:
        (bin_dir / "MAXINE_GoldenCorpus.HeadlessServerLauncher.exe").write_text("runtime placeholder", encoding="utf-8")
    return engine


def _apb_report(root: Path) -> Path:
    report = root / "apb-live" / "asset_processor_batch_live_report.json"
    report.parent.mkdir(parents=True)
    products = []
    for index, product_type in enumerate(
        ["azmodel", "actor", "procprefab", "motion", "motionset", "animgraph", "pxmesh", "azmaterial"],
        start=1,
    ):
        product = {
            "product_type": product_type,
            "product_path": f"pc/assets/characters/maxine/release/maxine.{product_type}",
            "platform": "pc",
            "status": "ready",
            "source_uuid": "11111111111141118111111111111111",
            "source_sub_id": str(index),
            "produced_by_source_uuid": True,
            "evidence_source": "asset_processor_database",
        }
        if product_type == "procprefab":
            product.update(
                {
                    "product_path": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
                    "asset_id": "{794D1588-3C41-5795-8A9A-EEBD6A663A60}:11695305",
                    "asset_type_id": "{9B7C8459-471E-4EAD-A363-7990CC4065A9}",
                    "asset_type_name": "AZ::Prefab::ProceduralPrefabAsset",
                }
            )
        products.append(product)
    report.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "report_type": "asset_processor_batch_golden_corpus_summary_v1",
                "status": "pass",
                "produced_products": products,
                "missing_products": [],
                "pending_products": [],
                "cache_heuristic_used": False,
            }
        ),
        encoding="utf-8",
    )
    return report


def _append_apb_products(apb_report: Path, products: list[dict]) -> None:
    report = json.loads(apb_report.read_text(encoding="utf-8"))
    report.setdefault("produced_products", []).extend(products)
    apb_report.write_text(json.dumps(report), encoding="utf-8")


def _runtime_env(tmp_path: Path, *, launcher: bool = True, gates: bool = False) -> tuple[dict, Path, Path, Path]:
    engine = _engine(tmp_path, launcher=launcher)
    project = _project(tmp_path)
    apb = _apb_report(tmp_path)
    env = os.environ.copy()
    env["O3DE_ENGINE_ROOT"] = str(engine)
    env["O3DE_PROJECT_PATH"] = str(project)
    env["MAXINE_ALLOW_LIVE_PUBLICATION"] = "0"
    env["MAXINE_ENABLE_RELEASE_PACKAGING"] = "0"
    if gates:
        env["MAXINE_ENABLE_O3DE_RUNTIME_HARNESS"] = "1"
        env["MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS"] = "1"
    return env, engine, project, apb


def _write_animation_source_validation_files(engine: Path) -> None:
    source_files = {
        "Gems/EMotionFX/Code/Source/Integration/Components/ActorComponent.h": (
            'AZ_COMPONENT(ActorComponent, "{BDC97E7F-A054-448B-A26F-EA2B5D78E377}")\n'
            "EMotionFX::ActorInstance* GetActorInstance();\n"
        ),
        "Gems/EMotionFX/Code/Source/Integration/Components/ActorComponent.cpp": (
            "ActorComponentRequestBus::Handler::BusConnect(entityId);\n"
            "m_actorInstance = AZStd::unique_ptr<EMotionFX::ActorInstance>();\n"
        ),
        "Gems/EMotionFX/Code/Include/Integration/ActorComponentBus.h": (
            "class ActorComponentRequests : public AZ::ComponentBus\n"
            "virtual EMotionFX::ActorInstance* GetActorInstance() = 0;\n"
            "using ActorComponentRequestBus = AZ::EBus<ActorComponentRequests>;\n"
        ),
        "Gems/EMotionFX/Code/Source/Integration/Components/AnimGraphComponent.h": (
            'AZ_COMPONENT(AnimGraphComponent, "{77624349-D5C4-4902-9F08-665814520999}")\n'
            "EMotionFX::AnimGraphInstance* GetAnimGraphInstance();\n"
            "void SetActiveMotionSet(AZ::Data::AssetId motionSetAssetId);\n"
            "void StartAnimGraph();\n"
            "void StopAnimGraph();\n"
        ),
        "Gems/EMotionFX/Code/Source/Integration/Components/AnimGraphComponent.cpp": (
            "AnimGraphComponentRequestBus::Handler::BusConnect(entityId);\n"
            "SetAnimGraphAssetId(animGraphAssetId);\n"
            "SetMotionSetAssetId(motionSetAssetId);\n"
            "StartAnimGraph();\n"
        ),
        "Gems/EMotionFX/Code/Include/Integration/AnimGraphComponentBus.h": (
            "class AnimGraphComponentRequests : public AZ::ComponentBus\n"
            "virtual EMotionFX::AnimGraphInstance* GetAnimGraphInstance() = 0;\n"
            "virtual void SetActiveMotionSet(AZ::Data::AssetId motionSetAssetId) = 0;\n"
            "virtual void StartAnimGraph() = 0;\n"
            "using AnimGraphComponentRequestBus = AZ::EBus<AnimGraphComponentRequests>;\n"
        ),
        "Gems/EMotionFX/Code/Source/Integration/Components/SimpleMotionComponent.h": (
            'AZ_COMPONENT(SimpleMotionComponent, "{DBE3C105-6FC1-418F-A8B1-D0F29FE8D5BD}")\n'
            "float GetPlayTime() const;\n"
            "float GetDuration() const;\n"
            "void PlayMotion();\n"
        ),
        "Gems/EMotionFX/Code/Source/Integration/Components/SimpleMotionComponent.cpp": (
            "SimpleMotionComponentRequestBus::Handler::BusConnect(entityId);\n"
            "SetMotionAssetId(motionAssetId);\n"
            "PlayMotionInternal();\n"
            "actorInstance->GetMotionSystem()->PlayMotion(m_motionAsset.Get()->GetMotion(), &playInfo);\n"
        ),
        "Gems/EMotionFX/Code/Include/Integration/SimpleMotionComponentBus.h": (
            "class SimpleMotionComponentRequests : public AZ::ComponentBus\n"
            "virtual float GetPlayTime() const = 0;\n"
            "virtual float GetDuration() const = 0;\n"
            "virtual void Motion(AZ::Data::AssetId motionAssetId) = 0;\n"
            "virtual void PlayMotion() = 0;\n"
            "using SimpleMotionComponentRequestBus = AZ::EBus<SimpleMotionComponentRequests>;\n"
        ),
        "Gems/EMotionFX/Code/Source/Integration/Assets/ActorAsset.h": (
            'AZ_RTTI(ActorAsset, "{F67CC648-EA51-464C-9F5D-4A9CE41A7F86}", EMotionFXAsset)\n'
        ),
        "Gems/EMotionFX/Code/Source/Integration/Assets/MotionAsset.h": (
            'AZ_RTTI(MotionAsset, "{00494B8E-7578-4BA2-8B28-272E90680787}", EMotionFXAsset)\n'
        ),
        "Gems/EMotionFX/Code/Source/Integration/Assets/MotionSetAsset.h": (
            'AZ_RTTI(MotionSetAsset, "{1DA936A0-F766-4B2F-B89C-9F4C8E1310F9}", EMotionFXAsset)\n'
        ),
        "Gems/EMotionFX/Code/Source/Integration/Assets/AnimGraphAsset.h": (
            'AZ_RTTI(AnimGraphAsset, "{28003359-4A29-41AE-8198-0AEFE9FF5263}", EMotionFXAsset)\n'
        ),
        "Gems/EMotionFX/Code/Source/Integration/Assets/ActorAsset.cpp": (
            'GetAssetType() const\nreturn azrtti_typeid<ActorAsset>();\nreturn "actor";\n'
        ),
        "Gems/EMotionFX/Code/Source/Integration/Assets/MotionAsset.cpp": (
            'GetAssetType() const\nreturn azrtti_typeid<MotionAsset>();\nreturn "motion";\n'
        ),
        "Gems/EMotionFX/Code/Source/Integration/Assets/MotionSetAsset.cpp": (
            'GetAssetType() const\nreturn azrtti_typeid<MotionSetAsset>();\nreturn "motionset";\n'
        ),
        "Gems/EMotionFX/Code/Source/Integration/Assets/AnimGraphAsset.cpp": (
            'GetAssetType() const\nreturn azrtti_typeid<AnimGraphAsset>();\nreturn "animgraph";\n'
        ),
        "Gems/EMotionFX/Code/Source/Integration/System/SystemComponent.cpp": (
            "ActorAssetHandler\nMotionAssetHandler\nMotionSetAssetHandler\nAnimGraphAssetHandler\n"
        ),
    }
    for relative, content in source_files.items():
        path = engine / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _enable_fixture_gem(project: Path) -> None:
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload.setdefault("gem_names", []).append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_defaultlevel_bootstrap(project: Path) -> tuple[Path, Path, str, str]:
    registry = project / "Registry"
    registry.mkdir()
    source = registry / "load_level.setreg"
    source.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    cache = project / "Cache" / "pc"
    cache.mkdir(parents=True)
    bootstrap = cache / "bootstrap.server.profile.setreg"
    original_bootstrap = json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}})
    bootstrap.write_text(original_bootstrap, encoding="utf-8")
    return source, bootstrap, source.read_text(encoding="utf-8"), original_bootstrap


def test_runtime_harness_fixture_mode_reports_pass() -> None:
    report = runtime_harness.run_runtime_harness(mode="fixture")

    assert report["status"] == "pass"
    assert report["runtime_harness_status"] == "runtime_harness_ready_but_execution_not_requested"
    assert report["live_runtime_execution"] is False
    assert report["runtime_execution_attempted"] is False


def test_runtime_harness_readiness_selects_project_paired_launcher(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        check_local_readiness=True,
        strict=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_readiness_status"] == "runtime_harness_readiness_pass"
    assert report["runtime_executable_selected"] == "MAXINE_GoldenCorpus.HeadlessServerLauncher.exe"
    assert report["runtime_executable_provenance"] == "engine_profile_bin"
    assert report["runtime_executable_project_pairing"]["status"] == "pass"
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_harness_proof_is_character_proof"] is False


def test_runtime_harness_live_mode_requires_runtime_gates(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=False)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_harness=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_missing_runtime_gate"
    assert report["runtime_execution_attempted"] is False
    assert "MAXINE_ENABLE_O3DE_RUNTIME_HARNESS" in report["runtime_command_gate_env"]["missing"]
    assert "MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS" in report["runtime_command_gate_env"]["missing"]


def test_runtime_harness_command_pinning_reports_missing_executable_blocker(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, launcher=False)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        pin_runtime_command=True,
        strict=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_missing_runtime_executable"
    assert report["runtime_command_pinned"] is False
    assert report["runtime_execution_attempted"] is False


def test_runtime_harness_live_mode_pins_command_before_launch(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)

    def _runner(**kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = list(kwargs["argv"])  # type: ignore[index]
        assert any(str(arg).startswith("--console-command-file=") for arg in argv)
        return subprocess.CompletedProcess(argv, 0, stdout="runtime startup\n", stderr="")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_harness=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_status"] == "runtime_execution_pass"
    assert report["runtime_command_pinning_status"] == "runtime_command_pinning_pass"
    assert report["runtime_command_pinned"] is True
    assert report["runtime_execution_attempted"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_harness_proof_is_character_proof"] is False


def test_runtime_harness_command_pinning_mode_pins_console_quit_envelope_without_launch(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=False)

    def _runner(**_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("command-pinning mode must not launch the runtime process")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        pin_runtime_command=True,
        strict=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_status"] == "runtime_command_pinning_pass"
    assert report["runtime_command_pinning_status"] == "runtime_command_pinning_pass"
    assert report["runtime_command_pinned"] is True
    assert report["runtime_command_pin_verified"] is True
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_command_kind"] == "headless_console_quit_envelope"
    assert report["runtime_command_selected"].endswith("MAXINE_GoldenCorpus.HeadlessServerLauncher.exe")
    assert f"--project-path={project}" in report["runtime_command_arguments"]
    assert "-NullRenderer" in report["runtime_command_arguments"]
    assert "-rhi=null" in report["runtime_command_arguments"]
    assert "--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0" in report["runtime_command_arguments"]
    assert any(arg.startswith("--console-command-file=") for arg in report["runtime_command_arguments"])
    assert report["runtime_command_safety_profile"]["uses_production_level"] is False
    assert report["runtime_command_safety_profile"]["uses_temp_level"] is False
    assert report["runtime_command_safety_profile"]["uses_no_level"] is True


def test_runtime_harness_live_mode_executes_pinned_command_with_gates(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    log_dir = project / "user" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "Server.log").write_text("runtime command envelope log\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def _runner(**kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        argv = list(kwargs["argv"])  # type: ignore[index]
        command_file_arg = next(arg for arg in argv if str(arg).startswith("--console-command-file="))
        command_file = Path(str(command_file_arg).split("=", 1)[1])
        assert command_file.exists()
        assert command_file.read_text(encoding="utf-8").strip() == "quit"
        return subprocess.CompletedProcess(argv, 0, stdout="runtime startup\nquit requested\n", stderr="")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_harness=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_status"] == "runtime_execution_pass"
    assert report["runtime_command_pinning_status"] == "runtime_command_pinning_pass"
    assert report["runtime_command_pinned"] is True
    assert report["runtime_command_pin_verified"] is True
    assert report["runtime_execution_attempted"] is True
    assert report["runtime_execution_completed"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_character_proof_verified"] is False
    assert report["runtime_stdout_ref"].endswith("runtime_stdout.txt")
    assert report["runtime_stderr_ref"].endswith("runtime_stderr.txt")
    assert any(str(ref).endswith("Server.log") for ref in report["runtime_log_refs"])
    assert report["runtime_command_log_refs"] == report["runtime_log_refs"]
    assert report["runtime_log_scan"]["status"] == "pass"
    assert "runtime_bounded_command_executed" in report["required_runtime_harness_assertions_passed"]
    assert captured["timeout_seconds"] == 120


def test_runtime_harness_live_mode_records_timeout_and_kill_semantics(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)

    def _runner(**kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=kwargs["argv"], timeout=kwargs["timeout_seconds"], output="partial startup")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_harness=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["status"] == "fail"
    assert report["runtime_command_pin_verified"] is True
    assert report["runtime_execution_attempted"] is True
    assert report["runtime_execution_completed"] is True
    assert report["runtime_execution_verified"] is False
    assert report["runtime_execution_status"] == "runtime_execution_timed_out"
    assert report["runtime_timed_out"] is True
    assert report["runtime_timeout_stall"] is True
    assert report["runtime_kill_attempted"] is True
    assert report["runtime_kill_result"]["status"] == "runtime_execution_killed_after_timeout"
    assert "runtime_bounded_command" in report["required_runtime_harness_assertions_failed"]


def test_runtime_harness_live_mode_classifies_nonzero_crash_like_exit(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    log_dir = project / "user" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "Server.log").write_text(
        "\n".join(
            [
                "O3DE could not initialize correctly for the following reason(s):",
                "Element 'NULL' found in AZStd::intrusive_ptr<PipelineLayoutDescriptor> is not registered with the serializer!",
                "File materials/types/standardpbr_mainpipeline_forwardpass_standardlighting.azshader",
            ]
        ),
        encoding="utf-8",
    )

    def _runner(**kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = list(kwargs["argv"])  # type: ignore[index]
        return subprocess.CompletedProcess(
            argv,
            3221225477,
            stdout=(
                "AssetProcessorConnection::ConnectThread: Network connection attempt failure\n"
                "GAME: Negotiation with asset processor failed\n"
                "[Error] (Serialize) - Element 'NULL' found in PipelineLayoutDescriptor\n"
            ),
            stderr=(
                "Assert: C:/src/o3de/Code/Framework/AzCore/AzCore/Asset/AssetCommon.cpp:244 "
                "(void AZ::Data::AssetData::Release(void)): Attempting to release asset after AssetManager has been destroyed!\n"
                "Assert: C:/src/o3de/Code/Framework/AzCore/AzCore/Asset/AssetCommon.cpp:276 "
                "(void AZ::Data::AssetData::ReleaseWeak(void)): Attempting to release asset after AssetManager has been destroyed!\n"
            ),
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_harness=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["status"] == "fail"
    assert report["runtime_execution_attempted"] is True
    assert report["runtime_execution_completed"] is True
    assert report["runtime_execution_verified"] is False
    assert report["runtime_exit_code"] == 3221225477
    assert report["runtime_exit_code_decimal"] == 3221225477
    assert report["runtime_exit_code_hex"] == "0xC0000005"
    assert report["runtime_exit_code_signed"] == -1073741819
    assert report["runtime_exit_code_name"] == "STATUS_ACCESS_VIOLATION"
    assert report["runtime_exit_is_windows_ntstatus_like"] is True
    assert report["runtime_exit_is_crash_like"] is True
    assert report["runtime_exit_classification"] == "runtime_execution_failed_access_violation_like_exit"
    assert report["runtime_crash_classification"] == "runtime_execution_failed_access_violation_like_exit"
    assert report["runtime_exit_diagnostic_status"] == "runtime_exit_code_classified"
    assert report["runtime_asset_manager_asserts"]["status"] == "runtime_execution_failed_asset_manager_shutdown_assert"
    assert report["runtime_asset_manager_asserts"]["count"] == 2
    assert report["runtime_assertion_summary"]["assert_count"] == 2
    assert report["runtime_stdout_error_summary"]["asset_processor_negotiation_failure_count"] == 2
    assert report["runtime_log_error_summary"]["shader_serializer_error_count"] == 1
    assert report["runtime_command_variant_result"]["status"] == "runtime_command_variant_not_attempted"
    assert report["runtime_root_cause_confidence"] == "low"
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_character_proof_verified"] is False


def test_runtime_harness_live_mode_records_missing_runtime_log_diagnostic(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)

    def _runner(**kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = list(kwargs["argv"])  # type: ignore[index]
        return subprocess.CompletedProcess(argv, 3221225477, stdout="", stderr="")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_harness=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["runtime_log_refs"] == []
    assert report["runtime_log_error_summary"]["status"] == "blocked_by_missing_runtime_log"
    assert report["runtime_exit_diagnostic_status"] == "runtime_exit_code_classified"
    assert report["runtime_execution_verified"] is False


def test_runtime_harness_quit_variant_diagnostic_records_matrix_and_stops_after_clean_variant(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    log_dir = project / "user" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "Server.log").write_text("variant clean exit log\n", encoding="utf-8")
    launched: list[list[str]] = []

    def _runner(**kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = list(kwargs["argv"])  # type: ignore[index]
        launched.append([str(arg) for arg in argv])
        assert "-NullRenderer" in argv
        assert "-rhi=null" not in argv
        command_file_arg = next(arg for arg in argv if str(arg).startswith("--console-command-file="))
        command_file = Path(str(command_file_arg).split("=", 1)[1])
        assert command_file.read_text(encoding="utf-8").strip() == "quit"
        return subprocess.CompletedProcess(argv, 0, stdout="Console only mode enabled.\nquit requested\n", stderr="")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_quit_variants=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["status"] == "pass"
    assert len(launched) == 1
    assert report["runtime_command_pinning_status"] == "runtime_command_pinning_pass"
    assert report["runtime_command_pinned"] is True
    assert report["runtime_command_pin_verified"] is True
    assert report["runtime_quit_variant_diagnostic_status"] == "runtime_command_variant_selected_clean_exit"
    assert report["runtime_safer_variant_selected"] == "nullrenderer_only_console_quit"
    assert report["runtime_safer_variant_verified"] is True
    assert report["runtime_execution_attempted"] is True
    assert report["runtime_execution_completed"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_character_proof_verified"] is False
    matrix = report["runtime_command_variant_matrix"]
    assert matrix == report["runtime_command_variants"]
    null_variant = next(item for item in matrix if item["runtime_command_variant_id"] == "nullrenderer_only_console_quit")
    rhi_variant = next(item for item in matrix if item["runtime_command_variant_id"] == "rhi_null_only_console_quit")
    help_variant = next(item for item in matrix if item["runtime_command_variant_id"] == "help_or_version_surface")
    assert null_variant["runtime_command_variant_status"] == "runtime_command_variant_pass"
    assert null_variant["runtime_command_variant_runtime_execution_verified"] is True
    assert null_variant["runtime_command_variant_runtime_character_proof_claimed"] is False
    assert null_variant["runtime_command_variant_exit_code_decimal"] == 0
    assert null_variant["runtime_command_variant_exit_code_hex"] == "0x00000000"
    assert null_variant["runtime_command_variant_expected_exit_codes"] == [0]
    assert null_variant["runtime_command_variant_stdout_ref"].endswith("runtime_variant_nullrenderer_only_console_quit_stdout.txt")
    assert rhi_variant["runtime_command_variant_status"] == "runtime_command_variant_not_attempted"
    assert rhi_variant["runtime_command_variant_reason"] == "stopped_after_clean_variant"
    assert help_variant["runtime_command_variant_status"] == "runtime_command_variant_rejected_missing_source_validation"
    assert "runtime_quit_variant_clean_exit" in report["required_runtime_harness_assertions_passed"]


def test_runtime_harness_quit_variant_diagnostic_classifies_failed_variants(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    log_dir = project / "user" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "Server.log").write_text(
        "Element 'NULL' found in PipelineLayoutDescriptor is not registered with the serializer!\n",
        encoding="utf-8",
    )
    launched: list[list[str]] = []

    def _runner(**kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = list(kwargs["argv"])  # type: ignore[index]
        launched.append([str(arg) for arg in argv])
        return subprocess.CompletedProcess(
            argv,
            3221225477,
            stdout="GAME: Negotiation with asset processor failed\n[Error] (Serialize) - Element 'NULL' found\n",
            stderr="Assert: AssetManager has been destroyed\n",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_quit_variants=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["status"] == "fail"
    assert len(launched) == 2
    assert report["runtime_execution_attempted"] is True
    assert report["runtime_execution_completed"] is True
    assert report["runtime_execution_verified"] is False
    assert report["runtime_exit_code_decimal"] == 3221225477
    assert report["runtime_exit_code_hex"] == "0xC0000005"
    assert report["runtime_exit_classification"] == "runtime_execution_failed_access_violation_like_exit"
    assert report["runtime_quit_variant_diagnostic_status"] == "runtime_command_variant_failed_access_violation_like_exit"
    assert report["runtime_safer_variant_verified"] is False
    assert report["runtime_safer_variant_selected"] == ""
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_character_proof_verified"] is False
    attempted = [
        item for item in report["runtime_command_variant_matrix"] if item["runtime_command_variant_attempted"] is True
    ]
    assert [item["runtime_command_variant_id"] for item in attempted] == [
        "nullrenderer_only_console_quit",
        "rhi_null_only_console_quit",
    ]
    for variant in attempted:
        assert variant["runtime_command_variant_status"] == "runtime_command_variant_failed_access_violation_like_exit"
        assert variant["runtime_command_variant_exit_code_decimal"] == 3221225477
        assert variant["runtime_command_variant_exit_code_hex"] == "0xC0000005"
        assert variant["runtime_command_variant_runtime_execution_verified"] is False
        assert variant["runtime_command_variant_expected_exit_codes"] == [0]
        assert variant["runtime_command_variant_asset_manager_asserts"]["count"] == 1
        assert variant["runtime_command_variant_shader_serializer_errors"]["count"] >= 1
        assert variant["runtime_command_variant_asset_processor_negotiation_errors"]["count"] >= 1
    assert "runtime_quit_variant_clean_exit" in report["required_runtime_harness_assertions_failed"]


def test_runtime_harness_exit_strategy_diagnostic_records_source_matrix_without_unsafe_launch(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)

    def _runner(**_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("no exit strategy candidate should launch when every candidate is rejected")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_exit_strategies=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_exit_strategy_status"] == "blocked_by_missing_source_validated_runtime_exit_strategy"
    assert report["runtime_exit_strategy_verified"] is False
    assert report["runtime_exit_strategy_selected"] == ""
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_quit_variant_matrix_result"]["status"] == "preserved_from_pr127"
    candidates = report["runtime_exit_strategy_candidates"]
    assert candidates == report["runtime_exit_strategy_candidate_matrix"]
    candidate_by_id = {item["runtime_exit_strategy_candidate_id"]: item for item in candidates}
    assert candidate_by_id["console_command_file_immediate_quit"][
        "runtime_exit_strategy_candidate_status"
    ] == "runtime_exit_strategy_candidate_rejected_unsafe"
    assert candidate_by_id["settings_registry_runtime_console_quit_setregpatch"][
        "runtime_exit_strategy_candidate_status"
    ] == "runtime_exit_strategy_candidate_rejected_unsafe"
    assert candidate_by_id["post_app_start_callback_exit"][
        "runtime_exit_strategy_candidate_status"
    ] == "runtime_exit_strategy_candidate_rejected_no_exit_strategy"
    assert candidate_by_id["tick_queued_delayed_quit"][
        "runtime_exit_strategy_candidate_status"
    ] == "runtime_exit_strategy_candidate_rejected_missing_source_validation"
    assert report["runtime_exit_strategy_blocked_reason"] == "headless_launcher_no_level_exit_strategy_unavailable"


def test_runtime_harness_exit_strategy_diagnostic_can_verify_clean_source_validated_candidate(
    tmp_path: Path, monkeypatch
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    log_dir = project / "user" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "Server.log").write_text("clean exit strategy log\n", encoding="utf-8")

    def _fake_candidates(command: dict, *, artifact_dir: Path, timeout_seconds: int) -> list[dict]:
        command_file = artifact_dir / "maxine_runtime_exit_strategy_clean.cfg"
        command_file.write_text("quit\n", encoding="utf-8")
        return [
            {
                "runtime_exit_strategy_candidate_id": "test_after_init_quit",
                "runtime_exit_strategy_candidate_name": "Test after-init quit",
                "runtime_exit_strategy_candidate_status": "runtime_exit_strategy_candidate_source_validated",
                "runtime_exit_strategy_candidate_kind": "test_after_init_quit",
                "runtime_exit_strategy_candidate_command": command["argv"][0],
                "runtime_exit_strategy_candidate_arguments": [
                    *command["argv"][1:-1],
                    f"--console-command-file={command_file}",
                ],
                "runtime_exit_strategy_candidate_argument_shape": {
                    "exit_strategy": "test source-validated after-init quit"
                },
                "runtime_exit_strategy_candidate_safety_profile": {
                    "local": True,
                    "bounded_by_timeout": True,
                    "non_publishing": True,
                    "non_packaging": True,
                    "mutates_production": False,
                    "uses_production_level": False,
                    "uses_no_level": True,
                },
                "runtime_exit_strategy_candidate_source_validation": {
                    "status": "runtime_exit_strategy_candidate_source_validated"
                },
                "runtime_exit_strategy_candidate_source_refs": ["test_source:1"],
                "runtime_exit_strategy_candidate_selected": False,
                "runtime_exit_strategy_candidate_attempted": False,
                "runtime_exit_strategy_candidate_rejected_reason": "",
                "runtime_exit_strategy_candidate_exit_code_decimal": None,
                "runtime_exit_strategy_candidate_exit_code_hex": "",
                "runtime_exit_strategy_candidate_exit_classification": "runtime_execution_not_attempted",
                "runtime_exit_strategy_candidate_expected_exit_codes": [0],
                "runtime_exit_strategy_candidate_expected_exit_matched": False,
                "runtime_exit_strategy_candidate_timeout_seconds": timeout_seconds,
                "runtime_exit_strategy_candidate_timed_out": False,
                "runtime_exit_strategy_candidate_kill_attempted": False,
                "runtime_exit_strategy_candidate_kill_result": {"status": "not_run"},
                "runtime_exit_strategy_candidate_stdout_ref": "",
                "runtime_exit_strategy_candidate_stderr_ref": "",
                "runtime_exit_strategy_candidate_log_refs": [],
                "runtime_exit_strategy_candidate_log_scan": {"status": "runtime_execution_not_attempted", "matches": []},
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
        ]

    monkeypatch.setattr(runtime_harness, "_runtime_exit_strategy_candidate_matrix", _fake_candidates)

    def _runner(**kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = list(kwargs["argv"])  # type: ignore[index]
        return subprocess.CompletedProcess(argv, 0, stdout="clean after-init quit\n", stderr="")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_exit_strategies=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_exit_strategy_status"] == "runtime_exit_strategy_verified_clean_exit"
    assert report["runtime_exit_strategy_selected"] == "test_after_init_quit"
    assert report["runtime_exit_strategy_verified"] is True
    assert report["runtime_execution_attempted"] is True
    assert report["runtime_execution_completed"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_character_proof_claimed"] is False
    candidate = report["runtime_exit_strategy_candidate_matrix"][0]
    assert candidate["runtime_exit_strategy_candidate_status"] == "runtime_exit_strategy_candidate_attempted_pass"
    assert candidate["runtime_exit_strategy_candidate_runtime_execution_verified"] is True
    assert candidate["runtime_exit_strategy_candidate_runtime_character_proof_claimed"] is False
    assert candidate["runtime_exit_strategy_candidate_exit_code_decimal"] == 0
    assert candidate["runtime_exit_strategy_candidate_exit_code_hex"] == "0x00000000"
    assert "runtime_exit_strategy_clean_exit" in report["required_runtime_harness_assertions_passed"]


def test_runtime_harness_exit_strategy_diagnostic_classifies_nonzero_candidate(tmp_path: Path, monkeypatch) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    log_dir = project / "user" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "Server.log").write_text(
        "Element 'NULL' found in PipelineLayoutDescriptor is not registered with the serializer!\n",
        encoding="utf-8",
    )

    def _fake_candidates(command: dict, *, artifact_dir: Path, timeout_seconds: int) -> list[dict]:
        command_file = artifact_dir / "maxine_runtime_exit_strategy_fail.cfg"
        command_file.write_text("quit\n", encoding="utf-8")
        candidate = runtime_harness._runtime_exit_strategy_candidate_payload(
            candidate_id="test_failing_exit",
            name="Test failing exit",
            status="runtime_exit_strategy_candidate_source_validated",
            kind="test_exit",
            argv=[command["argv"][0], *command["argv"][1:-1], f"--console-command-file={command_file}"],
            source_validation={"status": "runtime_exit_strategy_candidate_source_validated"},
            source_refs=["test_source:2"],
            safety_profile={"local": True, "bounded_by_timeout": True, "non_publishing": True},
            reason="test candidate",
            rejected_reason="",
            timeout_seconds=timeout_seconds,
        )
        return [candidate]

    monkeypatch.setattr(runtime_harness, "_runtime_exit_strategy_candidate_matrix", _fake_candidates)

    def _runner(**kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = list(kwargs["argv"])  # type: ignore[index]
        return subprocess.CompletedProcess(
            argv,
            3221225477,
            stdout="GAME: Negotiation with asset processor failed\n[Error] (Serialize) - Element 'NULL' found\n",
            stderr="Assert: AssetManager has been destroyed\n",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_exit_strategies=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=_runner,
        artifact_root=tmp_path / "runtime-artifacts",
    )

    assert report["status"] == "fail"
    assert report["runtime_exit_strategy_status"] == "runtime_exit_strategy_candidate_attempted_failed_access_violation_like_exit"
    assert report["runtime_exit_strategy_verified"] is False
    assert report["runtime_execution_attempted"] is True
    assert report["runtime_execution_verified"] is False
    assert report["runtime_exit_code_decimal"] == 3221225477
    assert report["runtime_exit_code_hex"] == "0xC0000005"
    candidate = report["runtime_exit_strategy_candidate_matrix"][0]
    assert candidate["runtime_exit_strategy_candidate_status"] == (
        "runtime_exit_strategy_candidate_attempted_failed_access_violation_like_exit"
    )
    assert candidate["runtime_exit_strategy_candidate_runtime_execution_verified"] is False
    assert candidate["runtime_exit_strategy_candidate_expected_exit_codes"] == [0]
    assert candidate["runtime_exit_strategy_candidate_asset_manager_asserts"]["count"] == 1
    assert candidate["runtime_exit_strategy_candidate_shader_serializer_errors"]["count"] >= 1
    assert candidate["runtime_exit_strategy_candidate_asset_processor_negotiation_errors"]["count"] >= 1
    assert "runtime_exit_strategy_clean_exit" in report["required_runtime_harness_assertions_failed"]


def test_runtime_harness_validation_rejects_exit_strategy_verified_without_clean_candidate() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_exit_strategy_selected": "test_failing_exit",
            "runtime_exit_strategy_verified": True,
            "runtime_execution_attempted": True,
            "runtime_execution_completed": True,
            "runtime_execution_verified": False,
            "runtime_exit_strategy_candidate_matrix": [
                {
                    "runtime_exit_strategy_candidate_id": "test_failing_exit",
                    "runtime_exit_strategy_candidate_status": (
                        "runtime_exit_strategy_candidate_attempted_failed_access_violation_like_exit"
                    ),
                    "runtime_exit_strategy_candidate_attempted": True,
                    "runtime_exit_strategy_candidate_expected_exit_codes": [0],
                    "runtime_exit_strategy_candidate_exit_code_decimal": 3221225477,
                    "runtime_exit_strategy_candidate_exit_code_hex": "0xC0000005",
                    "runtime_exit_strategy_candidate_runtime_execution_verified": False,
                }
            ],
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in validation.error_codes


def test_runtime_harness_exit_fixture_diagnostic_records_project_rebuild_blocker_without_launch(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)

    def _runner(**_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("blocked runtime exit fixture diagnostic must not launch a process")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_exit_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
        command_runner=_runner,
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_exit_fixture_status"] == "blocked_by_fixture_requires_project_code_rebuild"
    assert report["runtime_exit_fixture_available"] is False
    assert report["runtime_exit_fixture_requires_rebuild"] is True
    assert report["runtime_exit_fixture_rebuild_status"] == "not_attempted"
    assert report["runtime_exit_fixture_enabled_for_project"] is False
    assert report["runtime_exit_fixture_execution_attempted"] is False
    assert report["runtime_exit_fixture_execution_completed"] is False
    assert report["runtime_exit_fixture_execution_verified"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_exit_fixture_gate_env"] == [
        "MAXINE_ENABLE_O3DE_RUNTIME_HARNESS=1",
        "MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS=1",
        "MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE=1",
    ]
    assert report["runtime_exit_fixture_is_runtime_character_proof"] is False
    assert report["runtime_exit_fixture_character_proof_claimed"] is False
    assert report["runtime_exit_fixture_character_proof_verified"] is False
    assert report["runtime_exit_strategy_result"]["status"] == "preserved_from_pr128"
    assert report["runtime_quit_variant_matrix_result"]["status"] == "preserved_from_pr127"
    assert report["runtime_command_pinning_result"]["status"] == "preserved_from_pr125"


def test_runtime_harness_exit_fixture_source_check_records_repo_owned_gem_source_ready(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=False)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        check_runtime_exit_fixture_source=True,
        strict=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_exit_fixture_source_readiness"
    assert report["runtime_exit_fixture_source_status"] == "runtime_exit_fixture_source_ready"
    assert report["runtime_exit_fixture_source_owned_by_repo"] is True
    assert report["runtime_exit_fixture_source_path"] == "o3de/gems/MaxineRuntimeExitFixture"
    assert report["runtime_exit_fixture_gem_name"] == "MaxineRuntimeExitFixture"
    assert report["runtime_exit_fixture_gem_type"] == "Code"
    assert report["runtime_exit_fixture_gem_json_path"].endswith("gem.json")
    assert report["runtime_exit_fixture_cmake_path"].endswith("MaxineRuntimeExitFixture/CMakeLists.txt")
    assert report["runtime_exit_fixture_component_name"] == "MaxineRuntimeExitFixtureSystemComponent"
    assert report["runtime_exit_fixture_lifecycle_point"] == "AZ::Component::Activate plus AZ::TickBus::OnTick"
    assert report["runtime_exit_fixture_exit_api"] == "AzFramework::ApplicationRequests::ExitMainLoop"
    assert "/Amazon/MAXINE/RuntimeHarness/EnableExitFixture" in report["runtime_exit_fixture_settings_registry_keys"]
    assert "/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks" in report["runtime_exit_fixture_settings_registry_keys"]
    assert "MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE=1" in report["runtime_exit_fixture_gate_env"]
    assert report["runtime_exit_fixture_enabled_by_default"] is False
    assert report["runtime_exit_fixture_is_shipping_behavior"] is False
    assert report["runtime_exit_fixture_execution_attempted"] is False
    assert report["runtime_exit_fixture_execution_verified"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_exit_fixture_character_proof_claimed"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_exit_fixture_rebuild_gate_records_mutation_and_rebuild_not_attempted(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=False)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        check_runtime_exit_fixture_rebuild_gate=True,
        strict=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_exit_fixture_rebuild_gate"
    assert report["runtime_exit_fixture_source_status"] == "runtime_exit_fixture_source_ready"
    assert report["runtime_exit_fixture_registration_status"] == "runtime_exit_fixture_registration_ready_not_attempted"
    assert report["runtime_exit_fixture_enablement_status"] == "blocked_by_fixture_not_enabled_for_project"
    assert report["runtime_exit_fixture_requires_project_mutation"] is True
    assert report["runtime_exit_fixture_project_mutation_attempted"] is False
    assert report["runtime_exit_fixture_project_mutation_reversible"] is True
    assert "MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION=1" in report["runtime_exit_fixture_project_mutation_gate_env"]
    assert report["runtime_exit_fixture_requires_rebuild"] is True
    assert report["runtime_exit_fixture_rebuild_gate_status"] == "runtime_exit_fixture_rebuild_gate_pass"
    assert report["runtime_exit_fixture_rebuild_attempted"] is False
    assert report["runtime_exit_fixture_rebuild_result"] == "runtime_exit_fixture_rebuild_not_attempted"
    assert report["runtime_exit_fixture_enabled_for_project"] is False
    assert report["runtime_exit_fixture_execution_attempted"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_exit_fixture_is_runtime_character_proof"] is False
    assert report["runtime_exit_fixture_character_proof_claimed"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_validation_rejects_fixture_source_ready_when_not_repo_owned() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_exit_fixture_source_status": "runtime_exit_fixture_source_ready",
            "runtime_exit_fixture_source_owned_by_repo": False,
            "runtime_exit_fixture_source_path": "C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus/Gem",
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_PATH_UNSAFE" in validation.error_codes


def test_runtime_harness_validation_rejects_fixture_enabled_by_default_or_shipping() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_exit_fixture_source_status": "runtime_exit_fixture_source_ready",
            "runtime_exit_fixture_source_owned_by_repo": True,
            "runtime_exit_fixture_enabled_by_default": True,
            "runtime_exit_fixture_is_shipping_behavior": True,
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_PATH_UNSAFE" in validation.error_codes


def test_runtime_harness_validation_rejects_fixture_project_mutation_without_gate() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_exit_fixture_source_status": "runtime_exit_fixture_source_ready",
            "runtime_exit_fixture_source_owned_by_repo": True,
            "runtime_exit_fixture_project_mutation_attempted": True,
            "runtime_exit_fixture_project_mutation_status": "blocked_by_fixture_missing_project_mutation_gate",
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_PATH_UNSAFE" in validation.error_codes


def test_runtime_harness_validation_rejects_fixture_rebuild_without_gate_or_as_execution_proof() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_exit_fixture_source_status": "runtime_exit_fixture_source_ready",
            "runtime_exit_fixture_source_owned_by_repo": True,
            "runtime_exit_fixture_rebuild_attempted": True,
            "runtime_exit_fixture_rebuild_gate_status": "blocked_by_fixture_missing_rebuild_gate",
            "runtime_execution_verified": True,
            "runtime_exit_fixture_execution_attempted": False,
            "runtime_exit_fixture_execution_verified": False,
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_PATH_UNSAFE" in validation.error_codes
    assert "MXN_RUNTIME_SMOKE_FAIL" in validation.error_codes


def test_runtime_harness_validation_rejects_exit_fixture_verified_without_clean_execution() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_exit_fixture_status": "runtime_exit_fixture_verified_clean_exit",
            "runtime_exit_fixture_available": True,
            "runtime_exit_fixture_execution_attempted": False,
            "runtime_exit_fixture_execution_completed": False,
            "runtime_exit_fixture_execution_verified": True,
            "runtime_exit_fixture_exit_code_decimal": 3221225477,
            "runtime_exit_fixture_exit_code_hex": "0xC0000005",
            "runtime_exit_fixture_exit_classification": "runtime_execution_failed_access_violation_like_exit",
            "runtime_execution_attempted": False,
            "runtime_execution_completed": False,
            "runtime_execution_verified": False,
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in validation.error_codes


def test_runtime_harness_validation_rejects_exit_fixture_character_proof_claim() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_exit_fixture_is_runtime_character_proof": False,
            "runtime_exit_fixture_character_proof_claimed": True,
            "runtime_exit_fixture_character_proof_verified": False,
            "runtime_character_proof_claimed": True,
            "runtime_character_proof_verified": False,
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in validation.error_codes


def test_runtime_harness_validation_rejects_exit_fixture_shipping_behavior() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_exit_fixture_status": "runtime_exit_fixture_available",
            "runtime_exit_fixture_available": True,
            "runtime_exit_fixture_shipping_status": "shipping_behavior",
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_PATH_UNSAFE" in validation.error_codes


def test_runtime_harness_validation_rejects_safer_variant_verified_without_clean_execution() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_safer_variant_selected": "nullrenderer_only_console_quit",
            "runtime_safer_variant_verified": True,
            "runtime_execution_attempted": True,
            "runtime_execution_completed": True,
            "runtime_execution_verified": False,
            "runtime_command_variant_matrix": [
                {
                    "runtime_command_variant_id": "nullrenderer_only_console_quit",
                    "runtime_command_variant_status": "runtime_command_variant_failed_access_violation_like_exit",
                    "runtime_command_variant_attempted": True,
                    "runtime_command_variant_expected_exit_codes": [0],
                    "runtime_command_variant_exit_code_decimal": 3221225477,
                    "runtime_command_variant_exit_code_hex": "0xC0000005",
                    "runtime_command_variant_runtime_execution_verified": False,
                }
            ],
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in validation.error_codes


def test_runtime_harness_validation_rejects_command_pin_verified_without_pinned() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report["runtime_command_pin_verified"] = True
    report["runtime_command_pinned"] = False

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in validation.error_codes


def test_runtime_harness_validation_rejects_crash_like_exit_as_verified_execution() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_execution_attempted": True,
            "runtime_execution_completed": True,
            "runtime_execution_verified": True,
            "runtime_execution_status": "runtime_execution_pass",
            "runtime_exit_code_decimal": 3221225477,
            "runtime_exit_code_hex": "0xC0000005",
            "runtime_exit_is_crash_like": True,
        }
    )

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in validation.error_codes


def test_runtime_harness_validation_rejects_execution_verified_without_attempt() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report["runtime_execution_verified"] = True
    report["runtime_execution_attempted"] = False

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in validation.error_codes


def test_runtime_harness_registration_missing_gate_blocks_project_mutation(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        register_runtime_exit_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
    )

    assert report["status"] == "fail"
    assert report["runtime_exit_fixture_registration_status"] == "blocked_by_fixture_registration_missing_gate"
    assert report["runtime_exit_fixture_registration_attempted"] is False
    assert report["runtime_exit_fixture_project_mutation_attempted"] is False
    assert report["runtime_execution_verified"] is False


def test_runtime_harness_register_and_enable_fixture_record_reversible_project_mutation(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path)
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"

    def runner(argv, **kwargs):
        if "register" in argv:
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            payload.setdefault("external_subdirectories", []).append(str(runtime_harness.RUNTIME_EXIT_FIXTURE_SOURCE_PATH))
            (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, stdout="registered fixture\n", stderr="")
        if "enable-gem" in argv:
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            payload.setdefault("gem_names", []).append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
            (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, stdout="enabled fixture\n", stderr="")
        raise AssertionError(argv)

    registration = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        register_runtime_exit_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
    )
    enablement = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
    )

    assert registration["status"] == "pass"
    assert registration["runtime_exit_fixture_registration_status"] == "runtime_exit_fixture_registration_pass"
    assert registration["runtime_exit_fixture_registration_attempted"] is True
    assert registration["runtime_exit_fixture_project_mutation_attempted"] is True
    assert registration["runtime_exit_fixture_project_mutation_reversible"] is True
    assert registration["runtime_exit_fixture_registration_stdout_ref"].endswith("runtime_exit_fixture_registration_stdout.txt")
    assert enablement["status"] == "pass"
    assert enablement["runtime_exit_fixture_enablement_status"] == "runtime_exit_fixture_enablement_pass"
    assert enablement["runtime_exit_fixture_enabled_for_project"] is True
    assert enablement["runtime_execution_verified"] is False


def test_runtime_harness_rebuild_gate_runs_scoped_target_only_with_gate(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path)
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
    launched = []

    def runner(argv, **kwargs):
        launched.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="built target\n", stderr="")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        rebuild_runtime_exit_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=1800,
    )

    assert report["status"] == "pass"
    assert report["runtime_exit_fixture_rebuild_status"] == "runtime_exit_fixture_rebuild_pass"
    assert report["runtime_exit_fixture_rebuild_attempted"] is True
    assert report["runtime_exit_fixture_rebuild_exit_code"] == 0
    assert "--target" in launched[0]
    assert "MAXINE_GoldenCorpus.HeadlessServerLauncher" in launched[0]
    assert report["runtime_execution_verified"] is False


def test_runtime_harness_fixture_command_uses_settings_registry_exit_not_console_quit(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
    launched = []

    def runner(argv, **kwargs):
        launched.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n",
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_command=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_exit_fixture_status"] == "runtime_exit_fixture_verified_clean_exit"
    assert report["runtime_exit_fixture_execution_attempted"] is True
    assert report["runtime_exit_fixture_execution_verified"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_exit_fixture_character_proof_claimed"] is False
    assert report["runtime_exit_fixture_runtime_command_uses_console_command_file_quit"] is False
    assert report["runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit"] is True
    assert any("/Amazon/MAXINE/RuntimeHarness/EnableExitFixture=true" in arg for arg in launched[0])
    assert not any(str(arg).startswith("--console-command-file=") for arg in launched[0])
    assert report["runtime_exit_fixture_marker_observed"] is True
    assert report["runtime_exit_fixture_blocked_reason"] == ""


def test_runtime_harness_fixture_command_rejects_unexpected_level_load(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n"
                "Game Level Load Time: Level Levels/defaultlevel/defaultlevel.spawnable loaded in 0.00 seconds\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_command=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_default_level_autoload"
    assert report["runtime_exit_fixture_execution_verified"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_exit_fixture_level_load_observed"] is True
    assert report["runtime_exit_fixture_unexpected_level_load"] is True
    assert report["runtime_exit_fixture_uses_no_level"] is False
    assert report["runtime_exit_fixture_uses_production_level"] is True
    assert report["runtime_exit_fixture_blocked_reason"] == "blocked_by_default_level_autoload"
    assert any(
        item.get("signal") == "unexpected_level_load"
        for item in report["runtime_exit_fixture_disqualifying_signals"]["matches"]
    )


def test_runtime_harness_launch_hygiene_diagnostic_source_validates_regremove_strategy(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    registry = project / "Registry"
    registry.mkdir()
    (registry / "load_level.setreg").write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_launch_hygiene=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_launch_hygiene_diagnostic"
    assert report["runtime_launch_hygiene_status"] == "runtime_no_default_level_strategy_source_validated"
    assert report["runtime_default_level_source"] == str(registry / "load_level.setreg")
    assert report["runtime_default_level_path"] == "Levels/defaultlevel/defaultlevel.spawnable"
    assert report["runtime_default_level_disqualifying"] is True
    assert report["runtime_no_default_level_strategy"] == "settings_registry_regremove_autoexec_loadlevel"
    assert report["runtime_no_default_level_strategy_status"] == "runtime_no_default_level_strategy_source_validated"
    assert "--regremove=/O3DE/Autoexec/ConsoleCommands/LoadLevel" in report["runtime_no_default_level_arguments"]
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_execution_verified"] is False


def test_runtime_harness_no_default_level_fixture_command_verifies_clean_launch(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
    launched = []

    def runner(argv, **kwargs):
        launched.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n",
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_no_default_level=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_launch_hygiene_status"] == "runtime_launch_hygiene_pass"
    assert report["runtime_no_default_level_strategy_status"] == "runtime_no_default_level_strategy_pass"
    assert report["runtime_exit_fixture_execution_verified"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_console_command_file_quit"] is False
    assert report["runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_no_default_level_strategy"] is True
    assert any(arg == "--regremove=/O3DE/Autoexec/ConsoleCommands/LoadLevel" for arg in launched[0])
    assert report["runtime_default_level_autoload_detected"] is False
    assert report["runtime_no_default_level_actual_level_loads"] == []
    assert report["runtime_asset_processor_negotiation_signal_status"] == "runtime_asset_processor_negotiation_signal_absent"
    assert report["runtime_shader_serializer_signal_status"] == "runtime_shader_serializer_signal_absent"
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_no_default_level_fixture_command_blocks_shader_serializer_signal(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n"
                "[Error] (Serialize) Shader serializer failed to load descriptor\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_no_default_level=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_shader_serializer_signal"
    assert report["runtime_launch_hygiene_status"] == "runtime_launch_hygiene_failed"
    assert report["runtime_shader_serializer_signal_status"] == "runtime_shader_serializer_signal_present"
    assert report["runtime_shader_serializer_disqualifying"] is True
    assert report["runtime_exit_fixture_execution_verified"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_loadlevel_override_diagnostic_records_effective_candidate_matrix(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    registry = project / "Registry"
    registry.mkdir()
    (registry / "load_level.setreg").write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_loadlevel_override=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_loadlevel_override_diagnostic"
    assert report["runtime_loadlevel_override_status"] == "runtime_loadlevel_override_source_discovery_pass"
    assert report["runtime_settings_registry_merge_order_summary"]["status"] == "runtime_loadlevel_override_source_discovery_pass"
    assert report["runtime_settings_registry_command_line_override_order"] == "command_line_runs_before_project_registry_and_again_after_project_user_registry"
    assert report["runtime_settings_registry_project_registry_order"] == "project_registry_merges_after_early_command_line_and_before_final_command_line"
    assert report["runtime_autoexec_console_command_source"] == str(registry / "load_level.setreg")
    assert report["runtime_autoexec_console_command_effective_state"]["queued_key"] == runtime_harness.RUNTIME_DEFERRED_LOADLEVEL_KEY
    assert report["runtime_loadlevel_override_candidate_matrix_recorded"] is True
    candidate_ids = [candidate["id"] for candidate in report["runtime_loadlevel_override_candidates"]]
    assert candidate_ids == [
        "settings_registry_regremove_autoexec_loadlevel",
        "settings_registry_regremove_autoexec_and_deferred_loadlevel",
    ]
    assert report["runtime_loadlevel_override_candidates"][0]["result"] == "runtime_loadlevel_override_candidate_attempted_failed_defaultlevel_autoload"
    assert report["runtime_loadlevel_override_selected"] == "settings_registry_regremove_autoexec_and_deferred_loadlevel"
    assert report["runtime_loadlevel_override_selected_reason"] == "removes_project_autoexec_key_and_spawnable_level_system_deferred_load_queue"
    assert report["runtime_loadlevel_override_candidate_command_args"] == [
        "--regremove=/O3DE/Autoexec/ConsoleCommands/LoadLevel",
        "--regremove=/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel",
    ]
    assert report["runtime_loadlevel_override_verified"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_loadlevel_override_fixture_command_uses_deferred_removal_and_verifies_clean_launch(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
    launched = []

    def runner(argv, **kwargs):
        launched.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n",
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_loadlevel_override=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_exit_fixture_loadlevel_override_command"
    assert report["runtime_loadlevel_override_status"] == "runtime_loadlevel_override_verified_no_defaultlevel"
    assert report["runtime_loadlevel_override_verified"] is True
    assert report["runtime_loadlevel_override_selected"] == "settings_registry_regremove_autoexec_and_deferred_loadlevel"
    assert "--regremove=/O3DE/Autoexec/ConsoleCommands/LoadLevel" in launched[0]
    assert "--regremove=/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel" in launched[0]
    assert report["runtime_exit_fixture_runtime_command_uses_loadlevel_override_strategy"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_console_command_file_quit"] is False
    assert report["runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit"] is True
    assert report["runtime_default_level_autoload_detected"] is False
    assert report["runtime_loadlevel_override_candidate_actual_level_loads"] == []
    assert report["runtime_launch_hygiene_status"] == "runtime_launch_hygiene_pass"
    assert report["runtime_exit_fixture_execution_verified"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_loadlevel_override_fixture_command_blocks_when_defaultlevel_still_loads(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n"
                "Game Level Load Time: Level Levels/defaultlevel/defaultlevel.spawnable loaded in 0.00 seconds\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_loadlevel_override=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_default_level_autoload"
    assert report["runtime_loadlevel_override_status"] == "runtime_loadlevel_override_candidate_attempted_failed_defaultlevel_autoload"
    assert report["runtime_loadlevel_override_verified"] is False
    assert report["runtime_default_level_autoload_detected"] is True
    assert report["runtime_default_level_disqualifying"] is True
    assert report["runtime_exit_fixture_execution_verified"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_later_registry_patch_diagnostic_records_source_validated_candidate_matrix(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    registry = project / "Registry"
    registry.mkdir()
    (registry / "load_level.setreg").write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_later_registry_patch=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_later_registry_patch_diagnostic"
    assert report["runtime_later_registry_patch_status"] == "runtime_later_registry_patch_source_discovery_pass"
    assert report["runtime_later_registry_patch_candidate_matrix_recorded"] is True
    candidate_ids = [candidate["id"] for candidate in report["runtime_later_registry_patch_candidates"]]
    assert candidate_ids == [
        "settings_registry_regremove_autoexec_loadlevel",
        "settings_registry_regremove_autoexec_and_deferred_loadlevel",
        "artifact_setregpatch_remove_autoexec_and_deferred_loadlevel",
        "artifact_setreg_merge_patch_null_autoexec_and_deferred_loadlevel",
    ]
    failed_json_patch = report["runtime_later_registry_patch_candidates"][2]
    assert failed_json_patch["result"] == "runtime_later_registry_patch_candidate_rejected_json_patch_remove_target_missing"
    assert failed_json_patch["blocker"] == "blocked_by_fixture_temp_registry_patch_not_safe"
    assert report["runtime_later_registry_patch_selected"] == (
        "artifact_setreg_merge_patch_null_autoexec_and_deferred_loadlevel"
    )
    assert report["runtime_later_registry_patch_candidate_patch_path"].endswith(
        "maxine_runtime_later_precedence_loadlevel_null_remove.setreg"
    )
    assert report["runtime_later_registry_patch_candidate_patch_contents_summary"] == (
        "JSON Merge Patch sets /O3DE/Autoexec/ConsoleCommands/LoadLevel and "
        "/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel to null so the keys are deleted."
    )
    assert report["runtime_later_registry_patch_candidate_merge_mechanism"] == (
        "command_line_regset_file_setreg_json_merge_patch_null_delete"
    )
    assert report["runtime_later_registry_patch_candidate_merge_order"] == (
        "final_command_line_regset_file_after_project_registry_and_project_user_registry"
    )
    assert "MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH=1" in report[
        "runtime_later_registry_patch_candidate_gate_env"
    ]
    assert report["runtime_later_registry_patch_candidate_mutates_project"] is False
    assert report["runtime_later_registry_patch_candidate_mutates_defaultlevel"] is False
    assert report["runtime_later_registry_patch_candidate_mutates_production_level"] is False
    assert report["runtime_later_registry_patch_candidate_command_args"] == [
        f"--regset-file={report['runtime_later_registry_patch_candidate_patch_path']}"
    ]
    assert report["runtime_later_registry_patch_verified"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_later_registry_patch_fixture_requires_temp_registry_patch_gate(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        raise AssertionError("runtime command must not launch without the temp registry patch gate")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_later_registry_patch=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_fixture_temp_registry_patch_gate_missing"
    assert report["runtime_later_registry_patch_status"] == "blocked_by_fixture_temp_registry_patch_gate_missing"
    assert report["runtime_later_registry_patch_candidate_attempted"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_exit_fixture_execution_attempted"] is False
    assert not (tmp_path / "artifacts" / "maxine_runtime_later_precedence_loadlevel_null_remove.setreg").exists()


def test_runtime_harness_later_registry_patch_fixture_command_generates_patch_and_verifies_clean_launch(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
    launched = []

    def runner(argv, **kwargs):
        launched.append(argv)
        regset_file_arg = next(arg for arg in argv if str(arg).startswith("--regset-file="))
        patch_path = Path(str(regset_file_arg).split("=", 1)[1])
        assert patch_path.exists()
        assert json.loads(patch_path.read_text(encoding="utf-8")) == {
            "O3DE": {
                "Autoexec": {"ConsoleCommands": {"LoadLevel": None}},
                "Runtime": {"SpawnableLevelSystem": {"DeferredLoadLevel": None}},
            }
        }
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n",
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_later_registry_patch=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_exit_fixture_later_registry_patch_command"
    assert report["runtime_later_registry_patch_status"] == "runtime_later_registry_patch_verified_no_defaultlevel"
    assert report["runtime_later_registry_patch_verified"] is True
    assert report["runtime_loadlevel_override_verified"] is True
    assert report["runtime_later_registry_patch_candidate_result"] == "runtime_later_registry_patch_candidate_attempted_pass"
    assert report["runtime_exit_fixture_runtime_command_uses_later_registry_patch_strategy"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_loadlevel_override_strategy"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_console_command_file_quit"] is False
    assert report["runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit"] is True
    assert any(str(arg).startswith("--regset-file=") for arg in launched[0])
    assert not any(str(arg).startswith("--regremove=") for arg in launched[0])
    assert report["runtime_later_registry_patch_candidate_patch_path"].endswith(
        "maxine_runtime_later_precedence_loadlevel_null_remove.setreg"
    )
    assert report["runtime_later_registry_patch_candidate_actual_level_loads"] == []
    assert report["runtime_default_level_autoload_detected"] is False
    assert report["runtime_launch_hygiene_status"] == "runtime_launch_hygiene_pass"
    assert report["runtime_exit_fixture_execution_verified"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_character_proof_claimed"] is False
    assert report["defaultlevel_mutation"] is False
    assert report["production_level_mutation"] is False


def test_runtime_harness_later_registry_patch_fixture_command_blocks_when_defaultlevel_still_loads(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH"] = "1"
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n"
                "Game Level Load Time: Level Levels/defaultlevel/defaultlevel.spawnable loaded in 0.00 seconds\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_later_registry_patch=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_default_level_autoload"
    assert report["runtime_later_registry_patch_status"] == (
        "runtime_later_registry_patch_candidate_attempted_failed_defaultlevel_autoload"
    )
    assert report["runtime_later_registry_patch_verified"] is False
    assert report["runtime_later_registry_patch_candidate_blocker"] == "blocked_by_settings_registry_merge_order"
    assert report["runtime_default_level_autoload_detected"] is True
    assert report["runtime_default_level_disqualifying"] is True
    assert report["runtime_exit_fixture_execution_verified"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_validation_rejects_later_registry_patch_verified_without_clean_execution() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_later_registry_patch_verified": True,
            "runtime_later_registry_patch_selected": "artifact_setreg_merge_patch_null_autoexec_and_deferred_loadlevel",
            "runtime_execution_verified": False,
            "runtime_launch_hygiene_status": "runtime_launch_hygiene_failed",
            "runtime_default_level_autoload_detected": True,
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_later_registry_patch_verified=true requires verified runtime execution" in message for message in result.messages)


def test_runtime_harness_pre_autoexec_diagnostic_records_source_validated_candidate_matrix(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    registry = project / "Registry"
    registry.mkdir()
    (registry / "load_level.setreg").write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_pre_autoexec_loadlevel_suppression=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_pre_autoexec_loadlevel_suppression_diagnostic"
    assert report["runtime_pre_autoexec_loadlevel_suppression_status"] == (
        "runtime_pre_autoexec_suppression_source_discovery_pass"
    )
    assert report["runtime_settings_registry_project_user_registry_order"] == (
        "project_user_registry_merges_before_project_registry_in_shared_settings_and_again_after_project_registry_in_user_settings"
    )
    assert report["runtime_console_autoexec_notification_timing"] == (
        "console_registers_settings_registry_notifier_before_project_registry_merge_and_executes_autoexec_on_each_merged_key"
    )
    assert report["runtime_spawnable_level_deferred_load_timing"] == (
        "LoadLevel_before_level_system_queues_deferred_key_and_spawnable_level_system_consumes_it_in_constructor"
    )
    assert report["runtime_pre_autoexec_candidate_matrix_recorded"] is True
    candidate_ids = [candidate["id"] for candidate in report["runtime_pre_autoexec_loadlevel_suppression_candidates"]]
    assert candidate_ids == [
        "settings_registry_regremove_autoexec_loadlevel",
        "settings_registry_regremove_autoexec_and_deferred_loadlevel",
        "artifact_setreg_merge_patch_null_autoexec_and_deferred_loadlevel",
        "project_user_registry_null_delete_loadlevel",
        "project_cache_bootstrap_setreg_defaultlevel_suppression",
        "project_registry_load_level_setreg_temporarily_disabled_pre_autoexec",
    ]
    rejected_user = report["runtime_pre_autoexec_loadlevel_suppression_candidates"][3]
    assert rejected_user["result"] == "runtime_pre_autoexec_candidate_rejected_project_user_precedes_project_registry"
    assert rejected_user["blocker"] == "blocked_by_project_user_registry_override_not_safe"
    rejected_cache = report["runtime_pre_autoexec_loadlevel_suppression_candidates"][4]
    assert rejected_cache["result"] == "runtime_pre_autoexec_candidate_rejected_requires_asset_cache_mutation"
    assert rejected_cache["blocker"] == "blocked_by_project_cache_bootstrap_defaultlevel_autoload"
    assert report["runtime_pre_autoexec_selected"] == "project_registry_load_level_setreg_temporarily_disabled_pre_autoexec"
    assert report["runtime_pre_autoexec_candidate_mutates_project"] is True
    assert report["runtime_pre_autoexec_candidate_mutates_project_user"] is False
    assert report["runtime_pre_autoexec_candidate_mutates_defaultlevel"] is False
    assert report["runtime_pre_autoexec_candidate_mutates_production_level"] is False
    assert report["runtime_pre_autoexec_candidate_reversible"] is True
    assert "MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION=1" in report["runtime_pre_autoexec_candidate_gate_env"]
    assert report["runtime_pre_autoexec_suppression_verified"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_pre_autoexec_records_cache_bootstrap_blocker(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    registry = project / "Registry"
    registry.mkdir()
    source = registry / "load_level.setreg"
    source.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    cache = project / "Cache" / "pc"
    cache.mkdir(parents=True)
    (cache / "bootstrap.server.profile.setreg").write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n"
                "Game Level Load Time: Level Levels/defaultlevel/defaultlevel.spawnable loaded in 0.00 seconds\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_project_cache_bootstrap_defaultlevel_autoload"
    assert report["runtime_pre_autoexec_candidate_blocker"] == "blocked_by_project_cache_bootstrap_defaultlevel_autoload"
    assert report["runtime_pre_autoexec_cache_bootstrap_loadlevel_source_count"] == 1
    assert report["runtime_pre_autoexec_cache_bootstrap_loadlevel_sources"][0].endswith(
        "Cache/pc/bootstrap.server.profile.setreg"
    )
    assert report["runtime_pre_autoexec_suppression_verified"] is False
    assert source.exists()


def test_runtime_harness_pre_autoexec_fixture_requires_project_mutation_gate(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    registry = project / "Registry"
    registry.mkdir()
    source = registry / "load_level.setreg"
    source.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    original = source.read_text(encoding="utf-8")
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        raise AssertionError("runtime command must not launch without the project mutation gate")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_fixture_project_mutation_gate_missing"
    assert report["runtime_pre_autoexec_loadlevel_suppression_status"] == (
        "blocked_by_fixture_project_mutation_gate_missing"
    )
    assert report["runtime_pre_autoexec_candidate_attempted"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_exit_fixture_execution_attempted"] is False
    assert source.exists()
    assert source.read_text(encoding="utf-8") == original


def test_runtime_harness_pre_autoexec_fixture_temporarily_disables_load_level_and_restores(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    registry = project / "Registry"
    registry.mkdir()
    source = registry / "load_level.setreg"
    source.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    original = source.read_text(encoding="utf-8")
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
    launched = []

    def runner(argv, **kwargs):
        launched.append(argv)
        assert not source.exists()
        assert (registry / "load_level.setreg.maxine_pre_autoexec_disabled").exists()
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n",
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_exit_fixture_pre_autoexec_loadlevel_suppression_command"
    assert report["runtime_pre_autoexec_loadlevel_suppression_status"] == (
        "runtime_pre_autoexec_suppression_verified_no_defaultlevel"
    )
    assert report["runtime_pre_autoexec_suppression_verified"] is True
    assert report["runtime_pre_autoexec_candidate_result"] == "runtime_pre_autoexec_candidate_attempted_pass"
    assert report["runtime_exit_fixture_runtime_command_uses_pre_autoexec_suppression_strategy"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_console_command_file_quit"] is False
    assert not any(str(arg).startswith("--regremove=") for arg in launched[0])
    assert not any(str(arg).startswith("--regset-file=") for arg in launched[0])
    assert report["runtime_pre_autoexec_candidate_actual_level_loads"] == []
    assert report["runtime_pre_autoexec_candidate_mutation_path"].endswith("Registry/load_level.setreg")
    assert report["runtime_pre_autoexec_candidate_mutation_restored"] is True
    assert source.exists()
    assert source.read_text(encoding="utf-8") == original
    assert not (registry / "load_level.setreg.maxine_pre_autoexec_disabled").exists()
    assert report["runtime_default_level_autoload_detected"] is False
    assert report["runtime_launch_hygiene_status"] == "runtime_launch_hygiene_pass"
    assert report["runtime_exit_fixture_execution_verified"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_character_proof_claimed"] is False
    assert report["defaultlevel_mutation"] is False
    assert report["production_level_mutation"] is False


def test_runtime_harness_pre_autoexec_fixture_blocks_when_defaultlevel_still_loads(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    registry = project / "Registry"
    registry.mkdir()
    source = registry / "load_level.setreg"
    source.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n"
                "Game Level Load Time: Level Levels/defaultlevel/defaultlevel.spawnable loaded in 0.00 seconds\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_pre_autoexec_loadlevel_suppression=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_default_level_autoload"
    assert report["runtime_pre_autoexec_loadlevel_suppression_status"] == (
        "runtime_pre_autoexec_candidate_attempted_failed_defaultlevel_autoload"
    )
    assert report["runtime_pre_autoexec_suppression_verified"] is False
    assert report["runtime_pre_autoexec_candidate_blocker"] == "blocked_by_default_level_autoload"
    assert report["runtime_default_level_autoload_detected"] is True
    assert report["runtime_default_level_disqualifying"] is True
    assert report["runtime_exit_fixture_execution_verified"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_character_proof_claimed"] is False
    assert source.exists()


def test_runtime_harness_validation_rejects_pre_autoexec_verified_without_clean_execution() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_pre_autoexec_suppression_verified": True,
            "runtime_pre_autoexec_selected": "project_registry_load_level_setreg_temporarily_disabled_pre_autoexec",
            "runtime_pre_autoexec_candidate_reversible": True,
            "runtime_pre_autoexec_candidate_mutation_restored": True,
            "runtime_execution_verified": False,
            "runtime_launch_hygiene_status": "runtime_launch_hygiene_failed",
            "runtime_default_level_autoload_detected": True,
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_pre_autoexec_suppression_verified=true requires verified runtime execution" in message for message in result.messages)


def test_runtime_harness_cache_bootstrap_diagnostic_records_inventory_and_candidate_matrix(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    registry = project / "Registry"
    registry.mkdir()
    (registry / "load_level.setreg").write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    cache = project / "Cache" / "pc"
    cache.mkdir(parents=True)
    bootstrap = cache / "bootstrap.server.profile.setreg"
    bootstrap.write_text(
        json.dumps(
            {
                "O3DE": {
                    "Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}},
                    "Runtime": {"SpawnableLevelSystem": {"DeferredLoadLevel": "defaultlevel"}},
                }
            }
        ),
        encoding="utf-8",
    )
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_cache_bootstrap_loadlevel_source=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_cache_bootstrap_loadlevel_source_diagnostic"
    assert report["runtime_cache_bootstrap_loadlevel_source_status"] == "runtime_cache_bootstrap_source_discovery_pass"
    assert report["runtime_cache_bootstrap_source_discovery_status"] == "runtime_cache_bootstrap_loadlevel_source_detected"
    assert report["runtime_cache_bootstrap_generation_source"] == "AssetProcessor_SettingsRegistryBuilder"
    assert "SettingsRegistryBuilder.cpp" in " ".join(report["runtime_cache_bootstrap_generation_source_refs"])
    assert "GameApplication.cpp" in " ".join(report["runtime_cache_bootstrap_generation_source_refs"])
    assert report["runtime_cache_bootstrap_runtime_load_timing"] == (
        "GameApplication_MergeSettingsToRegistry_merges_bootstrap_launcher_config_setreg_from_cache_root_after_shared_settings_before_user_settings"
    )
    assert report["runtime_cache_bootstrap_candidate_matrix_recorded"] is True
    candidate_ids = [candidate["id"] for candidate in report["runtime_cache_bootstrap_candidate_matrix"]]
    assert candidate_ids == [
        "cache_bootstrap_read_only_inventory",
        "cache_bootstrap_scoped_apb_refresh_after_source_suppression",
        "cache_bootstrap_generated_registry_overlay_before_autoexec",
        "cache_bootstrap_setreg_temporarily_neutralized_with_project_source_suppression",
        "cache_bootstrap_requires_asset_cache_deletion",
    ]
    assert report["runtime_cache_bootstrap_selected"] == (
        "cache_bootstrap_setreg_temporarily_neutralized_with_project_source_suppression"
    )
    assert report["runtime_cache_bootstrap_verified"] is False
    assert report["asset_cache_deleted"] is False
    assert len(report["runtime_cache_bootstrap_files"]) == 1
    scanned = report["runtime_cache_bootstrap_files"][0]
    assert scanned["path"].endswith("Cache/pc/bootstrap.server.profile.setreg")
    assert scanned["exists"] is True
    assert scanned["hash"]
    assert scanned["mtime"]
    assert scanned["contains_loadlevel"] is True
    assert scanned["contains_deferred_loadlevel"] is True
    assert scanned["loadlevel_value"] == "defaultlevel"
    assert scanned["source_candidate"] == "project_registry_load_level_setreg"
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_cache_bootstrap_fixture_requires_mutation_gate(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    registry = project / "Registry"
    registry.mkdir()
    source = registry / "load_level.setreg"
    source.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    cache = project / "Cache" / "pc"
    cache.mkdir(parents=True)
    bootstrap = cache / "bootstrap.server.profile.setreg"
    original_bootstrap = json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}})
    bootstrap.write_text(original_bootstrap, encoding="utf-8")
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        raise AssertionError("runtime command must not launch without the cache-bootstrap mutation gate")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_fixture_cache_bootstrap_mutation_gate_missing"
    assert report["runtime_cache_bootstrap_loadlevel_source_status"] == (
        "blocked_by_fixture_cache_bootstrap_mutation_gate_missing"
    )
    assert report["runtime_cache_bootstrap_candidate_attempted"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_exit_fixture_execution_attempted"] is False
    assert source.exists()
    assert bootstrap.read_text(encoding="utf-8") == original_bootstrap
    assert report["asset_cache_deleted"] is False


def test_runtime_harness_cache_bootstrap_fixture_neutralizes_bootstrap_and_restores_hashes(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION"] = "1"
    registry = project / "Registry"
    registry.mkdir()
    source = registry / "load_level.setreg"
    source.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    cache = project / "Cache" / "pc"
    cache.mkdir(parents=True)
    bootstrap = cache / "bootstrap.server.profile.setreg"
    original_bootstrap = json.dumps(
        {
            "O3DE": {
                "Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}},
                "Runtime": {"SpawnableLevelSystem": {"DeferredLoadLevel": "defaultlevel"}},
            }
        }
    )
    bootstrap.write_text(original_bootstrap, encoding="utf-8")
    original_source = source.read_text(encoding="utf-8")
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
    launched = []

    def runner(argv, **kwargs):
        launched.append(argv)
        assert not source.exists()
        mutated = json.loads(bootstrap.read_text(encoding="utf-8"))
        assert "LoadLevel" not in mutated["O3DE"]["Autoexec"]["ConsoleCommands"]
        assert "DeferredLoadLevel" not in mutated["O3DE"]["Runtime"]["SpawnableLevelSystem"]
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n",
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_exit_fixture_cache_bootstrap_loadlevel_source_command"
    assert report["runtime_cache_bootstrap_loadlevel_source_status"] == "runtime_cache_bootstrap_verified_no_defaultlevel"
    assert report["runtime_cache_bootstrap_candidate_result"] == "runtime_cache_bootstrap_candidate_attempted_pass"
    assert report["runtime_cache_bootstrap_verified"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_cache_bootstrap_strategy"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_pre_autoexec_suppression_strategy"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_settings_registry_fixture_exit"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_console_command_file_quit"] is False
    assert not any(str(arg).startswith("--regremove=") for arg in launched[0])
    assert not any(str(arg).startswith("--regset-file=") for arg in launched[0])
    assert report["runtime_cache_bootstrap_candidate_backup_refs"]
    assert report["runtime_cache_bootstrap_candidate_restore_status"] == "runtime_cache_bootstrap_restore_pass"
    assert report["runtime_cache_bootstrap_candidate_hash_verified"] is True
    assert report["runtime_cache_bootstrap_candidate_mutates_cache"] is True
    assert report["runtime_cache_bootstrap_candidate_mutates_project"] is True
    assert report["runtime_cache_bootstrap_candidate_mutates_defaultlevel"] is False
    assert report["runtime_cache_bootstrap_candidate_mutates_production_level"] is False
    assert report["runtime_cache_bootstrap_candidate_actual_level_loads"] == []
    assert report["runtime_default_level_autoload_detected"] is False
    assert report["runtime_launch_hygiene_status"] == "runtime_launch_hygiene_pass"
    assert report["runtime_exit_fixture_execution_verified"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_character_proof_claimed"] is False
    assert source.exists()
    assert source.read_text(encoding="utf-8") == original_source
    assert bootstrap.read_text(encoding="utf-8") == original_bootstrap
    assert report["asset_cache_deleted"] is False
    assert report["defaultlevel_mutation"] is False
    assert report["production_level_mutation"] is False


def test_runtime_harness_cache_bootstrap_fixture_blocks_when_defaultlevel_still_loads(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION"] = "1"
    registry = project / "Registry"
    registry.mkdir()
    source = registry / "load_level.setreg"
    source.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    cache = project / "Cache" / "pc"
    cache.mkdir(parents=True)
    bootstrap = cache / "bootstrap.server.profile.setreg"
    bootstrap.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n"
                "Game Level Load Time: Level Levels/defaultlevel/defaultlevel.spawnable loaded in 0.00 seconds\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_cache_bootstrap_loadlevel_source=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_default_level_autoload"
    assert report["runtime_cache_bootstrap_loadlevel_source_status"] == (
        "runtime_cache_bootstrap_candidate_attempted_failed_defaultlevel_autoload"
    )
    assert report["runtime_cache_bootstrap_candidate_blocker"] == "blocked_by_default_level_autoload"
    assert report["runtime_cache_bootstrap_candidate_restore_status"] == "runtime_cache_bootstrap_restore_pass"
    assert report["runtime_cache_bootstrap_candidate_hash_verified"] is True
    assert report["runtime_cache_bootstrap_verified"] is False
    assert report["runtime_default_level_autoload_detected"] is True
    assert report["runtime_default_level_disqualifying"] is True
    assert report["runtime_exit_fixture_execution_verified"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_character_proof_claimed"] is False
    assert source.exists()
    assert bootstrap.exists()
    assert report["asset_cache_deleted"] is False


def test_runtime_harness_validation_rejects_cache_bootstrap_verified_without_clean_execution() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_cache_bootstrap_verified": True,
            "runtime_cache_bootstrap_selected": "cache_bootstrap_setreg_temporarily_neutralized_with_project_source_suppression",
            "runtime_cache_bootstrap_candidate_reversible": True,
            "runtime_cache_bootstrap_candidate_restore_status": "runtime_cache_bootstrap_restore_pass",
            "runtime_cache_bootstrap_candidate_hash_verified": True,
            "runtime_execution_verified": False,
            "runtime_launch_hygiene_status": "runtime_launch_hygiene_failed",
            "runtime_default_level_autoload_detected": True,
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_cache_bootstrap_verified=true requires verified runtime execution" in message for message in result.messages)


def test_runtime_harness_validation_rejects_asset_cache_deletion() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report["asset_cache_deleted"] = True

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("Runtime harness must not delete Asset Cache" in message for message in result.messages)


def test_runtime_harness_ap_shader_signal_diagnostic_records_source_classification_matrix(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_ap_shader_signals=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_ap_shader_signal_classification_diagnostic"
    assert report["runtime_signal_classification_status"] == "runtime_signal_classification_source_discovery_pass"
    assert report["runtime_signal_classification_candidate_matrix_recorded"] is True
    candidate_ids = [candidate["id"] for candidate in report["runtime_signal_classification_candidates"]]
    assert candidate_ids == [
        "ap_shader_read_only_existing_log_classification",
        "ap_shader_no_defaultlevel_cache_bootstrap_fixture_rerun",
        "ap_shader_controlled_asset_processor_session_comparison",
        "ap_shader_shader_product_completeness_audit",
        "ap_shader_keep_disqualifying_if_unclassified",
    ]
    assert report["runtime_signal_classification_selected"] == "ap_shader_no_defaultlevel_cache_bootstrap_fixture_rerun"
    assert "AssetProcessorConnection.cpp" in " ".join(report["runtime_asset_processor_negotiation_source_refs"])
    assert "Launcher.cpp" in " ".join(report["runtime_asset_processor_negotiation_source_refs"])
    assert "ObjectStream.cpp" in " ".join(report["runtime_shader_serializer_source_refs"])
    assert "Atom/RHI/Null" in " ".join(report["runtime_shader_serializer_source_refs"])
    assert report["runtime_signal_classification_verified"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_ap_shader_fixture_classifies_known_signals_without_character_proof(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION"] = "1"
    registry = project / "Registry"
    registry.mkdir()
    source = registry / "load_level.setreg"
    source.write_text(
        json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}}),
        encoding="utf-8",
    )
    cache = project / "Cache" / "pc"
    cache.mkdir(parents=True)
    bootstrap = cache / "bootstrap.server.profile.setreg"
    original_bootstrap = json.dumps({"O3DE": {"Autoexec": {"ConsoleCommands": {"LoadLevel": "defaultlevel"}}}})
    bootstrap.write_text(original_bootstrap, encoding="utf-8")
    original_source = source.read_text(encoding="utf-8")
    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    payload["gem_names"].append(runtime_harness.RUNTIME_EXIT_FIXTURE_GEM_NAME)
    (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "Launcher: Connecting to Asset Processor...\n"
                "AssetProcessorConnection::ConnectThread: Network connection attempt failure, negotiation with 127.0.0.1:45643 failed.\n"
                "GAME: Negotiation with asset processor failed\n"
                "<12:38:04> [Error] (Serialize) - Element 'NULL'(0x41405e39) with class ID "
                "'{1BAEE536-96CA-4AEB-BA73-D5D72EE35B45}' found in 'AZStd::intrusive_ptr<ShaderStageFunction>' "
                "is not registered with the serializer!\n"
                "<12:38:04> [Error] (Serialize) - Element 'NULL'(0x41405e39) with class ID "
                "'{A606478A-97E9-402D-A776-88EE72DAC6F9}' found in 'AZStd::intrusive_ptr<ShaderStageFunction>' "
                "is not registered with the serializer!\n"
                "<12:38:04> [Error] (Serialize) - Element 'NULL'(0x41405e39) with class ID "
                "'{A10B0F03-F43D-4462-9306-66195B4EFC46}' found in 'AZStd::intrusive_ptr<PipelineLayoutDescriptor>' "
                "is not registered with the serializer!\n"
                "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_exit_fixture_ap_shader_signal_classification=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=120,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_exit_fixture_ap_shader_signal_classification_command"
    assert report["runtime_signal_classification_status"] == "runtime_signal_classification_verified"
    assert report["runtime_signal_classification_verified"] is True
    assert report["runtime_asset_processor_negotiation_signal_present"] is True
    assert report["runtime_asset_processor_negotiation_classification"] == "runtime_asset_processor_negotiation_classified_harmless"
    assert report["runtime_asset_processor_negotiation_disqualifying"] is False
    assert report["runtime_shader_serializer_signal_present"] is True
    assert report["runtime_shader_serializer_classification"] == "runtime_shader_serializer_classified_harmless"
    assert report["runtime_shader_serializer_disqualifying"] is False
    assert report["runtime_default_level_autoload_detected"] is False
    assert report["runtime_production_level_loaded"] is False
    assert report["runtime_launch_hygiene_status"] == "runtime_launch_hygiene_pass"
    assert report["runtime_exit_fixture_execution_verified"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_cache_bootstrap_candidate_restore_status"] == "runtime_cache_bootstrap_restore_pass"
    assert report["runtime_cache_bootstrap_candidate_hash_verified"] is True
    assert source.exists()
    assert source.read_text(encoding="utf-8") == original_source
    assert bootstrap.read_text(encoding="utf-8") == original_bootstrap
    assert report["asset_cache_deleted"] is False


def test_runtime_harness_validation_rejects_signal_classification_without_source_refs() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_signal_classification_verified": True,
            "runtime_signal_classification_selected": "ap_shader_no_defaultlevel_cache_bootstrap_fixture_rerun",
            "runtime_execution_verified": True,
            "runtime_launch_hygiene_status": "runtime_launch_hygiene_pass",
            "runtime_asset_processor_negotiation_signal_present": True,
            "runtime_asset_processor_negotiation_classification": "runtime_asset_processor_negotiation_classified_harmless",
            "runtime_asset_processor_negotiation_disqualifying": False,
            "runtime_asset_processor_negotiation_source_refs": [],
            "runtime_asset_processor_negotiation_harmless_only_if": [],
            "runtime_shader_serializer_signal_present": True,
            "runtime_shader_serializer_classification": "runtime_shader_serializer_classified_harmless",
            "runtime_shader_serializer_disqualifying": False,
            "runtime_shader_serializer_source_refs": [],
            "runtime_shader_serializer_harmless_only_if": [],
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_signal_classification_verified=true requires AP and shader source refs" in message for message in result.messages)


def test_runtime_harness_character_product_load_diagnostic_records_source_validation_matrix(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    _enable_fixture_gem(project)
    _append_apb_products(
        apb,
        [
            {
                "product_type": "spawnable",
                "product_path": "pc/assets/characters/maxine/release/maxine_character.spawnable",
                "source_path": "Assets/Characters/Maxine/Release/maxine_character.prefab",
                "source_uuid": "55555555555545558555555555555555",
                "source_sub_id": "45",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            }
        ],
    )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_character_product_load=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_character_product_load_diagnostic"
    assert report["runtime_character_product_load_status"] == "runtime_character_product_load_source_discovery_pass"
    assert report["runtime_character_product_load_probe_enabled"] is False
    assert report["runtime_character_product_load_probe_shipping_behavior"] is False
    assert report["runtime_character_product_load_source_refs"]
    assert "AssetManagerBus.h" in " ".join(report["runtime_character_product_load_source_refs"])
    assert "AssetManager.h" in " ".join(report["runtime_character_product_load_source_refs"])
    assert "AssetCommon.h" in " ".join(report["runtime_character_product_load_source_refs"])
    assert report["runtime_character_product_load_asset_catalog_api"] == "AZ::Data::AssetCatalogRequestBus::GetAssetIdByPath"
    assert report["runtime_character_product_load_asset_manager_api"] == "AZ::Data::AssetManager::GetAsset"
    assert report["runtime_character_product_load_candidate_matrix_recorded"] is True
    candidate_ids = [candidate["id"] for candidate in report["runtime_character_product_load_candidate_matrix"]]
    assert candidate_ids == [
        "runtime_character_product_load_source_api_discovery",
        "runtime_character_product_load_assetcatalog_resolution_only",
        "runtime_character_product_load_generic_assetmanager_load",
        "runtime_character_product_load_type_specific_assetmanager_load",
        "runtime_character_product_load_keep_blocked_without_source_validation",
    ]
    assert report["runtime_character_product_load_selected_strategy"] == "runtime_character_product_load_generic_assetmanager_load"
    assert [product["product_kind"] for product in report["runtime_character_product_load_products"]] == list(
        runtime_harness.RUNTIME_CHARACTER_PRODUCT_LOAD_UPDATED_REQUIRED_PRODUCTS
    )
    assert "procprefab" not in [product["product_kind"] for product in report["runtime_character_product_load_products"]]
    assert report["runtime_character_product_load_direct_procprefab_required"] is False
    assert report["runtime_character_product_load_runtime_equivalent_required"] is True
    assert all(product["catalog_path"].startswith("assets/") for product in report["runtime_character_product_load_products"])
    assert report["runtime_character_product_load_claimed"] is False
    assert report["runtime_character_product_load_verified"] is False
    assert report["runtime_character_product_load_is_instantiation_proof"] is False
    assert report["runtime_character_instantiation_claimed"] is False
    assert report["runtime_character_animation_claimed"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_character_product_load_derives_asset_id_from_apb_database_fields(tmp_path: Path) -> None:
    _env, _engine_root, _project_path, apb = _runtime_env(tmp_path, gates=True)
    products = runtime_harness._runtime_character_product_load_products_from_apb(
        runtime_harness._product_evidence_from_apb(apb)
    )
    procprefab = next(product for product in products if product["product_kind"] == "procprefab")

    assert procprefab["asset_id"] == "{794D1588-3C41-5795-8A9A-EEBD6A663A60}:11695305"
    assert procprefab["asset_type_id"] == "{9B7C8459-471E-4EAD-A363-7990CC4065A9}"
    assert procprefab["asset_type_name"] == "AZ::Prefab::ProceduralPrefabAsset"
    assert (
        runtime_harness._runtime_product_asset_id(
            {
                "source_uuid": "634bcaf8a44b56b0bc6f4468bdd8be67",
                "source_sub_id": "-998238619",
            }
        )
        == "{634BCAF8-A44B-56B0-BC6F-4468BDD8BE67}:c4801665"
    )


def test_runtime_harness_procprefab_handler_surface_diagnostic_records_builder_only_handler(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    _enable_fixture_gem(project)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_procprefab_handler_or_spawnable_surface=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_procprefab_handler_or_surface_diagnostic"
    assert report["runtime_procprefab_handler_or_surface_status"] == "runtime_procprefab_surface_source_discovery_pass"
    assert report["runtime_procprefab_direct_load_status"] == "runtime_procprefab_direct_load_unsupported_builder_only"
    assert report["runtime_procprefab_direct_load_asset_id"] == "{794D1588-3C41-5795-8A9A-EEBD6A663A60}:11695305"
    assert report["runtime_procprefab_direct_load_asset_type"] == "{9B7C8459-471E-4EAD-A363-7990CC4065A9}"
    assert report["runtime_procprefab_direct_load_asset_class"] == "AZ::Prefab::ProceduralPrefabAsset"
    assert report["runtime_procprefab_direct_load_handler_status"] == "runtime_procprefab_direct_load_handler_missing"
    assert report["runtime_procprefab_direct_load_handler_module"] == "Gem::PrefabBuilder.Builders"
    assert report["runtime_procprefab_direct_load_supported"] is False
    assert report["runtime_procprefab_direct_load_supported_reason"] == "runtime_procprefab_direct_load_unsupported_builder_only"
    assert report["runtime_procprefab_direct_load_blocker"] == "blocked_by_runtime_procprefab_direct_load_unsupported"
    assert report["runtime_procprefab_direct_load_claimed"] is False
    assert report["runtime_procprefab_direct_load_verified"] is False
    source_refs = " ".join(report["runtime_procprefab_direct_load_handler_source_refs"])
    assert "ProceduralPrefabAsset.h" in source_refs
    assert "ProceduralAssetHandler.cpp" in source_refs
    assert "PrefabBuilder" in source_refs
    assert report["runtime_procprefab_surface_candidate_matrix_recorded"] is True
    candidate_ids = [candidate["id"] for candidate in report["runtime_procprefab_surface_candidate_matrix"]]
    assert candidate_ids == [
        "runtime_procprefab_direct_assetmanager_load",
        "runtime_spawnable_asset_load_surface",
        "runtime_spawnable_instantiation_surface",
        "runtime_procprefab_keep_blocked_without_runtime_surface",
    ]
    assert report["runtime_procprefab_surface_selected"] == ""
    assert report["runtime_procprefab_runtime_equivalent_surface_claimed"] is False
    assert report["runtime_procprefab_runtime_equivalent_surface_verified"] is False
    assert report["runtime_procprefab_surface_remaining_blocker"] == "blocked_by_missing_runtime_equivalent_spawnable_surface"
    assert report["runtime_character_product_load_contract_updated"] is True
    assert report["runtime_character_product_load_direct_procprefab_required"] is False
    assert report["runtime_character_product_load_runtime_equivalent_required"] is True
    assert report["runtime_character_product_load_contract_blocker"] == "blocked_by_missing_runtime_equivalent_spawnable_surface"
    assert report["runtime_character_product_load_claimed"] is False
    assert report["runtime_character_product_load_verified"] is False
    assert report["runtime_character_instantiation_claimed"] is False
    assert report["runtime_character_animation_claimed"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_character_spawnable_surface_diagnostic_rejects_level_and_generic_candidates(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    _enable_fixture_gem(project)
    _append_apb_products(
        apb,
        [
            {
                "product_type": "spawnable",
                "product_path": "pc/levels/defaultlevel/defaultlevel.spawnable",
                "source_path": "Levels/DefaultLevel/DefaultLevel.prefab",
                "source_uuid": "22222222222242228222222222222222",
                "source_sub_id": "-1950141713",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            },
            {
                "product_type": "spawnable",
                "product_path": "pc/levels/_maxine_smoke/generated/generated.spawnable",
                "source_path": "Levels/_maxine_smoke/generated/generated.prefab",
                "source_uuid": "33333333333343338333333333333333",
                "source_sub_id": "12",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            },
            {
                "product_type": "spawnable",
                "product_path": "pc/prefabs/basic.spawnable",
                "source_path": "Prefabs/Basic.prefab",
                "source_uuid": "44444444444444448444444444444444",
                "source_sub_id": "23",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            },
        ],
    )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_character_spawnable_surface=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_character_spawnable_surface_diagnostic"
    assert report["runtime_character_spawnable_surface_status"] == "runtime_character_spawnable_surface_generation_required"
    assert report["runtime_character_spawnable_surface_source_validation"] == "runtime_character_spawnable_surface_source_discovery_pass"
    assert report["runtime_character_spawnable_surface_search_status"] == "approved_character_runtime_spawnable_surface_missing"
    assert report["runtime_character_spawnable_surface_candidate_matrix_recorded"] is True
    rejected = {
        candidate["product_path"]: candidate["rejected_reason"]
        for candidate in report["runtime_character_spawnable_surface_candidates"]
    }
    assert rejected["pc/levels/defaultlevel/defaultlevel.spawnable"] == (
        "runtime_character_spawnable_surface_candidate_rejected_defaultlevel_spawnable"
    )
    assert rejected["pc/levels/_maxine_smoke/generated/generated.spawnable"] == (
        "runtime_character_spawnable_surface_candidate_rejected_level_spawnable"
    )
    assert rejected["pc/prefabs/basic.spawnable"] == (
        "runtime_character_spawnable_surface_candidate_rejected_not_character_specific"
    )
    assert report["runtime_character_spawnable_surface_found"] is False
    assert report["runtime_character_spawnable_surface_claimed"] is False
    assert report["runtime_character_spawnable_surface_verified"] is False
    assert report["runtime_character_spawnable_surface_generation_required"] is True
    assert report["runtime_character_spawnable_surface_generation_blocker"] == (
        "blocked_by_runtime_character_spawnable_generation_required"
    )
    assert report["runtime_character_product_load_runtime_equivalent_surface_kind"] == "approved_character_spawnable"
    assert report["runtime_character_product_load_verified"] is False
    assert report["runtime_character_product_load_claimed"] is False
    assert report["runtime_character_instantiation_claimed"] is False
    assert report["runtime_character_animation_claimed"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_character_spawnable_surface_diagnostic_selects_approved_candidate_without_spawn_claim(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    _enable_fixture_gem(project)
    _append_apb_products(
        apb,
        [
            {
                "product_type": "spawnable",
                "product_path": "pc/assets/characters/maxine/release/maxine_character.spawnable",
                "source_path": "Assets/Characters/Maxine/Release/maxine_character.prefab",
                "source_uuid": "55555555555545558555555555555555",
                "source_sub_id": "34",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            }
        ],
    )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_character_spawnable_surface=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_character_spawnable_surface_status"] == "runtime_character_spawnable_surface_found"
    assert report["runtime_character_spawnable_surface_search_status"] == "approved_character_runtime_spawnable_surface_found"
    assert report["runtime_character_spawnable_surface_found"] is True
    assert report["runtime_character_spawnable_surface_selected"] == "pc/assets/characters/maxine/release/maxine_character.spawnable"
    selected = report["runtime_character_spawnable_surface_candidates"][0]
    assert selected["is_character_specific"] is True
    assert selected["is_approved"] is True
    assert selected["asset_id"] == "{55555555-5555-4555-8555-555555555555}:00000022"
    assert selected["asset_type"] == "{855E3021-D305-4845-B284-20C3F7FDF16B}"
    assert selected["handler_status"] == "runtime_character_spawnable_asset_handler_source_validated"
    assert selected["runtime_api"] == "AZ::Data::AssetManager::GetAsset<AzFramework::Spawnable>"
    assert selected["attempted"] is False
    assert selected["result"] == "runtime_character_spawnable_surface_found_load_not_attempted"
    assert report["runtime_character_spawnable_surface_claimed"] is False
    assert report["runtime_character_spawnable_surface_verified"] is False
    assert report["runtime_character_instantiation_claimed"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_character_prefab_source_diagnostic_reports_repo_owned_source_and_missing_apb_product(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    _enable_fixture_gem(project)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_character_prefab_source=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_character_prefab_source_diagnostic"
    assert report["runtime_character_prefab_source_status"] == "runtime_character_prefab_source_apb_product_missing"
    assert report["runtime_character_prefab_source_path"] == (
        "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
    )
    assert report["runtime_character_prefab_source_kind"] == "reviewed_character_prefab_source"
    assert report["runtime_character_prefab_source_owned_by_repo"] is True
    assert report["runtime_character_prefab_source_committed"] is True
    assert report["runtime_character_prefab_source_is_defaultlevel"] is False
    assert report["runtime_character_prefab_source_is_production_level"] is False
    assert report["runtime_character_prefab_source_is_temp"] is False
    assert report["runtime_character_prefab_source_is_generic_transform_only"] is False
    assert report["runtime_character_prefab_source_is_character_specific"] is True
    assert report["runtime_character_prefab_source_is_approved"] is True
    assert report["runtime_character_prefab_source_generation_strategy"] == (
        "repo_owned_reviewed_prefab_source_referencing_approved_release_procprefab"
    )
    assert report["runtime_character_prefab_source_generation_source_validation"] == (
        "runtime_character_prefab_source_source_discovery_pass"
    )
    source_refs = " ".join(report["runtime_character_prefab_source_generation_source_refs"])
    assert "PrefabBuilderComponent.cpp" in source_refs
    assert "SpawnableUtils.cpp" in source_refs
    assert "release_rigged.prefab" in source_refs
    assert report["runtime_character_prefab_source_apb_expected_product"] == (
        "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable"
    )
    assert report["runtime_character_prefab_source_apb_product_found"] is False
    assert report["runtime_character_prefab_source_apb_product_status"] == (
        "runtime_character_prefab_source_apb_product_missing"
    )
    assert report["runtime_character_spawnable_surface_generation_required"] is True
    assert report["runtime_character_spawnable_surface_generation_completed"] is False
    assert report["runtime_character_spawnable_surface_claimed"] is False
    assert report["runtime_character_spawnable_surface_verified"] is False
    assert report["runtime_character_product_load_claimed"] is False
    assert report["runtime_character_product_load_verified"] is False
    assert report["runtime_character_instantiation_claimed"] is False
    assert report["runtime_character_animation_claimed"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_character_prefab_source_diagnostic_records_generated_spawnable_without_load_claim(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    _enable_fixture_gem(project)
    _append_apb_products(
        apb,
        [
            {
                "product_type": "spawnable",
                "product_path": "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable",
                "source_path": "Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "source_uuid": "66666666666646668666666666666666",
                "source_sub_id": "45",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            }
        ],
    )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_character_prefab_source=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
    )

    assert report["status"] == "pass"
    assert report["runtime_character_prefab_source_status"] == "runtime_character_prefab_source_apb_product_found"
    assert report["runtime_character_prefab_source_apb_product_found"] is True
    assert report["runtime_character_prefab_source_apb_product_path"] == (
        "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable"
    )
    assert report["runtime_character_prefab_source_apb_product_asset_id"] == (
        "{66666666-6666-4666-8666-666666666666}:0000002d"
    )
    assert report["runtime_character_prefab_source_apb_product_asset_type"] == "{855E3021-D305-4845-B284-20C3F7FDF16B}"
    assert report["runtime_character_prefab_source_apb_product_builder"] == "Prefabs"
    assert report["runtime_character_spawnable_surface_status"] == "runtime_character_spawnable_surface_found"
    assert report["runtime_character_spawnable_surface_found"] is True
    assert report["runtime_character_spawnable_surface_selected"] == (
        "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable"
    )
    assert report["runtime_character_spawnable_surface_generation_required"] is False
    assert report["runtime_character_spawnable_surface_generation_completed"] is True
    assert report["runtime_character_spawnable_surface_generation_source_changes"] == [
        "examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab"
    ]
    assert report["runtime_character_spawnable_surface_claimed"] is False
    assert report["runtime_character_spawnable_surface_verified"] is False
    assert report["runtime_character_product_load_claimed"] is False
    assert report["runtime_character_product_load_verified"] is False
    assert report["runtime_character_instantiation_claimed"] is False
    assert report["runtime_character_animation_claimed"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_validation_rejects_approved_prefab_source_for_defaultlevel_or_transform_only() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_character_prefab_source_status": "runtime_character_prefab_source_committed",
            "runtime_character_prefab_source_path": "Levels/defaultlevel/defaultlevel.prefab",
            "runtime_character_prefab_source_owned_by_repo": True,
            "runtime_character_prefab_source_committed": True,
            "runtime_character_prefab_source_is_defaultlevel": True,
            "runtime_character_prefab_source_is_production_level": False,
            "runtime_character_prefab_source_is_temp": False,
            "runtime_character_prefab_source_is_generic_transform_only": True,
            "runtime_character_prefab_source_is_character_specific": False,
            "runtime_character_prefab_source_is_approved": True,
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_character_prefab_source_is_approved=true cannot use defaultlevel" in message for message in result.messages)
    assert any("runtime_character_prefab_source_is_approved=true cannot be generic Transform-only content" in message for message in result.messages)


def test_runtime_harness_validation_rejects_character_spawnable_surface_claim_without_verified_surface() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_character_spawnable_surface_claimed": True,
            "runtime_character_spawnable_surface_verified": False,
            "runtime_character_spawnable_surface_selected": "pc/assets/characters/maxine/release/maxine_character.spawnable",
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_character_spawnable_surface_claimed=true requires verified approved surface" in message for message in result.messages)


def test_runtime_harness_validation_rejects_product_load_claim_without_approved_character_spawnable_surface() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_character_product_load_verified": True,
            "runtime_character_product_load_claimed": True,
            "runtime_character_product_load_contract_updated": True,
            "runtime_character_product_load_direct_procprefab_required": False,
            "runtime_character_product_load_runtime_equivalent_required": True,
            "runtime_character_product_load_runtime_equivalent_surface_kind": "approved_character_spawnable",
            "runtime_procprefab_runtime_equivalent_surface_verified": True,
            "runtime_character_spawnable_surface_verified": False,
            "runtime_character_product_load_selected_strategy": "runtime_character_product_load_generic_assetmanager_load",
            "runtime_character_product_load_source_refs": ["C:/src/o3de/Code/Framework/AzCore/AzCore/Asset/AssetManager.h"],
            "runtime_character_product_load_required_products_complete": True,
            "runtime_character_product_load_all_required_ready": True,
            "runtime_character_product_load_products": [
                {
                    "product_kind": "actor",
                    "product_path": "pc/assets/characters/maxine/release/jack.actor",
                    "catalog_path": "assets/characters/maxine/release/jack.actor",
                    "asset_id": "{7E3BE43C-A0C7-512B-9F3E-FA6C2A4DBDAC}:914f19b7",
                    "ready": True,
                }
            ],
            "runtime_execution_verified": True,
            "runtime_exit_fixture_execution_verified": True,
            "runtime_launch_hygiene_status": "runtime_launch_hygiene_pass",
            "runtime_signal_classification_verified": True,
            "runtime_cache_bootstrap_verified": True,
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any(
        "runtime_character_product_load_verified=true requires verified approved runtime character spawnable surface"
        in message
        for message in result.messages
    )


def test_runtime_harness_validation_rejects_direct_procprefab_claim_with_missing_handler() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_procprefab_direct_load_claimed": True,
            "runtime_procprefab_direct_load_verified": True,
            "runtime_procprefab_direct_load_handler_status": "runtime_procprefab_direct_load_handler_missing",
            "runtime_procprefab_direct_load_asset_id": "{794D1588-3C41-5795-8A9A-EEBD6A663A60}:11695305",
            "runtime_procprefab_direct_load_asset_type": "{9B7C8459-471E-4EAD-A363-7990CC4065A9}",
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_procprefab_direct_load_verified=true requires a registered runtime handler" in message for message in result.messages)


def test_runtime_harness_validation_rejects_updated_product_load_contract_without_equivalent_surface() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_character_product_load_verified": True,
            "runtime_character_product_load_claimed": True,
            "runtime_character_product_load_contract_updated": True,
            "runtime_character_product_load_direct_procprefab_required": False,
            "runtime_character_product_load_runtime_equivalent_required": True,
            "runtime_procprefab_runtime_equivalent_surface_verified": False,
            "runtime_character_product_load_selected_strategy": "runtime_character_product_load_generic_assetmanager_load",
            "runtime_character_product_load_source_refs": ["C:/src/o3de/Code/Framework/AzCore/AzCore/Asset/AssetManager.h"],
            "runtime_character_product_load_required_products_complete": True,
            "runtime_character_product_load_all_required_ready": True,
            "runtime_character_product_load_products": [
                {
                    "product_kind": "actor",
                    "product_path": "pc/assets/characters/maxine/release/jack.actor",
                    "catalog_path": "assets/characters/maxine/release/jack.actor",
                    "asset_id": "{7E3BE43C-A0C7-512B-9F3E-FA6C2A4DBDAC}:914f19b7",
                    "ready": True,
                }
            ],
            "runtime_execution_verified": True,
            "runtime_exit_fixture_execution_verified": True,
            "runtime_launch_hygiene_status": "runtime_launch_hygiene_pass",
            "runtime_signal_classification_verified": True,
            "runtime_cache_bootstrap_verified": True,
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("updated product-load contract requires verified runtime-equivalent prefab/spawnable surface" in message for message in result.messages)


def test_runtime_fixture_product_load_registry_reads_do_not_accumulate_values() -> None:
    source = (
        Path("o3de/gems/MaxineRuntimeExitFixture/Code/Source/Clients/MaxineRuntimeExitFixtureSystemComponent.cpp")
        .read_text(encoding="utf-8")
    )

    assert "ReadProductProbeValue" in source
    assert "CharacterProductLoadProbeProductSpecsKey" in source
    assert "CharacterProductLoadProbeProductSpecsHexKey" in source
    assert "DecodeProductLoadSpecHex" in source
    assert "SplitProductLoadSpec" in source
    assert 'entry.m_kind = ReadProductProbeValue("Kind");' in source
    assert 'entry.m_productPath = ReadProductProbeValue("ProductPath");' in source
    assert 'entry.m_catalogPath = ReadProductProbeValue("CatalogPath");' in source
    assert 'entry.m_expectedCategory = ReadProductProbeValue("ExpectedCategory");' in source


def test_runtime_fixture_spawn_instantiation_probe_is_gated_and_uses_spawnable_entities_interface() -> None:
    source = (
        Path("o3de/gems/MaxineRuntimeExitFixture/Code/Source/Clients/MaxineRuntimeExitFixtureSystemComponent.cpp")
        .read_text(encoding="utf-8")
    )
    header = (
        Path("o3de/gems/MaxineRuntimeExitFixture/Code/Source/Clients/MaxineRuntimeExitFixtureSystemComponent.h")
        .read_text(encoding="utf-8")
    )

    assert "EnableCharacterSpawnInstantiationProbeKey" in source
    assert "CharacterSpawnInstantiationProbeSpawnableCatalogPathKey" in source
    assert "AzFramework::SpawnableEntitiesInterface::Get()" in source
    assert "SpawnAllEntities(m_characterSpawnTicket" in source
    assert "DespawnAllEntities" in source
    assert "GameEntityContextRequestBus::BroadcastResult" in source
    assert "MAXINE_RUNTIME_CHARACTER_SPAWN_REQUESTED" in source
    assert "MAXINE_RUNTIME_CHARACTER_SPAWN_COMPLETED" in source
    assert "MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY" in source
    assert "MAXINE_RUNTIME_CHARACTER_SPAWN_CLEANUP" in source
    assert "MAXINE_RUNTIME_CHARACTER_SPAWN_SUMMARY" in source
    assert "m_characterSpawnProbeEnabled = false" in header
    assert "m_characterSpawnTicket" in header


def test_runtime_harness_character_product_load_fixture_requires_probe_gate(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION"] = "1"
    _enable_fixture_gem(project)
    _write_defaultlevel_bootstrap(project)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_character_product_load_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=180,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_runtime_character_product_load_probe_gate_missing"
    assert report["runtime_character_product_load_status"] == "blocked_by_runtime_character_product_load_probe_gate_missing"
    assert report["runtime_character_product_load_probe_enabled"] is False
    assert report["runtime_exit_fixture_execution_attempted"] is False
    assert report["runtime_character_product_load_claimed"] is False
    assert report["runtime_character_product_load_verified"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_character_product_load_fixture_requires_temp_registry_patch_gate(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION"] = "1"
    _enable_fixture_gem(project)
    _write_defaultlevel_bootstrap(project)

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_character_product_load_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=180,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_fixture_temp_registry_patch_gate_missing"
    assert report["runtime_character_product_load_status"] == "blocked_by_fixture_temp_registry_patch_gate_missing"
    assert report["runtime_execution_attempted"] is False
    assert not (tmp_path / "artifacts" / runtime_harness.RUNTIME_CHARACTER_PRODUCT_LOAD_PATCH_FILENAME).exists()


def test_runtime_harness_character_product_load_fixture_records_all_products_ready_without_character_proof(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH"] = "1"
    _enable_fixture_gem(project)
    source, bootstrap, original_source, original_bootstrap = _write_defaultlevel_bootstrap(project)
    _append_apb_products(
        apb,
        [
            {
                "product_type": "spawnable",
                "product_path": "pc/assets/characters/maxine/release/maxine_character.spawnable",
                "source_path": "Assets/Characters/Maxine/Release/maxine_character.prefab",
                "source_uuid": "55555555555545558555555555555555",
                "source_sub_id": "45",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            }
        ],
    )
    products = runtime_harness._runtime_character_product_load_products_from_apb(
        runtime_harness._product_evidence_from_apb(apb),
        project=project,
        engine_root=engine,
    )

    def runner(argv, **kwargs):
        marker_lines = ["MAXINE_RUNTIME_PRODUCT_LOAD_START count=8 timeout_ticks=120 require_all=true"]
        for index, product in enumerate(products):
            marker_lines.extend(
                [
                    (
                        f"MAXINE_RUNTIME_PRODUCT_LOAD_RESOLVED index={index} kind={product['product_kind']} "
                        f"path={product['product_path']} catalog_path={product['catalog_path']} "
                        f"asset_id={{11111111-1111-4111-8111-111111111111}}:{index + 1} "
                        f"asset_type={{22222222-2222-4222-8222-222222222222}} asset_type_name=runtime_catalog_asset_type"
                    ),
                    f"MAXINE_RUNTIME_PRODUCT_LOAD_READY index={index} kind={product['product_kind']} path={product['product_path']} status=ready",
                    f"MAXINE_RUNTIME_PRODUCT_LOAD_RELEASED index={index} kind={product['product_kind']} path={product['product_path']} status=released",
                ]
            )
        marker_lines.append("MAXINE_RUNTIME_PRODUCT_LOAD_SUMMARY status=pass required=8 ready=8 failed=0 timed_out=0")
        prefixed_marker_lines = [
            f"<12:38:04> (MaxineRuntimeExitFixture) - {line}" for line in marker_lines
        ]
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "Launcher: Connecting to Asset Processor...\n"
                "AssetProcessorConnection::ConnectThread: Network connection attempt failure, negotiation with 127.0.0.1:45643 failed.\n"
                "GAME: Negotiation with asset processor failed\n"
                "<12:38:04> [Error] (Serialize) - Element 'NULL'(0x41405e39) with class ID "
                "'{1BAEE536-96CA-4AEB-BA73-D5D72EE35B45}' found in 'AZStd::intrusive_ptr<ShaderStageFunction>' "
                "is not registered with the serializer!\n"
                "<12:38:04> [Error] (Serialize) - Element 'NULL'(0x41405e39) with class ID "
                "'{A606478A-97E9-402D-A776-88EE72DAC6F9}' found in 'AZStd::intrusive_ptr<ShaderStageFunction>' "
                "is not registered with the serializer!\n"
                "<12:38:04> [Error] (Serialize) - Element 'NULL'(0x41405e39) with class ID "
                "'{A10B0F03-F43D-4462-9306-66195B4EFC46}' found in 'AZStd::intrusive_ptr<PipelineLayoutDescriptor>' "
                "is not registered with the serializer!\n"
                + "\n".join(prefixed_marker_lines)
                + "\nMAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=5\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_character_product_load_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=180,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_character_product_load_fixture_command"
    assert report["runtime_exit_fixture_runtime_command_uses_product_load_probe"] is True
    command_text = " ".join(report["runtime_exit_fixture_runtime_command"])
    assert f"--regset-file={tmp_path / 'artifacts' / runtime_harness.RUNTIME_CHARACTER_PRODUCT_LOAD_PATCH_FILENAME}" in command_text
    assert "/CharacterProductLoadProbe/Products/0/ProductPath=" not in command_text
    patch = json.loads(
        (tmp_path / "artifacts" / runtime_harness.RUNTIME_CHARACTER_PRODUCT_LOAD_PATCH_FILENAME).read_text(encoding="utf-8")
    )
    probe = patch["Amazon"]["MAXINE"]["RuntimeHarness"]["CharacterProductLoadProbe"]
    assert probe["ProductCount"] == 8
    assert probe["Products"]["0"]["ProductPath"] == products[0]["product_path"]
    assert probe["Products"]["7"]["CatalogPath"] == products[7]["catalog_path"]
    assert probe["TimeoutTicks"] == 3600
    assert report["runtime_character_product_load_status"] == "runtime_character_product_load_verified_all_required_products_ready"
    assert report["runtime_character_product_load_claimed"] is True
    assert report["runtime_character_product_load_verified"] is True
    assert report["runtime_character_product_load_all_required_ready"] is True
    assert report["runtime_character_product_load_required_products_complete"] is True
    assert report["runtime_character_product_load_missing_products"] == []
    assert report["runtime_character_product_load_timed_out_products"] == []
    assert report["runtime_character_product_load_failed_products"] == []
    assert len(report["runtime_character_product_load_products"]) == 8
    assert [product["product_kind"] for product in report["runtime_character_product_load_products"]] == list(
        runtime_harness.RUNTIME_CHARACTER_PRODUCT_LOAD_UPDATED_REQUIRED_PRODUCTS
    )
    assert report["runtime_character_spawnable_surface_verified"] is True
    assert report["runtime_character_spawnable_surface_load_ready"] is True
    assert report["runtime_procprefab_runtime_equivalent_surface_verified"] is True
    assert all(product["ready"] is True for product in report["runtime_character_product_load_products"])
    assert all(product["load_requested"] is True for product in report["runtime_character_product_load_products"])
    assert all(product["release_status"] == "runtime_character_product_load_product_released" for product in report["runtime_character_product_load_products"])
    assert report["runtime_signal_classification_verified"] is True
    assert report["runtime_cache_bootstrap_verified"] is True
    assert report["runtime_exit_fixture_execution_verified"] is True
    assert report["runtime_execution_verified"] is True
    assert report["runtime_default_level_autoload_detected"] is False
    assert report["runtime_production_level_loaded"] is False
    assert report["runtime_character_product_load_is_instantiation_proof"] is False
    assert report["runtime_character_instantiation_claimed"] is False
    assert report["runtime_character_instantiation_verified"] is False
    assert report["runtime_character_animation_claimed"] is False
    assert report["runtime_character_animation_verified"] is False
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_character_proof_verified"] is False
    assert source.exists()
    assert source.read_text(encoding="utf-8") == original_source
    assert bootstrap.read_text(encoding="utf-8") == original_bootstrap
    assert report["asset_cache_deleted"] is False


def test_runtime_harness_character_spawn_instantiation_diagnostic_records_source_validation_without_claim(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    _append_apb_products(
        apb,
        [
            {
                "product_type": "spawnable",
                "product_path": "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable",
                "source_path": "Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "source_uuid": "55555555555545558555555555555555",
                "source_sub_id": "0xf6ec8847",
                "asset_id": "{CFCA52C7-573E-579E-97E0-707122217DA0}:f6ec8847",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            }
        ],
    )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        diagnose_runtime_character_spawn_instantiation=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=180,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_character_spawn_instantiation_diagnostic"
    assert report["runtime_character_spawn_instantiation_status"] == "runtime_character_spawn_source_discovery_pass"
    assert report["runtime_character_spawn_instantiation_source_validation"] == "runtime_character_spawn_source_discovery_pass"
    source_refs = " ".join(report["runtime_character_spawn_instantiation_source_refs"])
    assert "SpawnableEntitiesInterface.h" in source_refs
    assert "SpawnableEntitiesManager.cpp" in source_refs
    assert "GameEntityContextBus.h" in source_refs
    assert "SpawnableScriptMediator.cpp" in source_refs
    assert report["runtime_character_spawn_instantiation_api"] == "AzFramework::SpawnableEntitiesInterface::SpawnAllEntities"
    assert report["runtime_character_spawn_instantiation_api_argument_shape"]["ticket"] == (
        "AzFramework::EntitySpawnTicket(AZ::Data::Asset<AzFramework::Spawnable>)"
    )
    assert report["runtime_character_spawn_instantiation_context_status"] == "runtime_character_spawn_context_source_validated"
    assert report["runtime_character_spawn_instantiation_spawnable_product_path"] == (
        "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable"
    )
    assert report["runtime_character_spawn_instantiation_spawnable_loaded_ready"] is False
    assert report["runtime_character_spawn_instantiation_candidate_matrix_recorded"] is True
    assert report["runtime_character_spawn_instantiation_spawn_request_issued"] is False
    assert report["runtime_character_spawn_instantiation_spawn_completion_observed"] is False
    assert report["runtime_character_spawn_instantiation_spawned_entity_count"] == 0
    assert report["runtime_character_spawn_instantiation_claimed"] is False
    assert report["runtime_character_spawn_instantiation_verified"] is False
    assert report["runtime_character_instantiation_claimed"] is False
    assert report["runtime_character_instantiation_verified"] is False
    assert report["runtime_character_animation_claimed"] is False
    assert report["runtime_character_animation_verified"] is False
    assert report["runtime_character_proof_claimed"] is False


def test_runtime_harness_character_spawn_instantiation_fixture_requires_spawn_gate(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH"] = "1"
    _enable_fixture_gem(project)
    _write_defaultlevel_bootstrap(project)
    _append_apb_products(
        apb,
        [
            {
                "product_type": "spawnable",
                "product_path": "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable",
                "source_path": "Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "source_uuid": "55555555555545558555555555555555",
                "source_sub_id": "0xf6ec8847",
                "asset_id": "{CFCA52C7-573E-579E-97E0-707122217DA0}:f6ec8847",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            }
        ],
    )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_character_spawn_instantiation_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=180,
    )

    assert report["status"] == "fail"
    assert report["runtime_harness_status"] == "blocked_by_runtime_character_spawn_instantiation_gate_missing"
    assert report["runtime_character_spawn_instantiation_status"] == (
        "blocked_by_runtime_character_spawn_instantiation_gate_missing"
    )
    assert report["runtime_character_spawn_instantiation_probe_enabled"] is False
    assert report["runtime_exit_fixture_execution_attempted"] is False
    assert report["runtime_character_spawn_instantiation_claimed"] is False
    assert report["runtime_character_instantiation_claimed"] is False


def test_runtime_harness_character_spawn_instantiation_fixture_records_spawned_entities_without_animation_proof(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH"] = "1"
    _enable_fixture_gem(project)
    source, bootstrap, original_source, original_bootstrap = _write_defaultlevel_bootstrap(project)
    _append_apb_products(
        apb,
        [
            {
                "product_type": "spawnable",
                "product_path": "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable",
                "source_path": "Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "source_uuid": "55555555555545558555555555555555",
                "source_sub_id": "0xf6ec8847",
                "asset_id": "{CFCA52C7-573E-579E-97E0-707122217DA0}:f6ec8847",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            }
        ],
    )
    products = runtime_harness._runtime_character_product_load_products_from_apb(
        runtime_harness._product_evidence_from_apb(apb),
        project=project,
        engine_root=engine,
    )

    def runner(argv, **kwargs):
        marker_lines = ["MAXINE_RUNTIME_PRODUCT_LOAD_START count=8 timeout_ticks=120 require_all=true"]
        for index, product in enumerate(products):
            marker_lines.extend(
                [
                    (
                        f"MAXINE_RUNTIME_PRODUCT_LOAD_RESOLVED index={index} kind={product['product_kind']} "
                        f"path={product['product_path']} catalog_path={product['catalog_path']} "
                        f"asset_id={{11111111-1111-4111-8111-111111111111}}:{index + 1} "
                        f"asset_type={{22222222-2222-4222-8222-222222222222}} asset_type_name=runtime_catalog_asset_type"
                    ),
                    f"MAXINE_RUNTIME_PRODUCT_LOAD_READY index={index} kind={product['product_kind']} path={product['product_path']} status=ready",
                    f"MAXINE_RUNTIME_PRODUCT_LOAD_RELEASED index={index} kind={product['product_kind']} path={product['product_path']} status=released",
                ]
            )
        marker_lines.extend(
            [
                "MAXINE_RUNTIME_PRODUCT_LOAD_SUMMARY status=pass required=8 ready=8 failed=0 timed_out=0",
                (
                    "MAXINE_RUNTIME_CHARACTER_SPAWN_START "
                    "product_path=pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable "
                    "catalog_path=assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable "
                    "asset_id={CFCA52C7-573E-579E-97E0-707122217DA0}:f6ec8847 "
                    "asset_type={855E3021-D305-4845-B284-20C3F7FDF16B} timeout_ticks=3600 "
                    "require_positive_entity_count=true cleanup=true"
                ),
                "MAXINE_RUNTIME_CHARACTER_SPAWN_SOURCE_VALIDATED api=AzFramework::SpawnableEntitiesInterface::SpawnAllEntities status=pass",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_CONTEXT status=game_entity_context_available context_id={33333333-3333-4333-8333-333333333333}",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_TICKET ticket=7 valid=true",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_REQUESTED ticket=7 api=AzFramework::SpawnableEntitiesInterface::SpawnAllEntities",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_COMPLETED ticket=7 result=completed entity_count=1",
                (
                    "MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY ticket=7 index=0 "
                    "entity_id={44444444-4444-4444-8444-444444444444} "
                    "name=MAXINE_RuntimeApprovedCharacter component_count=3 "
                    "components={A863EE1B-8CFD-4EDD-BA0D-1CEC2879AD44};{5B9F6A67-5D5B-4C0D-8E8B-ABEF3F1F7D7D};{27F1CAA5-7E06-4D3D-BC50-6611D13F161B}"
                ),
                "MAXINE_RUNTIME_CHARACTER_SPAWN_CLEANUP ticket=7 status=complete",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_SUMMARY status=pass requested=1 completed=1 spawned=1 cleanup=complete timed_out=0",
            ]
        )
        prefixed_marker_lines = [
            f"<12:38:04> (MaxineRuntimeExitFixture) - {line}" for line in marker_lines
        ]
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "Launcher: Connecting to Asset Processor...\n"
                "AssetProcessorConnection::ConnectThread: Network connection attempt failure, negotiation with 127.0.0.1:45643 failed.\n"
                "GAME: Negotiation with asset processor failed\n"
                "<12:38:04> [Error] (Serialize) - Element 'NULL'(0x41405e39) with class ID "
                "'{1BAEE536-96CA-4AEB-BA73-D5D72EE35B45}' found in 'AZStd::intrusive_ptr<ShaderStageFunction>' "
                "is not registered with the serializer!\n"
                + "\n".join(prefixed_marker_lines)
                + "\nMAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=9\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_character_spawn_instantiation_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=180,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_character_spawn_instantiation_fixture_command"
    assert report["runtime_exit_fixture_runtime_command_uses_product_load_probe"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_spawn_instantiation_probe"] is True
    command_text = " ".join(report["runtime_exit_fixture_runtime_command"])
    assert f"--regset-file={tmp_path / 'artifacts' / runtime_harness.RUNTIME_CHARACTER_PRODUCT_LOAD_PATCH_FILENAME}" in command_text
    assert f"--regset-file={tmp_path / 'artifacts' / runtime_harness.RUNTIME_CHARACTER_SPAWN_INSTANTIATION_PATCH_FILENAME}" in command_text
    patch = json.loads(
        (tmp_path / "artifacts" / runtime_harness.RUNTIME_CHARACTER_SPAWN_INSTANTIATION_PATCH_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    probe = patch["Amazon"]["MAXINE"]["RuntimeHarness"]["CharacterSpawnInstantiationProbe"]
    assert probe["SpawnableProductPath"] == "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable"
    assert probe["SpawnableCatalogPath"] == "assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable"
    assert probe["RequirePositiveEntityCount"] is True
    assert report["runtime_character_product_load_verified"] is True
    assert report["runtime_character_spawnable_surface_verified"] is True
    assert report["runtime_character_spawn_instantiation_status"] == "runtime_character_spawn_instantiation_verified"
    assert report["runtime_character_spawn_instantiation_spawn_request_issued"] is True
    assert report["runtime_character_spawn_instantiation_spawn_ticket"] == "7"
    assert report["runtime_character_spawn_instantiation_spawn_completion_observed"] is True
    assert report["runtime_character_spawn_instantiation_spawned_entity_count"] == 1
    assert report["runtime_character_spawn_instantiation_spawned_entity_names"] == ["MAXINE_RuntimeApprovedCharacter"]
    assert report["runtime_character_spawn_instantiation_cleanup_status"] == "runtime_character_spawn_instantiation_cleanup_complete"
    assert report["runtime_character_spawn_instantiation_claimed"] is True
    assert report["runtime_character_spawn_instantiation_verified"] is True
    assert report["runtime_character_instantiation_claimed"] is True
    assert report["runtime_character_instantiation_verified"] is True
    assert report["runtime_character_spawn_instantiation_is_animation_proof"] is False
    assert report["runtime_character_animation_claimed"] is False
    assert report["runtime_character_animation_verified"] is False
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_character_proof_verified"] is False
    assert report["runtime_default_level_autoload_detected"] is False
    assert report["runtime_production_level_loaded"] is False
    assert source.exists()
    assert source.read_text(encoding="utf-8") == original_source
    assert bootstrap.read_text(encoding="utf-8") == original_bootstrap
    assert report["asset_cache_deleted"] is False


def test_runtime_harness_character_animation_playback_surface_fixture_records_missing_surface_blocker(
    tmp_path: Path,
) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)
    _write_animation_source_validation_files(engine)
    env["MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION"] = "1"
    env["MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION"] = "1"
    env["MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH"] = "1"
    _enable_fixture_gem(project)
    source, bootstrap, original_source, original_bootstrap = _write_defaultlevel_bootstrap(project)
    _append_apb_products(
        apb,
        [
            {
                "product_type": "spawnable",
                "product_path": "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable",
                "source_path": "Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab",
                "source_uuid": "55555555555545558555555555555555",
                "source_sub_id": "0xf6ec8847",
                "asset_id": "{CFCA52C7-573E-579E-97E0-707122217DA0}:f6ec8847",
                "asset_type_id": "{855E3021-D305-4845-B284-20C3F7FDF16B}",
                "builder": "Prefabs",
                "status": "ready",
            }
        ],
    )
    products = runtime_harness._runtime_character_product_load_products_from_apb(
        runtime_harness._product_evidence_from_apb(apb),
        project=project,
        engine_root=engine,
    )

    def runner(argv, **kwargs):
        marker_lines = ["MAXINE_RUNTIME_PRODUCT_LOAD_START count=8 timeout_ticks=120 require_all=true"]
        for index, product in enumerate(products):
            marker_lines.extend(
                [
                    (
                        f"MAXINE_RUNTIME_PRODUCT_LOAD_RESOLVED index={index} kind={product['product_kind']} "
                        f"path={product['product_path']} catalog_path={product['catalog_path']} "
                        f"asset_id={{11111111-1111-4111-8111-111111111111}}:{index + 1} "
                        f"asset_type={{22222222-2222-4222-8222-222222222222}} asset_type_name=runtime_catalog_asset_type"
                    ),
                    f"MAXINE_RUNTIME_PRODUCT_LOAD_READY index={index} kind={product['product_kind']} path={product['product_path']} status=ready",
                    f"MAXINE_RUNTIME_PRODUCT_LOAD_RELEASED index={index} kind={product['product_kind']} path={product['product_path']} status=released",
                ]
            )
        marker_lines.extend(
            [
                "MAXINE_RUNTIME_PRODUCT_LOAD_SUMMARY status=pass required=8 ready=8 failed=0 timed_out=0",
                (
                    "MAXINE_RUNTIME_CHARACTER_SPAWN_START "
                    "product_path=pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable "
                    "catalog_path=assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable "
                    "asset_id={CFCA52C7-573E-579E-97E0-707122217DA0}:f6ec8847 "
                    "asset_type={855E3021-D305-4845-B284-20C3F7FDF16B} timeout_ticks=3600 "
                    "require_positive_entity_count=true cleanup=true"
                ),
                "MAXINE_RUNTIME_CHARACTER_SPAWN_SOURCE_VALIDATED api=AzFramework::SpawnableEntitiesInterface::SpawnAllEntities status=pass",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_CONTEXT status=game_entity_context_available context_id={33333333-3333-4333-8333-333333333333}",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_TICKET ticket=1 valid=true",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_REQUESTED ticket=1 api=AzFramework::SpawnableEntitiesInterface::SpawnAllEntities",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_COMPLETED ticket=1 result=completed entity_count=3",
                (
                    "MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY ticket=1 index=0 "
                    "entity_id={44444444-4444-4444-8444-444444444444} "
                    "name=MAXINE_Release_Rigged_Runtime_Character_Source component_count=1 "
                    "components={22B10178-39B6-4C12-BB37-77DB45FDD3B6}"
                ),
                (
                    "MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY ticket=1 index=1 "
                    "entity_id={55555555-5555-4555-8555-555555555555} "
                    "name=maxine_idle_fbx component_count=1 components={22B10178-39B6-4C12-BB37-77DB45FDD3B6}"
                ),
                (
                    "MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY ticket=1 index=2 "
                    "entity_id={66666666-6666-4666-8666-666666666666} "
                    "name=transform component_count=1 components={22B10178-39B6-4C12-BB37-77DB45FDD3B6}"
                ),
                "MAXINE_RUNTIME_CHARACTER_SPAWN_CLEANUP ticket=1 status=complete",
                "MAXINE_RUNTIME_CHARACTER_SPAWN_SUMMARY status=pass requested=1 completed=1 spawned=3 cleanup=complete timed_out=0",
            ]
        )
        prefixed_marker_lines = [
            f"<12:38:04> (MaxineRuntimeExitFixture) - {line}" for line in marker_lines
        ]
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "Launcher: Connecting to Asset Processor...\n"
                "AssetProcessorConnection::ConnectThread: Network connection attempt failure, negotiation with 127.0.0.1:45643 failed.\n"
                "GAME: Negotiation with asset processor failed\n"
                "<12:38:04> [Error] (Serialize) - Element 'NULL'(0x41405e39) with class ID "
                "'{1BAEE536-96CA-4AEB-BA73-D5D72EE35B45}' found in 'AZStd::intrusive_ptr<ShaderStageFunction>' "
                "is not registered with the serializer!\n"
                + "\n".join(prefixed_marker_lines)
                + "\nMAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=9\n"
            ),
            stderr="",
        )

    report = runtime_harness.run_runtime_harness(
        manifest=runtime_harness.DEFAULT_MANIFEST,
        enable_runtime_character_animation_playback_surface_fixture=True,
        strict_integration=True,
        engine_root=engine,
        project=project,
        apb_report=apb,
        env=env,
        command_runner=runner,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=180,
    )

    assert report["status"] == "pass"
    assert report["runtime_harness_mode"] == "runtime_character_animation_playback_surface_fixture_command"
    assert report["runtime_exit_fixture_runtime_command_uses_product_load_probe"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_spawn_instantiation_probe"] is True
    assert report["runtime_exit_fixture_runtime_command_uses_animation_playback_surface_probe"] is True
    assert report["runtime_character_product_load_verified"] is True
    assert report["runtime_character_spawn_instantiation_verified"] is True
    assert report["runtime_character_animation_spawn_prerequisite_verified"] is True
    assert report["runtime_character_animation_product_load_prerequisite_verified"] is True
    assert report["runtime_character_animation_playback_surface_diagnostic_attempted"] is True
    assert report["runtime_character_animation_playback_surface_diagnostic_completed"] is True
    assert report["runtime_character_animation_playback_surface_found"] is False
    assert report["runtime_character_animation_playback_surface_verified"] is False
    assert report["runtime_character_animation_playback_surface_blocker"] == (
        "runtime_animation_playback_surface_missing_on_approved_spawned_character"
    )
    assert report["runtime_character_animation_actor_component_found"] is False
    assert report["runtime_character_animation_anim_graph_component_found"] is False
    assert report["runtime_character_animation_simple_motion_component_found"] is False
    assert report["runtime_character_animation_actor_instance_found"] is False
    assert report["runtime_character_animation_motion_set_found"] is False
    assert report["runtime_character_animation_anim_graph_instance_found"] is False
    assert report["runtime_character_animation_component_inventory"][0]["entity_name"] == (
        "MAXINE_Release_Rigged_Runtime_Character_Source"
    )
    assert report["runtime_character_animation_component_inventory"][0]["components"][0]["type_id"] == (
        "{22B10178-39B6-4C12-BB37-77DB45FDD3B6}"
    )
    assert any(
        candidate["id"] == "approved_spawnable_runtime_emotionfx_surface"
        and candidate["result"] == "runtime_animation_playback_candidate_blocked_missing_runtime_component_surface"
        for candidate in report["runtime_character_animation_playback_candidate_matrix"]
    )
    assert report["runtime_character_animation_playback_attempted"] is False
    assert report["runtime_character_animation_playback_request_issued"] is False
    assert report["runtime_character_animation_playback_started"] is False
    assert report["runtime_character_animation_playback_observed"] is False
    assert report["runtime_character_animation_playback_tick_count"] == 0
    assert report["runtime_character_animation_playback_cleanup_complete"] is True
    assert report["runtime_character_animation_claimed"] is False
    assert report["runtime_character_animation_verified"] is False
    assert report["runtime_character_animation_is_full_character_proof"] is False
    assert report["runtime_character_proof_claimed"] is False
    assert report["runtime_character_proof_verified"] is False
    assert source.exists()
    assert source.read_text(encoding="utf-8") == original_source
    assert bootstrap.read_text(encoding="utf-8") == original_bootstrap
    assert report["asset_cache_deleted"] is False


def test_runtime_harness_validation_rejects_product_load_verified_without_ready_products() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_character_product_load_verified": True,
            "runtime_character_product_load_claimed": True,
            "runtime_character_product_load_selected_strategy": "runtime_character_product_load_generic_assetmanager_load",
            "runtime_character_product_load_source_refs": ["C:/src/o3de/Code/Framework/AzCore/AzCore/Asset/AssetManager.h"],
            "runtime_character_product_load_required_products_complete": True,
            "runtime_character_product_load_all_required_ready": False,
            "runtime_character_product_load_products": [
                {
                    "product_kind": "actor",
                    "product_path": "pc/assets/characters/maxine/release/jack.actor",
                    "catalog_path": "assets/characters/maxine/release/jack.actor",
                    "resolution_status": "runtime_character_product_load_product_resolved",
                    "load_status": "runtime_character_product_load_product_timeout",
                    "ready": False,
                }
            ],
            "runtime_execution_verified": True,
            "runtime_launch_hygiene_status": "runtime_launch_hygiene_pass",
            "runtime_exit_fixture_execution_verified": True,
            "runtime_signal_classification_verified": True,
            "runtime_cache_bootstrap_verified": True,
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_character_product_load_verified=true requires every required selected product ready" in message for message in result.messages)


def test_runtime_harness_validation_rejects_spawn_claim_without_positive_entity_evidence() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_character_product_load_verified": True,
            "runtime_character_product_load_claimed": True,
            "runtime_character_product_load_selected_strategy": "runtime_character_product_load_generic_assetmanager_load",
            "runtime_character_product_load_source_refs": ["C:/src/o3de/Code/Framework/AzCore/AzCore/Asset/AssetManager.h"],
            "runtime_character_product_load_required_products_complete": True,
            "runtime_character_product_load_all_required_ready": True,
            "runtime_character_product_load_missing_products": [],
            "runtime_character_product_load_timed_out_products": [],
            "runtime_character_product_load_failed_products": [],
            "runtime_character_product_load_products": [
                {
                    "product_kind": "approved_character_spawnable",
                    "product_path": "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable",
                    "catalog_path": "assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable",
                    "asset_id": "{CFCA52C7-573E-579E-97E0-707122217DA0}:f6ec8847",
                    "resolution_status": "runtime_character_product_load_product_resolved",
                    "load_status": "runtime_character_product_load_product_ready",
                    "ready": True,
                }
            ],
            "runtime_character_product_load_contract_updated": True,
            "runtime_character_product_load_runtime_equivalent_required": True,
            "runtime_character_product_load_runtime_equivalent_surface_kind": "approved_character_spawnable",
            "runtime_procprefab_runtime_equivalent_surface_verified": True,
            "runtime_character_spawnable_surface_found": True,
            "runtime_character_spawnable_surface_claimed": True,
            "runtime_character_spawnable_surface_verified": True,
            "runtime_character_spawnable_surface_selected": "pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable",
            "runtime_character_spawn_instantiation_claimed": True,
            "runtime_character_spawn_instantiation_verified": True,
            "runtime_character_instantiation_claimed": True,
            "runtime_character_instantiation_verified": True,
            "runtime_character_spawn_instantiation_source_refs": [
                "C:/src/o3de/Code/Framework/AzFramework/AzFramework/Spawnable/SpawnableEntitiesInterface.h"
            ],
            "runtime_character_spawn_instantiation_api": "AzFramework::SpawnableEntitiesInterface::SpawnAllEntities",
            "runtime_character_spawn_instantiation_spawn_request_issued": True,
            "runtime_character_spawn_instantiation_spawn_completion_observed": True,
            "runtime_character_spawn_instantiation_spawned_entity_count": 0,
            "runtime_character_spawn_instantiation_spawned_entity_ids": [],
            "runtime_character_spawn_instantiation_timeout": False,
            "runtime_character_spawn_instantiation_log_errors": [],
            "runtime_character_spawn_instantiation_cleanup_status": "runtime_character_spawn_instantiation_cleanup_complete",
            "runtime_execution_attempted": True,
            "runtime_execution_completed": True,
            "runtime_execution_status": "runtime_execution_pass",
            "runtime_execution_verified": True,
            "runtime_exit_fixture_execution_attempted": True,
            "runtime_exit_fixture_execution_completed": True,
            "runtime_exit_fixture_execution_verified": True,
            "runtime_exit_fixture_status": "runtime_exit_fixture_verified_clean_exit",
            "runtime_exit_fixture_exit_code_decimal": 0,
            "runtime_launch_hygiene_status": "runtime_launch_hygiene_pass",
            "runtime_signal_classification_verified": True,
            "runtime_signal_classification_selected": "ap_shader_no_defaultlevel_cache_bootstrap_fixture_rerun",
            "runtime_asset_processor_negotiation_source_refs": ["C:/src/o3de/Code/Framework/AzFramework/AzFramework/Asset/AssetSystemComponent.cpp"],
            "runtime_shader_serializer_source_refs": ["C:/src/o3de/Gems/Atom/RHI/Null/Code/Source/RHI.Reflect/ReflectSystemComponent.cpp"],
            "runtime_cache_bootstrap_verified": True,
            "runtime_cache_bootstrap_selected": "cache_bootstrap_setreg_temporarily_neutralized_with_project_source_suppression",
            "runtime_cache_bootstrap_candidate_reversible": True,
            "runtime_cache_bootstrap_candidate_restore_status": "runtime_cache_bootstrap_restore_pass",
            "runtime_cache_bootstrap_candidate_hash_verified": True,
            "runtime_default_level_autoload_detected": False,
            "runtime_production_level_loaded": False,
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_character_spawn_instantiation_verified=true requires positive spawned entity evidence" in message for message in result.messages)


def test_runtime_harness_validation_rejects_animation_verified_without_playback_evidence() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report.update(
        {
            "runtime_character_animation_claimed": True,
            "runtime_character_animation_verified": True,
            "runtime_character_animation_playback_surface_found": True,
            "runtime_character_animation_playback_surface_verified": True,
            "runtime_character_animation_source_refs": [
                "C:/src/o3de/Gems/EMotionFX/Code/Source/Integration/Components/SimpleMotionComponent.cpp"
            ],
            "runtime_character_animation_spawn_prerequisite_verified": True,
            "runtime_character_animation_product_load_prerequisite_verified": True,
            "runtime_character_animation_actor_component_found": True,
            "runtime_character_animation_simple_motion_component_found": True,
            "runtime_character_animation_playback_attempted": True,
            "runtime_character_animation_playback_request_issued": False,
            "runtime_character_animation_playback_started": False,
            "runtime_character_animation_playback_observed": False,
            "runtime_character_animation_playback_tick_count": 0,
            "runtime_character_animation_playback_cleanup_complete": True,
        }
    )

    result = runtime_harness.validate_runtime_harness_report(report)

    assert not result.ok
    assert any("runtime_character_animation_verified=true requires observed playback evidence" in message for message in result.messages)


def test_runtime_character_product_load_selected_errors_match_asset_id_no_handler() -> None:
    products = [
        {
            "product_kind": "procprefab",
            "product_path": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "catalog_path": "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "asset_id": "{794D1588-3C41-5795-8A9A-EEBD6A663A60}:11695305",
        }
    ]
    combined_text = (
        "[Error] (AssetDatabase) - No handler was registered for this asset "
        "(id={794D1588-3C41-5795-8A9A-EEBD6A663A60}:11695305, type={9B7C8459-471E-4EAD-A363-7990CC4065A9})!"
    )

    matches = runtime_harness._runtime_character_product_selected_product_errors(products, combined_text)

    assert matches == [
        {
            "product_kind": "procprefab",
            "product_path": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "catalog_path": "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "line": combined_text,
        }
    ]


def test_runtime_character_product_load_error_marker_preserves_resolved_asset_id() -> None:
    products = [
        {
            "product_kind": "procprefab",
            "product_path": "pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "catalog_path": "assets/characters/maxine/release/maxine_idle_fbx.procprefab",
            "asset_id": "",
            "asset_type_id": "",
            "resolution_status": "runtime_character_product_load_not_attempted",
            "load_status": "runtime_character_product_load_not_attempted",
            "ready": False,
            "timeout": False,
            "error": "",
            "release_status": "runtime_character_product_load_release_not_required",
        }
    ]
    combined_text = (
        "<15:58:07> (MaxineRuntimeExitFixture) - MAXINE_RUNTIME_PRODUCT_LOAD_ERROR index=2 kind=procprefab "
        "path=pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab "
        "catalog_path=assets/characters/maxine/release/maxine_idle_fbx.procprefab "
        "asset_id={794D1588-3C41-5795-8A9A-EEBD6A663A60}:11695305 "
        "asset_type={9B7C8459-471E-4EAD-A363-7990CC4065A9} error=asset_handler_missing"
    )

    parsed, _summary, observed = runtime_harness._runtime_character_product_load_parse_markers(
        products=products,
        combined_text=combined_text,
    )

    assert observed is True
    assert parsed[0]["asset_id"] == "{794D1588-3C41-5795-8A9A-EEBD6A663A60}:11695305"
    assert parsed[0]["asset_type_id"] == "{9B7C8459-471E-4EAD-A363-7990CC4065A9}"
    assert parsed[0]["resolution_status"] == "runtime_character_product_load_product_resolved"
    assert parsed[0]["load_status"] == "runtime_character_product_load_product_error"
    assert parsed[0]["error"] == "asset_handler_missing"
