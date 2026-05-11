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
