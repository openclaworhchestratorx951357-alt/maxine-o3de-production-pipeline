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


def test_runtime_harness_live_mode_records_unpinned_command_without_launch(tmp_path: Path) -> None:
    env, engine, project, apb = _runtime_env(tmp_path, gates=True)

    def _runner(**_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("runtime process must not launch while command is unpinned")

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
    assert report["runtime_harness_status"] == "blocked_by_unpinned_runtime_command"
    assert report["runtime_execution_attempted"] is False
    assert report["runtime_execution_verified"] is False
    assert report["runtime_harness_proof_claimed"] is True
    assert report["runtime_harness_proof_is_character_proof"] is False


def test_runtime_harness_validation_rejects_execution_verified_without_attempt() -> None:
    report = runtime_harness.fixture_runtime_harness_report()
    report["runtime_execution_verified"] = True
    report["runtime_execution_attempted"] = False

    validation = runtime_harness.validate_runtime_harness_report(report, strict=True)

    assert validation.status == "fail"
    assert "MXN_RUNTIME_SMOKE_FAIL" in validation.error_codes
