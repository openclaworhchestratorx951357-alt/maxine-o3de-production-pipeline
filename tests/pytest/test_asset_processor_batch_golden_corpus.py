import json
import os
import sqlite3
import subprocess as subprocess_module
import subprocess
import sys
from pathlib import Path

from tools.o3de.asset_processor_batch import (
    load_corpus_reports,
    run_asset_processor_batch_corpus,
    validate_asset_processor_batch_report,
)
from tools.validation.schema_utils import load_json, schema_validate


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS = REPO_ROOT / "examples" / "golden-corpus"
SCHEMA = REPO_ROOT / "schemas" / "maxine.asset-processor-batch-report.schema.json"
SCRIPT = REPO_ROOT / "tools" / "o3de" / "asset_processor_batch.py"
VALIDATE_ALL = REPO_ROOT / "tools" / "validation" / "validate_all.py"
GOLDEN_PROJECT_FIXTURE = REPO_ROOT / "examples" / "o3de-golden-project" / "maxine-golden-project.fixture.json"
INVALID_GOLDEN_PROJECT_FIXTURE = (
    REPO_ROOT / "examples" / "o3de-golden-project" / "maxine-golden-project.invalid-cache-heuristic.fail.json"
)
FULL_APB_FAILED_EXAMPLE = REPO_ROOT / "examples" / "private-runner" / "apb-live-full-golden-corpus.failed.example.json"


def _fixture(name: str) -> dict:
    return load_json(CORPUS / name / "asset_processor_batch.fixture.json")


