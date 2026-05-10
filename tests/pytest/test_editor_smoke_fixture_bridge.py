import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from tools.o3de.editor_smoke import (
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


def _write_in_editor_report(env: Mapping[str, str], *, status: str = "pass", exit_code: int = 0) -> subprocess.CompletedProcess[str]:
    report_out = Path(env["MAXINE_EDITOR_SMOKE_REPORT_OUT"])
    payload = json.loads(Path(env["MAXINE_EDITOR_SMOKE_REPORT_TEMPLATE"]).read_text(encoding="utf-8"))
    payload.update(
        {
            "status": status,
            "live_editor_execution": True,
            "exit_code": exit_code,
            "editor_python_bindings_available": True,
            "temp_level_path_redacted": "Levels/_maxine_smoke/maxine_smoke_test",
            "entity_smoke": {"status": "pass", "entity_id": "EntityId(1)", "name": "maxine_smoke_entity"},
            "prefab_smoke": {"status": "unavailable", "reason": "not attempted by unit test"},
            "actor_smoke": {"status": "unavailable", "reason": "not attempted by unit test"},
            "component_smoke": {"status": "unavailable", "reason": "not attempted by unit test"},
            "instantiated_entities": [{"name": "maxine_smoke_entity", "components": ["Transform"], "source": "editor_python"}],
            "missing_components": [],
            "errors": [] if status == "pass" else ["MXN_RUNTIME_SMOKE_FAIL"],
            "warnings": [],
        }
    )
    report_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return subprocess.CompletedProcess(args=["Editor.exe"], returncode=exit_code, stdout="editor stdout", stderr="")


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
