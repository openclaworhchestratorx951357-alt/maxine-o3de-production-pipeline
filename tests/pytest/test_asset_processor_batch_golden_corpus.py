import json
import os
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


def _fixture(name: str) -> dict:
    return load_json(CORPUS / name / "asset_processor_batch.fixture.json")


def test_asset_processor_batch_report_schema_validates():
    schema = load_json(SCHEMA)
    reports = load_corpus_reports(CORPUS)

    assert reports
    for _, report in reports:
        result = schema_validate(report, schema)
        assert result.status == "pass", result.messages


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
            "--strict-integration",
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode != 0
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout


def test_validate_all_includes_fixture_golden_corpus():
    result = subprocess.run(
        [sys.executable, str(VALIDATE_ALL)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Asset Processor Batch golden corpus" in result.stdout
