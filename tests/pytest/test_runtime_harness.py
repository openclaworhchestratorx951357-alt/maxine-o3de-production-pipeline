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
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "IConsole.h",
        engine / "Code" / "Framework" / "AzCore" / "AzCore" / "Console" / "Console.cpp",
        engine / "Code" / "Legacy" / "CrySystem" / "LevelSystem" / "SpawnableLevelSystem.cpp",
    ):
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("source validation fixture\n", encoding="utf-8")
    if launcher:
        (bin_dir / "MAXINE_GoldenCorpus.HeadlessServerLauncher.exe").write_text("runtime placeholder", encoding="utf-8")
    return engine


def _apb_report(root: Path) -> Path:
    report = root / "apb-live" / "asset_processor_batch_live_report.json"
    report.parent.mkdir(parents=True)
    products = [
        {
            "product_type": product_type,
            "product_path": f"pc/assets/characters/maxine/release/maxine.{product_type}",
            "platform": "pc",
            "status": "ready",
            "source_uuid": "11111111111141118111111111111111",
            "source_sub_id": str(index),
            "produced_by_source_uuid": True,
            "evidence_source": "asset_processor_database",
        }
        for index, product_type in enumerate(
            ["azmodel", "actor", "procprefab", "motion", "motionset", "animgraph", "pxmesh", "azmaterial"],
            start=1,
        )
    ]
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
