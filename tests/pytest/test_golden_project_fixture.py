import json
import os
import subprocess
import sys
from pathlib import Path

from tools.ci.o3de_runner_readiness import build_readiness_report
from tools.ci.run_o3de_integration_suite import run_integration_suite
from tools.o3de.golden_project_fixture import (
    DEFAULT_FIXTURE,
    FIXTURE_DIR,
    SCHEMA_PATH,
    load_fixture_files,
    run_golden_project_fixture,
    validate_golden_project_fixture,
)
from tools.validation.schema_utils import load_json, schema_validate


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "o3de" / "golden_project_fixture.py"
VALIDATE_ALL = REPO_ROOT / "tools" / "validation" / "validate_all.py"


def _unavailable_env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env.pop("O3DE_EDITOR_EXECUTABLE", None)
    env.pop("ASSET_PROCESSOR_BATCH", None)
    env.pop("ASSET_PROCESSOR_BATCH_EXECUTABLE", None)
    env.pop("MAXINE_ALLOW_LIVE_O3DE_COMMANDS", None)
    return env


def _fixture(name: str) -> dict:
    return load_json(FIXTURE_DIR / name)


def test_golden_project_fixture_schema_validates():
    schema = load_json(SCHEMA_PATH)
    fixtures = load_fixture_files(FIXTURE_DIR)

    assert fixtures
    for _, payload in fixtures:
        result = schema_validate(payload, schema)
        assert result.status == "pass", result.messages


def test_golden_project_fixture_default_passes():
    result = run_golden_project_fixture(DEFAULT_FIXTURE)

    assert result["status"] == "pass"
    assert result["mode"] == "fixture"
    assert result["live_o3de_execution"] is False
    assert result["live_asset_processor_batch_execution"] is False
    assert result["live_editor_execution"] is False


def test_golden_project_fixture_all_fixtures_validate():
    result = run_golden_project_fixture(FIXTURE_DIR)

    assert result["status"] == "pass"
    observed = {case["case_id"]: case["observed_status"] for case in result["cases"]}
    assert observed["maxine-golden-project"] == "pass"
    assert observed["maxine-golden-project.invalid-unsafe-path"] == "fail"
    assert observed["maxine-golden-project.invalid-cache-heuristic"] == "fail"
    assert observed["maxine-golden-project.invalid-missing-prefab"] == "fail"
    assert observed["maxine-golden-project.local-unavailable"] == "skipped"


def test_golden_project_fixture_unsafe_path_fails():
    result = validate_golden_project_fixture(_fixture("maxine-golden-project.invalid-unsafe-path.fail.json"))

    assert result.status == "fail"
    assert "MXN_PATH_UNSAFE" in result.error_codes


def test_golden_project_fixture_cache_heuristic_release_fails():
    result = validate_golden_project_fixture(_fixture("maxine-golden-project.invalid-cache-heuristic.fail.json"))

    assert result.status == "fail"
    assert "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN" in result.error_codes


def test_golden_project_fixture_missing_prefab_fails():
    result = validate_golden_project_fixture(_fixture("maxine-golden-project.invalid-missing-prefab.fail.json"))

    assert result.status == "fail"
    assert "MXN_ASSET_PRODUCT_MISSING" in result.error_codes


def test_golden_project_fixture_local_unavailable_skips_non_strict(tmp_path):
    result = run_golden_project_fixture(
        DEFAULT_FIXTURE,
        check_local_readiness=True,
        strict=False,
        env=_unavailable_env(tmp_path),
    )

    assert result["status"] == "skipped"
    assert result["mode"] == "unavailable"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result["warnings"]
    assert result["live_o3de_execution"] is False


def test_golden_project_fixture_local_unavailable_fails_strict(tmp_path):
    result = run_golden_project_fixture(
        DEFAULT_FIXTURE,
        check_local_readiness=True,
        strict=True,
        env=_unavailable_env(tmp_path),
    )

    assert result["status"] == "fail"
    assert result["mode"] == "unavailable"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result["errors"]


def test_golden_project_fixture_temp_level_policy_forbids_production_level():
    payload = _fixture("maxine-golden-project.fixture.json")
    payload["temp_level_policy"]["level_root"] = "Levels/Production"

    result = validate_golden_project_fixture(payload)

    assert result.status == "fail"
    assert "MXN_PATH_UNSAFE" in result.error_codes


def test_golden_project_fixture_no_absolute_output_roots_by_default():
    payload = _fixture("maxine-golden-project.fixture.json")
    payload["expected_artifact_paths"]["logs"] = "C:/temp/maxine/logs"

    result = validate_golden_project_fixture(payload)

    assert result.status == "fail"
    assert "MXN_PATH_UNSAFE" in result.error_codes


def test_golden_project_fixture_cli_validates_all_fixtures():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--fixtures", str(FIXTURE_DIR)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Golden project fixture: pass" in result.stdout
    assert "maxine-golden-project.invalid-cache-heuristic" in result.stdout


def test_golden_project_fixture_cli_strict_readiness_fails_when_unavailable(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--fixture", str(DEFAULT_FIXTURE), "--check-local-readiness", "--strict"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=_unavailable_env(tmp_path),
    )

    assert result.returncode != 0
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout
    assert "live_o3de_execution: false" in result.stdout


def test_validate_all_includes_golden_project_fixture():
    result = subprocess.run(
        [sys.executable, str(VALIDATE_ALL)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "O3DE golden project fixture" in result.stdout


def test_runner_readiness_mentions_golden_project_fixture(tmp_path):
    report = build_readiness_report(env=_unavailable_env(tmp_path))

    assert report["golden_project_fixture"]["present"] is True
    assert report["golden_project_fixture"]["path"].endswith("examples/o3de-golden-project/maxine-golden-project.fixture.json")


def test_integration_suite_dry_run_mentions_golden_project_fixture(tmp_path):
    report = run_integration_suite(mode="dry_run", env=_unavailable_env(tmp_path))

    assert report["golden_project_fixture_ref"].endswith("examples/o3de-golden-project/maxine-golden-project.fixture.json")
    assert report["live_o3de_execution"] is False
