import json
import subprocess
import sys
from pathlib import Path

from tools.o3de.diagnose_asset_processor_batch import build_diagnostic_report
from tools.validation.schema_utils import load_json, schema_validate


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "o3de" / "diagnose_asset_processor_batch.py"
SCHEMA = REPO_ROOT / "schemas" / "maxine.apb-diagnostic-report.schema.json"
EXAMPLE = REPO_ROOT / "examples" / "private-runner" / "apb-diagnostic.remotecontrolhost-stall.example.json"
BUILD_BLOCKED_EXAMPLE = REPO_ROOT / "examples" / "private-runner" / "apb-diagnostic.project-paired-apb-build-blocked.example.json"
BUILD_PRODUCED_EXAMPLE = REPO_ROOT / "examples" / "private-runner" / "apb-diagnostic.project-paired-apb-produced.example.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _engine(root: Path) -> Path:
    root.mkdir(parents=True)
    _write_json(root / "engine.json", {"engine_name": "o3de", "O3DEVersion": "0.1.0.0"})
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "o3de.bat").write_text("@echo off\n", encoding="utf-8")
    return root


def _project(root: Path, name: str = "MAXINE_GoldenCorpus") -> Path:
    root.mkdir(parents=True)
    _write_json(root / "project.json", {"project_name": name, "engine": "o3de", "engine_version": "4.2.0"})
    return root