def _live_ready_env(tmp_path: Path) -> dict:
    engine_root = tmp_path / "o3de-engine"
    project_path = tmp_path / "MAXINE_GoldenCorpus"
    apb = tmp_path / "AssetProcessorBatch.exe"
    engine_root.mkdir()
    project_path.mkdir()
    (project_path / "project.json").write_text(json.dumps({"project_name": "MAXINE_GoldenCorpus"}), encoding="utf-8")
    apb.write_text("fixture executable placeholder", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env["O3DE_ENGINE_ROOT"] = str(engine_root)
    env["O3DE_PROJECT_PATH"] = str(project_path)
    env["ASSET_PROCESSOR_BATCH_EXECUTABLE"] = str(apb)
    env["MAXINE_ENABLE_O3DE_INTEGRATION"] = "1"
    env["MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"] = "1"
    env["MAXINE_ALLOW_LIVE_O3DE_COMMANDS"] = "1"
    env.pop("MAXINE_ENABLE_O3DE_EDITOR_SMOKE", None)
    env.pop("O3DE_EDITOR_EXECUTABLE", None)
    return env


def _write_asset_db(project_path: Path, product_names: list[str]) -> Path:
    db = project_path / "Cache" / "assetdb.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("create table Sources (SourceID integer primary key, ScanFolderPK integer, SourceName text, SourceGuid blob)")
    con.execute(
        "create table Jobs (JobID integer primary key, SourcePK integer, JobKey text, Fingerprint integer, Platform text, BuilderGuid blob, Status integer, JobRunKey integer, ErrorCount integer, WarningCount integer)"
    )
    con.execute(
        "create table Products (ProductID integer primary key, JobPK integer, ProductName text, SubID integer, AssetType blob, LegacyGuid blob, Hash integer, Flags integer)"
    )
    con.execute(
        "insert into Sources (SourceID, ScanFolderPK, SourceName, SourceGuid) values (1, 1, 'Models/test.fbx', ?)",
        (bytes.fromhex("00112233445566778899aabbccddeeff"),),
    )
    con.execute(
        "insert into Jobs (JobID, SourcePK, JobKey, Fingerprint, Platform, BuilderGuid, Status, JobRunKey, ErrorCount, WarningCount) values (1, 1, 'Scene Builder', 1, 'pc', ?, 4, 1, 0, 0)",
        (bytes.fromhex("ffeeddccbbaa99887766554433221100"),),
    )
    for idx, product_name in enumerate(product_names, start=1):
        con.execute(
            "insert into Products (ProductID, JobPK, ProductName, SubID, AssetType, LegacyGuid, Hash, Flags) values (?, 1, ?, ?, ?, ?, 1, 1)",
            (idx, product_name, idx, b"", b""),
        )
    con.commit()
    con.close()
    return db


class _RecordingRunner:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        return subprocess_module.CompletedProcess(
            argv,
            self.returncode,
            stdout="AssetProcessorBatch fixture stdout\n",
            stderr="AssetProcessorBatch fixture stderr\n" if self.returncode else "",
        )


class _TimeoutRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        raise subprocess_module.TimeoutExpired(argv, kwargs.get("timeout", 1), output="partial stdout", stderr="partial stderr")


def test_asset_processor_batch_report_schema_validates():
    schema = load_json(SCHEMA)
    reports = load_corpus_reports(CORPUS)

    assert reports
    for _, report in reports:
        result = schema_validate(report, schema)
        assert result.status == "pass", result.messages


def test_asset_processor_batch_report_schema_supports_live_fields():
    schema = load_json(SCHEMA)

    for field in [
        "integration_executed",
        "runner_context",
        "golden_project_fixture_ref",
        "command",
        "logs",
        "safety",
        "approved_runtime_character_prefab_source_staging",
    ]:
        assert field in schema["properties"]


def test_asset_processor_batch_fixture_corpus_passes():
    result = run_asset_processor_batch_corpus(CORPUS, mode="fixture")

    assert result["status"] == "pass"
    assert result["mode"] == "fixture"
    assert result["live_asset_processor_batch_execution"] is False
    assert {case["case_id"]: case["observed_status"] for case in result["cases"]}["release_rigged"] == "pass"
    assert {case["case_id"]: case["observed_status"] for case in result["cases"]}["release_rigged_missing_product"] == "fail"


def test_asset_processor_batch_release_missing_product_fails():
    report = _fixture("release_rigged_missing_product")
    result = validate_asset_processor_batch_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_ASSET_PRODUCT_MISSING" in result.error_codes
    assert "actor" in " ".join(result.messages)


def test_asset_processor_batch_release_pending_product_fails():
    report = _fixture("release_rigged_pending_product")
    result = validate_asset_processor_batch_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_ASSET_PRODUCTS_PENDING" in result.error_codes


def test_asset_processor_batch_cache_heuristic_release_fails():
    report = _fixture("release_rigged_cache_heuristic")
    result = validate_asset_processor_batch_report(report, strict=True)

    assert result.status == "fail"
    assert "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" in result.error_codes


def test_asset_processor_batch_integration_gate_off_uses_fixture(monkeypatch):
    monkeypatch.delenv("MAXINE_ENABLE_O3DE_INTEGRATION", raising=False)
    monkeypatch.delenv("MAXINE_ENABLE_ASSET_PROCESSOR_BATCH", raising=False)

    result = run_asset_processor_batch_corpus(CORPUS)

    assert result["mode"] == "fixture"
    assert result["status"] == "pass"
    assert result["integration_enabled"] is False
    assert result["live_asset_processor_batch_execution"] is False


def test_asset_processor_batch_integration_unavailable_skips_non_strict(tmp_path, monkeypatch):
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env.pop("ASSET_PROCESSOR_BATCH", None)
    env["MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"] = "1"

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=False,
        env=env,
    )

    assert result["mode"] == "unavailable"
    assert result["status"] == "skipped"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result["warnings"]
    assert result["live_asset_processor_batch_execution"] is False


def test_asset_processor_batch_integration_unavailable_fails_strict(tmp_path):
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env.pop("ASSET_PROCESSOR_BATCH", None)
    env["MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"] = "1"

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        env=env,
    )

    assert result["mode"] == "unavailable"
    assert result["status"] == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result["errors"]


