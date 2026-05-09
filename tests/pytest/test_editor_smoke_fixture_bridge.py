import json
import os
import subprocess
import sys
from pathlib import Path

from tools.o3de.editor_smoke import (
    load_fixture_reports,
    run_editor_smoke_corpus,
    validate_editor_smoke_report,
)
from tools.validation.schema_utils import load_json, schema_validate


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS = REPO_ROOT / "examples" / "editor-smoke"
SCHEMA = REPO_ROOT / "schemas" / "maxine.editor-smoke-report.schema.json"
SCRIPT = REPO_ROOT / "tools" / "o3de" / "editor_smoke.py"
VALIDATE_ALL = REPO_ROOT / "tools" / "validation" / "validate_all.py"


def _fixture(name: str) -> dict:
    return load_json(CORPUS / name)


def test_editor_smoke_report_schema_validates():
    schema = load_json(SCHEMA)
    reports = load_fixture_reports(CORPUS)

    assert reports
    for _, report in reports:
        result = schema_validate(report, schema)
        assert result.status == "pass", result.messages


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


def test_validate_all_includes_fixture_editor_smoke():
    result = subprocess.run(
        [sys.executable, str(VALIDATE_ALL)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Editor smoke fixture bridge" in result.stdout