def _apb(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fake apb", encoding="utf-8")
    return path


def test_apb_diagnostic_inventory_rejects_asset_processor_exe_substitute(tmp_path):
    engine = _engine(tmp_path / "o3de")
    project = _project(tmp_path / "Projects" / "MAXINE_GoldenCorpus")
    asset_processor = tmp_path / "Projects" / "McpSandbox" / "build" / "windows" / "bin" / "profile" / "AssetProcessor.exe"
    _apb(asset_processor)

    report = build_diagnostic_report(
        search_roots=[tmp_path],
        engine_root=engine,
        project_path=project,
    )

    rejected = {Path(candidate["path"]).name: candidate for candidate in report["rejected_candidates"]}
    assert "AssetProcessor.exe" in rejected
    assert rejected["AssetProcessor.exe"]["is_rejected_asset_processor_substitute"] is True
    assert "AssetProcessor.exe is not AssetProcessorBatch.exe" in rejected["AssetProcessor.exe"]["reason"]


def test_apb_diagnostic_scores_project_paired_apb_over_remotecontrolhost_archive(tmp_path):
    engine = _engine(tmp_path / "o3de")
    project = _project(tmp_path / "Projects" / "MAXINE_GoldenCorpus")
    paired = _apb(project / "build" / "windows" / "bin" / "profile" / "AssetProcessorBatch.exe")
    remote_project = _project(tmp_path / "Projects" / "_archive" / "RemoteControlHost-2026-04-20", "RemoteControlHost")
    remote_apb = _apb(remote_project / "build" / "windows" / "bin" / "profile" / "AssetProcessorBatch.exe")

    report = build_diagnostic_report(
        search_roots=[tmp_path],
        engine_root=engine,
        project_path=project,
    )

    assert report["selected_apb_candidate"]["path"] == str(paired)
    rejected_paths = {candidate["path"] for candidate in report["rejected_candidates"]}
    assert str(remote_apb) in rejected_paths


def test_apb_diagnostic_rejects_remotecontrolhost_archive_when_project_mismatch(tmp_path):
    engine = _engine(tmp_path / "o3de")
    project = _project(tmp_path / "Projects" / "MAXINE_GoldenCorpus")
    remote_project = _project(tmp_path / "Projects" / "_archive" / "RemoteControlHost-2026-04-20", "RemoteControlHost")
    remote_apb = _apb(remote_project / "build" / "windows" / "bin" / "profile" / "AssetProcessorBatch.exe")

    report = build_diagnostic_report(
        search_roots=[tmp_path],
        engine_root=engine,
        project_path=project,
    )

    assert report["selected_apb_candidate"] is None
    rejected = {candidate["path"]: candidate for candidate in report["rejected_candidates"]}
    assert rejected[str(remote_apb)]["remotecontrolhost_archive"] is True
    assert "project_name mismatch" in rejected[str(remote_apb)]["reason"]


def test_apb_bounded_diagnostics_records_timeout_without_live_success(tmp_path):
    engine = _engine(tmp_path / "o3de")
    project = _project(tmp_path / "Projects" / "MAXINE_GoldenCorpus")
    paired = _apb(project / "build" / "windows" / "bin" / "profile" / "AssetProcessorBatch.exe")

    def stalled_runner(**kwargs):
        return {
            "label": kwargs["label"],
            "argv": kwargs["argv"],
            "cwd": kwargs["cwd"],
            "status": "stalled",
            "exit_code": None,
            "duration_seconds": kwargs["timeout_seconds"],
            "timeout_seconds": kwargs["timeout_seconds"],
            "termination_reason": "timeout",
            "process_cleanup": {"attempted": True, "method": "test-runner"},
            "stdout_log_ref": "",
            "stderr_log_ref": "",
            "errors": ["MXN_APB_DIAGNOSTIC_STALLED"],
            "warnings": [],
        }

    report = build_diagnostic_report(
        search_roots=[tmp_path],
        engine_root=engine,
        project_path=project,
        candidate=paired,
        run_bounded_diagnostics=True,
        timeout_seconds=2,
        command_runner=stalled_runner,
    )

    assert report["status"] == "stalled"
    assert report["stall_detected"] is True
    assert report["live_asset_processor_batch_execution"] is False
    assert report["live_editor_execution"] is False
    assert report["command_matrix"][0]["process_cleanup"]["attempted"] is True


def test_apb_bounded_diagnostics_tolerates_responsive_unsupported_help(tmp_path):
    engine = _engine(tmp_path / "o3de")
    project = _project(tmp_path / "Projects" / "MAXINE_GoldenCorpus")
    paired = _apb(engine / "build" / "windows" / "bin" / "profile" / "AssetProcessorBatch.exe")

    def responsive_runner(**kwargs):
        if kwargs["label"] == "candidate_help":
            return {
                "label": kwargs["label"],
                "argv": kwargs["argv"],
                "cwd": kwargs["cwd"],
                "status": "fail",
                "exit_code": 1,
                "duration_seconds": 0.5,
                "timeout_seconds": kwargs["timeout_seconds"],
                "termination_reason": "exited",
                "process_cleanup": {"attempted": False, "method": "", "return_code": None},
                "stdout_log_ref": "",
                "stderr_log_ref": "",
                "errors": ["MXN_VALIDATION_TOOL_UNAVAILABLE"],
                "warnings": [],
            }
        return {
            "label": kwargs["label"],
            "argv": kwargs["argv"],
            "cwd": kwargs["cwd"],
            "status": "pass",
            "exit_code": 0,
            "duration_seconds": 0.5,
            "timeout_seconds": kwargs["timeout_seconds"],
            "termination_reason": "exited",
            "process_cleanup": {"attempted": False, "method": "", "return_code": None},
            "stdout_log_ref": "",
            "stderr_log_ref": "",
            "errors": [],
            "warnings": [],
        }

    report = build_diagnostic_report(
        search_roots=[tmp_path],
        engine_root=engine,
        project_path=project,
        candidate=paired,
        run_bounded_diagnostics=True,
        timeout_seconds=2,
        command_runner=responsive_runner,
    )

    assert report["status"] == "pass"
    help_command = report["command_matrix"][0]
    assert help_command["label"] == "candidate_help"
    assert help_command["status"] == "pass"
    assert help_command["diagnostic_result"] == "responsive_nonzero_tolerated"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in help_command["warnings"]
    assert report["live_asset_processor_batch_execution"] is False
    assert report["live_editor_execution"] is False


def test_apb_diagnostic_report_schema_validates_example():
    result = schema_validate(load_json(EXAMPLE), load_json(SCHEMA))

    assert result.status == "pass", result.messages


def test_apb_diagnostic_report_schema_validates_project_paired_build_blocker_example():
    payload = load_json(BUILD_BLOCKED_EXAMPLE)
    result = schema_validate(payload, load_json(SCHEMA))

    assert result.status == "pass", result.messages
    assert payload["project_paired_apb_found"] is False
    assert payload["project_paired_apb_built"] is False
    assert payload["build_attempted"] is True
    assert payload["live_asset_processor_batch_execution"] is False


def test_apb_diagnostic_report_schema_validates_project_paired_build_produced_example():
    payload = load_json(BUILD_PRODUCED_EXAMPLE)
    result = schema_validate(payload, load_json(SCHEMA))

    assert result.status == "pass", result.messages
    assert payload["project_paired_apb_found"] is True
    assert payload["project_paired_apb_built"] is True
    assert payload["build_result"] == "success"
    assert payload["live_asset_processor_batch_execution"] is False
    assert payload["live_editor_execution"] is False


def test_apb_diagnostic_cli_inventory_json_uses_search_root(tmp_path):
    engine = _engine(tmp_path / "o3de")
    project = _project(tmp_path / "Projects" / "MAXINE_GoldenCorpus")
    paired = _apb(project / "build" / "windows" / "bin" / "profile" / "AssetProcessorBatch.exe")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--inventory",
            "--json",
            "--search-root",
            str(tmp_path),
            "--engine-root",
            str(engine),
            "--project",
            str(project),
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["selected_apb_candidate"]["path"] == str(paired)
    assert payload["live_asset_processor_batch_execution"] is False