def test_apb_live_requires_all_gates(tmp_path):
    env = _live_ready_env(tmp_path)
    env.pop("MAXINE_ALLOW_LIVE_O3DE_COMMANDS")
    runner = _RecordingRunner()

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=False,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=runner,
        env=env,
    )

    assert result["status"] == "skipped"
    assert result["mode"] == "unavailable"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result["warnings"]
    assert result["live_asset_processor_batch_execution"] is False
    assert runner.calls == []


def test_apb_live_fails_without_gates_strict(tmp_path):
    env = _live_ready_env(tmp_path)
    env.pop("MAXINE_ALLOW_LIVE_O3DE_COMMANDS")
    runner = _RecordingRunner()

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=runner,
        env=env,
    )

    assert result["status"] == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result["errors"]
    assert result["live_asset_processor_batch_execution"] is False
    assert runner.calls == []


def test_apb_live_rejects_asset_processor_exe_substitute(tmp_path):
    env = _live_ready_env(tmp_path)
    asset_processor = tmp_path / "AssetProcessor.exe"
    asset_processor.write_text("not the batch executable", encoding="utf-8")
    env["ASSET_PROCESSOR_BATCH_EXECUTABLE"] = str(asset_processor)
    runner = _RecordingRunner()

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=runner,
        env=env,
    )

    assert result["status"] == "fail"
    assert result["mode"] == "unavailable"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result["errors"]
    assert result["live_asset_processor_batch_execution"] is False
    assert runner.calls == []


def test_apb_check_local_readiness_passes_when_tools_detected(tmp_path):
    env = _live_ready_env(tmp_path)
    runner = _RecordingRunner()

    result = run_asset_processor_batch_corpus(
        CORPUS,
        check_local_readiness=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=runner,
        env=env,
    )

    assert result["status"] == "pass"
    assert result["live_asset_processor_batch_execution"] is False
    assert runner.calls == []


def test_apb_live_does_not_invoke_editor(tmp_path):
    env = _live_ready_env(tmp_path)
    runner = _RecordingRunner()

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=runner,
        env=env,
    )

    assert result["mode"] == "local_asset_processor_batch"
    assert result["status"] == "pass"
    assert result["integration_executed"] is True
    assert result["live_asset_processor_batch_execution"] is True
    assert result["live_editor_execution"] is False
    assert result["safety"]["live_publication"] is False
    assert len(runner.calls) == 1
    assert not any("Editor" in part or "editor" in part for part in runner.calls[0][0])


def test_apb_live_uses_golden_project_fixture(tmp_path):
    env = _live_ready_env(tmp_path)

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=_RecordingRunner(),
        env=env,
    )

    assert result["golden_project_fixture_ref"].endswith("examples/o3de-golden-project/maxine-golden-project.fixture.json")
    assert any(ref.get("kind") == "o3de_golden_project_fixture" for ref in result["evidence_refs"])


def test_apb_live_stages_approved_runtime_character_prefab_source_when_gate_set(tmp_path):
    env = _live_ready_env(tmp_path)
    env["MAXINE_ALLOW_RUNTIME_CHARACTER_PREFAB_SOURCE_GENERATION"] = "1"
    project_path = Path(env["O3DE_PROJECT_PATH"])
    target = project_path / "Assets" / "Characters" / "MAXINE_GoldenCorpus" / "prefabs" / "release_rigged.prefab"
    runner = _RecordingRunner()

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=runner,
        env=env,
    )

    staging = result["approved_runtime_character_prefab_source_staging"]
    assert result["status"] == "pass"
    assert staging["status"] == "copied"
    assert staging["project_mutation_attempted"] is True
    assert staging["project_mutation_reversible"] is True
    assert staging["defaultlevel_mutation"] is False
    assert staging["production_level_mutation"] is False
    assert target.is_file()
    assert runner.calls


def test_apb_live_refuses_to_overwrite_existing_prefab_source_with_different_hash(tmp_path):
    env = _live_ready_env(tmp_path)
    env["MAXINE_ALLOW_RUNTIME_CHARACTER_PREFAB_SOURCE_GENERATION"] = "1"
    project_path = Path(env["O3DE_PROJECT_PATH"])
    target = project_path / "Assets" / "Characters" / "MAXINE_GoldenCorpus" / "prefabs" / "release_rigged.prefab"
    target.parent.mkdir(parents=True)
    target.write_text("{\"different\": true}\n", encoding="utf-8")
    runner = _RecordingRunner()

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=runner,
        env=env,
    )

    staging = result["approved_runtime_character_prefab_source_staging"]
    assert result["status"] == "fail"
    assert result["live_asset_processor_batch_execution"] is False
    assert staging["status"] == "fail"
    assert staging["project_mutation_attempted"] is False
    assert "refusing to overwrite" in staging["message"]
    assert runner.calls == []


def test_apb_live_rejects_invalid_project_fixture(tmp_path):
    env = _live_ready_env(tmp_path)
    runner = _RecordingRunner()

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=INVALID_GOLDEN_PROJECT_FIXTURE,
        command_runner=runner,
        env=env,
    )

    assert result["status"] == "fail"
    assert result["mode"] == "invalid"
    assert "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" in result["errors"]
    assert result["live_asset_processor_batch_execution"] is False
    assert runner.calls == []


def test_apb_live_generated_outputs_are_under_artifact_root(tmp_path):
    env = _live_ready_env(tmp_path)

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=_RecordingRunner(),
        env=env,
    )

    assert result["logs"]["stdout_log_ref"].startswith("artifacts/o3de-integration/apb/")
    assert result["logs"]["stderr_log_ref"].startswith("artifacts/o3de-integration/apb/")
    assert result["apb_report_ref"].startswith("artifacts/o3de-integration/apb/")
    assert result["asset_processor_log_ref"] == ""


def test_apb_live_nonzero_exit_fails(tmp_path):
    env = _live_ready_env(tmp_path)

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=_RecordingRunner(returncode=2),
        env=env,
    )

    assert result["status"] == "fail"
    assert result["exit_code"] == 2
    assert "MXN_APB_PROCESS_EXIT_NONZERO" in result["errors"]
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" not in result["errors"]
    assert result["live_asset_processor_batch_execution"] is True


def test_apb_live_nonzero_exit_keeps_product_evidence_separate_from_process_failure(tmp_path):
    env = _live_ready_env(tmp_path)
    project_path = Path(env["O3DE_PROJECT_PATH"])
    _write_asset_db(
        project_path,
        [
            "pc/assets/characters/maxine/release/test.azmodel",
            "pc/assets/characters/maxine/release/test.actor",
            "pc/assets/characters/maxine/release/test.procprefab",
            "pc/assets/characters/maxine/release/test.motion",
            "pc/assets/characters/maxine/release/test.motionset",
            "pc/assets/characters/maxine/release/test.animgraph",
            "pc/assets/characters/maxine/release/test.pxmesh",
            "pc/assets/characters/maxine/release/test.azmaterial",
        ],
    )

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=_RecordingRunner(returncode=1),
        env=env,
    )

    assert result["status"] == "fail"
    assert result["exit_code"] == 1
    assert result["missing_products"] == []
    assert "MXN_APB_PROCESS_EXIT_NONZERO" in result["errors"]
    assert "MXN_ASSET_PRODUCT_MISSING" not in result["errors"]


def test_apb_live_records_failed_assets_from_process_output(tmp_path):
    class _FailedAssetRunner(_RecordingRunner):
        def __call__(self, argv, **kwargs):
            proc = super().__call__(argv, **kwargs)
            proc.stdout = (
                "---------------FAILED ASSETS-------------\n"
                "AssetProcessor: C:/src/o3de/Gems/DiffuseProbeGrid/Assets/Passes/DiffuseProbeGridQueryFullscreenWithAlbedo.pass\n"
                "AssetProcessor: -----------------------------------------\n"
                "AssetProcessor: Number of Assets Failed to Process: 1.\n"
                "-----------------------------------------\n"
            )
            return proc

    env = _live_ready_env(tmp_path)

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=_FailedAssetRunner(returncode=1),
        env=env,
    )

    assert result["failed_assets"] == [
        "C:/src/o3de/Gems/DiffuseProbeGrid/Assets/Passes/DiffuseProbeGridQueryFullscreenWithAlbedo.pass"
    ]


def test_apb_live_exit_zero_records_missing_expected_products_from_asset_db(tmp_path):
    env = _live_ready_env(tmp_path)
    project_path = Path(env["O3DE_PROJECT_PATH"])
    _write_asset_db(project_path, ["pc/models/test.azmodel"])

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=_RecordingRunner(),
        env=env,
    )

    assert result["status"] == "fail"
    assert result["exit_code"] == 0
    assert result["produced_products"][0]["product_type"] == "azmodel"
    assert "actor" in result["missing_products"]
    assert "MXN_ASSET_PRODUCT_MISSING" in result["errors"]
    assert result["cache_heuristic_used"] is False


def test_apb_live_full_failed_example_records_missing_products_without_editor_or_publication():
    payload = load_json(FULL_APB_FAILED_EXAMPLE)

    assert payload["status"] == "fail"
    assert payload["live_asset_processor_batch_execution"] is True
    assert payload["live_editor_execution"] is False
    assert payload["live_publication"] is False
    assert payload["cache_heuristic_used"] is False
    assert "MXN_ASSET_PRODUCT_MISSING" in payload["errors"]
    assert {"actor", "motion", "motionset", "animgraph", "pxmesh"} <= set(payload["missing_products"])


def test_apb_live_timeout_records_stalled_status_without_editor_or_publication(tmp_path):
    env = _live_ready_env(tmp_path)
    env["MAXINE_APB_TIMEOUT_SECONDS"] = "1"
    runner = _TimeoutRunner()

    result = run_asset_processor_batch_corpus(
        CORPUS,
        enable_asset_processor_batch=True,
        strict_integration=True,
        golden_project_fixture=GOLDEN_PROJECT_FIXTURE,
        command_runner=runner,
        env=env,
    )

    assert result["status"] == "stalled"
    assert result["timeout_seconds"] == 1
    assert result["exit_code"] is None
    assert "MXN_APB_EXECUTION_STALLED" in result["errors"]
    assert result["live_asset_processor_batch_execution"] is True
    assert result["live_editor_execution"] is False
    assert result["live_publication"] is False
    assert runner.calls[0][1]["timeout"] == 1


def test_asset_processor_batch_cli_fixture_passes():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--corpus", str(CORPUS), "--mode", "fixture"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Asset Processor Batch golden corpus: pass" in result.stdout


def test_asset_processor_batch_cli_strict_integration_fails_when_unavailable(tmp_path):
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env.pop("ASSET_PROCESSOR_BATCH", None)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--corpus",
            str(CORPUS),
            "--enable-asset-processor-batch",
            "--golden-project-fixture",
            str(GOLDEN_PROJECT_FIXTURE),
            "--strict-integration",
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode != 0
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout


def test_asset_processor_batch_cli_non_strict_live_attempt_skips_when_unavailable(tmp_path):
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env.pop("ASSET_PROCESSOR_BATCH", None)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--corpus",
            str(CORPUS),
            "--enable-asset-processor-batch",
            "--golden-project-fixture",
            str(GOLDEN_PROJECT_FIXTURE),
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode == 0
    assert "Asset Processor Batch golden corpus: skipped" in result.stdout
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout
    assert "live_asset_processor_batch_execution: false" in result.stdout


def test_validate_all_includes_fixture_golden_corpus():
    result = subprocess.run(
        [sys.executable, str(VALIDATE_ALL)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Asset Processor Batch golden corpus" in result.stdout
